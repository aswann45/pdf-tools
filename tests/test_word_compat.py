"""Word conversion and functional unoserver listener checks."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from docx import Document
from pdf_oxide import PdfDocument

from pdf_tools import unoserver_listener
from pdf_tools.convert import service, unoserver_ctx
from pdf_tools.models.files import File


@pytest.mark.parametrize("extension", ["doc", "docx"])
def test_word_output_and_bookmark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    extension: str,
) -> None:
    """Word dispatch retains paths and bookmark metadata."""
    source = tmp_path / f"source.{extension}"
    source.touch()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(service, "assert_office_ready", lambda: None)

    def convert(command: list[str], **_: Any) -> None:
        calls.append(command)
        Path(command[2]).touch()

    monkeypatch.setattr(service.subprocess, "run", convert)
    result = service.convert_word_to_pdf(
        File(path=source, bookmark_name="Chapter"),
        output_path=output_dir,
    )

    assert calls == [
        ["unoconvert", str(source), str(output_dir / "source.pdf")]
    ]
    assert result.path == output_dir / "source.pdf"
    assert result.bookmark_name == "Chapter"


def test_word_output_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Word conversion preserves preflight path errors."""
    monkeypatch.setattr(service, "assert_office_ready", lambda: None)
    source = tmp_path / "source.docx"
    source.touch()
    existing = tmp_path / "existing.pdf"
    existing.touch()
    directory = tmp_path / "directory.pdf"
    directory.mkdir()

    with pytest.raises(FileExistsError):
        service.convert_word_to_pdf(source, existing)
    with pytest.raises(ValueError, match="is a directory"):
        service.convert_word_to_pdf(source, directory)
    with pytest.raises(FileNotFoundError):
        service.convert_word_to_pdf(source, tmp_path / "absent" / "out.pdf")


def test_listener_starts_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    """The public context manager still manages a real listener process."""
    events: list[str] = []

    class Process:
        def terminate(self) -> None:
            events.append("terminate")

        def wait(self, timeout: int) -> None:
            events.append("wait")

    monkeypatch.setattr(unoserver_ctx, "_UNOSERVER_CMD", "unoserver")
    monkeypatch.setattr(
        unoserver_ctx,
        "_wait_until_port_listens",
        lambda port, timeout: events.append("ready"),
    )
    monkeypatch.setattr(
        unoserver_ctx.subprocess,
        "Popen",
        lambda *args, **kwargs: Process(),
    )

    with unoserver_listener():
        events.append("body")

    assert events == ["ready", "body", "terminate", "wait"]


def test_listener_requires_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing unoserver executable is reported before startup."""
    monkeypatch.setattr(unoserver_ctx, "_UNOSERVER_CMD", None)
    with pytest.raises(FileNotFoundError, match="unoserver"):
        with unoserver_listener():
            pass


def test_word_requires_unoconvert(monkeypatch: pytest.MonkeyPatch) -> None:
    """A missing conversion executable retains its documented error."""
    monkeypatch.setattr(unoserver_ctx.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="unoconvert"):
        unoserver_ctx.assert_office_ready()


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("PDF_TOOLS_TEST_LIBREOFFICE") != "1"
    or shutil.which("soffice") is None
    or shutil.which("unoserver") is None
    or shutil.which("unoconvert") is None,
    reason="Set PDF_TOOLS_TEST_LIBREOFFICE=1 for Office integration",
)
def test_unoserver_docx(tmp_path: Path) -> None:
    """The original listener path converts a real DOCX fixture."""
    source = tmp_path / "source.docx"
    document = Document()
    document.add_paragraph("Word conversion")
    document.save(str(source))

    with unoserver_listener():
        result = service.convert_word_to_pdf(source)

    pdf = PdfDocument(str(result.path))
    assert "Word conversion" in pdf.extract_text(0)


@pytest.mark.slow
@pytest.mark.skipif(
    os.environ.get("PDF_TOOLS_TEST_LIBREOFFICE") != "1"
    or shutil.which("soffice") is None
    or shutil.which("unoserver") is None
    or shutil.which("unoconvert") is None,
    reason="Set PDF_TOOLS_TEST_LIBREOFFICE=1 for Office integration",
)
def test_unoserver_doc(tmp_path: Path) -> None:
    """Legacy binary DOC stays supported through the listener."""
    source_docx = tmp_path / "source.docx"
    document = Document()
    document.add_paragraph("Legacy Word conversion")
    document.save(str(source_docx))

    with TemporaryDirectory() as directory:
        profile = (Path(directory) / "profile").as_uri()
        subprocess.run(
            [
                "soffice",
                f"-env:UserInstallation={profile}",
                "--headless",
                "--convert-to",
                "doc",
                "--outdir",
                str(tmp_path),
                str(source_docx),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )

    with unoserver_listener():
        result = service.convert_word_to_pdf(tmp_path / "source.doc")

    pdf = PdfDocument(str(result.path))
    assert "Legacy Word conversion" in pdf.extract_text(0)
