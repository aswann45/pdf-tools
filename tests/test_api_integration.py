"""Real-file parity between functional operations and PDFTools methods."""

from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError
from pypdf import PdfReader
from reportlab.pdfgen import canvas

import pdf_tools
from pdf_tools import (
    DocumentExtraction,
    ExtractionOptions,
    File,
    OcrMode,
    PDFTools,
    TextSource,
    WatermarkOptions,
    WatermarkResult,
)
from pdf_tools.extract.exceptions import ExtractionError


def make_pdf(path: Path, labels: list[str]) -> None:
    """Create a small PDF with selectable text on each page."""
    writer = canvas.Canvas(str(path))
    for label in labels:
        writer.drawString(72, 700, label)
        writer.showPage()
    writer.save()


def test_merge_with_bookmarks_and_order(tmp_path: Path) -> None:
    """Both merge interfaces retain page order and bookmarks."""
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    make_pdf(first, ["First document"])
    make_pdf(second, ["Second document", "Last page"])
    outputs = [tmp_path / "functional.pdf", tmp_path / "facade.pdf"]
    files = [
        File(path=first, bookmark_name="Start"),
        File(path=second, bookmark_name="Continuation"),
    ]
    results = [
        pdf_tools.merge_pdfs(files, outputs[0], set_bookmarks=True),
        PDFTools().merge_pdfs(files, outputs[1], set_bookmarks=True),
    ]
    for result, output in zip(results, outputs, strict=True):
        assert result.path == output
        reader = PdfReader(output)
        assert len(reader.pages) == 3
        assert [getattr(item, "title", None) for item in reader.outline] == [
            "Start",
            "Continuation",
        ]
        assert [page.extract_text().strip() for page in reader.pages] == [
            "First document",
            "Second document",
            "Last page",
        ]


def test_image_conversion_and_batch(tmp_path: Path) -> None:
    """Image conversion and batch result models agree across APIs."""
    image = tmp_path / "picture.png"
    Image.new("RGB", (40, 30), "blue").save(image)
    outputs = [tmp_path / "functional.pdf", tmp_path / "facade.pdf"]
    results = [
        pdf_tools.convert_image_to_pdf(image, outputs[0]),
        PDFTools().convert_image_to_pdf(image, outputs[1]),
    ]
    for result, output in zip(results, outputs, strict=True):
        assert isinstance(result, File)
        assert result.path == output
        assert len(PdfReader(output).pages) == 1
    unsupported = tmp_path / "notes.txt"
    unsupported.write_text("unsupported", encoding="utf-8")
    out_a = tmp_path / "batch_a"
    out_b = tmp_path / "batch_b"
    out_a.mkdir()
    out_b.mkdir()
    batches = [
        pdf_tools.convert_files_to_pdfs([image, unsupported], out_a),
        PDFTools().convert_files_to_pdfs([image, unsupported], out_b),
    ]
    for batch in batches:
        assert len(batch.converted) == 1
        assert len(batch.skipped) == 1
        assert batch.skipped[0].path == unsupported
        assert len(PdfReader(batch.converted[0].path).pages) == 1


def test_process_and_watermark(tmp_path: Path) -> None:
    """Processing and watermarking produce readable equivalent PDFs."""
    image = tmp_path / "picture.jpg"
    Image.new("RGB", (20, 20), "green").save(image)
    pdf = tmp_path / "native.pdf"
    make_pdf(pdf, ["Native"])
    merged_paths = [tmp_path / "merged_a.pdf", tmp_path / "merged_b.pdf"]
    merged = [
        pdf_tools.convert_and_merge_pdfs([pdf, image], merged_paths[0]),
        PDFTools().convert_and_merge_pdfs([pdf, image], merged_paths[1]),
    ]
    for merge_result in merged:
        assert len(PdfReader(merge_result.path).pages) == 2
    options = WatermarkOptions(text="DRAFT", all_pages=True)
    stamped_paths = [tmp_path / "stamp_a.pdf", tmp_path / "stamp_b.pdf"]
    stamped = [
        pdf_tools.add_text_watermark(
            src=pdf, dst=stamped_paths[0], opts=options
        ),
        PDFTools().add_text_watermark(
            src=pdf, dst=stamped_paths[1], opts=options
        ),
    ]
    for stamp_result, output in zip(stamped, stamped_paths, strict=True):
        assert isinstance(stamp_result, WatermarkResult)
        assert stamp_result.pages_processed == 1
        assert stamp_result.output.path == output
        assert "DRAFT" in PdfReader(output).pages[0].extract_text()


