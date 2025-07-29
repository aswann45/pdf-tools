"""Shared fixtures and helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from pdf_tools.models.files import File


def make_pdf(path: Path, pages: int = 1) -> None:  # pragma: no cover
    """Create a simple PDF via ReportLab."""
    c = canvas.Canvas(str(path))
    for i in range(pages):
        c.drawString(72, 720, f"Page {i + 1}")
        c.showPage()
    c.save()


@pytest.fixture(scope="session")
def libreoffice_available() -> bool:  # noqa: D401
    """Return True if a LibreOffice CLI tool is on $PATH."""
    return shutil.which("unoconvert") is not None  # pragma: nocover


@pytest.fixture(scope="function")
def sample_pdfs(tmp_path: Path) -> list[File]:
    """Return three small PDF files with 1-3 pages each."""
    paths: list[Path] = []
    for i, pages in enumerate((1, 2, 3), 1):
        p = tmp_path / f"sample{i}.pdf"
        make_pdf(p, pages)
        paths.append(p)
    return [File(path=p) for p in paths]
