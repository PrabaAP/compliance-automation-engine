# CLAUDE.md — Compliance Automation Engine
## Autonomous Build Instructions for Claude Code

**Project:** GenAI Compliance & Workflow Automation Engine  
**Author:** Arun Prabakar Vadaseri Rajendran  
**Stack:** Python · Multi-provider AI (user-supplied key) · Streamlit · SQLite · n8n

---

## Model Instructions

| Phase | Task type | Model to use |
|-------|-----------|-------------|
| Planning, architecture, reviewing specs | Thinking/design | `claude-opus-4-6` |
| Writing code, scripts, configs | Execution | `claude-sonnet-4-6` |
| Debugging, fixing errors | Execution | `claude-sonnet-4-6` |
| Documentation | Execution | `claude-sonnet-4-6` |

Switch with `/model claude-opus-4-6` or `/model claude-sonnet-4-6` before each phase.

---

## Project Context

A compliance automation engine for accounting firms. Reads CRA regulatory PDFs, cross-references against a client business profile, produces a 5-point compliance risk checklist, drafts a client email, saves it to Gmail via n8n.

**AI connection model:** The user enters their own API key inside the Streamlit app. No API key is stored in `.env`, code, or the repository. The key lives in `st.session_state` for the session only.

**Supported providers — user picks one at setup:**

| Provider | Free tier? | Model used | Notes |
|----------|-----------|------------|-------|
| **Groq** | ✅ Yes — no credit card | `llama-3.3-70b-versatile` | 14,400 req/day free |
| **OpenRouter** | ✅ Yes — no credit card | `meta-llama/llama-3.3-70b-instruct:free` | Free models available |
| **Anthropic** | ❌ Pay-per-use | `claude-opus-4-6` | Needs API billing |
| **OpenAI** | ❌ Pay-per-use | `gpt-4o` | Needs API billing |
| **Custom** | Depends on provider | User-specified | Any OpenAI-compatible endpoint |

**The Custom option** lets any user bring any provider not listed above — Mistral, Together AI, Perplexity, Azure OpenAI, any local server — by entering their own base URL and model name. Since most modern AI providers support the OpenAI API format, this covers virtually every provider in existence.

**Implementation note:** Groq, OpenRouter, OpenAI, and Custom all use the OpenAI-compatible SDK. Only Anthropic needs its own SDK. `requirements.txt` only needs `openai` and `anthropic`.

**Critical constraints:**
- No API keys in `.env`, code, or repo — ever
- No Ollama, no local AI
- No university, course, or portfolio project labels anywhere
- Author attribution: "Arun Prabakar Vadaseri Rajendran" only

---

## Environment

**Pre-conditions:**
- Python 3.9+ available
- CRA PDFs exist in `docs/regulations/` (at least one)
- `docs/clients/client_profile.txt` exists

**Folder structure already exists:**
```
Project2_Compliance_Automation/
├── docs/regulations/      ← CRA PDFs
├── docs/clients/          ← client_profile.txt
├── scripts/               ← you create all scripts here
├── outputs/reports/       ← generated JSON and summaries
├── outputs/emails/        ← email drafts
├── database/              ← SQLite audit DB
└── n8n/                   ← workflow JSON export
```

---

## Phase 1 — Planning (use claude-opus-4-6)

Switch: `/model claude-opus-4-6`

Before writing any code:
1. Read `docs/clients/client_profile.txt` — understand its structure
2. List files in `docs/regulations/` — confirm at least one PDF exists
3. Review the full build plan below and flag any ambiguity
4. Confirm understanding before switching to Sonnet

---

## Phase 2 — Setup (switch to claude-sonnet-4-6)

Switch: `/model claude-sonnet-4-6`

### 2a. `requirements.txt`
```
openai
anthropic
pypdf
pandas
rich
streamlit
plotly
python-dotenv
requests
```

### 2b. `scripts/01_test_connection.py`

```python
"""
Tests AI provider connection with a given API key.
Called by the dashboard to validate before running analysis.
Usage: python scripts/01_test_connection.py --provider groq --key YOUR_KEY
"""
```

