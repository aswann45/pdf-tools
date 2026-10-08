"""Watermark adds overlay and keeps page count."""

from __future__ import annotations

from pathlib import Path

import pytest
from pdf_oxide import PdfDocument
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DictionaryObject
from reportlab.pdfgen import canvas

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

    resources = PdfReader(destination).pages[0]["/Resources"].get_object()
    assert isinstance(resources, DictionaryObject)
    states = resources["/ExtGState"].get_object()
    assert isinstance(states, DictionaryObject)
    assert any(
        state.get_object().get("/ca") == pytest.approx(0.4)
        for state in states.values()
    )


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

    matrices: list[list[float]] = []

    def record_text(
        text: str,
        current_matrix: list[float],
        _text_matrix: list[float],
        _font: object,
        _font_size: float,
    ) -> None:
        if "AX" in text:
            matrices.append(current_matrix)

    PdfReader(destination).pages[0].extract_text(visitor_text=record_text)
    assert len(matrices) == 1
    assert (matrices[0][0], -matrices[0][1]) == pytest.approx(direction)


def test_watermark_alignment_on_custom_page(tmp_path: Path) -> None:
    """Text alignment uses the requested box on a non-default page size."""
    source = tmp_path / "source.pdf"
    drawing = canvas.Canvas(str(source), pagesize=(400, 600))
    drawing.drawString(20, 20, "SOURCE")
    drawing.save()

    x_positions: dict[str, float] = {}
    for alignment in ("left", "center", "right"):
        destination = tmp_path / f"{alignment}.pdf"
        add_text_watermark(
            src=source,
            dst=destination,
            opts=WatermarkOptions(
                text="TEST",
                box_width=200,
                h_align=alignment,
            ),
        )
        document = PdfDocument(str(destination))
        page_box = PdfReader(destination).pages[0].mediabox
        assert (float(page_box.width), float(page_box.height)) == (
            400,
            600,
        )
        spans = [
            span for span in document.extract_spans(0) if span.text == "TEST"
        ]
        assert len(spans) == 1
        x_positions[alignment] = spans[0].bbox[0]
        assert "SOURCE" in document.extract_text(0)

    assert x_positions["left"] == pytest.approx(100)
    assert x_positions["left"] < x_positions["center"]
    assert x_positions["center"] < x_positions["right"]


def test_watermark_font_alias_and_lineheight(tmp_path: Path) -> None:
    """Existing font aliases and line spacing remain accepted."""
    source = tmp_path / "source.pdf"
    destination = tmp_path / "destination.pdf"
    make_pdf(source)

    add_text_watermark(
        src=source,
        dst=destination,
        opts=WatermarkOptions(
            text="TOP\nBOTTOM",
            font_name="hebo",
            font_size=24,
            lineheight=1.5,
        ),
    )

    spans = {
        span.text: span
        for span in PdfDocument(str(destination)).extract_spans(0)
        if span.text in {"TOP", "BOTTOM"}
    }
    assert set(spans) == {"TOP", "BOTTOM"}
    assert spans["TOP"].font_name == "Helvetica-Bold"
    assert spans["TOP"].bbox[1] - spans["BOTTOM"].bbox[1] == pytest.approx(36)


def test_watermark_uses_visible_size_of_rotated_page(tmp_path: Path) -> None:
    """A source page's rotation does not shift explicit watermark positions."""
    original = tmp_path / "original.pdf"
    source = tmp_path / "rotated.pdf"
    destination = tmp_path / "destination.pdf"
    drawing = canvas.Canvas(str(original), pagesize=(400, 600))
    drawing.drawString(20, 20, "SOURCE")
    drawing.save()
    writer = PdfWriter(clone_from=original)
    writer.pages[0].rotate(90)
    writer.write(source)

    add_text_watermark(
        src=source,
        dst=destination,
        opts=WatermarkOptions(text="AX", x=100, y=120),
    )

    page = PdfReader(destination).pages[0]
    assert page.rotation == 0
    assert (float(page.mediabox.width), float(page.mediabox.height)) == (
        600,
        400,
    )
    document = PdfDocument(str(destination))
    spans = [span for span in document.extract_spans(0) if span.text == "AX"]
    assert len(spans) == 1
    assert spans[0].bbox[0] < 100
    assert spans[0].bbox[0] + spans[0].bbox[2] > 100
    assert "SOURCE" in document.extract_text(0)
