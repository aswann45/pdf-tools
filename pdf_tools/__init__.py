from pdf_tools.api import PDFTools
from pdf_tools.convert import (
    UnsupportedFileTypeError,
    convert_file_to_pdf,
    convert_files_to_pdfs,
    convert_folder_to_pdfs,
    convert_image_to_pdf,
    convert_word_to_pdf,
    unoserver_listener,
)
from pdf_tools.extract import (
    ExtractionError,
    OcrUnavailableError,
    extract_pdf,
    extract_pdf_images,
    extract_pdf_text,
)
from pdf_tools.merge import merge_pdfs
from pdf_tools.models import (
    ConversionBatchResult,
    DocumentExtraction,
    ExtractedImage,
    ExtractionOptions,
    File,
    FileInput,
    Files,
    FilesInput,
    OcrMode,
    PageExtraction,
    SkippedFile,
    TextSource,
    WatermarkOptions,
    WatermarkResult,
)
from pdf_tools.process import convert_and_merge_pdfs
from pdf_tools.watermark import add_text_watermark

__all__ = [
    "PDFTools",
    "ConversionBatchResult",
    "DocumentExtraction",
    "ExtractedImage",
    "ExtractionOptions",
    "File",
    "FileInput",
    "Files",
    "FilesInput",
    "OcrMode",
    "PageExtraction",
    "SkippedFile",
    "TextSource",
    "WatermarkOptions",
    "WatermarkResult",
    "ExtractionError",
    "OcrUnavailableError",
    "UnsupportedFileTypeError",
    "add_text_watermark",
    "convert_and_merge_pdfs",
    "convert_file_to_pdf",
    "convert_files_to_pdfs",
    "convert_folder_to_pdfs",
    "convert_image_to_pdf",
    "convert_word_to_pdf",
    "extract_pdf",
    "extract_pdf_images",
    "extract_pdf_text",
    "merge_pdfs",
    "unoserver_listener",
]
