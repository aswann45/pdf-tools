"""Image → PDF conversion round-trip."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image

from pdf_tools.convert import service
from pdf_tools.convert.service import convert_file_to_pdf
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


def test_pathlike_png_to_pdf(tmp_path: Path) -> None:
    """Path-like inputs are accepted directly."""
    img_path = tmp_path / "pathlike.png"
    Image.new("RGB", (50, 50), (255, 0, 0)).save(img_path)

    pdf_file = convert_file_to_pdf(file=img_path, output_path=tmp_path)
    assert pdf_file.path == tmp_path / "pathlike.pdf"
    assert pdf_file.path.stat().st_size > 0


@pytest.mark.parametrize(
    ("extension", "image_format"),
    [
        ("jpg", "JPEG"),
        ("jpeg", "JPEG"),
        ("png", "PNG"),
        ("tiff", "TIFF"),
        ("bmp", "BMP"),
    ],
)
def test_supported_image_formats_dispatch(
    tmp_path: Path, extension: str, image_format: str
) -> None:
    """Dispatcher routes all documented image formats."""
    img_path = tmp_path / f"supported.{extension}"
    Image.new("RGB", (50, 50), (255, 0, 0)).save(img_path, format=image_format)

    pdf_file = convert_file_to_pdf(file=img_path, output_path=tmp_path)
    assert pdf_file.path == tmp_path / "supported.pdf"
    assert pdf_file.path.stat().st_size > 0


@pytest.mark.parametrize(
    ("extension", "image_format"),
    [("gif", "GIF"), ("webp", "WEBP")],
)
def test_unsupported_format(
    tmp_path: Path, extension: str, image_format: str
) -> None:
    """Pillow-readable formats outside the allowlist are rejected."""
    image = tmp_path / f"bad.{extension}"
    Image.new("RGB", (50, 50)).save(image, format=image_format)
    with pytest.raises(ValueError, match="Unsupported file type"):
        convert_file_to_pdf(file=File(path=image), output_path=tmp_path)


@pytest.fixture()
def tmp_image(tmp_path: Path) -> File:
    """Return a simple 10×10 PNG wrapped in File."""
    img_path = tmp_path / "tiny.png"
    Image.new("RGBA", (10, 10), (255, 0, 0)).save(img_path)
    return File(path=img_path)


def test_output_dir_handler(tmp_path: Path) -> None:
    """Helper resolves file name."""
    input_path = tmp_path / "demo.docx"
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    result = service._output_dir_handler(input_path, output_dir)
    assert (
        result == output_dir / "demo.pdf"
    )  # lines 72-73 :contentReference[oaicite:0]{index=0}


def test_image_directory_output(tmp_image: File, tmp_path: Path) -> None:
    """Directory path resolution."""
    out_dir = tmp_path / "exports"
    out_dir.mkdir()
    result = service.convert_image_to_pdf(
        tmp_image, output_path=out_dir, overwrite=True
    )
    assert result.path == out_dir / "tiny.pdf"


def test_image_file_exists(tmp_image: File) -> None:
    """Refuses to overwrite unless ``overwrite=True``."""
    pdf_path = tmp_image.path.with_suffix(".pdf")
    pdf_path.touch()
    with pytest.raises(FileExistsError):
        service.convert_image_to_pdf(tmp_image)


def test_image_output_is_directory(tmp_image: File, tmp_path: Path) -> None:
    """Path points at an existing directory."""
    dir_path = tmp_path / "weird.pdf"
    dir_path.mkdir()
    with pytest.raises(ValueError):
        service.convert_image_to_pdf(
            tmp_image, output_path=dir_path, overwrite=True
        )


def test_image_parent_missing(tmp_image: File, tmp_path: Path) -> None:
    """Parent folder absent."""
    missing = tmp_path / "nowhere" / "img.pdf"
    with pytest.raises(FileNotFoundError):
        service.convert_image_to_pdf(tmp_image, output_path=missing)


def test_image_unsupported_format(tmp_path: Path) -> None:
    """Lines 212 & 224-225 ― unsupported GIF → RuntimeError."""
    bad_img = tmp_path / "bad.gif"
    Image.new("RGBA", (10, 10)).save(bad_img, "GIF")

    with pytest.raises(RuntimeError):
        service.convert_image_to_pdf(File(path=bad_img), overwrite=True)


def test_batch_conversion_reports_skipped_unsupported(
    tmp_path: Path,
) -> None:
    """Batch conversion keeps supported files and reports skipped inputs."""
    good_img = tmp_path / "good.png"
    bad_file = tmp_path / "bad.txt"
    Image.new("RGB", (10, 10)).save(good_img, "PNG")
    bad_file.write_text("not convertible")

    result = service.convert_files_to_pdfs(
        [good_img, bad_file],
        output_dir=tmp_path,
        overwrite=True,
    )

    assert [file.path for file in result.converted] == [tmp_path / "good.pdf"]
    assert len(result.skipped) == 1
    assert result.skipped[0].path == bad_file
    assert "Unsupported file type" in result.skipped[0].reason


def test_batch_conversion_reports_missing_output_directory(
    tmp_path: Path,
) -> None:
    """A missing output directory becomes a skipped batch result."""
    image = tmp_path / "image.png"
    Image.new("RGB", (10, 10)).save(image)

    result = service.convert_files_to_pdfs(
        [image], output_dir=tmp_path / "missing"
    )

    assert result.converted == []
    assert [item.path for item in result.skipped] == [image]
    assert "Output directory" in result.skipped[0].reason


def test_image_rgb_conversion(
    tmp_image: File, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-RGB images are converted to RGB."""
    called = {"converted": False}

    def _convert(self: Image.Image, *args: Any, **kwargs: Any) -> Image.Image:
        called["converted"] = True
        return orig_convert(self, *args, **kwargs)

    orig_convert = Image.Image.convert  # backup original
    monkeypatch.setattr(Image.Image, "convert", _convert, raising=True)

    service.convert_image_to_pdf(tmp_image, overwrite=True)
    assert called["converted"] is True
