"""Watermark adds overlay and keeps page count."""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest
from pdf_oxide import PdfDocument

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
    output = PdfDocument(str(dst))
    assert output.page_count() == 3
    assert "TEST" in output.extract_text(0)
    assert "TEST" not in output.extract_text(1)
    assert "TEST" not in output.extract_text(2)
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


def test_watermark_all_pages_and_style(tmp_path: Path) -> None:
    """Text, color, size, and opacity survive the output save."""
    source = tmp_path / "source.pdf"
    destination = tmp_path / "destination.pdf"
    make_pdf(source, pages=2)
    options = WatermarkOptions(
        text="DRAFT",
        all_pages=True,
        color="#00FF00",
        font_size=36,
        opacity=0.4,
        x=200,
        y=300,
        h_align="left",
    )

    result = add_text_watermark(src=source, dst=destination, opts=options)

    assert result.pages_processed == 2
    document = PdfDocument(str(destination))
    for page_number in range(2):
        spans = [
            span
            for span in document.extract_spans(page_number)
            if span.text == "DRAFT"
        ]
        assert len(spans) == 1
        assert spans[0].color == pytest.approx((0.0, 1.0, 0.0))
        assert spans[0].font_size == pytest.approx(36.0)
        assert spans[0].bbox[0] == pytest.approx(200 - 250, abs=2)

    with pymupdf.open(destination) as styled:
        trace = styled[0].get_texttrace()
        watermark = next(
            item
            for item in trace
            if "".join(chr(char[0]) for char in item["chars"]) == "DRAFT"
        )
        assert watermark["opacity"] == pytest.approx(0.4)


@pytest.mark.parametrize(
    ("rotation", "direction"),
    [
        (0, (1.0, 0.0)),
        (90, (0.0, -1.0)),
        (180, (-1.0, 0.0)),
        (270, (0.0, 1.0)),
    ],
)
def test_watermark_rotation(
    tmp_path: Path, rotation: int, direction: tuple[float, float]
) -> None:
    """All supported right-angle rotations affect written text."""
    source = tmp_path / "source.pdf"
    destination = tmp_path / "destination.pdf"
    make_pdf(source)

    add_text_watermark(
        src=source,
        dst=destination,
        opts=WatermarkOptions(
            text="AX",
            rotation=rotation,
            x=200,
            y=300,
            box_width=300,
            box_height=100,
        ),
    )

    with pymupdf.open(destination) as styled:
        trace = styled[0].get_texttrace()
        watermark = next(
            item
            for item in trace
            if "".join(chr(char[0]) for char in item["chars"]) == "AX"
        )
        assert watermark["dir"] == pytest.approx(direction)
