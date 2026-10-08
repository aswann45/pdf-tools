"""Private PDF operations and version-specific compatibility fallbacks."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from pdf_oxide import OfficeConverter, Pdf, PdfDocument
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


def convert_docx_to_pdf(source: Path, destination: Path) -> None:
    """Convert a DOCX using PDF Oxide's Python binding."""
    OfficeConverter.from_docx(str(source)).save(str(destination))


def convert_word_with_libreoffice(source: Path, destination: Path) -> None:
    """Convert Word input through an isolated headless LibreOffice process.

    PDF Oxide 0.3.78 blocks indefinitely on valid DOCX fixtures. This
    compatibility path keeps Word conversion usable until that is fixed.
    """
    command = shutil.which("soffice") or shutil.which("libreoffice")
    if command is None:
        raise RuntimeError("LibreOffice is required for Word conversion.")

    with TemporaryDirectory() as directory:
        temporary = Path(directory)
        profile = (temporary / "profile").as_uri()
        output_dir = temporary / "output"
        output_dir.mkdir()
        try:
            result = subprocess.run(
                [
                    command,
                    f"-env:UserInstallation={profile}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(output_dir),
                    str(source),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                f"LibreOffice failed to convert '{source}' → "
                f"'{destination}': {exc}."
            ) from exc
        generated = output_dir / f"{source.stem}.pdf"
        if not generated.is_file():
            raise RuntimeError(
                f"LibreOffice did not create '{generated}'. "
                f"Output: {result.stdout.decode(errors='replace')} "
                f"{result.stderr.decode(errors='replace')}"
            )
        shutil.move(str(generated), str(destination))


def merge_pdf_files(
    sources: Sequence[Path],
    destination: Path,
    bookmark_names: Sequence[str] | None = None,
) -> None:
    """Merge PDFs, retaining the outline writer for requested bookmarks.

    PDF Oxide 0.3.78's Python binding has no outline-writing method.
    Remove the compatibility branch when it gains one.
    """
    if sources and bookmark_names is None:
        Pdf.merge([str(source) for source in sources]).save(str(destination))
        return

    writer = PdfWriter()
    try:
        if bookmark_names is None:
            writer.write(str(destination))
            return
        for source, name in zip(sources, bookmark_names, strict=True):
            writer.append(str(source), outline_item=name)
        with destination.open("wb") as output:
            writer.write(output)
    finally:
        writer.close()


def get_pdf_page_count(source: Path) -> int:
    """Return the number of PDF pages using PDF Oxide."""
    return PdfDocument(str(source)).page_count()
