"""
Core analysis. Sends PDFs + client profile to AI, returns structured risk JSON.
Requires provider and api_key to be passed — never reads them from env.

Importable: exposes run_analysis(provider, api_key) and parse_json_response(text).
"""

import importlib.util
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table

# Ensure sibling modules import cleanly regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_router import call_ai, get_model_name  # noqa: E402

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGULATIONS_DIR = PROJECT_ROOT / "docs" / "regulations"
CLIENT_PROFILE = PROJECT_ROOT / "docs" / "clients" / "client_profile.txt"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"
DB_PATH = PROJECT_ROOT / "database" / "audit.db"

SEVERITY_COLORS = {"HIGH": "red", "MEDIUM": "yellow", "LOW": "green"}


def _load_sibling(module_name, filename):
    """Load a digit-prefixed sibling script (e.g. 02_extract_pdf.py) as a module."""
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# extract_text_from_folder lives in 02_extract_pdf.py (not a normal import name).
extract_text_from_folder = _load_sibling("extract_pdf", "02_extract_pdf.py").extract_text_from_folder


def parse_json_response(text: str) -> dict:
    """
    Parse an AI response into a dict.

    1. Try json.loads() directly.
    2. If that fails, extract a ```json ... ``` (or bare ``` ... ```) block.
    3. As a last resort, grab the first {...} span.

    Raises ValueError if no valid JSON can be recovered.
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    # Fenced code block, optionally tagged as json.
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except json.JSONDecodeError:
            pass

    # First balanced-looking {...} span.
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not parse AI response as JSON")


def _extract_client_name(profile_text: str) -> str:
    """Pull the client name from the 'Company Name:' line in the profile."""
    for line in profile_text.splitlines():
        if line.strip().lower().startswith("company name:"):
            return line.split(":", 1)[1].strip()
    return "Unknown Client"


def _build_prompt(pdf_text: str, client_profile: str) -> str:
    return f"""You are a Senior Compliance Auditor with expertise in Canadian tax law (CRA).

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
{{"compliance_risks": [{{"title":"...","severity":"...","cra_reference":"...","client_exposure":"...","action":"..."}}, ...]}}"""


def _save_audit_row(run_date, client_name, provider, model, pdf_count, risk_count, report_file):
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
        conn.execute(
            "INSERT INTO analyses "
            "(run_date, client_name, provider, model, pdf_count, risk_count, report_file) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (run_date, client_name, provider, model, pdf_count, risk_count, report_file),
        )
        conn.commit()
    finally:
        conn.close()


def _print_risk_table(client_name, risks):
    table = Table(title=f"Compliance Risk Checklist — {client_name}")
    table.add_column("Severity", style="bold")
    table.add_column("Title")
    table.add_column("CRA Reference", style="italic")
    table.add_column("Action")
    for risk in risks:
        severity = str(risk.get("severity", "")).upper()
        color = SEVERITY_COLORS.get(severity, "white")
        table.add_row(
            f"[{color}]{severity}[/{color}]",
            risk.get("title", ""),
            risk.get("cra_reference", ""),
            risk.get("action", ""),
        )
    console.print(table)


def run_analysis(provider: str, api_key: str, custom_base_url: str = None, custom_model: str = None) -> dict:
    """
    Run the full compliance analysis and persist the report, summary and audit row.
    Returns the report dict.
    """
    if not CLIENT_PROFILE.exists():
        raise FileNotFoundError(
            f"Client profile not found at {CLIENT_PROFILE}. "
            f"Add docs/clients/client_profile.txt and try again."
        )

    client_profile = CLIENT_PROFILE.read_text(encoding="utf-8")
    client_name = _extract_client_name(client_profile)

    pdf_text = extract_text_from_folder(str(REGULATIONS_DIR))
    pdf_count = len(list(REGULATIONS_DIR.glob("*.pdf")))

    prompt = _build_prompt(pdf_text, client_profile)
    model = get_model_name(provider, custom_model)

    with console.status(f"[bold cyan]Sending to {provider} ({model})...[/bold cyan]", spinner="dots"):
        raw = call_ai(
            prompt=prompt,
            provider=provider,
            api_key=api_key,
            custom_base_url=custom_base_url,
            custom_model=custom_model,
        )

    parsed = parse_json_response(raw)
    risks = parsed.get("compliance_risks", [])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"report_{timestamp}.json"
    summary_path = REPORTS_DIR / f"report_{timestamp}_summary.txt"

    report = {
        "client_name": client_name,
        "run_date": run_date,
        "provider": provider,
        "model": model,
        "compliance_risks": risks,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Human-readable summary table.
    summary_lines = ["SEVERITY | Title | Action"]
    for risk in risks:
        summary_lines.append(
            f"{str(risk.get('severity','')).upper()} | "
            f"{risk.get('title','')} | {risk.get('action','')}"
        )
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    _save_audit_row(
        run_date, client_name, provider, model, pdf_count, len(risks), report_path.name
    )

    _print_risk_table(client_name, risks)
    console.print(f"\n[green]✓ Report saved:[/green] {report_path}")
    console.print(f"[green]✓ Summary saved:[/green] {summary_path}")

    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run compliance analysis directly.")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    args = parser.parse_args()

    run_analysis(args.provider, args.key, args.base_url, args.model)
