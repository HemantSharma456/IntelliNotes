import { useEffect } from 'react';
import { X, ExternalLink, Download, FileText } from 'lucide-react';
import type { DocumentMeta } from '../types';
import { getDocumentFileUrl } from '../services/api';

interface PdfShowcaseModalProps {
  document: DocumentMeta | null;
  onClose: () => void;
}

export default function PdfShowcaseModal({ document: doc, onClose }: PdfShowcaseModalProps) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    if (doc) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [doc, onClose]);

  if (!doc) return null;

  const fileUrl = getDocumentFileUrl(doc.id);
  const sizeMb = (doc.file_size / (1024 * 1024)).toFixed(2);

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 bg-[#1C1917]/80 backdrop-blur-xs flex items-center justify-center p-2 sm:p-5 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="bg-[#FBF9F1] border border-[#E7E2D7] rounded-2xl w-full max-w-6xl h-[94vh] overflow-hidden shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-4 py-3 bg-[#F5F1E6] border-b border-[#E7E2D7] flex items-center justify-between gap-3 shrink-0">
          <div className="min-w-0 flex items-center gap-2.5">
            <span className="p-1.5 rounded-lg bg-[#FEF08A] text-[#854D0E] shrink-0 shadow-2xs">
              <FileText size={16} />
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-xs sm:text-sm font-semibold text-[#1C1917] truncate max-w-[240px] sm:max-w-md">
                  {doc.filename}
                </span>
                <span className="text-[10px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-[#FEF08A] text-[#713F12]">
                  {doc.file_type}
                </span>
                {doc.num_pages !== null && (
                  <span className="text-[11px] text-[#78716C] hidden sm:inline">
                    {doc.num_pages} {doc.num_pages === 1 ? 'page' : 'pages'}
                  </span>
                )}
                <span className="text-[11px] text-[#78716C] hidden md:inline">
                  {sizeMb} MB
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1.5 shrink-0">
            <a
              href={fileUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#EAE3D4] transition-colors flex items-center gap-1 text-xs cursor-pointer"
              title="Open in new window"
            >
              <ExternalLink size={14} />
              <span className="hidden sm:inline">New Tab</span>
            </a>
            <a
              href={fileUrl}
              download={doc.filename}
              className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#EAE3D4] transition-colors flex items-center gap-1 text-xs cursor-pointer"
              title="Download file"
            >
              <Download size={14} />
              <span className="hidden sm:inline">Download</span>
            </a>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-[#78716C] hover:text-[#1C1917] hover:bg-[#EAE3D4] transition-colors cursor-pointer"
              title="Close viewer (Esc)"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Fullscreen PDF Frame */}
        <div className="flex-1 w-full bg-[#525659] overflow-hidden relative">
          <iframe
            src={`${fileUrl}#view=FitH&toolbar=1`}
            title={doc.filename}
            className="w-full h-full border-0"
          />
        </div>
      </div>
    </div>
  );
}
