"""Compatibility and behavior of the root API and PDFTools facade."""

import importlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, assert_type, cast, get_type_hints
from unittest.mock import MagicMock

import pytest
from hypothesis import given
from hypothesis import strategies as st

import pdf_tools
import pdf_tools.api as api_module
from pdf_tools import (
    DocumentExtraction,
    ExtractionOptions,
    File,
    FileInput,
    FilesInput,
    OcrMode,
    PDFTools,
    WatermarkOptions,
)
from pdf_tools.extract.exceptions import ExtractionError, OcrUnavailableError

OPERATIONS = (
    "convert_word_to_pdf",
    "convert_image_to_pdf",
    "convert_file_to_pdf",
    "convert_files_to_pdfs",
    "convert_folder_to_pdfs",
    "merge_pdfs",
    "convert_and_merge_pdfs",
    "add_text_watermark",
    "extract_pdf",
    "extract_pdf_text",
    "extract_pdf_images",
)

COMPONENTS = {
    "convert_word_to_pdf": "convert",
    "convert_image_to_pdf": "convert",
    "convert_file_to_pdf": "convert",
    "convert_files_to_pdfs": "convert",
    "convert_folder_to_pdfs": "convert",
    "merge_pdfs": "merge",
    "convert_and_merge_pdfs": "process",
    "add_text_watermark": "watermark",
    "extract_pdf": "extract",
    "extract_pdf_text": "extract",
    "extract_pdf_images": "extract",
}


@pytest.fixture(scope="module")
def baseline() -> dict[str, Any]:
    """Load the manifest captured before any production API edits."""
    path = Path(__file__).parent / "data" / "api_v0_4_0_baseline.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def test_root_exports_preserve_baseline(baseline: dict[str, Any]) -> None:
    """Existing root and component exports retain their identities."""
    assert baseline["version"] == "0.4.0"
    assert baseline["commit"] == "121ab41f777bb7ba97ee09a89e4063ac2347c9a4"
    assert set(baseline["exports"]) <= set(pdf_tools.__all__)
    assert {"PDFTools", "FileInput", "FilesInput"} <= set(pdf_tools.__all__)
    assert len(pdf_tools.__all__) == len(set(pdf_tools.__all__))
    assert all(hasattr(pdf_tools, name) for name in pdf_tools.__all__)
    namespace: dict[str, object] = {}
    exec("from pdf_tools import *", namespace)
    assert set(pdf_tools.__all__) <= set(namespace)
    assert pdf_tools.FileInput == FileInput
    assert pdf_tools.FilesInput == FilesInput
    assert pdf_tools.PDFTools is PDFTools
    assert api_module.__all__ == ["PDFTools"]
    for module_name, exports in baseline["module_exports"].items():
        module = importlib.import_module(module_name)
        assert list(module.__all__) == exports
    for name, component in COMPONENTS.items():
        module = importlib.import_module(f"pdf_tools.{component}")
        service = importlib.import_module(f"pdf_tools.{component}.service")
        assert getattr(pdf_tools, name) is getattr(module, name)
        assert getattr(module, name) is getattr(service, name)
    assert pdf_tools.ExtractionError is ExtractionError
    assert pdf_tools.OcrUnavailableError is OcrUnavailableError
    assert pdf_tools.File is File


@pytest.mark.parametrize("name", OPERATIONS)
def test_signatures_match_baseline_and_facade(
    name: str, baseline: dict[str, Any]
) -> None:
    """Service signatures remain frozen and bound methods mirror them."""
    service = getattr(pdf_tools, name)
    method = getattr(PDFTools(), name)
    expected = baseline["service_signatures"][name]
    assert str(inspect.signature(service)) == expected
    assert service.__module__ == baseline["function_modules"][name]
    assert (
        repr(inspect.signature(service).return_annotation)
        == (baseline["return_annotations"][name])
    )
    service_sig = inspect.signature(service)
    method_sig = inspect.signature(method)
    assert list(method_sig.parameters) == list(service_sig.parameters)
    for service_arg, method_arg in zip(
        service_sig.parameters.values(),
        method_sig.parameters.values(),
        strict=True,
    ):
        assert service_arg.kind == method_arg.kind
        assert service_arg.default == method_arg.default
    assert get_type_hints(method) == get_type_hints(service)
    assert not inspect.iscoroutinefunction(method)


