"""Synchronous page-oriented PDF extraction."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from pdf_tools._pdf_backend import BackendOcrUnavailable, PdfExtractionBackend
from pdf_tools.extract.exceptions import ExtractionError, OcrUnavailableError
from pdf_tools.models.extraction import (
    DocumentExtraction,
    ExtractedImage,
    ExtractionOptions,
    OcrMode,
    PageExtraction,
    TextSource,
)
from pdf_tools.models.files import FileInput, coerce_file


def image_filename(page_number: int, index: int, format: str) -> str:
    """Return a stable one-based image filename."""
    extension = "jpg" if format.lower() in {"jpg", "jpeg"} else format.lower()
    return f"page-{page_number:04d}-image-{index:03d}.{extension}"


def _extract_page_text(
    backend: PdfExtractionBackend,
    index: int,
    opts: ExtractionOptions,
) -> tuple[str, TextSource, list[str]]:
    """Extract one page and retain a single authoritative provenance."""
    if not opts.extract_text:
        return "", TextSource.NONE, []
    if opts.ocr == OcrMode.ALWAYS:
        try:
            text = backend.extract_text_ocr(index)
        except BackendOcrUnavailable as error:
            raise OcrUnavailableError(str(error)) from error
        source = TextSource.OCR if text.strip() else TextSource.NONE
        return text, source, []
    if opts.ocr == OcrMode.AUTO:
        kind = backend.page_kind(index)
        if kind in {"scanned", "image_only", "needs_ocr"}:
            try:
                backend.check_ocr_available()
                text = backend.extract_text_auto(index)
                return (
                    text,
                    TextSource.OCR if text.strip() else TextSource.NONE,
                    [],
                )
            except BackendOcrUnavailable:
                text = backend.extract_text(index)
                source = TextSource.NATIVE if text.strip() else TextSource.NONE
                return text, source, ["OCR unavailable; used native text only"]
        if kind in {"text_layer", "empty"}:
            text = backend.extract_text_auto(index)
            return (
                text,
                TextSource.NATIVE if text.strip() else TextSource.NONE,
                [],
            )
        # PDF Oxide 0.3.x may classify a page as hybrid. Its auto API
        # returns only text, so choose one source before returning it.
        text = backend.extract_text(index)
        if text.strip():
            return text, TextSource.NATIVE, []
        try:
            text = backend.extract_text_ocr(index)
            return (
                text,
                TextSource.OCR if text.strip() else TextSource.NONE,
                [],
            )
        except BackendOcrUnavailable:
            return (
                "",
                TextSource.NONE,
                ["OCR unavailable; used native text only"],
            )
    text = backend.extract_text(index)
    return text, TextSource.NATIVE if text.strip() else TextSource.NONE, []


def _extract_images(
    backend: PdfExtractionBackend,
    index: int,
    number: int,
    output: Path | None,
    overwrite: bool,
) -> tuple[list[ExtractedImage], list[tuple[Path, bytes]]]:
    """Collect image outputs and preflight their destination paths."""
    images: list[ExtractedImage] = []
    pending: list[tuple[Path, bytes]] = []
    if output is None:
        return images, pending
    for image_index, image in enumerate(backend.extract_images(index), 1):
        target = output / image_filename(number, image_index, image.format)
        if target.exists() and not overwrite:
            raise ExtractionError(f"Image output already exists: {target}")
        images.append(
            ExtractedImage(
                page_number=number,
                index=image_index,
                path=target,
                width=image.width,
                height=image.height,
                format=image.format,
            )
        )
        pending.append((target, image.data))
    return images, pending


def _validate_image_output(
    directory: str | Path | None,
    enabled: bool,
) -> Path | None:
    """Require an existing output directory when images are requested."""
    if not enabled:
        return None
    if directory is None:
        raise ExtractionError("image_output_dir is required for images")
    output = Path(directory)
    if not output.is_dir():
        raise ExtractionError(
            f"Image output directory does not exist: {output}"
        )
    return output


def extract_pdf(
    source: FileInput,
    options: ExtractionOptions | None = None,
    *,
    image_output_dir: str | Path | None = None,
    overwrite: bool = False,
) -> DocumentExtraction:
    """Extract selected pages from one PDF into a structured result.

    Parameters
    ----------
    source : FileInput
        PDF file to read.
    options : ExtractionOptions | None
        Components, OCR mode, and selected one-based pages.
    image_output_dir : str | Path | None
        Existing directory for embedded images when requested.
    overwrite : bool
        Allow replacement of existing image paths.

    Returns
    -------
    DocumentExtraction
        Page-level text and image metadata.
    """
    file = coerce_file(source)
    opts = options or ExtractionOptions()
    path = file.absolute_path
    if file.type.lower() != "pdf":
        raise ExtractionError(f"Source is not a PDF: {path}")
    if not path.is_file():
        raise ExtractionError(f"PDF file does not exist: {path}")
    output = _validate_image_output(image_output_dir, opts.extract_images)
    try:
        with PdfExtractionBackend(path) as backend:
            count = backend.page_count
            selected = (
                opts.pages
                if opts.pages is not None
                else list(range(1, count + 1))
            )
            if selected and selected[-1] > count:
                raise ExtractionError(
                    f"Page {selected[-1]} exceeds PDF page count {count}"
                )
            pages: list[PageExtraction] = []
            pending: list[tuple[Path, bytes]] = []
            for number in selected:
                index = number - 1
                text, source_kind, warnings = _extract_page_text(
                    backend, index, opts
                )
                images, new_pending = _extract_images(
                    backend,
                    index,
                    number,
                    output if opts.extract_images else None,
                    overwrite,
                )
                pending.extend(new_pending)
                pages.append(
                    PageExtraction(
                        page_number=number,
                        text=text,
                        text_source=source_kind,
                        images=images,
                        warnings=warnings,
                    )
                )
            for target, data in pending:
                target.write_bytes(data)
            return DocumentExtraction(
                source=file, page_count=count, pages=pages
            )
    except (OcrUnavailableError, ExtractionError):
        raise
    except (OSError, RuntimeError, ValueError, ValidationError) as error:
        raise ExtractionError(
            f"Could not extract PDF {path}: {error}"
        ) from error


def extract_pdf_text(
    source: FileInput,
    *,
    ocr: OcrMode = OcrMode.NEVER,
    pages: Sequence[int] | None = None,
) -> DocumentExtraction:
    """Extract only text using the main extraction pipeline."""
    return extract_pdf(
        source,
        ExtractionOptions(
            ocr=ocr, pages=list(pages) if pages is not None else None
        ),
    )


def extract_pdf_images(
    source: FileInput,
    output_dir: str | Path,
    *,
    pages: Sequence[int] | None = None,
    overwrite: bool = False,
) -> DocumentExtraction:
    """Extract only embedded images using the main extraction pipeline."""
    return extract_pdf(
        source,
        ExtractionOptions(
            extract_text=False,
            extract_images=True,
            pages=list(pages) if pages is not None else None,
        ),
        image_output_dir=output_dir,
        overwrite=overwrite,
    )
