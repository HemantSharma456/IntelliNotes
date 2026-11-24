"""
Tests for the store service (SQLite operations).
"""

import pytest
import tempfile
from pathlib import Path

from app.services.store import StoreService


@pytest.fixture
def store(tmp_path):
    """Create a fresh store with a temporary database."""
    db_path = tmp_path / "test.db"
    return StoreService(db_path)


class TestDocumentCRUD:
    """Tests for document create/read/delete."""

    def test_create_document(self, store):
        """Create a document and verify its metadata."""
        doc = store.create_document("test.pdf", "pdf", 1024, num_pages=5)
        assert doc["id"]
        assert doc["filename"] == "test.pdf"
        assert doc["file_type"] == "pdf"
        assert doc["file_size"] == 1024
        assert doc["num_pages"] == 5
        assert doc["created_at"]

    def test_get_document(self, store):
        """Retrieve a document by ID."""
        doc = store.create_document("test.txt", "txt", 512)
        fetched = store.get_document(doc["id"])
        assert fetched is not None
        assert fetched["filename"] == "test.txt"

    def test_get_nonexistent_document(self, store):
        """Returns None for missing document."""
        assert store.get_document("nonexistent-id") is None

    def test_get_all_documents(self, store):
        """List all documents."""
        store.create_document("a.pdf", "pdf", 100)
        store.create_document("b.txt", "txt", 200)
        docs = store.get_all_documents()
        assert len(docs) == 2

    def test_delete_document(self, store):
        """Delete a document and verify it's gone."""
        doc = store.create_document("del.pdf", "pdf", 100)
        assert store.delete_document(doc["id"]) is True
        assert store.get_document(doc["id"]) is None

    def test_delete_nonexistent(self, store):
        """Deleting a missing document returns False."""
        assert store.delete_document("nonexistent") is False

    def test_count_documents(self, store):
        """Count documents."""
        assert store.count_documents() == 0
        store.create_document("a.pdf", "pdf", 100)
        assert store.count_documents() == 1
        store.create_document("b.pdf", "pdf", 200)
        assert store.count_documents() == 2


class TestChunkCRUD:
    """Tests for chunk storage."""

    def test_store_and_retrieve_chunks(self, store):
        """Store chunks and retrieve by document ID."""
        doc = store.create_document("test.pdf", "pdf", 1000, num_pages=2)
        chunks = [
            {"text": "First chunk", "page": 1, "start_char": 0, "end_char": 11},
            {"text": "Second chunk", "page": 2, "start_char": 11, "end_char": 23},
        ]
        chunk_ids = store.store_chunks(doc["id"], chunks)
        assert len(chunk_ids) == 2

        retrieved = store.get_chunks_by_document(doc["id"])
        assert len(retrieved) == 2
        assert retrieved[0]["text"] == "First chunk"
        assert retrieved[0]["page"] == 1

    def test_get_chunk_by_id(self, store):
        """Retrieve a single chunk by ID."""
        doc = store.create_document("test.pdf", "pdf", 1000)
        chunk_ids = store.store_chunks(doc["id"], [
            {"text": "Test chunk", "page": 1, "start_char": 0, "end_char": 10}
        ])
        chunk = store.get_chunk(chunk_ids[0])
        assert chunk is not None
        assert chunk["text"] == "Test chunk"

    def test_chunks_by_ids(self, store):
        """Retrieve multiple chunks by IDs."""
        doc = store.create_document("test.pdf", "pdf", 1000)
        chunk_ids = store.store_chunks(doc["id"], [
            {"text": "Chunk A", "page": 1, "start_char": 0, "end_char": 7},
            {"text": "Chunk B", "page": 1, "start_char": 7, "end_char": 14},
        ])
        chunks = store.get_chunks_by_ids(chunk_ids)
        assert len(chunks) == 2

    def test_cascade_delete(self, store):
        """Deleting a document removes its chunks."""
        doc = store.create_document("test.pdf", "pdf", 1000)
        chunk_ids = store.store_chunks(doc["id"], [
            {"text": "Test", "page": 1, "start_char": 0, "end_char": 4}
        ])
        store.delete_document(doc["id"])
        assert store.get_chunk(chunk_ids[0]) is None
        assert store.get_chunks_by_document(doc["id"]) == []

    def test_all_chunk_ids(self, store):
        """Get all chunk IDs after deletion excludes deleted ones."""
        doc1 = store.create_document("a.pdf", "pdf", 100)
        doc2 = store.create_document("b.pdf", "pdf", 100)
        ids1 = store.store_chunks(doc1["id"], [
            {"text": "A", "page": 1, "start_char": 0, "end_char": 1}
        ])
        ids2 = store.store_chunks(doc2["id"], [
            {"text": "B", "page": 1, "start_char": 0, "end_char": 1}
        ])

        all_ids = store.get_all_chunk_ids()
        assert len(all_ids) == 2

        store.delete_document(doc1["id"])
        remaining = store.get_all_chunk_ids()
        assert len(remaining) == 1
        assert remaining[0] == ids2[0]

    def test_empty_chunks_list(self, store):
        """Getting chunks by empty ID list returns empty."""
        assert store.get_chunks_by_ids([]) == []


class TestStudyCache:
    """Tests for study tools caching in SQLite."""

    def test_cache_miss_returns_none(self, store):
        assert store.get_study_cache("doc-1", "summary", 0) is None

    def test_cache_set_and_hit(self, store):
        doc = store.create_document("test.pdf", "pdf", 100)
        sample = {"document_id": doc["id"], "summary": "Key summary points"}
        store.set_study_cache(doc["id"], "summary", sample, 0)

        hit = store.get_study_cache(doc["id"], "summary", 0)
        assert hit is not None
        assert hit["summary"] == "Key summary points"

    def test_cache_cascade_on_document_delete(self, store):
        doc = store.create_document("test.pdf", "pdf", 100)
        sample = {"document_id": doc["id"], "summary": "Sample"}
        store.set_study_cache(doc["id"], "summary", sample, 0)

        store.delete_document(doc["id"])
        assert store.get_study_cache(doc["id"], "summary", 0) is None

