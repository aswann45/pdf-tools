# pdf-tools

*A Swiss-army knife for everyday PDF workflows – pure-Python, cross-platform, and fully typed.*

---

## Features

| Capability | Sub-command / API | Notes |
|------------|------------------|-------|
| **Convert** images (`.png`, `.jpg`, …) or Word (`.docx`) to PDF | `pdf-tools convert …` <br>`pdf_tools.convert.service.convert_file_to_pdf()` | Uses **Pillow + img2pdf** for images and **LibreOffice / unoserver** for Word files. |
| **Merge** multiple PDFs (or whole folders) | `pdf-tools merge …` <br>`pdf_tools.merge.service.merge_pdfs()` | Preserves bookmarks; skips non-PDF inputs with a warning. |
| **Process** = Convert **→** Merge in one go | `pdf-tools process convert-and-merge …` | Handy for ad-hoc batches of mixed file types. |
| **Watermark** (text stamp) | `pdf-tools watermark add-text …` <br>`pdf_tools.watermark.service.add_text_watermark()` | PyMuPDF in-place editing; configurable font, colour, opacity, rotation, position. |
| **Async-friendly CLI** | Built on Typer + custom `AsyncTyper` | Callbacks can be `async def` – future-proof for parallel work. |
| **Pydantic v2 models** | `File`, `Files`, `WatermarkOptions`, … | JSON-serialisable contracts for easy automation. |
| **Fully typed** + Ruff + Mypy + pytest + hypothesis |   | CI fails on lint, type, docs, or test issues. |

---

## Installation

```bash
pip install pdf-tools[full]               # everything
# or choose extras:
pip install pdf-tools[convert]            # +Pillow, img2pdf, unoserver
pip install pdf-tools[watermark]          # +PyMuPDF
```

External dependency: LibreOffice must be installed and on your $PATH for Word→PDF conversion.

On Linux it “just works”. On macOS/Windows either:

1) use the bundled python that ships with LibreOffice, or
2) call soffice --headless directly (see Batch listeners below).

## CLI Quick Start

```bash
# 1. Convert a single Word file
pdf-tools convert file-to-pdf draft.docx draft.pdf

# 2. Convert every image in a folder → PDFs in ./out
pdf-tools convert folder-to-pdfs assets/ --output-dir out/

# 3. Merge selected PDFs (output first!)
pdf-tools merge pdf-files merged.pdf a.pdf b.pdf c.pdf

# 4. Merge *all* PDFs in a folder
pdf-tools merge pdfs-in-folder merged.pdf scans/

# 5. One-liner: convert images + docs → merge
pdf-tools process convert-and-merge final.pdf image1.jpg doc1.docx doc2.docx

# 6. Add a diagonal red DRAFT watermark on every page
pdf-tools watermark add-text src.pdf stamped.pdf \
    --text "DRAFT" --color "#FF0000" --font-size 72 --opacity 0.2 --rotation 45
```

###  Batch LibreOffice Listener (faster)

```bash
# spin up a listener for the whole session (Linux)
unoserver --interface 127.0.0.1 --port 2002 &
export LIBRE_PORT=2002   # used by convert helpers
pdf-tools process convert-and-merge ...
kill %1                  # when done
```

## Using the Python API

```python
from pathlib import Path
from pdf_tools.convert.service import convert_file_to_pdf
from pdf_tools.merge.service import merge_pdfs
from pdf_tools.watermark.models import WatermarkOptions
from pdf_tools.watermark.service import add_text_watermark

# 1. Convert
img_pdf = convert_file_to_pdf(
    input_path=Path("diagram.png"),
    output_dir=Path("out"),
)

# 2. Merge two PDFs
merge_pdfs(
    input_paths=[Path("intro.pdf"), img_pdf.path],
    output_path=Path("bundle.pdf"),
)

# 3. Watermark (first page only)
opts = WatermarkOptions(text="CONFIDENTIAL", font_size=36, all_pages=False)
add_text_watermark(src=Path("bundle.pdf"), dst=Path("bundle_wm.pdf"), opts=opts)
```

### Spinning up transient LibreOffice listener
```python
from pdf_tools.libreoffice.unoserver_ctx import unoserver_listener
from pdf_tools.process.service import convert_and_merge_pdfs

with unoserver_listener(port=2002):            # starts & auto-kills unoserver
    convert_and_merge_pdfs(
        input_paths=[Path("doc1.docx"), Path("pic.jpg")],
        output_path=Path("package.pdf"),
    )
```

## Development setup

```bash
git clone https://github.com/your-org/pdf-tools.git
cd pdf-tools
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,full]"   # tox, pytest, ruff, mypy, etc.

# Run checks
ruff check .
mypy .
pytest -q
mkdocs serve
```
