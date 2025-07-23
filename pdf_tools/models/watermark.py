"""pydantic models that describe watermark configuration."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field, computed_field, field_validator

from .files import File


class WatermarkOptions(BaseModel):
    """User-tunable styling for text watermarks."""

    text: Annotated[str, Field(min_length=1, description="Label to stamp")]
    font_size: Annotated[int, Field(gt=0)] = 48
    font_name: str = "helv"  # built-in Helvetica alias in MuPDF
    rotation: float = Field(default=45.0, description="degrees CCW")
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
    all_pages: bool = Field(
        default=True,
        description="apply formatting to all pages; only first page if False",
    )

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v):
        """Accept #RGB hex or float tuple."""
        if isinstance(v, str):
            v = v.lstrip("#")
            if len(v) not in (6, 3):
                raise ValueError("Hex colours must be #RRGGBB or #RGB")
            if len(v) == 3:
                v = "".join(ch * 2 for ch in v)
            return tuple(int(v[i : i + 2], 16) / 255 for i in (0, 2, 4))
        return v


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
