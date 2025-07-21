"""
High‑level orchestration.

Functions to *convert* a batch of heterogenous files to PDFs **and then merge**
them into a single document.

In many user flows you don’t want to remember two separate commands (“convert
then merge”)—you just want the final PDF.  This helper squeezes those steps
into one synchronous call so the CLI (or your own API) can offer a simple
one‑liner.

Workflow
--------
1. **Convert** – Each incoming :class:`pdf_tools.models.files.File` is passed
   to :func:`pdf_tools.convert.service.convert_file_to_pdf`. Unsupported types
   remain unchanged (the converter returns the original file object).
2. **Merge** – The (now mostly PDF) list is forwarded to
   :func:`pdf_tools.merge.service.merge_pdfs`.

The function is intentionally *blocking* and writes the merged PDF to disk.
Wrap it in a thread executor if you need async I/O.
"""

from collections.abc import Sequence
from pathlib import Path

from pdf_tools.convert.service import convert_file_to_pdf
from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File

__all__: Sequence[str] = [
    "convert_and_merge_pdfs",
]


def convert_and_merge_pdfs(
    files: Sequence[File], output_path: Path, set_bookmarks: bool = False
) -> File:
    """Convert *files* to PDFs (if needed) and merge them into one document.

    Parameters
    ----------
    files : Sequence[File]
        Ordered collection of :class:`~pdf_tools.models.files.File` objects.
        Each entry is run through the conversion layer **before** merging.
    output_path_str : str | pathlib.Path
        Filesystem location where the merged PDF will be written.
    set_bookmarks : bool, default ``False``
        When *True*, a top‑level outline (bookmark) is created for each source
        document (mirroring :func:`pdf_tools.merge.service.merge_pdfs`).

    Returns
    -------
    File
        :class:`~pdf_tools.models.files.File` describing the merged PDF.

    Examples
    --------
    >>> from pdf_tools.process.service import convert_and_merge_pdfs
    >>> from pdf_tools.models.files import File
    >>> final = convert_and_merge_pdfs(
    ...     files=[
    ...         File(path_str="report.docx"),
    ...         File(path_str="photo.jpg"),
    ...         File(path_str="appendix.pdf"),
    ...     ],
    ...     output_path_str="bundle.pdf",
    ...     set_bookmarks=True,
    ... )
    >>> final.name
    'bundle.pdf'
    """
    files = [convert_file_to_pdf(file) for file in files]
    return merge_pdfs(files, output_path, set_bookmarks)
