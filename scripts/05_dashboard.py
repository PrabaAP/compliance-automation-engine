"""
Compliance Review Engine · Streamlit dashboard.

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
import streamlit.components.v1 as components

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"
CLIENT_PROFILE = PROJECT_ROOT / "docs" / "clients" / "client_profile.txt"
DB_PATH = PROJECT_ROOT / "database" / "audit.db"
DEMO_REPORT = PROJECT_ROOT / "data" / "demo_report.json"

TEST_SCRIPT = SCRIPTS_DIR / "01_test_connection.py"
PIPELINE_SCRIPT = SCRIPTS_DIR / "04_run_pipeline.py"

SEVERITY_COLOR = {"HIGH": "#991B1B", "MEDIUM": "#B45309", "LOW": "#14532D"}
SEVERITY_WEIGHT = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# ── Theme palettes (CSS custom properties) ───────────────────────────────────
_LIGHT_VARS = """
    --bg: #faf9f5;
    --surface: #faf9f5;
    --surface-2: #f4f4f0;
    --surface-3: #efeeea;
    --sidebar-bg: #f4f4f0;
    --text: #1b1c1a;
    --muted: #404941;
    --border: #c0c9be;
    --primary: #003b1b;
    --primary-deep: #14532d;
    --shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.02);
    --accent-gold: #904d00;
    --glow: rgba(0, 59, 27, 0.08);
    --error: #ba1a1a;
    --error-container: #ffdad6;
    --on-error-container: #93000a;
    --error-bg: rgba(255, 218, 214, 0.15);
    --warning: #904d00;
    --warning-bg: rgba(254, 147, 44, 0.12);
    --secondary-container: #fe932c;
    --on-secondary-container: #663500;
    --badge-high-bg: #ffdad6;
    --badge-high-text: #93000a;
    --badge-high-border: rgba(186, 26, 26, 0.5);
    --badge-med-bg: #fe932c;
    --badge-med-text: #663500;
    --badge-med-border: rgba(144, 77, 0, 0.5);
    --action-border: rgba(0, 59, 27, 0.35);
"""
_DARK_VARS = """
    --bg: #0b0f0d;
    --surface: #121915;
    --surface-2: #1e2924;
    --surface-3: #253329;
    --sidebar-bg: #121915;
    --text: #e8ede9;
    --muted: #9aada5;
    --border: #364c40;
    --primary: #10b981;
    --primary-deep: #047857;
    --shadow: 0 8px 30px rgba(0, 0, 0, 0.35);
    --glow: rgba(16, 185, 129, 0.12);
    --accent-gold: #f59e0b;
    --error: #ef4444;
    --error-container: rgba(239, 68, 68, 0.08);
    --on-error-container: #ef4444;
    --error-bg: rgba(239, 68, 68, 0.08);
    --warning: #f59e0b;
    --warning-bg: rgba(245, 158, 11, 0.08);
    --secondary-container: rgba(245, 158, 11, 0.15);
    --on-secondary-container: #f59e0b;
    --badge-high-bg: rgba(239, 68, 68, 0.15);
    --badge-high-text: #ef4444;
    --badge-high-border: rgba(239, 68, 68, 0.35);
    --badge-med-bg: rgba(245, 158, 11, 0.15);
    --badge-med-text: #f59e0b;
    --badge-med-border: rgba(245, 158, 11, 0.35);
    --action-border: rgba(16, 185, 129, 0.22);
    --badge-high-bg: rgba(239, 68, 68, 0.18);
    --badge-high-text: #fca5a5;
    --badge-high-border: rgba(239, 68, 68, 0.40);
    --badge-med-bg: rgba(245, 158, 11, 0.18);
    --badge-med-text: #fcd34d;
    --badge-med-border: rgba(245, 158, 11, 0.40);
