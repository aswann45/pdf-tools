"""
Core data models that represent filesystem artefacts used by :mod:`pdf-tools`.

The public surface of the library manipulates files and directories in many
places—CLI converters, merger utilities, and the processing pipeline.  To keep
those layers loosely-coupled and testable we expose two small, fully-typed
:mod:`pydantic` v2 models:

* :class:`File`  - a single file or directory on disk, enriched with lazily
  computed convenience attributes (name, parent, suffix, etc.).
* :class:`Files` - a lightweight container that wraps an ordered collection of
  :class:`File` instances but still behaves like a regular :class:`Sequence`
  for idiomatic iteration and indexing.

Both models deliberately avoid any I/O side-effects; they merely *describe*
paths.  All validations happen eagerly via Pydantic so downstream code can rely
on type guarantees.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeAlias

from pydantic import BaseModel, Field, RootModel, computed_field

__all__ = [
    "File",
    "Files",
    "FileInput",
    "FilesInput",
    "SkippedFile",
    "ConversionBatchResult",
    "coerce_file",
    "coerce_files",
]


class File(BaseModel):
    """Serializable description of a single file or directory on disk.

    Parameters
    ----------
    path : :class:`Path`
        Path supplied by the caller.  It can be absolute or relative; the
        :attr:`absolute_path` property resolves it.
    bookmark_name : `str` | `None`, optional
        Optional human-friendly alias that a user may register via the CLI so
        they can reference the path later without typing the full string.

    Notes
    -----
    *The model does **not** check whether the given path exists.*  This
    decision lets higher-level services decide when (and if) to touch the
    filesystem. Use :attr:`absolute_path.exists` in those layers if needed.
    """

    path: Path
    bookmark_name: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def absolute_path(self) -> Path:
        """Return an absolute, resolved version of :attr:`path`."""
        return self.path.resolve()

    @computed_field  # type: ignore[prop-decorator]
    @property
    def type(self) -> str:
        """Infer the resource *type*.

        Returns
        -------
        str
            ``"dir"`` if the path represents a directory, otherwise the file
            extension **without** the leading dot (e.g., ``"pdf"``, ``"png"``).
        """
        if self.absolute_path.is_dir():
            return "dir"
        return self.path.suffix.replace(".", "")

    @computed_field  # type: ignore[prop-decorator]
    @property
    def name(self) -> str:
        """Return just the filename (or directory name) portion of the path."""
        return self.path.name

    @computed_field  # type: ignore[prop-decorator]
    @property
    def parent(self) -> Path:
        """Return the parent directory as a :class:`pathlib.Path`."""
        return self.path.parent


class Files(RootModel):
    """Container model for an ordered collection of :class:`File` objects.

    The class inherits from :class:`pydantic.RootModel` so that the JSON schema
    for a list of files is ``[{...}, {...}]`` rather than ``{"root": [...]}``.

    This wrapper:

    * Preserves Pydantic's validation and serialisation features.
    * Implements ``__iter__`` and ``__getitem__`` so it quacks like a normal
      sequence in most contexts (``for f in files: ...``).

    Examples
    --------
    >>> from pdf_tools.models.files import File, Files
    >>> files = Files(
    ...     [
    ...         File(path="report.pdf"),
    ...         File(path="images", bookmark_name="assets"),
    ...     ]
    ... )
    >>> [f.type for f in files]
    ['pdf', 'dir']
    """

    root: Sequence[File]

    def __iter__(self) -> Any:
        """Return an iterator over the underlying :class:`File` objects."""
        return iter(self.root)

    def __getitem__(self, item: Any) -> Any:
        """Return *item* from the underlying sequence.

        Parameters
        ----------
        item : int | slice
            Standard index or slice object.

        Returns
        -------
        File | Files
            A single :class:`File` when *item* is an ``int``;
            a new :class:`Files` instance when *item* is a ``slice``.
        """
        return self.root[item]


FileInput: TypeAlias = File | str | Path
FilesInput: TypeAlias = Files | Sequence[FileInput]


class SkippedFile(BaseModel):
    """A file skipped during a batch operation."""

    path: Path
    reason: str


class ConversionBatchResult(BaseModel):
    """Structured result for batch conversion helpers."""

    converted: list[File] = Field(default_factory=list)
    skipped: list[SkippedFile] = Field(default_factory=list)


def coerce_file(file: FileInput) -> File:
    """Normalize a path-like object into a :class:`File` model."""
    if isinstance(file, File):
        return file
    return File(path=Path(file))


def coerce_files(files: FilesInput) -> list[File]:
    """Normalize a sequence of path-like objects into :class:`File` models."""
    if isinstance(files, Files):
        return list(files.root)
    if isinstance(files, (File, str, Path)):
        raise TypeError("Expected a sequence of files, not a single file.")
    return [coerce_file(file) for file in files]
