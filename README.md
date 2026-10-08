# pdf-tools

Tools for converting documents to PDF, merging PDFs, and adding text watermarks.
The Python package is `pdf-toolchest`; the installed command is `pdf-tools`.

## Supported operations

| Operation | Inputs | Behavior |
| --- | --- | --- |
| Convert | Images with `.jpg`, `.jpeg`, `.png`, `.tiff`, or `.bmp` extensions; Word `.doc` and `.docx` files | Pillow validates images and PDF Oxide creates their PDFs. TIFF, BMP, and non-RGB images are normalized to PNG first. Word files retain LibreOffice, `unoserver`, and `unoconvert`. |
| Merge | PDFs | PDF Oxide merges PDFs. Non-PDF inputs are skipped with a warning. Optional bookmarks use `File.bookmark_name`, falling back to the filename. pypdf temporarily writes the outline entries. |
| Process | Supported conversion inputs and existing PDFs | Converts what it can, then merges the successful conversions and existing PDFs. |
| Watermark | PDF | Adds text with open-source ReportLab and pypdf. Rotation must be a multiple of 90 degrees. |

## Installation

```bash
pip install pdf-toolchest
pdf-tools --help
```

Word conversion requires LibreOffice and working `unoserver`/`unoconvert` executables with UNO bindings. PDF Oxide 0.3.78's Python DOCX converter did not complete on valid test files, so the original Word converter remains in place.

```bash
pipx install unoserver --system-site-packages
```

CLI commands start and stop a listener for Word inputs. Direct Python calls need an existing listener or the `unoserver_listener` context manager.

## CLI quick start

Output parent directories must already exist. Commands do not create them. In this example, `out/` is created before conversion; the other outputs are written to the current directory.

```bash
# Convert one Word file beside its source
pdf-tools convert file-to-pdf draft.docx

# Convert immediate children of a folder into an existing output directory
mkdir -p out
pdf-tools convert folder-to-pdfs assets/ --output-dir out/

# Merge selected PDFs in the given order
pdf-tools merge pdf-files a.pdf b.pdf c.pdf -o merged.pdf

# Merge PDFs found in a folder
pdf-tools merge pdfs-in-folder scans/ -o merged.pdf

# Convert images and Word files, then merge the successful inputs
pdf-tools process convert-and-merge-pdfs image1.jpg doc1.docx doc2.docx -o final.pdf

# Add a red DRAFT watermark on every page
pdf-tools watermark add-text src.pdf stamped.pdf \
    --text "DRAFT" --color "#FF0000" --font-size 72 --opacity 0.2 --rotation 90
```

Watermark rotation must be a multiple of 90 degrees (for example, `0`, `90`, `180`, or `270`). `--rotation 45` fails model validation.

`merge pdfs-in-folder` uses the filesystem's directory enumeration order. Alphabetical order is not guaranteed; pass files explicitly to `merge pdf-files` in the desired sequence when order matters.

Batch conversion continues after an individual input fails. `convert files-to-pdfs` and `convert folder-to-pdfs` print a reason for each skipped file and a converted/skipped count. They exit successfully if at least one file converted, even when others were skipped; they exit with code 1 when none converted. A missing output directory makes each attempted conversion fail and appear in the skipped results.

`process convert-and-merge-pdfs` is **best-effort**: an input that cannot be converted is omitted, while successful conversions and existing PDFs may still be merged. The output can contain fewer documents than requested. The process CLI does not list omitted inputs. If every input fails, no merge is written. For all-or-nothing work, run conversion separately, inspect every result, and merge only after all required inputs succeeded.

## Python API

Common APIs are exported from `pdf_tools`. Their accepted input types vary by operation:

