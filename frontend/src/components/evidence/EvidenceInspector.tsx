import React from "react";
import { createPortal } from "react-dom";
import { ShieldCheck, FileText, CornerDownRight, Hash, Eye } from "lucide-react";
import { ComplianceBadge } from "../status/StatusBadges";

export interface EvidenceData {
  document: string;
  page: number;
  block_id?: string;
  bbox?: [number, number, number, number];
  snippet: string;
  grounding_state?: "VERIFIED" | "UNVERIFIED" | "REVIEW";
  confidence_heuristic?: "HIGH" | "MEDIUM" | "LOW";
  requirement_id?: string;
  expected?: string | number;
  actual?: string;
  operator_used?: string;
  status?: string;
  reason?: string;
}

interface EvidenceInspectorProps {
  evidence: EvidenceData | null;
  position?: { x: number; y: number } | null;
  onClose?: () => void;
  isPinned?: boolean;
}

export const EvidenceInspector: React.FC<EvidenceInspectorProps> = ({
  evidence,
  position,
  onClose,
  isPinned = false,
}) => {
  if (!evidence) return null;

  const style: React.CSSProperties = position
    ? {
        position: "fixed",
        top: Math.min(position.y + 12, window.innerHeight - 380),
        left: Math.min(position.x + 16, window.innerWidth - 440),
        zIndex: 9999,
      }
    : {
        position: "relative",
      };

  const card = (
    <div
      style={style}
      className="w-96 rounded-lg bg-slate-950 border border-slate-700 shadow-2xl text-slate-100 overflow-hidden font-sans select-none animate-in fade-in zoom-in-95 duration-100"
    >
      <div className="px-3.5 py-2.5 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-2 truncate">
          <FileText className="w-4 h-4 text-blue-400 shrink-0" />
          <span className="font-mono text-xs font-semibold text-slate-200 truncate">
            {evidence.document}
          </span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-blue-950 text-blue-300 border border-blue-800">
            Page {evidence.page}
          </span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            {evidence.grounding_state || "VERIFIED"}
          </span>
          {isPinned && onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-0.5 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-200 ml-1"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="px-3.5 py-1.5 bg-slate-900/60 border-b border-slate-800/80 flex items-center justify-between text-[10px] font-mono text-slate-400">
        <div className="flex items-center gap-1">
          <Hash className="w-3 h-3 text-slate-500" />
          <span>Block ID: {evidence.block_id || `BLK-P${evidence.page}-001`}</span>
        </div>
        <div>
          BBox: [{evidence.bbox ? evidence.bbox.map((n) => Math.round(n)).join(", ") : "0, 0, 0, 0"}]
        </div>
      </div>

      <div className="p-3.5 space-y-2">
        <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 flex items-center gap-1">
          <Eye className="w-3 h-3 text-blue-400" />
          <span>Verbatim Extracted TextBlock (PyMuPDF)</span>
        </div>
        <div className="p-2.5 rounded bg-slate-900 border border-slate-800/80 font-mono text-xs text-slate-200 leading-relaxed max-h-36 overflow-y-auto">
          “{evidence.snippet}”
        </div>
      </div>

      {evidence.requirement_id && (
        <div className="px-3.5 py-2.5 bg-slate-900/90 border-t border-slate-800 space-y-1.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="font-mono text-[11px] text-slate-300 font-semibold">
              {evidence.requirement_id}
            </span>
            {evidence.status && <ComplianceBadge status={evidence.status} size="sm" />}
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
            <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800/60">
              <span className="text-[10px] text-slate-400 block font-mono">Rule Threshold:</span>
              <span className="font-mono font-bold text-slate-200">{String(evidence.expected)}</span>
            </div>
            <div className="bg-slate-950/60 p-1.5 rounded border border-slate-800/60">
              <span className="text-[10px] text-slate-400 block font-mono">Extracted Fact:</span>
              <span className="font-mono font-bold text-blue-300">{evidence.actual}</span>
            </div>
          </div>

          {evidence.reason && (
            <p className="text-[10px] text-slate-400 pt-1 leading-snug flex items-start gap-1 font-mono">
              <CornerDownRight className="w-3 h-3 text-slate-500 shrink-0 mt-0.5" />
              <span>{evidence.reason}</span>
            </p>
          )}
        </div>
      )}

      <div className="px-3.5 py-1.5 bg-slate-950 border-t border-slate-900 flex items-center justify-between text-[9px] font-mono text-slate-400">
        <span>Extraction: Step 6 Physical Segmentation</span>
        <span>Decision: Step 4 Rule Engine</span>
      </div>
    </div>
  );

  return position && typeof document !== "undefined" ? createPortal(card, document.body) : card;
};
