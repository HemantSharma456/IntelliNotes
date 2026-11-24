import { useState, useEffect, useCallback, useRef } from 'react';
import {
  BookOpen,
  HelpCircle,
  Layers,
  Award,
  Sparkles,
  Loader2,
  RefreshCw,
  CheckCircle2,
  XCircle,
  ChevronLeft,
  ChevronRight,
  RotateCw,
  Eye,
  EyeOff,
  Copy,
  Check,
  FileText,
  Download,
  Video,
  Play,
  ExternalLink,
  Maximize2,
  Clock,
  Send,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import PdfShowcaseModal from './PdfShowcaseModal';
import type {
  DocumentMeta,
  VideoMeta,
  StudyTool,
  SummaryResponse,
  MCQResponse,
  FlashcardResponse,
  VivaResponse,
  VideoRecommendationResponse,
  VideoSummaryResponse,
  ConversationMessage,
  ChatMessage,
} from '../types';
import {
  generateSummary,
  generateMCQs,
  generateFlashcards,
  generateViva,
  getVideoRecommendations,
  getDocumentFileUrl,
  generateVideoSummary,
  streamChatMessage,
} from '../services/api';

interface StudyToolsViewProps {
  documents: DocumentMeta[];
  videos?: VideoMeta[];
  selectedDocId: string | null;
  selectedVideoId?: string | null;
  onSelectDocument: (id: string | null) => void;
  onSelectVideo?: (id: string | null) => void;
  onPlayVideo?: (req: { youtubeId: string; title: string; channel?: string | null; startTime?: number }) => void;
}

export default function StudyToolsView({
  documents,
  videos = [],
  selectedDocId,
  selectedVideoId = null,
  onSelectDocument,
  onSelectVideo,
  onPlayVideo,
}: StudyToolsViewProps) {
  const [activeTool, setActiveTool] = useState<StudyTool>('summary');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPdfModal, setShowPdfModal] = useState(false);

  // Tool results cache per document
  const [summaries, setSummaries] = useState<Record<string, SummaryResponse>>({});
  const [mcqs, setMcqs] = useState<Record<string, MCQResponse>>({});
  const [flashcards, setFlashcards] = useState<Record<string, FlashcardResponse>>({});
  const [vivas, setVivas] = useState<Record<string, VivaResponse>>({});
  const [videoRecs, setVideoRecs] = useState<Record<string, VideoRecommendationResponse>>({});

  // Video study state
  const [videoTool, setVideoTool] = useState<'player' | 'summary' | 'rag'>('player');
  const [videoSummaries, setVideoSummaries] = useState<Record<string, VideoSummaryResponse>>({});
  const [videoLoading, setVideoLoading] = useState(false);
  const [videoError, setVideoError] = useState<string | null>(null);
  const [videoStartTime, setVideoStartTime] = useState<number>(0);
  const [videoCopied, setVideoCopied] = useState(false);

  // Video RAG Chat state
  const [videoChats, setVideoChats] = useState<Record<string, ConversationMessage[]>>({});
  const [videoChatInput, setVideoChatInput] = useState('');
  const [videoChatLoading, setVideoChatLoading] = useState(false);
  const [videoChatError, setVideoChatError] = useState<string | null>(null);
  const videoChatEndRef = useRef<HTMLDivElement>(null);

  // Quiz state
  const [userAnswers, setUserAnswers] = useState<Record<number, string>>({});
  const [quizSubmitted, setQuizSubmitted] = useState(false);

  // Flashcards state
  const [currentCardIndex, setCurrentCardIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  // Viva state
  const [expandedAnswers, setExpandedAnswers] = useState<Record<number, boolean>>({});

  // Copy state
  const [copied, setCopied] = useState(false);

  const currentDoc = documents.find((d) => d.id === selectedDocId) || null;
  const currentVideo = videos.find((v) => v.id === selectedVideoId) || null;
  const currentVideoRecs = selectedDocId ? videoRecs[selectedDocId] : null;
  const currentVideoSummary = selectedVideoId ? videoSummaries[selectedVideoId] : null;

  useEffect(() => {
    setUserAnswers({});
    setQuizSubmitted(false);
    setCurrentCardIndex(0);
    setIsFlipped(false);
    setExpandedAnswers({});
    setError(null);
  }, [selectedDocId, activeTool]);

  useEffect(() => {
    setVideoError(null);
    setVideoStartTime(0);
  }, [selectedVideoId]);

  const handleGenerateVideoSummary = async (videoId: string, forceRefresh = false) => {
    if (!videoId) return;
    if (!forceRefresh && videoSummaries[videoId]) return;

    setVideoLoading(true);
    setVideoError(null);

    try {
      const res = await generateVideoSummary(videoId, forceRefresh);
      setVideoSummaries((prev) => ({ ...prev, [videoId]: res }));
    } catch (err: any) {
      setVideoError(err.message || 'Failed to generate video summary.');
    } finally {
      setVideoLoading(false);
    }
  };

  const handleCopyVideoSummary = (text: string) => {
    navigator.clipboard.writeText(text);
    setVideoCopied(true);
    setTimeout(() => setVideoCopied(false), 2000);
  };

  const handleDownloadVideoSummary = (summaryText: string, videoTitle: string) => {
    const blob = new Blob([`# Video Summary: ${videoTitle}\n\n${summaryText}`], {
      type: 'text/markdown;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${videoTitle.replace(/[^a-zA-Z0-9_-]/g, '_')}-summary.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const formatDuration = (seconds?: number | null) => {
    if (!seconds || seconds <= 0) return null;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const formatSeconds = (sec?: number | null) => {
    if (sec === undefined || sec === null || sec < 0) return '00:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  const handleSendVideoChat = async (questionText?: string) => {
    if (!selectedVideoId || !currentVideo) return;
    const q = (questionText || videoChatInput).trim();
    if (!q || videoChatLoading) return;

    setVideoChatInput('');
    setVideoChatError(null);

    const userMsg: ConversationMessage = { role: 'user', content: q };
    const assistantMsg: ConversationMessage = {
      role: 'assistant',
      content: '',
      isStreaming: true,
      citations: [],
    };

    const currentMessages = videoChats[selectedVideoId] || [];
    setVideoChats((prev) => ({
      ...prev,
      [selectedVideoId]: [...currentMessages, userMsg, assistantMsg],
    }));
    setVideoChatLoading(true);

    try {
      const history: ChatMessage[] = currentMessages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      await streamChatMessage(
        q,
        null,
        history,
        {
          onMetadata: (data) => {
            setVideoChats((prev) => {
              const current = prev[selectedVideoId] || [];
              if (current.length === 0) return prev;
              const lastIdx = current.length - 1;
              const lastMsg = current[lastIdx];
              if (lastMsg.role !== 'assistant') return prev;
              const updatedMsg = {
                ...lastMsg,
                citations: data.citations,
                insufficient_context: data.insufficient_context,
              };
              return {
                ...prev,
                [selectedVideoId]: [...current.slice(0, lastIdx), updatedMsg],
              };
            });
          },
          onToken: (token) => {
            setVideoChats((prev) => {
              const current = prev[selectedVideoId] || [];
              if (current.length === 0) return prev;
              const lastIdx = current.length - 1;
              const lastMsg = current[lastIdx];
              if (lastMsg.role !== 'assistant') return prev;
              const updatedMsg = {
                ...lastMsg,
                content: lastMsg.content + token,
              };
              return {
                ...prev,
                [selectedVideoId]: [...current.slice(0, lastIdx), updatedMsg],
              };
            });
          },
          onDone: (data) => {
            setVideoChats((prev) => {
              const current = prev[selectedVideoId] || [];
              if (current.length === 0) return prev;
              const lastIdx = current.length - 1;
              const lastMsg = current[lastIdx];
              if (lastMsg.role !== 'assistant') return prev;
              const updatedMsg = {
                ...lastMsg,
                isStreaming: false,
                latency_ms: data.latency_ms,
              };
              return {
                ...prev,
                [selectedVideoId]: [...current.slice(0, lastIdx), updatedMsg],
              };
            });
          },
          onError: (errMsg) => {
            setVideoChatError(errMsg);
            setVideoChats((prev) => {
              const current = prev[selectedVideoId] || [];
              if (current.length === 0) return prev;
              const lastIdx = current.length - 1;
              const lastMsg = current[lastIdx];
              if (lastMsg.role !== 'assistant') return prev;
              const updatedMsg = {
                ...lastMsg,
                isStreaming: false,
                content:
                  lastMsg.content ||
                  'I could not find a confident answer for that in the video transcript.',
              };
              return {
                ...prev,
                [selectedVideoId]: [...current.slice(0, lastIdx), updatedMsg],
              };
            });
          },
        },
        'videos',
        currentVideo.id
      );
    } catch (err: any) {
      setVideoChatError(err.message || 'Error querying video');
    } finally {
      setVideoChatLoading(false);
    }
  };

  useEffect(() => {
    if (videoTool === 'rag') {
      videoChatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [videoChats, videoChatLoading, videoTool]);

  // Eager background prefetch of video recommendations when document is selected
  useEffect(() => {
    if (selectedDocId && !videoRecs[selectedDocId]) {
      getVideoRecommendations(selectedDocId)
        .then((res) => {
          setVideoRecs((prev) => ({ ...prev, [selectedDocId]: res }));
        })
        .catch(() => {});
    }
  }, [selectedDocId]);

  // Auto-upgrade stale cached video suggestions that lack real youtube_id
  useEffect(() => {
    if (activeTool === 'videos' && selectedDocId && videoRecs[selectedDocId]) {
      const rec = videoRecs[selectedDocId];
      const items = rec.suggestions || rec.external_suggestions || [];
      const hasValid = items.length > 0 && items.some((s) => Boolean(s.youtube_id));
      if (!hasValid && !loading) {
        handleGenerate('videos', true);
      }
    }
  }, [activeTool, selectedDocId, videoRecs, loading]);

  const handleGenerate = async (toolToRun = activeTool, forceRefresh = false) => {
    if (!selectedDocId) return;
    if (toolToRun === 'preview') return;

    if (!forceRefresh) {
      if (toolToRun === 'summary' && summaries[selectedDocId]) return;
      if (toolToRun === 'mcqs' && mcqs[selectedDocId]) return;
      if (toolToRun === 'flashcards' && flashcards[selectedDocId]) return;
      if (toolToRun === 'viva' && vivas[selectedDocId]) return;
      if (toolToRun === 'videos' && videoRecs[selectedDocId]) return;
    }

    setLoading(true);
    setError(null);

    try {
      if (toolToRun === 'summary') {
        const res = await generateSummary(selectedDocId);
        setSummaries((prev) => ({ ...prev, [selectedDocId]: res }));
        // Pre-fetch video recommendations in background for summary footer card
        if (!videoRecs[selectedDocId]) {
          getVideoRecommendations(selectedDocId)
            .then((vRes) => setVideoRecs((prev) => ({ ...prev, [selectedDocId]: vRes })))
            .catch(() => {});
        }
      } else if (toolToRun === 'mcqs') {
        const res = await generateMCQs(selectedDocId, 5);
        setMcqs((prev) => ({ ...prev, [selectedDocId]: res }));
        setUserAnswers({});
        setQuizSubmitted(false);
      } else if (toolToRun === 'flashcards') {
        const res = await generateFlashcards(selectedDocId, 8);
        setFlashcards((prev) => ({ ...prev, [selectedDocId]: res }));
        setCurrentCardIndex(0);
        setIsFlipped(false);
      } else if (toolToRun === 'viva') {
        const res = await generateViva(selectedDocId, 6);
        setVivas((prev) => ({ ...prev, [selectedDocId]: res }));
        setExpandedAnswers({});
      } else if (toolToRun === 'videos') {
        const res = await getVideoRecommendations(selectedDocId, forceRefresh);
        setVideoRecs((prev) => ({ ...prev, [selectedDocId]: res }));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate study materials. Check Gemini API configuration.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyText = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadSummary = (summaryText: string, docName: string) => {
    const blob = new Blob([`# Summary: ${docName}\n\n${summaryText}`], {
      type: 'text/markdown;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${docName.replace(/\.[^/.]+$/, '')}-summary.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const currentSummary = selectedDocId ? summaries[selectedDocId] : null;
  const currentMcq = selectedDocId ? mcqs[selectedDocId] : null;
  const currentFlashcard = selectedDocId ? flashcards[selectedDocId] : null;
  const currentViva = selectedDocId ? vivas[selectedDocId] : null;

  // Flashcards keyboard navigation
  const handleNextCard = useCallback(() => {
    if (!currentFlashcard) return;
    setIsFlipped(false);
    setCurrentCardIndex((i) => Math.min(currentFlashcard.flashcards.length - 1, i + 1));
  }, [currentFlashcard]);

  const handlePrevCard = useCallback(() => {
    setIsFlipped(false);
    setCurrentCardIndex((i) => Math.max(0, i - 1));
  }, []);

  const handleToggleFlip = useCallback(() => {
    setIsFlipped((f) => !f);
  }, []);

  useEffect(() => {
    if (activeTool !== 'flashcards' || !currentFlashcard) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) return;
      if (e.code === 'Space') {
        e.preventDefault();
        handleToggleFlip();
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        handleNextCard();
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        handlePrevCard();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTool, currentFlashcard, handleToggleFlip, handleNextCard, handlePrevCard]);

  const hasItems = documents.length > 0 || videos.length > 0;

  if (!hasItems) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#faf8f0] text-[#1C1917] animate-fade-in-up">
        {/* Icon */}
        <div className="w-16 h-16 rounded-2xl bg-[#1a1714] flex items-center justify-center mb-5 shadow-lg">
          <BookOpen size={28} className="text-[#fde047]" />
        </div>
        {/* Headline */}
        <h2 className="font-sans text-2xl font-700 text-[#1C1917] mb-2 tracking-tight">
          Your AI Study Workspace
        </h2>
        <p className="text-sm text-[#78716C] max-w-sm leading-relaxed mb-8">
          Upload a PDF document or add a YouTube lecture from the sidebar to unlock AI-powered summaries, flashcards, quizzes, and more.
        </p>
        {/* Feature pills */}
        <div className="flex flex-wrap justify-center gap-2 max-w-sm stagger-1">
          {[
            { icon: <BookOpen size={12}/>, label: 'AI Summary' },
            { icon: <Layers size={12}/>, label: 'Flashcards' },
            { icon: <HelpCircle size={12}/>, label: 'Quiz' },
            { icon: <Award size={12}/>, label: 'Viva' },
            { icon: <Video size={12}/>, label: 'Video RAG' },
          ].map((f, i) => (
            <span key={i} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-white border border-[#e7e2d7] text-[11px] font-semibold text-[#44403c] shadow-sm">
              <span className="text-[#854d0e]">{f.icon}</span>
              {f.label}
            </span>
          ))}
        </div>
      </div>
    );
  }

  // Video Workspace View
  if (selectedVideoId && currentVideo) {
    return (
      <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#faf8f0] text-[#1C1917]">
        {/* Subheader: Minimal Video Tool Switcher */}
        <div className="shrink-0 px-4 sm:px-5 py-2.5 border-b border-[#e7e2d7] bg-[#f4f0e4]/80 backdrop-blur-sm flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className="px-2 py-0.5 rounded-full text-[10px] font-700 bg-rose-100 text-rose-700 border border-rose-200 shrink-0">
              VIDEO
            </span>
            <span className="text-[12px] font-semibold text-[#1C1917] truncate max-w-[180px] sm:max-w-[320px]">
              {currentVideo.title}
            </span>
            {currentVideo.duration ? (
              <span className="text-[11px] text-[#78716C] bg-[#eae3d4] px-1.5 py-0.5 rounded-lg shrink-0 font-mono">
                {formatDuration(currentVideo.duration)}
              </span>
            ) : null}
            {videoTool === 'summary' && (
              <button
                type="button"
                onClick={() => handleGenerateVideoSummary(currentVideo.id, true)}
                disabled={videoLoading}
                className="p-1 rounded-lg text-[#a8a29e] hover:text-[#1C1917] hover:bg-[#eae3d4] transition-colors cursor-pointer"
                title="Regenerate Video Summary"
              >
                <RefreshCw size={12} className={videoLoading ? 'animate-spin' : ''} />
              </button>
            )}
          </div>

          {/* Video Tool Pills */}
          <div className="flex items-center gap-0.5 bg-[#e5dfd2]/80 p-1 rounded-2xl">
            {[
              { key: 'player',  icon: <Play size={11}/>,        label: 'Video View'          },
              { key: 'summary', icon: <Sparkles size={11}/>,    label: 'Timestamped Summary' },
              { key: 'rag',     icon: <HelpCircle size={11}/>,  label: 'Ask Video (RAG)'     },
            ].map((tab) => (
              <button
                key={tab.key}
                type="button"
                onClick={() => {
                  setVideoTool(tab.key as 'player' | 'summary' | 'rag');
                  if (tab.key === 'summary' && !currentVideoSummary && !videoLoading) {
                    handleGenerateVideoSummary(currentVideo.id);
                  }
                }}
                className={`tool-tab ${videoTool === tab.key ? 'active' : ''}`}
              >
                <span className={videoTool === tab.key ? 'text-[#fde047]' : 'text-[#a8a29e]'}>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Video Tool Body */}
        <div className="flex-1 overflow-y-auto">
          {videoTool === 'player' && (
            <div className="max-w-5xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
              {/* Showcase Bar */}
              <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-4 sm:p-5 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div className="min-w-0">
                  <h2 className="font-serif text-lg sm:text-xl font-medium text-[#1C1917] leading-snug line-clamp-2">
                    {currentVideo.title}
                  </h2>
                  <div className="flex items-center gap-3 mt-1 text-xs text-[#78716C]">
                    {currentVideo.channel && (
                      <span className="font-medium text-[#44403C]">{currentVideo.channel}</span>
                    )}
                    {currentVideo.duration ? (
                      <span>• {formatDuration(currentVideo.duration)}</span>
                    ) : null}
                    <span>• {currentVideo.num_chunks} transcript segments</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
                  <button
                    type="button"
                    onClick={() =>
                      onPlayVideo?.({
                        youtubeId: currentVideo.youtube_id,
                        title: currentVideo.title,
                        channel: currentVideo.channel,
                        startTime: videoStartTime,
                      })
                    }
                    className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-medium border border-[#EAB308]/40 transition-all cursor-pointer shadow-xs"
                    title="Fullscreen player modal"
                  >
                    <Maximize2 size={13} />
                    <span>Fullscreen</span>
                  </button>

                  <a
                    href={currentVideo.url}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 sm:flex-initial flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-xl bg-[#F5F1E6] hover:bg-[#EAE3D4] text-[#57534E] hover:text-[#1C1917] text-xs font-medium border border-[#E7E2D7] transition-all cursor-pointer"
                  >
                    <ExternalLink size={13} />
                    <span>YouTube</span>
                  </a>
                </div>
              </div>

              {/* Embedded Player 16:9 Showcase */}
              <div className="relative aspect-video w-full rounded-2xl overflow-hidden border border-[#E7E2D7] shadow-md bg-black">
                <iframe
                  key={`${currentVideo.youtube_id}-${videoStartTime}`}
                  src={`https://www.youtube-nocookie.com/embed/${currentVideo.youtube_id}?start=${videoStartTime}&autoplay=1&enablejsapi=1`}
                  title={currentVideo.title}
                  className="w-full h-full border-0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                />
              </div>

              {/* Jump to Chapter Strip (if summary generated) */}
              {currentVideoSummary && currentVideoSummary.timestamps.length > 0 && (
                <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-5 shadow-xs">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <Clock size={14} className="text-[#854D0E]" />
                      <span className="text-xs font-semibold text-[#1C1917] uppercase tracking-wider">
                        Quick Chapters
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setVideoTool('summary')}
                      className="text-xs text-[#854D0E] hover:underline font-medium cursor-pointer"
                    >
                      View Full Summary & Descriptions →
                    </button>
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {currentVideoSummary.timestamps.map((ts, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => setVideoStartTime(ts.time_seconds)}
                        className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-2 cursor-pointer border ${
                          videoStartTime === ts.time_seconds
                            ? 'bg-[#FEF08A] text-[#713F12] border-[#EAB308]'
                            : 'bg-[#F5F1E6] hover:bg-[#FEFCE8] text-[#1C1917] border-[#E7E2D7]'
                        }`}
                      >
                        <span className="font-mono text-[11px] font-semibold text-[#B45309]">
                          {ts.timestamp_formatted}
                        </span>
                        <span className="truncate max-w-[160px] sm:max-w-[220px]">{ts.topic}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Prompt to generate summary if not already present */}
              {!currentVideoSummary && (
                <div className="bg-[#FEFCE8] border border-[#FEF08A] rounded-2xl p-6 text-center space-y-3">
                  <div className="w-10 h-10 rounded-full bg-[#FEF08A] text-[#854D0E] flex items-center justify-center mx-auto">
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <h3 className="font-serif text-base font-medium text-[#1C1917]">
                      Need a timestamped summary for this lecture?
                    </h3>
                    <p className="text-xs text-[#78716C] max-w-md mx-auto mt-1">
                      Generate an AI chapter-by-chapter outline with clickable timestamps to review the core concepts faster.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setVideoTool('summary');
                      handleGenerateVideoSummary(currentVideo.id);
                    }}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-medium border border-[#EAB308]/40 transition-all cursor-pointer shadow-xs"
                  >
                    <Sparkles size={13} />
                    <span>Generate Timestamped Summary</span>
                  </button>
                </div>
              )}
            </div>
          )}

          {videoTool === 'summary' && (
            <div className="max-w-4xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
              {videoLoading && (
                <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-12 text-center shadow-xs">
                  <Loader2 size={28} className="animate-spin text-[#854D0E] mx-auto mb-3" />
                  <h3 className="font-serif text-lg font-medium text-[#1C1917] mb-1">
                    Analyzing Video Lecture...
                  </h3>
                  <p className="text-xs text-[#78716C] max-w-sm mx-auto">
                    Synthesizing transcript, extracting key topics, and calculating chapter timestamps.
                  </p>
                </div>
              )}

              {videoError && !videoLoading && (
                <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-center space-y-3">
                  <div className="w-10 h-10 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
                    <XCircle size={20} />
                  </div>
                  <div>
                    <h3 className="font-medium text-sm text-red-900">Failed to generate video summary</h3>
                    <p className="text-xs text-red-700 max-w-md mx-auto mt-1">{videoError}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleGenerateVideoSummary(currentVideo.id, true)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-600 hover:bg-red-700 text-white text-xs font-medium transition-colors cursor-pointer"
                  >
                    <RefreshCw size={12} />
                    <span>Try Again</span>
                  </button>
                </div>
              )}

              {!currentVideoSummary && !videoLoading && !videoError && (
                <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-10 text-center shadow-xs space-y-4">
                  <div className="w-12 h-12 rounded-xl bg-[#FEF08A] border border-[#EAB308]/40 flex items-center justify-center mx-auto text-[#854D0E] shadow-xs">
                    <Sparkles size={20} />
                  </div>
                  <div>
                    <h3 className="font-serif text-xl font-normal text-[#1C1917] mb-1">
                      Timestamped Video Summary
                    </h3>
                    <p className="text-xs text-[#78716C] max-w-md mx-auto leading-relaxed">
                      AI will analyze the complete transcript of &ldquo;{currentVideo.title}&rdquo; to generate structured study notes and clickable chapter timestamps.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleGenerateVideoSummary(currentVideo.id)}
                    className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-medium border border-[#EAB308]/40 transition-all cursor-pointer shadow-xs"
                  >
                    <Sparkles size={13} />
                    <span>Generate Summary</span>
                  </button>
                </div>
              )}

              {currentVideoSummary && !videoLoading && (
                <div className="space-y-6">
                  {/* Top Action Header */}
                  <div className="flex flex-wrap items-center justify-between gap-3 bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-4 shadow-xs">
                    <div>
                      <h3 className="font-serif text-lg font-medium text-[#1C1917]">
                        {currentVideoSummary.video_title}
                      </h3>
                      <p className="text-xs text-[#78716C] mt-0.5">
                        {currentVideoSummary.timestamps.length} chronological chapters identified
                      </p>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleCopyVideoSummary(currentVideoSummary.summary)}
                        className="px-3 py-1.5 rounded-lg bg-[#F5F1E6] hover:bg-[#EAE3D4] text-[#1C1917] text-xs font-medium transition-colors flex items-center gap-1.5 cursor-pointer"
                        title="Copy Markdown Summary"
                      >
                        {videoCopied ? <Check size={13} className="text-emerald-600" /> : <Copy size={13} />}
                        <span>{videoCopied ? 'Copied' : 'Copy'}</span>
                      </button>

                      <button
                        type="button"
                        onClick={() =>
                          handleDownloadVideoSummary(
                            currentVideoSummary.summary,
                            currentVideoSummary.video_title
                          )
                        }
                        className="px-3 py-1.5 rounded-lg bg-[#F5F1E6] hover:bg-[#EAE3D4] text-[#1C1917] text-xs font-medium transition-colors flex items-center gap-1.5 cursor-pointer"
                        title="Download Markdown File"
                      >
                        <Download size={13} />
                        <span>Download .md</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleGenerateVideoSummary(currentVideo.id, true)}
                        className="p-1.5 rounded-lg bg-[#F5F1E6] hover:bg-[#EAE3D4] text-[#78716C] hover:text-[#1C1917] transition-colors cursor-pointer"
                        title="Regenerate"
                      >
                        <RefreshCw size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Section 1: Timestamps & Chapters */}
                  {currentVideoSummary.timestamps.length > 0 && (
                    <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-6 shadow-xs space-y-4">
                      <div className="flex items-center gap-2 pb-2 border-b border-[#E7E2D7]">
                        <Clock size={16} className="text-[#854D0E]" />
                        <h4 className="font-serif text-base font-medium text-[#1C1917]">
                          Chapters & Key Timestamps
                        </h4>
                        <span className="text-[11px] font-semibold text-[#854D0E] bg-[#FEF08A] px-2 py-0.5 rounded-full border border-[#EAB308]/30">
                          Click to Play
                        </span>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                        {currentVideoSummary.timestamps.map((ts, idx) => (
                          <div
                            key={idx}
                            className="p-3.5 rounded-xl border border-[#E7E2D7] bg-[#FBF9F1] hover:bg-[#FEFCE8] hover:border-[#CA8A04]/40 transition-all flex flex-col justify-between group"
                          >
                            <div className="flex items-start justify-between gap-2 mb-1.5">
                              <span className="font-medium text-xs text-[#1C1917] group-hover:text-[#854D0E] transition-colors">
                                {ts.topic}
                              </span>
                              <button
                                type="button"
                                onClick={() => {
                                  setVideoStartTime(ts.time_seconds);
                                  setVideoTool('player');
                                }}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md font-mono text-[11px] font-semibold bg-[#FEF08A] text-[#713F12] border border-[#EAB308]/40 hover:bg-[#FDE047] transition-all cursor-pointer shrink-0 shadow-2xs"
                                title={`Play video from ${ts.timestamp_formatted}`}
                              >
                                <Play size={10} className="fill-[#713F12]" />
                                <span>{ts.timestamp_formatted}</span>
                              </button>
                            </div>
                            <p className="text-[11px] text-[#57534E] leading-relaxed line-clamp-3">
                              {ts.description}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Section 2: In-Depth Markdown Summary */}
                  <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-6 sm:p-8 shadow-xs space-y-4">
                    <div className="flex items-center gap-2 pb-3 border-b border-[#E7E2D7]">
                      <BookOpen size={16} className="text-[#854D0E]" />
                      <h4 className="font-serif text-base font-medium text-[#1C1917]">
                        Comprehensive Video Notes
                      </h4>
                    </div>

                    <div className="markdown-body prose max-w-none text-xs sm:text-sm leading-relaxed text-[#1C1917]">
                      <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                        {currentVideoSummary.summary}
                      </ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {videoTool === 'rag' && (
            <div className="max-w-4xl mx-auto p-4 sm:p-6 lg:p-8 flex flex-col h-full space-y-4">
              {/* Top Banner */}
              <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-4 sm:p-5 shadow-xs flex items-center justify-between gap-3 shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-[#FEF08A] text-[#854D0E] flex items-center justify-center shrink-0 shadow-2xs">
                    <Sparkles size={18} />
                  </div>
                  <div>
                    <h3 className="font-serif text-base font-medium text-[#1C1917]">
                      Ask Video (Semantic Lecture RAG)
                    </h3>
                    <p className="text-xs text-[#78716C]">
                      Query concepts taught in &ldquo;{currentVideo.title}&rdquo; with verified clickable timestamp citations.
                    </p>
                  </div>
                </div>

                {videoChats[currentVideo.id] && videoChats[currentVideo.id].length > 0 && (
                  <button
                    type="button"
                    onClick={() => setVideoChats((prev) => ({ ...prev, [currentVideo.id]: [] }))}
                    className="px-2.5 py-1 text-xs text-[#78716C] hover:text-[#1C1917] hover:bg-[#F5F1E6] rounded-lg transition-colors cursor-pointer"
                  >
                    Clear Chat
                  </button>
                )}
              </div>

              {/* Chat Thread / Messages Area */}
              <div className="flex-1 overflow-y-auto space-y-4 min-h-[300px] max-h-[500px] pr-1">
                {(!videoChats[currentVideo.id] || videoChats[currentVideo.id].length === 0) && (
                  <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-8 text-center shadow-xs space-y-4">
                    <div className="w-12 h-12 rounded-xl bg-[#FEF08A] border border-[#EAB308]/40 flex items-center justify-center mx-auto text-[#854D0E] shadow-xs">
                      <HelpCircle size={22} />
                    </div>
                    <div>
                      <h4 className="font-serif text-lg font-normal text-[#1C1917] mb-1">
                        Semantic Video Knowledge Retrieval
                      </h4>
                      <p className="text-xs text-[#78716C] max-w-md mx-auto leading-relaxed">
                        Ask any question about this lecture. IntelliNotes retrieves the exact spoken passages and cites the timestamp where it is taught.
                      </p>
                    </div>

                    <div className="flex flex-wrap justify-center gap-2 pt-2">
                      {[
                        'What are the core concepts explained in this video?',
                        'Can you explain the main example or proof shown?',
                        'Summarize the key takeaways and practical points.',
                      ].map((prompt, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => handleSendVideoChat(prompt)}
                          className="px-3 py-1.5 rounded-xl bg-[#F5F1E6] hover:bg-[#FEFCE8] text-[#1C1917] border border-[#E7E2D7] hover:border-[#CA8A04]/40 text-xs transition-all cursor-pointer shadow-2xs text-left"
                        >
                          &ldquo;{prompt}&rdquo;
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {videoChats[currentVideo.id]?.map((msg, idx) => (
                  <div
                    key={idx}
                    className={`flex flex-col ${
                      msg.role === 'user' ? 'items-end' : 'items-start'
                    } space-y-1.5`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl p-4 sm:p-5 shadow-xs ${
                        msg.role === 'user'
                          ? 'bg-[#EAE3D4] text-[#1C1917]'
                          : 'bg-[#FFFFFF] border border-[#E7E2D7] text-[#1C1917]'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1.5 text-xs text-[#78716C]">
                        <span className="font-semibold text-[#1C1917]">
                          {msg.role === 'user' ? 'You' : 'IntelliNotes AI'}
                        </span>
                        {msg.latency_ms ? <span>• {Math.round(msg.latency_ms)}ms</span> : null}
                      </div>

                      <div className="markdown-body prose max-w-none text-xs sm:text-sm leading-relaxed text-[#1C1917]">
                        <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                          {msg.content}
                        </ReactMarkdown>
                      </div>

                      {msg.isStreaming && (
                        <div className="flex items-center gap-1.5 mt-2 text-xs text-[#854D0E]">
                          <Loader2 size={12} className="animate-spin" />
                          <span>Streaming answer...</span>
                        </div>
                      )}

                      {/* Video Citations */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-[#E7E2D7]/60 space-y-2">
                          <span className="text-[11px] font-semibold text-[#854D0E] uppercase tracking-wider block">
                            Verified Video Timestamps ({msg.citations.length})
                          </span>
                          <div className="flex flex-wrap gap-2">
                            {msg.citations.map((c, cIdx) => (
                              <button
                                key={cIdx}
                                type="button"
                                onClick={() => {
                                  if (c.start_time !== undefined && c.start_time !== null) {
                                    setVideoStartTime(c.start_time);
                                    setVideoTool('player');
                                  }
                                }}
                                className="group/cit px-2.5 py-1.5 rounded-lg bg-[#FEFCE8] hover:bg-[#FEF08A] border border-[#EAB308]/40 text-left transition-all cursor-pointer flex items-center gap-2 shadow-2xs"
                                title={`Jump to timestamp ${formatSeconds(c.start_time || 0)}`}
                              >
                                <Play size={10} className="fill-[#713F12] text-[#713F12]" />
                                <span className="font-mono text-xs font-semibold text-[#B45309]">
                                  {formatSeconds(c.start_time || 0)}
                                </span>
                                <span className="text-xs text-[#44403C] truncate max-w-[160px]">
                                  {c.excerpt}
                                </span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}

                <div ref={videoChatEndRef} />
              </div>

              {/* Chat Input Bar */}
              <div className="bg-[#FFFFFF] rounded-2xl border border-[#E7E2D7] p-2 sm:p-3 shadow-xs flex items-center gap-2 shrink-0">
                <textarea
                  value={videoChatInput}
                  onChange={(e) => setVideoChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendVideoChat();
                    }
                  }}
                  placeholder="Ask a question about this video lecture... (Enter to send)"
                  rows={1}
                  disabled={videoChatLoading}
                  className="flex-1 bg-transparent px-2.5 py-1.5 text-xs sm:text-sm text-[#1C1917] placeholder:text-[#A8A29E] focus:outline-hidden resize-none"
                />

                <button
                  type="button"
                  onClick={() => handleSendVideoChat()}
                  disabled={!videoChatInput.trim() || videoChatLoading}
                  className="p-2 sm:px-3.5 sm:py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] disabled:opacity-40 text-[#713F12] text-xs font-medium border border-[#EAB308]/40 transition-all cursor-pointer shadow-xs flex items-center gap-1.5 shrink-0"
                >
                  {videoChatLoading ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Send size={13} />
                  )}
                  <span className="hidden sm:inline">Ask</span>
                </button>
              </div>

              {videoChatError && (
                <p className="text-xs text-red-600 px-2">{videoChatError}</p>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (!selectedDocId || !currentDoc) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-[#faf8f0] text-[#1C1917] overflow-y-auto animate-fade-in">
        <div className="w-14 h-14 rounded-2xl bg-[#fef08a] border border-[#eab308]/30 flex items-center justify-center mb-4 text-[#854D0E] shadow-md">
          <BookOpen size={24} />
        </div>
        <h3 className="font-sans text-lg font-700 text-[#1C1917] mb-1 tracking-tight">Select a Study Resource</h3>
        <p className="text-sm text-[#78716C] max-w-sm mb-7 leading-relaxed">
          Choose a document or video from your library on the left to open its AI study workspace.
        </p>

        <div className="w-full max-w-sm space-y-5">
          {documents.length > 0 && (
            <div className="text-left animate-fade-in-up stagger-1">
              <span className="text-[10px] uppercase tracking-widest font-700 text-[#a8a29e] block mb-2 px-1">
                Documents ({documents.length})
              </span>
              <div className="flex flex-wrap gap-2">
                {documents.map((doc) => (
                  <button
                    key={doc.id}
                    type="button"
                    onClick={() => onSelectDocument(doc.id)}
                    className="px-3.5 py-2 rounded-xl bg-white hover:bg-[#fefce8] border border-[#e7e2d7] hover:border-[#ca8a04]/40 text-xs font-medium text-[#1C1917] transition-all flex items-center gap-2 shadow-sm cursor-pointer"
                  >
                    <FileText size={13} className="text-[#854D0E]" />
                    <span className="truncate max-w-[180px]">{doc.filename}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {videos.length > 0 && (
            <div className="text-left animate-fade-in-up stagger-2">
              <span className="text-[10px] uppercase tracking-widest font-700 text-[#a8a29e] block mb-2 px-1">
                Videos ({videos.length})
              </span>
              <div className="flex flex-wrap gap-2">
                {videos.map((vid) => (
                  <button
                    key={vid.id}
                    type="button"
                    onClick={() => onSelectVideo?.(vid.id)}
                    className="px-3.5 py-2 rounded-xl bg-white hover:bg-[#fff1f1] border border-[#e7e2d7] hover:border-rose-300 text-xs font-medium text-[#1C1917] transition-all flex items-center gap-2 shadow-sm cursor-pointer"
                  >
                    <Video size={13} className="text-[#DC2626]" />
                    <span className="truncate max-w-[180px]">{vid.title}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#faf8f0] text-[#1C1917]">

      {/* ── Document Tool Subheader ── */}
      <div className="shrink-0 px-4 sm:px-5 py-2.5 border-b border-[#e7e2d7] bg-[#f4f0e4]/80 backdrop-blur-sm flex items-center justify-between gap-3">

        {/* Left: doc name + refresh */}
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-6 h-6 rounded-lg bg-[#fef08a] border border-[#eab308]/30 flex items-center justify-center text-[#854d0e] shrink-0">
            <FileText size={12} />
          </div>
          <span className="text-[12px] font-semibold text-[#1C1917] truncate max-w-[160px] sm:max-w-[260px]" title={currentDoc.filename}>
            {currentDoc.filename}
          </span>
          <button
            type="button"
            onClick={() => handleGenerate(activeTool, true)}
            disabled={loading}
            className="p-1 rounded-lg text-[#a8a29e] hover:text-[#1C1917] hover:bg-[#eae3d4] transition-colors cursor-pointer"
            title="Regenerate"
          >
            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        {/* Right: Tool Tab Pills */}
        <div className="flex items-center gap-0.5 bg-[#e5dfd2]/80 p-1 rounded-2xl overflow-x-auto">
          {[
            { key: 'preview',    icon: <FileText size={11}/>,    label: 'PDF View'  },
            { key: 'summary',    icon: <BookOpen size={11}/>,    label: 'Summary'   },
            { key: 'mcqs',       icon: <HelpCircle size={11}/>,  label: 'Quiz'      },
            { key: 'flashcards', icon: <Layers size={11}/>,      label: 'Flashcards'},
            { key: 'viva',       icon: <Award size={11}/>,       label: 'Viva'      },
            { key: 'videos',     icon: <Video size={11}/>,       label: 'Videos'    },
          ].map((tab) => (
            <button
              key={tab.key}
              type="button"
              onClick={() => {
                setActiveTool(tab.key as StudyTool);
                if (tab.key === 'videos' && selectedDocId && !videoRecs[selectedDocId]) {
                  handleGenerate('videos');
                }
              }}
              className={`tool-tab ${activeTool === tab.key ? 'active' : ''}`}
            >
              <span className={activeTool === tab.key ? 'text-[#fde047]' : 'text-[#a8a29e]'}>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Content Area ── */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6">
        {error && (
          <div className="mb-6 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between gap-3 animate-fade-in">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => handleGenerate(activeTool, true)}
              className="px-2.5 py-1 rounded-lg bg-rose-100 text-rose-800 font-semibold hover:bg-rose-200 cursor-pointer"
            >
              Retry
            </button>
          </div>
        )}

        {/* ── 0. PDF SHOWCASE TOOL ── */}
        {activeTool === 'preview' && (
          <div className="max-w-5xl mx-auto space-y-4 animate-fade-in">
            {/* Showcase Control Header */}
            <div className="bg-[#FFFFFF] border border-[#E7E2D7] rounded-2xl p-4 sm:p-5 shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-11 h-11 rounded-xl bg-[#FEF08A] text-[#854D0E] flex items-center justify-center shrink-0 border border-[#EAB308]/30 shadow-2xs">
                  <FileText size={20} />
                </div>
                <div className="min-w-0">
                  <h3 className="font-serif text-base sm:text-lg font-medium text-[#1C1917] truncate">
                    {currentDoc.filename}
                  </h3>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-[#78716C]">
                    <span className="uppercase font-bold tracking-wider px-1.5 py-0.5 rounded text-[10px] bg-[#FEF08A] text-[#713F12]">
                      {currentDoc.file_type}
                    </span>
                    {currentDoc.num_pages !== null && (
                      <span>• {currentDoc.num_pages} {currentDoc.num_pages === 1 ? 'page' : 'pages'}</span>
                    )}
                    <span>• {(currentDoc.file_size / (1024 * 1024)).toFixed(2)} MB</span>
                  </div>
                </div>
              </div>

              {/* Showcase Action Controls */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  type="button"
                  onClick={() => setShowPdfModal(true)}
                  className="px-3.5 py-1.5 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-semibold shadow-xs transition-all flex items-center gap-1.5 cursor-pointer"
                  title="Expand to Fullscreen Showcase"
                >
                  <Maximize2 size={13} />
                  <span>Fullscreen</span>
                </button>

                <a
                  href={getDocumentFileUrl(currentDoc.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-3 py-1.5 rounded-xl border border-[#E7E2D7] bg-[#FFFFFF] hover:bg-[#F5F1E6] text-[#78716C] hover:text-[#1C1917] text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer shadow-2xs"
                  title="Open PDF in new tab"
                >
                  <ExternalLink size={13} />
                  <span className="hidden sm:inline">New Tab</span>
                </a>

                <a
                  href={getDocumentFileUrl(currentDoc.id)}
                  download={currentDoc.filename}
                  className="px-3 py-1.5 rounded-xl border border-[#E7E2D7] bg-[#FFFFFF] hover:bg-[#F5F1E6] text-[#78716C] hover:text-[#1C1917] text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer shadow-2xs"
                  title="Download document"
                >
                  <Download size={13} />
                  <span className="hidden sm:inline">Download</span>
                </a>
              </div>
            </div>

            {/* Embedded PDF Showcase Reader */}
            <div className="w-full h-[76vh] bg-[#525659] border border-[#E7E2D7] rounded-2xl shadow-sm overflow-hidden relative">
              <iframe
                src={`${getDocumentFileUrl(currentDoc.id)}#view=FitH&toolbar=1`}
                title={currentDoc.filename}
                className="w-full h-full border-0"
              />
            </div>
          </div>
        )}

        {/* ── 1. SUMMARY TOOL ── */}
        {activeTool === 'summary' && (
          <div className="max-w-3xl mx-auto">
            {!currentSummary && !loading ? (
              <div className="text-center py-12 bg-[#FFFFFF] border border-[#E7E2D7] rounded-2xl p-8 shadow-xs">
                <Sparkles size={28} className="mx-auto text-[#854D0E] mb-2.5" />
                <h4 className="font-serif text-lg font-normal text-[#1C1917] mb-1">Generate Summary</h4>
                <p className="text-xs text-[#78716C] max-w-sm mx-auto mb-5 leading-relaxed">
                  Extract core takeaways and high-yield concepts from {currentDoc.filename}.
                </p>
                <button
                  type="button"
                  onClick={() => handleGenerate('summary')}
                  className="px-4 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-semibold shadow-xs transition-all cursor-pointer"
                >
                  Generate Summary
                </button>
              </div>
            ) : loading && !currentSummary ? (
              <div className="text-center py-16">
                <Loader2 size={24} className="animate-spin text-[#854D0E] mx-auto mb-3" />
                <p className="text-xs text-[#57534E]">Synthesizing notes...</p>
              </div>
            ) : currentSummary ? (
              <div className="bg-[#FFFFFF] border border-[#E7E2D7] rounded-2xl p-6 sm:p-8 shadow-xs relative animate-fade-in">
                <div className="flex items-center justify-between pb-3 mb-5 border-b border-[#F5F1E6]">
                  <h3 className="font-serif text-xl font-normal text-[#1C1917]">
                    Summary
                  </h3>
                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => handleDownloadSummary(currentSummary.summary, currentSummary.document_name)}
                      className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#F5F1E6] transition-colors cursor-pointer"
                      title="Download Markdown"
                    >
                      <Download size={14} />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCopyText(currentSummary.summary)}
                      className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#F5F1E6] transition-colors cursor-pointer"
                      title="Copy text"
                    >
                      {copied ? <Check size={14} className="text-emerald-600" /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>
                <div className="prose max-w-none text-sm text-[#292524] leading-relaxed">
                  <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                    {currentSummary.summary}
                  </ReactMarkdown>
                </div>

                {/* Preview: Related Video Lectures */}
                <div className="mt-8 pt-6 border-t border-[#F5F1E6]">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="p-1 rounded bg-[#FEF08A] text-[#854D0E]">
                        <Video size={13} />
                      </span>
                      <h4 className="text-xs font-semibold text-[#1C1917] uppercase tracking-wider">
                        Related Video Lectures
                      </h4>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveTool('videos');
                        if (!currentVideoRecs) handleGenerate('videos');
                      }}
                      className="text-xs font-medium text-[#854D0E] hover:text-[#713F12] flex items-center gap-1 cursor-pointer transition-colors"
                    >
                      View all lectures →
                    </button>
                  </div>

                  {currentVideoRecs && ((currentVideoRecs.suggestions && currentVideoRecs.suggestions.length > 0) || (currentVideoRecs.external_suggestions && currentVideoRecs.external_suggestions.length > 0)) ? (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      {((currentVideoRecs.suggestions && currentVideoRecs.suggestions.length > 0)
                        ? currentVideoRecs.suggestions
                        : currentVideoRecs.external_suggestions
                      ).slice(0, 2).map((s, idx) => {
                        const yid = s.youtube_id || s.watch_url?.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/)?.[1] || '';
                        const thumb = s.thumbnail_url || (yid ? `https://img.youtube.com/vi/${yid}/hqdefault.jpg` : '');
                        const watchUrl = s.watch_url || (yid ? `https://www.youtube.com/watch?v=${yid}` : s.search_url);

                        return (
                          <div
                            key={idx}
                            onClick={() => {
                              if (onPlayVideo && yid) {
                                onPlayVideo({
                                  youtubeId: yid,
                                  title: s.title,
                                  channel: s.channel,
                                  startTime: 0,
                                });
                              } else if (watchUrl) {
                                window.open(watchUrl, '_blank', 'noopener,noreferrer');
                              }
                            }}
                            className="p-3 rounded-xl bg-[#FFFFFF] border border-[#E7E2D7] hover:border-[#CA8A04]/40 hover:bg-[#FEFCE8]/30 transition-all flex items-center gap-3 group cursor-pointer shadow-2xs"
                          >
                            {thumb ? (
                              <div className="w-16 h-12 rounded-lg overflow-hidden bg-[#1C1917] relative shrink-0">
                                <img src={thumb} alt={s.title} className="w-full h-full object-cover" />
                                <div className="absolute inset-0 bg-black/20 flex items-center justify-center">
                                  <Play size={10} className="fill-current text-[#FEF08A]" />
                                </div>
                              </div>
                            ) : null}
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-1.5 mb-1">
                                <span className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.2 rounded bg-[#FEF08A] text-[#854D0E]">
                                  {s.topic || 'Video'}
                                </span>
                                {s.channel && (
                                  <span className="text-[10px] text-[#78716C] truncate max-w-[100px]">
                                    {s.channel}
                                  </span>
                                )}
                              </div>
                              <div className="text-xs font-medium text-[#1C1917] line-clamp-1 group-hover:text-[#854D0E]">
                                {s.title}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="p-3 rounded-xl bg-[#F5F1E6]/50 border border-dashed border-[#E7E2D7] text-center">
                      <button
                        type="button"
                        onClick={() => {
                          setActiveTool('videos');
                          handleGenerate('videos');
                        }}
                        className="text-xs text-[#854D0E] font-medium hover:underline cursor-pointer"
                      >
                        Discover recommended video lectures for this document →
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* ── 2. MCQS QUIZ TOOL ── */}
        {activeTool === 'mcqs' && (
          <div className="max-w-2xl mx-auto">
            {!currentMcq && !loading ? (
              <div className="text-center py-12 bg-[#FFFFFF] border border-[#E7E2D7] rounded-2xl p-8 shadow-xs">
                <HelpCircle size={28} className="mx-auto text-[#854D0E] mb-2.5" />
                <h4 className="font-serif text-lg font-normal text-[#1C1917] mb-1">Generate Practice Quiz</h4>
                <p className="text-xs text-[#78716C] max-w-sm mx-auto mb-5 leading-relaxed">
                  Test your understanding with 5 questions formulated from your notes.
                </p>
                <button
                  type="button"
                  onClick={() => handleGenerate('mcqs')}
                  className="px-4 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-semibold shadow-xs transition-all cursor-pointer"
                >
                  Start Quiz
                </button>
              </div>
            ) : loading && !currentMcq ? (
              <div className="text-center py-16">
                <Loader2 size={24} className="animate-spin text-[#854D0E] mx-auto mb-3" />
                <p className="text-xs text-[#57534E]">Formulating quiz questions...</p>
              </div>
            ) : currentMcq ? (
              <div className="space-y-4 animate-fade-in">
                {/* Score Banner when submitted */}
                {quizSubmitted && (
                  <div className="p-3.5 rounded-xl bg-[#FEF9C3] border border-[#EAB308]/30 flex items-center justify-between text-xs">
                    <span className="font-semibold text-[#713F12]">Quiz Results</span>
                    <span className="font-bold text-[#854D0E]">
                      {
                        currentMcq.questions.filter(
                          (q, i) => userAnswers[i]?.toUpperCase() === q.correct_answer.toUpperCase()
                        ).length
                      }{' '}
                      / {currentMcq.questions.length} Correct
                    </span>
                  </div>
                )}

                {/* Questions */}
                {currentMcq.questions.map((q, idx) => {
                  const selected = userAnswers[idx];
                  const isCorrect = selected?.toUpperCase() === q.correct_answer.toUpperCase();

                  return (
                    <div
                      key={idx}
                      className="p-5 rounded-2xl bg-[#FFFFFF] border border-[#E7E2D7] shadow-xs"
                    >
                      <h4 className="text-sm font-medium text-[#1C1917] mb-3 leading-snug">
                        {idx + 1}. {q.question}
                      </h4>

                      <div className="space-y-2">
                        {q.options.map((opt) => {
                          const optLabel = opt.label.toUpperCase();
                          const isOptionSelected = selected === optLabel;
                          const isOptionCorrect = q.correct_answer.toUpperCase() === optLabel;

                          let btnStyle = 'bg-[#FAF8F2] border-[#E7E2D7] text-[#292524] hover:bg-[#F4EFE6]';

                          if (quizSubmitted) {
                            if (isOptionCorrect) {
                              btnStyle = 'bg-emerald-50 border-emerald-300 text-emerald-900 font-medium';
                            } else if (isOptionSelected && !isCorrect) {
                              btnStyle = 'bg-rose-50 border-rose-300 text-rose-900';
                            }
                          } else if (isOptionSelected) {
                            btnStyle = 'bg-[#FEF9C3] border-[#EAB308]/50 text-[#713F12] font-medium';
                          }

                          return (
                            <button
                              key={opt.label}
                              type="button"
                              disabled={quizSubmitted}
                              onClick={() => setUserAnswers((prev) => ({ ...prev, [idx]: optLabel }))}
                              className={`w-full text-left p-2.5 rounded-xl border text-xs flex items-center gap-2.5 transition-all cursor-pointer ${btnStyle}`}
                            >
                              <span
                                className={`w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold shrink-0 border ${
                                  quizSubmitted && isOptionCorrect
                                    ? 'bg-emerald-600 text-white border-emerald-600'
                                    : quizSubmitted && isOptionSelected && !isCorrect
                                    ? 'bg-rose-600 text-white border-rose-600'
                                    : isOptionSelected
                                    ? 'bg-[#854D0E] text-white border-[#854D0E]'
                                    : 'border-[#D5CDBC] text-[#78716C] bg-[#FFFFFF]'
                                }`}
                              >
                                {opt.label}
                              </span>
                              <span className="flex-1">{opt.text}</span>
                              {quizSubmitted && isOptionCorrect && (
                                <CheckCircle2 size={14} className="text-emerald-600 shrink-0" />
                              )}
                              {quizSubmitted && isOptionSelected && !isCorrect && (
                                <XCircle size={14} className="text-rose-600 shrink-0" />
                              )}
                            </button>
                          );
                        })}
                      </div>

                      {quizSubmitted && (
                        <div className="mt-3 p-3 rounded-xl bg-[#FBF9F1] border border-[#E7E2D7] text-xs text-[#57534E] animate-fade-in">
                          <p className="font-semibold text-[#713F12] mb-0.5">
                            Answer ({q.correct_answer}):
                          </p>
                          <p className="leading-relaxed">{q.explanation}</p>
                        </div>
                      )}
                    </div>
                  );
                })}

                <div className="flex justify-end pt-2">
                  {!quizSubmitted ? (
                    <button
                      type="button"
                      onClick={() => setQuizSubmitted(true)}
                      disabled={Object.keys(userAnswers).length === 0}
                      className="px-5 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] font-semibold text-xs shadow-xs disabled:opacity-40 transition-all cursor-pointer"
                    >
                      Submit Answers
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => {
                        setUserAnswers({});
                        setQuizSubmitted(false);
                      }}
                      className="px-4 py-2 rounded-xl bg-[#FFFFFF] hover:bg-[#F5F1E6] text-[#44403C] font-medium text-xs border border-[#E7E2D7] transition-all cursor-pointer"
                    >
                      Retake Quiz
                    </button>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* ── 3. FLASHCARDS TOOL ── */}
        {activeTool === 'flashcards' && (
          <div className="max-w-xl mx-auto">
            {!currentFlashcard && !loading ? (
              <div className="text-center py-12 bg-[#FFFFFF] border border-[#E7E2D7] rounded-2xl p-8 shadow-xs">
                <Layers size={28} className="mx-auto text-[#854D0E] mb-2.5" />
                <h4 className="font-serif text-lg font-normal text-[#1C1917] mb-1">Generate Flashcards</h4>
                <p className="text-xs text-[#78716C] max-w-sm mx-auto mb-5 leading-relaxed">
                  Create high-retention cards for active recall and rapid memorization.
                </p>
                <button
                  type="button"
                  onClick={() => handleGenerate('flashcards')}
                  className="px-4 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-semibold shadow-xs transition-all cursor-pointer"
                >
                  Generate Flashcards
                </button>
              </div>
            ) : loading && !currentFlashcard ? (
              <div className="text-center py-16">
                <Loader2 size={24} className="animate-spin text-[#854D0E] mx-auto mb-3" />
                <p className="text-xs text-[#57534E]">Extracting key flashcards...</p>
              </div>
            ) : currentFlashcard && currentFlashcard.flashcards.length > 0 ? (
              <div className="space-y-4 animate-fade-in flex flex-col items-center">
                <div className="w-full flex items-center justify-between text-xs text-[#78716C]">
                  <span>
                    Card {currentCardIndex + 1} of {currentFlashcard.flashcards.length}
                  </span>
                  <span className="text-[11px] text-[#A8A29E]">Press Space to flip</span>
                </div>

                {/* 3D Flip Card */}
                <div
                  className="w-full h-72 cursor-pointer select-none [perspective:1000px]"
                  onClick={handleToggleFlip}
                >
                  <div
                    className={`relative w-full h-full duration-500 [transform-style:preserve-3d] transition-transform ${
                      isFlipped ? '[transform:rotateY(180deg)]' : ''
                    }`}
                  >
                    {/* Front */}
                    <div className="absolute inset-0 w-full h-full rounded-2xl bg-[#FFFFFF] border border-[#E7E2D7] p-6 sm:p-8 flex flex-col justify-between shadow-xs [backface-visibility:hidden]">
                      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-[#854D0E]">
                        <span>Question</span>
                        <RotateCw size={13} className="opacity-50" />
                      </div>
                      <div className="my-auto text-center">
                        <p className="font-serif text-xl sm:text-2xl font-normal text-[#1C1917] leading-snug">
                          {currentFlashcard.flashcards[currentCardIndex].front}
                        </p>
                      </div>
                      <div className="text-center text-[11px] text-[#A8A29E]">Tap to reveal answer</div>
                    </div>

                    {/* Back */}
                    <div className="absolute inset-0 w-full h-full rounded-2xl bg-[#FEFCE8] border border-[#EAB308]/40 p-6 sm:p-8 flex flex-col justify-between shadow-xs [backface-visibility:hidden] [transform:rotateY(180deg)]">
                      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-[#713F12]">
                        <span>Answer</span>
                        <RotateCw size={13} className="opacity-50" />
                      </div>
                      <div className="my-auto text-center">
                        <p className="text-sm sm:text-base text-[#292524] leading-relaxed">
                          {currentFlashcard.flashcards[currentCardIndex].back}
                        </p>
                      </div>
                      <div className="text-center text-[11px] text-[#713F12]/60">Tap to return</div>
                    </div>
                  </div>
                </div>

                {/* Nav Controls */}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    disabled={currentCardIndex === 0}
                    onClick={handlePrevCard}
                    className="p-2 rounded-xl bg-[#FFFFFF] hover:bg-[#F5F1E6] disabled:opacity-30 border border-[#E7E2D7] text-[#1C1917] transition-colors cursor-pointer shadow-xs"
                    title="Previous"
                  >
                    <ChevronLeft size={16} />
                  </button>

                  <button
                    type="button"
                    onClick={handleToggleFlip}
                    className="px-3.5 py-1.5 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] font-semibold text-xs transition-colors cursor-pointer shadow-xs"
                  >
                    Flip
                  </button>

                  <button
                    type="button"
                    disabled={currentCardIndex === currentFlashcard.flashcards.length - 1}
                    onClick={handleNextCard}
                    className="p-2 rounded-xl bg-[#FFFFFF] hover:bg-[#F5F1E6] disabled:opacity-30 border border-[#E7E2D7] text-[#1C1917] transition-colors cursor-pointer shadow-xs"
                    title="Next"
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        )}

        {/* ── 4. VIVA PREP TOOL ── */}
        {activeTool === 'viva' && (
          <div className="max-w-2xl mx-auto">
            {!currentViva && !loading ? (
              <div className="text-center py-12 bg-[#FFFFFF] border border-[#E7E2D7] rounded-2xl p-8 shadow-xs">
                <Award size={28} className="mx-auto text-[#854D0E] mb-2.5" />
                <h4 className="font-serif text-lg font-normal text-[#1C1917] mb-1">Oral Exam & Viva Prep</h4>
                <p className="text-xs text-[#78716C] max-w-sm mx-auto mb-5 leading-relaxed">
                  Practice responding to challenging oral examination questions from professors.
                </p>
                <button
                  type="button"
                  onClick={() => handleGenerate('viva')}
                  className="px-4 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-semibold shadow-xs transition-all cursor-pointer"
                >
                  Generate Questions
                </button>
              </div>
            ) : loading && !currentViva ? (
              <div className="text-center py-16">
                <Loader2 size={24} className="animate-spin text-[#854D0E] mx-auto mb-3" />
                <p className="text-xs text-[#57534E]">Preparing oral exam questions...</p>
              </div>
            ) : currentViva ? (
              <div className="space-y-3 animate-fade-in">
                {currentViva.questions.map((item, idx) => {
                  const isExpanded = !!expandedAnswers[idx];

                  return (
                    <div
                      key={idx}
                      className="p-4 rounded-xl bg-[#FFFFFF] border border-[#E7E2D7] shadow-xs"
                    >
                      <div className="flex items-start justify-between gap-3 mb-1.5">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-[#854D0E] bg-[#FEF9C3] px-2 py-0.5 rounded-md">
                          {item.category || 'Theory'}
                        </span>

                        <button
                          type="button"
                          onClick={() =>
                            setExpandedAnswers((prev) => ({ ...prev, [idx]: !prev[idx] }))
                          }
                          className="flex items-center gap-1 text-[11px] font-medium text-[#78716C] hover:text-[#1C1917] cursor-pointer"
                        >
                          {isExpanded ? <EyeOff size={12} /> : <Eye size={12} />}
                          <span>{isExpanded ? 'Hide' : 'Reveal'}</span>
                        </button>
                      </div>

                      <h4 className="text-xs sm:text-sm font-medium text-[#1C1917] leading-snug">
                        {idx + 1}. {item.question}
                      </h4>

                      {isExpanded && (
                        <div className="mt-3 pt-3 border-t border-[#F5F1E6] text-xs text-[#44403C] leading-relaxed animate-fade-in">
                          <p className="font-semibold text-[#713F12] mb-1">Model Answer:</p>
                          <p className="whitespace-pre-wrap">{item.model_answer}</p>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : null}
          </div>
        )}

        {/* ── 5. VIDEO LECTURES TOOL ── */}
        {activeTool === 'videos' && (
          <div className="max-w-5xl mx-auto space-y-6">
            {!currentVideoRecs && !loading ? (
              <div className="text-center py-12 bg-[#FFFFFF] border border-[#E7E2D7] rounded-2xl p-8 shadow-xs">
                <Video size={28} className="mx-auto text-[#854D0E] mb-2.5" />
                <h4 className="font-serif text-lg font-normal text-[#1C1917] mb-1">
                  Educational Video Recommendations
                </h4>
                <p className="text-xs text-[#78716C] max-w-md mx-auto mb-5 leading-relaxed">
                  Discover the most directly relevant video lectures, conceptual deep-dives, and tutorials tailored specifically to <span className="font-medium text-[#44403C]">{currentDoc.filename}</span>.
                </p>
                <button
                  type="button"
                  onClick={() => handleGenerate('videos')}
                  className="px-4 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-semibold shadow-xs transition-all cursor-pointer"
                >
                  Find Relevant Video Lectures
                </button>
              </div>
            ) : loading && !currentVideoRecs ? (
              <div className="space-y-5 animate-fade-in">
                <div className="flex items-center justify-between px-1">
                  <div>
                    <div className="h-6 w-64 bg-[#E7E2D7]/60 rounded-md animate-pulse mb-1.5" />
                    <div className="h-3.5 w-96 bg-[#E7E2D7]/40 rounded-md animate-pulse" />
                  </div>
                  <div className="flex items-center gap-2 text-xs text-[#854D0E] font-medium">
                    <Loader2 size={14} className="animate-spin text-[#854D0E]" />
                    <span>Finding best video lectures...</span>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className="rounded-2xl bg-[#FFFFFF] border border-[#E7E2D7] overflow-hidden shadow-xs animate-pulse"
                    >
                      <div className="w-full aspect-video bg-[#EAE3D4]/50" />
                      <div className="p-4 sm:p-5 space-y-3">
                        <div className="h-3 w-28 bg-[#FEF08A]/80 rounded-md" />
                        <div className="h-5 w-5/6 bg-[#E7E2D7]/80 rounded-md" />
                        <div className="h-3.5 w-full bg-[#E7E2D7]/40 rounded-md" />
                        <div className="h-3.5 w-4/6 bg-[#E7E2D7]/40 rounded-md" />
                        <div className="pt-2 flex justify-between items-center border-t border-[#F5F1E6]">
                          <div className="h-3.5 w-24 bg-[#E7E2D7]/60 rounded-md" />
                          <div className="h-6 w-20 bg-[#E7E2D7]/40 rounded-lg" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : currentVideoRecs ? (
              <div className="space-y-5 animate-fade-in">
                {/* Header & Refresh */}
                <div className="flex items-center justify-between px-1">
                  <div>
                    <h3 className="font-serif text-xl text-[#1C1917]">
                      Recommended Lectures for {currentDoc.filename}
                    </h3>
                    <p className="text-xs text-[#78716C] mt-0.5">
                      Click any thumbnail or watch button to play directly in IntelliNotes, or open on YouTube.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleGenerate('videos', true)}
                    disabled={loading}
                    className="p-2 rounded-xl border border-[#E7E2D7] bg-[#FFFFFF] hover:bg-[#F5F1E6] text-[#78716C] hover:text-[#1C1917] transition-all cursor-pointer disabled:opacity-50 flex items-center gap-1.5 text-xs font-medium shadow-2xs"
                    title="Refresh recommendations"
                  >
                    <RefreshCw size={13} className={loading ? 'animate-spin' : ''} />
                    <span>Refresh</span>
                  </button>
                </div>

                {/* Large 2-Column Video Cards Grid */}
                {(() => {
                  const items = (currentVideoRecs.suggestions && currentVideoRecs.suggestions.length > 0)
                    ? currentVideoRecs.suggestions
                    : currentVideoRecs.external_suggestions || [];

                  if (items.length === 0) {
                    return (
                      <div className="text-center py-10 bg-[#FFFFFF] border border-[#E7E2D7] rounded-2xl p-6">
                        <p className="text-xs text-[#78716C]">No video suggestions found for this document yet.</p>
                      </div>
                    );
                  }

                  return (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      {items.map((s, idx) => {
                        const yid = s.youtube_id || s.watch_url?.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/)?.[1] || '';
                        const thumb = s.thumbnail_url || (yid ? `https://img.youtube.com/vi/${yid}/hqdefault.jpg` : '');
                        const watchUrl = s.watch_url || (yid ? `https://www.youtube.com/watch?v=${yid}` : s.search_url);

                        return (
                          <div
                            key={idx}
                            className="rounded-2xl bg-[#FFFFFF] border border-[#E7E2D7] hover:border-[#CA8A04]/40 hover:shadow-md transition-all flex flex-col overflow-hidden group shadow-xs"
                          >
                            {/* Big 16:9 Thumbnail preview with play badge */}
                            <div
                              onClick={() => {
                                if (onPlayVideo && yid) {
                                  onPlayVideo({
                                    youtubeId: yid,
                                    title: s.title,
                                    channel: s.channel,
                                    startTime: 0,
                                  });
                                } else if (watchUrl) {
                                  window.open(watchUrl, '_blank', 'noopener,noreferrer');
                                }
                              }}
                              className="w-full aspect-video overflow-hidden bg-[#1C1917] relative cursor-pointer border-b border-[#E7E2D7]/80"
                              title={yid ? "Click to play in IntelliNotes" : "Click to view video"}
                            >
                              {thumb ? (
                                <img
                                  src={thumb}
                                  alt={s.title}
                                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                                  loading="lazy"
                                  onError={(e) => {
                                    const target = e.currentTarget;
                                    if (yid && !target.src.includes('mqdefault')) {
                                      target.src = `https://img.youtube.com/vi/${yid}/mqdefault.jpg`;
                                    }
                                  }}
                                />
                              ) : (
                                <div className="w-full h-full flex flex-col items-center justify-center bg-gradient-to-br from-[#292524] to-[#1C1917] text-[#FEF08A] p-4 text-center">
                                  <Video size={36} className="mb-2 text-[#FEF08A]/80" />
                                  <span className="text-xs text-[#E7E2D7] font-medium line-clamp-1">{s.title}</span>
                                </div>
                              )}
                              <div className="absolute inset-0 bg-black/20 flex items-center justify-center group-hover:bg-black/35 transition-colors">
                                <div className="w-12 h-12 rounded-full bg-[#FEF08A] text-[#713F12] flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                                  <Play size={18} className="fill-current ml-0.5" />
                                </div>
                              </div>
                            </div>

                            {/* Details & Rationale */}
                            <div className="p-4 sm:p-5 flex-1 flex flex-col justify-between">
                              <div>
                                <div className="flex flex-wrap items-center gap-2 mb-2">
                                  <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#FEF08A] text-[#854D0E]">
                                    {s.topic || 'Relevant Lecture'}
                                  </span>
                                  {s.channel && (
                                    <span className="text-xs font-medium text-[#57534E]">
                                      {s.channel}
                                    </span>
                                  )}
                                </div>

                                <h4
                                  onClick={() => {
                                    if (onPlayVideo && yid) {
                                      onPlayVideo({
                                        youtubeId: yid,
                                        title: s.title,
                                        channel: s.channel,
                                        startTime: 0,
                                      });
                                    } else if (watchUrl) {
                                      window.open(watchUrl, '_blank', 'noopener,noreferrer');
                                    }
                                  }}
                                  className="font-serif text-base font-normal text-[#1C1917] mb-2 line-clamp-2 group-hover:text-[#854D0E] transition-colors cursor-pointer"
                                >
                                  {s.title}
                                </h4>

                                <p className="text-xs text-[#78716C] leading-relaxed line-clamp-2 mb-4">
                                  {s.rationale}
                                </p>
                              </div>

                              {/* Action Buttons */}
                              <div className="flex items-center gap-2 pt-2 border-t border-[#F5F1E6]">
                                {yid ? (
                                  <button
                                    type="button"
                                    onClick={() => {
                                      if (onPlayVideo) {
                                        onPlayVideo({
                                          youtubeId: yid,
                                          title: s.title,
                                          channel: s.channel,
                                          startTime: 0,
                                        });
                                      } else if (watchUrl) {
                                        window.open(watchUrl, '_blank', 'noopener,noreferrer');
                                      }
                                    }}
                                    className="flex-1 px-3.5 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-semibold flex items-center justify-center gap-1.5 shadow-2xs transition-all cursor-pointer"
                                  >
                                    <Play size={12} className="fill-current" />
                                    <span>Watch Video</span>
                                  </button>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => handleGenerate('videos', true)}
                                    className="flex-1 px-3.5 py-2 rounded-xl bg-[#FEF08A] hover:bg-[#FDE047] text-[#713F12] text-xs font-semibold flex items-center justify-center gap-1.5 shadow-2xs transition-all cursor-pointer"
                                  >
                                    <RefreshCw size={12} />
                                    <span>Load Video Player</span>
                                  </button>
                                )}

                                {watchUrl && (
                                  <a
                                    href={watchUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="px-3.5 py-2 rounded-xl bg-[#F5F1E6] hover:bg-[#EAE3D4] text-[#1C1917] text-xs font-medium transition-colors flex items-center gap-1.5 cursor-pointer shrink-0"
                                    title="Open video on YouTube in a new tab"
                                  >
                                    <span>YouTube</span>
                                    <ExternalLink size={12} />
                                  </a>
                                )}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  );
                })()}
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Fullscreen PDF Showcase Modal */}
      <PdfShowcaseModal
        document={showPdfModal && currentDoc ? currentDoc : null}
        onClose={() => setShowPdfModal(false)}
      />
    </div>
  );
}
