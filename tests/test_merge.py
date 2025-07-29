"""Merging produces correct page count and order."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader, PdfWriter

from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File


def _make_blank_pdf(path: Path) -> None:
    """Create a one-page blank PDF at *path* using pypdf."""
    writer = PdfWriter()
    # A minimal 1-pt × 1-pt blank page is enough for tests
    writer.add_blank_page(width=1, height=1)
    with path.open("wb") as fh:
        writer.write(fh)


def test_merge_page_count(sample_pdfs: Sequence[File], tmp_path: Path) -> None:
    """Total pages equals sum of inputs."""
    out = tmp_path / "merged.pdf"
    merge_pdfs(files=sample_pdfs, output_path=out)
    assert out.exists()

    total_in = sum(len(PdfReader(p.path).pages) for p in sample_pdfs)
    total_out = len(PdfReader(out).pages)
    assert total_in == total_out


def test_merge_pdfs_success(tmp_path: Path, monkeypatch: Any) -> None:
    """A merged file is written and a validated File is returned."""
    # Arrange – two tiny PDFs
    input1 = tmp_path / "a.pdf"
    input2 = tmp_path / "b.pdf"
    _make_blank_pdf(input1)
    _make_blank_pdf(input2)

    files = [File(path=input1), File(path=input2)]
    output_path = tmp_path / "merged.pdf"

    # Silence Typer chatter
    monkeypatch.setattr(
        "pdf_tools.merge.service.typer.echo", lambda *_args, **_kw: None
    )

    # Act
    merged_file = merge_pdfs(files=files, output_path=output_path)

    # Assert
    assert output_path.exists(), (
        "merge_pdfs should write the output PDF to disk"
    )
    assert merged_file.path == output_path
    assert merged_file.type == "pdf"


def test_merge_pdfs_raises_when_output_exists(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Raise FileExistsError if output already exists and overwrite False."""
    # Arrange – source PDF & pre-existing destination
    src = tmp_path / "src.pdf"
    _make_blank_pdf(src)
    out_path = tmp_path / "already_there.pdf"
    _make_blank_pdf(out_path)  # occupy the target

    files = [File(path=src)]

    monkeypatch.setattr(
        "pdf_tools.merge.service.typer.echo", lambda *_args, **_kw: None
    )

    # Act / Assert
    with pytest.raises(FileExistsError):
        merge_pdfs(files=files, output_path=out_path, overwrite=False)


def test_merge_pdfs_skips_when_wrong_file_type(
    tmp_path: Path, monkeypatch: Any, capfd: Any
) -> None:
    """Skip merging file if file is not a PDF."""
    # Arrange
    src = tmp_path / "src.img"
    _make_blank_pdf(src)
    dest_dir = tmp_path / "missing"
    out_path = dest_dir / "dest.pdf"  # parent directory is absent

    files = [File(path=src)]

    monkeypatch.setattr(
        "pdf_tools.merge.service.typer.echo", lambda *_args, **_kw: None
    )

    # Act / Assert
    with pytest.raises(FileNotFoundError):
        merge_pdfs(files=files, output_path=out_path)


def test_merge_pdfs_raises_when_parent_dir_missing(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Raise FileNotFoundError if the parent directory does not exist."""
    # Arrange
    src = tmp_path / "src.pdf"
    _make_blank_pdf(src)
    dest_dir = tmp_path / "missing"
    out_path = dest_dir / "dest.pdf"  # parent directory is absent

    files = [File(path=src)]

    monkeypatch.setattr(
        "pdf_tools.merge.service.typer.echo", lambda *_args, **_kw: None
    )

    # Act / Assert
    with pytest.raises(FileNotFoundError):
        merge_pdfs(files=files, output_path=out_path)
