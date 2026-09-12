import React, { useState, useEffect } from "react";
import {
  ZoomIn,
  ZoomOut,
  Maximize2,
  ChevronLeft,
  ChevronRight,
  FileText,
  Scan,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { PhysicalTextBlock } from "../../data/demoCases";
import { EvidenceData } from "./EvidenceInspector";

interface DocumentCanvasProps {
  documentName: string;
  bidId: string;
  textBlocks: PhysicalTextBlock[];
  selectedClauseId: string | null;
  selectedBlockId?: string | null;
  onSelectClause: (clauseId: string) => void;
  onSelectBlock?: (blockId: string) => void;
  onHoverEvidence: (evidence: EvidenceData | null, pos?: { x: number; y: number }) => void;
}

export const DocumentCanvas: React.FC<DocumentCanvasProps> = ({
  documentName,
  bidId,
  textBlocks,
  selectedClauseId,
  selectedBlockId,
  onSelectClause,
  onSelectBlock,
  onHoverEvidence,
}) => {
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [zoomLevel, setZoomLevel] = useState<number>(95);

  const totalPages = Math.max(1, ...textBlocks.map((b) => b.page));

  // Automatically switch page when active clause or evidence block changes
  useEffect(() => {
    if (textBlocks.length > 0) {
      const match = selectedBlockId
        ? textBlocks.find((b) => b.id === selectedBlockId)
        : selectedClauseId
        ? textBlocks.find((b) => {
            const cid = b.clause_id || (b as any).matched_clause_id;
            return cid === selectedClauseId || (cid && selectedClauseId.includes(cid));
          })
        : undefined;

      if (match?.page) {
        setCurrentPage(match.page);
      }
    }
  }, [selectedClauseId, selectedBlockId, textBlocks]);

  const pageBlocks = textBlocks.filter((b) => b.page === currentPage);

  const handleZoom = (delta: number) => {
    setZoomLevel((prev) => Math.min(150, Math.max(75, prev + delta)));
  };

  return (
    <div className="flex flex-col h-full bg-slate-950 border border-slate-800 rounded-lg overflow-hidden shadow-lg select-none">
      {/* 1. Header Toolbar */}
      <div className="h-10 px-3.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-blue-400 shrink-0" />
          <span className="text-xs font-mono font-bold text-slate-200 truncate max-w-[170px]">
            {documentName}
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
            {bidId}
          </span>
        </div>

        {/* Page Stepper */}
        <div className="flex items-center gap-2 text-xs font-mono text-slate-300">
          <button
            type="button"
            disabled={currentPage <= 1}
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            className="p-1 rounded hover:bg-slate-800 disabled:opacity-30 text-slate-300 transition-colors"
            title="Previous Page"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="font-semibold text-slate-200 px-1 bg-slate-950/80 rounded py-0.5 border border-slate-800">
            PAGE {currentPage} OF {totalPages}
          </span>
          <button
            type="button"
            disabled={currentPage >= totalPages}
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            className="p-1 rounded hover:bg-slate-800 disabled:opacity-30 text-slate-300 transition-colors"
            title="Next Page"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1.5 text-slate-300 text-xs font-mono">
          <button
            type="button"
            onClick={() => handleZoom(-10)}
            className="p-1 rounded hover:bg-slate-800"
            title="Zoom Out"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px] text-slate-400 w-9 text-center">{zoomLevel}%</span>
          <button
            type="button"
            onClick={() => handleZoom(10)}
            className="p-1 rounded hover:bg-slate-800"
            title="Zoom In"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setZoomLevel(95)}
            className="p-1 rounded hover:bg-slate-800 ml-1 text-slate-400 hover:text-slate-200"
            title="Fit Page"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* 2. Simulated PDF Canvas Scroll Viewport */}
      <div className="flex-1 overflow-y-auto p-4 bg-slate-950 flex justify-center items-start">
        <div
          style={{
            transform: `scale(${zoomLevel / 100})`,
            transformOrigin: "top center",
            transition: "transform 0.15s ease-out",
            width: "560px",
            minHeight: "792px",
          }}
          className="bg-white rounded shadow-2xl relative p-8 border border-slate-300 text-slate-900 select-text"
        >
          {/* Document Simulated Header */}
          <div className="border-b-2 border-slate-900 pb-2.5 mb-5 flex items-start justify-between">
            <div>
              <h2 className="text-xs font-bold tracking-tight text-slate-900 uppercase">
                GOVERNMENT E-MARKETPLACE (GeM) · BID SUBMISSION
              </h2>
              <p className="text-[10px] font-mono text-slate-500 mt-0.5">
                File: {documentName} · Bidder Identifier: {bidId}
              </p>
            </div>
            <div className="text-right font-mono text-[10px] text-slate-500">
              <span className="font-bold">PAGE {currentPage}</span> / {totalPages}
            </div>
          </div>

          {/* Physical Text Blocks */}
          <div className="space-y-3.5">
            {pageBlocks.length === 0 ? (
              <div className="p-8 text-center text-slate-400 font-mono text-xs">
                No segmented text blocks on this page.
              </div>
            ) : (
              pageBlocks.map((block) => {
                const blockClauseId = block.clause_id || (block as any).matched_clause_id;
                const isSelected = selectedBlockId === block.id || (!selectedBlockId && selectedClauseId && blockClauseId === selectedClauseId);

                return (
                  <div
                    key={block.id}
                    onClick={() => {
                      if (blockClauseId) {
                        onSelectClause(blockClauseId);
                      } else if (onSelectBlock) {
                        onSelectBlock(block.id);
                      }
                    }}
                    onMouseEnter={(e) => {
                      const rect = e.currentTarget.getBoundingClientRect();
                      onHoverEvidence(
                        {
                          document: documentName,
                          page: block.page,
                          block_id: block.id,
                          bbox: block.bbox,
                          snippet: block.text,
                          requirement_id: block.clause_id,
                          grounding_state: block.grounding_state,
                          confidence_heuristic: block.confidence_heuristic,
                        },
                        { x: rect.right, y: rect.top }
                      );
                    }}
                    onMouseLeave={() => onHoverEvidence(null)}
                    className={`relative p-3 rounded transition-all cursor-pointer ${
                      isSelected
                        ? "bg-amber-50/90 ring-2 ring-amber-500 shadow-lg border border-amber-400"
                        : block.clause_id
                        ? "hover:bg-blue-50/60 border border-dashed border-blue-300 hover:border-blue-500"
                        : "border border-transparent hover:border-slate-200"
                    }`}
                  >
                    {/* Bounding Box Coordinate Tag */}
                    {block.clause_id && (
                      <div className="flex items-center justify-between pb-1 mb-1.5 border-b border-slate-200/80 text-[10px] font-mono select-none">
                        <div className="flex items-center gap-1.5">
                          <Scan className={`w-3.5 h-3.5 ${isSelected ? "text-amber-700" : "text-blue-600"}`} />
                          <span className={`font-bold ${isSelected ? "text-amber-900" : "text-slate-800"}`}>
                            {block.clause_id}
                          </span>
                          <span className="text-slate-500">({block.id})</span>
                        </div>
                        <span className="text-[9px] text-slate-500 font-mono">
                          [{block.bbox.map((n) => Math.round(n)).join(", ")}]
                        </span>
                      </div>
                    )}

                    {/* Verbatim Content */}
                    <p className="font-mono text-[11px] text-slate-800 leading-relaxed whitespace-pre-line">
                      {block.text}
                    </p>

                    {/* Active Golden Left Focus Ribbon */}
                    {isSelected && (
                      <div className="absolute -left-1.5 top-1.5 bottom-1.5 w-1.5 bg-amber-500 rounded-l" />
                    )}
                  </div>
                );
              })
            )}
          </div>

          {/* Page Footer */}
          <div className="absolute bottom-3 left-8 right-8 pt-2 border-t border-slate-200 flex items-center justify-between text-[9px] font-mono text-slate-400">
            <span>Physical Document Evidence Grounding · PyMuPDF Ingestion</span>
            <span>Page {currentPage} of {totalPages}</span>
          </div>
        </div>
      </div>
    </div>
  );
};