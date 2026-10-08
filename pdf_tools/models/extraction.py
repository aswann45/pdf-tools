"""Page-oriented PDF extraction results and options."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from pdf_tools.models.files import File


class OcrMode(StrEnum):
    """OCR routing policy."""

    NEVER = "never"
    AUTO = "auto"
    ALWAYS = "always"


class TextSource(StrEnum):
    """Origin of a page's authoritative text."""

    NATIVE = "native"
    OCR = "ocr"
    NONE = "none"


class ExtractionOptions(BaseModel):
    """Select extraction components and one-based pages.

    Parameters
    ----------
    extract_text : bool
        Extract page text.
    extract_images : bool
        Save embedded images.
    ocr : OcrMode
        OCR routing policy.
    pages : list[int] | None
        One-based pages, or all pages when omitted.
    """

    extract_text: bool = True
    extract_images: bool = False
    ocr: OcrMode = OcrMode.NEVER
    pages: list[int] | None = None

    @field_validator("pages")
    @classmethod
    def valid_pages(cls, pages: list[int] | None) -> list[int] | None:
        """Require positive page numbers and normalize order."""
        if pages is not None:
            if any(page < 1 for page in pages):
                raise ValueError("Page numbers must be at least 1")
            return sorted(set(pages))
        return None

    @model_validator(mode="after")
    def valid_content(self) -> "ExtractionOptions":
        """Require at least one extraction component."""
        if not self.extract_text and not self.extract_images:
            raise ValueError("Enable text or images")
        return self


class ExtractedImage(BaseModel):
    """A saved embedded image and its dimensions.

    Parameters
    ----------
    page_number : int
        One-based source page.
    index : int
        One-based index within the page.
    path : Path
        Saved image path.
    width : int
        Pixel width.
    height : int
        Pixel height.
    format : str
        Actual saved encoding.
    """

    page_number: int = Field(ge=1)
    index: int = Field(ge=1)
    path: Path
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    format: str


class PageExtraction(BaseModel):
    """Text, images, and diagnostics from one PDF page."""

    page_number: int = Field(ge=1)
    text: str = ""
    text_source: TextSource = TextSource.NONE
    images: list[ExtractedImage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DocumentExtraction(BaseModel):
    """Independent, serializable result for a single PDF."""

    source: File
    page_count: int = Field(ge=0)
    pages: list[PageExtraction]

    @property
    def text(self) -> str:
        """Join selected page text with form-feed boundaries."""
        return "\f".join(page.text for page in self.pages)
