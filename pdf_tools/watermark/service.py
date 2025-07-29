"""Service helpers for stamping text watermarks onto PDF pages."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

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
    """Stamp *text* onto a PDF using :mod:`PyMuPDF`.

    Parameters
    ----------
    src : :class:`Path`
        Input PDF path.
    dst : :class:`Path`
        Output PDF path.
    opts : :class:`WatermarkOptions`
        Styling & placement options; see
        :class:`pdf_tools.models.watermark.WatermarkOptions`.

    Returns
    -------
    :class:`WatermarkResult`
        Metadata describing the operation.  Raises on error.

    Raises
    ------
    ValueError
        If source and destination paths are the same.
    """
    if src == dst:
        raise ValueError("Source and destination paths must differ.")

    with pymupdf.open(src) as doc:
        # Prepare placement defaults ------------------------------------------
        for page in _iter_target_pages(doc, all_pages=opts.all_pages):
            bbox = page.rect  # full page rectangle
            cx = opts.x if opts.x is not None else bbox.width / 2
            cy = opts.y if opts.y is not None else bbox.height / 2

            half_w = opts.box_width / 2
            half_h = opts.box_height / 2

            rect = pymupdf.Rect(
                cx - half_w, cy - half_h, cx + half_w, cy + half_h
            )

            h_align_map: Mapping[str, Any] = {
                "left": pymupdf.TEXT_ALIGN_LEFT,
                "center": pymupdf.TEXT_ALIGN_CENTER,
                "right": pymupdf.TEXT_ALIGN_RIGHT,
            }
            align = h_align_map.get(opts.h_align, pymupdf.TEXT_ALIGN_CENTER)

            page.insert_textbox(
                rect,
                opts.text,
                fontname=opts.font_name,
                fontsize=opts.font_size,
                lineheight=opts.lineheight,
                rotate=opts.rotation,
                color=opts.color,  # validated to (r,g,b)
                fill_opacity=opts.opacity,
                render_mode=0,  # fill text
                align=align,
            )
        len_ = len(doc)
        doc.save(dst, deflate=True)

    return WatermarkResult(
        output=File.model_validate({"path": dst}),
        pages_processed=(len_ if opts.all_pages else 1),
    )