- Accepts `--provider`, `--key`, and optionally `--base-url` and `--model` as CLI arguments
- Sends test prompt: `"Respond with exactly: Connected."`
- Calls `call_ai()` from `scripts/ai_router.py`, passing custom args if provider is "custom"
- Prints: `"✅ {provider} connected — model: {model_name}"`
- Exits with code 1 on failure, prints the error clearly

### 2c. `scripts/ai_router.py`

```python
"""
Central AI routing module. All scripts import call_ai() from here.
No API keys are stored here — key is always passed as a parameter.
"""
```

**`call_ai(prompt: str, provider: str, api_key: str) -> str`:**

```python
PROVIDER_CONFIG = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "sdk": "openai"
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "sdk": "openai"
    },
    "openai": {
        "base_url": None,
        "model": "gpt-4o",
        "sdk": "openai"
    },
    "anthropic": {
        "model": "claude-opus-4-6",
        "sdk": "anthropic"
    },
    "custom": {
        "base_url": None,   # populated at runtime from user input
        "model": None,      # populated at runtime from user input
        "sdk": "openai"     # all custom providers must be OpenAI-compatible
    }
}
```

**`call_ai(prompt, provider, api_key, custom_base_url=None, custom_model=None) -> str`:**
- For `sdk: "openai"` providers: use `openai.OpenAI(api_key=key, base_url=base_url)` → `client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}])` → return `response.choices[0].message.content`
- For provider `"custom"`: use `custom_base_url` and `custom_model` instead of config values — raise `ValueError` if either is None or empty
- For `sdk: "anthropic"`: use `anthropic.Anthropic(api_key=key)` → `client.messages.create(model=model, max_tokens=2048, messages=[...])` → return `message.content[0].text`
- Retry up to 3 times on timeout (5s wait between retries)
- Raise `ValueError` with provider name and clear message on auth failure (401)
- Raise `ConnectionError` on network failure

**`get_model_name(provider, custom_model=None) -> str`:** returns model string; for "custom" returns `custom_model`.

**Test after creating:**
```bash
# Replace with your actual Groq key (free at console.groq.com)
python scripts/01_test_connection.py --provider groq --key YOUR_GROQ_KEY
```
Expected: `✅ groq connected — model: llama-3.3-70b-versatile`

---

## Phase 3 — PDF Extraction (claude-sonnet-4-6)

### `scripts/02_extract_pdf.py`

```python
"""
Extracts and combines text from all PDFs in a folder.
Importable: from scripts.extract_pdf import extract_text_from_folder
"""
```

- **`extract_text_from_folder(folder_path: str) -> str`**
- Uses `pypdf` (not PyPDF2)
- Separates files with: `"\n\n=== SOURCE: {filename} ===\n\n"`
- Rich progress bar: `"Reading page {n} of {total} — {filename}"`
- Skip encrypted PDFs (warn), skip blank pages (silent)
- Raises `FileNotFoundError` if folder has no PDFs
- If run directly: extract from `docs/regulations/`, print character count + first 300 chars

**Test:**
```bash
python scripts/02_extract_pdf.py
```
Expected: character count > 0. Do not proceed until this passes.

---

## Phase 4 — Compliance Analysis Engine (claude-sonnet-4-6)

### `scripts/03_analyze_compliance.py`

```python
"""
Core analysis. Sends PDFs + client profile to AI, returns structured risk JSON.
Requires provider and api_key to be passed — never reads them from env.
"""
```

**Function `parse_json_response(text: str) -> dict`:**
- Try `json.loads(text)` first
- If fails: regex to extract block between ` ```json ` and ` ``` `, try again
- If still fails: raise `ValueError("Could not parse AI response as JSON")`

**Function `run_analysis(provider: str, api_key: str) -> dict`:**

1. Read `docs/clients/client_profile.txt`
2. Call `extract_text_from_folder("docs/regulations/")`
3. Extract `client_name` from line starting with "Company Name:" in profile
4. Build and send this prompt via `call_ai(prompt, provider, api_key)`:

