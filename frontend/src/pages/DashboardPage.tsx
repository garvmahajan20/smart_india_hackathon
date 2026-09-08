import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock3,
  FileCheck2,
  Fingerprint,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import {
  CANONICAL_DEMO_CASES,
  SEEDED_DEMO_VERIFICATIONS,
} from "../data/demoCases";
import {
  ComplianceBadge,
  IntegrityBadge,
  OverallBadge,
} from "../components/status/StatusBadges";

const cardVariants = {
  hidden: { opacity: 0, y: 12 },
  visible: (index: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, delay: index * 0.06 },
  }),
};

const getRiskMeta = (label: string) => {
  switch (label) {
    case "MANIPULATED":
      return {
        tone: "rose",
        eyebrow: "Integrity alert",
        icon: Fingerprint,
        action: "Investigate contradiction",
      };
    case "UNCERTAIN":
      return {
        tone: "amber",
        eyebrow: "Officer review",
        icon: AlertTriangle,
        action: "Review ambiguous claims",
      };
    case "NON_COMPLIANT":
      return {
        tone: "orange",
        eyebrow: "Compliance failure",
        icon: ShieldAlert,
        action: "Inspect failed clauses",
      };
    default:
      return {
        tone: "emerald",
        eyebrow: "Verified clean",
        icon: ShieldCheck,
        action: "View verification",
      };
  }
};

