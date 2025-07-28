"""Word → PDF conversion (skipped if LibreOffice absent)."""

from __future__ import annotations

from pathlib import Path

import pytest

from pdf_tools.convert.service import convert_word_to_pdf
from pdf_tools.convert.unoserver_ctx import unoserver_listener
from pdf_tools.models.files import File
from tests.conftest import libreoffice_available


@pytest.mark.skipif(
    not libreoffice_available, reason="LibreOffice CLI not found"
)
@pytest.mark.slow
def test_docx_conversion(tmp_path: Path) -> None:
    """DOCX converts without error."""

    def _dummy_docx(path: Path) -> None:
        """Write an empty ZIP file so DocxTemplate accepts the path."""
        path.write_bytes(b"PK\x05\x06" + b"\x00" * 18)

    _dummy_docx(src := tmp_path / "sample.docx")

    out = tmp_path / "out.pdf"
    with unoserver_listener():
        pdf_file = convert_word_to_pdf(file=File(path=src), output_path=out)
    assert pdf_file.path.exists()
