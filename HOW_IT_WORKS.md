# How It Works · Compliance Automation Engine

**Author: Arun Prabakar Vadaseri Rajendran**

A complete technical and conceptual walkthrough of the Compliance Automation Engine — what every part does, how each piece connects to the others, and why it was designed this way.

---

## What the system does

The engine takes two inputs: a folder of CRA regulatory PDFs and a plain-text client business profile. It extracts the text from every PDF, combines it with the client profile, and sends both to an AI model with a structured prompt. The AI responds with exactly five compliance risk items, each tagged with a severity level, a CRA reference, an explanation of why this specific client is exposed, and a concrete next action. Those five risks are saved to disk as a JSON report and a human-readable summary, logged to a SQLite audit database, and displayed in a Streamlit dashboard. An optional n8n schedule converts the summary into a draft client email and saves it straight to Gmail Drafts.

The AI connection is **bring-your-own-key and bring-your-own-model**: the user enters their API key and model name in the dashboard. Nothing is hardcoded — no default models exist anywhere in the codebase. This means any current or future model from any provider works without touching the code.

A **demo mode** is built in: if no real analysis has been run yet, the dashboard loads a pre-built sample report from `data/demo_report.json`. This populates the full dashboard for anyone opening the Streamlit Cloud link without needing an API key.

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
               (build prompt, call AI via ai_router, parse JSON)
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
                    (demo fallback: data/demo_report.json
                     shown when outputs/reports/ is empty)
                            |
                            v (optional, via n8n)
               email draft saved to Gmail Drafts