export const DashboardPage: React.FC = () => {
  const failedCases = CANONICAL_DEMO_CASES.filter(
    (c) => c.expected_overall === "FAIL",
  );
  const passedCases = CANONICAL_DEMO_CASES.filter(
    (c) => c.expected_overall === "PASS",
  );
  const reviewSignals = SEEDED_DEMO_VERIFICATIONS.reduce(
    (total, verification) => total + verification.human_review_items.length,
    0,
  );
  const contradictionCount = SEEDED_DEMO_VERIFICATIONS.reduce(
    (total, verification) => total + verification.contradictions.length,
    0,
  );

  const attentionCases = [
    CANONICAL_DEMO_CASES.find((c) => c.bid_id === "BID-00001"),
    CANONICAL_DEMO_CASES.find((c) => c.bid_id === "BID-00667"),
    CANONICAL_DEMO_CASES.find((c) => c.bid_id === "BID-00733"),
  ].filter(Boolean) as typeof CANONICAL_DEMO_CASES;

  return (
    <div className="space-y-5 pb-8">
      {/* Hero */}
      <motion.section
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="relative overflow-hidden rounded-2xl border border-slate-200 bg-slate-950 px-6 py-6 text-white shadow-lg sm:px-8"
      >
        <div className="absolute -right-24 -top-24 h-64 w-64 rounded-full bg-blue-500/20 blur-3xl" />
        <div className="absolute -bottom-32 left-1/3 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />

        <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-300">
                <Sparkles className="h-3 w-3 text-cyan-300" />
                Procurement intelligence
              </span>
              <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2.5 py-1 font-mono text-[10px] font-semibold text-cyan-200">
                TENDER-0069 · LOCAL DEMO
              </span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
              Verification command center
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Evidence-first compliance and integrity checks across bidder
              submissions, with every finding traceable back to its source
              document.
            </p>
          </div>

          <Link
            to="/verify/new"
            className="group inline-flex shrink-0 items-center justify-center gap-2 rounded-lg bg-white px-4 py-2.5 text-xs font-bold text-slate-950 shadow-sm transition hover:bg-slate-100"
          >
            <FileCheck2 className="h-4 w-4" />
            Run new verification
            <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </Link>
        </div>
      </motion.section>

      {/* Verification pulse */}
      <section>
        <div className="mb-3 flex items-end justify-between px-1">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
              Verification pulse
            </p>
            <h2 className="mt-1 text-base font-bold text-slate-900">
              What needs attention right now?
            </h2>
          </div>
          <span className="hidden font-mono text-[10px] text-slate-400 sm:block">
            CANONICAL DATASET · 4 BIDS
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            {
              label: "Evaluated",
              value: CANONICAL_DEMO_CASES.length,
              detail: "bid submissions",
              icon: ScanSearch,
              className: "border-slate-200 bg-white text-slate-900",
              iconClass: "bg-slate-100 text-slate-600",
            },
            {
              label: "Compliant",
              value: passedCases.length,
              detail: "ready to proceed",
              icon: CheckCircle2,
              className: "border-emerald-200 bg-emerald-50/60 text-emerald-900",
              iconClass: "bg-white text-emerald-600",
            },
            {
              label: "Need action",
              value: failedCases.length,
              detail: "mandatory failures",
              icon: ShieldAlert,
              className: "border-rose-200 bg-rose-50/60 text-rose-900",
              iconClass: "bg-white text-rose-600",
            },
            {
              label: "Review signals",
              value: reviewSignals,
              detail: `${contradictionCount} contradiction${contradictionCount === 1 ? "" : "s"} detected`,
              icon: AlertTriangle,
              className: "border-amber-200 bg-amber-50/60 text-amber-900",
              iconClass: "bg-white text-amber-600",
            },
          ].map((metric, index) => {
            const Icon = metric.icon;
            return (
              <motion.div
                key={metric.label}
                custom={index}
                variants={cardVariants}
                initial="hidden"
                animate="visible"
                className={`rounded-xl border p-4 shadow-sm transition-shadow hover:shadow-md ${metric.className}`}
              >
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[10px] font-bold uppercase tracking-[0.14em] opacity-70">
                    {metric.label}
                  </span>
                  <span className={`flex h-8 w-8 items-center justify-center rounded-lg ${metric.iconClass}`}>
                    <Icon className="h-4 w-4" />
                  </span>
                </div>
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="font-mono text-3xl font-bold tracking-tight">
                    {metric.value}
                  </span>
                  <span className="text-[10px] font-semibold opacity-60">
                    {metric.detail}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* Attention + health */}
      <section className="grid gap-5 lg:grid-cols-[1.55fr_0.85fr]">
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-rose-500" />
                <h2 className="text-sm font-bold text-slate-900">Attention required</h2>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">
                Start with the highest-signal findings instead of scanning every bid.
              </p>
            </div>
            <Link
              to="/review"
              className="hidden items-center gap-1 text-[11px] font-bold text-blue-600 hover:text-blue-800 sm:inline-flex"
            >
              Review queue <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="divide-y divide-slate-100">
            {attentionCases.map((c, index) => {
              const risk = getRiskMeta(c.ground_truth_label);
              const RiskIcon = risk.icon;
              const verifId = `VERIF-${c.tender_id}-${c.bid_id}`;
              const highlight = c.highlights[0] ?? c.description;

              return (
                <motion.div
                  key={c.bid_id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.3, delay: 0.15 + index * 0.07 }}
                  className="group flex items-center gap-4 px-5 py-4 transition hover:bg-slate-50"
                >
                  <div
                    className={`hidden h-10 w-10 shrink-0 items-center justify-center rounded-xl sm:flex ${
                      risk.tone === "rose"
                        ? "bg-rose-50 text-rose-600"
                        : risk.tone === "amber"
                          ? "bg-amber-50 text-amber-600"
                          : "bg-orange-50 text-orange-600"
                    }`}
                  >
                    <RiskIcon className="h-5 w-5" />
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[10px] font-bold text-slate-400">
                        {c.bid_id}
                      </span>
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                        {risk.eyebrow}
                      </span>
                    </div>
                    <h3 className="mt-1 truncate text-sm font-bold text-slate-900">
                      {c.company_name}
                    </h3>
                    <p className="mt-0.5 truncate text-[11px] text-slate-500">
                      {highlight}
                    </p>
                  </div>

                  <div className="hidden shrink-0 sm:block">
                    <OverallBadge status={c.expected_overall} size="sm" />
                  </div>

                  <Link
                    to={`/verification/${verifId}`}
                    className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-[10px] font-bold text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-950"
                  >
                    <span className="hidden md:inline">{risk.action}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </motion.div>
              );
            })}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
                Verification health
              </p>
              <h2 className="mt-1 text-sm font-bold text-slate-900">Outcome distribution</h2>
            </div>
            <ShieldCheck className="h-5 w-5 text-slate-400" />
          </div>

          <div className="mt-5 flex items-end gap-4">
            <div>
              <span className="font-mono text-4xl font-bold tracking-tight text-slate-900">
                {Math.round((passedCases.length / CANONICAL_DEMO_CASES.length) * 100)}%
              </span>
              <p className="mt-1 text-[10px] font-semibold text-slate-500">clean submissions</p>
            </div>
            <div className="mb-1 h-10 w-px bg-slate-200" />
            <div>
              <span className="font-mono text-lg font-bold text-slate-700">
                {CANONICAL_DEMO_CASES.length - passedCases.length}
              </span>
              <p className="mt-1 text-[10px] font-semibold text-slate-500">need attention</p>
            </div>
          </div>

          <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-emerald-500"
              style={{ width: `${(passedCases.length / CANONICAL_DEMO_CASES.length) * 100}%` }}
            />
          </div>

          <div className="mt-5 space-y-3">
            <div className="flex items-center justify-between text-[11px]">
              <span className="flex items-center gap-2 font-semibold text-slate-600">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Compliant
              </span>
              <span className="font-mono font-bold text-slate-900">{passedCases.length}</span>
            </div>
            <div className="flex items-center justify-between text-[11px]">
              <span className="flex items-center gap-2 font-semibold text-slate-600">
                <span className="h-2 w-2 rounded-full bg-rose-500" />
                Non-compliant
              </span>
              <span className="font-mono font-bold text-slate-900">{failedCases.length}</span>
            </div>
            <div className="flex items-center justify-between text-[11px]">
              <span className="flex items-center gap-2 font-semibold text-slate-600">
                <span className="h-2 w-2 rounded-full bg-amber-500" />
                Human review signals
              </span>
              <span className="font-mono font-bold text-slate-900">{reviewSignals}</span>
            </div>
          </div>
        </div>
      </section>

      {/* Demo cases */}
      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-2 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-900">Canonical tender cases</h2>
              <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[9px] font-bold text-slate-500">
                SIH DEMO
              </span>
            </div>
            <p className="mt-1 text-[11px] text-slate-500">
              Four representative outcomes designed to demonstrate the full verification workflow.
            </p>
          </div>
          <span className="font-mono text-[10px] text-slate-400">TENDER-0069</span>
        </div>

        <div className="grid gap-3 p-4 md:grid-cols-2 xl:grid-cols-4">
          {CANONICAL_DEMO_CASES.map((c, index) => {
            const risk = getRiskMeta(c.ground_truth_label);
            const verifId = `VERIF-${c.tender_id}-${c.bid_id}`;
            const isClean = c.expected_overall === "PASS";

            return (
              <motion.div
                key={c.bid_id}
                custom={index}
                variants={cardVariants}
                initial="hidden"
                animate="visible"
                whileHover={{ y: -3 }}
                className="group flex min-h-[218px] flex-col rounded-xl border border-slate-200 bg-slate-50/70 p-4 transition-shadow hover:shadow-md"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-[10px] font-bold text-slate-500">
                    {c.bid_id}
                  </span>
                  <OverallBadge status={c.expected_overall} size="sm" />
                </div>

                <div className="mt-4 flex items-start gap-2">
                  <span
                    className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${
                      isClean ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {isClean ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <risk.icon className="h-4 w-4" />
                    )}
                  </span>
                  <div className="min-w-0">
                    <h3 className="truncate text-sm font-bold text-slate-900">
                      {c.company_name}
                    </h3>
                    <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-slate-500">
                      {c.description}
                    </p>
                  </div>
                </div>

                <div className="mt-4 flex-1 border-t border-slate-200 pt-3">
                  <p className="line-clamp-2 text-[10px] font-semibold leading-4 text-slate-600">
                    {c.highlights[0]}
                  </p>
                </div>

                <Link
                  to={`/verification/${verifId}`}
                  className="mt-3 inline-flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-[10px] font-bold text-slate-700 shadow-sm transition hover:border-slate-300 hover:text-slate-950"
                >
                  <span>{isClean ? "View verification" : "Investigate case"}</span>
                  <ArrowRight className="h-3.5 w-3.5 text-slate-400 transition-transform group-hover:translate-x-0.5" />
                </Link>
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* Recent activity */}
      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <div>
            <h2 className="text-sm font-bold text-slate-900">Recent verification activity</h2>
            <p className="mt-1 text-[11px] text-slate-500">
              Deterministic runs completed by the verification pipeline.
            </p>
          </div>
          <Clock3 className="h-4 w-4 text-slate-400" />
        </div>

        <div className="divide-y divide-slate-100">
          {SEEDED_DEMO_VERIFICATIONS.map((v) => {
            const demo = CANONICAL_DEMO_CASES.find((d) => d.bid_id === v.bid_id);
            return (
              <Link
                key={v.verification_id}
                to={`/verification/${v.verification_id}`}
                className="group flex flex-col gap-3 px-5 py-3.5 transition hover:bg-slate-50 sm:flex-row sm:items-center"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-xs font-bold text-slate-900">
                      {demo?.company_name || v.bid_id}
                    </span>
                    <span className="hidden rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[9px] text-slate-500 sm:inline">
                      {v.bid_id}
                    </span>
                  </div>
                  <p className="mt-0.5 truncate font-mono text-[9px] text-slate-400">
                    {v.verification_id} · {v.deterministic_run_id}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <OverallBadge status={v.overall_status} size="sm" />
                  <ComplianceBadge status={v.compliance_status} size="sm" />
                  <IntegrityBadge status={v.integrity_status} size="sm" />
                  <ArrowRight className="ml-1 h-3.5 w-3.5 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-slate-500" />
                </div>
              </Link>
            );
          })}
        </div>
      </section>
    </div>
  );
};
