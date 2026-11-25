import type {
  DocumentMeta,
  ChatMessage,
  ChatResponse,
  SummaryResponse,
  MCQResponse,
  FlashcardResponse,
  VivaResponse,
  HealthResponse,
  Citation,
  SourceMode,
  VideoMeta,
  VideoSuggestion,
  VideoRecommendationResponse,
  VideoSummaryResponse,
} from '../types';

const rawApiBase = import.meta.env.VITE_API_URL || '/api';
const API_BASE = rawApiBase.replace(/\/+$/, '');

class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = 'ApiError';
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
    },
  });

  if (!res.ok) {
    let detail = `Request failed with status ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // ignore parse errors
    }
    throw new ApiError(detail, res.status);
  }

  return res.json();
}

/* ── Health ── */

export async function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health');
}

/* ── Documents ── */

export async function uploadDocument(file: File): Promise<DocumentMeta> {
  const formData = new FormData();
  formData.append('file', file);
  return request<DocumentMeta>('/documents/upload', {
    method: 'POST',
    body: formData,
  });
}

export async function getDocuments(): Promise<{ documents: DocumentMeta[] }> {
  return request<{ documents: DocumentMeta[] }>('/documents');
}

export async function deleteDocument(
  documentId: string
): Promise<{ message: string; document_id: string }> {
  return request('/documents/' + documentId, {
    method: 'DELETE',
  });
}

export function getDocumentFileUrl(documentId: string): string {
  return `${API_BASE}/documents/${documentId}/file`;
}

/* ── Videos ── */

export async function getVideos(): Promise<{ videos: VideoMeta[] }> {
  return request<{ videos: VideoMeta[] }>('/videos');
}

export async function ingestVideo(url: string): Promise<{ video: VideoMeta; num_chunks: number }> {
  return request('/videos/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ url }),
  });
}

export async function deleteVideo(videoId: string): Promise<{ message: string; video_id: string }> {
  return request('/videos/' + videoId, {
    method: 'DELETE',
  });
}

export async function generateVideoSummary(
  videoId: string,
  forceRefresh: boolean = false
): Promise<VideoSummaryResponse> {
  return request<VideoSummaryResponse>('/study-tools/video-summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ video_id: videoId, force_refresh: forceRefresh }),
  });
}

export async function suggestVideosForDocument(
  documentId: string
): Promise<{ document_id: string; document_name: string; suggestions: VideoSuggestion[] }> {
  return request(`/documents/${documentId}/suggest-videos`, {
    method: 'POST',
  });
}

/* ── Chat ── */

export async function sendChatMessage(
  question: string,
  documentId?: string | null,
  history?: ChatMessage[],
  sourceMode: SourceMode = 'all',
  videoId?: string | null
): Promise<ChatResponse> {
  return request<ChatResponse>('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      document_id: documentId || null,
      video_id: videoId || null,
      source_mode: sourceMode,
      history: history || [],
    }),
  });
}

export interface StreamCallbacks {
  onMetadata?: (data: { citations: Citation[]; insufficient_context: boolean }) => void;
  onToken?: (token: string) => void;
  onDone?: (data: { latency_ms: number }) => void;
  onError?: (error: string) => void;
}

export async function streamChatMessage(
  question: string,
  documentId: string | null | undefined,
  history: ChatMessage[] = [],
  callbacks: StreamCallbacks,
  sourceMode: SourceMode = 'all',
  videoId?: string | null
): Promise<void> {
  const url = `${API_BASE}/chat/stream`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      document_id: documentId || null,
      video_id: videoId || null,
      source_mode: sourceMode,
      history,
    }),
  });

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // ignore
    }
    callbacks.onError?.(detail);
    return;
  }

  if (!response.body) {
    callbacks.onError?.('ReadableStream not supported by browser');
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const blocks = buffer.split('\n\n');
      buffer = blocks.pop() || '';

      for (const block of blocks) {
        if (!block.trim()) continue;
        const lines = block.split('\n');
        let eventType = 'message';
        let dataStr = '';

        for (const line of lines) {
          if (line.startsWith('event:')) {
            eventType = line.replace('event:', '').trim();
          } else if (line.startsWith('data:')) {
            dataStr = line.replace('data:', '').trim();
          }
        }

        if (!dataStr) continue;

        try {
          const payload = JSON.parse(dataStr);
          if (eventType === 'metadata') {
            callbacks.onMetadata?.({
              citations: payload.citations || [],
              insufficient_context: Boolean(payload.insufficient_context),
            });
          } else if (eventType === 'token') {
            callbacks.onToken?.(payload.text || '');
          } else if (eventType === 'done') {
            callbacks.onDone?.({ latency_ms: payload.latency_ms || 0 });
          } else if (eventType === 'error') {
            callbacks.onError?.(payload.error || 'Stream error');
          }
        } catch {
          // ignore malformed chunk
        }
      }
    }
  } catch (err: any) {
    callbacks.onError?.(err.message || 'Stream connection interrupted');
  }
}

/* ── Study Tools ── */

export async function generateSummary(
  documentId: string
): Promise<SummaryResponse> {
  return request<SummaryResponse>('/study-tools/summary', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId }),
  });
}

export async function generateMCQs(
  documentId: string,
  numItems: number = 5
): Promise<MCQResponse> {
  return request<MCQResponse>('/study-tools/mcqs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId, num_items: numItems }),
  });
}

export async function generateFlashcards(
  documentId: string,
  numItems: number = 10
): Promise<FlashcardResponse> {
  return request<FlashcardResponse>('/study-tools/flashcards', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId, num_items: numItems }),
  });
}

export async function generateViva(
  documentId: string,
  numItems: number = 8
): Promise<VivaResponse> {
  return request<VivaResponse>('/study-tools/viva', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ document_id: documentId, num_items: numItems }),
  });
}

export async function getVideoRecommendations(
  documentId: string,
  forceRefresh: boolean = false
): Promise<VideoRecommendationResponse> {
  return request<VideoRecommendationResponse>(
    `/documents/${documentId}/video-recommendations?force_refresh=${forceRefresh}`
  );
}

export { ApiError };
