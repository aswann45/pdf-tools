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
from typing import Annotated, Optional

from typer import Argument, Option

from pdf_tools.cli import AsyncTyper
from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File, Files

cli = AsyncTyper(no_args_is_help=True)


@cli.command()
def pdf_files(
    output_path: Annotated[
        Path, Argument(help="Destination path for the merged PDF.")
    ],
    file_paths: Annotated[
        Optional[list[Path]],
        Argument(
            help="Paths to input PDF files (ignored if --json-file is given)."
        ),
    ] = None,
    json_file: Annotated[
        Optional[Path],
        Argument(
            help="Path to a JSON file containing a serialised Files list."
        ),
    ] = None,
    set_bookmarks: Annotated[
        bool,
        Option(help="Create a top‑level bookmark for each source document."),
    ] = False,
) -> None:
    """Merge explicit PDF paths *or* a JSON bundle.

    The command supports two mutually‑exclusive input modes and
    passes every entry to :func:`pdf_tools.merge.service.merge_pdfs`:

    1. **Path list** – supply one or more *file_path* directly on the command
       line: ``pdf-tools merge pdf-files a.pdf b.pdf out.pdf``.
    2. **JSON bundle** – provide ``--json-file`` that contains a serialised
       :class:`pdf_tools.models.files.Files` object (as produced by other
       commands).  This is handy for very long file lists or scripted flows.
    """
    files: Sequence[File]
    if json_file is not None:
        with open(json_file) as f:
            files = Files.model_validate_json(f.read()).root
    elif file_paths is None:
        raise ValueError("Either file_paths or json_file must be provided")
    else:
        files = [File.model_validate({"path": p}) for p in file_paths]
    merge_pdfs(files, output_path, set_bookmarks)


@cli.command()
def pdfs_in_folder(
    input_dir_path: Annotated[
        Path, Argument(help="Directory containing PDF files.")
    ],
    output_path: Annotated[
        Path, Argument(help="Destination path for the merged PDF.")
    ],
    set_bookmarks: Annotated[
        bool,
        Option(help="Create a top‑level bookmark for each source document."),
    ] = False,
) -> None:
    """Merge **all** PDFs found in *path_str*.

    Additional information:
    The command scans the directory non‑recursively (``Path.iterdir``) and
    passes every entry to :func:`pdf_tools.merge.service.merge_pdfs`.
    """
    files = [
        File.model_validate({"path": str(f)}) for f in input_dir_path.iterdir()
    ]
    merge_pdfs(files, output_path, set_bookmarks)
