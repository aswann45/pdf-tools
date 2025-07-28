"""Property checks for File/Files models."""

from __future__ import annotations

import string
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pdf_tools.models.files import File
from pdf_tools.models.watermark import WatermarkOptions


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    st.text(alphabet=string.ascii_letters, min_size=1).filter(
        lambda s: "." not in s
    )
)
def test_dir_type(tmp_path: Path, name: str) -> None:
    """File.type == 'dir' for real directories."""
    d = tmp_path / name
    d.mkdir()
    assert File(path=d).type == "dir"
    d.rmdir()  # cleanup


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(st.sampled_from(["pdf", "png", "txt"]))
def test_file_path_props(tmp_path: Path, ext: str) -> None:
    """File props match expected outputs."""
    f = tmp_path / f"foo.{ext}"
    f.touch()
    assert (file := File(path=f)).type == ext
    assert file.name == f.name
    assert file.parent == f.parent
    f.unlink()  # cleanup


def test_validate_color() -> None:
    """Color field validator ensures correct formatting."""
    with pytest.raises(ValueError):
        WatermarkOptions(text="TEST", color="bad_color")