def test_text_extraction_and_selection(tmp_path: Path) -> None:
    """Both entry points return matching page-level text and provenance."""
    path = tmp_path / "native.pdf"
    make_pdf(path, ["First", "Second", "Third"])
    tools = PDFTools()
    functional = pdf_tools.extract_pdf_text(
        path, ocr=OcrMode.NEVER, pages=[3, 1, 3]
    )
    facade = tools.extract_pdf_text(path, ocr=OcrMode.NEVER, pages=[3, 1, 3])
    assert isinstance(facade, DocumentExtraction)
    assert facade == functional
    assert facade.text == "First\fThird"
    assert [page.page_number for page in facade.pages] == [1, 3]
    assert all(page.text_source == TextSource.NATIVE for page in facade.pages)
    options = ExtractionOptions(ocr=OcrMode.NEVER, pages=[2])
    assert tools.extract_pdf(path, options) == pdf_tools.extract_pdf(
        path, options
    )


def test_image_extraction_and_errors(tmp_path: Path) -> None:
    """Both interfaces save images and preserve extraction errors."""
    image = tmp_path / "embedded.jpg"
    Image.new("RGB", (25, 15), "red").save(image)
    path = tmp_path / "image.pdf"
    writer = canvas.Canvas(str(path))
    writer.drawImage(str(image), 72, 600)
    writer.save()
    out_a = tmp_path / "images_a"
    out_b = tmp_path / "images_b"
    out_a.mkdir()
    out_b.mkdir()
    functional = pdf_tools.extract_pdf_images(path, out_a)
    facade = PDFTools().extract_pdf_images(path, out_b)
    assert len(functional.pages[0].images) == 1
    assert len(facade.pages[0].images) == 1
    left = functional.pages[0].images[0]
    right = facade.pages[0].images[0]
    assert (left.width, left.height, left.format) == (
        right.width,
        right.height,
        right.format,
    )
    assert left.path.is_file() and right.path.is_file()
    cases = [
        (
            lambda: pdf_tools.extract_pdf_text(tmp_path / "missing.pdf"),
            lambda: PDFTools().extract_pdf_text(tmp_path / "missing.pdf"),
        ),
        (
            lambda: pdf_tools.extract_pdf_text(path, pages=[2]),
            lambda: PDFTools().extract_pdf_text(path, pages=[2]),
        ),
        (
            lambda: pdf_tools.extract_pdf_images(path, tmp_path / "missing"),
            lambda: PDFTools().extract_pdf_images(path, tmp_path / "missing"),
        ),
        (
            lambda: pdf_tools.extract_pdf_images(path, out_a),
            lambda: PDFTools().extract_pdf_images(path, out_b),
        ),
        (
            lambda: pdf_tools.extract_pdf_text(path, pages=[0]),
            lambda: PDFTools().extract_pdf_text(path, pages=[0]),
        ),
    ]
    for functional_call, facade_call in cases:
        with pytest.raises((ExtractionError, ValidationError)) as left_error:
            functional_call()
        with pytest.raises((ExtractionError, ValidationError)) as right_error:
            facade_call()
        assert type(left_error.value) is type(right_error.value)
        assert str(left_error.value) == str(right_error.value) or (
            isinstance(left_error.value, ExtractionError)
            and "already exists" in str(left_error.value)
            and "already exists" in str(right_error.value)
        )
