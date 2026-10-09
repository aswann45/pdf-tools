"""Stateless, synchronous facade over the public PDF service functions."""

from collections.abc import Sequence
from pathlib import Path

from pdf_tools.convert.service import (
    convert_file_to_pdf as _convert_file_to_pdf,
)
from pdf_tools.convert.service import (
    convert_files_to_pdfs as _convert_files_to_pdfs,
)
from pdf_tools.convert.service import (
    convert_folder_to_pdfs as _convert_folder_to_pdfs,
)
from pdf_tools.convert.service import (
    convert_image_to_pdf as _convert_image_to_pdf,
)
from pdf_tools.convert.service import (
    convert_word_to_pdf as _convert_word_to_pdf,
)
from pdf_tools.extract.service import extract_pdf as _extract_pdf
from pdf_tools.extract.service import extract_pdf_images as _extract_pdf_images
from pdf_tools.extract.service import extract_pdf_text as _extract_pdf_text
from pdf_tools.merge.service import merge_pdfs as _merge_pdfs
from pdf_tools.models.extraction import (
    DocumentExtraction,
    ExtractionOptions,
    OcrMode,
)
from pdf_tools.models.files import (
    ConversionBatchResult,
    File,
    FileInput,
    FilesInput,
)
from pdf_tools.models.watermark import WatermarkOptions, WatermarkResult
from pdf_tools.process.service import (
    convert_and_merge_pdfs as _convert_and_merge_pdfs,
)
from pdf_tools.watermark.service import (
    add_text_watermark as _add_text_watermark,
)

__all__ = ["PDFTools"]


