"""
Tests for Study Tool Video Recommendations (Phase 3.4).
Verifies hybrid workspace matching, external suggestions, SQLite study caching, and API routing.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.models.schemas import (
    VideoRecommendationResponse,
    WorkspaceVideoMatch,
    VideoSuggestion,
)
from app.services.store import StoreService
from app.services.study import StudyService
from app.services.retrieval import RetrievalResult
from app.main import create_app
from app.api.routes import set_state
from app.config import Settings


@pytest.fixture
def test_env(tmp_path):
    """Set up test store, mock LLM, and mock retrieval service."""
    db_path = tmp_path / "test_recs.db"
    store = StoreService(db_path)

    # Insert a test document and chunks
    doc = store.create_document("lecture_notes.pdf", 2, 2048)
    store.store_chunks(
        doc["id"],
        [
            {"text": "Eigenvalues and eigenvectors in linear transformations.", "page": 1, "token_count": 8},
            {"text": "Matrix diagonalization and spectral theorem concepts.", "page": 2, "token_count": 8},
        ],
    )

    # Insert a test video and chunks
    vid = store.create_video(
        youtube_id="abc123xyz00",
        url="https://www.youtube.com/watch?v=abc123xyz00",
        title="Gilbert Strang Linear Algebra Lecture 21",
        channel="MIT OpenCourseWare",
        duration=3000,
        thumbnail_url="https://i.ytimg.com/vi/abc123xyz00/hqdefault.jpg",
    )
    store.store_video_chunks(
        vid["id"],
        [
            {
                "start_time": 120.0,
                "end_time": 210.0,
                "text": "Today we discuss eigenvalues and diagonalizing symmetric matrices.",
                "token_count": 10,
            }
        ],
    )

    # Mock LLM service returning structured suggestions
    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {
        "suggestions": [
            {
                "title": "MIT 18.06 Eigenvalues and Eigenvectors",
                "topic": "Eigenvalues",
                "search_url": "https://www.youtube.com/results?search_query=MIT+18.06+Eigenvalues",
                "rationale": "Renowned lecture covering the exact spectral concepts in the notes.",
            },
            {
                "title": "3Blue1Brown Essence of Linear Algebra Chapter 14",
                "topic": "Geometric Intuition for Eigenvectors",
                "search_url": "https://www.youtube.com/results?search_query=3Blue1Brown+Eigenvectors",
                "rationale": "Visual explanation of linear transformations.",
            },
        ]
    }

    # Mock retrieval service
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = [
        RetrievalResult(
            chunk_id="chunk_vid_1",
            text="Today we discuss eigenvalues and diagonalizing symmetric matrices.",
            score=0.88,
            source_type="video",
            video_id=vid["id"],
            video_title=vid["title"],
            channel=vid["channel"],
            start_time=120.0,
            end_time=210.0,
            timestamp_url=f"https://www.youtube.com/watch?v={vid['youtube_id']}&t=120s",
        )
    ]

    study_service = StudyService(store=store, llm=mock_llm, retrieval=mock_retrieval)
    study_service._search_youtube_video = MagicMock(return_value={
        "youtube_id": "test_yt_id_01",
        "title": "MIT 18.06 Eigenvalues and Eigenvectors",
        "channel": "MIT OpenCourseWare",
    })

    return {
        "store": store,
        "doc": doc,
        "vid": vid,
        "mock_llm": mock_llm,
        "mock_retrieval": mock_retrieval,
        "study": study_service,
        "tmp_path": tmp_path,
    }


class TestVideoRecommendations:
    def test_generate_video_recommendations_hybrid(self, test_env):
        study = test_env["study"]
        doc = test_env["doc"]

        res = study.generate_video_recommendations(doc["id"])

        assert res["document_id"] == doc["id"]
        assert res["document_name"] == "lecture_notes.pdf"

        # Check workspace matches
        assert len(res["workspace_matches"]) == 1
        match = res["workspace_matches"][0]
        assert match["video_title"] == "Gilbert Strang Linear Algebra Lecture 21"
        assert match["start_time"] == 120.0
        assert "&t=120s" in match["timestamp_url"]

        # Check external suggestions
        assert len(res["external_suggestions"]) == 2
        sug = res["external_suggestions"][0]
        assert "MIT 18.06" in sug["title"]
        assert "Eigenvalues" in sug["topic"]
        assert "youtube.com" in sug["search_url"]

    def test_caching_behavior(self, test_env):
        study = test_env["study"]
        doc = test_env["doc"]
        mock_llm = test_env["mock_llm"]

        # First call generates and caches
        res1 = study.generate_video_recommendations(doc["id"])
        assert mock_llm.generate_json.call_count == 1

        # Second call hits cache without calling LLM again
        res2 = study.generate_video_recommendations(doc["id"])
        assert mock_llm.generate_json.call_count == 1
        assert res1 == res2

        # Force refresh bypasses cache and calls LLM again
        res3 = study.generate_video_recommendations(doc["id"], force_refresh=True)
        assert mock_llm.generate_json.call_count == 2
        assert len(res3["external_suggestions"]) == 2

    def test_empty_workspace_videos_fallback(self, test_env):
        store = test_env["store"]
        study = test_env["study"]
        vid = test_env["vid"]
        doc = test_env["doc"]

        # Delete all videos from store
        store.delete_video(vid["id"])
        assert store.count_videos() == 0

        res = study.generate_video_recommendations(doc["id"], force_refresh=True)
        assert res["workspace_matches"] == []
        assert len(res["external_suggestions"]) == 2

    def test_missing_document_raises_value_error(self, test_env):
        study = test_env["study"]
        with pytest.raises(ValueError, match="Document not found"):
            study.generate_video_recommendations("non-existent-doc-id")


class TestVideoRecommendationsAPI:
    def test_api_get_video_recommendations_success(self, test_env):
        doc = test_env["doc"]
        study = test_env["study"]
        store = test_env["store"]

        app = create_app()
        set_state({
            "store": store,
            "study_service": study,
            "embedding_service": MagicMock(),
        })

        client = TestClient(app)
        response = client.get(f"/documents/{doc['id']}/video-recommendations")
        assert response.status_code == 200
        data = response.json()

        assert data["document_id"] == doc["id"]
        assert len(data["workspace_matches"]) == 1
        assert len(data["external_suggestions"]) == 2
        assert data["workspace_matches"][0]["video_title"] == "Gilbert Strang Linear Algebra Lecture 21"

    def test_api_get_video_recommendations_not_found(self, test_env):
        study = test_env["study"]
        store = test_env["store"]

        app = create_app()
        set_state({
            "store": store,
            "study_service": study,
            "embedding_service": MagicMock(),
        })

        client = TestClient(app)
        response = client.get("/documents/unknown-doc-id/video-recommendations")
        assert response.status_code == 404