```
You are a Senior Compliance Auditor with expertise in Canadian tax law (CRA).

REGULATORY DOCUMENTS:
{pdf_text}

CLIENT PROFILE:
{client_profile}

Identify exactly 5 compliance risk areas for this client based on the documents.
For each risk provide:
- title: 4 words maximum
- severity: HIGH, MEDIUM, or LOW
- cra_reference: specific CRA section from the documents above
- client_exposure: one sentence — why THIS client is specifically at risk
- action: one concrete next step

Return ONLY valid JSON, no other text:
{"compliance_risks": [{"title":"...","severity":"...","cra_reference":"...","client_exposure":"...","action":"..."}, ...]}
```

5. Show rich spinner: `"Sending to {provider} ({get_model_name(provider)})..."`
6. Parse with `parse_json_response()`
7. Save to `outputs/reports/report_{YYYYMMDD_HHMMSS}.json`:
   ```json
   {
     "client_name": "...",
     "run_date": "...",
     "provider": "groq",
     "model": "llama-3.3-70b-versatile",
     "compliance_risks": [...]
   }
   ```
8. Save summary to `outputs/reports/report_{timestamp}_summary.txt`:
   ```
   SEVERITY | Title | Action
   HIGH | Contractor Misclassification | Review contractor agreements...
   ```
9. Save audit row to `database/audit.db`:
   ```sql
   CREATE TABLE IF NOT EXISTS analyses (
     id INTEGER PRIMARY KEY AUTOINCREMENT,
     run_date TEXT,
     client_name TEXT,
     provider TEXT,
     model TEXT,
     pdf_count INTEGER,
     risk_count INTEGER,
     report_file TEXT
   )
   ```
10. Print rich colour-coded table: HIGH=red MEDIUM=yellow LOW=green

---

## Phase 5 — Pipeline Runner (claude-sonnet-4-6)

### `scripts/04_run_pipeline.py`

```python
"""
Master orchestrator. Called by Streamlit dashboard and n8n.
provider and api_key must be passed as arguments.
Usage: python scripts/04_run_pipeline.py --provider groq --key YOUR_KEY
"""
```

- Accepts `--provider` and `--key` CLI args
- Pre-flight checks (stop on failure):
  - Provider is in the supported list
  - At least one PDF in `docs/regulations/`
  - `docs/clients/client_profile.txt` exists
- Calls `run_analysis(provider, api_key)` directly (not subprocess)
- Rich progress display with ✅ per step
- Final summary box:
  ```
  ┌────────────────────────────────────────────────────────┐
  │  ✅ Report:   outputs/reports/report_20240606.json     │
  │  ✅ Summary:  outputs/reports/report_20240606_sum.txt  │
  │  🤖 Provider: groq (llama-3.3-70b-versatile)          │
  │  ⏱  Runtime:  42.3 seconds                            │
  └────────────────────────────────────────────────────────┘
  ```

---

## Phase 6 — Dashboard (claude-sonnet-4-6)

> Step 6.1 (Claude Design) is done by the user in the Claude Design web app.
> Implement based on the handoff bundle, or use the spec below if not yet received.

### `scripts/05_dashboard.py`

**Constants:**
```python
CHART_BG   = "rgba(0,0,0,0)"
GRID_COLOR = "rgba(128,128,128,0.15)"
AXIS_STYLE = dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)
```

**Page config:**
```python
st.set_page_config(page_title="Compliance Review Engine", layout="wide", page_icon="⚖️")
```

**Session state initialisation at top:**
```python
if "provider" not in st.session_state:
    st.session_state.provider = None
if "api_key" not in st.session_state:
    st.session_state.api_key = None
if "connected" not in st.session_state:
    st.session_state.connected = False
```

**Sidebar — Connection Setup:**

```python
st.sidebar.title("⚖️ Compliance Engine")
st.sidebar.markdown("---")
st.sidebar.subheader("1. Connect Your AI")
```

Provider selector:
```python
provider = st.sidebar.selectbox(
    "AI Provider",
    options=["groq", "openrouter", "anthropic", "openai", "custom"],
    format_func=lambda x: {
        "groq":       "🟢 Groq — Free (Llama 3.3 70B)",
        "openrouter": "🟢 OpenRouter — Free tier available",
        "anthropic":  "Claude (Anthropic API)",
        "openai":     "GPT-4o (OpenAI API)",
        "custom":     "➕ Custom — Any OpenAI-compatible provider"
    }[x]
)
```

