from pathlib import Path
from typing import Annotated

from typer import Argument

from pdf_tools.cli import AsyncTyper
from pdf_tools.convert.service import convert_file_to_pdf
from pdf_tools.models.files import File

cli = AsyncTyper(no_args_is_help=True)


@cli.command()
def file_to_pdf(path_str: Annotated[str, Argument()]) -> File:
    file = File.model_validate({"path_str": path_str})
    return convert_file_to_pdf(file)


@cli.command()
def files_to_pdf(path_strs: Annotated[list[str], Argument()]) -> list[File]:
    files = [
        File.model_validate({"path_str": path_str}) for path_str in path_strs
    ]
    return [convert_file_to_pdf(file) for file in files]


@cli.command()
def folder_to_pdfs(path_str: Annotated[str, Argument()]) -> list[File]:
    folder = Path(path_str)
    files = [
        File.model_validate({"path_str": str(file)})
        for file in folder.iterdir()
    ]
    return [convert_file_to_pdf(file) for file in files]
