"""
Typer commands for batch PDF processing.

Typer command that **converts** a batch of files to PDF *and then merges* them
into a single document.

This wrapper around :func:`pdf_tools.process.service.convert_and_merge_pdfs`
provides the simplest possible UX for users who only care about the final PDF.
They can supply paths directly or hand over a JSON bundle produced by other
commands.
"""

from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from pdf_tools.cli import AsyncTyper
from pdf_tools.convert.unoserver_ctx import unoserver_listener
from pdf_tools.models.files import File, Files
from pdf_tools.process.service import (
    convert_and_merge_pdfs as _convert_and_merge_pdfs,
)

cli = AsyncTyper(no_args_is_help=True)


def _requires_office(files: Sequence[File]) -> bool:
    return any(file.type.lower() in {"doc", "docx"} for file in files)


@cli.command()
def convert_and_merge_pdfs(
    file_paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help="One or more input paths. Ignored when --json-file is used."
        ),
    ] = None,
    json_file: Annotated[
        Path | None,
        typer.Option(
            "--json-file",
            "-j",
            help="Path to a JSON file containing a serialised Files list.",
        ),
    ] = None,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output-path",
            "-o",
            help=(
                "Destination path for the merged PDF. "
                "Defaults to 'output.pdf' in current directory."
            ),
        ),
    ] = None,
    set_bookmarks: Annotated[
        bool,
        typer.Option(
            help="Create a top-level bookmark for each source document."
        ),
    ] = False,
    overwrite_existing: Annotated[
        bool,
        typer.Option(help="Overwrite output files if they already exist."),
    ] = False,
) -> None:
    """Convert inputs to PDF, then merge them."""
    if (file_paths is None) == (json_file is None):
        raise typer.BadParameter(
            "Provide *either* input paths *or* --json-file, not both."
        )
    if output_path is None:
        output_path = Path().cwd() / "output.pdf"
    files: Sequence[File]
    if json_file is not None:
        try:
            json_text = json_file.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise typer.BadParameter(
                f"JSON file not found: {json_file}"
            ) from exc
        except OSError as exc:
            raise typer.BadParameter(f"Cannot read JSON file: {exc}") from exc

        try:
            files = Files.model_validate_json(json_text).root
        except (ValidationError, ValueError) as ve:
            raise typer.BadParameter(
                f"JSON in {json_file} is not a valid `Files` payload:\n{ve}"
            ) from ve

    elif file_paths is None:
        raise ValueError("Either file_paths or json_file must be provided")
    else:
        files = [File.model_validate({"path": p}) for p in file_paths]
    context = (
        unoserver_listener(uno_port=2002)
        if _requires_office(files)
        else nullcontext()
    )
    with context:
        _convert_and_merge_pdfs(
            files, output_path, set_bookmarks, overwrite=overwrite_existing
        )
    typer.echo(f"Merged PDFs to {output_path.resolve()}")
