import { useState, useEffect, useCallback } from 'react';
import {
  Menu,
  X,
  Key,
  Copy,
  Check,
  BookOpen,
  Bot,
} from 'lucide-react';
import Sidebar from './components/Sidebar';
import StudyToolsView from './components/StudyToolsView';
import ChatView from './components/ChatView';
import VideoPlayerModal, { type VideoPlayRequest } from './components/VideoPlayerModal';
import { getDocuments, getHealth, getVideos } from './services/api';
import type { DocumentMeta, HealthResponse, VideoMeta, ConversationMessage } from './types';

export default function App() {
  const [documents, setDocuments] = useState<DocumentMeta[]>([]);
  const [videos, setVideos] = useState<VideoMeta[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [selectedVideoId, setSelectedVideoId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<'tools' | 'chat'>('tools');
  const [chatMessages, setChatMessages] = useState<ConversationMessage[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showKeyModal, setShowKeyModal] = useState(false);
  const [copiedKeyText, setCopiedKeyText] = useState(false);
  const [activeVideoModal, setActiveVideoModal] = useState<VideoPlayRequest | null>(null);

  // Fetch documents list
  const refreshDocuments = useCallback(async () => {
    try {
      const res = await getDocuments();
      setDocuments(res.documents || []);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
    }
  }, []);

  // Fetch videos list
  const refreshVideos = useCallback(async () => {
    try {
      const res = await getVideos();
      setVideos(res.videos || []);
    } catch (err) {
      console.error('Failed to fetch videos:', err);
    }
  }, []);

  // Fetch health status
  const checkHealth = useCallback(async () => {
    try {
      const h = await getHealth();
      setHealth(h);
    } catch {
      setHealth(null);
    }
  }, []);

  useEffect(() => {
    refreshDocuments();
    refreshVideos();
    checkHealth();
    const interval = setInterval(checkHealth, 20000);
    return () => clearInterval(interval);
  }, [refreshDocuments, refreshVideos, checkHealth]);

  const copyConfigSnippet = () => {
    navigator.clipboard.writeText('GEMINI_API_KEY=your_key_here\nGEMINI_MODEL=gemini-3.8-flash');
    setCopiedKeyText(true);
    setTimeout(() => setCopiedKeyText(false), 2000);
  };

  return (
    <div className="flex h-screen w-screen bg-[#faf8f0] text-[#1C1917] overflow-hidden font-sans select-none">

      {/* ── Mobile Sidebar Overlay ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden backdrop-blur-sm transition-opacity animate-fade-in"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <div
        className={`fixed md:static inset-y-0 left-0 z-50 w-[272px] min-w-[272px] max-w-[272px] shrink-0 h-full transform md:transform-none transition-transform duration-250 ease-in-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        <Sidebar
          documents={documents}
          videos={videos}
          selectedDocId={selectedDocId}
          selectedVideoId={selectedVideoId}
          activeView={activeView}
          onSelectView={setActiveView}
          onSelectDocument={(id) => {
            setSelectedDocId(id);
            if (id) setSelectedVideoId(null);
            setSidebarOpen(false);
          }}
          onSelectVideo={(id) => {
            setSelectedVideoId(id);
            if (id) setSelectedDocId(null);
            setSidebarOpen(false);
          }}
          onDocumentsChange={refreshDocuments}
          onVideosChange={refreshVideos}
          onPlayVideo={setActiveVideoModal}
        />
      </div>

      {/* ── Main Workspace ── */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">

        {/* ── Top Header Bar ── */}
        <header className="h-13 px-4 md:px-5 bg-[#faf8f0]/90 border-b border-[#e7e2d7] flex items-center justify-between shrink-0 z-20 backdrop-blur-md sticky top-0">

          {/* Left: mobile toggle + context label */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#eee8dc] md:hidden transition-colors cursor-pointer"
              title="Toggle sidebar"
            >
              {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
            </button>

            {/* Breadcrumb context */}
            <div className="hidden md:flex items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-widest text-[#a8a29e]">
                IntelliQ Notes
              </span>
              <span className="text-[#d6cfc0]">/</span>
              <span className="text-[12px] font-medium text-[#78716c]">
                {activeView === 'chat'
                  ? 'AI Tutor Chat'
                  : selectedVideoId
                  ? 'Video Study Suite'
                  : selectedDocId
                  ? 'Document Workspace'
                  : 'Study Hub'}
              </span>
            </div>
          </div>

          {/* Center Mode Switcher Tabs (Study Suite vs AI Tutor) */}
          <div className="flex items-center gap-0.5 bg-[#e5dfd2]/80 p-0.5 sm:p-1 rounded-2xl border border-[#ddd7c8]">
            <button
              type="button"
              onClick={() => setActiveView('tools')}
              className={`px-3 py-1 sm:px-3.5 sm:py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
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
              onClick={() => setActiveView('chat')}
              className={`px-3 py-1 sm:px-3.5 sm:py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all cursor-pointer ${
                activeView === 'chat'
                  ? 'bg-[#1a1714] text-white shadow-sm'
                  : 'text-[#57534e] hover:text-[#1c1917]'
              }`}
            >
              <Bot size={12} className={activeView === 'chat' ? 'text-[#fde047]' : ''} />
              <span>AI Tutor</span>
            </button>
          </div>

          {/* Right: AI status + key config */}
          <div className="flex items-center gap-2">
            {health?.status === 'ok' && !health.gemini_configured && (
              <button
                type="button"
                onClick={() => setShowKeyModal(true)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-semibold bg-[#FEF08A] hover:bg-[#fde047] text-[#713F12] border border-[#EAB308]/40 transition-all cursor-pointer shadow-sm"
                title="Configure Gemini API Key"
              >
                <Key size={11} />
                <span>Configure AI Key</span>
              </button>
            )}

            {health?.status === 'ok' && health.gemini_configured && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span className="text-[10.5px] font-semibold text-emerald-700">AI Online</span>
              </div>
            )}
          </div>
        </header>

        {/* ── Workspace Body ── */}
        <main className="flex-1 flex flex-col min-h-0 overflow-hidden bg-[#faf8f0]">
          {activeView === 'tools' ? (
            <StudyToolsView
              documents={documents}
              videos={videos}
              selectedDocId={selectedDocId}
              selectedVideoId={selectedVideoId}
              onSelectDocument={(id) => {
                setSelectedDocId(id);
                if (id) setSelectedVideoId(null);
              }}
              onSelectVideo={(id) => {
                setSelectedVideoId(id);
                if (id) setSelectedDocId(null);
              }}
              onPlayVideo={setActiveVideoModal}
            />
          ) : (
            <ChatView
              selectedDoc={documents.find((d) => d.id === selectedDocId) || null}
              messages={chatMessages}
              setMessages={setChatMessages}
              onOpenStudyTools={() => setActiveView('tools')}
              onPlayVideo={setActiveVideoModal}
            />
          )}
        </main>
      </div>

      {/* ── Video Player Modal ── */}
      <VideoPlayerModal
        video={activeVideoModal}
        onClose={() => setActiveVideoModal(null)}
      />

      {/* ── API Key Setup Modal ── */}
      {showKeyModal && (
        <div
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
          onClick={() => setShowKeyModal(false)}
        >
          <div
            className="w-full max-w-md bg-white border border-[#e7e2d7] rounded-2xl p-6 shadow-2xl space-y-4 animate-scale-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between pb-3 border-b border-[#f0ece0]">
              <div className="flex items-center gap-2.5 text-[#1C1917] font-semibold text-sm">
                <div className="w-8 h-8 rounded-xl bg-[#FEF08A] text-[#854D0E] flex items-center justify-center border border-[#EAB308]/30 shadow-sm">
                  <Key size={15} />
                </div>
                <span>Gemini API Setup</span>
              </div>
              <button
                type="button"
                onClick={() => setShowKeyModal(false)}
                className="w-7 h-7 rounded-lg flex items-center justify-center text-[#78716C] hover:text-[#1C1917] hover:bg-[#f4f0e4] transition-colors cursor-pointer"
              >
                <X size={14} />
              </button>
            </div>

            <p className="text-xs text-[#57534E] leading-relaxed">
              Configure your Gemini API key in the backend to enable AI-grounded chat, summaries, quizzes, and flashcards.
            </p>

            <div className="p-3.5 rounded-xl bg-[#faf8f0] border border-[#e7e2d7] space-y-1.5 text-xs font-mono">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[#78716C] text-[11px] font-sans font-medium">backend/.env</span>
                <button
                  type="button"
                  onClick={copyConfigSnippet}
                  className="flex items-center gap-1 text-[11px] text-[#854D0E] hover:text-[#713F12] cursor-pointer font-sans font-medium transition-colors"
                >
                  {copiedKeyText ? <Check size={11} className="text-emerald-600" /> : <Copy size={11} />}
                  <span>{copiedKeyText ? 'Copied!' : 'Copy'}</span>
                </button>
              </div>
              <p className="text-[#854D0E] font-medium select-all">GEMINI_API_KEY=AIzaSy...your_key_here</p>
              <p className="text-[#78716C]">GEMINI_MODEL=gemini-3.8-flash</p>
            </div>

            <div className="text-[11px] text-[#78716C] space-y-1">
              <p>• Get a free API key at <a href="https://aistudio.google.com/" target="_blank" rel="noreferrer" className="text-[#854D0E] underline underline-offset-2">aistudio.google.com</a></p>
              <p>• Restart the backend server after saving the key.</p>
            </div>

            <div className="pt-1 flex justify-end">
              <button
                type="button"
                onClick={() => setShowKeyModal(false)}
                className="btn-pill btn-pill-brand text-xs"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
