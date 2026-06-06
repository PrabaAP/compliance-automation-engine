# ⚖️ Compliance Automation Engine

**Author: Arun Prabakar Vadaseri Rajendran**

A GenAI tool for accounting and advisory firms. It reads CRA regulatory PDFs, cross-references them against a client's business profile, and produces a five-point compliance risk checklist with a ready-to-send client email. You connect your own AI provider inside the app, and the email can be pushed straight to Gmail Drafts through an n8n workflow.

`Python` · `Streamlit` · `Plotly` · `SQLite` · `n8n` · multi-provider LLM (OpenAI-compatible + Anthropic)

---

## What this does

Drop your CRA regulation PDFs into `docs/regulations/`, upload a client business profile, and the engine asks your chosen AI to act as a senior compliance auditor: it returns exactly five ranked risks — each with a severity, the CRA reference it comes from, why this specific client is exposed, and a concrete next step. Every run is saved as a JSON report, a plain-text summary, and an audit-trail row in SQLite, and an optional n8n schedule turns the summary into a polite client email saved to Gmail Drafts.

The AI connection is **bring-your-own-key**: you enter your key in the dashboard, it lives in the session only, and it is never written to `.env`, to the code, or to the repository.

## Supported AI providers

You pick one provider at setup. Two of them have a genuinely free tier with no credit card required.

| Provider | Free tier | Model | Notes |
|----------|-----------|-------|-------|
| **Groq** | ✅ Yes — no card | `llama-3.3-70b-versatile` | Recommended. 14,400 free requests/day |
| **OpenRouter** | ✅ Yes — no card | `meta-llama/llama-3.3-70b-instruct:free` | Free community models available |
| **Anthropic** | Pay-per-use | `claude-opus-4-8` | Requires API billing |
| **OpenAI** | Pay-per-use | `gpt-4o` | Requires API billing |
| **Custom** | Depends on provider | Your choice | Any OpenAI-compatible endpoint (Mistral, Together, Azure OpenAI, local servers, …) |

The **Custom** option lets you bring almost any provider by entering a base URL and model name, since most modern AI APIs follow the OpenAI format.

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/PrabaAP/compliance-automation-engine.git
cd compliance-automation-engine

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add at least one CRA regulation PDF
#    (place your PDFs in docs/regulations/)

# 4. Launch the dashboard
streamlit run scripts/05_dashboard.py
```

In the dashboard sidebar: choose a provider, paste your API key, click **Connect**, upload a client profile (`.txt`), then click **Analyse Now**. Groq is free and a good starting point.

> **Note:** CRA PDFs, generated reports, and the audit database are intentionally excluded from version control (see `.gitignore`). Add your own regulation PDFs to `docs/regulations/` before running.

## Run

```bash
streamlit run scripts/05_dashboard.py
```

The pipeline also runs from the command line, which is what the n8n schedule calls:

```bash
python scripts/04_run_pipeline.py --provider groq --key YOUR_GROQ_KEY
```

## Project structure

```
compliance-automation-engine/
├── docs/
│   ├── regulations/        CRA regulation PDFs (you supply these)
│   └── clients/            client_profile.txt
├── scripts/
│   ├── ai_router.py            central provider routing (no keys stored)
│   ├── 01_test_connection.py   validate a provider + key
│   ├── 02_extract_pdf.py       combine text from all PDFs
│   ├── 03_analyze_compliance.py AI risk analysis + reports + audit row
│   ├── 04_run_pipeline.py      orchestrator (dashboard + n8n entry point)
│   └── 05_dashboard.py         Streamlit UI
├── outputs/
│   ├── reports/            JSON reports + text summaries
│   └── emails/             email drafts
├── database/
│   └── audit.db            SQLite audit trail
├── n8n/
│   └── compliance_workflow.json   scheduled email automation
├── requirements.txt
├── README.md
└── USER_GUIDE.md
```

## Automated email (n8n)

`n8n/compliance_workflow.json` is a five-node workflow you can import into n8n: a daily 9 AM trigger runs the pipeline, reads the latest summary, asks any OpenAI-compatible API to draft a client email, and saves it to Gmail Drafts via OAuth. Because the AI call uses a plain HTTP Request node, it works with whichever provider you prefer. Edit the project path, API key, and Gmail credential after importing.

## About the author

- Background in professional services and advisory work, where compliance review is a recurring, manual task this project aims to speed up.
- IBM-certified professional in data and AI.
- LinkedIn: [linkedin.com/in/arun-prabakar-vadaseri-rajendran](https://www.linkedin.com/in/arun-prabakar-vadaseri-rajendran)

See [USER_GUIDE.md](USER_GUIDE.md) for a non-technical walkthrough.
