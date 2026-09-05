import React, { useState, useMemo } from "react";
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
  ArrowUpDown,
  Search,
  Scan,
  ChevronLeft,
  ChevronRight,
  HelpCircle,
} from "lucide-react";
import { VerificationResult } from "../../types";
import { ComplianceBadge, SeverityBadge } from "../status/StatusBadges";

interface RequirementMatrixTableProps {
  data: VerificationResult[];
  selectedClauseId: string | null;
  onSelectClause: (clauseId: string) => void;
  onTriggerEvidence: (item: VerificationResult, pos?: { x: number; y: number }) => void;
}

export const RequirementMatrixTable: React.FC<RequirementMatrixTableProps> = ({
  data,
  selectedClauseId,
  onSelectClause,
  onTriggerEvidence,
}) => {
  const [sorting, setSorting] = useState<SortingState>([]);
  const [globalFilter, setGlobalFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("ALL");
  const [rowSelection, setRowSelection] = useState<Record<string, boolean>>({});

  const filteredData = useMemo(() => {
    if (statusFilter === "ALL") return data;
    return data.filter((item) => item.status === statusFilter);
  }, [data, statusFilter]);

  const columns = useMemo<ColumnDef<VerificationResult>[]>(
    () => [
      {
        id: "select",
        header: ({ table }) => (
          <input
            type="checkbox"
            checked={table.getIsAllPageRowsSelected()}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5 cursor-pointer"
            aria-label="Select all"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            checked={row.getIsSelected()}
            disabled={!row.getCanSelect()}
            onChange={row.getToggleSelectedHandler()}
            onClick={(e) => e.stopPropagation()}
            className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 w-3.5 h-3.5 cursor-pointer"
            aria-label={`Select ${row.original.requirement_id}`}
          />
        ),
        enableSorting: false,
      },
      {
        accessorKey: "requirement_id",
        header: ({ column }) => (
          <button
            type="button"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
            className="inline-flex items-center gap-1 font-bold text-slate-700 hover:text-slate-900 uppercase text-[10px]"
          >
            Clause
            <ArrowUpDown className="w-3 h-3 text-slate-400" />
          </button>
        ),
        cell: ({ row }) => {
          const item = row.original;
          const isSelected = selectedClauseId === item.requirement_id;
          const shortCode = item.requirement_id.split("/").pop() || item.requirement_id;
          return (
            <div className="flex items-center gap-1.5">
              <span
                className={`font-mono text-[11px] font-bold px-1.5 py-0.5 rounded transition-colors ${
                  isSelected
                    ? "bg-amber-500 text-slate-950 font-extrabold"
                    : "bg-slate-100 text-slate-800 border border-slate-200"
                }`}
              >
                {shortCode}
              </span>
            </div>
          );
        },
      },
      {
        accessorKey: "expected",
        header: () => <span className="uppercase text-[10px] font-bold text-slate-600">Rule Threshold</span>,
        cell: ({ row }) => (
          <span className="font-mono text-xs text-slate-700 tabular-nums">
            {String(row.original.expected)}
          </span>
        ),
      },
      {
        accessorKey: "actual",
        header: () => <span className="uppercase text-[10px] font-bold text-slate-600">Extracted Fact</span>,
        cell: ({ row }) => (
          <span className="font-mono text-xs font-bold text-slate-900 tabular-nums">
            {row.original.actual}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: ({ column }) => (
          <button
            type="button"
            onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
            className="inline-flex items-center gap-1 font-bold text-slate-700 hover:text-slate-900 uppercase text-[10px]"
          >
            Compliance
            <ArrowUpDown className="w-3 h-3 text-slate-400" />
          </button>
        ),
        cell: ({ row }) => <ComplianceBadge status={row.original.status} size="sm" />,
      },
      {
        id: "evidence_action",
        header: () => <span className="uppercase text-[10px] font-bold text-slate-600">Evidence BBox</span>,
        cell: ({ row }) => {
          const item = row.original;
          const ev = item.evidence[0];
          const isSelected = selectedClauseId === item.requirement_id;

          return (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSelectClause(item.requirement_id);
                const rect = e.currentTarget.getBoundingClientRect();
                onTriggerEvidence(item, { x: rect.left, y: rect.bottom });
              }}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono font-bold transition-all ${
                isSelected
                  ? "bg-amber-500 text-slate-950 shadow-xs"
                  : "bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100"
              }`}
            >
              <Scan className="w-3 h-3" />
              <span>{ev ? `P.${ev.page}` : "Inspect"}</span>
            </button>
          );
        },
      },
      {
        accessorKey: "reason",
        header: () => <span className="uppercase text-[10px] font-bold text-slate-600">Deterministic Reason</span>,
        cell: ({ row }) => (
          <p className="text-[11px] text-slate-600 leading-snug truncate max-w-[220px]" title={row.original.reason}>
            {row.original.reason}
          </p>
        ),
      },
    ],
    [selectedClauseId, onSelectClause, onTriggerEvidence]
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
    initialState: {
      pagination: {
        pageSize: 8,
      },
    },
  });

  const selectedCount = Object.keys(rowSelection).filter((k) => rowSelection[k]).length;

  return (
    <div className="flex flex-col h-full bg-white border border-slate-200 rounded-lg overflow-hidden shadow-sm">
      {/* 1. Matrix Filter Bar */}
      <div className="p-2.5 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-2 shrink-0 select-none">
        <div className="relative flex-1 min-w-[160px] max-w-xs">
          <Search className="w-3 h-3 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={globalFilter ?? ""}
            onChange={(e) => setGlobalFilter(e.target.value)}
            placeholder="Search clause or fact..."
            className="w-full pl-7 pr-3 py-1 bg-white border border-slate-300 rounded text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex items-center gap-1">
          {["ALL", "FAIL", "REVIEW", "PASS"].map((st) => (
            <button
              key={st}
              type="button"
              onClick={() => setStatusFilter(st)}
              className={`px-2 py-0.5 rounded text-[10px] font-bold transition-colors ${
                statusFilter === st
                  ? "bg-slate-900 text-white shadow-2xs"
                  : "bg-white text-slate-600 hover:bg-slate-100 border border-slate-200"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {selectedCount > 0 && (
          <div className="flex items-center gap-1.5 bg-amber-50 px-2 py-0.5 rounded border border-amber-200 text-xs text-amber-900">
            <span className="font-bold text-[11px]">{selectedCount} sel</span>
            <button
              type="button"
              onClick={() => alert(`Escalated ${selectedCount} clause(s) to review.`)}
              className="px-1.5 py-0.5 rounded bg-amber-600 text-white font-bold text-[10px]"
            >
              Escalate
            </button>
          </div>
        )}
      </div>

      {/* 2. TanStack Table */}
      <div className="flex-1 overflow-auto">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-100/90 text-slate-700 font-semibold border-b border-slate-200 uppercase text-[10px] sticky top-0 z-10 backdrop-blur-xs">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="px-3 py-2">
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody className="divide-y divide-slate-100 text-slate-800">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="p-8 text-center text-slate-500 font-mono text-xs">
                  No matching requirements found.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => {
                const isSelected = selectedClauseId === row.original.requirement_id;
                return (
                  <tr
                    key={row.id}
                    onClick={() => onSelectClause(row.original.requirement_id)}
                    className={`cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-amber-50/70 font-semibold text-slate-900"
                        : "hover:bg-slate-50/70"
                    }`}
                  >
                    {row.getVisibleCells().map((cell) => (
                      <td key={cell.id} className="px-3 py-2 whitespace-nowrap">
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 3. Footer */}
      <div className="h-8 px-3 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-xs text-slate-500 shrink-0 select-none">
        <span className="font-mono text-[10px]">
          {table.getRowModel().rows.length} / {data.length} Requirements
        </span>

        <div className="flex items-center gap-1 font-mono text-xs">
          <button
            type="button"
            disabled={!table.getCanPreviousPage()}
            onClick={() => table.previousPage()}
            className="p-0.5 rounded hover:bg-slate-200 disabled:opacity-30 text-slate-600"
          >
            <ChevronLeft className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px]">
            {table.getState().pagination.pageIndex + 1} / {table.getPageCount() || 1}
          </span>
          <button
            type="button"
            disabled={!table.getCanNextPage()}
            onClick={() => table.nextPage()}
            className="p-0.5 rounded hover:bg-slate-200 disabled:opacity-30 text-slate-600"
          >
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
};
