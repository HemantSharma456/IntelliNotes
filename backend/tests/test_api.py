"""
Tests for API routes using FastAPI TestClient.
"""

import pytest
import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

from fastapi.testclient import TestClient

from app.main import create_app
from app.api.routes import set_state
from app.services.store import StoreService
from app.config import Settings


@pytest.fixture
def app_client(tmp_path):
    """Create a test client with mocked services."""
    settings = Settings(
        GEMINI_API_KEY="test-key",
        DATA_DIR=str(tmp_path / "data"),
        CHUNK_SIZE=128,
        CHUNK_OVERLAP=16,
    )

    store = StoreService(tmp_path / "test.db")

    # Mock embedding service
    mock_embedding = MagicMock()
    mock_embedding.total_vectors = 0
    mock_embedding.add_chunks = MagicMock()
    mock_embedding.rebuild_index = MagicMock()

    # Mock RAG service
    mock_rag = MagicMock()
    mock_rag.answer = MagicMock(return_value={
        "answer": "A primary key uniquely identifies records.",
        "citations": [
            {
                "document_id": "doc-1",
                "document_name": "test.pdf",
                "chunk_id": "chunk-1",
                "page": 1,
                "excerpt": "A primary key is...",
                "score": 0.85,
            }
        ],
        "insufficient_context": False,
        "latency_ms": 150.0,
    })

    async def mock_answer_stream(*args, **kwargs):
        yield {
            "type": "metadata",
            "citations": [
                {
                    "document_id": "doc-1",
                    "document_name": "test.pdf",
                    "chunk_id": "chunk-1",
                    "page": 1,
                    "excerpt": "A primary key is...",
                    "score": 0.85,
                }
            ],
            "insufficient_context": False,
        }
        yield {"type": "token", "text": "A primary key "}
        yield {"type": "token", "text": "identifies records."}
        yield {"type": "done", "latency_ms": 110.0}

    mock_rag.answer_stream = mock_answer_stream

    # Mock study service
    mock_study = MagicMock()
    mock_study.generate_summary = MagicMock(return_value={
        "document_id": "doc-1",
        "document_name": "test.pdf",
        "summary": "This is a summary.",
    })
    mock_study.generate_mcqs = MagicMock(return_value={
        "document_id": "doc-1",
        "document_name": "test.pdf",
        "questions": [{
            "question": "What is X?",
            "options": [
                {"label": "A", "text": "Option A"},
                {"label": "B", "text": "Option B"},
                {"label": "C", "text": "Option C"},
                {"label": "D", "text": "Option D"},
            ],
            "correct_answer": "A",
            "explanation": "Because...",
        }],
    })
    mock_study.generate_flashcards = MagicMock(return_value={
        "document_id": "doc-1",
        "document_name": "test.pdf",
        "flashcards": [{"front": "Q?", "back": "A."}],
    })
    mock_study.generate_viva = MagicMock(return_value={
        "document_id": "doc-1",
        "document_name": "test.pdf",
        "questions": [{"question": "Explain X.", "category": "Conceptual", "model_answer": "X is..."}],
    })

    set_state({
        "settings": settings,
        "store": store,
        "embedding_service": mock_embedding,
        "retrieval_service": MagicMock(),
        "rag_service": mock_rag,
        "study_service": mock_study,
    })

    # Create app without lifespan (we set state manually)
    from fastapi import FastAPI
    from app.api.routes import router
    app = FastAPI()
    app.include_router(router)

    return TestClient(app), store, mock_rag, mock_study


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health(self, app_client):
        client, _, _, _ = app_client
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["gemini_configured"] is True


