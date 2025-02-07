import typer
from pypdf import PdfWriter

from pdf_tools.models.files import File


def merge_pdfs(
    files: list[File], output_path_str: str, set_bookmarks: bool = False
) -> File:
    merger = PdfWriter()
    for file in files:
        if file.type != "pdf":
            typer.echo(
                f"Skipping {file.path.resolve()} because it is not a PDF"
            )
            continue
        if set_bookmarks:
            merger.append(
                str(file.absolute_path),
                outline_item=file.bookmark_name or file.name,
            )
        else:
            merger.append(str(file.absolute_path))

    with open(output_path_str, "wb") as output:
        merger.write(output)

    return File.model_validate({"path_str": output_path_str})
