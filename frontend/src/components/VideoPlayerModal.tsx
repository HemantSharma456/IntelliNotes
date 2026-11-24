import { useEffect } from 'react';
import { X, ExternalLink, Video } from 'lucide-react';

export interface VideoPlayRequest {
  youtubeId: string;
  title: string;
  channel?: string | null;
  startTime?: number;
}

interface VideoPlayerModalProps {
  video: VideoPlayRequest | null;
  onClose: () => void;
}

export default function VideoPlayerModal({ video, onClose }: VideoPlayerModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (video) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [video, onClose]);

  if (!video) return null;

  const startSec = Math.floor(video.startTime || 0);
  const m = Math.floor(startSec / 60);
  const s = startSec % 60;
  const timeFormatted = `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  const embedUrl = `https://www.youtube-nocookie.com/embed/${video.youtubeId}?start=${startSec}&autoplay=1&rel=0`;
  const watchUrl = `https://www.youtube.com/watch?v=${video.youtubeId}&t=${startSec}s`;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 bg-[#1C1917]/75 backdrop-blur-xs flex items-center justify-center p-3 sm:p-6 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-[#FBF9F1] border border-[#E7E2D7] rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-4 py-3 bg-[#F5F1E6] border-b border-[#E7E2D7] flex items-center justify-between gap-3">
          <div className="min-w-0 flex items-center gap-2.5">
            <span className="p-1.5 rounded-lg bg-[#FEF08A] text-[#854D0E] shrink-0 shadow-2xs">
              <Video size={15} />
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-[#1C1917] truncate max-w-[280px] sm:max-w-md">
                  {video.title}
                </span>
                {video.startTime !== undefined && (
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-[#FEF08A] text-[#713F12] font-semibold shrink-0">
                    {timeFormatted}
                  </span>
                )}
              </div>
              {video.channel && (
                <p className="text-[11px] text-[#78716C] truncate">{video.channel}</p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <a
              href={watchUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#EAE3D4] transition-colors flex items-center gap-1 text-xs cursor-pointer"
              title="Open video on YouTube"
            >
              <ExternalLink size={14} />
              <span className="hidden sm:inline">YouTube</span>
            </a>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#EAE3D4] transition-colors cursor-pointer"
              title="Close player (Esc)"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* 16:9 Video Player */}
        <div className="relative aspect-video w-full bg-black">
          <iframe
            src={embedUrl}
            title={video.title}
            className="w-full h-full border-0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          />
        </div>

        {/* Modal Footer / Context info */}
        <div className="px-4 py-2.5 bg-[#F5F1E6]/60 border-t border-[#E7E2D7] flex items-center justify-between text-[11px] text-[#78716C]">
          <span>Playing from {timeFormatted}</span>
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-[#854D0E] font-medium hover:underline cursor-pointer"
          >
            Done studying
          </button>
        </div>
      </div>
    </div>
  );
}
