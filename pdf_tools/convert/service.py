"""
Synchronous helpers that turn common document types into *flattened* PDFs.

The conversion layer writes results to disk and returns
:class:`pdf_tools.models.files.File` instances that describe the freshly
minted PDFs. Public helpers accept either those models or plain path-like
inputs.

Supported input types & back-ends
---------------------------------
* **Microsoft Word** (``.doc``/``.docx``) → LibreOffice :mod:`unoconvert` CLI.
* **Raster images** (``.jpg``/``.jpeg``/``.png``/``.tiff``/``.bmp``) →
  :mod:`Pillow` + :mod:`img2pdf`.

Both back-ends are platform-dependent: LibreOffice must be on ``$PATH`` and
Pillow relies on system image libraries.  Each helper therefore emits a
:meth:`typer.echo` so the CLI shows *progress* but your own code can swap it
for a custom logger.

Design notes
------------
* All functions are **blocking** and may run external processes; call them in a
  ThreadPool if you need async flows.
* The helpers never *overwrite* an existing file unless the caller explicitly
  points *output_path* to an existing location.
"""

import subprocess
from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Final

import img2pdf  # type: ignore
import typer
from PIL import Image

from pdf_tools.convert.unoserver_ctx import assert_office_ready
from pdf_tools.models.files import (
    ConversionBatchResult,
    File,
    FileInput,
    FilesInput,
    SkippedFile,
    coerce_file,
    coerce_files,
)

__all__: Sequence[str] = [
    "convert_word_to_pdf",
    "convert_image_to_pdf",
    "convert_file_to_pdf",
    "convert_files_to_pdfs",
    "convert_folder_to_pdfs",
    "UnsupportedFileTypeError",
]

SUPPORTED_IMAGE_FORMATS: set[str] = {"jpeg", "png", "jpg", "tiff", "bmp"}
SUPPORTED_WORD_FORMATS: set[str] = {"doc", "docx"}
SUPPORTED_FILE_FORMATS: set[str] = (
    SUPPORTED_IMAGE_FORMATS | SUPPORTED_WORD_FORMATS
)
_UNOCONVERT_CMD: Final[str] = "unoconvert"


class UnsupportedFileTypeError(ValueError):
    """Raised when no converter exists for a file type."""

    def __init__(self, file: File) -> None:
        file_type = f".{file.type}" if file.type else "no extension"
        supported = ", ".join(
            f".{suffix}" for suffix in sorted(SUPPORTED_FILE_FORMATS)
        )
        super().__init__(
            f"Unsupported file type for '{file.path}': {file_type}. "
            f"Supported types: {supported}."
        )


def _resolve_output_path(file: File, output_path: str | Path | None) -> Path:
    if output_path is None:
        return file.absolute_path.with_suffix(".pdf")

    path = Path(output_path)
    if path.suffix == "":
        return (path / file.path.stem).with_suffix(".pdf")
    return path


def _output_dir_handler(input_path: Path, output_dir: Path) -> Path:
    """
    Create an output path from given input file and output directory.

    Takes an input file path (regardless of file type) and returns the filename
    from the input file with a PDF extension and located within the given
    output directory.

    Parameters
    ----------
    input_path : :class:`Path`
        Input file path to extract filename from.
    output_dir : :class:`Path`
        Path to output directory where the resulting file will reside in.

    Returns
    -------
    :class:`Path`
        New file path located inside the given `output_dir` and with a
        `.pdf` extension.
    """
    name = input_path.stem
    return (output_dir / name).with_suffix(".pdf")


