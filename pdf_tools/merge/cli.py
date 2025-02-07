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
    path_strs: Annotated[list[str], Argument()],
    output_path_str: Annotated[str, Argument()],
    set_bookmarks: Annotated[bool, Option()] = False,
    json_file: Annotated[Optional[str], Option()] = None,
) -> None:
    files: Sequence[File]
    if json_file is not None:
        with open(json_file) as f:
            files = Files.model_validate_json(f.read()).root
    elif path_strs is None:
        raise ValueError("Either path_strs or json_file must be provided")
    else:
        files = [
            File.model_validate({"path_str": path_str})
            for path_str in path_strs
        ]
    merge_pdfs(files, output_path_str, set_bookmarks)


@cli.command()
def pdfs_in_folder(
    path_str: Annotated[str, Argument()],
    output_path_str: Annotated[str, Argument()],
    set_bookmarks: Annotated[bool, Option()] = False,
) -> None:
    files = [
        File.model_validate({"path_str": str(f)})
        for f in Path(path_str).iterdir()
    ]
    merge_pdfs(files, output_path_str, set_bookmarks)
