from pathlib import Path
from typing import Annotated

from typer import Argument, Option

from pdf_tools.cli import AsyncTyper
from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File

cli = AsyncTyper(no_args_is_help=True)


@cli.command()
def pdf_files(
    path_strs: Annotated[list[str], Argument()],
    output_path_str: Annotated[str, Argument()],
    set_bookmarks: Annotated[bool, Option()] = False,
) -> None:
    files = [
        File.model_validate({"path_str": path_str}) for path_str in path_strs
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
