"""Service helpers for stamping text watermarks onto PDF pages."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pymupdf  # type: ignore[import-untyped]

from pdf_tools.models.files import File
from pdf_tools.models.watermark import WatermarkOptions, WatermarkResult


def _iter_target_pages(
    doc: pymupdf.Document, *, all_pages: bool
) -> Iterable[pymupdf.Page]:
    return doc if all_pages else [doc[0]]  # first page only


def add_text_watermark(
    *,
    src: Path,
    dst: Path,
    opts: WatermarkOptions,
) -> WatermarkResult:
    """Stamp *text* onto a PDF using PyMuPDF.

    Parameters
    ----------
    src, dst
        Input and output PDF paths.
    opts
        Styling & placement options; see
        :class:`~pdf_tools.watermark.models.WatermarkOptions`.

    Returns
    -------
    WatermarkResult
        Metadata describing the operation.  Raises on error.
    """
    if src == dst:
        raise ValueError("Source and destination paths must differ.")

    with pymupdf.open(src) as doc:
        # Prepare placement defaults ------------------------------------------
        for page in _iter_target_pages(doc, all_pages=opts.all_pages):
            bbox = page.rect  # full page rectangle
            x = opts.x if opts.x is not None else bbox.width / 2
            y = opts.y if opts.y is not None else bbox.height / 2

            page.insert_text(
                (x, y),
                opts.text,
                fontname=opts.font_name,
                fontsize=opts.font_size,
                rotate=opts.rotation,
                color=opts.color,  # validated to (r,g,b)
                fill_opacity=opts.opacity,
                render_mode=0,  # fill text
                align=1,  # centre on (x,y)
            )

        doc.save(dst, deflate=True)

    return WatermarkResult(
        output=File.model_validate({"path_str": str(dst)}),
        pages_processed=(len(doc) if opts.all_pages else 1),
    )
