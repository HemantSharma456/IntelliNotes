"""
Tests for document extraction service.
"""

import pytest
import tempfile
from pathlib import Path

from app.services.documents import (
    extract_text,
    extract_text_from_txt,
    ExtractionError,
)


class TestTxtExtraction:
    """Tests for TXT file extraction."""

    def test_extract_utf8(self, tmp_path):
        """Extract text from a UTF-8 TXT file."""
        f = tmp_path / "test.txt"
        f.write_text("Hello, this is a test document.", encoding="utf-8")
        text = extract_text_from_txt(f)
        assert "Hello" in text
        assert "test document" in text

    def test_empty_txt_raises(self, tmp_path):
        """Empty TXT file raises ExtractionError."""
        f = tmp_path / "empty.txt"
        f.write_text("", encoding="utf-8")
        with pytest.raises(ExtractionError, match="empty"):
            extract_text_from_txt(f)

    def test_whitespace_only_raises(self, tmp_path):
        """Whitespace-only TXT file raises ExtractionError."""
        f = tmp_path / "blank.txt"
        f.write_text("   \n\n\t  ", encoding="utf-8")
        with pytest.raises(ExtractionError, match="empty"):
            extract_text_from_txt(f)

    def test_extract_text_dispatch(self, tmp_path):
        """extract_text dispatches to txt handler."""
        f = tmp_path / "test.txt"
        f.write_text("Content here.", encoding="utf-8")
        text, page_breaks, num_pages = extract_text(f, "txt")
        assert "Content" in text
        assert page_breaks is None
        assert num_pages is None


class TestUnsupportedFiles:
    """Tests for unsupported file types."""

    def test_unsupported_extension(self, tmp_path):
        """Unsupported extension raises ExtractionError."""
        f = tmp_path / "test.docx"
        f.write_text("content", encoding="utf-8")
        with pytest.raises(ExtractionError, match="Unsupported"):
            extract_text(f, "docx")


class TestPDFExtraction:
    """Tests for PDF extraction (requires PyMuPDF)."""

    def test_pdf_extraction(self, tmp_path):
        """Extract text from a simple PDF."""
        import pymupdf

        pdf_path = tmp_path / "test.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Hello from PDF page 1")
        page2 = doc.new_page()
        page2.insert_text((72, 72), "Content on page 2")
        doc.save(str(pdf_path))
        doc.close()

        text, page_breaks, num_pages = extract_text(pdf_path, "pdf")
        assert "Hello from PDF" in text
        assert "Content on page 2" in text
        assert num_pages == 2
        assert len(page_breaks) == 1  # break between page 1 and 2

    def test_pdf_page_numbers_preserved(self, tmp_path):
        """PDF page numbers are correctly tracked through page_breaks."""
        import pymupdf

        pdf_path = tmp_path / "pages.pdf"
        doc = pymupdf.open()
        for i in range(5):
            page = doc.new_page()
            page.insert_text((72, 72), f"Page {i + 1} content here.")
        doc.save(str(pdf_path))
        doc.close()

        text, page_breaks, num_pages = extract_text(pdf_path, "pdf")
        assert num_pages == 5
        assert len(page_breaks) == 4  # 4 breaks between 5 pages
