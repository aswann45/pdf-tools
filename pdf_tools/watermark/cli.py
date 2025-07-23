"""CLI surface for the watermark module."""

from pathlib import Path
from typing import Annotated, Optional

import typer
from typer import Argument, Option

from pdf_tools.models.watermark import WatermarkOptions
from pdf_tools.watermark.service import add_text_watermark

cli = typer.Typer(help="Add text or image watermarks to PDFs.")


@cli.command()
def add_text(
    src: Annotated[Path, Argument(exists=True, help="PDF to watermark.")],
    dst: Annotated[Path, Argument(help="Destination PDF.")],
    text: Annotated[str, Option("--text", "-t", help="Label to stamp.")],
    font_size: Annotated[
        int, Option("--font-size", "-s", help="Font size (pts).")
    ] = 48,
    font_name: Annotated[
        str, Option("--font-name", "-f", help="Typeface name.")
    ] = "helv",
    color: Annotated[
        str, Option("--color", "-c", help="Hex colour (#RRGGBB).")
    ] = "FF0000",
    opacity: Annotated[
        float, Option("--opacity", "-o", help="0 transparent … 1 opaque.")
    ] = 0.15,
    rotation: Annotated[
        float, Option("--rotation", "-r", help="Degrees counter-clockwise.")
    ] = 45.0,
    x_position: Annotated[
        Optional[float],
        Option("--x-position", "-x", help="X position (pts from left)."),
    ] = None,
    y_position: Annotated[
        Optional[float],
        Option("--y-position", "-y", help="Y position (pts from top)."),
    ] = None,
    first_page_only: Annotated[
        bool, Option("--first-page-only", help="Stamp only on the first page.")
    ] = False,
) -> None:
    """Add a semi-transparent text stamp (watermark)."""
    opts = WatermarkOptions(
        text=text,
        font_size=font_size,
        font_name=font_name,
        color=color,
        opacity=opacity,
        rotation=rotation,
        x=x_position,
        y=y_position,
        all_pages=not first_page_only,
    )
    result = add_text_watermark(src=src, dst=dst, opts=opts)
    typer.secho(f"✅  {result.message}", fg="green")
