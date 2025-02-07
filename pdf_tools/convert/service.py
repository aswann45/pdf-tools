import subprocess
from io import BytesIO

import img2pdf  # type: ignore
import typer
from PIL import Image

from pdf_tools.models.files import File


def convert_word_to_pdf(
    file: File, output_path_str: str | None = None
) -> File:
    typer.echo(f"Converting {file.path.resolve()}")
    if output_path_str is not None:
        new_path = output_path_str
    else:
        new_path = str(file.absolute_path.with_suffix(".pdf"))
    subprocess.run(["unoconvert", str(file.absolute_path), new_path])

    _file_data = {"path_str": new_path, "bookmark_name": file.bookmark_name}
    return File.model_validate(_file_data)


def convert_image_to_pdf(
    file: File, output_path_str: str | None = None
) -> File:
    typer.echo(f"Converting {file.path.resolve()}")
    if output_path_str is not None:
        new_path = output_path_str
    else:
        new_path = str(file.absolute_path.with_suffix(".pdf"))

    with Image.open(file.absolute_path) as image:
        if image.mode != "RGB":
            image = image.convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        with open(new_path, "wb") as pdf:
            pdf_bytes = img2pdf.convert(buffer.getvalue())
            pdf.write(pdf_bytes)
    _file_data = {"path_str": new_path, "bookmark_name": file.bookmark_name}
    return File.model_validate(_file_data)


def convert_file_to_pdf(
    file: File, output_path_str: str | None = None
) -> File:
    if file.type in ["doc", "docx"]:
        return convert_word_to_pdf(file, output_path_str)

    if file.type in ["jpg", "jpeg", "png"]:
        return convert_image_to_pdf(file, output_path_str)

    return file
