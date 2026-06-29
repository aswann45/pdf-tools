"""
Typer-powered command-line interface for PDF *merge* operations.

This module registers two subcommands under the *merge* namespace:

* ``pdf-files`` – merge arbitrary PDF paths (or a JSON bundle) into one file.
* ``pdfs-in-folder`` – merge every PDF inside a single directory.

Each command is deliberately lightweight; it validates inputs and then
delegates all heavy lifting to :func:`pdf_tools.merge.service.merge_pdfs`.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from pdf_tools.cli import AsyncTyper
from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File, Files

cli = AsyncTyper(no_args_is_help=True)


@cli.command()
def pdf_files(
    file_paths: Annotated[
        list[Path] | None,
        typer.Argument(
            help="Paths to input PDF files (ignored if --json-file is given)."
        ),
    ] = None,
    json_file: Annotated[
        Path | None,
        typer.Option(
            help="Path to a JSON file containing a serialised Files list.",
            exists=False,
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
    """Merge explicit PDF paths or a JSON bundle."""
    if (file_paths is None) == (json_file is None):
        raise typer.BadParameter(
            "Provide either file_paths or --json-file, not both."
        )
    if output_path is None:
        output_path = Path().cwd() / "output.pdf"

    files: Sequence[File]
    if json_file is not None:
        try:
            json_text = json_file.read_text("utf-8")
        except FileNotFoundError as ex:
            raise typer.BadParameter(
                f"JSON file not found: {json_file}"
            ) from ex
        except OSError as ox:
            raise typer.BadParameter(f"Cannot read JSON file: {ox}") from ox

        try:
            files = Files.model_validate_json(json_text).root
        except (ValidationError, ValueError) as ex:
            raise typer.BadParameter(
                f"JSON in {json_file} is not a valid `Files` payload:\n{ex}"
            ) from ex
    elif file_paths is None:
        raise ValueError("Either file_paths or json_file must be provided")
    else:
        files = [File.model_validate({"path": p}) for p in file_paths]
    merge_pdfs(files, output_path, set_bookmarks, overwrite=overwrite_existing)
    typer.echo(f"Merged PDFs to {output_path.resolve()}")


@cli.command()
def pdfs_in_folder(
    input_dir_path: Annotated[
        Path, typer.Argument(help="Directory containing PDF files.")
    ],
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
    """Merge all PDFs found in *input_dir_path*."""
    if output_path is None:
        output_path = Path().cwd() / "output.pdf"
    files = [
        File.model_validate({"path": str(f)}) for f in input_dir_path.iterdir()
    ]
    merge_pdfs(files, output_path, set_bookmarks, overwrite=overwrite_existing)
    typer.echo(f"Merged PDFs to {output_path.resolve()}")
