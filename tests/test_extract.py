"""Extraction API and CLI coverage."""

import json
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from PIL import Image
from reportlab.pdfgen import canvas
from typer.testing import CliRunner

from pdf_tools import ExtractionOptions, OcrMode, TextSource, extract_pdf
from pdf_tools._pdf_backend import BackendOcrUnavailable, PdfExtractionBackend
from pdf_tools.extract.cli import parse_pages
from pdf_tools.extract.exceptions import ExtractionError, OcrUnavailableError
from pdf_tools.extract.service import image_filename
from pdf_tools.main import app


def make_pdf(path: Path, labels: list[str]) -> None:
    """Create a small PDF with distinct pages."""
    pdf = canvas.Canvas(str(path))
    for label in labels:
        if label:
            pdf.drawString(72, 700, label)
        pdf.showPage()
    pdf.save()


def test_native_pages_and_json(tmp_path: Path) -> None:
    """Text stays page-oriented and preserves empty pages."""
    path = tmp_path / "input.pdf"
    make_pdf(path, ["First", "", "Third"])
    result = extract_pdf(path, ExtractionOptions(pages=[3, 1, 3, 2]))
    assert result.page_count == 3
    assert [p.page_number for p in result.pages] == [1, 2, 3]
    assert [p.text_source for p in result.pages] == [
        TextSource.NATIVE,
        TextSource.NONE,
        TextSource.NATIVE,
    ]
    assert result.text == "First\f\fThird"
    data = json.loads(result.model_dump_json())
    assert data["pages"][0]["text_source"] == "native"
    assert data["source"]["path"] == str(path)


def test_invalid_source_and_page(tmp_path: Path) -> None:
    """Usage errors receive domain exceptions."""
    with pytest.raises(ExtractionError, match="does not exist"):
        extract_pdf(tmp_path / "missing.pdf")
    with pytest.raises(ExtractionError, match="not a PDF"):
        extract_pdf(tmp_path / "note.txt")
    path = tmp_path / "input.pdf"
    make_pdf(path, ["One"])
    with pytest.raises(ExtractionError, match="exceeds"):
        extract_pdf(path, ExtractionOptions(pages=[2]))
    with pytest.raises(ValueError):
        ExtractionOptions(pages=[0])