def test_keyword_only_arguments_are_preserved() -> None:
    """Watermark and extraction keyword-only boundaries remain enforced."""
    tools = PDFTools()
    with pytest.raises(TypeError):
        cast(Any, tools.add_text_watermark)(
            "a.pdf", "b.pdf", WatermarkOptions(text="x")
        )
    with pytest.raises(TypeError):
        cast(Any, tools.extract_pdf_text)("a.pdf", OcrMode.NEVER)
    with pytest.raises(TypeError):
        cast(Any, tools.extract_pdf_images)("a.pdf", "out", [1])
    with pytest.raises(TypeError):
        cast(Any, tools.extract_pdf)("a.pdf", None, "out")


@pytest.mark.parametrize(
    ("name", "args", "kwargs", "expected_args", "expected_kwargs"),
    [
        (
            "convert_word_to_pdf",
            ("a.docx",),
            {},
            ("a.docx", None),
            {"overwrite": False},
        ),
        (
            "convert_image_to_pdf",
            (Path("a.png"),),
            {"output_path": None, "overwrite": True},
            (Path("a.png"), None),
            {"overwrite": True},
        ),
        (
            "convert_file_to_pdf",
            ("a.png", "out.pdf"),
            {},
            ("a.png", "out.pdf"),
            {"overwrite": False},
        ),
        (
            "convert_files_to_pdfs",
            (["a.png"],),
            {},
            (["a.png"], None),
            {"overwrite": False},
        ),
        (
            "convert_folder_to_pdfs",
            (Path("images"),),
            {},
            (Path("images"), None),
            {"overwrite": False},
        ),
        (
            "merge_pdfs",
            (["a.pdf"], Path("out.pdf")),
            {},
            (["a.pdf"], Path("out.pdf"), False),
            {"overwrite": False},
        ),
        (
            "convert_and_merge_pdfs",
            (["a.pdf"], "out.pdf"),
            {"set_bookmarks": True},
            (["a.pdf"], "out.pdf", True),
            {"overwrite": False},
        ),
        (
            "add_text_watermark",
            (),
            {
                "src": "a.pdf",
                "dst": "b.pdf",
                "opts": WatermarkOptions(text="X"),
            },
            (),
            {
                "src": "a.pdf",
                "dst": "b.pdf",
                "opts": WatermarkOptions(text="X"),
            },
        ),
        (
            "extract_pdf",
            ("a.pdf",),
            {},
            ("a.pdf", None),
            {"image_output_dir": None, "overwrite": False},
        ),
        (
            "extract_pdf_text",
            ("a.pdf",),
            {"ocr": OcrMode.AUTO, "pages": [2]},
            ("a.pdf",),
            {"ocr": OcrMode.AUTO, "pages": [2]},
        ),
        (
            "extract_pdf_images",
            ("a.pdf", Path("images")),
            {"pages": None, "overwrite": True},
            ("a.pdf", Path("images")),
            {"pages": None, "overwrite": True},
        ),
    ],
)
def test_delegates_once_and_preserves_result(
    name: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
    expected_args: tuple[object, ...],
    expected_kwargs: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every method forwards to exactly one service call without wrapping."""
    result = object()
    dependency = MagicMock(return_value=result)
    monkeypatch.setattr(api_module, f"_{name}", dependency)
    assert getattr(PDFTools(), name)(*args, **kwargs) is result
    dependency.assert_called_once_with(*expected_args, **expected_kwargs)


@pytest.mark.parametrize("name", OPERATIONS)
def test_exception_instance_propagates(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The facade neither catches nor replaces service exceptions."""
    sentinel = RuntimeError("sentinel")
    dependency = MagicMock(side_effect=sentinel)
    monkeypatch.setattr(api_module, f"_{name}", dependency)
    signature = inspect.signature(getattr(PDFTools(), name))
    kwargs = {
        parameter.name: object()
        for parameter in signature.parameters.values()
        if parameter.default is inspect.Parameter.empty
    }
    with pytest.raises(RuntimeError) as caught:
        getattr(PDFTools(), name)(**kwargs)
    assert caught.value is sentinel
    dependency.assert_called_once()


def test_construction_does_not_probe_external_services(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Construction and method access leave resources untouched."""
    probe = MagicMock(side_effect=AssertionError("external work"))
    monkeypatch.setattr(api_module, "_convert_word_to_pdf", probe)
    monkeypatch.setattr(api_module, "_extract_pdf", probe)
    before = list(tmp_path.iterdir())
    tools = PDFTools()
    assert tools.__dict__ == {}
    assert callable(tools.convert_word_to_pdf)
    assert callable(tools.extract_pdf)
    assert list(tmp_path.iterdir()) == before
    probe.assert_not_called()


def test_fresh_import_needs_no_optional_services() -> None:
    """A fresh process can import and construct the facade immediately."""
    command = [
        sys.executable,
        "-c",
        "from pdf_tools import PDFTools; assert PDFTools().__dict__ == {}",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_argument_objects_are_forwarded_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The facade does not copy options or caller-owned sequences."""
    files = ["a.pdf", "b.pdf"]
    pages = [2, 1]
    options = ExtractionOptions(ocr=OcrMode.NEVER, pages=pages)
    merge = MagicMock(return_value=object())
    extract = MagicMock(return_value=object())
    images = MagicMock(return_value=object())
    monkeypatch.setattr(api_module, "_merge_pdfs", merge)
    monkeypatch.setattr(api_module, "_extract_pdf", extract)
    monkeypatch.setattr(api_module, "_extract_pdf_images", images)
    tools = PDFTools()
    tools.merge_pdfs(files, "out.pdf")
    tools.extract_pdf("a.pdf", options)
    tools.extract_pdf_images("a.pdf", "out", pages=pages)
    assert merge.call_args.args[0] is files
    assert extract.call_args.args[1] is options
    assert images.call_args.kwargs["pages"] is pages
    assert files == ["a.pdf", "b.pdf"]
    assert pages == [2, 1]


@given(st.text(alphabet="abcxyz", min_size=1, max_size=8))
def test_path_representation_forwarding(name: str) -> None:
    """Path and string inputs both reach the same conversion dependency."""
    for source in (name + ".png", Path(name + ".png")):
        dependency = MagicMock(return_value=object())
        from pytest import MonkeyPatch

        with MonkeyPatch.context() as patch:
            patch.setattr(api_module, "_convert_file_to_pdf", dependency)
            PDFTools().convert_file_to_pdf(source)
        assert dependency.call_args.args[0] is source


if TYPE_CHECKING:
    from pdf_tools import (
        ConversionBatchResult,
        DocumentExtraction,
        File,
        WatermarkResult,
        convert_file_to_pdf,
        extract_pdf_text,
    )

    facade = PDFTools()
    assert_type(facade.convert_file_to_pdf("a.png"), File)
    assert_type(convert_file_to_pdf("a.png"), File)
    assert_type(facade.convert_files_to_pdfs(["a.png"]), ConversionBatchResult)
    assert_type(facade.merge_pdfs(["a.pdf"], "out.pdf"), File)
    assert_type(
        facade.add_text_watermark(
            src="a.pdf", dst="b.pdf", opts=WatermarkOptions(text="X")
        ),
        WatermarkResult,
    )
    assert_type(facade.extract_pdf_text("a.pdf"), DocumentExtraction)
    assert_type(extract_pdf_text("a.pdf"), DocumentExtraction)
