"""
Compliance Review Engine — Streamlit dashboard.

The user connects their own AI provider (key lives only in this session),
uploads a client profile, and runs the full compliance pipeline. Results and
an audit trail are shown in two tabs.

Theming: an in-app System / Light / Dark toggle drives CSS custom properties.
"System" follows the viewer's OS via prefers-color-scheme.

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

SEVERITY_COLOR = {"HIGH": "#DC2626", "MEDIUM": "#D97706", "LOW": "#059669"}
SEVERITY_WEIGHT = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# ── Theme palettes (CSS custom properties) ───────────────────────────────────
_LIGHT_VARS = """
    --bg: #EDF1F8;
    --surface: #FFFFFF;
    --surface-2: #F2F5FB;
    --text: #0F1B2D;
    --muted: #5B6B86;
    --border: #E1E7F1;
    --primary: #2F54EB;
    --primary-deep: #15327A;
    --shadow: 0 1px 2px rgba(16,24,40,.04), 0 6px 20px rgba(16,24,40,.07);
"""
_DARK_VARS = """
    --bg: #0A0F1A;
    --surface: #121C2D;
    --surface-2: #182640;
    --text: #E8ECF4;
    --muted: #94A3BB;
    --border: #233149;
    --primary: #6E8BFF;
    --primary-deep: #1A2C58;
    --shadow: 0 1px 2px rgba(0,0,0,.45), 0 10px 28px rgba(0,0,0,.5);
