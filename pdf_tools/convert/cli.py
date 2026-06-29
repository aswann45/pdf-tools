"""
Typer sub-commands that turn common document types into PDFs.

Commands
--------
* ``file-to-pdf``     – convert a **single** file.
* ``files-to-pdfs``   – convert an explicit list *or* JSON bundle of paths.
* ``folder-to-pdfs``  – convert **every** supported file in a directory.

Each command wraps :func:`pdf_tools.convert.service.convert_file_to_pdf`,
ensuring that business logic stays in the service layer while the CLI focuses
on parameter parsing, user feedback, and error handling.
"""

from collections.abc import Sequence
from contextlib import nullcontext
from pathlib import Path
from typing import Annotated

import typer

from pdf_tools.cli import AsyncTyper
from pdf_tools.convert.service import (
    convert_file_to_pdf,
    convert_files_to_pdfs,
)
from pdf_tools.convert.unoserver_ctx import unoserver_listener
from pdf_tools.models.files import ConversionBatchResult, File, Files

cli = AsyncTyper(no_args_is_help=True)


def _requires_office(files: Sequence[File]) -> bool:
    return any(file.type.lower() in {"doc", "docx"} for file in files)


def _echo_batch_result(result: ConversionBatchResult) -> None:
    for skipped in result.skipped:
        typer.secho(
            f"Skipping {skipped.path}: {skipped.reason}",
            fg="yellow",
        )

    typer.secho(
        f"Converted {len(result.converted)} file(s); "
        f"{len(result.skipped)} skipped.",
        fg="green",
    )


@cli.command()
def file_to_pdf(
    path: Annotated[
        Path,
        typer.Argument(help="Path to the input file (Word doc, image, etc.)."),
    ],
    overwrite_existing: Annotated[
        bool,
        typer.Option(help="Overwrite output file if it already exists."),
    ] = False,
) -> File:
    """Convert one document to PDF and output to the same directory."""
    context = (
        unoserver_listener(uno_port=2002)
        if path.suffix.lower() in {".doc", ".docx"}
        else nullcontext()
    )
    with context:
        try:
            return convert_file_to_pdf(path, overwrite=overwrite_existing)
        except ValueError as ex:
            raise typer.BadParameter(str(ex)) from ex


@cli.command()
def files_to_pdfs(
    file_paths: Annotated[
        list[Path] | None,
        typer.Argument(help="Files to convert."),
    ] = None,
    json_file: Annotated[
        Path | None,
        typer.Option(
            help="Path to a JSON file containing a serialised Files list."
        ),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option(
            "--output-dir",
            "-o",
            help=(
                "Directory where the PDFs will be written. "
                "Defaults to current working directory."
            ),
        ),
    ] = None,
    overwrite_existing: Annotated[
        bool,
        typer.Option(help="Overwrite output files if they already exist."),
    ] = False,
) -> ConversionBatchResult:
    """Convert many documents to PDFs.

    Use ``--json-file`` when the file list is too long for the shell.
    """
    if (file_paths is None) == (json_file is None):
        raise typer.BadParameter(
            "Provide either file_paths or --json-file, not both."
        )
    if output_dir is None:
        output_dir = Path().cwd()
    files: Sequence[File]
    if json_file is not None:
        with open(json_file) as f:
            files = Files.model_validate_json(f.read()).root
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
        result = convert_files_to_pdfs(
            files,
            output_dir=output_dir,
            overwrite=overwrite_existing,
        )

    _echo_batch_result(result)
    if not result.converted:
        raise typer.Exit(code=1)
    return result


@cli.command()
def folder_to_pdfs(
    input_dir: Annotated[
        Path,
        typer.Argument(
            help="Directory whose immediate children will be converted."
        ),
    ],
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory where the PDFs will be written.",
        ),
    ],
    overwrite_existing: Annotated[
        bool,
        typer.Option(help="Overwrite output files if they already exist."),
    ] = False,
) -> ConversionBatchResult:
    """Convert every supported file in *input_dir*.

    The scan is non-recursive; it only checks the folder's first level.
    """
    folder = Path(input_dir)
    files = [File.model_validate({"path": file}) for file in folder.iterdir()]
    context = (
        unoserver_listener(uno_port=2002)
        if _requires_office(files)
        else nullcontext()
    )
    with context:
        result = convert_files_to_pdfs(
            files,
            output_dir=output_dir,
            overwrite=overwrite_existing,
        )

    _echo_batch_result(result)
    if not result.converted:
        raise typer.Exit(code=1)
    return result
