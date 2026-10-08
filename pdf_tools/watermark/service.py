"""Service helpers for stamping text watermarks onto PDF pages."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from pdf_tools.models.files import File
from pdf_tools.models.watermark import WatermarkOptions, WatermarkResult

_FONT_ALIASES = {
    "helv": "Helvetica",
    "hebo": "Helvetica-Bold",
    "heit": "Helvetica-Oblique",
    "hebi": "Helvetica-BoldOblique",
    "cour": "Courier",
    "cobo": "Courier-Bold",
    "coit": "Courier-Oblique",
    "cobi": "Courier-BoldOblique",
    "tiro": "Times-Roman",
    "tibo": "Times-Bold",
    "tiit": "Times-Italic",
    "tibi": "Times-BoldItalic",
    "symb": "Symbol",
    "zadb": "ZapfDingbats",
}


def _font_name(name: str) -> str:
    """Translate MuPDF's built-in font aliases to ReportLab names."""
    return _FONT_ALIASES.get(name.lower(), name)


def _overlay_for_page(page: PageObject, opts: WatermarkOptions) -> PdfReader:
    """Create a one-page text overlay sized to the target PDF page."""
    width = float(page.cropbox.width)
    height = float(page.cropbox.height)
    center_x = opts.x if opts.x is not None else width / 2
    center_y = opts.y if opts.y is not None else height / 2
    font = _font_name(opts.font_name)
    # A quarter turn swaps the textbox axes used by insert_textbox.
    quarter_turn = opts.rotation % 180 != 0
    text_width = opts.box_height if quarter_turn else opts.box_width
    text_height = opts.box_width if quarter_turn else opts.box_height
    lines = simpleSplit(opts.text, font, opts.font_size, text_width)

    stream = BytesIO()
    drawing = canvas.Canvas(stream, pagesize=(width, height))
    drawing.setFont(font, opts.font_size)
    drawing.setFillColorRGB(*opts.color)
    drawing.setFillAlpha(opts.opacity)
    drawing.translate(center_x, height - center_y)
    drawing.rotate(opts.rotation)

    # Coordinates in WatermarkOptions have a top-left origin, as in PyMuPDF.
    top = text_height / 2
    line_step = opts.font_size * opts.lineheight
    for index, line in enumerate(lines):
        # Match the Helvetica ascender offset of the former PyMuPDF path.
        baseline = top - opts.font_size * 1.075 - index * line_step
        if baseline < -text_height / 2:
            break
        if opts.h_align == "left":
            x = -text_width / 2
        elif opts.h_align == "right":
            x = text_width / 2 - pdfmetrics.stringWidth(
                line, font, opts.font_size
            )
        else:
            x = -pdfmetrics.stringWidth(line, font, opts.font_size) / 2
        drawing.drawString(x, baseline, line)

    drawing.save()
    stream.seek(0)
    return PdfReader(stream)


def add_text_watermark(
    *,
    src: str | Path,
    dst: str | Path,
    opts: WatermarkOptions,
) -> WatermarkResult:
    """Stamp text onto a PDF using ReportLab and pypdf.

    Parameters
    ----------
    src : str | Path
        Input PDF path.
    dst : str | Path
        Output PDF path.
    opts : WatermarkOptions
        Styling and placement options.

    Returns
    -------
    WatermarkResult
        Metadata describing the operation.

    Raises
    ------
    ValueError
        If source and destination paths are the same.
    FileNotFoundError
        If the source or destination parent directory does not exist.
    OSError
        If the source cannot be read or the destination cannot be written.
    """
    src = Path(src)
    dst = Path(dst)
    if src == dst:
        raise ValueError("Source and destination paths must differ.")

    writer = PdfWriter(clone_from=src)
    page_count = len(writer.pages)
    pages_processed = page_count if opts.all_pages else 1
    for page in writer.pages[:pages_processed]:
        if page.rotation:
            page.transfer_rotation_to_content()
        overlay = _overlay_for_page(page, opts)
        placement = Transformation().translate(
            float(page.cropbox.left),
            float(page.cropbox.bottom),
        )
        page.merge_transformed_page(overlay.pages[0], placement)
    writer.write(dst)

    return WatermarkResult(
        output=File.model_validate({"path": dst}),
        pages_processed=pages_processed,
    )
