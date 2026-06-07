"""
Extracts and combines text from all PDFs in a folder.

Importable:
    from importlib helper used by the pipeline, this exposes
    extract_text_from_folder(folder_path) -> str
"""

import sys
from pathlib import Path

from pypdf import PdfReader
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REGULATIONS_DIR = PROJECT_ROOT / "docs" / "regulations"

SOURCE_SEPARATOR = "\n\n=== SOURCE: {filename} ===\n\n"


def extract_text_from_folder(folder_path: str) -> str:
    """
    Read every PDF in ``folder_path`` and return their combined text.

    - Files are separated by a clear "=== SOURCE: <filename> ===" header.
    - Encrypted PDFs are skipped with a warning.
    - Blank pages are skipped silently.

    Raises:
        FileNotFoundError if the folder contains no PDF files.
    """
    folder = Path(folder_path)
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")

    pdf_files = sorted(folder.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found in {folder}. "
            f"Add at least one CRA regulation PDF and try again."
        )

    combined = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    ) as progress:
        for pdf_path in pdf_files:
            try:
                reader = PdfReader(str(pdf_path))
            except Exception as exc:  # noqa: BLE001 (a malformed file should not kill the run)
                console.print(f"[yellow]⚠ Skipping unreadable PDF {pdf_path.name}: {exc}[/yellow]")
                continue

            if reader.is_encrypted:
                # Try an empty-password decrypt; many "encrypted" PDFs allow it.
                try:
                    if reader.decrypt("") == 0:
                        console.print(f"[yellow]⚠ Skipping encrypted PDF: {pdf_path.name}[/yellow]")
                        continue
                except Exception:
                    console.print(f"[yellow]⚠ Skipping encrypted PDF: {pdf_path.name}[/yellow]")
                    continue

            total_pages = len(reader.pages)
            combined.append(SOURCE_SEPARATOR.format(filename=pdf_path.name))

            task = progress.add_task(f"Reading {pdf_path.name}", total=total_pages)
            for n, page in enumerate(reader.pages, start=1):
                progress.update(
                    task,
                    description=f"Reading page {n} of {total_pages}: {pdf_path.name}",
                    completed=n,
                )
                text = page.extract_text() or ""
                if text.strip():  # skip blank pages silently
                    combined.append(text)

    return "".join(combined)


if __name__ == "__main__":
    try:
        text = extract_text_from_folder(str(DEFAULT_REGULATIONS_DIR))
    except FileNotFoundError as exc:
        console.print(f"[red]✗ {exc}[/red]")
        sys.exit(1)

    console.print(f"\n[green]✓ Extracted {len(text):,} characters[/green]")
    console.print("\n[bold]First 300 characters:[/bold]")
    console.print(text[:300])
