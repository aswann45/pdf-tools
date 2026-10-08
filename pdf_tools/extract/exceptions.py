"""Public extraction errors."""


class ExtractionError(RuntimeError):
    """PDF extraction failed."""


class OcrUnavailableError(ExtractionError):
    """OCR runtime or model assets are unavailable."""
