import React, { useState, useMemo } from "react";
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
  ListTodo,
  Search,
  Filter,
  ArrowUpDown,
  ArrowRight,
  ShieldAlert,
  UserCheck,
  ChevronLeft,
  ChevronRight,
  FileText,
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
  source_documents: string[];
  created_at: string;
  status: string;
}

export const ReviewQueuePage: React.FC = () => {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("ALL");
  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});

  // Flatten review items from all demo verifications
  const rawItems: ReviewRow[] = useMemo(() => {
    return SEEDED_DEMO_VERIFICATIONS.flatMap((v) =>
      v.human_review_items.map((item) => ({
        ...item,
        bid_id: v.bid_id,
        tender_id: v.tender_id,
        verification_id: v.verification_id,
        source_documents: item.source_documents.length > 0 ? item.source_documents : [`${v.bid_id}.pdf`],
      }))
    );
  }, []);

  const filteredData = useMemo(() => {
    if (categoryFilter === "ALL") return rawItems;
    return rawItems.filter((r) => r.category === categoryFilter);
  }, [rawItems, categoryFilter]);

  const columns = useMemo<ColumnDef<ReviewRow>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <input
            type="checkbox"
            checked={table.getIsAllPageRowsSelected()}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5 cursor-pointer"
            aria-label="Select all rows"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.getIsSelected()}
            disabled={!row.getCanSelect()}
            onChange={row.getToggleSelectedHandler()}
            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5 cursor-pointer"
            aria-label={`Select ${row.original.review_id}`}
          />
        ),
        enableSorting: false,
      },
      {
        accessorKey: "review_id",
        header: ({ column }) => (
          <button
            type="button"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
            className="inline-flex items-center gap-1 font-semibold text-slate-700 hover:text-slate-900 uppercase text-[11px]"
          >
            Review ID / Bid
            <ArrowUpDown className="w-3 h-3 text-slate-400" />
          </button>
        ),
        cell: ({ row }) => (
          <div>
            <span className="font-mono text-xs font-bold text-slate-900 block">{row.original.review_id}</span>
            <span className="font-mono text-[11px] text-blue-600 block">{row.original.bid_id}</span>
          </div>
        ),
      },
      {
        accessorKey: "category",
        header: () => <span className="uppercase text-[11px] text-slate-600">Category</span>,
        cell: ({ row }) => (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-slate-100 text-slate-700 border border-slate-200">
            {row.original.category}
          </span>
        ),
      },
      {
        accessorKey: "severity",
        header: () => <span className="uppercase text-[11px] text-slate-600">Severity</span>,
        cell: ({ row }) => <SeverityBadge severity={row.original.severity} />,
      },
      {
        accessorKey: "reason",
        header: () => <span className="uppercase text-[11px] text-slate-600">Escalation Trigger</span>,
        cell: ({ row }) => (
          <p className="text-xs text-slate-700 max-w-sm leading-snug">
            {row.original.reason}
          </p>
        ),
      },
      {
        accessorKey: "source_documents",
        header: () => <span className="uppercase text-[11px] text-slate-600">Evidence Source</span>,
        cell: ({ row }) => (
          <div className="flex items-center gap-1 text-[11px] font-mono text-slate-500">
            <FileText className="w-3 h-3 text-slate-400 shrink-0" />
            <span className="truncate max-w-[120px]">{row.original.source_documents.join(", ")}</span>
          </div>
        ),
      },
      {
        id: "action",
        header: () => <span className="uppercase text-[11px] text-slate-600 text-right block">Adjudication</span>,
        cell: ({ row }) => (
          <div className="flex items-center justify-end gap-1.5">
            <Link
              to={`/verification/${row.original.verification_id}`}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-slate-900 hover:bg-slate-800 text-white rounded text-xs font-semibold shadow-2xs transition-colors"
            >
              <span>Investigate</span>
              <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        ),
      },
    ],
    []
  );

  const table = useReactTable({
    data: filteredData,
    columns,
    state: {
      sorting,
      globalFilter,
      rowSelection,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onRowSelectionChange: setRowSelection,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const selectedCount = Object.keys(rowSelection).filter((k) => rowSelection[k]).length;

  return (
    <div className="space-y-4 font-sans select-none">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-3 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Officer Review & Adjudication Queue
            </h1>
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-amber-100 text-amber-800">
              {rawItems.length} Open Escalations
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Human-in-the-loop decision center: review ambiguous declarations, unverified exemptions, and cross-document discrepancies.
          </p>
        </div>
      </div>

      {/* TanStack Table Card */}
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm flex flex-col">
        {/* Table Control Bar */}
        <div className="p-3 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
          {/* Search */}
          <div className="relative min-w-[220px]">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={globalFilter ?? ""}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder="Search by review ID, bid, or trigger..."
              className="w-full pl-8 pr-3 py-1.5 bg-white border border-slate-300 rounded text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>

          {/* Category Filter Buttons */}
          <div className="flex items-center gap-1.5">
            {["ALL", "AMBIGUOUS_COMPLIANCE", "INTEGRITY_CONTRADICTION"].map((cat) => (
              <button
                key={cat}
                type="button"
                onClick={() => setCategoryFilter(cat)}
                className={`px-3 py-1 rounded text-xs font-semibold transition-colors ${
                  categoryFilter === cat
                    ? "bg-slate-900 text-white shadow-2xs"
                    : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
                }`}
              >
                {cat.replace("_", " ")}
              </button>
            ))}
          </div>

          {/* Bulk Action Controls */}
          {selectedCount > 0 && (
            <div className="flex items-center gap-2 bg-blue-50 px-3 py-1 rounded border border-blue-200 text-xs text-blue-900">
              <span className="font-bold">{selectedCount} items selected</span>
              <button
                type="button"
                onClick={() => alert(`Officer bulk action executed on ${selectedCount} items.`)}
                className="px-2 py-0.5 rounded bg-blue-600 hover:bg-blue-700 text-white font-semibold text-[11px]"
              >
                Approve Selected
              </button>
            </div>
          )}
        </div>

        {/* Table Content */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-100/80 text-slate-700 font-semibold border-b border-slate-200 uppercase text-[11px]">
              {table.getHeaderGroups().map((headerGroup) => (
                <tr key={headerGroup.id}>
                  {headerGroup.headers.map((header) => (
                    <th key={header.id} className="px-4 py-2.5">
                      {header.isPlaceholder
                        ? null
                        : flexRender(header.column.columnDef.header, header.getContext())}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-800">
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50/70 transition-colors">
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Table Footer */}
        <div className="h-10 px-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500 select-none">
          <span className="font-mono text-[11px]">
            Showing {table.getRowModel().rows.length} of {rawItems.length} Escalations
          </span>

          <div className="flex items-center gap-1.5 font-mono text-xs">
            <button
              type="button"
              disabled={!table.getCanPreviousPage()}
              onClick={() => table.previousPage()}
              className="p-1 rounded hover:bg-slate-200 disabled:opacity-30 text-slate-600"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span>
              {table.getState().pagination.pageIndex + 1} / {table.getPageCount() || 1}
            </span>
            <button
              type="button"
              disabled={!table.getCanNextPage()}
              onClick={() => table.nextPage()}
              className="p-1 rounded hover:bg-slate-200 disabled:opacity-30 text-slate-600"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
