/* === IntelliNotes Type Definitions === */

export interface DocumentMeta {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  num_chunks: number;
  num_pages: number | null;
  created_at: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface Citation {
  source_type?: 'document' | 'video';
  chunk_id: string;
  document_id?: string | null;
  document_name?: string | null;
  page?: number | null;
  video_id?: string | null;
  video_title?: string | null;
  channel?: string | null;
  start_time?: number | null;
  end_time?: number | null;
  timestamp_url?: string | null;
  excerpt: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  insufficient_context: boolean;
  latency_ms: number;
}

export interface StudyToolRequest {
  document_id: string;
  num_items?: number;
}

export interface SummaryResponse {
  document_id: string;
  document_name: string;
  summary: string;
}

export interface MCQOption {
  label: string;
  text: string;
}

export interface MCQ {
  question: string;
  options: MCQOption[];
  correct_answer: string;
  explanation: string;
}

export interface MCQResponse {
  document_id: string;
  document_name: string;
  questions: MCQ[];
}

export interface Flashcard {
  front: string;
  back: string;
}

export interface FlashcardResponse {
  document_id: string;
  document_name: string;
  flashcards: Flashcard[];
}

export interface VivaQuestion {
  question: string;
  category: string;
  model_answer: string;
}

export interface VivaResponse {
  document_id: string;
  document_name: string;
  questions: VivaQuestion[];
}

export interface HealthResponse {
  status: string;
  gemini_configured: boolean;
  embedding_model: string;
  documents_count: number;
}

export type StudyTool = 'preview' | 'summary' | 'mcqs' | 'flashcards' | 'viva' | 'videos';

export interface ConversationMessage extends ChatMessage {
  citations?: Citation[];
  insufficient_context?: boolean;
  latency_ms?: number;
  isStreaming?: boolean;
}

export type SourceMode = 'all' | 'documents' | 'videos';

export interface VideoMeta {
  id: string;
  youtube_id: string;
  url: string;
  title: string;
  channel?: string | null;
  duration?: number | null;
  thumbnail_url?: string | null;
  num_chunks: number;
  created_at: string;
}

export interface VideoChunkMeta {
  id: string;
  video_id: string;
  chunk_index: number;
  start_time: number;
  end_time: number;
  text: string;
  timestamp_url: string;
}

export interface VideoSuggestion {
  youtube_id: string;
  title: string;
  channel?: string | null;
  topic: string;
  thumbnail_url: string;
  watch_url: string;
  search_url?: string;
  rationale: string;
}

export interface WorkspaceVideoMatch {
  chunk_id: string;
  video_id: string;
  video_title: string;
  channel?: string | null;
  start_time: number;
  end_time: number;
  timestamp_url: string;
  text: string;
  score: number;
}

export interface VideoRecommendationResponse {
  document_id: string;
  document_name: string;
  suggestions?: VideoSuggestion[];
  workspace_matches: WorkspaceVideoMatch[];
  external_suggestions: VideoSuggestion[];
}

export interface VideoTimestampItem {
  time_seconds: number;
  timestamp_formatted: string;
  topic: string;
  description: string;
}

export interface VideoSummaryResponse {
  video_id: string;
  youtube_id: string;
  video_title: string;
  channel?: string | null;
  summary: string;
  timestamps: VideoTimestampItem[];
}