"""

_CSS_RULES = """
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    ::-webkit-scrollbar-track {
        background: var(--bg);
    }
    ::-webkit-scrollbar-thumb {
        background: var(--border);
        border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--muted);
    }

    html, body, .stApp, [data-testid="stSidebar"] {
        font-family: 'Inter', system-ui, -apple-system, sans-serif;
    }
    .stApp, [data-testid="stAppViewContainer"] { 
        background-color: var(--bg); 
        color: var(--text); 
    }
    [data-testid="stHeader"] { background: transparent; }
    .block-container { padding-top: 2.5rem; }

    h1, h2, h3, h4 {
        font-family: 'Inter', system-ui, sans-serif;
        color: var(--text);
        letter-spacing: -0.02em;
        font-weight: 700;
    }
    p, span, label, li, [data-testid="stMarkdownContainer"] { 
        color: var(--text); 
        font-family: 'Inter', system-ui, sans-serif;
    }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { 
        color: var(--muted) !important; 
    }

    /* Top App Bar */
    .hero {
        background-color: var(--surface) !important;
        border-bottom: 1px solid var(--border) !important;
        padding: 18px 32px !important;
        margin-bottom: 28px !important;
        display: flex !important;
        justify-content: space-between !important;
        align-items: center !important;
        border-radius: 0 !important;
        margin-left: -2.5rem !important;
        margin-right: -2.5rem !important;
        margin-top: -2.5rem !important;
        box-shadow: 0 4px 24px -12px rgba(0,0,0,0.05) !important;
    }
    .hero h1 {
        color: var(--text) !important;
        margin: 0 !important;
        font-size: 2rem;
        font-weight: 700;
        font-family: 'Inter', system-ui, sans-serif !important;
        letter-spacing: -0.02em;
        text-transform: none !important;
    }
    .hero p { 
        display: none !important; /* Hide old description, handled by meta */
    }
    .hero-metadata {
        display: flex !important;
        flex-direction: column !important;
        text-align: right !important;
    }
    .hero-meta-label {
        font-family: 'Inter', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        color: var(--text) !important;
    }
    .hero-meta-sub {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.72rem !important;
        color: var(--muted) !important;
        margin-top: 2px !important;
    }

    /* Sidebar Header */
    .sidebar-header {
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        padding-bottom: 20px !important;
        border-bottom: 1px solid var(--border) !important;
        margin-bottom: 20px !important;
    }
    .sidebar-header .header-icon {
        font-family: 'Material Symbols Outlined' !important;
        font-size: 28px !important;
        color: var(--primary) !important;
        font-variation-settings: 'FILL' 1, 'wght' 400 !important;
        display: inline-block;
    }
    .sidebar-header .header-text h2 {
        font-family: 'Playfair Display', Georgia, serif !important;
        font-size: 1.35rem !important;
        margin: 0 !important;
        color: var(--text) !important;
        font-weight: 700 !important;
    }
    .sidebar-header .header-text .sub {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.72rem !important;
        color: var(--muted) !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        display: block !important;
        margin-top: 2px !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid var(--border) !important;
    }
    [data-testid="stSidebar"] hr, hr { border-color: var(--border); }

    /* Sidebar spacing: enough gap so section headers don't collide with widget labels */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: 0.55rem !important; }
    [data-testid="stSidebar"] .stSelectbox > label,
    [data-testid="stSidebar"] .stFileUploader > label { margin-top: 10px !important; display: block !important; }
    [data-testid="stSidebarUserContent"] { padding-top: 0.75rem !important; }
    [data-testid="stSidebar"] hr { margin: 6px 0 !important; }
    [data-testid="stSidebar"] h3 {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.66rem !important; font-weight: 700 !important;
        text-transform: uppercase !important; letter-spacing: 0.10em !important;
        color: var(--muted) !important; margin: 12px 0 8px 0 !important; padding: 0 !important;
    }

    /* Text inputs / selects / textareas */
    [data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    [data-baseweb="base-input"] {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
    }
    [data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {
        border-color: var(--accent-gold) !important;
        box-shadow: 0 0 0 3px var(--glow) !important;
    }
    input, textarea, [data-baseweb="select"] div { color: var(--text) !important; }
    input::placeholder, textarea::placeholder { color: var(--muted) !important; }

    /* Dropdown popovers: outer shell only gets the border */
    [data-baseweb="popover"] > div, [data-baseweb="menu"], [role="listbox"] {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px !important;
    }
    [data-baseweb="popover"] div div { border: none !important; background: transparent !important; }
    [data-baseweb="popover"] li, [role="option"] { color: var(--text) !important; }

    /* File uploader */
    [data-testid="stFileUploaderDropzone"] { 
        background-color: var(--surface-2) !important;
        border: 1px dashed var(--border) !important; 
        border-radius: 8px; 
        transition: all 0.2s ease !important;
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--primary) !important;
    }
    [data-testid="stFileUploaderDropzone"] * { color: var(--muted) !important; }

    /* Buttons */
    .stButton > button { 
        background: var(--primary-deep) !important; 
        color: #fff !important; 
        border: 1px solid var(--border) !important; 
        border-radius: 6px !important;
        font-weight: 600 !important; 
        font-family: 'Inter', system-ui, sans-serif !important;
        text-transform: uppercase !important;
        letter-spacing: 0.05em !important;
        font-size: 0.85rem !important;
        padding: 0.55rem 1.2rem !important; 
        box-shadow: var(--shadow) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important; 
    }
    .stButton > button:hover { 
        background: var(--primary) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 15px rgba(21, 128, 61, 0.15) !important;
        filter: brightness(1.05) !important; 
    }
    .stButton > button:active { transform: translateY(0) !important; }
    .stButton > button:disabled { opacity: .45 !important; box-shadow: none !important; transform: none !important; }

    /* Metric cards */
    [data-testid="stMetric"] { 
        background: var(--surface) !important; 
        border: 1px solid var(--border) !important;
        border-radius: 6px !important; 
        padding: 18px 20px !important; 
        box-shadow: var(--shadow) !important; 
        transition: all 0.2s ease !important;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-2px) !important;
        border-color: var(--accent-gold) !important;
    }
    [data-testid="stMetricValue"] { 
        color: var(--text) !important; 
        font-family: 'Playfair Display', Georgia, serif !important;
        font-weight: 700 !important; 
        font-size: 2.25rem !important;
        letter-spacing: -0.02em !important;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Inter', system-ui, sans-serif !important;
        color: var(--muted) !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        font-size: 0.72rem !important;
        margin-bottom: 4px !important;
    }
    [data-testid="column"]:nth-child(1) [data-testid="stMetric"] { 
        border-left: 4px solid var(--primary) !important; 
    }
    [data-testid="column"]:nth-child(2) [data-testid="stMetric"] { 
        border-left: 4px solid var(--error) !important; 
        background-color: var(--error-bg) !important; 
        border-color: rgba(186, 26, 26, 0.2) !important;
    }
    [data-testid="column"]:nth-child(3) [data-testid="stMetric"] { 
        border-left: 4px solid var(--warning) !important; 
        background-color: var(--warning-bg) !important;
        border-color: rgba(144, 77, 0, 0.2) !important;
    }

    /* Expanders */
    [data-testid="stExpander"] { 
        border: 1px solid var(--border) !important; 
        border-radius: 6px !important; 
        background: var(--surface) !important;
        margin-bottom: 12px !important; 
        box-shadow: var(--shadow) !important; 
        overflow: hidden !important; 
        transition: all 0.2s ease !important;
    }
    [data-testid="stExpander"]:hover {
        border-color: var(--primary) !important;
    }
    [data-testid="stExpander"] summary {
        color: var(--text) !important;
        font-family: 'Inter', system-ui, sans-serif !important;
        font-weight: 700 !important; 
        font-size: 1.15rem !important;
        padding: 14px 20px !important;
    }
    [data-testid="stExpander"] summary:hover { color: var(--primary) !important; }

    /* Custom action callouts inside expanders */
    .action-callout {
        padding: 16px !important;
        border-radius: 6px !important;
        font-family: 'Inter', system-ui, sans-serif !important;
        font-size: 0.95rem !important;
        line-height: 1.5 !important;
        margin-top: 12px !important;
        border: 1px solid var(--border) !important;
    }

    /* Alerts */
    [data-testid="stAlert"] { border-radius: 8px !important; border: 1px solid var(--border) !important; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] { 
        gap: 12px !important; 
        border-bottom: 2px solid var(--border) !important; 
        padding: 4px 4px 0px 4px !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', system-ui, sans-serif !important;
        font-weight: 600 !important; 
        color: var(--muted) !important; 
        border-radius: 6px 6px 0 0 !important;
        padding: 10px 18px !important;
        transition: all 0.2s ease !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--primary) !important;
        background-color: var(--surface-2) !important;
    }
    .stTabs [aria-selected="true"] { color: var(--primary) !important; font-weight: 700 !important; }
    .stTabs [data-baseweb="tab-highlight"] { background-color: var(--primary) !important; height: 3px !important; }

    /* Dataframe */
    [data-testid="stDataFrame"] { 
        border: 1px solid var(--border) !important; 
        border-radius: 8px !important; 
        overflow: hidden !important;
        box-shadow: var(--shadow) !important;
    }

    /* Sidebar Navigation radio → clean list */
    [data-testid="stSidebar"] [role="radiogroup"] { 
        display: flex !important;
        flex-direction: column !important;
        gap: 4px !important; 
        width: 100% !important; 
    }
    [data-testid="stSidebar"] [role="radiogroup"] label {
        background-color: transparent !important;
        border: none !important;
        border-left: 4px solid transparent !important;
        border-radius: 0 6px 6px 0 !important;
        padding: 8px 16px !important;
        margin: 0 !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
        display: flex !important;
        align-items: center !important;
        width: 100% !important;
        color: var(--muted) !important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        background-color: var(--surface-2) !important;
        color: var(--text) !important;
    }
    /* (active state now handled via :has(input:checked) at bottom of CSS) */
    [data-testid="stSidebar"] [role="radiogroup"] label > div:first-child {
        display: none !important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] label > div:last-child {
        margin-left: 0 !important;
    }

    /* Dropdown option list: no per-item borders, hover highlight only */
    [data-baseweb="menu"] { padding: 4px !important; }
    [data-baseweb="menu"] li, [data-baseweb="menu"] [role="option"] {
        border: none !important;
        border-radius: 5px !important;
        margin: 1px 0 !important;
    }
    [data-baseweb="menu"] [role="option"]:hover {
        background-color: var(--surface-2) !important;
        color: var(--text) !important;
    }
    [data-baseweb="menu"] [role="option"][aria-selected="true"] {
        background-color: var(--glow) !important;
        color: var(--primary) !important;
        font-weight: 600 !important;
    }

    /* Password input: remove separator line before eye icon */
    [data-testid="passwordInputVisibilityToggle"] {
        border-left: none !important;
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }

    /* Dropdown popover: ensure it overlays sidebar content correctly */
    [data-baseweb="popover"] { z-index: 999 !important; }
    [data-baseweb="popover"] > div { z-index: 999 !important; }

    /* Ensure button text is white in both modes */
    .stButton > button, .stButton > button span, .stButton > button p { color: #ffffff !important; }

    /* Hide Streamlit chrome but keep sidebar expand button visible */
    #MainMenu, [data-testid="stToolbar"], [data-testid="stDecoration"], footer { visibility: hidden; }
    [data-testid="stExpandSidebarButton"] {
        visibility: visible !important;
        border-radius: 8px !important;
        transition: background 0.15s ease !important;
    }
    [data-testid="stExpandSidebarButton"]:hover { background: var(--surface-3) !important; }
    [data-testid="stExpandSidebarButton"] svg { stroke: var(--text) !important; color: var(--text) !important; }
    [data-testid="stSidebarCollapseButton"] { visibility: visible !important; }
    [data-testid="stSidebarCollapseButton"] button { visibility: visible !important; border-radius: 8px !important; transition: background 0.15s ease !important; }
    [data-testid="stSidebarCollapseButton"] button svg { stroke: var(--muted) !important; color: var(--muted) !important; }
    [data-testid="stSidebarCollapseButton"] button:hover { background: var(--surface-3) !important; }
    [data-testid="stSidebarCollapseButton"] button:hover svg { stroke: var(--text) !important; color: var(--text) !important; }

    /* ── KPI Cards (Stitch exact) ──────────────────────────────────────────── */
    .kpi-row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 28px; }
    .kpi-card {
        position: relative; background: var(--surface); border: 1px solid var(--border);
        border-radius: 4px; padding: 24px; overflow: hidden;
        box-shadow: var(--shadow); min-height: 130px;
    }
    .kpi-total { border: 1px solid var(--border); }
    .kpi-high  { background: var(--error-bg)   !important; border: 1px solid rgba(186,26,26,.25) !important; }
    .kpi-medium{ background: var(--warning-bg) !important; border: 1px solid rgba(144,77,0,.25)  !important; }
    .kpi-high::before, .kpi-medium::before {
        content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
    }
    .kpi-high::before   { background: var(--error);   }
    .kpi-medium::before { background: var(--warning);  }
    .kpi-watermark {
        position: absolute; top: 10px; right: 12px;
        font-family: 'Material Symbols Outlined'; font-size: 64px;
        color: var(--muted); opacity: .12;
        font-variation-settings: 'FILL' 0, 'wght' 300;
        line-height: 1; pointer-events: none; user-select: none;
    }
    .kpi-label {
        font-size: .69rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: .08em; color: var(--muted); margin-bottom: 8px;
    }
    .kpi-high .kpi-label   { color: var(--on-error-container)     !important; }
    .kpi-medium .kpi-label { color: var(--on-secondary-container) !important; }
    .kpi-value {
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 2.5rem; font-weight: 700; color: var(--text);
        letter-spacing: -.01em; line-height: 1.2; position: relative; z-index: 1;
    }
    .kpi-high .kpi-value   { color: var(--on-error-container)     !important; }
    .kpi-medium .kpi-value { color: var(--on-secondary-container) !important; }
    .kpi-subtitle {
        font-size: .74rem; color: var(--muted);
        margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border);
    }
    .kpi-high .kpi-subtitle   { color: var(--on-error-container)     !important; border-color: rgba(186,26,26,.2)  !important; }
    .kpi-medium .kpi-subtitle { color: var(--on-secondary-container) !important; border-color: rgba(144,77,0,.2)   !important; }

    /* ── Section Headers (Inter, not serif) ───────────────────────────────── */
    .section-hdr {
        font-family: 'Inter', system-ui, sans-serif;
        font-size: 1.5rem; font-weight: 700; color: var(--text);
        padding-bottom: 12px; border-bottom: 1px solid var(--border);
        margin: 4px 0 20px 0; letter-spacing: -.02em;
    }

    /* ── Risk Cards (Stitch exact) ────────────────────────────────────────── */
    .risk-card {
        position: relative; background: var(--surface); border: 1px solid var(--border);
        overflow: hidden; margin-bottom: 18px;
        transition: border-color .2s ease; border-radius: 2px;
    }
    .risk-card:hover { border-color: var(--muted); }
    .risk-card::before {
        content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px;
    }
    .risk-high::before   { background: var(--error);   }
    .risk-medium::before { background: var(--warning); }
    .risk-low::before    { background: var(--primary); }
    .risk-inner { padding: 24px 32px 24px 32px; }
    .risk-hdr {
        display: flex; justify-content: space-between;
        align-items: flex-start; gap: 16px; margin-bottom: 20px;
    }
    .risk-title-area { flex: 1; }
    .risk-title {
        font-family: 'Inter', system-ui, sans-serif !important;
        font-size: 1.18rem !important; font-weight: 600 !important;
        color: var(--text) !important; margin: 0 0 5px 0 !important;
        letter-spacing: -.01em; line-height: 1.3;
    }
    .risk-ref {
        font-size: .78rem !important; font-style: italic !important;
        color: var(--muted) !important; margin: 0 !important;
    }
    .risk-badge {
        display: inline-block; padding: 4px 12px; border-radius: 3px;
        font-size: .67rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: .08em; flex-shrink: 0; margin-top: 2px; white-space: nowrap;
    }
    .badge-high   { background: var(--badge-high-bg);  color: var(--badge-high-text);  border: 1px solid var(--badge-high-border);  }
    .badge-medium { background: var(--badge-med-bg);   color: var(--badge-med-text);   border: 1px solid var(--badge-med-border);   }
    .badge-low    { background: rgba(0,59,27,.08);     color: var(--primary);          border: 1px solid rgba(0,59,27,.25);         }
    .risk-body { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    .risk-col-lbl {
        font-size: .67rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: .1em; color: var(--muted); margin-bottom: 8px;
    }
    .risk-action-lbl { color: var(--primary) !important; display: flex; align-items: center; gap: 5px; }
    .risk-col-txt { font-size: .9rem; color: var(--text); line-height: 1.65; margin: 0; }
    .risk-action-box {
        background: var(--surface-2);
        border: 1px solid var(--action-border);
        border-left: 4px solid var(--primary);
        border-radius: 4px; padding: 16px;
    }

    /* ── Nav radio active item (Streamlit 1.50: no data-checked, use :has) ── */
    [data-testid="stSidebar"] [role="radiogroup"] > div:has(input:checked) {
        background-color: var(--surface-2) !important;
        border-left: 4px solid var(--accent-gold) !important;
        border-radius: 0 6px 6px 0 !important;
        font-weight: 600 !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] [role="radiogroup"] > div:has(input:checked) label {
        color: var(--primary) !important;
    }

    /* ── Appearance pill: icon-only cells, CSS-driven (JS only fixes grid layout) */
    .st-key-theme_mode [role="radiogroup"] {
        background: var(--surface-3) !important;
        border-radius: 8px !important;
        padding: 3px !important;
        gap: 2px !important;
        width: 100% !important;
    }
    /* Each pill cell is a <label> in Streamlit 1.50 */
    .st-key-theme_mode [role="radiogroup"] > label {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        border-left: none !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 8px 4px !important;
        cursor: pointer !important;
        transition: all 0.15s ease !important;
        background: transparent !important;
    }
    /* Hide radio circle and original text */
    .st-key-theme_mode [role="radiogroup"] > label > div:first-child { display: none !important; }
    .st-key-theme_mode [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p {
        display: none !important;
    }
    .st-key-theme_mode [role="radiogroup"] > label [data-testid="stMarkdownContainer"] {
        display: flex !important; align-items: center !important; justify-content: center !important;
    }
    /* Show Material Symbol icon via ::after */
    .st-key-theme_mode [role="radiogroup"] > label [data-testid="stMarkdownContainer"]::after {
        font-family: 'Material Symbols Outlined' !important;
        font-size: 20px !important; line-height: 1 !important;
        font-variation-settings: 'FILL' 0, 'wght' 300 !important;
        color: var(--muted) !important;
    }
    .st-key-theme_mode [role="radiogroup"] > label:nth-child(1) [data-testid="stMarkdownContainer"]::after { content: "light_mode" !important; }
    .st-key-theme_mode [role="radiogroup"] > label:nth-child(2) [data-testid="stMarkdownContainer"]::after { content: "brightness_auto" !important; }
    .st-key-theme_mode [role="radiogroup"] > label:nth-child(3) [data-testid="stMarkdownContainer"]::after { content: "dark_mode" !important; }
    /* Selected cell: white background + filled primary-colour icon */
    .st-key-theme_mode [role="radiogroup"] > label:has(input:checked) {
        background: var(--surface) !important;
        box-shadow: 0 1px 4px rgba(0,0,0,.15) !important;
    }
    .st-key-theme_mode [role="radiogroup"] > label:has(input:checked) [data-testid="stMarkdownContainer"]::after {
        font-variation-settings: 'FILL' 1, 'wght' 600 !important;
        color: var(--primary) !important;
    }
    .st-key-theme_mode { width: 100% !important; }
    .st-key-theme_mode .stRadio { width: 100% !important; }
    .st-key-theme_mode > label {
        font-size: 0.68rem !important; font-weight: 700 !important;
        text-transform: uppercase !important; letter-spacing: 0.10em !important;
        color: var(--muted) !important; margin-bottom: 5px !important;
    }
    /* Keep selected icon centred within its cell */
    .st-key-theme_mode [role="radiogroup"] > label:has(input:checked) {
        justify-content: center !important;
    }
"""

_FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700;800&"
    "family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');"
)


def build_theme_css(mode: str) -> str:
    """Return the <style> block for the chosen appearance mode."""
    if mode == "Light":
        root = f":root {{ {_LIGHT_VARS} }}"
    elif mode == "Dark":
        root = f":root {{ {_DARK_VARS} }}"
    else:  # Auto: follow the OS preference
        root = (
            f":root {{ {_LIGHT_VARS} }}\n"
            f"@media (prefers-color-scheme: dark) {{ :root {{ {_DARK_VARS} }} }}"
        )
    return f"<style>\n{_FONT_IMPORT}\n{root}\n{_CSS_RULES}\n</style>"


def chart_palette(mode: str) -> dict:
    """Plotly font/grid colours per mode (Plotly can't read CSS variables)."""
    if mode == "Dark":
        return {"font": "#94A3BB", "grid": "rgba(255, 255, 255, 0.05)"}
    if mode == "Light":
        return {"font": "#475569", "grid": "rgba(0, 0, 0, 0.04)"}
    return {"font": "#64748B", "grid": "rgba(128, 128, 128, 0.08)"}  # System compromise


# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Compliance Review Engine",
    layout="wide",
    page_icon="⚖️",
    initial_sidebar_state="expanded",
)

# ── Session state (theme_mode must exist before the CSS is injected) ──────────
if "theme_mode" not in st.session_state or st.session_state.theme_mode == "System":
    st.session_state.theme_mode = "Light"
if "provider" not in st.session_state:
    st.session_state.provider = None
if "api_key" not in st.session_state:
    st.session_state.api_key = None
if "connected" not in st.session_state:
    st.session_state.connected = False
if "custom_base_url" not in st.session_state:
    st.session_state.custom_base_url = None
if "provider_model" not in st.session_state:
    st.session_state.provider_model = ""

st.markdown(build_theme_css(st.session_state.theme_mode), unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────
def latest_report():
    """Return the most recent report dict, or None."""
    files = sorted(glob.glob(str(REPORTS_DIR / "report_*.json")))
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as fh:
        return json.load(fh)


def load_demo_report():
    """Return the bundled demo report, or None if the file is missing."""
    if DEMO_REPORT.exists():
        with open(DEMO_REPORT, encoding="utf-8") as fh:
            return json.load(fh)
    return None


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
st.sidebar.markdown(
    '<div style="padding-bottom:16px;border-bottom:1px solid var(--border);margin-bottom:8px;">'
    '<span style="font-family:\'Material Symbols Outlined\';font-size:22px;color:var(--primary);'
    'font-variation-settings:\'FILL\' 1,\'wght\' 400;vertical-align:middle;margin-right:8px;">gavel</span>'
    '<span style="font-family:Inter,sans-serif;font-size:.95rem;font-weight:700;'
    'color:var(--text);letter-spacing:-.01em;">Compliance Engine</span>'
    '</div>',
    unsafe_allow_html=True,
)

nav_selection = st.sidebar.radio(
    "Navigation",
    options=["Latest Report", "Audit Trail"],
    label_visibility="collapsed",
)

st.sidebar.markdown("---")
st.sidebar.subheader("1. Connect Your AI")

provider = st.sidebar.selectbox(
    "AI Provider",
    options=["groq", "openrouter", "anthropic", "openai", "custom"],
    format_func=lambda x: {
        "groq":       "Groq  ·  Free tier",
        "openrouter": "OpenRouter  ·  Free tier",
        "anthropic":  "Anthropic  ·  Claude",
        "openai":     "OpenAI",
        "custom":     "Custom  ·  Any OpenAI-compatible",
    }[x],
)

custom_base_url = None
if provider == "custom":
    custom_base_url = st.sidebar.text_input(
        "API Base URL", placeholder="https://api.yourprovider.com/v1"
    )

# Every provider requires the user to supply their own model name.
provider_model = st.sidebar.text_input(
    "Model name",
    placeholder="Enter the model name for your provider",
)

key_label = {
    "groq":       "Groq API Key (free at console.groq.com)",
    "openrouter": "OpenRouter API Key (free at openrouter.ai)",
    "anthropic":  "Anthropic API Key",
    "openai":     "OpenAI API Key",
    "custom":     "API Key for your provider",
}
api_key = st.sidebar.text_input(key_label[provider], type="password")

if st.sidebar.button("Connect", use_container_width=True):
    if not api_key:
        st.sidebar.error("Enter an API key first.")
    elif not provider_model.strip():
        st.sidebar.error("Enter a model name first.")
    elif provider == "custom" and not custom_base_url:
        st.sidebar.error("Custom provider needs a base URL.")
    else:
        cmd = [
            sys.executable, str(TEST_SCRIPT),
            "--provider", provider,
            "--key", api_key,
            "--model", provider_model.strip(),
        ]
        if provider == "custom":
            cmd += ["--base-url", custom_base_url]
        with st.spinner(f"Testing {provider} connection..."):
            ok, output = run_subprocess(cmd)
        if ok:
            st.session_state.connected = True
            st.session_state.provider = provider
            st.session_state.api_key = api_key
            st.session_state.custom_base_url = custom_base_url
            st.session_state.provider_model = provider_model.strip()
            st.sidebar.success("✅ Connected")
        else:
            st.session_state.connected = False
            st.sidebar.error("Connection failed. Check your key, model name, and URL.")
            with st.sidebar.expander("Details"):
                st.code(output or "No output", language="text")

if st.session_state.connected:
    st.sidebar.caption(
        f"Connected to **{st.session_state.provider}** · "
        f"`{st.session_state.get('provider_model', '')}`"
    )

# ── Sidebar: upload + analyse ────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.subheader("2. Upload Client Profile")
uploaded = st.sidebar.file_uploader("Client profile (.txt)", type=["txt"])

if st.sidebar.button(
    "Analyse Now",
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
            "--provider", st.session_state.provider,
            "--key", st.session_state.api_key,
            "--model", st.session_state.get("provider_model", ""),
        ]
        if st.session_state.provider == "custom":
            cmd += ["--base-url", st.session_state.custom_base_url]
        with st.spinner(f"Analysing with {st.session_state.provider}..."):
            ok, output = run_subprocess(cmd)
        if ok:
            st.success("Analysis complete. See the Latest Report tab.")
        else:
            st.error("Analysis failed.")
            with st.expander("Details"):
                st.code(output or "No output", language="text")

st.sidebar.markdown("---")
st.sidebar.markdown('<div class="appearance-marker" style="display:none;height:0;margin:0;padding:0;"></div>', unsafe_allow_html=True)
st.sidebar.radio(
    "Appearance",
    options=["Light", "Auto", "Dark"],
    key="theme_mode",
    horizontal=True,
)

# Load latest report early to extract client name and processed date for the Top App Bar
report = latest_report()
is_demo = False
if report is None:
    report = load_demo_report()
    is_demo = report is not None

if report:
    client_name = report.get("client_name", "No Active Client")
    run_date = report.get("run_date", "N/A")
else:
    client_name = "No Active Client"
    run_date = "N/A"

# ── Main area ────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="hero">'
    f'<h1>Compliance Analysis Report</h1>'
    f'<div class="hero-metadata">'
    f'<span class="hero-meta-label">Client: {client_name}</span>'
    f'<span class="hero-meta-sub">Processed: {run_date}</span>'
    f'</div>'
    f'</div>',
    unsafe_allow_html=True,
)

if nav_selection == "Latest Report":
    if report is None:
        st.info("Connect your AI and run your first analysis using the sidebar.")
    elif is_demo:
        st.info(
            "📊 **Demo Mode** · Showing sample results for Meridian Advisory Group Inc. "
            "Connect your AI in the sidebar and click **Analyse Now** to process a real client file."
        )
    if report is not None:
        risks = report.get("compliance_risks", [])
        severities = [str(r.get("severity", "")).upper() for r in risks]
        high = severities.count("HIGH")
        medium = severities.count("MEDIUM")

        st.caption(
            f"**{report.get('client_name', 'Client')}** · "
            f"{report.get('run_date', '')} · "
            f"{report.get('provider', '')} ({report.get('model', '')})"
        )

        st.markdown(
            f"""
            <div class="kpi-row">
              <div class="kpi-card kpi-total">
                <div class="kpi-watermark">rule</div>
                <div class="kpi-label">Total Identified Risks</div>
                <div class="kpi-value">{len(risks)}</div>
                <div class="kpi-subtitle">Across CRA Regulatory Documents</div>
              </div>
              <div class="kpi-card kpi-high">
                <div class="kpi-label">High Severity</div>
                <div class="kpi-value">{high}</div>
                <div class="kpi-subtitle">Immediate action required</div>
              </div>
              <div class="kpi-card kpi-medium">
                <div class="kpi-label">Medium Severity</div>
                <div class="kpi-value">{medium}</div>
                <div class="kpi-subtitle">Monitor and document</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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
                    textfont=dict(color="#FFFFFF", size=11, family="Inter", weight="bold"),
                    hovertext=[r.get("client_exposure", "") for r in risks],
                )
            )
            fig.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color=pal["font"], family="Inter"),
                xaxis=dict(
                    title="Risk Severity",
                    gridcolor=pal["grid"], zerolinecolor=pal["grid"],
                    tickvals=[1, 2, 3],
                    ticktext=["Low", "Medium", "High"],
                ),
                yaxis=dict(autorange="reversed", gridcolor=pal["grid"], zerolinecolor=pal["grid"]),
                height=80 + 60 * len(risks),
                margin=dict(l=10, r=10, t=20, b=10),
                showlegend=False,
            )
            st.markdown(
                '<div style="background:var(--surface);border:1px solid var(--border);'
                'border-radius:8px;padding:24px 28px 8px 28px;margin-bottom:8px;">'
                '<div class="section-hdr" style="margin-top:0;">Risk Severity Overview</div>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="section-hdr">Detailed Findings</div>', unsafe_allow_html=True)
            for r in risks:
                sev = str(r.get("severity", "")).upper()
                stripe = {"HIGH": "risk-high", "MEDIUM": "risk-medium", "LOW": "risk-low"}.get(sev, "risk-low")
                badge  = {"HIGH": "badge-high", "MEDIUM": "badge-medium", "LOW": "badge-low"}.get(sev, "badge-low")
                st.markdown(
                    f"""
                    <article class="risk-card {stripe}">
                      <div class="risk-inner">
                        <div class="risk-hdr">
                          <div class="risk-title-area">
                            <h4 class="risk-title">{r.get('title', '')}</h4>
                            <p class="risk-ref">Ref: {r.get('cra_reference', '')}</p>
                          </div>
                          <span class="risk-badge {badge}">{sev}</span>
                        </div>
                        <div class="risk-body">
                          <div>
                            <div class="risk-col-lbl">Client Exposure</div>
                            <p class="risk-col-txt">{r.get('client_exposure', '')}</p>
                          </div>
                          <div class="risk-action-box">
                            <div class="risk-col-lbl risk-action-lbl">
                              <span style="font-family:'Material Symbols Outlined';font-size:15px;font-variation-settings:'FILL' 1,'wght' 400;line-height:1;">check_circle</span>
                              Recommended Action
                            </div>
                            <p class="risk-col-txt">{r.get('action', '')}</p>
                          </div>
                        </div>
                      </div>
                    </article>
                    """,
                    unsafe_allow_html=True,
                )

else:
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
    "Compliance Automation Engine  ·  **Arun Prabakar Vadaseri Rajendran**  ·  "
    "linkedin.com/in/arun-prabakar-vadaseri-rajendran"
)

# ── JS: appearance pill icons + nav radio active highlight ────────────────────
# Streamlit emotion CSS uses !important on layout properties; inline setProperty
# with 'important' priority is the only reliable override.
components.html("""
<script>
(function(){
  function applyStyles(){
    var d;
    try { d = window.parent.document; } catch(e){ return; }
    var cs = getComputedStyle(d.documentElement);

    /* ── Appearance pill: JS only forces grid display (CSS handles icons+selection) ── */
    var rg = d.querySelector('.st-key-theme_mode [role="radiogroup"]');
    if(rg){
      rg.style.setProperty('display','grid','important');
      rg.style.setProperty('grid-template-columns','repeat(3,1fr)','important');
      rg.style.setProperty('width','100%','important');
      [...rg.children].forEach(function(item){
        item.style.setProperty('width','auto','important');
        item.style.setProperty('min-width','0','important');
        item.style.setProperty('border-left','none','important');
      });
      if(!rg._pillBound){
        rg._pillBound = true;
        rg.addEventListener('change', function(){ setTimeout(applyStyles,60); });
      }
    } else {
      setTimeout(applyStyles, 300);
    }

    /* ── Full-width pill: expand .stRadio wrapper (emotion constrains it to ~118px) ── */
    var tm = d.querySelector('.st-key-theme_mode');
    if(tm){
      tm.style.setProperty('width','100%','important');
      var stRadio = tm.querySelector('.stRadio');
      if(stRadio) stRadio.style.setProperty('width','100%','important');
    }

    /* ── Nav radio active highlight ── */
    var surf2 = cs.getPropertyValue('--surface-2').trim()   || '#f4f4f0';
    var gold  = cs.getPropertyValue('--accent-gold').trim() || '#904d00';
    var prim  = cs.getPropertyValue('--primary').trim()     || '#003b1b';

    var navGroups = d.querySelectorAll('[data-testid="stSidebar"] [role="radiogroup"]');
    navGroups.forEach(function(group){
      if(group.closest('.st-key-theme_mode')) return;
      [...group.children].forEach(function(item){
        var ok  = !!item.querySelector('input:checked');
        item.style.setProperty('background-color', ok ? surf2 : 'transparent','important');
        item.style.setProperty('border-left', ok ? '4px solid '+gold : '4px solid transparent','important');
        item.style.setProperty('border-radius','0 6px 6px 0','important');
        /* In Streamlit 1.50, item may already be the <label> */
        var lbl = (item.tagName === 'LABEL') ? item : item.querySelector('label');
        if(lbl) lbl.style.setProperty('color', ok ? prim : '','important');
      });
      if(!group._navBound){
        group._navBound = true;
        group.addEventListener('change', function(){ setTimeout(applyStyles,60); });
      }
    });
  }

  /* Run after Streamlit renders, then watch for re-renders */
  setTimeout(applyStyles, 700);
  setTimeout(applyStyles, 1500);
  var obs = new MutationObserver(function(){ applyStyles(); });
  setTimeout(function(){
    var sb = null;
    try { sb = window.parent.document.querySelector('[data-testid="stSidebar"]'); } catch(e){}
    if(sb) obs.observe(sb, {childList:true, subtree:true, attributes:false});
  }, 1000);
})();
</script>
""", height=0)