class TestDocumentEndpoints:
    """Tests for document endpoints."""

    def test_list_documents_empty(self, app_client):
        client, _, _, _ = app_client
        response = client.get("/documents")
        assert response.status_code == 200
        assert response.json()["documents"] == []

    def test_upload_unsupported_file(self, app_client):
        client, _, _, _ = app_client
        response = client.post(
            "/documents/upload",
            files={"file": ("test.docx", b"content", "application/octet-stream")},
        )
        assert response.status_code == 415

    def test_upload_empty_file(self, app_client):
        client, _, _, _ = app_client
        response = client.post(
            "/documents/upload",
            files={"file": ("test.txt", b"", "text/plain")},
        )
        assert response.status_code == 422

    def test_upload_txt_file(self, app_client):
        client, store, _, _ = app_client
        content = b"This is a test document with enough content for chunking. " * 10
        response = client.post(
            "/documents/upload",
            files={"file": ("notes.txt", content, "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "notes.txt"
        assert data["file_type"] == "txt"
        assert data["num_chunks"] > 0

    def test_delete_document(self, app_client):
        client, store, _, _ = app_client
        # Create a document first
        content = b"Test content for deletion. " * 20
        upload_resp = client.post(
            "/documents/upload",
            files={"file": ("delete_me.txt", content, "text/plain")},
        )
        doc_id = upload_resp.json()["id"]

        # Delete it
        response = client.delete(f"/documents/{doc_id}")
        assert response.status_code == 200
        assert response.json()["document_id"] == doc_id

        # Verify it's gone
        assert store.get_document(doc_id) is None

    def test_delete_nonexistent(self, app_client):
        client, _, _, _ = app_client
        response = client.delete("/documents/nonexistent-id")
        assert response.status_code == 404

    def test_get_document_file_success(self, app_client):
        client, store, _, _ = app_client
        content = b"Content for preview streaming test. " * 15
        upload_resp = client.post(
            "/documents/upload",
            files={"file": ("preview_test.txt", content, "text/plain")},
        )
        assert upload_resp.status_code == 201
        doc_id = upload_resp.json()["id"]

        # Fetch file stream
        response = client.get(f"/documents/{doc_id}/file")
        assert response.status_code == 200
        assert "preview_test.txt" in response.headers.get("content-disposition", "")
        assert content in response.content

    def test_get_document_file_nonexistent(self, app_client):
        client, _, _, _ = app_client
        response = client.get("/documents/nonexistent-id-12345/file")
        assert response.status_code == 404


class TestChatEndpoint:
    """Tests for the chat endpoint."""

    def test_chat_success(self, app_client):
        client, store, mock_rag, _ = app_client
        response = client.post("/chat", json={
            "question": "What is a primary key?",
        })
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "citations" in data
        assert "latency_ms" in data

    def test_chat_with_document_filter(self, app_client):
        client, store, mock_rag, _ = app_client
        # Create a document
        doc = store.create_document("test.pdf", "pdf", 100)
        response = client.post("/chat", json={
            "question": "Explain this",
            "document_id": doc["id"],
        })
        assert response.status_code == 200

    def test_chat_missing_document(self, app_client):
        client, _, _, _ = app_client
        response = client.post("/chat", json={
            "question": "test",
            "document_id": "nonexistent",
        })
        assert response.status_code == 404

    def test_chat_empty_question(self, app_client):
        client, _, _, _ = app_client
        response = client.post("/chat", json={
            "question": "",
        })
        assert response.status_code == 422

    def test_chat_with_history(self, app_client):
        client, _, mock_rag, _ = app_client
        response = client.post("/chat", json={
            "question": "What about foreign keys?",
            "history": [
                {"role": "user", "content": "Explain database keys."},
                {"role": "assistant", "content": "Keys identify records."},
            ],
        })
        assert response.status_code == 200

    def test_chat_stream_success(self, app_client):
        client, store, mock_rag, _ = app_client
        response = client.post("/chat/stream", json={
            "question": "What is a primary key?",
        })
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "event: metadata" in body
        assert "event: token" in body
        assert "event: done" in body


class TestStudyToolEndpoints:
    """Tests for study tool endpoints."""

    def test_summary(self, app_client):
        client, store, _, _ = app_client
        doc = store.create_document("test.pdf", "pdf", 100)
        response = client.post("/study-tools/summary", json={
            "document_id": doc["id"],
        })
        assert response.status_code == 200
        assert "summary" in response.json()

    def test_mcqs(self, app_client):
        client, store, _, _ = app_client
        doc = store.create_document("test.pdf", "pdf", 100)
        response = client.post("/study-tools/mcqs", json={
            "document_id": doc["id"],
            "num_items": 3,
        })
        assert response.status_code == 200
        assert "questions" in response.json()

    def test_flashcards(self, app_client):
        client, store, _, _ = app_client
        doc = store.create_document("test.pdf", "pdf", 100)
        response = client.post("/study-tools/flashcards", json={
            "document_id": doc["id"],
        })
        assert response.status_code == 200
        assert "flashcards" in response.json()

    def test_viva(self, app_client):
        client, store, _, _ = app_client
        doc = store.create_document("test.pdf", "pdf", 100)
        response = client.post("/study-tools/viva", json={
            "document_id": doc["id"],
        })
        assert response.status_code == 200
        assert "questions" in response.json()

    def test_invalid_num_items(self, app_client):
        client, store, _, _ = app_client
        doc = store.create_document("test.pdf", "pdf", 100)
        response = client.post("/study-tools/mcqs", json={
            "document_id": doc["id"],
            "num_items": 0,
        })
        assert response.status_code == 422

    def test_num_items_too_large(self, app_client):
        client, store, _, _ = app_client
        doc = store.create_document("test.pdf", "pdf", 100)
        response = client.post("/study-tools/mcqs", json={
            "document_id": doc["id"],
            "num_items": 50,
        })
        assert response.status_code == 422
