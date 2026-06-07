# How It Works · Compliance Automation Engine

**Author: Arun Prabakar Vadaseri Rajendran**

This document is a complete technical and conceptual walkthrough of the Compliance Automation Engine. It explains what every part of the system does, how each piece connects to the others, and why it was designed this way.

---

## What the system does

The engine takes two inputs: a folder of CRA regulatory PDFs and a plain-text client business profile. It extracts the text from every PDF, combines it with the client profile, and sends both to an AI model with a structured prompt. The AI responds with exactly five compliance risk items, each tagged with a severity level, a CRA reference, an explanation of why this specific client is exposed, and a concrete next action. Those five risks are saved to disk as a JSON report and a human-readable summary, logged to a SQLite audit database, and displayed in a Streamlit dashboard. An optional n8n schedule can also convert the summary into a draft client email and save it straight to Gmail Drafts.

The AI connection is bring-your-own-key: the user enters their own API key in the dashboard. The key lives only in the browser session and is never written to disk, environment variables, or the repository.

---

## Data flow

```
docs/regulations/*.pdf          docs/clients/client_profile.txt
         |                                      |
         v                                      v
  02_extract_pdf.py                   (read directly)
  (extract + combine PDF text)
         |                                      |
         +------------------+-------------------+
                            |
                            v
               03_analyze_compliance.py
               (build prompt, call AI, parse JSON)
                            |
              +-------------+-------------+
              |             |             |
              v             v             v
         JSON report   text summary   audit row
         (outputs/     (outputs/      (database/
          reports/)     reports/)      audit.db)
                            |
                            v
               05_dashboard.py (Streamlit UI)
               shows risks, chart, audit trail
                            |
                            v (optional, via n8n)
               email draft saved to Gmail Drafts
```

---

## Components

### `scripts/ai_router.py` · Central provider router

All AI calls in the project go through one function: `call_ai(prompt, provider, api_key)`. This keeps credentials out of every other script and makes it trivial to swap providers.

The router holds a `PROVIDER_CONFIG` dictionary with base URLs and model names for each supported provider. For Groq, OpenRouter, OpenAI, and Custom it uses the `openai` SDK with a custom `base_url`, since all four follow the OpenAI API format. For Anthropic it uses the `anthropic` SDK directly. The Custom provider accepts a `custom_base_url` and `custom_model` at runtime, which means any OpenAI-compatible endpoint in existence can be used without touching the code.

The router also handles retries (up to three attempts on timeout) and raises typed exceptions for authentication failures and network errors so callers can give clear feedback to the user.

A companion function `get_model_name(provider, custom_model)` returns the model string that goes on reports and in the audit log.

### `scripts/01_test_connection.py` · Connection validator

Accepts `--provider`, `--key`, and optionally `--base-url` and `--model` on the command line. Sends a minimal prompt (`"Respond with exactly: Connected."`) through `call_ai()` and prints a confirmation line. Exit code 0 means success; exit code 1 means failure with a clear error message. The dashboard calls this as a subprocess when the user clicks Connect, so a green or red status message appears without any async complexity.

### `scripts/02_extract_pdf.py` · PDF extractor

Uses `pypdf` (not PyPDF2) to open every PDF in `docs/regulations/` and read it page by page. Pages are joined with a separator header (`=== SOURCE: filename ===`) so the AI can see which regulation each passage came from. Encrypted PDFs are skipped with a warning; blank pages are skipped silently. A Rich progress bar shows `Reading page N of total: filename` so long extractions are visible.

The result is one combined string passed directly to the analysis engine. This design avoids any chunking or vector database complexity: the full regulatory context goes to the AI in one prompt. For the document sizes typically used by accounting firms this works well, and it keeps the architecture simple.

### `scripts/03_analyze_compliance.py` · Analysis engine

This is the core of the system. It:

1. Reads `docs/clients/client_profile.txt`
2. Calls `extract_text_from_folder("docs/regulations/")` to get the combined PDF text
3. Builds a structured prompt that instructs the AI to act as a Senior Compliance Auditor with CRA expertise and return exactly five risks in a specific JSON schema
4. Calls `call_ai()` with a Rich spinner showing which provider and model are in use
5. Parses the response with `parse_json_response()`, which tries `json.loads()` first and then falls back to a regex that strips markdown code fences in case the AI wrapped its output in triple backticks
6. Saves the result to `outputs/reports/report_YYYYMMDD_HHMMSS.json` and a companion `_summary.txt`
7. Inserts an audit row into `database/audit.db`
8. Prints a colour-coded Rich table: HIGH risks in red, MEDIUM in yellow, LOW in green

The JSON schema enforced in the prompt:

```json
{
  "compliance_risks": [
    {
      "title": "four words max",
      "severity": "HIGH | MEDIUM | LOW",
      "cra_reference": "specific CRA section",
      "client_exposure": "why this client is at risk",
      "action": "one concrete next step"
    }
  ]
}
```

### `scripts/04_run_pipeline.py` · Orchestrator