def test_auto_and_always_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OCR provenance and unavailable policy are explicit."""
    path = tmp_path / "input.pdf"
    make_pdf(path, ["Native"])
    monkeypatch.setattr(
        PdfExtractionBackend, "page_kind", lambda self, index: "scanned"
    )
    monkeypatch.setattr(
        PdfExtractionBackend, "check_ocr_available", lambda self: None
    )
    monkeypatch.setattr(
        PdfExtractionBackend,
        "extract_text_auto",
        lambda self, index: "OCR text",
    )
    result = extract_pdf(path, ExtractionOptions(ocr=OcrMode.AUTO))
    assert result.pages[0].text_source == TextSource.OCR
    assert result.pages[0].text == "OCR text"
    monkeypatch.setattr(
        PdfExtractionBackend,
        "extract_text_ocr",
        lambda self, index: "Only OCR",
    )
    assert (
        extract_pdf(path, ExtractionOptions(ocr=OcrMode.ALWAYS)).pages[0].text
        == "Only OCR"
    )

    def unavailable(self: object) -> None:
        raise BackendOcrUnavailable("models missing")

    monkeypatch.setattr(
        PdfExtractionBackend, "check_ocr_available", unavailable
    )
    auto = extract_pdf(path, ExtractionOptions(ocr=OcrMode.AUTO))
    assert auto.pages[0].text_source == TextSource.NATIVE
    assert auto.pages[0].warnings
    monkeypatch.setattr(
        PdfExtractionBackend,
        "extract_text_ocr",
        lambda self, index: unavailable(self),
    )
    with pytest.raises(OcrUnavailableError, match="models missing"):
        extract_pdf(path, ExtractionOptions(ocr=OcrMode.ALWAYS))


def test_images_and_existing_file(tmp_path: Path) -> None:
    """Embedded image metadata and overwrite checks use stable paths."""
    image = tmp_path / "image.jpg"
    Image.new("RGB", (30, 20), "red").save(image)
    path = tmp_path / "input.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawImage(str(image), 72, 600)
    pdf.save()
    out = tmp_path / "out"
    out.mkdir()
    opts = ExtractionOptions(extract_text=False, extract_images=True)
    result = extract_pdf(path, opts, image_output_dir=out)
    saved = result.pages[0].images[0]
    assert saved.path.name == "page-0001-image-001.png"
    assert (saved.width, saved.height, saved.format) == (30, 20, "png")
    assert saved.path.read_bytes().startswith(b"\x89PNG")
    with pytest.raises(ExtractionError, match="already exists"):
        extract_pdf(path, opts, image_output_dir=out)
    assert (
        extract_pdf(path, opts, image_output_dir=out, overwrite=True)
        .pages[0]
        .images
    )


@given(st.lists(st.integers(min_value=1, max_value=100), min_size=1))
def test_page_parser_numbers(numbers: list[int]) -> None:
    """Comma lists normalize duplicates and order."""
    assert parse_pages(",".join(map(str, numbers))) == sorted(set(numbers))


@pytest.mark.parametrize("spec", ["0", "-1", "5-2", "abc", "1,,2", "1-", "-4"])
def test_page_parser_invalid(spec: str) -> None:
    """Malformed selection syntax fails."""
    with pytest.raises(ValueError):
        parse_pages(spec)


@given(st.integers(min_value=1), st.integers(min_value=1))
def test_image_filename(page: int, index: int) -> None:
    """Filenames retain one-based numbers."""
    assert (
        image_filename(page, index, "png")
        == f"page-{page:04d}-image-{index:03d}.png"
    )


def test_cli(tmp_path: Path) -> None:
    """CLI help, text output, JSON tree, and errors work end to end."""
    runner = CliRunner()
    for args in (
        ["extract", "--help"],
        ["extract", "text", "--help"],
        ["extract", "images", "--help"],
        ["extract", "document", "--help"],
    ):
        assert runner.invoke(app, args).exit_code == 0
    path = tmp_path / "input.pdf"
    make_pdf(path, ["First", "Second"])
    text = runner.invoke(app, ["extract", "text", str(path), "--pages", "2"])
    assert (
        text.exit_code == 0
        and "Second" in text.stdout
        and "First" not in text.stdout
    )
    assert (
        runner.invoke(
            app, ["extract", "text", str(path), "--pages", "0"]
        ).exit_code
        != 0
    )
    assert (
        runner.invoke(
            app, ["extract", "text", str(tmp_path / "missing.pdf")]
        ).exit_code
        != 0
    )
    out = tmp_path / "out"
    out.mkdir()
    result = runner.invoke(
        app, ["extract", "document", str(path), "--output-dir", str(out)]
    )
    assert result.exit_code == 0, result.output
    assert (out / "text.txt").read_text() == "First\fSecond"
    assert len(json.loads((out / "extraction.json").read_text())["pages"]) == 2
    assert (
        runner.invoke(
            app, ["extract", "document", str(path), "--output-dir", str(out)]
        ).exit_code
        != 0
    )


def test_never_does_not_initialize_ocr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Native-only mode never touches optional OCR machinery."""
    path = tmp_path / "input.pdf"
    make_pdf(path, ["Native"])

    def forbidden(self: object, index: int) -> str:
        raise AssertionError("OCR was called")

    monkeypatch.setattr(PdfExtractionBackend, "extract_text_ocr", forbidden)
    monkeypatch.setattr(PdfExtractionBackend, "extract_text_auto", forbidden)
    assert extract_pdf(path).pages[0].text_source == TextSource.NATIVE


