# Compliance Automation Engine

**Author: Arun Prabakar Vadaseri Rajendran**

A GenAI tool for accounting and advisory firms. It reads CRA regulatory PDFs, cross-references them against a client business profile, and produces a five-point compliance risk checklist with a ready-to-send client email. You connect your own AI provider inside the app, and the email can be pushed straight to Gmail Drafts through an n8n workflow.

`Python` · `Streamlit` · `Plotly` · `SQLite` · `n8n` · multi-provider LLM (OpenAI-compatible + Anthropic)

---

## What this does

Drop your CRA regulation PDFs into `docs/regulations/`, upload a client business profile, and the engine asks your chosen AI to act as a senior compliance auditor: it returns exactly five ranked risks, each with a severity, the CRA reference it comes from, why this specific client is exposed, and a concrete next step. Every run is saved as a JSON report, a plain-text summary, and an audit-trail row in SQLite, and an optional n8n schedule turns the summary into a polite client email saved to Gmail Drafts.

The AI connection is **bring-your-own-key**: you enter your API key and model name in the dashboard. Nothing is stored in the code, `.env`, or the repository — credentials live in the session only.

## Live demo

Open the Streamlit Cloud link and you will see a fully populated dashboard immediately — no API key needed. It shows pre-built sample results for a fictional client (Meridian Advisory Group Inc.) so you can explore every feature before connecting your own AI.

## Supported AI providers

You pick one provider at setup. Two have a genuinely free tier with no credit card required.

| Provider | Free tier | Notes |
|----------|-----------|-------|
| **Groq** | ✅ Yes (no card) | 14,400 free requests/day |
| **OpenRouter** | ✅ Yes (no card) | Free community models available |
| **Anthropic** | Pay-per-use | Claude models |
| **OpenAI** | Pay-per-use | GPT models |
| **Custom** | Depends on provider | Any OpenAI-compatible endpoint |

**You supply the model name yourself in the dashboard.** Nothing is hardcoded, so any current or future model works without touching the code. The Custom option additionally asks for a base URL, covering Mistral, Together AI, Azure OpenAI, local servers, and anything else that speaks the OpenAI format.

## Setup

```bash
# 1. Clone the repository
git clone https://github.com/PrabaAP/compliance-automation-engine.git
cd compliance-automation-engine

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the dashboard
streamlit run scripts/05_dashboard.py
```

In the sidebar: choose a provider, enter the model name, paste your API key, click **Connect**, upload a client profile (`.txt`), then click **Analyse Now**.

> **CRA regulation PDFs:** Two sample CRA PDFs are included so the demo and tests work immediately. Replace or add your own PDFs in `docs/regulations/` for real client work.

## Command-line usage

The pipeline can also run directly from the terminal — this is what the n8n schedule calls:

```bash
python scripts/04_run_pipeline.py \
  --provider groq \
  --key YOUR_API_KEY \
  --model YOUR_MODEL_NAME
```

For a custom provider, add `--base-url https://api.yourprovider.com/v1`.

## Project structure

```
compliance-automation-engine/
├── data/
│   └── demo_report.json        pre-built sample report (shown on Streamlit Cloud)
├── docs/
│   ├── regulations/            CRA regulation PDFs (two samples included)
│   └── clients/                client_profile.txt
├── scripts/
│   ├── ai_router.py            central provider routing (no keys or models stored)
│   ├── 01_test_connection.py   validate a provider + key + model
│   ├── 02_extract_pdf.py       combine text from all PDFs
│   ├── 03_analyze_compliance.py AI risk analysis, reports, audit row
│   ├── 04_run_pipeline.py      orchestrator (dashboard + n8n entry point)
│   └── 05_dashboard.py         Streamlit UI
├── outputs/
│   └── reports/                JSON reports + text summaries (gitignored)
├── database/
│   └── audit.db                SQLite audit trail (gitignored)
├── n8n/
│   └── compliance_workflow.json scheduled email automation
├── requirements.txt
├── README.md
├── USER_GUIDE.md
└── HOW_IT_WORKS.md
```

## Automated email (n8n)

`n8n/compliance_workflow.json` is a five-node workflow you can import into n8n:

1. **Daily 9 AM trigger** fires the pipeline automatically
2. **Execute Command** runs `04_run_pipeline.py` with your provider, key, and model
3. **Read File** reads the latest summary from `outputs/reports/`
4. **HTTP Request** calls any OpenAI-compatible API to draft a client email
5. **Gmail** saves the draft to Gmail Drafts via OAuth — it is never auto-sent

**Connecting your Gmail account:** In n8n, open the Gmail node → click *Add Credential* → *Gmail OAuth2* → sign in with the Google account you want drafts to appear in. n8n stores only the OAuth token, not your password. The draft lands in your Drafts folder with no recipient set, so you add the client's email address and review before sending.

## About the author

- Background in professional services, business, finance & operations analytics and advisory work, where compliance review is a recurring, manual task this project aims to speed up.
- IBM-certified professional in data and AI.
- LinkedIn: [linkedin.com/in/arun-prabakar-vadaseri-rajendran](https://www.linkedin.com/in/arun-prabakar-vadaseri-rajendran)

See [USER_GUIDE.md](USER_GUIDE.md) for a non-technical walkthrough and [HOW_IT_WORKS.md](HOW_IT_WORKS.md) for the full technical breakdown.
