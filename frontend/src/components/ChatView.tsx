import { useState, useRef, useEffect } from 'react';
import {
  Send,
  Loader2,
  AlertTriangle,
  User,
  Bot,
  Key,
  Copy,
  Check,
  ArrowRight,
  Sparkles,
  FileText,
  Video,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { ConversationMessage, DocumentMeta, ChatMessage, SourceMode } from '../types';
import { streamChatMessage } from '../services/api';
import CitationCard from './CitationCard';

interface ChatViewProps {
  selectedDoc: DocumentMeta | null;
  messages: ConversationMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ConversationMessage[]>>;
  onOpenStudyTools?: () => void;
  onPlayVideo?: (req: { youtubeId: string; title: string; channel?: string | null; startTime?: number }) => void;
}

export default function ChatView({
  selectedDoc,
  messages,
  setMessages,
  onPlayVideo,
}: ChatViewProps) {
  const [input, setInput] = useState('');
  const [sourceMode, setSourceMode] = useState<SourceMode>('all');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (textToSend?: string) => {
    const question = (textToSend || input).trim();
    if (!question || loading) return;

    setInput('');
    setError(null);

    const userMsg: ConversationMessage = { role: 'user', content: question };
    const streamingAssistantMsg: ConversationMessage = {
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, streamingAssistantMsg]);
    setLoading(true);

    try {
      const history: ChatMessage[] = messages.slice(-10).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      await streamChatMessage(question, selectedDoc?.id, history, {
        onMetadata: (data) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === 'assistant') {
              last.citations = data.citations;
              last.insufficient_context = data.insufficient_context;
            }
            return next;
          });
        },
        onToken: (token) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === 'assistant') {
              last.content += token;
            }
            return next;
          });
        },
        onDone: (data) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === 'assistant') {
              last.isStreaming = false;
              last.latency_ms = data.latency_ms;
            }
            return next;
          });
          setLoading(false);
        },
        onError: (err) => {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === 'assistant') {
              last.isStreaming = false;
              if (!last.content) {
                return next.slice(0, -1);
              }
            }
            return next;
          });
          setError(err);
          setLoading(false);
        },
      }, sourceMode);
    } catch (err: any) {
      setMessages((prev) => {
        const next = [...prev];
        const last = next[next.length - 1];
        if (last && last.role === 'assistant' && !last.content) {
          return next.slice(0, -1);
        }
        return next;
      });
      setError(err.message || 'Failed to stream response. Please check your AI configuration.');
      setLoading(false);
    }
  };


  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const copyMessageContent = (content: string, index: number) => {
    navigator.clipboard.writeText(content);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 130)}px`;
    }
  }, [input]);

  const starterPrompts = [
    selectedDoc
      ? `Summarize the core concepts in ${selectedDoc.filename}`
      : 'Summarize the key ideas from my notes',
    'Explain the most challenging concept in simple terms',
    'What key exam or viva questions could be asked on this?',
    'Give me 3 practice questions with answers to test my knowledge',
  ];

  return (
    <div className="flex-1 flex flex-col h-full min-h-0 bg-[#faf8f0] overflow-hidden relative text-[#1C1917]">
      {/* ── Minimal Header with Multimodal Source Mode Pills ── */}
      <div className="px-5 py-2.5 border-b border-[#e7e2d7] bg-[#f4f0e4]/80 backdrop-blur-md flex items-center justify-between z-10 shrink-0">
        <div className="flex items-center gap-2.5 text-xs">
          <div className="w-6 h-6 rounded-lg bg-[#1a1714] text-[#fde047] flex items-center justify-center shrink-0 shadow-sm">
            <Bot size={13} />
          </div>
          <span className="font-sans font-700 text-xs sm:text-sm text-[#1C1917]">AI Tutor Chat</span>
          {selectedDoc && (
            <span className="inline-flex items-center gap-1 text-[11px] px-2.5 py-0.5 rounded-full bg-[#fef9c3] text-[#713f12] font-semibold border border-[#eab308]/30 truncate max-w-[180px] sm:max-w-[240px]">
              <FileText size={10} className="text-[#854d0e]" />
              <span className="truncate">{selectedDoc.filename}</span>
            </span>
          )}
        </div>

        {/* Source Mode Pill Selector */}
        <div className="flex items-center gap-1 p-1 rounded-2xl bg-[#e5dfd2]/80 border border-[#e7e2d7]">
          <button
            type="button"
            onClick={() => setSourceMode('all')}
            className={`px-3 py-1 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
              sourceMode === 'all'
                ? 'bg-[#1a1714] text-[#ffffff] shadow-sm font-semibold'
                : 'text-[#78716C] hover:text-[#1C1917]'
            }`}
            title="Search both uploaded documents and lecture videos"
          >
            <Sparkles size={11} className={sourceMode === 'all' ? 'text-[#fde047]' : 'text-[#78716C]'} />
            <span className="hidden sm:inline">All Sources</span>
            <span className="sm:hidden">All</span>
          </button>

          <button
            type="button"
            onClick={() => setSourceMode('documents')}
            className={`px-3 py-1 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
              sourceMode === 'documents'
                ? 'bg-[#1a1714] text-[#ffffff] shadow-sm font-semibold'
                : 'text-[#78716C] hover:text-[#1C1917]'
            }`}
            title="Search only uploaded text documents and PDFs"
          >
            <FileText size={11} className={sourceMode === 'documents' ? 'text-[#fde047]' : 'text-[#78716C]'} />
            <span>Documents</span>
          </button>

          <button
            type="button"
            onClick={() => setSourceMode('videos')}
            className={`px-3 py-1 rounded-xl text-xs font-medium transition-all flex items-center gap-1.5 cursor-pointer ${
              sourceMode === 'videos'
                ? 'bg-[#1a1714] text-[#ffffff] shadow-sm font-semibold'
                : 'text-[#78716C] hover:text-[#1C1917]'
            }`}
            title="Search only ingested educational video lecture transcripts"
          >
            <Video size={11} className={sourceMode === 'videos' ? 'text-[#fde047]' : 'text-[#78716C]'} />
            <span>Videos</span>
          </button>
        </div>
      </div>

      {/* ── STATE 1: WELCOME SCREEN ── */}
      {messages.length === 0 && !loading ? (
        <div className="flex-1 min-h-0 overflow-y-auto px-4 py-10 flex flex-col items-center justify-center">
          <div className="w-full max-w-[640px] mx-auto flex flex-col items-center text-center animate-fade-in-up">
            <div className="w-14 h-14 rounded-2xl bg-[#1a1714] text-[#fde047] flex items-center justify-center mb-4 shadow-md">
              <Bot size={26} />
            </div>

            <h2 className="font-sans text-2xl sm:text-3xl font-700 text-[#1C1917] tracking-tight mb-2">
              What would you like to explore?
            </h2>

            <p className="text-xs sm:text-sm text-[#78716C] max-w-md leading-relaxed mb-6">
              Ask questions grounded directly in your uploaded study notes and video lectures, with interactive timestamp citations.
            </p>

            {/* Central Minimal Input Box */}
            <div className="w-full bg-[#FFFFFF] border border-[#e7e2d7] focus-within:border-[#ca8a04] focus-within:ring-2 focus-within:ring-[#fef08a] rounded-2xl p-3.5 shadow-sm transition-all mb-7 text-left">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  selectedDoc
                    ? `Ask anything about ${selectedDoc.filename}...`
                    : 'Ask a question about your study materials...'
                }
                rows={2}
                className="w-full bg-transparent text-sm text-[#1C1917] placeholder-[#A8A29E] outline-none resize-none leading-relaxed py-1 px-1"
                disabled={loading}
              />

              <div className="flex items-center justify-between pt-2 border-t border-[#f4f0e4] mt-1 px-1">
                <span className="text-[11px] text-[#A8A29E]">
                  Press <kbd className="px-1.5 py-0.5 rounded bg-[#f5f1e6] text-[#78716C] text-[10px] font-mono">Enter</kbd> to ask
                </span>

                <button
                  type="button"
                  onClick={() => handleSend()}
                  disabled={!input.trim() || loading}
                  className="btn-pill btn-pill-primary text-xs py-1.5 px-3.5"
                >
                  <span>Ask</span>
                  <Send size={11} />
                </button>
              </div>
            </div>

            {/* Minimal Starter Prompt Cards */}
            <div className="w-full text-left">
              <span className="text-[10px] font-700 uppercase tracking-widest text-[#a8a29e] block mb-2 px-1">
                Suggested Prompts
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                {starterPrompts.map((prompt, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleSend(prompt)}
                    className="p-3.5 rounded-xl bg-[#FFFFFF] hover:bg-[#fefce8] border border-[#e7e2d7] hover:border-[#ca8a04]/40 text-left transition-all group flex items-start justify-between gap-2 shadow-xs cursor-pointer"
                  >
                    <span className="text-xs text-[#44403C] group-hover:text-[#1C1917] leading-relaxed">
                      {prompt}
                    </span>
                    <ArrowRight size={13} className="text-[#A8A29E] group-hover:text-[#854D0E] shrink-0 mt-0.5 transition-colors" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* ── STATE 2: ACTIVE CONVERSATION ── */
        <>
          {/* Messages Stream */}
          <div className="flex-1 min-h-0 overflow-y-auto px-4 py-6">
            <div className="w-full max-w-[720px] mx-auto space-y-5">
              {messages.map((msg, i) => (
                <div
                  key={i}
                  className={`flex gap-3 ${
                    msg.role === 'user' ? 'justify-end' : 'justify-start'
                  } animate-fade-in`}
                >
                  {/* Assistant Icon */}
                  {msg.role === 'assistant' && (
                    <div className="w-7 h-7 rounded-lg bg-[#FEF08A] border border-[#EAB308]/40 flex items-center justify-center shrink-0 text-[#854D0E] mt-1 shadow-xs">
                      <Bot size={14} />
                    </div>
                  )}

                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-xs relative group ${
                      msg.role === 'user'
                        ? 'bg-[#FEF08A] text-[#1C1917] border border-[#EAB308]/30 rounded-br-xs'
                        : 'bg-[#FFFFFF] border border-[#E7E2D7] text-[#1C1917] rounded-bl-xs'
                    }`}
                  >
                    {msg.role === 'user' ? (
                      <p className="text-sm leading-relaxed whitespace-pre-wrap font-normal">
                        {msg.content}
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {/* Notice & Copy Actions */}
                        <div className="flex items-center justify-between gap-2">
                          {msg.insufficient_context ? (
                            <div className="flex items-center gap-1.5 text-amber-700 text-xs">
                              <AlertTriangle size={12} className="shrink-0" />
                              <span>Limited matching context found</span>
                            </div>
                          ) : (
                            <span className="text-[11px] text-[#78716C] font-medium">Answer</span>
                          )}

                          <button
                            type="button"
                            onClick={() => copyMessageContent(msg.content, i)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1 text-[11px] text-[#78716C] hover:text-[#1C1917] bg-[#F5F1E6] px-2 py-0.5 rounded-md border border-[#E7E2D7] cursor-pointer"
                            title="Copy response"
                          >
                            {copiedIndex === i ? (
                              <Check size={11} className="text-emerald-600" />
                            ) : (
                              <Copy size={11} />
                            )}
                            <span>{copiedIndex === i ? 'Copied' : 'Copy'}</span>
                          </button>
                        </div>

                        {/* Formatted Markdown */}
                        {msg.isStreaming && !msg.content ? (
                          <div className="flex items-center gap-2 text-xs text-[#78716C] py-1">
                            <Loader2 size={13} className="animate-spin text-[#854D0E]" />
                            <span>Consulting sources...</span>
                          </div>
                        ) : (
                          <div className="prose max-w-none text-sm text-[#292524] leading-relaxed">
                            <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]}>
                              {msg.content}
                            </ReactMarkdown>
                            {msg.isStreaming && (
                              <span className="inline-block w-1.5 h-3.5 bg-[#854D0E] ml-1 animate-pulse rounded-xs align-middle" />
                            )}
                          </div>
                        )}

                        {/* Citations */}
                        {msg.citations && msg.citations.length > 0 && (
                          <CitationCard citations={msg.citations} onPlayVideo={onPlayVideo} />
                        )}
                      </div>
                    )}
                  </div>

                  {/* User Avatar */}
                  {msg.role === 'user' && (
                    <div className="w-7 h-7 rounded-lg bg-[#F5F1E6] border border-[#E7E2D7] flex items-center justify-center shrink-0 text-[#78716C] mt-1 shadow-xs">
                      <User size={13} />
                    </div>
                  )}
                </div>
              ))}


              {/* Error Box */}
              {error && (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs space-y-2 animate-fade-in">
                  <p className="font-semibold text-rose-900">{error}</p>
                  {error.toLowerCase().includes('gemini_api_key') && (
                    <div className="p-2.5 rounded-lg bg-[#FFFFFF] border border-rose-200 text-[#44403C] text-[11px] space-y-1">
                      <p className="font-medium text-amber-800 flex items-center gap-1">
                        <Key size={12} />
                        <span>Action Required:</span>
                      </p>
                      <p>
                        Set <code className="text-amber-900 font-mono">GEMINI_API_KEY</code> in <code className="font-mono">backend/.env</code> and restart the server.
                      </p>
                    </div>
                  )}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Fixed Bottom Input Area */}
          <div className="shrink-0 border-t border-[#e7e2d7] bg-[#faf8f0] px-4 py-3">
            <div className="w-full max-w-[720px] mx-auto">
              <div className="flex items-end gap-2 bg-[#FFFFFF] border border-[#e7e2d7] focus-within:border-[#ca8a04] focus-within:ring-2 focus-within:ring-[#fef08a] rounded-2xl px-3.5 py-2.5 shadow-sm transition-all">
                <textarea
                  id="chat-input"
                  ref={textareaRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    selectedDoc
                      ? `Ask anything about ${selectedDoc.filename}...`
                      : 'Ask a question about your study materials...'
                  }
                  rows={1}
                  className="flex-1 bg-transparent text-sm text-[#1C1917] placeholder-[#A8A29E] outline-none resize-none max-h-32 leading-relaxed py-1"
                  disabled={loading}
                />

                <button
                  id="send-btn"
                  type="button"
                  onClick={() => handleSend()}
                  disabled={!input.trim() || loading}
                  className="shrink-0 w-8 h-8 rounded-xl bg-[#1a1714] hover:bg-[#2d2926] text-white flex items-center justify-center disabled:opacity-30 transition-all shadow-sm active:scale-95 cursor-pointer"
                  title="Send question"
                >
                  {loading ? (
                    <Loader2 size={14} className="animate-spin text-white" />
                  ) : (
                    <Send size={13} className="translate-x-0.5 text-[#fde047]" />
                  )}
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
