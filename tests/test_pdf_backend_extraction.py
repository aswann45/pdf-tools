"""Version-specific PDF Oxide extraction backend behavior."""

from pathlib import Path
from unittest.mock import MagicMock

import pdf_oxide
import pytest
from reportlab.pdfgen import canvas

import pdf_tools._pdf_backend as pdf_backend
from pdf_tools._pdf_backend import BackendOcrUnavailable, PdfExtractionBackend


def make_pdf(path: Path) -> None:
    """Create a minimal native PDF."""
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 700, "Native")
    pdf.save()


def test_backend_native_binding_and_context(tmp_path: Path) -> None:
    """A real PDF Oxide document exposes count, text, and classification."""
    path = tmp_path / "native.pdf"
    make_pdf(path)
    with PdfExtractionBackend(path) as backend:
        assert backend.page_count == 1
        assert backend.extract_text(0) == "Native"
        assert backend.extract_text_auto(0) == "Native"
        assert backend.page_kind(0) == "text_layer"
        assert backend.extract_images(0) == []


def test_ocr_runtime_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Explicit OCR fails before attempting to load model files."""
    path = tmp_path / "native.pdf"
    make_pdf(path)
    monkeypatch.setattr(
        pdf_backend.importlib.util, "find_spec", lambda name: None
    )
    with PdfExtractionBackend(path) as backend:
        with pytest.raises(
            BackendOcrUnavailable, match="pdf-toolchest\\[ocr\\]"
        ):
            backend.check_ocr_available()


def test_ocr_models_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The model directory is required when ONNX Runtime is installed."""
    path = tmp_path / "native.pdf"
    make_pdf(path)
    monkeypatch.setattr(
        pdf_backend.importlib.util, "find_spec", lambda name: object()
    )
    monkeypatch.setenv("PDF_OXIDE_MODEL_DIR", str(tmp_path / "missing"))
    with PdfExtractionBackend(path) as backend:
        with pytest.raises(BackendOcrUnavailable, match="models missing"):
            backend.check_ocr_available()


def test_ocr_engine_initialization_and_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One backend instance initializes one engine for multiple pages."""
    path = tmp_path / "native.pdf"
    make_pdf(path)
    models = tmp_path / "models"
    models.mkdir()
    for name in ("det.onnx", "rec.onnx", "en_dict.txt"):
        (models / name).write_bytes(b"test")
    monkeypatch.setenv("PDF_OXIDE_MODEL_DIR", str(models))
    monkeypatch.setattr(
        pdf_backend.importlib.util, "find_spec", lambda name: object()
    )
    engine = object()
    constructor = MagicMock(return_value=engine)
    monkeypatch.setattr(pdf_oxide, "OcrEngine", constructor)
    with PdfExtractionBackend(path) as backend:
        backend.check_ocr_available()
        backend.check_ocr_available()
    constructor.assert_called_once_with(
        str(models / "det.onnx"),
        str(models / "rec.onnx"),
        str(models / "en_dict.txt"),
    )


def test_ocr_engine_error_preserves_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Model loading errors retain their original cause."""
    path = tmp_path / "native.pdf"
    make_pdf(path)
    models = tmp_path / "models"
    models.mkdir()
    for name in ("det.onnx", "rec.onnx", "en_dict.txt"):
        (models / name).write_bytes(b"test")
    monkeypatch.setenv("PDF_OXIDE_MODEL_DIR", str(models))
    monkeypatch.setattr(
        pdf_backend.importlib.util, "find_spec", lambda name: object()
    )
    monkeypatch.setattr(
        pdf_oxide,
        "OcrEngine",
        MagicMock(side_effect=RuntimeError("bad model")),
    )
    with PdfExtractionBackend(path) as backend:
        with pytest.raises(BackendOcrUnavailable, match="bad model") as error:
            backend.extract_text_ocr(0)
    assert isinstance(error.value.__cause__, RuntimeError)


def test_ocr_execution_error_preserves_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OCR execution errors are translated by the private backend."""
    fake_document = MagicMock()
    fake_document.authenticate.return_value = True
    fake_document.extract_text_ocr.side_effect = RuntimeError("OCR failed")
    monkeypatch.setattr(
        pdf_backend, "PdfDocument", MagicMock(return_value=fake_document)
    )
    backend = PdfExtractionBackend(tmp_path / "unused.pdf")
    engine = object()
    monkeypatch.setattr(backend, "_ocr_engine", lambda: engine)
    with pytest.raises(BackendOcrUnavailable, match="OCR failed") as error:
        backend.extract_text_ocr(0)
    fake_document.extract_text_ocr.assert_called_once_with(0, engine)
    assert isinstance(error.value.__cause__, RuntimeError)
