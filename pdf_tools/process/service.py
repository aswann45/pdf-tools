"""
High-level orchestration.

Functions to *convert* a batch of heterogenous files to PDFs **and then merge**
them into a single document.

In many user flows you don't want to remember two separate commands (“convert
then merge”)—you just want the final PDF.  This helper squeezes those steps
into one synchronous call so the CLI (or your own API) can offer a simple
one-liner.

Workflow
--------
1. **Convert** - Existing PDFs pass through unchanged. Other inputs are
   converted individually; failures are silently omitted.
2. **Merge** - The (now mostly PDF) list is forwarded to
   :func:`pdf_tools.merge.service.merge_pdfs`.

The function is intentionally *blocking* and writes the merged PDF to disk.
Wrap it in a thread executor if you need async I/O.
"""

from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from tempfile import NamedTemporaryFile

from pdf_tools.convert.service import convert_file_to_pdf
from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File, FilesInput, coerce_files

__all__: Sequence[str] = [
    "convert_and_merge_pdfs",
]


def convert_and_merge_pdfs(
    files: FilesInput,
    output_path: str | Path,
    set_bookmarks: bool = False,
    overwrite: bool = False,
) -> File:
    """Convert *files* to PDFs (if needed) and merge them into one document.

    Parameters
    ----------
    files : Files | Sequence[File | str | Path]
        Ordered inputs. Existing PDFs pass through; other inputs are
        converted to temporary PDFs. Failed conversions are omitted without
        a report, so the output may contain fewer documents than requested.
        Word inputs use direct LibreOffice conversion without a listener.
    output_path : str | Path
        Destination PDF path. Its parent directory must already exist.
    set_bookmarks : bool, default ``False``
        When *True*, a top-level outline (bookmark) is created for each source
        document (mirroring :func:`pdf_tools.merge.service.merge_pdfs`).
    overwrite : `bool`, default ``False``
        When `True` overwrite output documents if they already exist.

    Returns
    -------
    File
        :class:`pdf_tools.models.files.File` describing the merged PDF.

    Raises
    ------
    TypeError
        If ``files`` is a single path or :class:`File`, not a sequence.
    ValueError
        If no inputs remain after conversion failures.
    FileExistsError
        If the output exists and ``overwrite`` is false.
    FileNotFoundError
        If the output parent does not exist, or an existing PDF input is
        missing when the merge reads it.
    OSError
        If reading an existing PDF or writing the output fails.

    Notes
    -----
    For all-or-nothing work, run conversion separately, inspect the results,
    and merge only when every required input succeeded.

    Examples
    --------
    >>> from pdf_tools.process.service import convert_and_merge_pdfs
    >>> final = convert_and_merge_pdfs(
    ...     files=["report.docx", "photo.jpg", "appendix.pdf"],
    ...     output_path="bundle.pdf",
    ...     set_bookmarks=True,
    ... )
    >>> final.name
    'bundle.pdf'
    """
    converted: list[File] = []
    temp_paths: list[Path] = []
    for file in coerce_files(files):
        if file.type.lower() == "pdf":
            converted.append(file)
            continue
        try:
            with NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_pdf:
                tmp_pdf.close()
                temp_path = Path(tmp_pdf.name)
                temp_paths.append(temp_path)
                converted.append(
                    convert_file_to_pdf(
                        file,
                        output_path=temp_path,
                        overwrite=True,
                    ),
                )
        except (RuntimeError, ValueError, OSError):
            continue
    if not converted:
        for temp_path in temp_paths:
            with suppress(OSError):
                temp_path.unlink()
        raise ValueError("No files successfully converted. Aborting merge.")

    try:
        return merge_pdfs(
            converted, Path(output_path), set_bookmarks, overwrite=overwrite
        )
    finally:
        for temp_path in temp_paths:
            with suppress(OSError):
                temp_path.unlink()
