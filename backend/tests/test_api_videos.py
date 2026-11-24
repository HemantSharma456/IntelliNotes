"""
Integration tests for Video API endpoints:
POST /videos/ingest
GET /videos
GET /videos/{video_id}
DELETE /videos/{video_id}
POST /videos/search
POST /documents/{document_id}/suggest-videos
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import create_app
from app.api.routes import set_state
from app.services.store import StoreService
from app.services.embeddings import EmbeddingService
from app.services.retrieval import RetrievalService
from app.services.video import VideoService, TranscriptUnavailableError
from app.services.llm import LLMService


@pytest.fixture
def video_app_env(tmp_path):
    """Set up test environment with SQLite and mocked external services."""
    store = StoreService(tmp_path / "test_videos.db")
    
    mock_embedding = MagicMock(spec=EmbeddingService)
    mock_embedding.embed_query.return_value = [0.1] * 384
    mock_embedding.add_chunks = MagicMock()
    mock_embedding.rebuild_index = MagicMock()
    mock_embedding.remove_chunks = MagicMock()

    retrieval_service = RetrievalService(mock_embedding, store)
    video_service = VideoService(store, mock_embedding)

    mock_llm = MagicMock(spec=LLMService)
    mock_llm.generate_json.return_value = {
        "suggestions": [
            {
                "title": "MIT 18.06 Linear Algebra - Lecture 1",
                "topic": "Systems of Linear Equations",
                "search_url": "https://www.youtube.com/results?search_query=MIT+18.06+Linear+Algebra",
                "rationale": "Directly explains the vector equations in chapter 1."
            }
        ]
    }

    mock_study = MagicMock()
    mock_study.generate_video_summary.return_value = {
        "video_id": "test-vid-id",
        "youtube_id": "search12345",
        "video_title": "Sorting Algorithms",
        "channel": "Computerphile",
        "summary": "This video introduces quicksort and partition algorithms.",
        "timestamps": [
            {
                "time_seconds": 12,
                "timestamp_formatted": "00:12",
                "topic": "Pivot Selection",
                "description": "Choosing an effective pivot element",
            }
        ],
    }

    state = {
        "settings": MagicMock(TOP_K=5, SIMILARITY_THRESHOLD=0.25),
        "store": store,
        "embedding_service": mock_embedding,
        "retrieval_service": retrieval_service,
        "rag_service": None,
        "study_service": mock_study,
        "video_service": video_service,
        "llm_service": mock_llm,
    }
    set_state(state)

    app = create_app()
    client = TestClient(app)
    return {
        "client": client,
        "store": store,
        "video_service": video_service,
        "embedding_service": mock_embedding,
        "retrieval_service": retrieval_service,
        "llm_service": mock_llm,
        "study_service": mock_study,
    }


class TestVideoAPI:
    """Tests for Video Knowledge Retrieval endpoints."""

    def test_ingest_video_success(self, video_app_env):
        client = video_app_env["client"]

        fake_transcript = [
            {"text": "Introduction to neural networks.", "start": 0.0, "duration": 4.0},
            {"text": "Backpropagation calculates gradients.", "start": 4.5, "duration": 5.0},
        ]
        fake_meta = {
            "title": "Neural Networks Explained",
            "channel": "3Blue1Brown",
            "thumbnail_url": "https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        }

        with patch.object(VideoService, "fetch_transcript", return_value=fake_transcript), \
             patch.object(VideoService, "fetch_metadata", new_callable=AsyncMock, return_value=fake_meta):

            resp = client.post("/videos/ingest", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["video"]["youtube_id"] == "dQw4w9WgXcQ"
            assert data["video"]["title"] == "Neural Networks Explained"
            assert data["video"]["channel"] == "3Blue1Brown"
            assert data["num_chunks"] == 1

            # Test deduplication: re-ingesting same URL returns existing without error
            resp2 = client.post("/videos/ingest", json={"url": "https://youtu.be/dQw4w9WgXcQ"})
            assert resp2.status_code == 200
            assert resp2.json()["video"]["id"] == data["video"]["id"]

    def test_ingest_video_invalid_url(self, video_app_env):
        client = video_app_env["client"]
        resp = client.post("/videos/ingest", json={"url": "https://vimeo.com/123456789"})
        assert resp.status_code == 400
        assert "Invalid YouTube URL" in resp.json()["detail"]

    def test_ingest_video_no_transcript(self, video_app_env):
        client = video_app_env["client"]
        with patch.object(VideoService, "fetch_transcript", side_effect=TranscriptUnavailableError("Captions disabled.")):
            resp = client.post("/videos/ingest", json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"})
            assert resp.status_code == 422
            assert "Captions disabled" in resp.json()["detail"]

    def test_list_and_get_video(self, video_app_env):
        client = video_app_env["client"]
        store = video_app_env["store"]

        # Create a video in DB
        video = store.create_video(
            youtube_id="abc12345678",
            url="https://www.youtube.com/watch?v=abc12345678",
            title="Database Normalization",
            channel="MIT OCW",
            duration=300,
            thumbnail_url="https://img.youtube.com/vi/abc12345678/hqdefault.jpg"
        )
        store.store_video_chunks(video["id"], [
            {"start_time": 0.0, "end_time": 60.0, "text": "First Normal Form requires atomic values.", "token_count": 8},
            {"start_time": 45.0, "end_time": 105.0, "text": "Second Normal Form removes partial dependencies.", "token_count": 8},
        ])

        # Test GET /videos
        resp = client.get("/videos")
        assert resp.status_code == 200
        videos = resp.json()["videos"]
        assert len(videos) == 1
        assert videos[0]["title"] == "Database Normalization"

        # Test GET /videos/{id}
        resp_detail = client.get(f"/videos/{video['id']}")
        assert resp_detail.status_code == 200
        data = resp_detail.json()
        assert len(data["chunks"]) == 2
        assert "&t=0s" in data["chunks"][0]["timestamp_url"]
        assert "&t=45s" in data["chunks"][1]["timestamp_url"]

        # Test GET non-existent
        assert client.get("/videos/non-existent-id").status_code == 404

    def test_delete_video(self, video_app_env):
        client = video_app_env["client"]
        store = video_app_env["store"]

        video = store.create_video(
            youtube_id="del12345678",
            url="https://www.youtube.com/watch?v=del12345678",
            title="Algorithms",
        )
        store.store_video_chunks(video["id"], [
            {"start_time": 0.0, "end_time": 60.0, "text": "Merge sort divides and conquers.", "token_count": 6}
        ])

        del_resp = client.delete(f"/videos/{video['id']}")
        assert del_resp.status_code == 200
        assert del_resp.json()["video_id"] == video["id"]

        # Confirm deleted from store
        assert store.get_video(video["id"]) is None
        assert store.get_video_chunks(video["id"]) == []

    def test_search_videos(self, video_app_env):
        client = video_app_env["client"]
        store = video_app_env["store"]
        mock_embedding = video_app_env["embedding_service"]

        video = store.create_video(
            youtube_id="search12345",
            url="https://www.youtube.com/watch?v=search12345",
            title="Sorting Algorithms",
            channel="Computerphile",
        )
        chunk_ids = store.store_video_chunks(video["id"], [
            {"start_time": 12.5, "end_time": 72.0, "text": "Quicksort chooses a pivot element.", "token_count": 6}
        ])

        # Mock embedding search returning the chunk
        mock_embedding.search.return_value = [(chunk_ids[0], 0.88)]

        search_resp = client.post("/videos/search", json={"query": "How does quicksort work?", "threshold": 0.5})
        assert search_resp.status_code == 200
        results = search_resp.json()["results"]
        assert len(results) == 1
        assert results[0]["video_title"] == "Sorting Algorithms"
        assert "&t=12s" in results[0]["timestamp_url"]
        assert results[0]["score"] == 0.88

    def test_suggest_videos_for_document(self, video_app_env):
        client = video_app_env["client"]
        store = video_app_env["store"]

        # Add document and chunks
        doc = store.create_document("calculus.pdf", "pdf", 2048, num_pages=2)
        store.store_chunks(doc["id"], [
            {"text": "Derivatives represent instantaneous rates of change in a function.", "page": 1, "start_char": 0, "end_char": 68}
        ])

        resp = client.post(f"/documents/{doc['id']}/suggest-videos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == doc["id"]
        assert len(data["suggestions"]) == 1
        assert "MIT 18.06" in data["suggestions"][0]["title"]
        assert "youtube.com/results" in data["suggestions"][0]["search_url"]

    def test_generate_video_summary_success(self, video_app_env):
        client = video_app_env["client"]
        resp = client.post("/study-tools/video-summary", json={"video_id": "test-vid-id"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["video_id"] == "test-vid-id"
        assert len(data["timestamps"]) == 1
        assert data["timestamps"][0]["time_seconds"] == 12
        assert data["timestamps"][0]["topic"] == "Pivot Selection"
        assert "quicksort" in data["summary"].lower()

    def test_generate_video_summary_not_found(self, video_app_env):
        client = video_app_env["client"]
        video_app_env["study_service"].generate_video_summary.side_effect = ValueError("Video not found: bad-id")
        resp = client.post("/study-tools/video-summary", json={"video_id": "bad-id"})
        assert resp.status_code == 404
