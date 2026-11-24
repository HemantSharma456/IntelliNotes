import { useState, useRef } from 'react';
import {
  Upload,
  FileText,
  Trash2,
  BookOpen,
  Plus,
  Loader2,
  Check,
  X,
  Video,
  Link as LinkIcon,
  MessageSquare,
} from 'lucide-react';
import type { DocumentMeta, VideoMeta } from '../types';
import { uploadDocument, deleteDocument, ingestVideo, deleteVideo } from '../services/api';

interface SidebarProps {
  documents: DocumentMeta[];
  videos?: VideoMeta[];
  selectedDocId: string | null;
  selectedVideoId?: string | null;
  activeView?: 'tools' | 'chat';
  onSelectView?: (view: 'tools' | 'chat') => void;
  onSelectDocument: (id: string | null) => void;
  onSelectVideo?: (id: string | null) => void;
  onDocumentsChange: () => void;
  onVideosChange?: () => void;
  onPlayVideo?: (req: { youtubeId: string; title: string; channel?: string | null; startTime?: number }) => void;
}

export default function Sidebar({
  documents,
  videos = [],
  selectedDocId,
  selectedVideoId = null,
  activeView = 'tools',
  onSelectView,
  onSelectDocument,
  onSelectVideo,
  onDocumentsChange,
  onVideosChange,
}: SidebarProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // Video Ingestion State
  const [showAddVideo, setShowAddVideo] = useState(false);
  const [videoUrlInput, setVideoUrlInput] = useState('');
  const [ingestingVideo, setIngestingVideo] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleProcessFile = async (file: File) => {
    if (!file) return;
    setUploading(true);
    setUploadError(null);

    try {
      await uploadDocument(file);
      onDocumentsChange();
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleProcessFile(file);
  };

  const handleDeleteDoc = async (docId: string) => {
    setDeletingId(docId);
    try {
      await deleteDocument(docId);
      if (selectedDocId === docId) onSelectDocument(null);
      onDocumentsChange();
    } catch (err: any) {
      setUploadError(err.message || 'Delete failed');
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const handleIngestVideo = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!videoUrlInput.trim()) return;

    setIngestingVideo(true);
    setVideoError(null);

    try {
      const res = await ingestVideo(videoUrlInput.trim());
      setVideoUrlInput('');
      setShowAddVideo(false);
      if (onVideosChange) onVideosChange();
      if (onSelectVideo && res.video) {
        onSelectVideo(res.video.id);
      }
    } catch (err: any) {
      setVideoError(err.message || 'Failed to ingest video. Ensure it has public English captions.');
    } finally {
      setIngestingVideo(false);
    }
  };

  const handleDeleteVideo = async (videoId: string) => {
    setDeletingId(videoId);
    try {
      await deleteVideo(videoId);
      if (selectedVideoId === videoId && onSelectVideo) onSelectVideo(null);
      if (onVideosChange) onVideosChange();
    } catch (err: any) {
      setVideoError(err.message || 'Failed to delete video');
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  return (
    <aside className="w-[272px] min-w-[272px] max-w-[272px] h-full flex flex-col bg-[#f4f0e4] border-r border-[#e3ddd0] select-none shrink-0 overflow-hidden text-[#1C1917]">

      {/* ── Brand Header ── */}
      <div className="h-13 px-4 flex items-center justify-between shrink-0 border-b border-[#ddd7c8]/80">
        <div className="flex items-center gap-2.5">
          {/* Logo mark */}
          <div className="w-8 h-8 rounded-xl bg-[#1a1714] flex items-center justify-center shadow-sm shrink-0">
            <BookOpen size={15} className="text-[#fde047]" />
          </div>
          <div className="flex flex-col leading-tight">
            <span className="font-sans text-[13.5px] font-700 tracking-tight text-[#1C1917]">IntelliQ Notes</span>
            <span className="text-[9.5px] font-semibold uppercase tracking-widest text-[#a8a29e]">AI Study Agent</span>
          </div>
        </div>

        {/* Quick upload shortcut */}
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#e5dfd2] transition-colors cursor-pointer disabled:opacity-40"
          title="Upload document"
        >
          <Plus size={16} />
        </button>
      </div>

      {/* ── Mode Switcher (Study Suite vs AI Tutor) ── */}
      <div className="p-2 pb-1 shrink-0 border-b border-[#ddd7c8]/60">
        <div className="grid grid-cols-2 gap-1 p-1 bg-[#e5dfd2]/80 rounded-xl border border-[#ddd7c8]">
          <button
            type="button"
            onClick={() => onSelectView?.('tools')}
            className={`py-1.5 px-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
              activeView === 'tools'
                ? 'bg-[#1a1714] text-white shadow-sm'
                : 'text-[#57534e] hover:text-[#1c1917]'
            }`}
          >
            <BookOpen size={12} className={activeView === 'tools' ? 'text-[#fde047]' : ''} />
            <span>Study Suite</span>
          </button>
          <button
            type="button"
            onClick={() => onSelectView?.('chat')}
            className={`py-1.5 px-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
              activeView === 'chat'
                ? 'bg-[#1a1714] text-white shadow-sm'
                : 'text-[#57534e] hover:text-[#1c1917]'
            }`}
          >
            <MessageSquare size={12} className={activeView === 'chat' ? 'text-[#fde047]' : ''} />
            <span>AI Tutor</span>
          </button>
        </div>
      </div>

      {/* ── Scrollable Body ── */}
      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col px-2 py-2 gap-1">

        {/* ── DOCUMENTS SECTION ── */}
        <div className="mt-1">
          <div className="flex items-center justify-between px-2 mb-1.5">
            <span className="text-[10px] font-700 uppercase tracking-widest text-[#a8a29e]">
              Documents
              {documents.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-[#eae3d4] text-[#78716c] text-[9px] font-semibold">{documents.length}</span>
              )}
            </span>
            <label
              className={`cursor-pointer inline-flex items-center gap-1 text-[11px] font-semibold text-[#854D0E] hover:text-[#713F12] transition-colors ${
                uploading ? 'opacity-40 pointer-events-none' : ''
              }`}
              title="Upload PDF or TXT"
            >
              {uploading ? (
                <Loader2 size={11} className="animate-spin" />
              ) : (
                <Upload size={11} />
              )}
              <span>{uploading ? 'Uploading…' : 'Upload'}</span>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.txt"
                onChange={handleFileSelect}
                disabled={uploading}
                className="hidden"
              />
            </label>
          </div>

          {/* Upload Error */}
          {uploadError && (
            <div className="mx-1 mb-2 p-2.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-[11px] flex items-center justify-between gap-1 animate-fade-in">
              <span className="truncate">{uploadError}</span>
              <button
                type="button"
                onClick={() => setUploadError(null)}
                className="text-rose-400 hover:text-rose-700 p-0.5 cursor-pointer shrink-0"
              >
                <X size={11} />
              </button>
            </div>
          )}

          {/* Upload Drop zone (shown when no documents) */}
          {documents.length === 0 && !uploading && (
            <div
              className="drop-zone mx-1 p-5 flex flex-col items-center gap-2 text-center cursor-pointer"
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="w-8 h-8 rounded-lg bg-[#fef08a] border border-[#eab308]/30 flex items-center justify-center text-[#854d0e]">
                <Upload size={15} />
              </div>
              <div>
                <p className="text-[11px] font-semibold text-[#44403c]">Drop a PDF here</p>
                <p className="text-[10px] text-[#a8a29e] mt-0.5">or click to browse</p>
              </div>
            </div>
          )}

          {/* Document List */}
          <div className="space-y-0.5 px-1">
            {documents.map((doc) => {
              const isSelected = selectedDocId === doc.id;
              return (
                <div
                  key={doc.id}
                  onClick={() => {
                    onSelectDocument(isSelected ? null : doc.id);
                    if (onSelectVideo) onSelectVideo(null);
                  }}
                  className={`group relative flex items-center justify-between gap-2 px-2.5 py-2 rounded-xl cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-[#fef9c3] text-[#713F12] font-semibold border border-[#eab308]/25 shadow-sm'
                      : 'text-[#44403C] hover:bg-[#eae3d4]/70 hover:text-[#1C1917]'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${isSelected ? 'bg-[#fde047] text-[#854d0e]' : 'bg-[#e5dfd2] text-[#78716c]'}`}>
                      <FileText size={12} />
                    </div>
                    <span className="text-[12px] truncate block" title={doc.filename}>
                      {doc.filename}
                    </span>
                  </div>

                  {confirmDeleteId === doc.id ? (
                    <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => handleDeleteDoc(doc.id)}
                        disabled={deletingId === doc.id}
                        className="p-1 rounded-lg bg-rose-100 text-rose-700 hover:bg-rose-200 cursor-pointer"
                        title="Confirm delete"
                      >
                        {deletingId === doc.id ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(null)}
                        className="p-1 rounded-lg bg-[#EAE3D4] text-[#57534E] hover:bg-[#DFD7C7] cursor-pointer"
                        title="Cancel"
                      >
                        <X size={11} />
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(doc.id); }}
                      className="opacity-0 group-hover:opacity-100 p-1 text-[#A8A29E] hover:text-rose-600 transition-opacity cursor-pointer shrink-0"
                      title="Delete document"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* ── Divider ── */}
        <div className="mx-2 my-2 border-t border-[#ddd7c8]/70" />

        {/* ── VIDEOS SECTION ── */}
        <div>
          <div className="flex items-center justify-between px-2 mb-1.5">
            <span className="text-[10px] font-700 uppercase tracking-widest text-[#a8a29e]">
              Videos
              {videos.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 rounded-full bg-[#eae3d4] text-[#78716c] text-[9px] font-semibold">{videos.length}</span>
              )}
            </span>
            <button
              type="button"
              onClick={() => { setShowAddVideo((v) => !v); setVideoError(null); }}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#854D0E] hover:text-[#713F12] transition-colors cursor-pointer"
            >
              <Plus size={11} />
              <span>Add Video</span>
            </button>
          </div>

          {/* Video URL Input */}
          {showAddVideo && (
            <form onSubmit={handleIngestVideo} className="mx-1 mb-2 p-3 rounded-xl bg-white border border-[#e7e2d7] shadow-sm space-y-2 animate-scale-in">
              <div className="flex items-center gap-1.5 text-xs text-[#854D0E] font-semibold">
                <LinkIcon size={12} />
                <span>Paste YouTube URL</span>
              </div>
              <input
                type="text"
                value={videoUrlInput}
                onChange={(e) => setVideoUrlInput(e.target.value)}
                placeholder="https://youtube.com/watch?v=..."
                disabled={ingestingVideo}
                className="w-full px-3 py-2 text-xs rounded-xl border border-[#e7e2d7] bg-[#faf8f0] text-[#1C1917] focus:outline-none focus:border-[#CA8A04] focus:ring-2 focus:ring-[#fef08a]/50 transition-all"
                autoFocus
              />
              {videoError && <p className="text-[10px] text-rose-600 leading-tight">{videoError}</p>}
              <div className="flex justify-end gap-1.5">
                <button
                  type="button"
                  onClick={() => { setShowAddVideo(false); setVideoError(null); setVideoUrlInput(''); }}
                  className="px-3 py-1.5 text-[11px] rounded-lg text-[#78716C] hover:bg-[#f0ece0] cursor-pointer transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={ingestingVideo || !videoUrlInput.trim()}
                  className="px-3 py-1.5 text-[11px] font-semibold rounded-lg bg-[#1a1714] hover:bg-[#2d2926] text-white flex items-center gap-1 cursor-pointer disabled:opacity-40 transition-colors"
                >
                  {ingestingVideo ? <Loader2 size={11} className="animate-spin" /> : null}
                  <span>{ingestingVideo ? 'Ingesting…' : 'Ingest'}</span>
                </button>
              </div>
            </form>
          )}

          {/* Video Empty State */}
          {videos.length === 0 && !showAddVideo && (
            <div className="mx-1 py-4 px-3 rounded-xl border border-dashed border-[#d6cfc0] bg-transparent text-center">
              <p className="text-[11px] text-[#a8a29e]">No videos yet</p>
              <p className="text-[10px] text-[#c4bdb0] mt-0.5">Add a YouTube lecture to get started</p>
            </div>
          )}

          {/* Video List */}
          <div className="space-y-0.5 px-1">
            {videos.map((vid) => {
              const isSelected = selectedVideoId === vid.id;
              return (
                <div
                  key={vid.id}
                  onClick={() => { if (onSelectVideo) onSelectVideo(isSelected ? null : vid.id); onSelectDocument(null); }}
                  className={`group relative flex items-center justify-between gap-2 px-2.5 py-2 rounded-xl cursor-pointer transition-all ${
                    isSelected
                      ? 'bg-[#fef9c3] text-[#713F12] font-semibold border border-[#eab308]/25 shadow-sm'
                      : 'text-[#44403C] hover:bg-[#eae3d4]/70 hover:text-[#1C1917]'
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${isSelected ? 'bg-[#fde047] text-[#854d0e]' : 'bg-rose-100 text-rose-600'}`}>
                      <Video size={11} />
                    </div>
                    <span className="text-[12px] truncate block" title={vid.title}>
                      {vid.title}
                    </span>
                  </div>

                  {confirmDeleteId === vid.id ? (
                    <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => handleDeleteVideo(vid.id)}
                        disabled={deletingId === vid.id}
                        className="p-1 rounded-lg bg-rose-100 text-rose-700 hover:bg-rose-200 cursor-pointer"
                        title="Confirm delete"
                      >
                        {deletingId === vid.id ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                      </button>
                      <button
                        type="button"
                        onClick={() => setConfirmDeleteId(null)}
                        className="p-1 rounded-lg bg-[#EAE3D4] text-[#57534E] hover:bg-[#DFD7C7] cursor-pointer"
                        title="Cancel"
                      >
                        <X size={11} />
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(vid.id); }}
                      className="opacity-0 group-hover:opacity-100 p-1 text-[#A8A29E] hover:text-rose-600 transition-opacity cursor-pointer shrink-0"
                      title="Delete video"
                    >
                      <Trash2 size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Sidebar Footer ── */}
      {(selectedDocId || selectedVideoId) && (
        <div className="p-2 border-t border-[#ddd7c8]/70 shrink-0">
          <button
            type="button"
            onClick={() => { onSelectDocument(null); if (onSelectVideo) onSelectVideo(null); }}
            className="w-full py-2 text-[11px] font-semibold text-[#854D0E] hover:text-[#713F12] hover:bg-[#FEF9C3] rounded-xl transition-colors text-center cursor-pointer"
          >
            ✕ Clear Selection
          </button>
        </div>
      )}
    </aside>
  );
}
