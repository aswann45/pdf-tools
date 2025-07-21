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
from pathlib import Path
from typing import Annotated, Optional

from typer import Argument, Option

from pdf_tools.cli import AsyncTyper
from pdf_tools.models.files import File, Files
from pdf_tools.process.service import (
    convert_and_merge_pdfs as _convert_and_merge_pdfs,
)

cli = AsyncTyper(no_args_is_help=True)


@cli.command()
def convert_and_merge_pdfs(
    output_path: Annotated[
        Path, Argument(help="Destination path for the merged PDF.")
    ],
    file_paths: Annotated[
        Optional[list[Path]],
        Argument(
            help="One or more input paths. Ignored when --json-file is used."
        ),
    ] = None,
    json_file: Annotated[
        Optional[str],
        Argument(
            help="Path to a JSON file containing a serialised Files list."
        ),
    ] = None,
    set_bookmarks: Annotated[
        bool,
        Option(help="Create a top-level bookmark for each source document."),
    ] = False,
) -> None:
    """Convert inputs to PDF, then merge them.

    Examples
    --------
    ```bash
    # Direct list of files
    pdf-tools process convert-and-merge-pdfs bundle.pdf report.docx photo.jpg

    # Using a JSON bundle generated elsewhere
    pdf-tools process convert-and-merge-pdfs bundle.pdf --json-file batch.json
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
    _convert_and_merge_pdfs(files, output_path, set_bookmarks)
