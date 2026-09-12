import React, { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  ColumnDef,
  SortingState,
  flexRender,
} from "@tanstack/react-table";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpDown,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileText,
  Gavel,
  MessageSquareText,
  Search,
  ShieldAlert,
  UserCheck,
  XCircle,
  Clock3,
  Filter,
} from "lucide-react";
import { SEEDED_DEMO_VERIFICATIONS } from "../data/demoCases";
import { SeverityBadge } from "../components/status/StatusBadges";

interface ReviewRow {
  review_id: string;
  bid_id: string;
  tender_id: string;
  verification_id: string;
  category: string;
  severity: string;
  reason: string;
  evidence_references: any[];
  source_documents: string[];
  source_pages: number[];
  created_at: string;
  status: string;
}

type Decision = "CONFIRM" | "DISMISS" | "CLARIFICATION";
type QueueFilter = "ALL" | "OPEN" | "DECIDED";

const decisionMeta: Record<Decision, { label: string; description: string }> = {
  CONFIRM: { label: "Confirm discrepancy", description: "Keep the escalation active as a substantiated finding." },
  DISMISS: { label: "Dismiss finding", description: "Record that the officer does not consider the finding actionable." },
  CLARIFICATION: { label: "Request clarification", description: "Send the bidder back for additional supporting evidence." },
};

