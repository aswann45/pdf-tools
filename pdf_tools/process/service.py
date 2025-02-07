from collections.abc import Sequence

from pdf_tools.convert.service import convert_file_to_pdf
from pdf_tools.merge.service import merge_pdfs
from pdf_tools.models.files import File


def convert_and_merge_pdfs(
    files: Sequence[File], output_path_str: str, set_bookmarks: bool = False
) -> File:
    files = [convert_file_to_pdf(file) for file in files]
    return merge_pdfs(files, output_path_str, set_bookmarks)
