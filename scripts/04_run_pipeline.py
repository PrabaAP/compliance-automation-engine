"""
Master orchestrator. Called by the Streamlit dashboard and by n8n.
provider and api_key must be passed as arguments.

Usage:
    python scripts/04_run_pipeline.py --provider groq --key YOUR_KEY
    python scripts/04_run_pipeline.py --provider custom --key KEY \\
        --base-url https://api.example.com/v1 --model my-model
"""

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_router import PROVIDER_CONFIG, get_model_name  # noqa: E402

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGULATIONS_DIR = PROJECT_ROOT / "docs" / "regulations"
CLIENT_PROFILE = PROJECT_ROOT / "docs" / "clients" / "client_profile.txt"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"


def _load_sibling(module_name, filename):
    path = Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_analysis = _load_sibling("analyze_compliance", "03_analyze_compliance.py").run_analysis


def preflight(provider: str, custom_base_url=None, custom_model=None) -> None:
    """Stop the run early if anything required is missing."""
    if provider not in PROVIDER_CONFIG:
        console.print(f"[red]✗ Unsupported provider '{provider}'.[/red]")
        sys.exit(1)
    console.print(f"[green]✓[/green] Provider '{provider}' is supported")

    if provider == "custom" and (not custom_base_url or not custom_model):
        console.print("[red]✗ Custom provider needs both --base-url and --model.[/red]")
        sys.exit(1)

    pdfs = list(REGULATIONS_DIR.glob("*.pdf")) if REGULATIONS_DIR.exists() else []
    if not pdfs:
        console.print(f"[red]✗ No PDFs found in {REGULATIONS_DIR}.[/red]")
        sys.exit(1)
    console.print(f"[green]✓[/green] Found {len(pdfs)} regulation PDF(s)")

    if not CLIENT_PROFILE.exists():
        console.print(f"[red]✗ Client profile missing: {CLIENT_PROFILE}.[/red]")
        sys.exit(1)
    console.print("[green]✓[/green] Client profile present")


def main():
    parser = argparse.ArgumentParser(description="Run the compliance automation pipeline.")
    parser.add_argument("--provider", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--model", required=True, help="Model name to use")
    parser.add_argument("--base-url", default=None, help="Base URL (custom provider only)")
    args = parser.parse_args()

    start = time.time()

    console.print("[bold]Pre-flight checks[/bold]")
    preflight(args.provider, args.base_url, args.model)

    console.print("\n[bold]Running analysis[/bold]")
    report = run_analysis(args.provider, args.key, args.model, args.base_url)

    runtime = time.time() - start
    model = get_model_name(args.provider, args.model)

    # Locate the freshly written report + summary.
    reports = sorted(REPORTS_DIR.glob("report_*.json"))
    summaries = sorted(REPORTS_DIR.glob("report_*_summary.txt"))
    report_file = reports[-1].name if reports else "(none)"
    summary_file = summaries[-1].name if summaries else "(none)"
    risk_count = len(report.get("compliance_risks", []))

    summary_box = (
        f"✅ Report:   outputs/reports/{report_file}\n"
        f"✅ Summary:  outputs/reports/{summary_file}\n"
        f"📋 Risks:    {risk_count} compliance risk areas\n"
        f"🤖 Provider: {args.provider} ({model})\n"
        f"⏱  Runtime:  {runtime:.1f} seconds"
    )
    console.print()
    console.print(Panel(summary_box, title="Pipeline Complete", border_style="green", expand=False))


if __name__ == "__main__":
    main()
