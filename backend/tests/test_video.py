"""
Unit tests for VideoService: URL parsing, transcript chunking, and metadata fetching.
"""

import pytest
from unittest.mock import MagicMock, patch
from youtube_transcript_api import TranscriptsDisabled, NoTranscriptFound

from app.services.video import VideoService, TranscriptUnavailableError
from app.services.store import StoreService
from app.services.embeddings import EmbeddingService


class TestVideoUrlExtraction:
    """Tests for extracting 11-char YouTube video IDs across different URL formats."""

    def test_standard_watch_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert VideoService.extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_watch_url_with_parameters(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&feature=shared&t=42s"
        assert VideoService.extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_shortened_youtu_be_url(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert VideoService.extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_shortened_youtu_be_with_timestamp(self):
        url = "https://youtu.be/dQw4w9WgXcQ?t=120"
        assert VideoService.extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_embed_url(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert VideoService.extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        assert VideoService.extract_youtube_id(url) == "dQw4w9WgXcQ"

    def test_bare_id(self):
        assert VideoService.extract_youtube_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_invalid_urls(self):
        assert VideoService.extract_youtube_id("https://vimeo.com/123456789") is None
        assert VideoService.extract_youtube_id("https://google.com") is None
        assert VideoService.extract_youtube_id("not-a-url") is None
        assert VideoService.extract_youtube_id("") is None
        assert VideoService.extract_youtube_id(None) is None


class TestVideoChunking:
    """Tests for time-based sliding window transcript chunking."""

    def test_short_transcript_single_chunk(self):
        """Transcripts shorter than target duration (75s) produce 1 chunk."""
        raw_transcript = [
            {"text": "Welcome to Linear Algebra.", "start": 0.0, "duration": 4.5},
            {"text": "Today we will talk about matrices.", "start": 5.0, "duration": 5.2},
            {"text": "A matrix is a rectangular array of numbers.", "start": 11.0, "duration": 6.0},
        ]
        chunks = VideoService.chunk_transcript(raw_transcript, target_duration=75.0, overlap_duration=15.0)
        assert len(chunks) == 1
        assert chunks[0]["start_time"] == 0.0
        assert chunks[0]["end_time"] == 17.0
        assert "Welcome to Linear Algebra." in chunks[0]["text"]
        assert chunks[0]["token_count"] > 0

    def test_long_transcript_multiple_chunks_with_overlap(self):
        """Transcripts spanning several minutes produce multiple overlapping chunks."""
        # Create synthetic 300-second transcript (5 minutes)
        raw_transcript = []
        for i in range(30):
            raw_transcript.append({
                "text": f"This is segment number {i} discussing machine learning concepts.",
                "start": float(i * 10),
                "duration": 9.5,
            })

        chunks = VideoService.chunk_transcript(raw_transcript, target_duration=75.0, overlap_duration=15.0)
        assert len(chunks) > 1

        # Check first chunk
        assert chunks[0]["start_time"] == 0.0
        assert chunks[0]["end_time"] > 60.0

        # Check overlap: second chunk should start before the first chunk ends
        assert chunks[1]["start_time"] < chunks[0]["end_time"]
        assert chunks[1]["start_time"] >= 50.0

    def test_empty_transcript(self):
        chunks = VideoService.chunk_transcript([])
        assert chunks == []


class TestVideoServiceErrors:
    """Tests for transcript unavailability error handling."""

    def test_transcripts_disabled_error(self, tmp_path):
        store = StoreService(tmp_path / "test.db")
        mock_embedding = MagicMock(spec=EmbeddingService)
        service = VideoService(store, mock_embedding)

        target = "youtube_transcript_api.YouTubeTranscriptApi.fetch" if hasattr(
            VideoService, "fetch_transcript"
        ) else "youtube_transcript_api.YouTubeTranscriptApi.get_transcript"

        with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", side_effect=TranscriptsDisabled("dQw4w9WgXcQ")):
            with pytest.raises(TranscriptUnavailableError) as exc_info:
                service.fetch_transcript("dQw4w9WgXcQ")
            assert "unavailable or disabled" in str(exc_info.value)

    def test_no_transcript_found_error(self, tmp_path):
        store = StoreService(tmp_path / "test.db")
        mock_embedding = MagicMock(spec=EmbeddingService)
        service = VideoService(store, mock_embedding)

        with patch("youtube_transcript_api.YouTubeTranscriptApi.fetch", side_effect=NoTranscriptFound("dQw4w9WgXcQ", ["en"], [])):
            with pytest.raises(TranscriptUnavailableError):
                service.fetch_transcript("dQw4w9WgXcQ")
