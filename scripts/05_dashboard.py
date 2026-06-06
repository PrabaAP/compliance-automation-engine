"""
Compliance Review Engine — Streamlit dashboard.

The user connects their own AI provider (key lives only in this session),
uploads a client profile, and runs the full compliance pipeline. Results and
an audit trail are shown in two tabs.

Run with:
    streamlit run scripts/05_dashboard.py
"""

import glob
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"
CLIENT_PROFILE = PROJECT_ROOT / "docs" / "clients" / "client_profile.txt"
DB_PATH = PROJECT_ROOT / "database" / "audit.db"

TEST_SCRIPT = SCRIPTS_DIR / "01_test_connection.py"
PIPELINE_SCRIPT = SCRIPTS_DIR / "04_run_pipeline.py"

# ── Chart styling ────────────────────────────────────────────────────────────
CHART_BG = "rgba(0,0,0,0)"
GRID_COLOR = "rgba(128,128,128,0.15)"
AXIS_STYLE = dict(gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR)

SEVERITY_COLOR = {"HIGH": "#DC2626", "MEDIUM": "#D97706", "LOW": "#059669"}
SEVERITY_WEIGHT = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Compliance Review Engine",
    layout="wide",
    page_icon="⚖️",
)

# ── Custom "audit brief" theme (distinct from the stock Streamlit look) ───────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:wght@600;700&display=swap');

    html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
        font-family: 'IBM Plex Sans', sans-serif;
    }
    [data-testid="stAppViewContainer"] { background-color: #F5F7FA; }
    [data-testid="stHeader"] { background: transparent; }
    h1, h2, h3 {
        font-family: 'IBM Plex Serif', Georgia, serif;
        color: #1E3A5F; letter-spacing: -0.01em;
    }

    /* Hero banner */
    .hero {
        background: linear-gradient(135deg, #1E3A5F 0%, #2C5282 100%);
        padding: 26px 32px; border-radius: 14px; margin-bottom: 18px;
        box-shadow: 0 8px 24px rgba(30,58,95,0.18);
    }
    .hero h1 { color: #FFFFFF !important; margin: 0; font-size: 2.05rem; }
    .hero p  { color: #CBD5E1; margin: 6px 0 0; font-size: 1.0rem;
               font-family: 'IBM Plex Sans', sans-serif; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E6E9EF; }

    /* Metric cards */
    [data-testid="stMetric"], [data-testid="metric-container"] {
        background: #FFFFFF; border: 1px solid #E6E9EF; border-left: 5px solid #1E3A5F;
        border-radius: 12px; padding: 16px 18px; box-shadow: 0 1px 3px rgba(16,24,40,0.06);
    }
    [data-testid="stMetricValue"] { color: #1E3A5F; font-weight: 700; }
    [data-testid="stMetricLabel"] { color: #64748B; }

    /* Primary buttons */
    .stButton > button {
        background: #1E3A5F; color: #FFFFFF; border: none; border-radius: 8px;
        font-weight: 600; padding: 0.5rem 1rem;
    }
    .stButton > button:hover { background: #2C5282; color: #FFFFFF; }

    /* Expanders as cards */
    [data-testid="stExpander"] {
        border: 1px solid #E6E9EF; border-radius: 10px; background: #FFFFFF; margin-bottom: 8px;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab"] { font-weight: 600; }

    /* Clean chrome for the deployed app */
    #MainMenu, [data-testid="stToolbar"], footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ────────────────────────────────────────────────────────────
if "provider" not in st.session_state:
    st.session_state.provider = None
if "api_key" not in st.session_state:
    st.session_state.api_key = None
if "connected" not in st.session_state:
    st.session_state.connected = False
if "custom_base_url" not in st.session_state:
    st.session_state.custom_base_url = None
if "custom_model" not in st.session_state:
    st.session_state.custom_model = None


# ── Helpers ──────────────────────────────────────────────────────────────────
def latest_report():
    """Return the most recent report dict, or None."""
    files = sorted(glob.glob(str(REPORTS_DIR / "report_*.json")))
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as fh:
        return json.load(fh)


def load_audit_dataframe():
    """Return the audit table as a DataFrame, creating the DB/table if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
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
            """
        )
        conn.commit()
        return pd.read_sql_query(
            "SELECT run_date, client_name, provider, model, pdf_count, risk_count "
            "FROM analyses ORDER BY id DESC",
            conn,
        )
    finally:
        conn.close()


def run_subprocess(cmd):
    """Run a pipeline script and return (success, combined_output)."""
    result = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output


# ── Sidebar: connection setup ────────────────────────────────────────────────
st.sidebar.title("⚖️ Compliance Engine")
st.sidebar.markdown("---")
st.sidebar.subheader("1. Connect Your AI")

provider = st.sidebar.selectbox(
    "AI Provider",
    options=["groq", "openrouter", "anthropic", "openai", "custom"],
    format_func=lambda x: {
        "groq": "🟢 Groq — Free (Llama 3.3 70B)",
        "openrouter": "🟢 OpenRouter — Free tier available",
        "anthropic": "Claude (Anthropic API)",
        "openai": "GPT-4o (OpenAI API)",
        "custom": "➕ Custom — Any OpenAI-compatible provider",
    }[x],
)

custom_base_url = None
custom_model = None
if provider == "custom":
    custom_base_url = st.sidebar.text_input(
        "API Base URL", placeholder="https://api.yourprovider.com/v1"
    )
    custom_model = st.sidebar.text_input(
        "Model name", placeholder="e.g. mistral-large, llama-3..."
    )

key_label = {
    "groq": "Groq API Key (free at console.groq.com)",
    "openrouter": "OpenRouter API Key (free at openrouter.ai)",
    "anthropic": "Anthropic API Key",
    "openai": "OpenAI API Key",
    "custom": "API Key for your provider",
}
api_key = st.sidebar.text_input(key_label[provider], type="password")

if st.sidebar.button("🔌 Connect", use_container_width=True):
    if not api_key:
        st.sidebar.error("Enter an API key first.")
    elif provider == "custom" and (not custom_base_url or not custom_model):
        st.sidebar.error("Custom provider needs a base URL and model name.")
    else:
        cmd = [sys.executable, str(TEST_SCRIPT), "--provider", provider, "--key", api_key]
        if provider == "custom":
            cmd += ["--base-url", custom_base_url, "--model", custom_model]
        with st.spinner(f"Testing {provider} connection..."):
            ok, output = run_subprocess(cmd)
        if ok:
            st.session_state.connected = True
            st.session_state.provider = provider
            st.session_state.api_key = api_key
            st.session_state.custom_base_url = custom_base_url
            st.session_state.custom_model = custom_model
            st.sidebar.success("✅ Connected")
        else:
            st.session_state.connected = False
            st.sidebar.error("Connection failed — check your key and URL")
            with st.sidebar.expander("Details"):
                st.code(output or "No output", language="text")

if st.session_state.connected:
    st.sidebar.caption(f"Connected to **{st.session_state.provider}**")

# ── Sidebar: upload + analyse ────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.subheader("2. Upload Client Profile")
uploaded = st.sidebar.file_uploader("Client profile (.txt)", type=["txt"])

if st.sidebar.button(
    "▶ Analyse Now",
    disabled=not st.session_state.connected,
    use_container_width=True,
):
    if uploaded is not None:
        CLIENT_PROFILE.parent.mkdir(parents=True, exist_ok=True)
        CLIENT_PROFILE.write_bytes(uploaded.getvalue())

    if not CLIENT_PROFILE.exists():
        st.sidebar.error("Upload a client profile (or add docs/clients/client_profile.txt).")
    else:
        cmd = [
            sys.executable,
            str(PIPELINE_SCRIPT),
            "--provider",
            st.session_state.provider,
            "--key",
            st.session_state.api_key,
        ]
        if st.session_state.provider == "custom":
            cmd += [
                "--base-url",
                st.session_state.custom_base_url,
                "--model",
                st.session_state.custom_model,
            ]
        with st.spinner(f"Analysing with {st.session_state.provider}..."):
            ok, output = run_subprocess(cmd)
        if ok:
            st.success("Analysis complete — see the Latest Report tab")
        else:
            st.error("Analysis failed.")
            with st.expander("Details"):
                st.code(output or "No output", language="text")

# ── Main area ────────────────────────────────────────────────────────────────
st.markdown(
    '<div class="hero">'
    '<h1>⚖️ Compliance Review Engine</h1>'
    '<p>AI-assisted CRA compliance risk review — bring your own AI, your data stays local</p>'
    '</div>',
    unsafe_allow_html=True,
)

tab_report, tab_audit = st.tabs(["📋 Latest Report", "📁 Audit Trail"])

with tab_report:
    report = latest_report()
    if report is None:
        st.info("Connect your AI and run your first analysis using the sidebar.")
    else:
        risks = report.get("compliance_risks", [])
        severities = [str(r.get("severity", "")).upper() for r in risks]
        high = severities.count("HIGH")
        medium = severities.count("MEDIUM")

        st.caption(
            f"**{report.get('client_name', 'Client')}** · "
            f"{report.get('run_date', '')} · "
            f"{report.get('provider', '')} ({report.get('model', '')})"
        )

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Risks", len(risks))
        c2.metric("High Severity", high, delta=high or None, delta_color="inverse")
        c3.metric("Medium Severity", medium, delta=medium or None, delta_color="inverse")

        if risks:
            titles = [r.get("title", f"Risk {i+1}") for i, r in enumerate(risks)]
            weights = [SEVERITY_WEIGHT.get(s, 1) for s in severities]
            colors = [SEVERITY_COLOR.get(s, "#9CA3AF") for s in severities]

            fig = go.Figure(
                go.Bar(
                    x=weights,
                    y=titles,
                    orientation="h",
                    marker_color=colors,
                    text=severities,
                    textposition="inside",
                    hovertext=[r.get("client_exposure", "") for r in risks],
                )
            )
            fig.update_layout(
                plot_bgcolor=CHART_BG,
                paper_bgcolor=CHART_BG,
                xaxis=dict(title="Severity (HIGH=3 · MEDIUM=2 · LOW=1)", **AXIS_STYLE),
                yaxis=dict(autorange="reversed", **AXIS_STYLE),
                height=80 + 60 * len(risks),
                margin=dict(l=10, r=10, t=30, b=10),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

            for r in risks:
                sev = str(r.get("severity", "")).upper()
                color = SEVERITY_COLOR.get(sev, "#9CA3AF")
                with st.expander(f"{sev} — {r.get('title', '')}"):
                    st.markdown(f"**{r.get('title', '')}**")
                    st.markdown(f"*CRA Reference: {r.get('cra_reference', '')}*")
                    st.markdown(f"**Client exposure:** {r.get('client_exposure', '')}")
                    st.markdown(
                        f"<div style='background:{color}22;border-left:4px solid {color};"
                        f"padding:8px 12px;border-radius:4px;'>"
                        f"<b>Action:</b> {r.get('action', '')}</div>",
                        unsafe_allow_html=True,
                    )

with tab_audit:
    df = load_audit_dataframe()
    if df.empty:
        st.info("No analyses recorded yet. Run your first analysis to populate the audit trail.")
    else:
        df = df.rename(
            columns={
                "run_date": "Date",
                "client_name": "Client",
                "provider": "Provider",
                "model": "Model",
                "pdf_count": "PDFs",
                "risk_count": "Risks Found",
            }
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

# ── Footer ───────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Compliance Automation Engine — **Arun Prabakar Vadaseri Rajendran** · "
    "linkedin.com/in/arun-prabakar-vadaseri-rajendran"
)
