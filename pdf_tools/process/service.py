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
1. **Convert** - Each incoming file is passed to
   :func:`pdf_tools.convert.service.convert_file_to_pdf`. Existing PDFs pass
   through unchanged, and unsupported types are skipped so supported files can
   still be merged.
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
    files : :class:`Sequence[File | str | Path]`
        Ordered collection of path-like inputs or
        :class:`pdf_tools.models.files.File` objects. Each entry is run through
        the conversion layer **before** merging.
    output_path : `str` | :class:`pathlib.Path`
        Filesystem location where the merged PDF will be written.
    set_bookmarks : bool, default ``False``
        When *True*, a top-level outline (bookmark) is created for each source
        document (mirroring :func:`pdf_tools.merge.service.merge_pdfs`).
    overwrite : `bool`, default ``False``
        When `True` overwrite output documents if they already exist.

    Returns
    -------
    File
        :class:`pdf_tools.models.files.File` describing the merged PDF.

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
