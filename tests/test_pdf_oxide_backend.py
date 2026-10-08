"""Regression checks for the private PDF Oxide integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from pdf_oxide import PdfDocument
from PIL import Image
from reportlab.pdfgen import canvas

from pdf_tools._pdf_backend import get_pdf_page_count
from pdf_tools.convert.service import convert_image_to_pdf
from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File


@pytest.mark.parametrize(
    ("image_format", "mode"),
    [
        ("JPEG", "RGB"),
        ("PNG", "RGB"),
        ("PNG", "RGBA"),
        ("PNG", "L"),
        ("TIFF", "RGB"),
        ("BMP", "RGB"),
    ],
)
def test_image_formats(tmp_path: Path, image_format: str, mode: str) -> None:
    """All accepted raster formats yield a valid one-page PDF."""
    suffix = {"JPEG": "jpg", "PNG": "png", "TIFF": "tiff"}.get(
        image_format, "bmp"
    )
    source = tmp_path / f"source.{suffix}"
    Image.new(mode, (24, 16)).save(source, format=image_format)

    result = convert_image_to_pdf(
        File(path=source, bookmark_name="Image"),
    )

    assert result.bookmark_name == "Image"
    assert get_pdf_page_count(result.path) == 1


def test_image_rejects_misleading_content(tmp_path: Path) -> None:
    """Pillow's detected format remains the source of truth."""
    source = tmp_path / "fake.png"
    source.write_text("not an image")
    with pytest.raises(RuntimeError, match="Could not convert image"):
        convert_image_to_pdf(source)


def test_merge_preserves_order_pages_and_size(tmp_path: Path) -> None:
    """PDF Oxide merge retains source order and page dimensions."""
    sources: list[Path] = []
    for index, size in enumerate(((200, 300), (300, 200), (400, 500))):
        source = tmp_path / f"source-{index}.pdf"
        fixture = canvas.Canvas(str(source), pagesize=size)
        fixture.drawString(20, 100, f"SOURCE {index}")
        fixture.showPage()
        fixture.drawString(20, 100, f"SECOND {index}")
        fixture.save()
        sources.append(source)

    output = tmp_path / "merged.pdf"
    merge_pdfs(sources, output)
    document = PdfDocument(str(output))

    assert document.page_count() == 6
    for index in range(3):
        first = index * 2
        assert f"SOURCE {index}" in document.extract_text(first)
        assert f"SECOND {index}" in document.extract_text(first + 1)
        assert document.page_media_box(first)[2:] == pytest.approx(
            ((200, 300), (300, 200), (400, 500))[index]
        )


def test_merge_bookmark_compatibility(tmp_path: Path) -> None:
    """Bookmark titles and destination pages remain intact."""
    sources: list[File] = []
    for index, name in enumerate(("Résumé", "second.pdf")):
        source = tmp_path / f"source-{index}.pdf"
        fixture = canvas.Canvas(str(source))
        fixture.drawString(20, 100, str(index))
        if index == 0:
            fixture.showPage()
            fixture.drawString(20, 100, "second page")
        fixture.save()
        sources.append(
            File(path=source, bookmark_name=name if index == 0 else None)
        )

    output = tmp_path / "bookmarked.pdf"
    merge_pdfs(sources, output, set_bookmarks=True)
    outline = PdfDocument(str(output)).get_outline()

    assert outline == [
        {"title": "Résumé", "page": 0, "children": []},
        {"title": "source-1.pdf", "page": 2, "children": []},
    ]