def test_malformed_and_encrypted(tmp_path: Path) -> None:
    """Unreadable and locked PDFs cannot silently yield empty results."""
    from pypdf import PdfWriter

    malformed = tmp_path / "broken.pdf"
    malformed.write_bytes(b"not a PDF")
    with pytest.raises(ExtractionError, match="Could not extract"):
        extract_pdf(malformed)
    encrypted = tmp_path / "locked.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("secret")
    writer.write(str(encrypted))
    writer.close()
    with pytest.raises(ExtractionError, match="Password-protected"):
        extract_pdf(encrypted)


def test_cli_selection_and_switches(tmp_path: Path) -> None:
    """CLI rejects bad OCR choices and honors disabled output components."""
    runner = CliRunner()
    path = tmp_path / "input.pdf"
    make_pdf(path, ["One"])
    assert (
        runner.invoke(
            app, ["extract", "text", str(path), "--ocr", "bad"]
        ).exit_code
        != 0
    )
    out = tmp_path / "out"
    out.mkdir()
    result = runner.invoke(
        app,
        [
            "extract",
            "document",
            str(path),
            "--output-dir",
            str(out),
            "--no-text",
        ],
    )
    assert result.exit_code == 0, result.output
    assert not (out / "text.txt").exists()
    data = json.loads((out / "extraction.json").read_text())
    assert data["pages"][0]["text"] == ""
    assert data["pages"][0]["text_source"] == "none"
    assert (
        runner.invoke(
            app,
            [
                "extract",
                "document",
                str(path),
                "--output-dir",
                str(out),
                "--no-text",
                "--no-images",
                "--overwrite",
            ],
        ).exit_code
        != 0
    )


@pytest.mark.slow
def test_real_ocr_when_provisioned(tmp_path: Path) -> None:
    """Exercise real OCR when its runtime and models are present."""
    import importlib.util
    import os

    if importlib.util.find_spec("onnxruntime") is None:
        pytest.skip("ONNX Runtime is not installed")
    models = Path(
        os.environ.get(
            "PDF_OXIDE_MODEL_DIR", Path.home() / ".cache/pdf_oxide/models"
        )
    )
    if not all(
        (models / name).is_file()
        for name in ("det.onnx", "rec.onnx", "en_dict.txt")
    ):
        pytest.skip("PDF Oxide OCR models are not provisioned")
    image = tmp_path / "scan.png"
    from PIL import ImageDraw, ImageFont

    bitmap = Image.new("RGB", (800, 200), "white")
    font = ImageFont.truetype("DejaVuSans.ttf", 60)
    ImageDraw.Draw(bitmap).text((40, 55), "HELLO OCR", fill="black", font=font)
    bitmap.save(image)
    path = tmp_path / "scan.pdf"
    pdf = canvas.Canvas(str(path), pagesize=(800, 200))
    pdf.drawImage(str(image), 0, 0, width=800, height=200)
    pdf.save()
    result = extract_pdf(path, ExtractionOptions(ocr=OcrMode.ALWAYS))
    assert result.pages[0].text_source == TextSource.OCR
    assert "HELLO" in result.pages[0].text.upper()


@pytest.mark.parametrize(
    ("kind", "returned_text", "expected_source"),
    [
        ("text_layer", "From native", TextSource.NATIVE),
        ("empty", "", TextSource.NONE),
    ],
)
def test_auto_native_classifications(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    returned_text: str,
    expected_source: TextSource,
) -> None:
    """Native and empty pages avoid explicit OCR in auto mode."""
    path = tmp_path / "input.pdf"
    make_pdf(path, ["Native"])
    monkeypatch.setattr(
        PdfExtractionBackend, "page_kind", lambda self, index: kind
    )
    monkeypatch.setattr(
        PdfExtractionBackend,
        "extract_text_auto",
        lambda self, index: returned_text,
    )

    def forbidden(self: object, index: int) -> str:
        raise AssertionError("Explicit OCR was called")

    monkeypatch.setattr(PdfExtractionBackend, "extract_text_ocr", forbidden)
    result = extract_pdf(path, ExtractionOptions(ocr=OcrMode.AUTO))
    assert result.pages[0].text_source == expected_source
    assert result.pages[0].text == returned_text