"""

_CSS_RULES = """
    html, body, .stApp, [data-testid="stSidebar"] {
        font-family: 'IBM Plex Sans', system-ui, sans-serif;
    }
    .stApp, [data-testid="stAppViewContainer"] { background-color: var(--bg); color: var(--text); }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { padding-top: 2.4rem; }

    h1, h2, h3 { font-family: 'IBM Plex Serif', Georgia, serif; color: var(--text); letter-spacing: -0.015em; }
    p, span, label, li, [data-testid="stMarkdownContainer"] { color: var(--text); }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: var(--muted) !important; }

    /* Hero banner */
    .hero { background: linear-gradient(135deg, var(--primary-deep) 0%, var(--primary) 100%);
            padding: 30px 34px; border-radius: 18px; margin-bottom: 22px; box-shadow: var(--shadow); }
    .hero h1 { color: #FFFFFF !important; margin: 0; font-size: 2.15rem; }
    .hero p  { color: rgba(255,255,255,0.84); margin: 8px 0 0; font-size: 1.02rem; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: var(--surface); border-right: 1px solid var(--border); }
    [data-testid="stSidebar"] hr, hr { border-color: var(--border); }

    /* Text inputs / selects / textareas */
    [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
        background-color: var(--surface-2) !important; border-color: var(--border) !important; border-radius: 10px !important; }
    input, textarea, [data-baseweb="select"] div { color: var(--text) !important; }
    input::placeholder, textarea::placeholder { color: var(--muted) !important; }

    /* Dropdown popovers */
    [data-baseweb="popover"] div, [data-baseweb="menu"], [role="listbox"] { background-color: var(--surface) !important; }
    [data-baseweb="popover"] li, [role="option"] { color: var(--text) !important; }

    /* File uploader */
    [data-testid="stFileUploaderDropzone"] { background-color: var(--surface-2) !important;
        border: 1px dashed var(--border) !important; border-radius: 12px; }
    [data-testid="stFileUploaderDropzone"] * { color: var(--muted) !important; }

    /* Buttons */
    .stButton > button { background: var(--primary); color: #fff; border: 0; border-radius: 10px;
        font-weight: 600; padding: 0.55rem 1rem; box-shadow: var(--shadow);
        transition: filter .15s ease, transform .05s ease; }
    .stButton > button:hover { filter: brightness(1.08); color: #fff; }
    .stButton > button:active { transform: translateY(1px); }
    .stButton > button:disabled { opacity: .45; box-shadow: none; }

    /* Metric cards */
    [data-testid="stMetric"] { background: var(--surface); border: 1px solid var(--border);
        border-left: 5px solid var(--primary); border-radius: 14px; padding: 18px 20px; box-shadow: var(--shadow); }
    [data-testid="stMetricValue"] { color: var(--text); font-weight: 700; }
    [data-testid="stMetricLabel"], [data-testid="stMetricLabel"] * { color: var(--muted) !important; }

    /* Expanders */
    [data-testid="stExpander"] { border: 1px solid var(--border); border-radius: 12px; background: var(--surface);
        margin-bottom: 10px; box-shadow: var(--shadow); overflow: hidden; }
    [data-testid="stExpander"] summary { color: var(--text); font-weight: 600; }
    [data-testid="stExpander"] summary:hover { color: var(--primary); }

    /* Alerts */
    [data-testid="stAlert"] { border-radius: 12px; border: 1px solid var(--border); }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid var(--border); }
    .stTabs [data-baseweb="tab"] { font-weight: 600; color: var(--muted); }
    .stTabs [aria-selected="true"] { color: var(--primary) !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: var(--primary) !important; }

    /* Dataframe */
    [data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 12px; }

    /* Theme toggle radio → pill row */
    [data-testid="stSidebar"] [role="radiogroup"] { gap: 6px; flex-wrap: wrap; }

    /* Hide Streamlit chrome for a clean look */
    #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], footer { visibility: hidden; }
"""

_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Serif:wght@600;700&display=swap');"
)


def build_theme_css(mode: str) -> str:
    """Return the <style> block for the chosen appearance mode."""
    if mode == "Light":
        root = f":root {{ {_LIGHT_VARS} }}"
    elif mode == "Dark":
        root = f":root {{ {_DARK_VARS} }}"
    else:  # System — follow the OS preference
        root = (
            f":root {{ {_LIGHT_VARS} }}\n"
            f"@media (prefers-color-scheme: dark) {{ :root {{ {_DARK_VARS} }} }}"
        )
    return f"<style>\n{_FONT_IMPORT}\n{root}\n{_CSS_RULES}\n</style>"


def chart_palette(mode: str) -> dict:
    """Plotly font/grid colours per mode (Plotly can't read CSS variables)."""
    if mode == "Dark":
        return {"font": "#C8D2E0", "grid": "rgba(255,255,255,0.10)"}
    if mode == "Light":
        return {"font": "#33415A", "grid": "rgba(15,23,42,0.08)"}
    return {"font": "#7385A0", "grid": "rgba(128,128,128,0.18)"}  # System compromise


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Compliance Review Engine",
    layout="wide",
    page_icon="⚖️",
)

# ── Session state (theme_mode must exist before the CSS is injected) ──────────
if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "System"
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

st.markdown(build_theme_css(st.session_state.theme_mode), unsafe_allow_html=True)


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


# ── Sidebar: appearance + connection setup ────────────────────────────────────
st.sidebar.title("⚖️ Compliance Engine")

st.sidebar.radio(
    "Appearance",
    options=["System", "Light", "Dark"],
    key="theme_mode",
    horizontal=True,
    format_func=lambda x: {"System": "🖥 System", "Light": "☀️ Light", "Dark": "🌙 Dark"}[x],
)

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
            pal = chart_palette(st.session_state.theme_mode)
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
                    textfont=dict(color="#FFFFFF", size=12),
                    hovertext=[r.get("client_exposure", "") for r in risks],
                )
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color=pal["font"], family="IBM Plex Sans"),
                xaxis=dict(
                    title="Severity (HIGH=3 · MEDIUM=2 · LOW=1)",
                    gridcolor=pal["grid"], zerolinecolor=pal["grid"],
                ),
                yaxis=dict(autorange="reversed", gridcolor=pal["grid"], zerolinecolor=pal["grid"]),
                height=80 + 64 * len(risks),
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
                        f"padding:8px 12px;border-radius:8px;'>"
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
