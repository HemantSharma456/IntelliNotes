"""
Document processing service: PDF and TXT text extraction.
"""

import logging
from pathlib import Path
from typing import Optional

import pymupdf  # PyMuPDF

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """Raised when document text cannot be extracted."""
    pass


class ScannedPDFError(ExtractionError):
    """Raised when a PDF appears to be scanned (no selectable text)."""
    pass


def extract_text_from_pdf(file_path: Path) -> tuple[str, list[int], int]:
    """
    Extract text from a PDF file.

    Returns:
        Tuple of (full_text, page_break_positions, num_pages).

    Raises:
        ExtractionError: If the file cannot be read.
        ScannedPDFError: If no selectable text is found (likely scanned).
    """
    try:
        doc = pymupdf.open(str(file_path))
    except Exception as e:
        raise ExtractionError(f"Failed to open PDF: {e}")

    full_text = ""
    page_breaks = []
    num_pages = len(doc)

    for page_num in range(num_pages):
        page = doc[page_num]
        page_text = page.get_text("text")
        if page_num > 0:
            page_breaks.append(len(full_text))
        full_text += page_text

    doc.close()

    # Check for scanned PDF
    stripped = full_text.strip()
    if not stripped:
        raise ScannedPDFError(
            "This PDF contains no selectable text. It may be a scanned document. "
            "OCR is not supported in this version of IntelliNotes."
        )

    return full_text, page_breaks, num_pages


def extract_text_from_txt(file_path: Path) -> str:
    """
    Extract text from a TXT file (UTF-8).

    Returns:
        The file's text content.

    Raises:
        ExtractionError: If the file cannot be read or is empty.
    """
    try:
        text = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            text = file_path.read_text(encoding="latin-1")
        except Exception as e:
            raise ExtractionError(f"Failed to read TXT file: {e}")
    except Exception as e:
        raise ExtractionError(f"Failed to read TXT file: {e}")

    if not text.strip():
        raise ExtractionError("The uploaded TXT file is empty or contains no readable text.")

    return text


def extract_text(file_path: Path, file_type: str) -> tuple[str, Optional[list[int]], Optional[int]]:
    """
    Extract text from a supported file.

    Returns:
        Tuple of (text, page_breaks_or_None, num_pages_or_None).
    """
    if file_type == "pdf":
        text, page_breaks, num_pages = extract_text_from_pdf(file_path)
        return text, page_breaks, num_pages
    elif file_type == "txt":
        text = extract_text_from_txt(file_path)
        return text, None, None
    else:
        raise ExtractionError(f"Unsupported file type: {file_type}")