| Operation | Accepted input types |
| --- | --- |
| Single-file conversion (`convert_file_to_pdf`, `convert_image_to_pdf`, `convert_word_to_pdf`) | `File`, `str`, or `Path` |
| Batch conversion (`convert_files_to_pdfs`) | `Files` or a sequence of `File`, `str`, or `Path` |
| Folder conversion (`convert_folder_to_pdfs`) | Directory as `str` or `Path` |
| Merge (`merge_pdfs`) and process (`convert_and_merge_pdfs`) | `Files` or a sequence of `File`, `str`, or `Path` |
| Watermark (`add_text_watermark`) | Source and destination as `str` or `Path`; options as `WatermarkOptions` |

The destination's parent directory must exist for single-file conversion, merging, and processing. Single-file conversion and merging raise `FileNotFoundError` for a missing output parent. Batch conversion records that error in `ConversionBatchResult.skipped` for each affected input. Processing raises `FileNotFoundError` at merge time if at least one input was retained; if none were retained, it raises `ValueError` instead.

```python
from pathlib import Path
from pdf_tools import WatermarkOptions, add_text_watermark, convert_file_to_pdf, merge_pdfs

Path("out").mkdir(exist_ok=True)
img_pdf = convert_file_to_pdf("diagram.png", output_path=Path("out"))
merged = merge_pdfs(["intro.pdf", img_pdf.path], output_path="bundle.pdf", set_bookmarks=True)
add_text_watermark(
    src=merged.path,
    dst="bundle_wm.pdf",
    opts=WatermarkOptions(text="CONFIDENTIAL", font_size=36, all_pages=False),
)
```

Batch conversion returns `ConversionBatchResult`: `converted` contains `File` models for successful PDFs; `skipped` contains each failed input path and its reason. It continues after a failed input and can return both lists populated.

```python
from pathlib import Path
from pdf_tools import convert_files_to_pdfs

Path("out").mkdir(exist_ok=True)
result = convert_files_to_pdfs(["photo.jpg", "notes.txt"], output_dir="out")
print(result.converted)
print(result.skipped)
```

Direct Python service calls involving Word files need a listener:

```python
from pdf_tools import convert_and_merge_pdfs, unoserver_listener

with unoserver_listener():
    convert_and_merge_pdfs(
        files=["doc1.docx", "pic.jpg", "appendix.pdf"],
        output_path="package.pdf",
    )
```

## Architecture

- **Models:** Pydantic v2 models describe inputs, options, and results.
- **Services:** Synchronous Python functions perform conversion, merging, processing, and watermarking.
- **CLI:** Typer commands parse arguments, print results, and manage CLI-specific resources.
- **PDF backend:** PDF Oxide creates image PDFs and merges PDFs. pypdf writes merge outline entries and places ReportLab text overlays for watermarks. The pinned PDF Oxide Python binding lacks equivalent styled watermark controls.
- **External tools:** LibreOffice with `unoserver` and `unoconvert` performs `.doc` and `.docx` conversion during the DOCX compatibility gap.

`unoserver_listener` remains a functional context manager for existing callers.

CLI setup and resource behavior can differ from direct service-layer calls.

## Development

```bash
git clone https://github.com/aswann45/pdf-tools.git
cd pdf-tools
poetry install --with dev
```

On Unix-like systems, `scripts/lint` is a Bash convenience wrapper. Run `poetry run bash scripts/lint` and `poetry run pytest`. The wrapper runs Mypy on `pdf_tools` and `tests`, Ruff lint on both directories with `ERA001` and `FIX002` ignored, and Ruff format checks on both directories.

On Windows, run the underlying commands in PowerShell. The Mypy configuration names `.venv/bin/python`, so override that Unix path with Poetry's environment interpreter:

```powershell
$venvPython = poetry env info --executable
poetry run mypy --python-executable $venvPython pdf_tools
poetry run mypy --python-executable $venvPython tests
poetry run ruff check pdf_tools --ignore ERA001 --ignore FIX002
poetry run ruff check tests --ignore ERA001 --ignore FIX002
poetry run ruff format pdf_tools --check
poetry run ruff format tests --check
poetry run pytest
```

The formatting check is `ruff format --check`; `scripts/format` applies formatting on Unix-like systems. Word-conversion tests marked `slow` require LibreOffice and working `uno` bindings.
