import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud,
  FileText,
  X,
  AlertCircle,
  Play,
  ArrowRight,
  Shield,
  CheckCircle2,
  Cpu,
  Scale,
  Loader2,
  AlertTriangle,
  UserRound,
  FileCheck2,
  LockKeyhole,
  Sparkles,
  Layers,
} from "lucide-react";
import { CANONICAL_DEMO_CASES, SEEDED_DEMO_VERIFICATIONS } from "../data/demoCases";
import { apiClient } from "../api/client";
import { AggregatedVerification } from "../types";

const MAX_FILE_SIZE = 25 * 1024 * 1024;

const PIPELINE_STAGES = [
  { step: 1, label: "PDF Ingestion & Page Segmentation", layer: "Physical pipeline" },
  { step: 2, label: "Text Extraction & BBox Grounding", layer: "Physical evidence" },
  { step: 3, label: "Candidate Parameter Extraction", layer: "AI-assisted upstream" },
  { step: 4, label: "Deterministic Compliance Evaluation", layer: "Authoritative rule engine" },
  { step: 5, label: "Contradictions & Government Registries", layer: "Integrity adapters" },
  { step: 6, label: "Audit Dossier Compilation & Sealing", layer: "Orchestration" },
];

export const NewVerificationPage: React.FC = () => {
  const navigate = useNavigate();
  const intervalRef = useRef<number | null>(null);
  const timeoutRef = useRef<number | null>(null);

  // Workflow mode: "live" (real backend verification) or "demo" (canonical showcase)
  const [activeTab, setActiveTab] = useState<"live" | "demo">("live");

  // Live verification file & metadata state
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [bidFiles, setBidFiles] = useState<File[]>([]);
  const [tenderId, setTenderId] = useState("");
  const [bidId, setBidId] = useState("");
  const [companyName, setCompanyName] = useState("");

  // Pipeline execution & error state
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentStage, setCurrentStage] = useState(0);
  const [isComplete, setIsComplete] = useState(false);
  const [completedResult, setCompletedResult] = useState<AggregatedVerification | null>(null);

  useEffect(() => () => {
    if (intervalRef.current) window.clearInterval(intervalRef.current);
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
  }, []);

  const validatePdf = (file: File, context: "tender" | "bid") => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      return context === "tender"
        ? "Only PDF documents (.pdf) are supported for tender specifications."
        : "All bidder submissions must be valid PDF documents (.pdf).";
    }
    if (file.size > MAX_FILE_SIZE) {
      return `${file.name} exceeds the 25MB file limit.`;
    }
    return null;
  };

  const handleTenderDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setValidationError(null);
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    const error = validatePdf(file, "tender");
    if (error) return setValidationError(error);
    setTenderFile(file);
  };

  const handleBidFilesDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setValidationError(null);
    const files = Array.from(e.dataTransfer.files || []);
    if (!files.length) return;
    const invalid = files.map((file) => validatePdf(file, "bid")).find(Boolean);
    if (invalid) return setValidationError(invalid);
    setBidFiles((prev) => [...prev, ...files]);
  };

  const handleTenderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValidationError(null);
    const file = e.target.files?.[0];
    if (!file) return;
    const error = validatePdf(file, "tender");
    if (error) return setValidationError(error);
    setTenderFile(file);
    e.target.value = "";
  };

  const handleBidSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValidationError(null);
    const files = Array.from(e.target.files || []);
    if (!files.length) return;
    const invalid = files.map((file) => validatePdf(file, "bid")).find(Boolean);
    if (invalid) return setValidationError(invalid);
    setBidFiles((prev) => [...prev, ...files]);
    e.target.value = "";
  };

  const removeBidFile = (index: number) => {
    setBidFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Execution: Live Backend Verification
  const executeLivePipeline = async () => {
    if (!tenderFile) {
      setValidationError("Please select or drop a valid Tender Specification PDF.");
      return;
    }
    if (bidFiles.length === 0) {
      setValidationError("Please select or drop at least one Bidder Submission PDF.");
      return;
    }

    if (intervalRef.current) window.clearInterval(intervalRef.current);
    if (timeoutRef.current) window.clearTimeout(timeoutRef.current);

    setValidationError(null);
    setIsProcessing(true);
    setIsComplete(false);
    setCompletedResult(null);
    setCurrentStage(1);

    // Realistic UI progression through early stages while backend executes
    intervalRef.current = window.setInterval(() => {
      setCurrentStage((prev) => {
        if (prev < 5) return prev + 1;
        return 5;
      });
    }, 650);

    const formData = new FormData();
    formData.append("tender_file", tenderFile);
    bidFiles.forEach((file) => {
      formData.append("bid_files", file);
    });
    if (tenderId.trim()) formData.append("tender_id", tenderId.trim());
    if (bidId.trim()) formData.append("bid_id", bidId.trim());
    if (companyName.trim()) formData.append("company_name", companyName.trim());
    formData.append("mode", "mock");

    try {
      const result = await apiClient.verifyBid(formData);

      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }

      setCurrentStage(6);
      setIsComplete(true);
      setCompletedResult(result);

      // Transition to Forensic Workbench using the real verification ID
      timeoutRef.current = window.setTimeout(() => {
        navigate(`/verification/${encodeURIComponent(result.verification_id)}`, {
          state: { verification: result },
        });
      }, 2000);
    } catch (err: any) {
      if (intervalRef.current) {
        window.clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setIsProcessing(false);
      setIsComplete(false);
      setCurrentStage(0);
      setValidationError(
        err.detail ||
          err.message ||
          "Failed to communicate with verification backend. Ensure backend is running at http://localhost:8000."
      );
    }
  };

  // Demo showcase navigation
  const inspectDemoCase = (demoCase: (typeof CANONICAL_DEMO_CASES)[number]) => {
    navigate(`/verification/VERIF-${demoCase.tender_id}-${demoCase.bid_id}`);
  };

  const readyToRunLive = !!tenderFile && bidFiles.length > 0 && !isProcessing;

  const totalRequirements = completedResult?.verification_results.length ?? 0;
  const failedRequirements =
    completedResult?.verification_results.filter((result) => result.status === "FAIL").length ?? 0;
  const integrityFindings = completedResult?.contradictions.length ?? 0;
  const reviewItems = completedResult?.human_review_items.length ?? 0;
  const reviewRequired = completedResult?.review_required ?? false;

  return (
    <div className="mx-auto max-w-6xl space-y-5 font-sans">
      <header className="flex flex-col gap-4 border-b border-slate-200 pb-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-white shadow-sm">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="app-eyebrow">Verification intake</p>
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-950">
              New Bid Verification & Ingestion
            </h1>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-slate-500">
              Upload real tender specifications and bidder submission evidence for evidence-grounded deterministic verification.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => setActiveTab("live")}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-bold transition-all ${
                activeTab === "live"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Cpu className="h-3.5 w-3.5" />
              Live Verification
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("demo")}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-bold transition-all ${
                activeTab === "demo"
                  ? "bg-white text-slate-900 shadow-sm"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              <Layers className="h-3.5 w-3.5" />
              Demo Showcase
            </button>
          </div>
        </div>
      </header>

      {validationError && (
        <div
          role="alert"
          className="flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs text-rose-800 shadow-sm"
        >
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span className="font-medium">{validationError}</span>
        </div>
      )}

      {activeTab === "live" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            {[
              ["01", "Upload PDFs", "Tender spec + bidder documents"],
              ["02", "Configure parameters", "Auto-detected or custom IDs"],
              ["03", "Run & inspect", "Real verification → Workbench"],
            ].map(([number, title, detail], index) => (
              <div
                key={number}
                className={`rounded-xl border px-4 py-3 ${
                  index === 0
                    ? "border-slate-300 bg-white"
                    : "border-slate-200 bg-slate-50/70"
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[10px] font-bold text-blue-600">
                    {number}
                  </span>
                  <div>
                    <p className="text-xs font-bold text-slate-900">{title}</p>
                    <p className="text-[10px] text-slate-500">{detail}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Tender PDF Section */}
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <FileText className="h-4 w-4 text-blue-600" />
                    <h2 className="text-sm font-bold text-slate-900">
                      Tender Specification PDF
                    </h2>
                  </div>
                  <p className="mt-1 text-[11px] leading-5 text-slate-500">
                    Official bid document defining eligibility criteria, GTC, STC, and ATC clauses.
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-2 py-1 font-mono text-[9px] font-bold uppercase text-slate-500">
                  Required
                </span>
              </div>

              {!tenderFile ? (
                <div
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={handleTenderDrop}
                  className="mt-4 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/50 p-7 text-center transition hover:border-blue-400 hover:bg-blue-50/20"
                >
                  <UploadCloud className="mx-auto mb-2 h-8 w-8 text-slate-400" />
                  <p className="text-xs font-semibold text-slate-700">
                    Drag & drop tender specification PDF
                  </p>
                  <p className="mt-1 text-[10px] text-slate-400">
                    PDF only · maximum 25MB
                  </p>
                  <label className="mt-3 inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-[11px] font-bold text-slate-700 shadow-sm hover:bg-slate-50">
                    Browse PDF
                    <input
                      type="file"
                      accept=".pdf"
                      className="hidden"
                      onChange={handleTenderSelect}
                    />
                  </label>
                </div>
              ) : (
                <div className="mt-4 flex items-center justify-between rounded-xl border border-emerald-200 bg-emerald-50/60 p-3">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-emerald-600">
                      <CheckCircle2 className="h-4 w-4" />
                    </span>
                    <div className="min-w-0">
                      <span className="block truncate text-xs font-semibold text-slate-800">
                        {tenderFile.name}
                      </span>
                      <span className="block font-mono text-[10px] text-slate-400">
                        {(tenderFile.size / 1024).toFixed(1)} KB · PDF accepted
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => setTenderFile(null)}
                    className="rounded-lg p-1.5 text-slate-500 hover:bg-white hover:text-slate-800"
                    aria-label="Remove tender PDF"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}
            </section>

            {/* Bidder PDFs Section */}
            <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <FileCheck2 className="h-4 w-4 text-blue-600" />
                    <h2 className="text-sm font-bold text-slate-900">
                      Bidder Submissions & Annexures
                    </h2>
                  </div>
                  <p className="mt-1 text-[11px] leading-5 text-slate-500">
                    Technical proposal, financial annexure, certificates, and declarations.
                  </p>
                </div>
                <span className="rounded-full bg-slate-100 px-2 py-1 font-mono text-[9px] font-bold uppercase text-slate-500">
                  {bidFiles.length} file{bidFiles.length === 1 ? "" : "s"}
                </span>
              </div>

              <div
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleBidFilesDrop}
                className="mt-4 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/50 p-7 text-center transition hover:border-blue-400 hover:bg-blue-50/20"
              >
                <UploadCloud className="mx-auto mb-2 h-8 w-8 text-slate-400" />
                <p className="text-xs font-semibold text-slate-700">
                  Drag & drop bidder PDFs
                </p>
                <p className="mt-1 text-[10px] text-slate-400">
                  Multiple files · maximum 25MB each
                </p>
                <label className="mt-3 inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-[11px] font-bold text-slate-700 shadow-sm hover:bg-slate-50">
                  Browse files
                  <input
                    type="file"
                    accept=".pdf"
                    multiple
                    className="hidden"
                    onChange={handleBidSelect}
                  />
                </label>
              </div>

              {bidFiles.length > 0 && (
                <div className="mt-3 space-y-1.5 border-t border-slate-100 pt-3">
                  {bidFiles.map((file, index) => (
                    <div
                      key={`${file.name}-${index}`}
                      className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2"
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        <FileText className="h-4 w-4 shrink-0 text-slate-500" />
                        <span className="truncate text-[11px] font-medium text-slate-800">
                          {file.name}
                        </span>
                      </div>
                      <button
                        type="button"
                        onClick={() => removeBidFile(index)}
                        className="rounded p-1 text-slate-400 hover:bg-white hover:text-slate-800"
                        aria-label={`Remove ${file.name}`}
                      >
                        <X className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>

          {/* Optional Submission Metadata */}
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
              <Cpu className="h-4 w-4 text-slate-600" />
              <h2 className="text-sm font-bold text-slate-900">
                Submission Parameters (Optional)
              </h2>
              <span className="text-[10px] text-slate-400">
                Leave blank to auto-detect from document contents
              </span>
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600">
                  Tender Identifier
                </label>
                <input
                  type="text"
                  placeholder="e.g. TENDER-0001"
                  value={tenderId}
                  onChange={(e) => setTenderId(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600">
                  Bidder Submission ID
                </label>
                <input
                  type="text"
                  placeholder="e.g. BID-00001"
                  value={bidId}
                  onChange={(e) => setBidId(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none"
                />
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600">
                  Bidder Legal Entity Name
                </label>
                <input
                  type="text"
                  placeholder="e.g. Acme Technologies Ltd"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="mt-1.5 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-900 focus:border-blue-500 focus:bg-white focus:outline-none"
                />
              </div>
            </div>
          </section>

          {/* Architectural Verification Pipeline Execution Card */}
          <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-col gap-4 bg-slate-950 px-5 py-4 text-white sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <Scale className="h-4 w-4 text-blue-300" />
                  <p className="text-xs font-bold">Architectural verification pipeline</p>
                </div>
                <p className="mt-1 font-mono text-[10px] text-slate-400">
                  Candidate extraction is upstream; deterministic rules retain decision authority.
                </p>
              </div>
              <button
                type="button"
                disabled={!readyToRunLive}
                onClick={executeLivePipeline}
                className={`inline-flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-xs font-bold transition ${
                  readyToRunLive
                    ? "bg-white text-slate-950 hover:bg-slate-100 shadow-sm"
                    : "cursor-not-allowed bg-slate-800 text-slate-500"
                }`}
              >
                {isProcessing ? (
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                ) : (
                  <Play className="h-4 w-4" />
                )}
                {isProcessing
                  ? `Verifying Submission · Step ${currentStage}/6`
                  : "Run verification pipeline"}
              </button>
            </div>

            {isProcessing && (
              <div className="p-4">
                <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
                  {PIPELINE_STAGES.map((stage) => {
                    const done = currentStage > stage.step || isComplete;
                    const current = currentStage === stage.step && !isComplete;
                    return (
                      <div
                        key={stage.step}
                        className={`rounded-lg border p-2.5 transition-all ${
                          done
                            ? "border-emerald-200 bg-emerald-50"
                            : current
                              ? "border-blue-400 bg-blue-50 ring-1 ring-blue-300"
                              : "border-slate-200 bg-slate-50"
                        }`}
                      >
                        <div className="flex items-center justify-between font-mono text-[9px] font-bold uppercase text-slate-500">
                          <span>Step {stage.step}</span>
                          {done ? (
                            <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                          ) : current ? (
                            <Loader2 className="h-3 w-3 animate-spin text-blue-600" />
                          ) : null}
                        </div>
                        <p className="mt-1.5 line-clamp-2 text-[10px] font-semibold leading-4 text-slate-800">
                          {stage.label}
                        </p>
                        <p className="mt-1 truncate text-[8px] text-slate-400">
                          {stage.layer}
                        </p>
                      </div>
                    );
                  })}
                </div>

                {isComplete && completedResult && (
                  <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50/60 p-4">
                    <div className="flex items-start gap-3">
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white text-emerald-600 shadow-sm">
                        <CheckCircle2 className="h-5 w-5" />
                      </span>
                      <div>
                        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-700">
                          Verification complete
                        </p>
                        <p className="mt-0.5 text-sm font-bold text-slate-900">
                          {completedResult.bid_id} · {completedResult.verification_id}
                        </p>
                        <p className="mt-0.5 text-[11px] text-slate-600">
                          Evidence-grounded result compiled from live backend. Opening the forensic workbench next.
                        </p>
                      </div>
                    </div>

                    <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
                      <div className="rounded-lg border border-emerald-200 bg-white p-3 shadow-2xs">
                        <p className="text-[9px] font-bold uppercase text-slate-400">
                          Compliance
                        </p>
                        <p className="mt-1 text-sm font-black text-emerald-700">
                          {completedResult.compliance_status}
                        </p>
                      </div>
                      <div
                        className={`rounded-lg border p-3 shadow-2xs ${
                          completedResult.integrity_status === "CONSISTENT"
                            ? "border-emerald-200 bg-white text-emerald-700"
                            : "border-rose-200 bg-white text-rose-700"
                        }`}
                      >
                        <p className="text-[9px] font-bold uppercase text-slate-400">
                          Integrity
                        </p>
                        <p className="mt-1 text-sm font-black">
                          {completedResult.integrity_status}
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-2xs">
                        <p className="text-[9px] font-bold uppercase text-slate-400">
                          Requirements
                        </p>
                        <p className="mt-1 text-sm font-black text-slate-900">
                          {totalRequirements}
                        </p>
                      </div>
                      <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-2xs">
                        <p className="text-[9px] font-bold uppercase text-slate-400">
                          Failures
                        </p>
                        <p className="mt-1 text-sm font-black text-slate-900">
                          {failedRequirements}
                        </p>
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-semibold">
                      <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-slate-600">
                        Integrity findings: {integrityFindings}
                      </span>
                      <span
                        className={`rounded-full border px-2.5 py-1 ${
                          reviewRequired
                            ? "border-amber-200 bg-amber-50 text-amber-800"
                            : "border-emerald-200 bg-emerald-50 text-emerald-800"
                        }`}
                      >
                        {reviewRequired ? (
                          <>
                            <UserRound className="mr-1 inline h-3 w-3" />
                            Officer review required · {reviewItems}
                          </>
                        ) : (
                          "No officer review required"
                        )}
                      </span>
                      {completedResult.overall_status === "FAIL" && (
                        <span className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 text-rose-800">
                          <AlertTriangle className="mr-1 inline h-3 w-3" />
                          Overall result: FAIL
                        </span>
                      )}
                    </div>

                    <div className="mt-4 flex items-center justify-end border-t border-emerald-200 pt-3">
                      <button
                        type="button"
                        onClick={() =>
                          navigate(`/verification/${encodeURIComponent(completedResult.verification_id)}`, {
                            state: { verification: completedResult },
                          })
                        }
                        className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-700 px-4 py-2 font-mono text-xs font-bold text-white shadow-sm hover:bg-emerald-800 transition"
                      >
                        Open verification workbench <ArrowRight className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}
          </section>
        </>
      ) : (
        /* Demo Showcase Tab */
        <section className="space-y-4">
          <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4 text-xs text-amber-900 shadow-sm">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-700" />
              <strong className="text-sm font-bold">Demonstration Showcase</strong>
            </div>
            <p className="mt-1 leading-relaxed text-amber-800">
              Explore pre-computed forensic evaluations from the SIH benchmark dataset. These profiles demonstrate edge-case scenarios including GSTIN cross-document contradictions, clause failures, and ambiguous claims. To verify your own uploaded documents against the real backend engine, switch to the <strong>Live Verification</strong> tab.
            </p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {CANONICAL_DEMO_CASES.map((c) => {
              const verification = SEEDED_DEMO_VERIFICATIONS.find((v) => v.bid_id === c.bid_id);
              return (
                <div
                  key={c.bid_id}
                  className="flex flex-col justify-between rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:border-blue-300 transition"
                >
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="font-mono text-[10px] font-bold text-blue-600">
                          {c.bid_id}
                        </span>
                        <p className="mt-1 text-xs font-bold text-slate-900">
                          {c.company_name}
                        </p>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[9px] font-bold uppercase text-slate-600">
                        {c.ground_truth_label}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-3 text-[10px] leading-4 text-slate-500">
                      {c.description}
                    </p>
                  </div>

                  <div className="mt-4 border-t border-slate-100 pt-3">
                    <div className="mb-3 flex items-center justify-between text-[9px] font-mono font-bold uppercase">
                      <span
                        className={
                          verification?.compliance_status === "PASS"
                            ? "text-emerald-600"
                            : "text-rose-600"
                        }
                      >
                        Compliance: {verification?.compliance_status ?? "—"}
                      </span>
                      <span
                        className={
                          verification?.integrity_status === "CONSISTENT"
                            ? "text-emerald-600"
                            : "text-rose-600"
                        }
                      >
                        Integrity: {verification?.integrity_status ?? "—"}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => inspectDemoCase(c)}
                      className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-bold text-slate-700 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-200 transition"
                    >
                      Inspect in Workbench <ArrowRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
};