```

---

## Components

### `scripts/ai_router.py` · Central provider router

All AI calls go through one function: `call_ai(prompt, provider, api_key, model, custom_base_url)`. This keeps credentials and model names out of every other script and makes swapping providers trivial.

`PROVIDER_CONFIG` stores only the fixed infrastructure for each provider: the base URL for the API endpoint and which SDK to use. **Model names are not stored here.** The user supplies the model name at runtime through the dashboard, which passes it through to every script via the `--model` command-line argument.

```python
PROVIDER_CONFIG = {
    "groq":       {"base_url": "https://api.groq.com/openai/v1", "sdk": "openai"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1",   "sdk": "openai"},
    "openai":     {"base_url": None,                              "sdk": "openai"},
    "anthropic":  {"base_url": None,                              "sdk": "anthropic"},
    "custom":     {"base_url": None,                              "sdk": "openai"},
}
```

Groq, OpenRouter, OpenAI, and Custom all use the OpenAI SDK with a `base_url` override, since they follow the same chat-completions format. Anthropic uses its own SDK. The Custom provider additionally accepts a user-supplied `custom_base_url`, so any OpenAI-compatible endpoint works without code changes.

`call_ai()` raises a `ValueError` if no model name is provided, ensuring the requirement is enforced at the lowest level. It also handles retries (up to three on timeout) and raises typed exceptions for authentication and network failures.

`get_model_name(provider, model)` returns the model string that appears on reports and in the audit log.

### `scripts/01_test_connection.py` · Connection validator

Accepts `--provider`, `--key`, and `--model` on the command line (all required). Sends a minimal prompt (`"Respond with exactly: Connected."`) through `call_ai()` and prints a confirmation line. Exit code 0 means success; exit code 1 means failure with a clear error message. The dashboard calls this as a subprocess when the user clicks Connect.

### `scripts/02_extract_pdf.py` · PDF extractor

Uses `pypdf` to open every PDF in `docs/regulations/` and read it page by page. Pages are joined with a separator header (`=== SOURCE: filename ===`) so the AI can see which regulation each passage came from. Encrypted PDFs are skipped with a warning; blank pages are skipped silently. A Rich progress bar shows extraction progress.

The result is one combined string passed directly to the analysis engine — no chunking or vector database. The full regulatory context goes to the AI in one prompt. For the document sizes typically used by accounting firms this works well and keeps the architecture simple.

### `scripts/03_analyze_compliance.py` · Analysis engine

Core of the system. Signature: `run_analysis(provider, api_key, model, custom_base_url=None)`.

1. Reads `docs/clients/client_profile.txt`
2. Calls `extract_text_from_folder("docs/regulations/")` for the combined PDF text
3. Builds a structured prompt: role + regulatory context + client profile + exact JSON schema
4. Calls `call_ai()` with a Rich spinner showing provider and model
5. Parses the response with `parse_json_response()` — tries `json.loads()` first, then strips markdown code fences as a fallback
6. Saves `outputs/reports/report_YYYYMMDD_HHMMSS.json` and a companion `_summary.txt`
7. Inserts an audit row into `database/audit.db`
8. Prints a colour-coded Rich table: HIGH in red, MEDIUM in yellow, LOW in green

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

Fixing the output count at five and specifying the schema in the prompt makes the response machine-readable without post-processing heuristics.

### `scripts/04_run_pipeline.py` · Orchestrator

Accepts `--provider`, `--key`, and `--model` (all required) plus optional `--base-url`. Runs pre-flight checks (provider is recognised, at least one PDF exists, client profile exists) then calls `run_analysis()`. Prints a Rich summary box showing the report path, model used, and wall-clock runtime. This is the entry point for both the dashboard (subprocess) and the n8n schedule (Execute Command node).

### `scripts/05_dashboard.py` · Streamlit dashboard

The dashboard is a single-file Streamlit app with full custom CSS and a light/auto/dark theme toggle.

**Sidebar: step 1 — Connect your AI**

A selectbox lets the user pick a provider. A **Model name** text input appears for all providers — this is where the user types the model they want to use. Choosing *Custom* additionally reveals a Base URL field. An API key field (password type) sits below. Clicking Connect runs `01_test_connection.py` as a subprocess; success stores provider, model, and key in `st.session_state` for the rest of the session — nothing is written to disk.

**Sidebar: step 2 — Upload and analyse**

A file uploader accepts a `.txt` client profile. The Analyse Now button is disabled until connected. On click, `04_run_pipeline.py` runs as a subprocess with provider, key, and model passed as arguments.

**Main area: Latest Report tab**

Loads the most recent JSON from `outputs/reports/`. If that folder is empty, falls back to `data/demo_report.json`. When demo data is shown a blue info banner notifies the user. Once a real analysis is run, the live results replace the demo automatically.

Renders:
- Three KPI cards: Total Risks, High Severity (error colour), Medium Severity (warning colour)
- A horizontal Plotly bar chart, one bar per risk, coloured by severity, transparent background that adapts to the active theme
- A styled risk card per finding: CRA reference, client exposure, and an action box with a left-side colour stripe

**Main area: Audit Trail tab**

Reads `database/audit.db` and displays the analyses table as a dataframe. Creates the database and table if they do not exist, so the tab never crashes on a fresh install.

**Appearance toggle**

A three-way Light / Auto / Dark pill at the bottom of the sidebar. Auto reads the OS preference via `prefers-color-scheme`. All colours are CSS custom properties on `:root`; the `build_theme_css()` function regenerates the full `<style>` block at render time. A JS snippet injected via `components.html()` handles a handful of inline overrides that Streamlit's emotion CSS requires `!important` priority for.

---

## The AI prompt design

```
You are a Senior Compliance Auditor with expertise in Canadian tax law (CRA).

REGULATORY DOCUMENTS:
{combined PDF text}

CLIENT PROFILE:
{client_profile.txt content}

Identify exactly 5 compliance risk areas for this client based on the documents.
...
Return ONLY valid JSON, no other text:
{"compliance_risks": [...]}
```

Fixing the output count at five and requiring a specific JSON schema means the response is machine-readable every time. The `parse_json_response()` fallback handles the edge case where a model wraps its output in triple backticks despite being told not to.

---

## Security design

- **No API keys stored:** not in `.env`, not in any config file, not in the repository. The key is held in `st.session_state` for the browser session and passed to subprocess arguments in memory only.
- **No model names stored:** the user's model choice is also session-only, keeping the tool neutral across providers and versions.
- **`.gitignore`** excludes `database/`, `outputs/`, and `.env`. The two sample CRA PDFs are explicitly un-ignored so the demo works out of the box.
- The Streamlit session ends when the browser tab closes, at which point both the key and model string are gone.

---

## Demo mode

`data/demo_report.json` is a pre-built compliance report for a fictional client (Meridian Advisory Group Inc.) that ships with the repository. The dashboard loads it automatically when `outputs/reports/` is empty. This means anyone opening the Streamlit Cloud link sees a fully populated dashboard immediately — all KPI cards, the risk chart, and all five risk cards — without needing an API key. As soon as a real analysis is run, the live report replaces the demo.

---

## The n8n automation

`n8n/compliance_workflow.json` is a five-node workflow:

| Node | Type | What it does |
|------|------|--------------|
| 1 | Schedule Trigger | Fires daily at 9:00 AM |
| 2 | Execute Command | Runs `04_run_pipeline.py --provider … --key … --model …` |
| 3 | Execute Command | Reads the latest `*_summary.txt` from `outputs/reports/` |
| 4 | HTTP Request | Calls any OpenAI-compatible API to draft a client email |
| 5 | Gmail | Saves the draft to Gmail Drafts via OAuth2 — never auto-sends |

**Gmail account setup:** In n8n, open the Gmail node and click *Add Credential* → *Gmail OAuth2*. A Google sign-in popup appears; sign in with the Gmail account you want drafts to appear in. n8n stores only the OAuth token — not your password. The draft is created with no "To" recipient, so you open it in Gmail, add the client's email address, review the content, and send when ready.

The email node uses a plain HTTP Request rather than a proprietary n8n AI node, so it works with whichever provider and model the team already uses. Update the `YOUR_PROVIDER`, `YOUR_API_KEY`, and `YOUR_MODEL_NAME` placeholders in nodes 2 and 4 after importing the workflow.

---

## Extending the system

**Adding a new AI provider:** Add an entry to `PROVIDER_CONFIG` in `ai_router.py` with the `base_url` and `sdk` keys. If the provider follows the OpenAI format set `"sdk": "openai"`. No model name goes here — the user supplies it at runtime.

**Changing the risk schema:** Edit the JSON template in the prompt inside `_build_prompt()` in `03_analyze_compliance.py` and update the display code in `05_dashboard.py`.

**Changing the number of risks:** Change "exactly 5" in the prompt in `03_analyze_compliance.py`.

**Adding more clients:** The client profile is a plain `.txt` file. Upload a different one for each session via the dashboard sidebar, or pass a path argument directly to the pipeline scripts.

---

*Compliance Automation Engine · Arun Prabakar Vadaseri Rajendran · [linkedin.com/in/arun-prabakar-vadaseri-rajendran](https://www.linkedin.com/in/arun-prabakar-vadaseri-rajendran)*
