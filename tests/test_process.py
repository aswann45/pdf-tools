"""Process pipeline tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pdf_oxide import PdfDocument
from PIL import Image

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
    assert PdfDocument(str(out)).page_count() == 3


def test_process_merges_successes_after_conversion_failure(
    tmp_path: Path,
) -> None:
    """Failed conversions are omitted while valid PDFs merge."""
    existing = tmp_path / "existing.pdf"
    image = tmp_path / "image.png"
    unsupported = tmp_path / "unsupported.txt"
    output = tmp_path / "merged.pdf"
    make_pdf(existing, pages=2)
    Image.new("RGB", (10, 10)).save(image)
    unsupported.write_text("cannot convert")

    convert_and_merge_pdfs([existing, unsupported, image], output_path=output)

    assert PdfDocument(str(output)).page_count() == 3


def test_process_requires_existing_output_parent(tmp_path: Path) -> None:
    """A retained PDF reaches merge, which rejects a missing output parent."""
    existing = tmp_path / "existing.pdf"
    make_pdf(existing, pages=1)

    with pytest.raises(FileNotFoundError, match="Output directory"):
        convert_and_merge_pdfs(
            [existing], output_path=tmp_path / "missing" / "merged.pdf"
        )
