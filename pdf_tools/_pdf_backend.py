"""Private PDF operations and version-specific compatibility fallbacks."""

from __future__ import annotations

from collections.abc import Sequence
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
