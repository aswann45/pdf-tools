"""
Core data models that represent filesystem artefacts used by :mod:`pdf-tools`.

The public surface of the library manipulates files and directories in many
places—CLI converters, merger utilities, and the processing pipeline.  To keep
those layers loosely-coupled and testable we expose two small
:mod:`pydantic` v2 models:

* :class:`File`  - a single file or directory on disk, enriched with lazily
  computed convenience attributes (name, parent, suffix, etc.).
* :class:`Files` - a container for an ordered collection of :class:`File`
  instances with iteration, indexing, and slicing.

These models do not mutate files on disk. Some computed properties inspect
filesystem state. Pydantic validates the supplied fields eagerly.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeAlias, overload

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
    path : Path | str
        Path supplied by the caller. It can be absolute or relative; the
        :attr:`absolute_path` property resolves it.
    bookmark_name : `str` | `None`, optional
        Optional outline title when merging with ``set_bookmarks=True``. If
        omitted or empty, the merge service uses the filename.

    Notes
    -----
    Construction does not require the path to exist. The computed ``type``
    property checks whether the resolved path is a directory.
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
    * Supports iteration and integer indexing. Slicing returns the underlying
      sequence's slice, not another :class:`Files` model.

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

    @overload
    def __getitem__(self, item: int) -> File: ...

    @overload
    def __getitem__(self, item: slice) -> Sequence[File]: ...

    def __getitem__(self, item: int | slice) -> File | Sequence[File]:
        """Return *item* from the underlying sequence.

        Parameters
        ----------
        item : int | slice
            Standard index or slice object.

        Returns
        -------
        File | Sequence[File]
            A single :class:`File` when *item* is an ``int``;
            a slice of the underlying sequence when *item* is a ``slice``.
        """
        return self.root[item]


FileInput: TypeAlias = File | str | Path
FilesInput: TypeAlias = Files | Sequence[FileInput]


class SkippedFile(BaseModel):
    """A batch input that failed conversion, with its path and error reason."""

    path: Path
    reason: str


class ConversionBatchResult(BaseModel):
    """Batch result with successful PDFs and inputs skipped on failure.

    ``converted`` contains generated PDF :class:`File` models. ``skipped``
    contains each failed input and its reason; both lists may be populated.
    """

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
