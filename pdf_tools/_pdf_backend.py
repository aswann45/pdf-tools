"""Private PDF operations and version-specific compatibility fallbacks."""

from __future__ import annotations

import importlib.util
import json
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from pdf_oxide import Pdf, PdfDocument
from PIL import Image
from pypdf import PdfWriter


def create_pdf_from_image(source: Path, destination: Path) -> None:
    """Create a PDF from a validated image, normalizing unsupported formats.

    Parameters
    ----------
    source : Path
        Image to convert.
    destination : Path
        PDF output path.
    """
    with Image.open(source) as image:
        if image.format in {"JPEG", "PNG"} and image.mode == "RGB":
            Pdf.from_image(str(source)).save(str(destination))
            return

        with TemporaryDirectory() as directory:
            normalized = Path(directory) / "image.png"
            image.convert("RGB").save(normalized, format="PNG")
            Pdf.from_image(str(normalized)).save(str(destination))


def merge_pdf_files(
    sources: Sequence[Path],
    destination: Path,
    bookmark_names: Sequence[str] | None = None,
) -> None:
    """Merge PDFs and add requested bookmarks with the outline writer.

    PDF Oxide 0.3.78's Python binding has no outline-writing method.
    Remove the pypdf branch when it gains one.
    """
    if not sources:
        writer = PdfWriter()
        try:
            writer.write(str(destination))
        finally:
            writer.close()
        return

    if bookmark_names is None:
        Pdf.merge([str(source) for source in sources]).save(str(destination))
        return

    with TemporaryDirectory() as directory:
        merged = Path(directory) / "merged.pdf"
        Pdf.merge([str(source) for source in sources]).save(str(merged))
        writer = PdfWriter(clone_from=str(merged))
        try:
            first_page = 0
            for source, name in zip(sources, bookmark_names, strict=True):
                writer.add_outline_item(name, first_page)
                first_page += get_pdf_page_count(source)
            with destination.open("wb") as output:
                writer.write(output)
        finally:
            writer.close()


def get_pdf_page_count(source: Path) -> int:
    """Return the number of PDF pages using PDF Oxide."""
    return PdfDocument(str(source)).page_count()


# PDF Oxide 0.3.78 exposes classification as JSON and image bytes as PNG;
# its Python binding does not expose extract_images_to_files or a close method.


@dataclass(frozen=True)
class BackendImage:
    """Library-independent embedded image payload."""

    width: int
    height: int
    format: str
    data: bytes


class BackendOcrUnavailable(RuntimeError):
    """OCR prerequisites cannot be loaded."""


class PdfExtractionBackend:
    """Reuse one PDF Oxide document for page-oriented extraction."""

    def __init__(self, source: Path) -> None:
        """Open a PDF at ``source``."""
        self.document = PdfDocument(str(source))
        self._cached_ocr_engine: object | None = None
        # PDF Oxide 0.3.78 may otherwise return empty text for an
        # unauthenticated encrypted document instead of raising.
        if not self.document.authenticate(""):
            raise ValueError("Password-protected PDF requires a password")

    def __enter__(self) -> PdfExtractionBackend:
        """Enter the PDF document context."""
        self.document.__enter__()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Release the PDF document context."""
        self.document.__exit__(exc_type, exc, tb)

    @property
    def page_count(self) -> int:
        """Return total pages."""
        return self.document.page_count()

    def extract_text(self, page_index: int) -> str:
        """Extract native text at a zero-based page index."""
        return self.document.extract_text(page_index)

    def page_kind(self, page_index: int) -> str:
        """Return PDF Oxide's explicit page classification."""
        return str(json.loads(self.document.classify_page(page_index))["kind"])

    def extract_text_auto(self, page_index: int) -> str:
        """Use PDF Oxide's automatic text/OCR routing."""
        return self.document.extract_text_auto(page_index)

    def _ocr_engine(self) -> object:
        """Load the optional ONNX runtime and user-provisioned OCR models."""
        from pdf_oxide import OcrEngine

        if self._cached_ocr_engine is not None:
            return self._cached_ocr_engine
        if importlib.util.find_spec("onnxruntime") is None:
            raise BackendOcrUnavailable("Install pdf-toolchest[ocr] for OCR")
        directory = Path(
            os.environ.get(
                "PDF_OXIDE_MODEL_DIR", Path.home() / ".cache/pdf_oxide/models"
            )
        )
        detection = directory / "det.onnx"
        recognition = directory / "rec.onnx"
        dictionary = directory / "en_dict.txt"
        if not all(
            path.is_file() for path in (detection, recognition, dictionary)
        ):
            raise BackendOcrUnavailable(
                f"OCR models missing in {directory}; set PDF_OXIDE_MODEL_DIR"
            )
        try:
            self._cached_ocr_engine = OcrEngine(
                str(detection), str(recognition), str(dictionary)
            )
            return self._cached_ocr_engine
        except (OSError, RuntimeError, ValueError) as error:
            raise BackendOcrUnavailable(str(error)) from error

    def extract_text_ocr(self, page_index: int) -> str:
        """Run explicit OCR, without native-text fallback."""
        engine = self._ocr_engine()
        try:
            return self.document.extract_text_ocr(page_index, engine)
        except (OSError, RuntimeError, ValueError) as error:
            raise BackendOcrUnavailable(str(error)) from error

    def extract_images(self, page_index: int) -> list[BackendImage]:
        """Return embedded images, decoded losslessly by PDF Oxide 0.3.x."""
        return [
            BackendImage(
                int(item["width"]),
                int(item["height"]),
                str(item["format"]),
                item["data"],
            )
            for item in self.document.extract_image_bytes(page_index)
        ]

    def check_ocr_available(self) -> None:
        """Check whether OCR runtime and model files can initialize."""
        self._ocr_engine()