export const ReviewQueuePage: React.FC = () => {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [queueFilter, setQueueFilter] = useState<QueueFilter>("ALL");
  const [selectedReview, setSelectedReview] = useState<ReviewRow | null>(null);
  const [selectedDecision, setSelectedDecision] = useState<Decision | null>(null);
  const [officerNote, setOfficerNote] = useState("");
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  const rawItems: ReviewRow[] = useMemo(() => SEEDED_DEMO_VERIFICATIONS.flatMap((v) =>
    v.human_review_items.map((item) => ({
      ...item,
      bid_id: v.bid_id,
      tender_id: v.tender_id,
      verification_id: v.verification_id,
      evidence_references: item.evidence_references || [],
      source_documents: item.source_documents.length > 0 ? item.source_documents : [`${v.bid_id}.pdf`],
    })),
  ), []);

  const filteredData = useMemo(() => rawItems.filter((r) => {
    const categoryMatch = categoryFilter === "ALL" || r.category === categoryFilter;
    const queueMatch = queueFilter === "ALL" || (queueFilter === "OPEN" ? !decisions[r.review_id] : !!decisions[r.review_id]);
    return categoryMatch && queueMatch;
  }), [rawItems, categoryFilter, queueFilter, decisions]);

  const openCount = rawItems.filter((r) => !decisions[r.review_id]).length;
  const decidedCount = rawItems.length - openCount;
  const confirmedCount = Object.values(decisions).filter((d) => d === "CONFIRM").length;
  const clarificationCount = Object.values(decisions).filter((d) => d === "CLARIFICATION").length;

  const openAdjudication = (review: ReviewRow) => {
    setSelectedReview(review);
    setSelectedDecision(decisions[review.review_id] || null);
    setOfficerNote("");
    setSavedMessage(null);
  };

  const recordDecision = () => {
    if (!selectedReview || !selectedDecision) return;
    setDecisions((prev) => ({ ...prev, [selectedReview.review_id]: selectedDecision }));
    setSavedMessage(`${decisionMeta[selectedDecision].label} recorded for ${selectedReview.review_id}.`);
    setOfficerNote("");
  };

  const columns = useMemo<ColumnDef<ReviewRow>[]>(() => [
    {
      accessorKey: "review_id",
      header: ({ column }) => (
        <button type="button" onClick={() => column.toggleSorting(column.getIsSorted() === "asc")} className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase text-slate-700 hover:text-slate-900">
          Review ID / Bid <ArrowUpDown className="h-3 w-3 text-slate-400" />
        </button>
      ),
      cell: ({ row }) => {
        const decision = decisions[row.original.review_id];
        return <div>
          <span className="block font-mono text-xs font-bold text-slate-900">{row.original.review_id}</span>
          <span className="block font-mono text-[11px] text-blue-600">{row.original.bid_id}</span>
          {decision && <span className="mt-1 inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[9px] font-bold uppercase text-emerald-700"><CheckCircle2 className="h-3 w-3" />{decisionMeta[decision].label}</span>}
        </div>;
      },
    },
    {
      accessorKey: "category",
      header: () => <span className="text-[11px] uppercase text-slate-600">Category</span>,
      cell: ({ row }) => <span className="rounded border border-slate-200 bg-slate-100 px-2 py-0.5 font-mono text-[10px] font-bold text-slate-700">{row.original.category.replace(/_/g, " ")}</span>,
    },
    { accessorKey: "severity", header: () => <span className="text-[11px] uppercase text-slate-600">Severity</span>, cell: ({ row }) => <SeverityBadge severity={row.original.severity} /> },
    {
      accessorKey: "reason",
      header: () => <span className="text-[11px] uppercase text-slate-600">Escalation Trigger</span>,
      cell: ({ row }) => <p className="max-w-sm text-xs leading-snug text-slate-700">{row.original.reason}</p>,
    },
    {
      accessorKey: "source_documents",
      header: () => <span className="text-[11px] uppercase text-slate-600">Evidence</span>,
      cell: ({ row }) => <div className="flex items-center gap-1 text-[11px] font-mono text-slate-500"><FileText className="h-3 w-3 shrink-0 text-slate-400" /><span className="max-w-[150px] truncate">{row.original.source_documents.join(", ")}</span><span className="text-slate-300">·</span><span>p.{row.original.source_pages.join(", ")}</span></div>,
    },
    {
      id: "action",
      header: () => <span className="block text-right text-[11px] uppercase text-slate-600">Adjudication</span>,
      cell: ({ row }) => {
        const decided = !!decisions[row.original.review_id];
        return <div className="flex items-center justify-end gap-1.5">
          <button type="button" onClick={() => openAdjudication(row.original)} className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-semibold shadow-sm transition-colors ${decided ? "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50" : "bg-slate-950 text-white hover:bg-slate-800"}`}>
            {decided ? <CheckCircle2 className="h-3 w-3" /> : <Gavel className="h-3 w-3" />} {decided ? "View decision" : "Decide"}
          </button>
          <Link to={`/verification/${row.original.verification_id}`} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 transition-colors hover:border-slate-300 hover:text-slate-950">Investigate <ArrowRight className="h-3 w-3" /></Link>
        </div>;
      },
    },
  ], [decisions]);

  const table = useReactTable({ data: filteredData, columns, state: { sorting, globalFilter }, onSortingChange: setSorting, onGlobalFilterChange: setGlobalFilter, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel(), getFilteredRowModel: getFilteredRowModel(), getPaginationRowModel: getPaginationRowModel() });

  return (
    <div className="space-y-5 font-sans">
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-bold tracking-tight text-slate-900">Officer Review & Adjudication Queue</h1><span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-800">{openCount} OPEN</span></div>
          <p className="mt-1 text-xs text-slate-500">Human-in-the-loop decision center for ambiguous claims, integrity discrepancies, and evidence gaps.</p>
        </div>
        <div className="grid grid-cols-3 gap-1.5 text-[10px] font-mono font-bold uppercase tracking-wider">
          <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-center shadow-sm"><span className="block text-slate-400">Open</span><span className="text-sm text-slate-900">{openCount}</span></div>
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-center text-emerald-700 shadow-sm"><span className="block text-emerald-500">Confirmed</span><span className="text-sm">{confirmedCount}</span></div>
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-center text-blue-700 shadow-sm"><span className="block text-blue-500">Clarification</span><span className="text-sm">{clarificationCount}</span></div>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-[1.35fr_1fr]">
        <div className="flex items-start gap-3 rounded-xl border border-blue-200 bg-blue-50/70 px-4 py-3"><UserCheck className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" /><div><p className="text-xs font-bold text-blue-950">Officer decision remains authoritative</p><p className="mt-0.5 text-[11px] leading-5 text-blue-800">Automated checks surface evidence and route exceptions. The final adjudication is explicitly recorded by a human officer.</p></div></div>
        <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm"><Clock3 className="h-4 w-4 shrink-0 text-slate-500" /><div><p className="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500">Queue state</p><p className="mt-0.5 text-xs font-semibold text-slate-800">{decidedCount} of {rawItems.length} escalations adjudicated in this session</p></div></div>
      </div>

      <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-slate-50 p-3">
          <div className="relative min-w-[240px] flex-1 sm:max-w-md"><Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" /><input type="text" value={globalFilter} onChange={(e) => setGlobalFilter(e.target.value)} placeholder="Search review ID, bid, or escalation trigger..." className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-8 pr-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500" /></div>
          <div className="flex items-center gap-1.5"><Filter className="h-3.5 w-3.5 text-slate-400" />{(["ALL", "OPEN", "DECIDED"] as QueueFilter[]).map((filter) => <button key={filter} type="button" onClick={() => setQueueFilter(filter)} className={`rounded-lg px-2.5 py-2 text-[10px] font-bold uppercase tracking-wide transition-colors ${queueFilter === filter ? "bg-slate-900 text-white" : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"}`}>{filter}</button>)}</div>
          <div className="flex flex-wrap items-center gap-1.5">{["ALL", "AMBIGUOUS_COMPLIANCE", "INTEGRITY_CONTRADICTION"].map((cat) => <button key={cat} type="button" onClick={() => setCategoryFilter(cat)} className={`rounded-lg px-2.5 py-2 text-[10px] font-bold uppercase tracking-wide transition-colors ${categoryFilter === cat ? "bg-slate-900 text-white shadow-sm" : "border border-slate-200 bg-white text-slate-600 hover:bg-slate-100"}`}>{cat === "ALL" ? "All categories" : cat.replace(/_/g, " ")}</button>)}</div>
        </div>

        <div className="overflow-x-auto"><table className="w-full min-w-[1000px] text-left text-xs"><thead className="border-b border-slate-200 bg-slate-100/80 text-slate-700"><tr>{table.getHeaderGroups()[0].headers.map((header) => <th key={header.id} className="px-4 py-3">{header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}</th>)}</tr></thead><tbody className="divide-y divide-slate-100 text-slate-800">{table.getRowModel().rows.map((row) => <tr key={row.id} className={`transition-colors hover:bg-slate-50/70 ${decisions[row.original.review_id] ? "bg-slate-50/40" : ""}`}>{row.getVisibleCells().map((cell) => <td key={cell.id} className="px-4 py-3.5 align-top">{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}</tr>)}{table.getRowModel().rows.length === 0 && <tr><td colSpan={6} className="px-6 py-12 text-center"><CheckCircle2 className="mx-auto h-7 w-7 text-emerald-500" /><p className="mt-2 text-sm font-bold text-slate-800">No matching escalations</p><p className="mt-1 text-xs text-slate-500">Adjust the search or queue/category filter.</p></td></tr>}</tbody></table></div>

        <div className="flex h-11 items-center justify-between border-t border-slate-200 bg-slate-50 px-4 text-xs text-slate-500"><span className="font-mono text-[10px]">Showing {table.getRowModel().rows.length} of {filteredData.length} matching escalations</span><div className="flex items-center gap-1.5 font-mono text-xs"><button type="button" disabled={!table.getCanPreviousPage()} onClick={() => table.previousPage()} className="rounded p-1 text-slate-600 hover:bg-slate-200 disabled:opacity-30"><ChevronLeft className="h-4 w-4" /></button><span>{table.getState().pagination.pageIndex + 1} / {table.getPageCount() || 1}</span><button type="button" disabled={!table.getCanNextPage()} onClick={() => table.nextPage()} className="rounded p-1 text-slate-600 hover:bg-slate-200 disabled:opacity-30"><ChevronRight className="h-4 w-4" /></button></div></div>
      </div>

      {selectedReview && <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/45 p-0 backdrop-blur-[2px] sm:items-center sm:p-6"><div className="flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-t-2xl border border-slate-200 bg-white shadow-2xl sm:rounded-2xl">
        <div className="flex items-start justify-between border-b border-slate-200 bg-slate-950 px-5 py-4 text-white"><div><div className="flex flex-wrap items-center gap-2"><span className="font-mono text-[10px] font-bold uppercase tracking-wider text-slate-400">Officer adjudication</span><SeverityBadge severity={selectedReview.severity} /></div><h2 className="mt-1 text-base font-bold">{selectedReview.review_id}</h2><p className="mt-0.5 text-[11px] text-slate-400">{selectedReview.bid_id} · {selectedReview.category.replace(/_/g, " ")}</p></div><button type="button" onClick={() => setSelectedReview(null)} className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/10 hover:text-white" aria-label="Close adjudication"><XCircle className="h-5 w-5" /></button></div>
        <div className="flex-1 overflow-y-auto p-5"><div className="grid gap-4 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="space-y-4"><section className="rounded-xl border border-rose-200 bg-rose-50/70 p-4"><div className="flex items-center gap-2 text-rose-700"><ShieldAlert className="h-4 w-4" /><span className="text-[10px] font-bold uppercase tracking-[0.16em]">Escalation trigger</span></div><p className="mt-2 text-sm font-semibold leading-6 text-slate-900">{selectedReview.reason}</p></section>
          <section><div className="mb-2 flex items-center justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Evidence basis</p><p className="mt-0.5 text-xs text-slate-500">Source material already surfaced by the verification engine.</p></div><FileText className="h-4 w-4 text-slate-400" /></div><div className="space-y-2">{selectedReview.evidence_references.map((evidence, index) => <div key={`${evidence.document}-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 p-3"><div className="flex items-center justify-between gap-3"><span className="font-mono text-[10px] font-bold text-slate-700">Evidence {String.fromCharCode(65 + index)}</span><span className="text-[10px] font-mono text-slate-400">{evidence.document} · Page {evidence.page}</span></div><p className="mt-2 font-mono text-[11px] leading-5 text-slate-700">“{evidence.snippet}”</p></div>)}</div></section></div>
          <div className="space-y-4"><section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center gap-2"><Gavel className="h-4 w-4 text-slate-600" /><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Decision</p><p className="text-xs font-semibold text-slate-800">What should happen to this escalation?</p></div></div><div className="mt-4 space-y-2">{(Object.keys(decisionMeta) as Decision[]).map((decision) => { const active = selectedDecision === decision; return <button key={decision} type="button" onClick={() => setSelectedDecision(decision)} className={`w-full rounded-lg border p-3 text-left transition-all ${active ? "border-slate-900 bg-slate-950 text-white shadow-sm" : "border-slate-200 bg-white text-slate-800 hover:border-slate-300 hover:bg-slate-50"}`}><div className="flex items-start gap-3"><span className={`mt-0.5 h-3.5 w-3.5 rounded-full border-2 ${active ? "border-white bg-white ring-2 ring-slate-500" : "border-slate-300"}`} /><span><span className="block text-xs font-bold">{decisionMeta[decision].label}</span><span className={`mt-0.5 block text-[10px] leading-4 ${active ? "text-slate-300" : "text-slate-500"}`}>{decisionMeta[decision].description}</span></span></div></button>; })}</div></section>
          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center gap-2"><MessageSquareText className="h-4 w-4 text-slate-600" /><div><p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">Officer note</p><p className="text-xs font-semibold text-slate-800">Optional audit trail comment</p></div></div><textarea value={officerNote} onChange={(e) => setOfficerNote(e.target.value)} rows={5} placeholder="Record the reasoning or clarification requested..." className="mt-3 w-full resize-none rounded-lg border border-slate-300 bg-slate-50 p-3 text-xs text-slate-800 placeholder:text-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500" /></section></div>
        </div>{savedMessage && <div className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs text-emerald-800"><CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" /><span className="font-semibold">{savedMessage}</span><span className="text-emerald-600">Officer decision recorded for this session.</span></div>}</div>
        <div className="flex flex-col-reverse gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3 sm:flex-row sm:items-center sm:justify-between"><Link to={`/verification/${selectedReview.verification_id}`} className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-100"><AlertTriangle className="h-3.5 w-3.5" />Re-open evidence</Link><div className="flex gap-2"><button type="button" onClick={() => setSelectedReview(null)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100">Cancel</button><button type="button" disabled={!selectedDecision} onClick={recordDecision} className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-slate-950 px-4 py-2 text-xs font-bold text-white shadow-sm transition-colors hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"><CheckCircle2 className="h-3.5 w-3.5" />Record Decision</button></div></div>
      </div></div>}
    </div>
  );
};