If `provider == "custom"`, show two extra fields:
```python
custom_base_url = st.sidebar.text_input("API Base URL", placeholder="https://api.yourprovider.com/v1")
custom_model    = st.sidebar.text_input("Model name",   placeholder="e.g. mistral-large, llama-3...")
```
Store both in `st.session_state`.

API key input (shown for all providers):
```python
key_label = {
    "groq":       "Groq API Key (free at console.groq.com)",
    "openrouter": "OpenRouter API Key (free at openrouter.ai)",
    "anthropic":  "Anthropic API Key",
    "openai":     "OpenAI API Key",
    "custom":     "API Key for your provider"
}
api_key = st.sidebar.text_input(key_label[provider], type="password")
```

Connect button:
- On click: call `01_test_connection.py` as subprocess, passing `--provider`, `--key`, and if custom: `--base-url` and `--model`
- If exit code 0: set `st.session_state.connected = True`, store provider/key/custom fields, show `st.sidebar.success("✅ Connected")`
- If exit code 1: show `st.sidebar.error("Connection failed — check your key and URL")`

After connection:
```python
st.sidebar.markdown("---")
st.sidebar.subheader("2. Upload Client Profile")
uploaded = st.sidebar.file_uploader("Client profile (.txt)", type=["txt"])
st.sidebar.button("▶ Analyse Now", disabled=not st.session_state.connected)
```

On Analyse click:
- Save uploaded file to `docs/clients/client_profile.txt`
- Run `scripts/04_run_pipeline.py --provider {provider} --key {api_key}` as subprocess
- Show `st.spinner(f"Analysing with {provider}...")`
- On completion: `st.success("Analysis complete — see Latest Report tab")`

**Main area — two tabs:**

TAB 1 "📋 Latest Report":
- Load most recent `outputs/reports/*.json`
- If none: `st.info("Connect your AI and run your first analysis using the sidebar.")`
- 3 metric cards: Total Risks, High Severity (red delta), Medium Severity (orange delta)
- Horizontal Plotly bar: one bar per risk, HIGH=#EF4444, MEDIUM=#F59E0B, LOW=#10B981, `plot_bgcolor=CHART_BG, paper_bgcolor=CHART_BG, xaxis=AXIS_STYLE, yaxis=AXIS_STYLE`
- `st.expander` per risk: Title (bold), CRA Reference (italic), Client Exposure, Action (green callout)

TAB 2 "📁 Audit Trail":
- Load `database/audit.db` analyses table
- Show as `st.dataframe`: Date | Client | Provider | Model | PDFs | Risks Found
- Create table if DB doesn't exist

**Footer:**
```python
st.caption("Compliance Automation Engine — **Arun Prabakar Vadaseri Rajendran** · linkedin.com/in/arun-prabakar-vadaseri-rajendran")
```

**Test:**
```bash
streamlit run scripts/05_dashboard.py
```
Expected: provider selector visible, key input works, Connect button validates, Analyse runs full pipeline.

---

## Phase 7 — n8n Workflow (claude-sonnet-4-6)

n8n handles the scheduled email automation. The AI call in n8n uses an HTTP Request node so it works with any provider — no proprietary n8n credential required.

**Build this 5-node workflow:**

**Node 1 — Schedule Trigger**: every day at 9:00 AM

