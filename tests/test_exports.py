"""Public import surface tests."""

from __future__ import annotations


def test_top_level_exports() -> None:
    """Common APIs are importable from the package root."""
    from pdf_tools import (  # noqa: PLC0415
        File,
        WatermarkOptions,
        add_text_watermark,
        convert_file_to_pdf,
        convert_files_to_pdfs,
        merge_pdfs,
    )

    assert File is not None
    assert WatermarkOptions is not None
    assert add_text_watermark is not None
    assert convert_file_to_pdf is not None
    assert convert_files_to_pdfs is not None
    assert merge_pdfs is not None


def test_watermark_package_exports() -> None:
    """Watermark APIs are importable from the feature package."""
    from pdf_tools.watermark import (  # noqa: PLC0415
        WatermarkOptions,
        add_text_watermark,
    )

    assert WatermarkOptions is not None
    assert add_text_watermark is not None
