"""Image → PDF conversion round-trip."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from typing import Final

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image

from pdf_tools.convert.service import convert_file_to_pdf
from pdf_tools.convert.unoserver_ctx import unoserver_listener
from pdf_tools.models.files import File


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    width=st.integers(min_value=50, max_value=500),
    height=st.integers(min_value=50, max_value=500),
    unique_filename=st.uuids().map(str),
)
def test_png_to_pdf(
    tmp_path: Path, width: int, height: int, unique_filename: str
) -> None:
    """Converted PDF exists and is non-empty."""
    img_path = tmp_path / f"{unique_filename}.png"
    Image.new("RGB", (width, height), (255, 0, 0)).save(img_path)

    pdf_file = convert_file_to_pdf(
        file=File(path=img_path), output_path=tmp_path
    )
    assert pdf_file.path.stat().st_size > 0
    pdf_file.path.unlink()  # cleanup
    Path(img_path).unlink()


def test_unsupported_format(tmp_path: Path) -> None:
    """GIF raises ValueError (per docstring)."""
    gif = tmp_path / "bad.gif"
    Image.new("RGB", (50, 50)).save(gif, format="GIF")
    with pytest.raises(ValueError):
        convert_file_to_pdf(file=File(path=gif), output_path=tmp_path)


SERVICE_PATH: Final = (
    Path(__file__).resolve().parents[1]
    / "pdf_tools"
    / "convert"
    / "service.py"
)
spec = importlib.util.spec_from_file_location(
    "pdf_tools.convert.service", SERVICE_PATH
)
assert spec is not None
service = importlib.util.module_from_spec(spec)
sys.modules["pdf_tools.convert.service"] = service
assert spec.loader is not None
spec.loader.exec_module(service)


@pytest.fixture()
def tmp_image(tmp_path: Path) -> File:
    """Return a simple 10×10 PNG wrapped in File."""
    img_path = tmp_path / "tiny.png"
    Image.new("RGBA", (10, 10), (255, 0, 0)).save(img_path)
    return File(path=img_path)


@pytest.fixture()
def stub_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace subprocess.run with a no-op success response."""
    monkeypatch.setattr(
        service.subprocess,
        "run",
        lambda *a, **kw: types.SimpleNamespace(returncode=0),
    )


def test_output_dir_handler(tmp_path: Path) -> None:
    """Helper resolves file name."""
    input_path = tmp_path / "demo.docx"
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    result = service._output_dir_handler(input_path, output_dir)
    assert (
        result == output_dir / "demo.pdf"
    )  # lines 72-73 :contentReference[oaicite:0]{index=0}


@pytest.mark.slow
def test_word_directory_output(tmp_path: Path, stub_subprocess: None) -> None:
    """Line 116 ― directory → proper filename.pdf."""
    src = tmp_path / "x.docx"
    src.touch()
    out_dir = tmp_path / "export"
    out_dir.mkdir()

    with unoserver_listener():
        result = service.convert_word_to_pdf(
            File(path=src), output_path=out_dir, overwrite=True
        )
    assert result.path == out_dir / "x.pdf"  # covers 116


@pytest.mark.slow
def test_word_default_path(tmp_path: Path, stub_subprocess: None) -> None:
    """Line 121 ― ``output_path=None``."""
    src = tmp_path / "y.docx"
    src.touch()
    with unoserver_listener():
        result = service.convert_word_to_pdf(File(path=src), overwrite=True)
    assert result.path == src.with_suffix(".pdf")  # covers 121


@pytest.mark.slow
def test_word_file_exists(tmp_path: Path, stub_subprocess: None) -> None:
    """Line 124 ― existing PDF raises FileExistsError."""
    src = tmp_path / "z.docx"
    pdf = src.with_suffix(".pdf")
    src.touch()
    pdf.touch()

    with pytest.raises(FileExistsError):
        with unoserver_listener():
            service.convert_word_to_pdf(File(path=src))


