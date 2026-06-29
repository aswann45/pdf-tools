# pdf-tools

*A Swiss-army knife for everyday PDF workflows - pure-Python, cross-platform, and fully typed.*

## Features

| Capability | Sub-command / API | Notes |
|------------|------------------|-------|
| **Convert** images (`.png`, `.jpg`, `.tiff`, `.bmp`, ...) or Word (`.doc`, `.docx`) to PDF | `pdf-tools convert ...` <br>`pdf_tools.convert_file_to_pdf()` | Uses Pillow + img2pdf for images and LibreOffice / unoserver for Word files. |
| **Merge** multiple PDFs or whole folders | `pdf-tools merge ...` <br>`pdf_tools.merge_pdfs()` | Preserves bookmarks; skips non-PDF inputs with a warning. |
| **Process** = convert then merge | `pdf-tools process convert-and-merge-pdfs ...` <br>`pdf_tools.convert_and_merge_pdfs()` | Converts supported inputs, passes existing PDFs through, and merges the result. |
| **Watermark** text stamps | `pdf-tools watermark add-text ...` <br>`pdf_tools.add_text_watermark()` | PyMuPDF-based text watermarking with configurable font, color, opacity, rotation, and position. |
| **Async-friendly CLI** | Built on Typer + `AsyncTyper` | CLI callbacks can be `async def`. |
| **Pydantic v2 models** | `File`, `Files`, `WatermarkOptions`, ... | JSON-serializable contracts for automation. |

## Installation

The published Python package is `pdf-toolchest`; the installed command is `pdf-tools`.

```bash
pip install pdf-toolchest
pdf-tools --help
```

Word conversion requires LibreOffice plus a working `unoserver` / `unoconvert` install. Install `unoserver` with the Python environment that can import LibreOffice's `uno` module; for many Linux setups this is:

```bash
pipx install unoserver --system-site-packages
```

## CLI Quick Start

```bash
# Convert a single Word file
pdf-tools convert file-to-pdf draft.docx

# Convert every supported file in a folder to PDFs in ./out
pdf-tools convert folder-to-pdfs assets/ --output-dir out/

# Merge selected PDFs
pdf-tools merge pdf-files a.pdf b.pdf c.pdf -o merged.pdf

# Merge all PDFs in a folder
pdf-tools merge pdfs-in-folder scans/ -o merged.pdf

# Convert images/docs and merge the PDFs
pdf-tools process convert-and-merge-pdfs image1.jpg doc1.docx doc2.docx -o final.pdf

# Add a diagonal red DRAFT watermark on every page
pdf-tools watermark add-text src.pdf stamped.pdf \
    --text "DRAFT" --color "#FF0000" --font-size 72 --opacity 0.2 --rotation 45
```

### Batch LibreOffice Listener

For repeated Word conversions, run one listener for the whole session. `--port` is the `unoconvert` XMLRPC port; `--uno-port` is the LibreOffice UNO port. Note that `unoserver` needs to have access to the `uno` package that ships with LibreOffice, so it needs to either be installed system-wide or, if using `pipx` for example, needs to have access to the system site packages.

```bash
unoserver --interface 127.0.0.1 --port 2003 --uno-port 2002 &
pdf-tools process convert-and-merge-pdfs doc1.docx doc2.docx -o final.pdf
kill %1
```

## Python API

Common APIs are exported from `pdf_tools`. Functions accept `str`, `Path`, or `File` inputs.

```python
from pathlib import Path
from pdf_tools import (
    WatermarkOptions,
    add_text_watermark,
    convert_file_to_pdf,
    merge_pdfs,
)

# Convert one image to out/diagram.pdf
img_pdf = convert_file_to_pdf("diagram.png", output_path=Path("out"))

# Merge PDFs
merged = merge_pdfs(
    ["intro.pdf", img_pdf.path],
    output_path="bundle.pdf",
    set_bookmarks=True,
)

# Watermark the first page
opts = WatermarkOptions(text="CONFIDENTIAL", font_size=36, all_pages=False)
add_text_watermark(src=merged.path, dst="bundle_wm.pdf", opts=opts)
```

Batch conversion returns structured information about converted and skipped files.

```python
from pdf_tools import convert_files_to_pdfs

result = convert_files_to_pdfs(["photo.jpg", "notes.txt"], output_dir="out")
print(result.converted)
print(result.skipped)
```

For Word conversion from Python, start a listener before calling conversion helpers.

```python
from pdf_tools import convert_and_merge_pdfs, unoserver_listener

with unoserver_listener():
    convert_and_merge_pdfs(
        files=["doc1.docx", "pic.jpg", "appendix.pdf"],
        output_path="package.pdf",
    )
```

## Development

```bash
git clone https://github.com/your-org/pdf-tools.git
cd pdf-tools
poetry install --with dev

scripts/lint
pytest -q -m "not slow"
```

Slow Word-conversion tests require LibreOffice and working `uno` bindings.