class PDFTools:
    """Provide the existing synchronous PDF operations as instance methods.

    Construction has no side effects or stored configuration. Each method
    calls its corresponding service function once and returns its result.
    File operations can write to disk. Word conversion still requires a
    caller-managed ``unoserver`` listener, and OCR needs optional assets.
    """

    def convert_word_to_pdf(
        self,
        file: FileInput,
        output_path: str | Path | None = None,
        overwrite: bool = False,
    ) -> File:
        """Convert a Word document using the existing Word service.

        Parameters
        ----------
        file : FileInput
            Input Word document.
        output_path : str | Path | None
            Output PDF path or directory; defaults beside the input.
        overwrite : bool
            Allow replacing an existing output.

        Returns
        -------
        File
            Created PDF description.

        Raises
        ------
        RuntimeError
            The caller-managed ``unoserver`` listener is unavailable or
            conversion fails. Other filesystem errors propagate unchanged.
        """
        return _convert_word_to_pdf(file, output_path, overwrite=overwrite)

    def convert_image_to_pdf(
        self,
        file: FileInput,
        output_path: str | Path | None = None,
        overwrite: bool = False,
    ) -> File:
        """Convert one supported image and write a PDF.

        Parameters
        ----------
        file : FileInput
            Input image.
        output_path : str | Path | None
            Output PDF path or directory; defaults beside the input.
        overwrite : bool
            Allow replacing an existing output.

        Returns
        -------
        File
            Created PDF description.

        Raises
        ------
        RuntimeError
            The image cannot be read or converted. Filesystem errors from
            the image service propagate unchanged.
        """
        return _convert_image_to_pdf(file, output_path, overwrite=overwrite)

    def convert_file_to_pdf(
        self,
        file: FileInput,
        output_path: str | Path | None = None,
        overwrite: bool = False,
    ) -> File:
        """Dispatch an image or Word file to its conversion service.

        Parameters
        ----------
        file : FileInput
            Supported image or Word input.
        output_path : str | Path | None
            Output PDF path or directory; defaults beside the input.
        overwrite : bool
            Allow replacing an existing output.

        Returns
        -------
        File
            Created PDF description.

        Raises
        ------
        UnsupportedFileTypeError
            The source type is unsupported. Conversion and filesystem
            exceptions propagate from the selected service.
        """
        return _convert_file_to_pdf(file, output_path, overwrite=overwrite)

    def convert_files_to_pdfs(
        self,
        files: FilesInput,
        output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> ConversionBatchResult:
        """Convert a batch and report successful and skipped inputs.

        Parameters
        ----------
        files : FilesInput
            Ordered inputs for conversion.
        output_dir : str | Path | None
            Destination directory; defaults to the current directory.
        overwrite : bool
            Allow replacing existing PDFs.

        Returns
        -------
        ConversionBatchResult
            Converted files and per-input failure reasons.

        Raises
        ------
        TypeError
            A single path was supplied instead of a sequence. This method
            retains the service's best-effort batch behavior and writes PDFs.
        """
        return _convert_files_to_pdfs(files, output_dir, overwrite=overwrite)

    def convert_folder_to_pdfs(
        self,
        input_dir: str | Path,
        output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> ConversionBatchResult:
        """Convert immediate children of a directory to PDFs.

        Parameters
        ----------
        input_dir : str | Path
            Directory to enumerate without recursion.
        output_dir : str | Path | None
            Destination directory; defaults to the current directory.
        overwrite : bool
            Allow replacing existing PDFs.

        Returns
        -------
        ConversionBatchResult
            Converted files and per-input failure reasons.

        Raises
        ------
        FileNotFoundError
            The input directory is missing. Other directory errors propagate
            from the service. Successful conversions write PDFs to disk.
        """
        return _convert_folder_to_pdfs(
            input_dir, output_dir, overwrite=overwrite
        )

    def merge_pdfs(
        self,
        files: FilesInput,
        output_path: str | Path,
        set_bookmarks: bool = False,
        overwrite: bool = False,
    ) -> File:
        """Merge PDF inputs into one output document.

        Parameters
        ----------
        files : FilesInput
            Ordered PDF inputs.
        output_path : str | Path
            Destination PDF path.
        set_bookmarks : bool
            Add one top-level bookmark per input.
        overwrite : bool
            Allow replacing an existing output.

        Returns
        -------
        File
            Merged PDF description.

        Raises
        ------
        FileExistsError
            The output exists without ``overwrite``. Filesystem and PDF
            errors propagate from the merge service, which writes the output.
        """
        return _merge_pdfs(
            files, output_path, set_bookmarks, overwrite=overwrite
        )

    def convert_and_merge_pdfs(
        self,
        files: FilesInput,
        output_path: str | Path,
        set_bookmarks: bool = False,
        overwrite: bool = False,
    ) -> File:
        """Convert supported inputs and merge the retained PDFs.

        Parameters
        ----------
        files : FilesInput
            Ordered PDF, image, or Word inputs.
        output_path : str | Path
            Destination PDF path.
        set_bookmarks : bool
            Add one top-level bookmark per retained input.
        overwrite : bool
            Allow replacing an existing output.

        Returns
        -------
        File
            Merged PDF description.

        Raises
        ------
        ValueError
            No inputs remain after conversion. Other exceptions and the
            service's best-effort conversion behavior are unchanged; Word
            inputs require a caller-managed listener.
        """
        return _convert_and_merge_pdfs(
            files, output_path, set_bookmarks, overwrite=overwrite
        )

    def add_text_watermark(
        self,
        *,
        src: str | Path,
        dst: str | Path,
        opts: WatermarkOptions,
    ) -> WatermarkResult:
        """Write a PDF with a text watermark.

        Parameters
        ----------
        src : str | Path
            Input PDF path.
        dst : str | Path
            Destination PDF path.
        opts : WatermarkOptions
            Text styling and placement.

        Returns
        -------
        WatermarkResult
            Output file and processed-page count.

        Raises
        ------
        ValueError
            Source and destination coincide. Filesystem errors propagate
            from the watermark service, which writes the destination.
        """
        return _add_text_watermark(src=src, dst=dst, opts=opts)

    def extract_pdf(
        self,
        source: FileInput,
        options: ExtractionOptions | None = None,
        *,
        image_output_dir: str | Path | None = None,
        overwrite: bool = False,
    ) -> DocumentExtraction:
        """Extract structured page text and optional embedded images.

        Parameters
        ----------
        source : FileInput
            Input PDF.
        options : ExtractionOptions | None
            Extraction components, OCR mode, and selected pages.
        image_output_dir : str | Path | None
            Existing directory required when extracting images.
        overwrite : bool
            Allow replacing existing image outputs.

        Returns
        -------
        DocumentExtraction
            Page-oriented extraction result.

        Raises
        ------
        ExtractionError
            PDF or output validation fails. ``OcrUnavailableError`` may
            propagate when explicit OCR is required. Images may be written.
        """
        return _extract_pdf(
            source,
            options,
            image_output_dir=image_output_dir,
            overwrite=overwrite,
        )

    def extract_pdf_text(
        self,
        source: FileInput,
        *,
        ocr: OcrMode = OcrMode.NEVER,
        pages: Sequence[int] | None = None,
    ) -> DocumentExtraction:
        """Extract selected PDF page text without writing image files.

        Parameters
        ----------
        source : FileInput
            Input PDF.
        ocr : OcrMode
            Native, automatic, or required OCR policy.
        pages : Sequence[int] | None
            One-based selected pages; defaults to all pages.

        Returns
        -------
        DocumentExtraction
            Page text with provenance and form-feed combined text.

        Raises
        ------
        ExtractionError
            PDF validation or extraction fails. ``OcrUnavailableError``
            propagates when required OCR assets are missing.
        """
        return _extract_pdf_text(source, ocr=ocr, pages=pages)

    def extract_pdf_images(
        self,
        source: FileInput,
        output_dir: str | Path,
        *,
        pages: Sequence[int] | None = None,
        overwrite: bool = False,
    ) -> DocumentExtraction:
        """Save embedded PDF images from selected pages.

        Parameters
        ----------
        source : FileInput
            Input PDF.
        output_dir : str | Path
            Existing image destination directory.
        pages : Sequence[int] | None
            One-based selected pages; defaults to all pages.
        overwrite : bool
            Allow replacing existing image outputs.

        Returns
        -------
        DocumentExtraction
            Pages with saved image metadata and paths.

        Raises
        ------
        ExtractionError
            PDF or output validation fails; image files may be written.
        """
        return _extract_pdf_images(
            source, output_dir, pages=pages, overwrite=overwrite
        )
