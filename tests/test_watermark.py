"""Watermark adds overlay and keeps page count."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from pdf_tools.models.watermark import WatermarkOptions
from pdf_tools.watermark.service import add_text_watermark
from tests.conftest import make_pdf


def test_watermark_first_page(tmp_path: Path) -> None:
    """First-page-only flag leaves later pages untouched."""
    src = tmp_path / "src.pdf"
    make_pdf(src, pages=3)

    opts = WatermarkOptions(text="TEST", all_pages=False, color="#F00")
    dst = tmp_path / "dst.pdf"
    result = add_text_watermark(src=src, dst=dst, opts=opts)

    assert result.pages_processed == 1
    assert len(PdfReader(dst).pages) == 3
    assert result.message == (
        f"Added watermark on {result.pages_processed} page(s) → "
        f"{result.output.path}"
    )


def test_same_src_dst_paths_raises_value_error(tmp_path: Path) -> None:
    """Identical source and destination paths raise ValueError."""
    src = tmp_path / "src.pdf"
    dst = src
    opts = WatermarkOptions(text="TEST")

    with pytest.raises(ValueError):
        add_text_watermark(src=src, dst=dst, opts=opts)


def test_watermark_accepts_pathlike_inputs(tmp_path: Path) -> None:
    """Watermark service accepts string paths."""
    src = tmp_path / "src.pdf"
    make_pdf(src, pages=1)
    dst = tmp_path / "dst.pdf"

    result = add_text_watermark(
        src=str(src),
        dst=str(dst),
        opts=WatermarkOptions(text="TEST"),
    )

    assert result.output.path == dst
    assert dst.exists()
