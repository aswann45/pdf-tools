"""
Synchronous helpers that turn common document types into *flattened* PDFs.

The conversion layer writes results to disk and returns
:class:`pdf_tools.models.files.File` instances that describe the PDFs.
Single-file helpers accept those models or ``str``/``Path`` inputs; batch
helpers accept :class:`pdf_tools.models.files.Files` or a sequence of them.

Supported input types & back-ends
---------------------------------
* **Microsoft Word** (``.doc``/``.docx``) → LibreOffice :mod:`unoconvert` CLI.
* **Raster images** (``.jpg``/``.jpeg``/``.png``/``.tiff``/``.bmp``) →
  :mod:`Pillow` + :mod:`img2pdf`.

Word conversion requires LibreOffice and a working ``unoserver`` listener for
``unoconvert``. CLI commands manage the listener when needed; direct service
callers must manage it themselves.

Design notes
------------
* All functions are **blocking** and may run external processes; call them in a
  ThreadPool if you need async flows.
* Output parent directories must already exist. Existing outputs are protected
  unless ``overwrite=True``.
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
        A Word document path or :class:`pdf_tools.models.files.File`. This
        direct helper passes the source to ``unoconvert``; it does not check
        the extension. The dispatcher selects it for ``.doc`` and ``.docx``.
    output_path : str | Path | None, optional
        Destination PDF path, or a directory when no suffix is supplied.
        When *None*, replace the source extension with ``.pdf`` beside the
        input. The output parent directory must exist. Direct callers must
        provide a running ``unoserver`` listener.
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
        If ``unoconvert`` or its listener is unavailable, or conversion fails.
    FileNotFoundError
        If `output_path`'s parent directory does not exist.
    ValueError
        If the resolved output path is a directory.
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
    """Convert one supported raster image to PDF.

    Pillow opens the source and checks its detected format against the
    supported allowlist. Non-RGB images are converted to RGB, then the image
    is encoded as PNG in memory. ``img2pdf`` builds the PDF from those PNG
    bytes. Source bytes are not passed through unchanged: JPEG data may be
    re-encoded, metadata may be lost, and large images may use extra memory.

    Parameters
    ----------
    file : :class:`File` | :class:`str` | :class:`Path`
        Source image path or :class:`pdf_tools.models.files.File`. This direct
        helper checks Pillow's detected format against JPEG, PNG, TIFF, and
        BMP. The dispatcher additionally requires a supported extension.
    output_path : str | Path | None, optional
        Destination PDF path, or a directory when no suffix is supplied.
        Defaults to the input path with ``.pdf`` extension. The output parent
        directory must exist.
    overwrite : bool, default ``False``
        Overwrite output file if it already exists.

    Returns
    -------
    File
        :class:`pdf_tools.models.files.File` for the created PDF.

    Raises
    ------
    RuntimeError
        If Pillow cannot read the image or its detected format is unsupported.
    ValueError
        If the resolved output path is a directory.
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
            normalized_image = (
                image if image.mode == "RGB" else image.convert("RGB")
            )
            buffer = BytesIO()
            normalized_image.save(buffer, format="PNG")
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
    output_path : str | Path | None, optional
        Desired output path. Resolved by the selected helper; its parent must
        exist.
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
    FileExistsError
        If the output exists and ``overwrite`` is false.
    FileNotFoundError
        If the output parent directory does not exist.
    ValueError
        If the resolved output path is a directory.
    RuntimeError
        If image or Word conversion fails, including unavailable Word tools.
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
    """Convert a batch and record individual failures without stopping.

    Parameters
    ----------
    files : Files | Sequence[File | str | Path]
        Inputs to convert in the given sequence.
    output_dir : str | Path | None, optional
        Existing output directory; defaults to the current directory. A
        missing directory produces one skipped result per input.
    overwrite : bool, default False
        Replace existing output PDFs when true.

    Returns
    -------
    ConversionBatchResult
        ``converted`` lists successful PDFs; ``skipped`` lists failed inputs
        and their reasons. Both may be populated or empty. The function does
        not start a Word-conversion listener for direct Python callers.

    Raises
    ------
    TypeError
        If ``files`` is a single path or :class:`File`, not a sequence.
    """
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
    """Convert immediate children of a folder using batch semantics.

    Parameters
    ----------
    input_dir : str | Path
        Folder to enumerate without recursion.
    output_dir : str | Path | None, optional
        Existing output directory; defaults to the current directory.
    overwrite : bool, default False
        Replace existing output PDFs when true.

    Returns
    -------
    ConversionBatchResult
        Successful conversions and skipped inputs with reasons.

    Raises
    ------
    FileNotFoundError
        If ``input_dir`` does not exist. A missing *output* directory is
        recorded as skipped results instead.
    NotADirectoryError
        If ``input_dir`` is not a directory.
    """
    folder = Path(input_dir)
    files = [File(path=file) for file in folder.iterdir()]
    return convert_files_to_pdfs(
        files,
        output_dir=output_dir,
        overwrite=overwrite,
    )
