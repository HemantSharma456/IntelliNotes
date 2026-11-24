import { useState } from 'react';
import { FileText, Video, Play, ExternalLink, ChevronDown, ChevronUp } from 'lucide-react';
import type { Citation } from '../types';

interface CitationCardProps {
  citations: Citation[];
  onPlayVideo?: (req: { youtubeId: string; title: string; channel?: string | null; startTime?: number }) => void;
}

function formatSeconds(sec?: number | null): string {
  if (sec == null) return '00:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

export default function CitationCard({ citations, onPlayVideo }: CitationCardProps) {
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!citations.length) return null;

  const docCount = citations.filter((c) => c.source_type !== 'video').length;
  const videoCount = citations.filter((c) => c.source_type === 'video').length;

  return (
    <div className="mt-3 pt-3 border-t border-[#E7E2D7] animate-fade-in">
      <div className="text-[11px] font-semibold text-[#78716C] uppercase tracking-wider mb-2 flex items-center gap-2">
        <span className="flex items-center gap-1 text-[#854D0E]">
          {videoCount > 0 ? <Video size={12} /> : <FileText size={12} />}
          <span>Sources ({citations.length})</span>
        </span>
        {videoCount > 0 && docCount > 0 && (
          <span className="text-[10px] text-[#A8A29E] font-normal normal-case">
            ({docCount} doc{docCount > 1 ? 's' : ''}, {videoCount} video{videoCount > 1 ? 's' : ''})
          </span>
        )}
      </div>

      <div className="space-y-1.5">
        {citations.map((c, i) => {
          const isItemExpanded = expanded === c.chunk_id;
          const isVideo = c.source_type === 'video';

          return (
            <div
              key={c.chunk_id + '-' + i}
              className={`rounded-xl border transition-all overflow-hidden ${
                isVideo
                  ? 'border-[#FDE68A] bg-[#FFFBEB] hover:border-[#FCD34D]'
                  : 'border-[#E7E2D7] bg-[#FAF8F2] hover:border-[#D5CDBC]'
              }`}
            >
              <button
                id={`citation-${i}`}
                type="button"
                onClick={() => setExpanded(isItemExpanded ? null : c.chunk_id)}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-[#F4EFE6]/70 transition-colors cursor-pointer"
              >
                {isVideo ? (
                  <span className="w-5 h-5 rounded-md bg-[#FDE68A] text-[#92400E] text-[10px] font-bold flex items-center justify-center shrink-0">
                    <Video size={11} />
                  </span>
                ) : (
                  <span className="w-5 h-5 rounded-md bg-[#FEF08A] text-[#713F12] text-[10px] font-bold flex items-center justify-center shrink-0">
                    {i + 1}
                  </span>
                )}

                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-medium text-[#1C1917] truncate block">
                      {isVideo ? c.video_title || 'Video Lecture' : c.document_name}
                    </span>
                  </div>
                  <div className="text-[10px] text-[#78716C] flex items-center gap-1.5">
                    {isVideo ? (
                      <span>
                        {c.channel ? `${c.channel} • ` : ''}clip at {formatSeconds(c.start_time)}
                      </span>
                    ) : c.page ? (
                      <span>Page {c.page}</span>
                    ) : (
                      <span>Document text</span>
                    )}
                  </div>
                </div>

                {isVideo && c.timestamp_url && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      const match = c.timestamp_url?.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
                      const yid = match ? match[1] : (c.video_id || '');
                      if (onPlayVideo && yid) {
                        onPlayVideo({
                          youtubeId: yid,
                          title: c.video_title || 'Video Lecture',
                          channel: c.channel,
                          startTime: c.start_time || 0,
                        });
                      } else if (c.timestamp_url) {
                        window.open(c.timestamp_url, '_blank', 'noopener,noreferrer');
                      }
                    }}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-lg text-[10px] font-semibold bg-[#FEF08A] text-[#713F12] hover:bg-[#FDE047] transition-all shrink-0 border border-[#FDE68A] cursor-pointer"
                    title="Watch clip in IntelliNotes player"
                  >
                    <Play size={9} className="fill-current" />
                    <span>{formatSeconds(c.start_time)}</span>
                  </button>
                )}

                <div className="text-[#78716C] p-0.5">
                  {isItemExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                </div>
              </button>

              {isItemExpanded && (
                <div className="px-3 pb-3 pt-1 animate-fade-in">
                  <div className="text-xs text-[#44403C] leading-relaxed p-2.5 rounded-lg bg-[#FFFFFF] border border-[#E7E2D7] italic font-serif">
                    &ldquo;{c.excerpt}&rdquo;
                  </div>
                  {isVideo && c.timestamp_url && (
                    <div className="mt-2 flex items-center justify-between text-[11px] text-[#78716C] px-0.5">
                      <span>
                        Timestamp span: {formatSeconds(c.start_time)} – {formatSeconds(c.end_time)}
                      </span>
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          onClick={() => {
                            const match = c.timestamp_url?.match(/(?:v=|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
                            const yid = match ? match[1] : (c.video_id || '');
                            if (onPlayVideo && yid) {
                              onPlayVideo({
                                youtubeId: yid,
                                title: c.video_title || 'Video Lecture',
                                channel: c.channel,
                                startTime: c.start_time || 0,
                              });
                            } else if (c.timestamp_url) {
                              window.open(c.timestamp_url, '_blank', 'noopener,noreferrer');
                            }
                          }}
                          className="inline-flex items-center gap-1 text-[#854D0E] font-semibold hover:underline text-[11px] cursor-pointer"
                        >
                          <Play size={10} className="fill-current" /> Watch in Player
                        </button>
                        <a
                          href={c.timestamp_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-[#78716C] hover:text-[#1C1917] text-[11px]"
                        >
                          <span>YouTube</span> <ExternalLink size={10} />
                        </a>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