@pytest.mark.slow
def test_word_output_is_directory(
    tmp_path: Path, stub_subprocess: None
) -> None:
    """Line 126 ― path resolves to an existing directory."""
    src = tmp_path / "a.docx"
    src.touch()
    dir_path = tmp_path / "a.pdf"
    dir_path.mkdir()

    with pytest.raises(ValueError):
        with unoserver_listener():
            service.convert_word_to_pdf(
                File(path=src), output_path=dir_path, overwrite=True
            )


@pytest.mark.slow
def test_word_parent_missing(tmp_path: Path, stub_subprocess: None) -> None:
    """Line 128 ― parent directory does not exist."""
    src = tmp_path / "b.docx"
    src.touch()
    out_path = tmp_path / "nope" / "b.pdf"

    with pytest.raises(FileNotFoundError):
        with unoserver_listener():
            service.convert_word_to_pdf(File(path=src), output_path=out_path)


@pytest.mark.slow
def test_word_subprocess_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lines 142-143 ― LibreOffice (subprocess) fails."""
    src = tmp_path / "c.docx"
    src.touch()

    def boom(*_a, **_kw) -> None:  # noqa: D401
        raise service.subprocess.CalledProcessError(
            1, "unoconvert", b"", b"err"
        )

    monkeypatch.setattr(service.subprocess, "run", boom)

    with pytest.raises(RuntimeError):
        with unoserver_listener():
            service.convert_word_to_pdf(File(path=src), overwrite=True)


def test_image_directory_output(tmp_image: File, tmp_path: Path) -> None:
    """Lines 194-198 ― directory path resolution."""
    out_dir = tmp_path / "exports"
    out_dir.mkdir()
    result = service.convert_image_to_pdf(
        tmp_image, output_path=out_dir, overwrite=True
    )
    assert result.path == out_dir / "tiny.pdf"


def test_image_file_exists(tmp_image: File) -> None:
    """Line 201 ― refuses to overwrite unless ``overwrite=True``."""
    pdf_path = tmp_image.path.with_suffix(".pdf")
    pdf_path.touch()
    with pytest.raises(FileExistsError):
        service.convert_image_to_pdf(tmp_image)


def test_image_output_is_directory(tmp_image: File, tmp_path: Path) -> None:
    """Line 203 ― path points at an existing directory."""
    dir_path = tmp_path / "weird.pdf"
    dir_path.mkdir()
    with pytest.raises(ValueError):
        service.convert_image_to_pdf(
            tmp_image, output_path=dir_path, overwrite=True
        )


def test_image_parent_missing(tmp_image: File, tmp_path: Path) -> None:
    """Line 205 ― parent folder absent."""
    missing = tmp_path / "nowhere" / "img.pdf"
    with pytest.raises(FileNotFoundError):
        service.convert_image_to_pdf(tmp_image, output_path=missing)


def test_image_unsupported_format(tmp_path: Path) -> None:
    """Lines 212 & 224-225 ― unsupported GIF → RuntimeError."""
    bad_img = tmp_path / "bad.gif"
    Image.new("RGBA", (10, 10)).save(bad_img, "GIF")

    with pytest.raises(RuntimeError):
        service.convert_image_to_pdf(File(path=bad_img), overwrite=True)


def test_image_rgb_conversion(
    tmp_image: File, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Line 218 ― non-RGB images are converted to RGB."""
    called = {"converted": False}

    def _convert(self, *args, **kwargs):  # type: ignore[no-self-use]
        called["converted"] = True
        return orig_convert(self, *args, **kwargs)

    orig_convert = Image.Image.convert  # backup original
    monkeypatch.setattr(Image.Image, "convert", _convert, raising=True)

    service.convert_image_to_pdf(tmp_image, overwrite=True)
    assert called["converted"] is True


@pytest.mark.slow
def test_dispatch_to_word(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Line 265 ― dispatches *.doc* files to `convert_word_to_pdf`."""
    sentinel = object()

    def _fake(*_a, **_kw):
        return sentinel

    monkeypatch.setattr(service, "convert_word_to_pdf", _fake)
    doc = tmp_path / "whatever.doc"
    doc.touch()

    with unoserver_listener():
        assert service.convert_file_to_pdf(File(path=doc)) is sentinel