def convert_word_to_pdf(
    file: FileInput,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> File:
    """Convert a Word document (``.doc``, ``.docx``) to PDF on disk.

    Parameters
    ----------
    file : :class:`File` | :class:`str` | :class:`Path`
        A Word document path or :class:`pdf_tools.models.files.File`
        (:attr:`file.type` must be either ``"doc"`` or ``"docx"``).
    output_path : :class:`Path` | :class:`None`, optional
        Destination path for the resulting PDF.  When *None* (default) the
        helper replaces the source extension with ``.pdf`` next to the input
        file.
    overwrite : `bool`, default ``False``
        Overwrite output file if it already exists.

    Returns
    -------
    :class:`File`
        A new :class:`pdf_tools.models.files.File` that points at the
        generated PDF and carries forward the original *bookmark_name*.

    Raises
    ------
    FileExistsError
        If `overwrite` is False and the output path already exists.
    RuntimeError
        If LibreOffice exits with a non-zero status.
    FileNotFoundError
        If `output_path`'s parent directory does not exist.
    """
    file = coerce_file(file)
    assert_office_ready()
    typer.echo(f"Converting {file.path.resolve()}")
    new_path = _resolve_output_path(file, output_path)

    if new_path.exists() and overwrite is False:
        raise FileExistsError(f"File {new_path} already exists. Exiting.")
    if new_path.is_dir():
        raise ValueError(f"Path {new_path} is a directory.")
    if new_path.parent.exists() is False:
        raise FileNotFoundError(
            f"Output directory {new_path.parent} does not exist. "
            f"Please create it or choose an existing directory."
        )
    try:
        subprocess.run(
            [
                _UNOCONVERT_CMD,
                str(file.absolute_path),
                str(new_path),
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as ex:
        raise RuntimeError(
            f"LibreOffice failed to convert '{file.path}' → '{new_path}'. "
            f"Exit code {ex.returncode}. Stderr:\n{ex.stderr.decode()}."
        ) from ex

    typer.echo(f"Converted {new_path}")
    _file_data = {"path": new_path, "bookmark_name": file.bookmark_name}
    return File.model_validate(_file_data)


def convert_image_to_pdf(
    file: FileInput,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> File:
    """Convert a single raster image to a *vector-wrapped* PDF.

    The routine uses :mod:`Pillow` to normalise color mode and :mod:`img2pdf`
    to wrap the image bytes without re-encoding (lossless).

    Parameters
    ----------
    file : :class:`File` | :class:`str` | :class:`Path`
        Source image path or :class:`pdf_tools.models.files.File`
        (``jpg``, ``jpeg``, ``tiff``, ``bmp``, or ``png``). Other types raise
        ``ValueError``.
    output_path : :class:`pathlib.Path` | `None`, optional
        Destination path for the resulting PDF.  Defaults to the input path
        with ``.pdf`` extension.
    overwrite : bool, default ``False``
        Overwrite output file if it already exists.

    Returns
    -------
    File
        :class:`pdf_tools.models.files.File` for the created PDF.

    Raises
    ------
    ValueError
        If :attr:`file.type` is not a supported image format.
    OSError
        If `Pillow` cannot read or decode the image.
    FileNotFoundError
        If `output_path`'s parent directory does not exist.
    FileExistsError
        If `overwrite` is False and the output path already exists.
    """
    file = coerce_file(file)
    typer.echo(f"Converting {file.path.resolve()}")
    new_path = _resolve_output_path(file, output_path)

    if new_path.exists() and overwrite is False and new_path.is_file():
        raise FileExistsError(f"File {new_path} already exists. Exiting.")
    if new_path.is_dir():
        raise ValueError(f"Path {new_path} is a directory.")
    if new_path.parent.exists() is False:
        raise FileNotFoundError(
            f"Output directory {new_path.parent} does not exist. "
            f"Please create it or choose an existing directory."
        )
    try:
        with Image.open(file.absolute_path) as image:
            image_format = (image.format or "").lower()
            if image_format not in SUPPORTED_IMAGE_FORMATS:
                raise ValueError(
                    f"Unsupported image format '{image.format}'. "
                    f"Supported formats: "
                    f"{', '.join(sorted(SUPPORTED_IMAGE_FORMATS))}."
                )
            if image.mode != "RGB":
                image = image.convert("RGB")
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            with open(new_path, "wb") as pdf:
                pdf_bytes = img2pdf.convert(buffer.getvalue())
                pdf.write(pdf_bytes)
    except (OSError, ValueError) as ex:
        raise RuntimeError(
            f"Could not convert image '{file.path}' to PDF: {ex}."
        ) from ex
    _file_data = {"path": new_path, "bookmark_name": file.bookmark_name}
    return File.model_validate(_file_data)


def convert_file_to_pdf(
    file: FileInput,
    output_path: str | Path | None = None,
    overwrite: bool = False,
) -> File:
    """Dispatch `file` to the appropriate conversion helper.

    Inspects :attr:`file.type <pdf_tools.models.files.File.type>`
    and forwards the call to either :func:`convert_word_to_pdf` or
    :func:`convert_image_to_pdf`. Unsupported types raise
    :class:`UnsupportedFileTypeError`.

    Parameters
    ----------
    file : :class:`File` | :class:`str` | :class:`Path`
        Any path-like input or :class:`pdf_tools.models.files.File` instance.
    output_path : `pathlib.Path` | `None`, optional
        Desired output path.  Passed verbatim to the underlying helper.
    overwrite : `bool`, default ``False``
        Overwrite output file if it already exists.

    Returns
    -------
    :class:`File`
        The converted PDF description.

    Raises
    ------
    UnsupportedFileTypeError
        If an unsupported file type is provided.
    """
    file = coerce_file(file)
    file_type = file.type.lower()

    if file_type in SUPPORTED_WORD_FORMATS:
        return convert_word_to_pdf(file, output_path, overwrite=overwrite)

    if file_type in SUPPORTED_IMAGE_FORMATS:
        return convert_image_to_pdf(file, output_path, overwrite=overwrite)

    raise UnsupportedFileTypeError(file)


def convert_files_to_pdfs(
    files: FilesInput,
    output_dir: str | Path | None = None,
    overwrite: bool = False,
) -> ConversionBatchResult:
    """Convert many files to PDFs, skipping failures."""
    target_dir = Path.cwd() if output_dir is None else Path(output_dir)
    converted: list[File] = []
    skipped: list[SkippedFile] = []

    for file in coerce_files(files):
        try:
            converted.append(
                convert_file_to_pdf(
                    file,
                    output_path=_output_dir_handler(file.path, target_dir),
                    overwrite=overwrite,
                )
            )
        except (RuntimeError, ValueError, OSError) as ex:
            skipped.append(SkippedFile(path=file.path, reason=str(ex)))

    return ConversionBatchResult(converted=converted, skipped=skipped)


def convert_folder_to_pdfs(
    input_dir: str | Path,
    output_dir: str | Path | None = None,
    overwrite: bool = False,
) -> ConversionBatchResult:
    """Convert immediate children of a folder to PDFs."""
    folder = Path(input_dir)
    files = [File(path=file) for file in folder.iterdir()]
    return convert_files_to_pdfs(
        files,
        output_dir=output_dir,
        overwrite=overwrite,
    )
