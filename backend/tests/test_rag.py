"""
Tests for RAGService: Dynamic hybrid retrieval, multimodal context formatting, and streaming citations.
"""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

from app.models.schemas import ChatMessage, Citation
from app.services.store import StoreService
from app.services.retrieval import RetrievalService, RetrievalResult
from app.services.rag import RAGService, INSUFFICIENT_CONTEXT_MSG
from app.services.llm import LLMService


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeRetrievalService:
    """Mock retrieval service returning configurable document and video results."""

    def __init__(self, doc_results: list[RetrievalResult], vid_results: list[RetrievalResult]):
        self.doc_results = doc_results
        self.vid_results = vid_results
        self.store = MagicMock()
        self.store.count_videos.return_value = len(vid_results)
        self.store.count_documents.return_value = len(doc_results)

    def retrieve(self, query: str, top_k: int = 5, document_id=None, video_id=None, source_type="all", threshold=0.0):
        if source_type == "document":
            return self.doc_results[:top_k]
        elif source_type == "video":
            return self.vid_results[:top_k]
        # "all" - by default return doc_results first
        combined = self.doc_results + self.vid_results
        return combined[:top_k]

    async def retrieve_async(self, query: str, top_k: int = 5, document_id=None, video_id=None, source_mode="all", threshold=0.0):
        return self.retrieve(query, top_k, document_id, video_id, source_mode, threshold)


@pytest.fixture
def rag_test_env():
    """Set up mock LLM and test results."""
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.generate.return_value = "Neural networks use backpropagation to optimize weights [Passage 1, Passage 2]."
    
    async def fake_stream(*args, **kwargs):
        for t in ["Neural ", "networks ", "use ", "backpropagation."]:
            yield t
    mock_llm.generate_stream = fake_stream

    doc_res = [
        RetrievalResult(
            chunk_id="doc_chunk_1",
            document_id="doc_1",
            document_name="deep_learning.pdf",
            text="Backpropagation calculates gradients of the loss function.",
            page=42,
            score=0.92,
            source_type="document",
        ),
        RetrievalResult(
            chunk_id="doc_chunk_2",
            document_id="doc_1",
            document_name="deep_learning.pdf",
            text="Activation functions introduce non-linearity.",
            page=43,
            score=0.85,
            source_type="document",
        ),
    ]

    vid_res = [
        RetrievalResult(
            chunk_id="vid_chunk_1",
            text="Let's visualize gradient descent stepping down the error surface.",
            score=0.89,
            source_type="video",
            video_id="vid_1",
            video_title="Neural Networks Chapter 2",
            channel="3Blue1Brown",
            start_time=125.0,
            end_time=195.0,
            timestamp_url="https://www.youtube.com/watch?v=vid123&t=125s",
        )
    ]

    retrieval = FakeRetrievalService(doc_res, vid_res)
    rag = RAGService(retrieval, mock_llm, top_k=4, similarity_threshold=0.25)

    return {
        "rag": rag,
        "llm": mock_llm,
        "retrieval": retrieval,
        "doc_res": doc_res,
        "vid_res": vid_res,
    }


class TestMultimodalRAG:
    """Test suite for Combined Document + Video RAG."""

    def test_answer_all_sources(self, rag_test_env):
        rag = rag_test_env["rag"]
        resp = rag.answer(
            question="How does backpropagation work?",
            source_mode="all"
        )
        assert resp["insufficient_context"] is False
        assert len(resp["citations"]) == 3

        # Check document citation
        doc_cit = next(c for c in resp["citations"] if c.source_type == "document")
        assert doc_cit.document_name == "deep_learning.pdf"
        assert doc_cit.page == 42

        # Check video citation
        vid_cit = next(c for c in resp["citations"] if c.source_type == "video")
        assert vid_cit.video_title == "Neural Networks Chapter 2"
        assert vid_cit.channel == "3Blue1Brown"
        assert vid_cit.start_time == 125.0
        assert "&t=125s" in vid_cit.timestamp_url

    def test_answer_documents_only_mode(self, rag_test_env):
        rag = rag_test_env["rag"]
        resp = rag.answer(
            question="What is backpropagation?",
            source_mode="documents"
        )
        assert len(resp["citations"]) == 2
        for c in resp["citations"]:
            assert c.source_type == "document"

    def test_answer_videos_only_mode(self, rag_test_env):
        rag = rag_test_env["rag"]
        resp = rag.answer(
            question="Show me gradient descent",
            source_mode="videos"
        )
        assert len(resp["citations"]) == 1
        assert resp["citations"][0].source_type == "video"
        assert resp["citations"][0].video_id == "vid_1"

    def test_context_formatting(self, rag_test_env):
        rag = rag_test_env["rag"]
        combined = rag_test_env["doc_res"] + rag_test_env["vid_res"]
        context_str = rag._build_context(combined)

        assert "📄 Document: deep_learning.pdf" in context_str
        assert "Page 42" in context_str
        assert "🎬 Video: Neural Networks Chapter 2" in context_str
        assert "Time: 02:05 - 03:15" in context_str

    def test_insufficient_context_refusal(self, rag_test_env):
        rag = rag_test_env["rag"]
        # Empty retrieval
        empty_retrieval = FakeRetrievalService([], [])
        rag.retrieval = empty_retrieval

        resp = rag.answer("What is quantum entanglement?")
        assert resp["insufficient_context"] is True
        assert resp["citations"] == []
        assert "relevant information" in resp["answer"]

    @pytest.mark.anyio
    async def test_streaming_emits_mixed_citations(self, rag_test_env):
        rag = rag_test_env["rag"]
        events = []
        async for evt in rag.answer_stream("Explain neural networks", source_mode="all"):
            events.append(evt)

        # First event must be metadata
        assert events[0]["type"] == "metadata"
        assert len(events[0]["citations"]) == 3
        types = {c["source_type"] for c in events[0]["citations"]}
        assert "document" in types
        assert "video" in types

        # Following events are tokens
        token_events = [e for e in events if e["type"] == "token"]
        assert len(token_events) == 4

        # Last event is done
        assert events[-1]["type"] == "done"
        assert events[-1]["latency_ms"] >= 0