@pytest.mark.parametrize(
    ("native", "ocr_text", "expected_source", "expected_text"),
    [
        ("Native", "OCR", TextSource.NATIVE, "Native"),
        ("", "OCR", TextSource.OCR, "OCR"),
        ("", "", TextSource.NONE, ""),
    ],
)
def test_auto_hybrid_chooses_one_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    native: str,
    ocr_text: str,
    expected_source: TextSource,
    expected_text: str,
) -> None:
    """Hybrid classification never concatenates native and OCR text."""
    path = tmp_path / "input.pdf"
    make_pdf(path, ["Native"])
    monkeypatch.setattr(
        PdfExtractionBackend, "page_kind", lambda self, index: "hybrid"
    )
    monkeypatch.setattr(
        PdfExtractionBackend, "extract_text", lambda self, index: native
    )
    monkeypatch.setattr(
        PdfExtractionBackend, "extract_text_ocr", lambda self, index: ocr_text
    )
    result = extract_pdf(path, ExtractionOptions(ocr=OcrMode.AUTO))
    assert result.pages[0].text_source == expected_source
    assert result.pages[0].text == expected_text


def test_auto_hybrid_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hybrid pages retain an OCR warning when no text is available."""
    path = tmp_path / "input.pdf"
    make_pdf(path, ["Native"])
    monkeypatch.setattr(
        PdfExtractionBackend, "page_kind", lambda self, index: "hybrid"
    )
    monkeypatch.setattr(
        PdfExtractionBackend, "extract_text", lambda self, index: ""
    )

    def unavailable(self: object, index: int) -> str:
        raise BackendOcrUnavailable("models missing")

    monkeypatch.setattr(PdfExtractionBackend, "extract_text_ocr", unavailable)
    result = extract_pdf(path, ExtractionOptions(ocr=OcrMode.AUTO))
    assert result.pages[0].text_source == TextSource.NONE
    assert result.pages[0].warnings == [
        "OCR unavailable; used native text only"
    ]


def make_image_pdf(path: Path, directory: Path) -> None:
    """Create two pages containing distinct embedded images."""
    first = directory / "red.jpg"
    second = directory / "blue.jpg"
    Image.new("RGB", (30, 20), "red").save(first)
    Image.new("RGB", (40, 25), "blue").save(second)
    pdf = canvas.Canvas(str(path))
    pdf.drawImage(str(first), 72, 600)
    pdf.drawImage(str(second), 150, 600)
    pdf.showPage()
    pdf.drawImage(str(second), 72, 600)
    pdf.save()


def test_multiple_images_and_late_collision(tmp_path: Path) -> None:
    """A later collision prevents any earlier image output."""
    path = tmp_path / "images.pdf"
    make_image_pdf(path, tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    late = out / "page-0002-image-001.png"
    late.write_bytes(b"existing")
    opts = ExtractionOptions(extract_text=False, extract_images=True)
    with pytest.raises(ExtractionError, match="already exists"):
        extract_pdf(path, opts, image_output_dir=out)
    assert list(out.iterdir()) == [late]
    assert late.read_bytes() == b"existing"
    result = extract_pdf(path, opts, image_output_dir=out, overwrite=True)
    assert [len(page.images) for page in result.pages] == [2, 1]
    assert [image.path.name for image in result.pages[0].images] == [
        "page-0001-image-001.png",
        "page-0001-image-002.png",
    ]
    assert result.pages[1].images[0].path == late
    assert late.read_bytes().startswith(b"\x89PNG")


def test_image_output_validation(tmp_path: Path) -> None:
    """Image output needs an existing directory; text ignores that option."""
    path = tmp_path / "input.pdf"
    make_pdf(path, ["Native"])
    opts = ExtractionOptions(extract_text=False, extract_images=True)
    with pytest.raises(ExtractionError, match="image_output_dir"):
        extract_pdf(path, opts)
    with pytest.raises(ExtractionError, match="does not exist"):
        extract_pdf(path, opts, image_output_dir=tmp_path / "missing")
    result = extract_pdf(path, image_output_dir=tmp_path / "missing")
    assert result.pages[0].text == "Native"
    assert not (tmp_path / "missing").exists()


def test_cli_text_file_and_images(tmp_path: Path) -> None:
    """Text and images commands write their requested outputs."""
    runner = CliRunner()
    path = tmp_path / "images.pdf"
    make_image_pdf(path, tmp_path)
    text_file = tmp_path / "text.txt"
    text = runner.invoke(
        app, ["extract", "text", str(path), "-o", str(text_file)]
    )
    assert text.exit_code == 0, text.output
    assert text_file.read_text() == "\f"
    repeated = runner.invoke(
        app, ["extract", "text", str(path), "-o", str(text_file)]
    )
    assert repeated.exit_code != 0
    assert "already exists" in repeated.output
    missing_text = runner.invoke(
        app,
        [
            "extract",
            "text",
            str(path),
            "-o",
            str(tmp_path / "missing" / "x.txt"),
        ],
    )
    assert missing_text.exit_code != 0
    assert "does not exist" in missing_text.output
    missing_images = runner.invoke(
        app,
        [
            "extract",
            "images",
            str(path),
            "--output-dir",
            str(tmp_path / "missing"),
        ],
    )
    assert missing_images.exit_code != 0
    out = tmp_path / "out"
    out.mkdir()
    images = runner.invoke(
        app, ["extract", "images", str(path), "--output-dir", str(out)]
    )
    assert images.exit_code == 0, images.output
    assert "Extracted 3 images from 2 pages" in images.output
    assert len(list(out.glob("*.png"))) == 3
    refused = runner.invoke(
        app, ["extract", "images", str(path), "--output-dir", str(out)]
    )
    assert refused.exit_code != 0
    overwritten = runner.invoke(
        app,
        [
            "extract",
            "images",
            str(path),
            "--output-dir",
            str(out),
            "--overwrite",
        ],
    )
    assert overwritten.exit_code == 0, overwritten.output


def test_public_wrappers_and_model_round_trip(tmp_path: Path) -> None:
    """Convenience APIs use the same page model and JSON schema."""
    from pdf_tools import (
        DocumentExtraction,
        extract_pdf_images,
        extract_pdf_text,
    )

    path = tmp_path / "input.pdf"
    make_image_pdf(path, tmp_path)
    text = extract_pdf_text(path, pages=[2, 1, 2])
    assert [page.page_number for page in text.pages] == [1, 2]
    assert text.text == "\f"
    restored = DocumentExtraction.model_validate_json(text.model_dump_json())
    assert restored.pages == text.pages
    out = tmp_path / "out"
    out.mkdir()
    images = extract_pdf_images(path, out, pages=[2])
    assert [page.page_number for page in images.pages] == [2]
    assert len(images.pages[0].images) == 1
    assert images.pages[0].text_source == TextSource.NONE
    with pytest.raises(ValueError, match="Enable text or images"):
        ExtractionOptions(extract_text=False, extract_images=False)


def test_cli_document_validation_and_no_images(tmp_path: Path) -> None:
    """Document command validates its tree and can omit images."""
    runner = CliRunner()
    path = tmp_path / "input.pdf"
    make_pdf(path, ["Native"])
    missing = runner.invoke(
        app,
        [
            "extract",
            "document",
            str(path),
            "--output-dir",
            str(tmp_path / "missing"),
        ],
    )
    assert missing.exit_code != 0
    assert "does not exist" in missing.output
    out = tmp_path / "out"
    out.mkdir()
    image_path = out / "images"
    image_path.write_text("file")
    blocked = runner.invoke(
        app, ["extract", "document", str(path), "--output-dir", str(out)]
    )
    assert blocked.exit_code != 0
    assert "not a directory" in blocked.output
    successful = runner.invoke(
        app,
        [
            "extract",
            "document",
            str(path),
            "--output-dir",
            str(out),
            "--no-images",
        ],
    )
    assert successful.exit_code == 0, successful.output
    assert (out / "text.txt").read_text() == "Native"
    data = json.loads((out / "extraction.json").read_text())
    assert data["pages"][0]["images"] == []
