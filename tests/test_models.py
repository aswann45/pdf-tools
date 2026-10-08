"""Property checks for File/Files models."""

from __future__ import annotations

import string
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pdf_tools.models.files import File, Files
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


@pytest.mark.parametrize("rotation", [0, 90, 180, 270, -90])
def test_supported_watermark_rotation(rotation: int) -> None:
    """Model accepts multiples of 90 degrees."""
    options = WatermarkOptions(text="TEST", rotation=rotation)
    assert options.rotation == rotation


@pytest.mark.parametrize("rotation", [45, 89, 91])
def test_unsupported_watermark_rotation(rotation: int) -> None:
    """Model rejects other rotations."""
    with pytest.raises(ValueError):
        WatermarkOptions(text="TEST", rotation=rotation)


def test_files_index_and_slice_return_underlying_items() -> None:
    """Integer indexing returns File; slicing returns a sequence of File."""
    first = File(path="first.pdf")
    second = File(path="second.pdf")
    files = Files([first, second])

    assert files[0] == first
    assert files[:1] == [first]
    assert not isinstance(files[:1], Files)
