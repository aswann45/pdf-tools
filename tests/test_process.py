"""Process pipeline tests."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from pdf_tools.process import convert_and_merge_pdfs
from tests.conftest import make_pdf


def test_convert_and_merge_accepts_paths_and_existing_pdfs(
    tmp_path: Path,
) -> None:
    """Existing PDFs pass through and path-like inputs are accepted."""
    pdf = tmp_path / "source.pdf"
    image = tmp_path / "image.png"
    out = tmp_path / "merged.pdf"
    make_pdf(pdf, pages=2)
    Image.new("RGB", (10, 10), (255, 0, 0)).save(image)

    result = convert_and_merge_pdfs([pdf, str(image)], output_path=out)

    assert result.path == out
    assert len(PdfReader(out).pages) == 3
