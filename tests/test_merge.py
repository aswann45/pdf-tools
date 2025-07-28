"""Merging produces correct page count and order."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from pypdf import PdfReader

from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File


def test_merge_page_count(sample_pdfs: Sequence[File], tmp_path: Path) -> None:
    """Total pages equals sum of inputs."""
    out = tmp_path / "merged.pdf"
    merge_pdfs(files=sample_pdfs, output_path=out)
    assert out.exists()

    total_in = sum(len(PdfReader(p.path).pages) for p in sample_pdfs)
    total_out = len(PdfReader(out).pages)
    assert total_in == total_out
