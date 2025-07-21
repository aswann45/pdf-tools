"""
Typer sub‑commands that turn common document types into PDFs.

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

from typer import Argument

from pdf_tools.cli import AsyncTyper
from pdf_tools.convert.service import convert_file_to_pdf
from pdf_tools.models.files import File, Files

cli = AsyncTyper(no_args_is_help=True)


@cli.command()
def file_to_pdf(
    path: Annotated[
        str, Argument(help="Path to the input file (Word doc, image, etc.).")
    ],
) -> File:
    """Convert *one* document to PDF.

    Examples
    --------
    ```bash
    pdf-tools convert file-to-pdf report.docx
    ```
    """
    file = File.model_validate({"path": path})
    return convert_file_to_pdf(file)


@cli.command()
def files_to_pdf(
    file_paths: Annotated[
        Optional[list[Path]],
        Argument(
            help="One or more input paths. Ignored when --json-file is used."
        ),
    ] = None,
    json_file: Annotated[
        Optional[Path],
        Argument(
            help="Path to a JSON file containing a serialised Files list."
        ),
    ] = None,
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
    files: Sequence[File]
    if json_file is not None:
        with open(json_file) as f:
            files = Files.model_validate_json(f.read()).root
    elif file_paths is None:
        raise ValueError("Either file_paths or json_file must be provided")
    else:
        files = [File.model_validate({"path": p}) for p in file_paths]
    return [convert_file_to_pdf(file) for file in files]


@cli.command()
def folder_to_pdfs(
    input_dir_path: Annotated[
        Path,
        Argument(help="Directory whose immediate children will be converted."),
    ],
) -> list[File]:
    """Convert every supported file in *path_str*.

    The scan is **non‑recursive**; it only checks the folder’s first level.
    """
    folder = Path(input_dir_path)
    files = [
        File.model_validate({"path": str(file)}) for file in folder.iterdir()
    ]
    return [convert_file_to_pdf(file) for file in files]
