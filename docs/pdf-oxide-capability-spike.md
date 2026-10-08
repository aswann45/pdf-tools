# PDF Oxide 0.3.78 capability spike

This branch pins `pdf-oxide>=0.3.78,<0.4.0` and probes the installed Python
binding. The results below were observed on Linux with Python 3.11.15.

| Capability | Result | Migration decision |
| --- | --- | --- |
| JPEG and RGB PNG to PDF | `Pdf.from_image(path)` succeeded | Use PDF Oxide directly. |
| TIFF and BMP to PDF | Direct call raised `RuntimeError: Unsupported image format` | Normalize to RGB PNG with Pillow, then use PDF Oxide. |
| RGBA and grayscale images | Normalized RGB PNG succeeded | Keep Pillow normalization. |
| PDF merge | Two and six-page merges preserved order and page dimensions | Use `Pdf.merge` when bookmarks are off. |
| Outline writing | `PdfDocument.get_outline()` reads outlines; no outline writer is exposed | Merge with PDF Oxide, then use pypdf only to write outline entries. |
| Styled watermark editing | `PdfPage.add_text` accepts text, x, y, and font size only | Use open-source ReportLab and pypdf for rotation, opacity, color, and alignment. |
| DOCX | `OfficeConverter.from_docx` did not complete within 120 seconds on a one-paragraph `python-docx` file; a LibreOffice-produced DOCX also timed out. Version 0.3.74 timed out on the same fixture. | Keep the existing LibreOffice + unoserver path until native conversion is reliable. |
| Binary DOC | `OfficeConverter.convert` converted one simple `.doc` file and produced extractable text | Keep the existing LibreOffice + unoserver path pending representative fidelity testing. |

The DOCX probe was also run outside the filesystem sandbox and still timed
out. The same DOCX converted successfully with direct headless LibreOffice.
These observations prevent removal of LibreOffice or pypdf under
the migration's compatibility rules. DOCX layout fidelity, native PDF Oxide
styled watermark parity, cross-platform wheel installation, and full DOC
capability remain open gates. ReportLab and pypdf now provide the styled
watermark compatibility path without PyMuPDF.

The [PDF Oxide Python reference](https://pdf.oxide.fyi/dart/docs/reference/python-api)
documents the current creation, editing, and inspection methods. The
[Python getting-started guide](https://github.com/yfedoseev/pdf_oxide/blob/main/docs/getting-started-python.md)
documents `OfficeConverter` and `Pdf.from_image`.
