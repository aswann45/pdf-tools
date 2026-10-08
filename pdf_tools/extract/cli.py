"""Typer commands for text, embedded images, and full extraction."""

from pathlib import Path
from typing import Annotated

import typer

from pdf_tools.cli import AsyncTyper
from pdf_tools.extract.exceptions import ExtractionError
from pdf_tools.extract.service import extract_pdf
from pdf_tools.models.extraction import ExtractionOptions, OcrMode

cli = AsyncTyper(no_args_is_help=True)


def parse_pages(spec: str) -> list[int]:
    """Parse one-based comma-separated pages and inclusive ranges."""
    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            raise ValueError("Empty page selection component")
        bounds = part.split("-")
        if len(bounds) == 1 and bounds[0].isdigit():
            first = last = int(bounds[0])
        elif len(bounds) == 2 and all(value.isdigit() for value in bounds):
            first, last = map(int, bounds)
        else:
            raise ValueError(f"Invalid page selection: {part}")
        if first < 1 or last < first:
            raise ValueError(f"Invalid page range: {part}")
        pages.update(range(first, last + 1))
    return sorted(pages)


def _pages(spec: str | None) -> list[int] | None:
    if spec is None:
        return None
    try:
        return parse_pages(spec)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error


def _fail(error: Exception) -> None:
    typer.echo(f"Error: {error}", err=True)
    raise typer.Exit(1) from error


def _output(path: Path, content: str, overwrite: bool) -> None:
    if not path.parent.is_dir():
        raise ExtractionError(
            f"Output directory does not exist: {path.parent}"
        )
    if path.exists() and not overwrite:
        raise ExtractionError(f"Output already exists: {path}")
    path.write_text(content, encoding="utf-8")


@cli.command("text")
def text_command(
    source: Annotated[Path, typer.Argument(help="Source PDF")],
    output_path: Annotated[
        Path | None, typer.Option("--output-path", "-o")
    ] = None,
    ocr: Annotated[
        OcrMode, typer.Option(help="OCR routing policy")
    ] = OcrMode.NEVER,
    pages: Annotated[
        str | None, typer.Option(help="One-based pages and ranges")
    ] = None,
) -> None:
    """Extract plain text with form-feed page boundaries."""
    selected = _pages(pages)
    try:
        result = extract_pdf(
            source, ExtractionOptions(ocr=ocr, pages=selected)
        )
        if output_path is None:
            typer.echo(result.text, nl=False)
        else:
            _output(output_path, result.text, False)
    except (ExtractionError, OSError, ValueError) as error:
        _fail(error)


@cli.command("images")
def images_command(
    source: Annotated[Path, typer.Argument(help="Source PDF")],
    output_dir: Annotated[Path, typer.Option(help="Existing image directory")],
    pages: Annotated[
        str | None, typer.Option(help="One-based pages and ranges")
    ] = None,
    overwrite: Annotated[
        bool, typer.Option(help="Replace existing images")
    ] = False,
) -> None:
    """Save embedded PDF images."""
    selected = _pages(pages)
    try:
        result = extract_pdf(
            source,
            ExtractionOptions(
                extract_text=False, extract_images=True, pages=selected
            ),
            image_output_dir=output_dir,
            overwrite=overwrite,
        )
        total = sum(len(page.images) for page in result.pages)
        typer.echo(
            f"Extracted {total} images from {len(result.pages)} "
            f"pages to {output_dir}"
        )
    except (ExtractionError, OSError, ValueError) as error:
        _fail(error)


@cli.command("document")
def document_command(
    source: Annotated[Path, typer.Argument(help="Source PDF")],
    output_dir: Annotated[
        Path, typer.Option(help="Existing output directory")
    ],
    ocr: Annotated[
        OcrMode, typer.Option(help="OCR routing policy")
    ] = OcrMode.NEVER,
    pages: Annotated[
        str | None, typer.Option(help="One-based pages and ranges")
    ] = None,
    text: Annotated[bool, typer.Option("--text/--no-text")] = True,
    images: Annotated[bool, typer.Option("--images/--no-images")] = True,
    overwrite: Annotated[
        bool, typer.Option(help="Replace existing outputs")
    ] = False,
) -> None:
    """Save structured JSON, plain text, and embedded images."""
    selected = _pages(pages)
    try:
        if not output_dir.is_dir():
            raise ExtractionError(
                f"Output directory does not exist: {output_dir}"
            )
        if not (text or images):
            raise ExtractionError("Enable text or images")
        targets = [output_dir / "extraction.json"]
        if text:
            targets.append(output_dir / "text.txt")
        if any(target.exists() for target in targets) and not overwrite:
            raise ExtractionError("Document output already exists")
        image_dir = output_dir / "images"
        if images and image_dir.exists() and not image_dir.is_dir():
            raise ExtractionError(
                f"Image path is not a directory: {image_dir}"
            )
        if images and not image_dir.exists():
            image_dir.mkdir()
        result = extract_pdf(
            source,
            ExtractionOptions(
                extract_text=text,
                extract_images=images,
                ocr=ocr,
                pages=selected,
            ),
            image_output_dir=image_dir if images else None,
            overwrite=overwrite,
        )
        _output(
            output_dir / "extraction.json",
            result.model_dump_json(indent=2),
            overwrite,
        )
        if text:
            _output(output_dir / "text.txt", result.text, overwrite)
        typer.echo(f"Extracted {len(result.pages)} pages to {output_dir}")
    except (ExtractionError, OSError, ValueError) as error:
        _fail(error)
