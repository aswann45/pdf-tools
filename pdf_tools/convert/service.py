import subprocess
from io import BytesIO

import img2pdf  # type: ignore
import typer
from PIL import Image

from pdf_tools.models.files import File


def convert_word_to_pdf(file: File) -> File:
    typer.echo(f"Converting {file.path.resolve()}")
    subprocess.run(
        [
            "unoconvert",
            str(file.absolute_path),
            (new_path := str(file.absolute_path.with_suffix(".pdf"))),
        ]
    )

    return File.model_validate({"path_str": new_path})


def convert_image_to_pdf(file: File) -> File:
    typer.echo(f"Converting {file.path.resolve()}")

    with Image.open(file.absolute_path) as image:
        if image.mode != "RGB":
            image = image.convert("RGB")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        with open(
            (new_path := str(file.absolute_path.with_suffix(".pdf"))), "wb"
        ) as pdf:
            pdf_bytes = img2pdf.convert(buffer.getvalue())
            pdf.write(pdf_bytes)

    return File.model_validate({"path_str": new_path})


def convert_file_to_pdf(file: File) -> File:
    if file.type in ["doc", "docx"]:
        return convert_word_to_pdf(file)

    if file.type in ["jpg", "jpeg", "png"]:
        return convert_image_to_pdf(file)

    return file
