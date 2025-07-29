"""
Typer sub-commands that turn common document types into PDFs.

Commands
--------
* ``file-to-pdf``     – convert a **single** file.
* ``files-to-pdf``    – convert an explicit list *or* JSON bundle of paths.
* ``folder-to-pdfs``  – convert **every** supported file in a directory.

Each command wraps :func:`pdf_tools.convert.service.convert_file_to_pdf`,
ensuring that business logic stays in the service layer while the CLI focuses
on parameter parsing, user feedback, and error handling.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Optional

import typer

from pdf_tools.cli import AsyncTyper
from pdf_tools.convert.service import _output_dir_handler, convert_file_to_pdf
from pdf_tools.convert.unoserver_ctx import unoserver_listener
from pdf_tools.models.files import File, Files

cli = AsyncTyper(no_args_is_help=True)


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
    """Convert *one* document to PDF and output to the same directory.

    Examples
    --------
    ```bash
    pdf-tools convert file-to-pdf report.docx
    ```
    """

    def _file_to_pdf(path: Path, overwrite: bool) -> File:
        file = File.model_validate({"path": path})
        return convert_file_to_pdf(file, overwrite=overwrite)

    if path.suffix in {".doc", ".docx"}:
        with unoserver_listener(port=2002):
            return _file_to_pdf(path, overwrite_existing)
    else:
        return _file_to_pdf(path, overwrite_existing)


@cli.command()
def files_to_pdfs(
    file_paths: Annotated[
        Optional[list[Path]],
        typer.Argument(help="Files to convert."),
    ] = None,
    json_file: Annotated[
        Optional[Path],
        typer.Option(
            help="Path to a JSON file containing a serialised Files list."
        ),
    ] = None,
    output_dir: Annotated[
        Optional[Path],
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
) -> list[File]:
    """Convert many documents to PDFs.

    Use ``--json-file`` when the file list is too long for the shell.

    Examples
    --------
    ```bash
    # Direct list
    pdf-tools convert files-to-pdf report.docx photo.jpg

    # Via JSON generated elsewhere
    pdf-tools convert files-to-pdf --json-file batch.json
    ```
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

    converted: list[File] = []
    failures: list[Path] = []

    with unoserver_listener(port=2002):
        for file in files:
            try:
                output_path = _output_dir_handler(file.path, output_dir)
                converted.append(
                    convert_file_to_pdf(
                        file,
                        output_path=output_path,
                        overwrite=overwrite_existing,
                    )
                )
            except (RuntimeError, ValueError, OSError) as ex:
                failures.append(file.path)
                typer.secho(f"⚠️  Skipping {file.path}: {ex}", fg="yellow")

    if not converted:
        raise typer.Exit(code=1)

    typer.secho(
        f"✅  Converted {len(converted)} file(s); {len(failures)} skipped.",
        fg="green",
    )
    return converted


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
) -> list[File]:
    """Convert every supported file in *input_dir_path*.

    The scan is **non-recursive**; it only checks the folder’s first level.
    """
    folder = Path(input_dir)
    files = [File.model_validate({"path": file}) for file in folder.iterdir()]
    converted: list[File] = []
    failures: list[Path] = []
    with unoserver_listener(port=2002):
        for file in files:
            try:
                output_path = _output_dir_handler(file.path, output_dir)
                converted.append(
                    convert_file_to_pdf(
                        file,
                        output_path=output_path,
                        overwrite=overwrite_existing,
                    )
                )
            except (RuntimeError, ValueError, OSError) as ex:
                failures.append(file.path)
                typer.secho(f"⚠️  Skipping {file.path}: {ex}", fg="yellow")

    if not converted:
        raise typer.Exit(code=1)

    typer.secho(
        f"✅  Converted {len(converted)} file(s); {len(failures)} skipped.",
        fg="green",
    )
    return converted