**Node 2 — Execute Command**:
```
cd /Users/[username]/Documents/Claude/Projects/Portfolio/Project2_Compliance_Automation && python scripts/04_run_pipeline.py --provider groq --key YOUR_GROQ_KEY
```
*(User sets their provider and key here — Groq recommended as it's free)*

**Node 3 — Read File**: find and read the latest `*_summary.txt` in `outputs/reports/`

**Node 4 — HTTP Request** (works for any OpenAI-compatible provider):
- Method: POST
- URL: `https://api.groq.com/openai/v1/chat/completions` *(or provider of choice)*
- Headers: `Authorization: Bearer YOUR_KEY`, `Content-Type: application/json`
- Body (JSON):
  ```json
  {
    "model": "llama-3.3-70b-versatile",
    "messages": [{
      "role": "user",
      "content": "Draft a polite professional compliance review email to a small business client. Risks: {{ $json.fileContent }}. Requirements: open warmly, list only HIGH and MEDIUM risks in plain English, one clarifying question per risk, suggest 30-minute call, under 400 words, sign-off: Compliance Review Team. Return email text only."
    }]
  }
  ```

**Node 5 — Gmail — Create Draft**:
- Connect Google account via OAuth (one-click)
- Subject: `Compliance Review — Items for Discussion`
- Body: `{{ $json.choices[0].message.content }}`

After testing: export as `n8n/compliance_workflow.json`

---

## Phase 8 — Documentation (claude-sonnet-4-6)

### `README.md`
1. Title and author
2. "What this does" — 2 sentences, mention: bring-your-own API key, CRA PDFs, Gmail automation
3. "Supported AI providers" — table showing Groq (free), OpenRouter (free), Anthropic, OpenAI
4. "Setup" — clone repo, `pip install -r requirements.txt`, open dashboard, connect AI
5. "Run" — `streamlit run scripts/05_dashboard.py`
6. Project structure tree
7. "About" — 3 bullets: advisory background, IBM cert, LinkedIn
8. No university, course, or portfolio number mentions

### `USER_GUIDE.md`
Non-technical guide for accounting firm staff:
1. "Quick Start" — 3 steps: open dashboard, connect AI (Groq is free), upload client file, click Analyse
2. "Connecting your AI" — plain English explanation of each provider, recommend Groq for zero cost
3. "Understanding the results" — KPI cards, risk chart, expandable risk cards, audit trail
4. "How the email works" — appears in Gmail Drafts within 60 seconds
5. "Troubleshooting" — 4 common issues
6. "About" — author name and links

---

## Final Verification

```bash
# 1. PDF extraction
python scripts/02_extract_pdf.py

# 2. AI connection (use your actual Groq key)
python scripts/01_test_connection.py --provider groq --key YOUR_KEY

# 3. Full pipeline
python scripts/04_run_pipeline.py --provider groq --key YOUR_KEY

# 4. Validate JSON
python -c "
import json, os
files = sorted([f for f in os.listdir('outputs/reports') if f.endswith('.json')])
data = json.load(open(f'outputs/reports/{files[-1]}'))
assert len(data['compliance_risks']) == 5
for r in data['compliance_risks']:
    assert r['severity'] in ['HIGH','MEDIUM','LOW']
print('✅ 5 valid risks confirmed')
"

# 5. Database check
python -c "
import sqlite3
rows = sqlite3.connect('database/audit.db').execute('SELECT COUNT(*) FROM analyses').fetchone()[0]
print(f'✅ Audit DB: {rows} row(s)')
"

# 6. Dashboard
streamlit run scripts/05_dashboard.py
```

---

## Error Recovery

| Error | Fix |
|-------|-----|
| `401 Unauthorized` | API key is wrong or expired — user re-enters in dashboard |
| `JSONDecodeError` | AI returned markdown-wrapped JSON — add regex strip in `parse_json_response` |
| `No PDFs found` | Confirm CRA PDFs are in `docs/regulations/` |
| `ModuleNotFoundError` | `pip install -r requirements.txt` |
| Empty dashboard | Run `python scripts/04_run_pipeline.py --provider groq --key KEY` first |

---

## GitHub

```bash
echo ".env
__pycache__/
*.pyc
database/
outputs/
docs/regulations/*.pdf" > .gitignore

git init
git add .
git commit -m "Initial commit: GenAI compliance automation engine"
git branch -M main
git remote add origin https://github.com/PrabaAP/compliance-automation-engine.git
git push -u origin main
```

**Streamlit Cloud deployment:**
- share.streamlit.io → connect repo → `scripts/05_dashboard.py`
- No secrets needed — user enters their own key in the app at runtime
