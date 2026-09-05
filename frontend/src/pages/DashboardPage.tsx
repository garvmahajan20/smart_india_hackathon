import React from "react";
import { Link } from "react-router-dom";
import {
  FileCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  Clock,
  ExternalLink,
} from "lucide-react";
import { CANONICAL_DEMO_CASES, SEEDED_DEMO_VERIFICATIONS } from "../data/demoCases";
import { ComplianceBadge, IntegrityBadge, OverallBadge } from "../components/status/StatusBadges";

export const DashboardPage: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* 1. PAGE TITLE & BANNER */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-200/80">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-bold text-slate-900 tracking-tight">
              Procurement Verification Dashboard
            </h1>
            <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-white/80 text-slate-700 tracking-wide font-mono border border-slate-200 shadow-xs">
              Demo / Sample Data
            </span>
          </div>
          <p className="text-xs text-slate-600 font-medium mt-1">
            Evidence-first bid compliance verification and deterministic integrity review for GeM procurement
          </p>
        </div>

        <Link
          to="/verify/new"
          className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-semibold shadow-sm transition-colors shrink-0"
        >
          <FileCheck className="w-4 h-4" />
          <span>New Verification</span>
        </Link>
      </div>

      {/* 2. KPI METRICS CARDS (Demo / Sample Data) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Verifications */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Total Verifications
            </span>
            <div className="w-8 h-8 rounded bg-slate-100 flex items-center justify-center text-slate-700">
              <FileCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-bold text-slate-900 font-mono tracking-tight">4</span>
            <span className="text-[11px] text-slate-500 block mt-1">Seeded canonical test evaluations</span>
          </div>
        </div>

        {/* Compliant Bids */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-700 uppercase tracking-wider">
              Compliant Bids
            </span>
            <div className="w-8 h-8 rounded bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-200">
              <CheckCircle2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-bold text-emerald-700 font-mono tracking-tight">1</span>
            <span className="text-[11px] text-emerald-600 font-medium block mt-1">
              All mandatory tender clauses satisfied
            </span>
          </div>
        </div>

        {/* Non-Compliant Bids */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-700 uppercase tracking-wider">
              Non-Compliant
            </span>
            <div className="w-8 h-8 rounded bg-rose-50 text-rose-600 flex items-center justify-center border border-rose-200">
              <XCircle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-bold text-rose-700 font-mono tracking-tight">3</span>
            <span className="text-[11px] text-rose-600 font-medium block mt-1">
              Mandatory requirement failures identified
            </span>
          </div>
        </div>

        {/* Review Required */}
        <div className="bg-white p-5 rounded-lg border border-slate-200 shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-700 uppercase tracking-wider">
              Review Required
            </span>
            <div className="w-8 h-8 rounded bg-amber-50 text-amber-600 flex items-center justify-center border border-amber-200">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-3xl font-bold text-amber-700 font-mono tracking-tight">3</span>
            <span className="text-[11px] text-amber-600 font-medium block mt-1">
              Ambiguous claims & discrepancies flagged
            </span>
          </div>
        </div>
      </div>

      {/* 3. CANONICAL SIH DEMO PRESETS */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              Quick Demo Cases (Canonical SIH Dataset)
            </h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Select any pre-verified canonical submission to immediately inspect the multi-engine verification workbench.
            </p>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">TENDER-0069</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {CANONICAL_DEMO_CASES.map((c) => {
            const verifId = `VERIF-${c.tender_id}-${c.bid_id}`;
            return (
              <div
                key={c.bid_id}
                className="rounded-lg border border-slate-200 bg-slate-50/50 p-4 flex flex-col justify-between hover:border-slate-300 hover:bg-slate-50 transition-all"
              >
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-xs font-bold text-slate-800">{c.bid_id}</span>
                    <OverallBadge status={c.expected_overall} size="sm" />
                  </div>
                  <h4 className="text-xs font-bold text-slate-900 truncate">{c.company_name}</h4>
                  <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                    {c.description}
                  </p>

                  <ul className="mt-3 space-y-1 text-[11px] text-slate-600 border-t border-slate-200/80 pt-2.5">
                    {c.highlights.slice(0, 2).map((h, i) => (
                      <li key={i} className="flex items-start gap-1.5 truncate">
                        <span className="text-blue-500 mt-0.5">•</span>
                        <span className="truncate">{h}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <Link
                  to={`/verification/${verifId}`}
                  className="mt-4 inline-flex items-center justify-between w-full px-3 py-1.5 bg-white hover:bg-slate-100 text-slate-800 border border-slate-300 rounded text-xs font-semibold shadow-2xs transition-colors"
                >
                  <span>Inspect Dossier</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                </Link>
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. RECENT VERIFICATIONS TABLE */}
      <div className="bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-900">Recent Verification Activity</h3>
            <p className="text-xs text-slate-500">
              Audit log of completed verification pipelines and deterministic run identifiers.
            </p>
          </div>
          <span className="text-[11px] font-mono text-slate-500">4 records</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200 uppercase tracking-wider text-[11px]">
              <tr>
                <th className="px-5 py-3">Verification ID / Bidder</th>
                <th className="px-4 py-3">Tender</th>
                <th className="px-4 py-3">Overall Verdict</th>
                <th className="px-4 py-3">Compliance</th>
                <th className="px-4 py-3">Integrity</th>
                <th className="px-4 py-3">Run ID</th>
                <th className="px-5 py-3 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 text-slate-800 font-medium">
              {SEEDED_DEMO_VERIFICATIONS.map((v) => {
                const demo = CANONICAL_DEMO_CASES.find((d) => d.bid_id === v.bid_id);
                return (
                  <tr key={v.verification_id} className="hover:bg-slate-50/80 transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-slate-900">{demo?.company_name || v.bid_id}</div>
                      <div className="text-[11px] text-slate-500 font-mono">{v.verification_id}</div>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-slate-600">{v.tender_id}</td>
                    <td className="px-4 py-3.5">
                      <OverallBadge status={v.overall_status} size="sm" />
                    </td>
                    <td className="px-4 py-3.5">
                      <ComplianceBadge status={v.compliance_status} size="sm" />
                    </td>
                    <td className="px-4 py-3.5">
                      <IntegrityBadge status={v.integrity_status} size="sm" />
                    </td>
                    <td className="px-4 py-3.5 font-mono text-[11px] text-slate-500">
                      {v.deterministic_run_id}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <Link
                        to={`/verification/${v.verification_id}`}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-blue-600 hover:text-blue-800"
                      >
                        View Dossier
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
