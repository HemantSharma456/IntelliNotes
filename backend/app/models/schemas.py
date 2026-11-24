"""
Pydantic schemas for IntelliNotes API requests and responses.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


# ── Document Schemas ──────────────────────────────────────────────────────────


class DocumentMeta(BaseModel):
    """Metadata for an uploaded document."""
    id: str
    filename: str
    file_type: str
    file_size: int
    num_chunks: int
    num_pages: Optional[int] = None
    created_at: str


class DocumentListResponse(BaseModel):
    """Response containing a list of documents."""
    documents: list[DocumentMeta]


class DocumentDeleteResponse(BaseModel):
    """Confirmation of document deletion."""
    message: str
    document_id: str


# ── Chat Schemas ──────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """A single message in conversation history."""
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=10000)


class ChatRequest(BaseModel):
    """Request to ask a question about uploaded sources (documents and/or videos)."""
    question: str = Field(..., min_length=1, max_length=5000)
    document_id: Optional[str] = None
    video_id: Optional[str] = None
    source_mode: Optional[str] = "all"  # "all", "documents", "videos"
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class Citation(BaseModel):
    """A source citation for an answer (supporting both documents and video timestamps)."""
    source_type: str = "document"  # "document" or "video"
    chunk_id: str
    document_id: Optional[str] = None
    document_name: Optional[str] = None
    page: Optional[int] = None
    video_id: Optional[str] = None
    video_title: Optional[str] = None
    channel: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    timestamp_url: Optional[str] = None
    excerpt: str
    score: float


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""
    answer: str
    citations: list[Citation]
    insufficient_context: bool = False
    latency_ms: float


# ── Study Tool Schemas ────────────────────────────────────────────────────────


class StudyToolRequest(BaseModel):
    """Request for a study tool."""
    document_id: str
    num_items: int = Field(default=5, ge=1, le=20)


class SummaryResponse(BaseModel):
    """Generated summary of a document."""
    document_id: str
    document_name: str
    summary: str


class MCQOption(BaseModel):
    """A single option in a multiple-choice question."""
    label: str
    text: str


class MCQ(BaseModel):
    """A multiple-choice question."""
    question: str
    options: list[MCQOption]
    correct_answer: str
    explanation: str


class MCQResponse(BaseModel):
    """Generated MCQs from a document."""
    document_id: str
    document_name: str
    questions: list[MCQ]


class Flashcard(BaseModel):
    """A revision flashcard."""
    front: str
    back: str


class FlashcardResponse(BaseModel):
    """Generated flashcards from a document."""
    document_id: str
    document_name: str
    flashcards: list[Flashcard]


class VivaQuestion(BaseModel):
    """An oral-examination question with model answer."""
    question: str
    category: str
    model_answer: str


class VivaResponse(BaseModel):
    """Generated viva questions from a document."""
    document_id: str
    document_name: str
    questions: list[VivaQuestion]


# ── Health ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    gemini_configured: bool
    embedding_model: str
    documents_count: int


# ── Video Schemas ─────────────────────────────────────────────────────────────


class VideoMeta(BaseModel):
    """Metadata for an ingested video."""
    id: str
    youtube_id: str
    url: str
    title: str
    channel: Optional[str] = None
    duration: Optional[int] = None
    thumbnail_url: Optional[str] = None
    num_chunks: int = 0
    created_at: str


class VideoChunkMeta(BaseModel):
    """Timestamped chunk of video transcript."""
    id: str
    video_id: str
    chunk_index: int
    start_time: float
    end_time: float
    text: str
    timestamp_url: str


class VideoTimestampItem(BaseModel):
    """A chapter or key topic within the video with exact timestamp."""
    time_seconds: int
    timestamp_formatted: str
    topic: str
    description: str


class VideoSummaryResponse(BaseModel):
    """Timestamped AI summary of an ingested video."""
    video_id: str
    youtube_id: str
    video_title: str
    channel: Optional[str] = None
    summary: str
    timestamps: list[VideoTimestampItem] = []


class VideoSummaryRequest(BaseModel):
    """Request to generate timestamped summary for a video."""
    video_id: str
    force_refresh: bool = False


class VideoDetailResponse(BaseModel):
    """Detailed video information including transcript chunks."""
    video: VideoMeta
    chunks: list[VideoChunkMeta]


class VideoListResponse(BaseModel):
    """Response containing a list of ingested videos."""
    videos: list[VideoMeta]


class VideoIngestRequest(BaseModel):
    """Request to ingest a YouTube video."""
    url: str = Field(..., min_length=5, max_length=500)


class VideoIngestResponse(BaseModel):
    """Response returned upon video ingestion."""
    video: VideoMeta
    num_chunks: int


class VideoSearchRequest(BaseModel):
    """Request to perform semantic search specifically over video transcripts."""
    query: str = Field(..., min_length=1, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=20)
    video_id: Optional[str] = None
    threshold: float = Field(default=0.25, ge=0.0, le=1.0)


class VideoSearchResult(BaseModel):
    """Single matching video segment with exact timestamp link."""
    chunk_id: str
    video_id: str
    video_title: str
    channel: Optional[str] = None
    start_time: float
    end_time: float
    timestamp_url: str
    text: str
    score: float


class VideoSearchResponse(BaseModel):
    """Results from video transcript search."""
    results: list[VideoSearchResult]


class VideoSuggestion(BaseModel):
    """A recommended educational video for an uploaded document."""
    youtube_id: str = ""
    title: str
    channel: Optional[str] = None
    topic: str
    thumbnail_url: str = ""
    watch_url: str = ""
    search_url: str = ""
    rationale: str


class VideoSuggestionsResponse(BaseModel):
    """Generated video suggestions for a document."""
    document_id: str
    document_name: str
    suggestions: list[VideoSuggestion]


class VideoDeleteResponse(BaseModel):
    """Confirmation of video deletion."""
    message: str
    video_id: str


class WorkspaceVideoMatch(BaseModel):
    """A relevant video chunk match from the user's ingested workspace library."""
    chunk_id: str
    video_id: str
    video_title: str
    channel: Optional[str] = None
    start_time: float
    end_time: float
    timestamp_url: str
    text: str
    score: float


class VideoRecommendationResponse(BaseModel):
    """Curated educational video recommendations for an uploaded document."""
    document_id: str
    document_name: str
    suggestions: list[VideoSuggestion] = []
    workspace_matches: list[WorkspaceVideoMatch] = []
    external_suggestions: list[VideoSuggestion] = []
