from collections.abc import Sequence
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
    output_path_str: Annotated[str, Argument()],
    path_strs: Annotated[Optional[list[str]], Argument()] = None,
    json_file: Annotated[Optional[str], Option()] = None,
    set_bookmarks: Annotated[bool, Option()] = False,
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
    _convert_and_merge_pdfs(files, output_path_str, set_bookmarks)
