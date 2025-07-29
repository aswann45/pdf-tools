"""pydantic models that describe watermark configuration."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

from .files import File


class WatermarkOptions(BaseModel):
    """User-tunable styling for text watermarks.

    Parameters
    ----------
    text : `str`
        Label to stamp.
    font_size : `int`, default 48
        Font size.
    font_name : `str`, default "helv"
        MuPDF font name. Defaults to "helv", the built-in Helvetica alias.
    lineheight : `float`, default 1.0
        Factor to increase/decrease vertical text spacing.
    rotation : `float`, default 0.0
        Text rotation in degrees. Must be multiple of 90.
    opacity : `float`, default 0.15
        Text opacity.
    color : `str` | `tuple[float, float, float]`, default "#FF0000"
        Text color as either a 3- or 6-character hex string or
        3-tuple float value.
    x : `float` | `None`, default `None`
        Horizontal position, center if None.
    y : `float` | `None`, default `None`
        Vertical position, center if None.
    box_width : `float`, default 500.0
        Width of textbox in points.
    box_height : `float`, default 200.0
        Height of textbox in points.
    h_align : `str`, default "center"
        Horizontal text alignment within textbox. One of "center," "left," or
        "right."
    v_align : `str`, default "center"
        Vertical text alignment within textbox. One of "center," "left," or
        "right."
    all_pages : `bool`, default ``True``
        Apply formatting to all pages if ``True``. If ``False``, only apply
        formatting to first page.
    """

    text: Annotated[str, Field(min_length=1, description="Label to stamp")]
    font_size: Annotated[int, Field(gt=0)] = 48
    font_name: str = "helv"  # built-in Helvetica alias in MuPDF
    lineheight: float = Field(
        default=1.0,
        description="Factor to increase/decrese vertical text spacing.",
    )
    rotation: float = Field(
        default=0.0, description="degrees, multiples of 90", multiple_of=90.0
    )
    opacity: Annotated[float, Field(ge=0.0, le=1.0)] = 0.15
    color: str | tuple[float, float, float] = Field(
        default="#FF0000", description="hex or 0-1 tuple"
    )
    x: float | None = Field(
        default=None, description="horizontal position, center if None"
    )
    y: float | None = Field(
        default=None, description="vertical position, center if None"
    )
    box_width: float = Field(
        default=500.0, description="pts; width of textbox"
    )
    box_height: float = Field(
        default=200.0, description="pts; height of the textbox"
    )
    h_align: Literal["left", "center", "right"] = "center"
    v_align: Literal["left", "center", "right"] = "center"
    all_pages: bool = Field(
        default=True,
        description="apply formatting to all pages; only first page if False",
    )

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | tuple[float, ...]) -> tuple[float, ...]:
        """Accept #RGB hex or float tuple."""
        if isinstance(v, str):
            v = v.lstrip("#")
            if len(v) not in (6, 3):
                raise ValueError("Hex colours must be #RRGGBB or #RGB")
            if len(v) == 3:
                v = "".join(ch * 2 for ch in v)
            return tuple(int(v[i : i + 2], 16) / 255 for i in (0, 2, 4))
        return v  # pragma: no cover

    model_config = ConfigDict(validate_default=True)


class WatermarkResult(BaseModel):
    """Return payload summarising what happened."""

    output: File
    pages_processed: int

    @computed_field  # type: ignore[prop-decorator]
    @property
    def message(self) -> str:
        """Human-readable summary."""
        return (
            f"Added watermark on {self.pages_processed} page(s) → "
            f"{self.output.path}"
        )