Accepts `--provider` and `--key` on the command line. Runs pre-flight checks (provider is recognised, at least one PDF exists, client profile exists) and then calls `run_analysis()` directly (not as a subprocess). Prints a Rich summary box at the end showing the report path, model used, and wall-clock runtime. This is the entry point for both the dashboard (which spawns it as a subprocess) and the n8n schedule (which runs it via an Execute Command node).

### `scripts/05_dashboard.py` · Streamlit dashboard

The dashboard is a single-file Streamlit app. It is organised into these areas:

**Sidebar: step 1 - Connect your AI**

A selectbox lets the user pick a provider. Choosing "Custom" reveals two extra fields for a base URL and model name. An API key field (password type) sits below. When the user clicks Connect, the dashboard spawns `01_test_connection.py` as a subprocess and reads the exit code. On success it stores the provider and key in `st.session_state` for the rest of the session.

**Sidebar: step 2 - Upload and analyse**

A file uploader accepts a `.txt` client profile and saves it to `docs/clients/client_profile.txt`. The Analyse Now button is disabled until a connection is established. On click, the dashboard spawns `04_run_pipeline.py` as a subprocess and shows a spinner while it runs.

**Main area: Latest Report tab**

Loads the most recent JSON file from `outputs/reports/`. If none exists, shows an onboarding message. Otherwise it renders:
- Three metric cards: Total Risks, High Severity (red delta), Medium Severity (amber delta)
- A horizontal Plotly bar chart with one bar per risk, coloured by severity (red / amber / green) and a transparent background that adapts to the active theme
- An expandable card per risk showing the CRA reference, client exposure, and a green-highlighted action box

**Main area: Audit Trail tab**

Reads `database/audit.db` and shows the analyses table as a dataframe. Creates the database and table if they do not exist yet, so the tab never crashes on a fresh install.

**Appearance toggle**

A three-way Light / Auto / Dark pill at the bottom of the sidebar switches the CSS custom properties that control every colour in the app. Auto reads the operating system preference via `prefers-color-scheme`. The icons on the pill are rendered with Material Symbols Outlined via CSS `::after` pseudo-elements so no image assets are needed.

**Theme system**

All colours are CSS custom properties on `:root`. The `build_theme_css()` function generates the full `<style>` block at render time based on the current `theme_mode` session value. A JS snippet injected via `components.html()` applies a handful of inline styles that override Streamlit's emotion CSS where `!important` in a stylesheet is not enough.

---

## The AI prompt design

The prompt is a role + context + schema instruction in one message:

```
You are a Senior Compliance Auditor with expertise in Canadian tax law (CRA).

REGULATORY DOCUMENTS:
{combined PDF text}

CLIENT PROFILE:
{client_profile.txt content}

Identify exactly 5 compliance risk areas...
Return ONLY valid JSON, no other text:
{"compliance_risks": [...]}
```

Fixing the output count at five and specifying the JSON schema in the prompt means the response is machine-readable without any post-processing heuristics. The `parse_json_response()` fallback handles the edge case where a model wraps its output in a markdown code block despite being told not to.

---

## Security design

- No API keys are ever stored: not in `.env`, not in any config file, not in the repository. The key is passed from the user's browser session to subprocess arguments in memory.
- The `.gitignore` excludes `database/`, `outputs/`, and all PDF files (with a negation rule to keep the two sample CRA PDFs that ship with the repo for demo purposes).
- The Streamlit session ends when the browser tab closes, at which point the key is gone.

---

## The n8n automation

`n8n/compliance_workflow.json` is a five-node workflow:

| Node | Type | What it does |
|------|------|-------------|
| 1 | Schedule Trigger | Fires daily at 9:00 AM |
| 2 | Execute Command | Runs `04_run_pipeline.py` with provider and key |
| 3 | Read File | Reads the latest `*_summary.txt` from `outputs/reports/` |
| 4 | HTTP Request | Calls any OpenAI-compatible API to draft a client email from the summary |
| 5 | Gmail | Saves the draft to Gmail Drafts via OAuth |

The email node uses a plain HTTP Request rather than a proprietary n8n AI node, so it works with whichever provider the team already uses. The draft is never sent automatically; it always lands in Gmail Drafts for human review first.

---

## Extending the system

**Adding a new AI provider**: add an entry to `PROVIDER_CONFIG` in `ai_router.py`. If the provider follows the OpenAI format, set `"sdk": "openai"` and supply the `base_url` and `model`. That is all.

**Changing the risk schema**: edit the JSON template in the prompt inside `run_analysis()` in `03_analyze_compliance.py` and update the display code in `05_dashboard.py`.

**Changing the number of risks**: change "exactly 5" in the prompt and update the assertion in the validation check.

**Adding more clients**: the client profile is a plain `.txt` file. Upload a different one for each session or modify the pipeline to accept a path argument.

---

*Compliance Automation Engine · Arun Prabakar Vadaseri Rajendran · [linkedin.com/in/arun-prabakar-vadaseri-rajendran](https://www.linkedin.com/in/arun-prabakar-vadaseri-rajendran)*
