"""
Tests for the chunking service.
"""

import pytest
from app.services.chunking import chunk_text


class TestChunking:
    """Tests for text chunking."""

    def test_basic_chunking(self):
        """Chunks text into expected number of pieces."""
        text = "A" * 1024
        chunks = chunk_text(text, chunk_size=512, chunk_overlap=64)
        # 1024 chars, step=448, so positions: 0, 448 → 2 chunks
        assert len(chunks) >= 2
        assert all(c["text"] for c in chunks)

    def test_chunk_size(self):
        """Each chunk is at most chunk_size characters."""
        text = "Hello world! " * 200
        chunks = chunk_text(text, chunk_size=256, chunk_overlap=32)
        for c in chunks:
            assert len(c["text"]) <= 256

    def test_chunk_overlap(self):
        """Overlapping chunks share characters."""
        text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 50  # 1300 chars
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)
        # Check that consecutive chunks overlap
        if len(chunks) >= 2:
            end_of_first = chunks[0]["end_char"]
            start_of_second = chunks[1]["start_char"]
            assert start_of_second < end_of_first  # overlap exists

    def test_empty_text(self):
        """Empty text returns no chunks."""
        assert chunk_text("") == []
        assert chunk_text("   ") == []
        assert chunk_text("\n\n") == []

    def test_small_text(self):
        """Text smaller than chunk_size yields one chunk."""
        text = "Short text."
        chunks = chunk_text(text, chunk_size=512, chunk_overlap=64)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Short text."

    def test_page_breaks(self):
        """Page numbers are determined from page break positions."""
        text = "Page one content. " * 30 + "Page two content. " * 30
        page_break = len("Page one content. " * 30)
        chunks = chunk_text(
            text, chunk_size=200, chunk_overlap=20, page_breaks=[page_break]
        )
        # First chunk should be page 1
        assert chunks[0]["page"] == 1
        # Last chunk should be page 2
        assert chunks[-1]["page"] == 2

    def test_chunk_positions(self):
        """Each chunk records start_char and end_char."""
        text = "Hello " * 100
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
        for c in chunks:
            assert c["start_char"] is not None
            assert c["end_char"] is not None
            assert c["start_char"] < c["end_char"]
            assert text[c["start_char"]:c["end_char"]] == c["text"]

    def test_overlap_exceeds_size_raises(self):
        """Overlap >= size raises ValueError."""
        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            chunk_text("Hello world", chunk_size=100, chunk_overlap=100)

        with pytest.raises(ValueError, match="chunk_overlap must be less than chunk_size"):
            chunk_text("Hello world", chunk_size=100, chunk_overlap=200)

    def test_no_page_breaks(self):
        """Without page breaks, page is None."""
        chunks = chunk_text("Hello world", chunk_size=512, chunk_overlap=64)
        assert chunks[0]["page"] is None


class TestChunkingEdgeCases:
    """Edge cases for chunking."""

    def test_whitespace_only_chunks_skipped(self):
        """Chunks that are all whitespace are not included."""
        text = "Content" + " " * 600 + "More content"
        chunks = chunk_text(text, chunk_size=100, chunk_overlap=10)
        for c in chunks:
            assert c["text"].strip()

    def test_single_character_text(self):
        """Single character produces one chunk."""
        chunks = chunk_text("X", chunk_size=512, chunk_overlap=64)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "X"
