"""
High-level PDF *merge* operations used by both the CLI and programmatic API.

Only one public helper is exposed—:func:`merge_pdfs`.  It provides a minimal
yet robust wrapper around :class:`pypdf.PdfWriter` so that downstream layers
can merge an arbitrary sequence of :class:`pdf_tools.models.files.File`
objects without fiddling with low-level writer mechanics or conditional
bookmark logic.

The function deliberately stays synchronous and file-system side-effectful
(*writes directly to disk*) because the surrounding Typer CLI command is also
synchronous.  When we need async behaviour we can slap this into a thread
executor.

**Design decisions**
--------------------
1. *Graceful non-PDF handling* – Non-PDF inputs are skipped with a
   user-friendly warning via :mod:`typer`.  This matches the CLI mantra of
   "be liberal in what you accept".
2. *Bookmark support* – If ``set_bookmarks=True`` we persist each source file's
   :attr:`pdf_tools.models.files.File.bookmark_name` (or fallback to its
   :attr:`pdf_tools.models.files.File.name`) as an outline entry so viewers
   like Acrobat or browser PDF readers render a helpful side panel.
3. *Pydantic return type* – The function returns a validated
   :class:`pdf_tools.models.files.File` describing the newly created output
   path.  This keeps the public API consistent with the rest of the project and
   avoids leaking raw :class:`Path` objects.
"""

from collections.abc import Sequence
from pathlib import Path

import typer
from pypdf import PdfWriter

from pdf_tools.models.files import File

__all__ = [
    "merge_pdfs",
]


def merge_pdfs(
    files: Sequence[File],
    output_path: Path,
    set_bookmarks: bool = False,
    overwrite: bool = False,
) -> File:
    """Merge multiple PDF files into a single document on disk.

    Parameters
    ----------
    files : :class:`Sequence[File]`
        Ordered iterable of :class:`pdf_tools.models.files.File` instances to
        merge.  Non-PDF entries are skipped after emitting a warning via
        :mod:`typer`.
    output_path: :class:`pathlib.Path`
        Filesystem path where the merged PDF will be written.  A ``.pdf``
        extension is not enforced but is *highly* recommended to avoid viewer
        confusion.
    set_bookmarks : `bool`, default ``False``
        When `True` each source document is inserted as a top-level outline
        (bookmark) in the resulting file.  The outline title is pulled from
        the corresponding :attr:`pdf_tools.models.files.File.bookmark_name`
        or falls back to :attr:`pdf_tools.models.files.File.name`.
    overwrite : `bool`, default ``False``
        When `True` overwrite output documents if they already exist.

    Returns
    -------
    File
        A new :class:`pdf_tools.models.files.File` instance pointing to the
        merged document.

    Raises
    ------
    FileExistsError
        If `overwrite` is False and the output path already exists.
    FileNotFoundError
        If `output_path`'s parent directory does not exist.
    OSError
        If the underlying OS call fails during write (e.g., permission error).

    Examples
    --------
    Merge three PDFs and create bookmarks for faster navigation.

    >>> from pdf_tools.merge.service import merge_pdfs
    >>> from pdf_tools.models.files import File, Files
    >>> merged = merge_pdfs(
    ...     files=[
    ...         File(path="intro.pdf", bookmark_name="Intro"),
    ...         File(path="chapter1.pdf", bookmark_name="Chapter 1"),
    ...         File(path="appendix.pdf", bookmark_name="Appendix"),
    ...     ],
    ...     output_path="full_report.pdf",
    ...     set_bookmarks=True,
    ... )
    >>> merged.name
    'full_report.pdf'
    >>> merged.type
    'pdf'
    """
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

    if output_path.exists() and overwrite is False:
        raise FileExistsError(f"File {output_path} already exists. Exiting.")
    if output_path.parent.exists() is False:
        raise FileNotFoundError(
            f"Output directory {output_path.parent} does not exist. "
            f"Please create it or choose an existing directory."
        )
    with open(output_path, "wb") as output:
        merger.write(output)

    merger.close()

    return File.model_validate({"path": output_path})
