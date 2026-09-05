import React from "react";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  MinusCircle,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
} from "lucide-react";
import { ComplianceStatus, IntegrityStatus, OverallStatus, Severity } from "../../types";

interface BadgeProps {
  className?: string;
  size?: "sm" | "md" | "lg";
}

export const ComplianceBadge: React.FC<BadgeProps & { status: ComplianceStatus | string }> = ({
  status,
  size = "md",
  className = "",
}) => {
  const s = (status || "N/A").toUpperCase();
  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs font-semibold gap-1",
    md: "px-2.5 py-1 text-xs font-semibold gap-1.5",
    lg: "px-3.5 py-1.5 text-sm font-semibold gap-2",
  }[size];

  switch (s) {
    case "PASS":
      return (
        <span
          className={`inline-flex items-center rounded-md bg-emerald-50 text-emerald-800 border border-emerald-300 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Compliance Status: PASS"
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 shrink-0" aria-hidden="true" />
          PASS
        </span>
      );
    case "FAIL":
      return (
        <span
          className={`inline-flex items-center rounded-md bg-rose-50 text-rose-800 border border-rose-300 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Compliance Status: FAIL"
        >
          <XCircle className="w-3.5 h-3.5 text-rose-600 shrink-0" aria-hidden="true" />
          FAIL
        </span>
      );
    case "REVIEW":
    case "PARTIAL":
      return (
        <span
          className={`inline-flex items-center rounded-md bg-amber-50 text-amber-800 border border-amber-300 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Compliance Status: REVIEW REQUIRED"
        >
          <AlertTriangle className="w-3.5 h-3.5 text-amber-600 shrink-0" aria-hidden="true" />
          {s === "PARTIAL" ? "PARTIAL" : "REVIEW"}
        </span>
      );
    case "MISSING":
      return (
        <span
          className={`inline-flex items-center rounded-md bg-slate-100 text-slate-700 border border-slate-300 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Compliance Status: MISSING"
        >
          <HelpCircle className="w-3.5 h-3.5 text-slate-500 shrink-0" aria-hidden="true" />
          MISSING
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center rounded-md bg-gray-100 text-gray-600 border border-gray-200 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Compliance Status: N/A"
        >
          <MinusCircle className="w-3.5 h-3.5 text-gray-400 shrink-0" aria-hidden="true" />
          N/A
        </span>
      );
  }
};

export const IntegrityBadge: React.FC<BadgeProps & { status: IntegrityStatus | string }> = ({
  status,
  size = "md",
  className = "",
}) => {
  const s = (status || "CONSISTENT").toUpperCase();
  const sizeClasses = {
    sm: "px-2 py-0.5 text-xs font-semibold gap-1",
    md: "px-2.5 py-1 text-xs font-semibold gap-1.5",
    lg: "px-3.5 py-1.5 text-sm font-semibold gap-2",
  }[size];

  switch (s) {
    case "CONSISTENT":
      return (
        <span
          className={`inline-flex items-center rounded-md bg-slate-100 text-slate-800 border border-slate-300 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Integrity Status: CONSISTENT"
        >
          <ShieldCheck className="w-3.5 h-3.5 text-slate-600 shrink-0" aria-hidden="true" />
          CONSISTENT
        </span>
      );
    case "CONTRADICTION":
      return (
        <span
          className={`inline-flex items-center rounded-md bg-rose-50 text-rose-900 border border-rose-300 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Integrity Status: CONTRADICTION DETECTED"
        >
          <ShieldAlert className="w-3.5 h-3.5 text-rose-600 shrink-0" aria-hidden="true" />
          CONTRADICTION
        </span>
      );
    case "REVIEW":
      return (
        <span
          className={`inline-flex items-center rounded-md bg-amber-50 text-amber-900 border border-amber-300 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Integrity Status: REVIEW REQUIRED"
        >
          <ShieldQuestion className="w-3.5 h-3.5 text-amber-600 shrink-0" aria-hidden="true" />
          REVIEW
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center rounded-md bg-gray-100 text-gray-700 border border-gray-300 font-medium ${sizeClasses} ${className}`}
          role="status"
          aria-label="Integrity Status: INCOMPLETE"
        >
          <ShieldQuestion className="w-3.5 h-3.5 text-gray-500 shrink-0" aria-hidden="true" />
          INCOMPLETE
        </span>
      );
  }
};

export const OverallBadge: React.FC<BadgeProps & { status: OverallStatus | string }> = ({
  status,
  size = "lg",
  className = "",
}) => {
  const s = (status || "REVIEW").toUpperCase();
  const sizeClasses = {
    sm: "px-2.5 py-0.5 text-xs font-bold gap-1",
    md: "px-3 py-1 text-xs font-bold gap-1.5",
    lg: "px-4 py-1.5 text-sm font-bold gap-2 tracking-wide",
  }[size];

  switch (s) {
    case "PASS":
      return (
        <span
          className={`inline-flex items-center rounded-full bg-emerald-100 text-emerald-900 border border-emerald-300 ${sizeClasses} ${className}`}
        >
          <CheckCircle2 className="w-4 h-4 text-emerald-700" aria-hidden="true" />
          PASS
        </span>
      );
    case "FAIL":
      return (
        <span
          className={`inline-flex items-center rounded-full bg-rose-100 text-rose-900 border border-rose-300 ${sizeClasses} ${className}`}
        >
          <XCircle className="w-4 h-4 text-rose-700" aria-hidden="true" />
          FAIL
        </span>
      );
    default:
      return (
        <span
          className={`inline-flex items-center rounded-full bg-amber-100 text-amber-900 border border-amber-300 ${sizeClasses} ${className}`}
        >
          <AlertTriangle className="w-4 h-4 text-amber-700" aria-hidden="true" />
          REVIEW REQUIRED
        </span>
      );
  }
};

export const SeverityBadge: React.FC<{ severity: Severity | string }> = ({ severity }) => {
  const sev = (severity || "INFO").toUpperCase();
  const styles: Record<string, string> = {
    CRITICAL: "bg-rose-50 text-rose-700 border-rose-200",
    MAJOR: "bg-orange-50 text-orange-700 border-orange-200",
    MEDIUM: "bg-amber-50 text-amber-700 border-amber-200",
    LOW: "bg-slate-50 text-slate-600 border-slate-200",
    INFO: "bg-blue-50 text-blue-600 border-blue-200",
  };

  return (
    <span
      className={`inline-block px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider rounded border ${styles[sev] || styles.INFO}`}
    >
      {sev}
    </span>
  );
};
