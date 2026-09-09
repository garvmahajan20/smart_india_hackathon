import React, { useState } from "react";
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
} from "lucide-react";
import { CANONICAL_DEMO_CASES, SEEDED_DEMO_VERIFICATIONS } from "../data/demoCases";

const PIPELINE_STAGES = [
  { step: 1, label: "PDF Ingestion & Page Segmentation", layer: "Step 6 Physical Pipeline", type: "system" },
  { step: 2, label: "Text Extraction & BBox Grounding", layer: "Step 6 Physical BBoxes", type: "system" },
  { step: 3, label: "Candidate Parameter Extraction", layer: "Step 7 AI-Assisted (Upstream)", type: "ai" },
  { step: 4, label: "Deterministic Compliance Evaluation", layer: "Step 4 Rule Engine (Authoritative)", type: "rule" },
  { step: 5, label: "Cross-Doc Contradictions & Govt Registries", layer: "Step 5 Adapters & Integrity", type: "rule" },
  { step: 6, label: "Audit Dossier Compilation & Sealing", layer: "Step 8 Orchestrator", type: "system" },
];

export const NewVerificationPage: React.FC = () => {
  const navigate = useNavigate();
  const [tenderFile, setTenderFile] = useState<File | null>(null);
  const [bidFiles, setBidFiles] = useState<File[]>([]);
  const [selectedDemoCase, setSelectedDemoCase] = useState<(typeof CANONICAL_DEMO_CASES)[number] | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [currentStage, setCurrentStage] = useState<number>(0);
  const [isComplete, setIsComplete] = useState<boolean>(false);

  const matchCanonicalCase = (files: File[]) => {
    const matched = CANONICAL_DEMO_CASES.find((demoCase) =>
      files.some((file) => file.name.toUpperCase().includes(demoCase.bid_id)),
    );
    if (matched) setSelectedDemoCase(matched);
    return matched || null;
  };

  const handleTenderDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setValidationError(null);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const f = e.dataTransfer.files[0];
      if (!f.name.toLowerCase().endsWith(".pdf")) {
        setValidationError("Only PDF documents (.pdf) are supported for tender specifications.");
        return;
      }
      setTenderFile(f);
    }
  };

  const handleBidFilesDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setValidationError(null);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const validFiles: File[] = [];
      for (let i = 0; i < e.dataTransfer.files.length; i++) {
        const f = e.dataTransfer.files[i];
        if (!f.name.toLowerCase().endsWith(".pdf")) {
          setValidationError("All bidder submissions must be valid PDF documents (.pdf).");
          return;
        }
        validFiles.push(f);
      }
      setBidFiles((prev) => [...prev, ...validFiles]);
      const matched = matchCanonicalCase(validFiles);
      if (matched) setValidationError(null);
    }
  };

  const handleTenderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValidationError(null);
    if (e.target.files && e.target.files[0]) {
      const f = e.target.files[0];
      if (!f.name.toLowerCase().endsWith(".pdf")) {
        setValidationError("Only PDF documents (.pdf) are supported.");
        return;
      }
      setTenderFile(f);
    }
  };

  const handleBidSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    setValidationError(null);
    if (e.target.files && e.target.files.length > 0) {
      const validFiles: File[] = [];
      for (let i = 0; i < e.target.files.length; i++) {
        const f = e.target.files[i];
        if (!f.name.toLowerCase().endsWith(".pdf")) {
          setValidationError("All bidder files must be .pdf files.");
          return;
        }
        validFiles.push(f);
      }
      setBidFiles((prev) => [...prev, ...validFiles]);
      matchCanonicalCase(validFiles);
    }
  };

  const removeBidFile = (index: number) => {
    setBidFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const selectDemoCase = (demoCase: (typeof CANONICAL_DEMO_CASES)[number]) => {
    setSelectedDemoCase(demoCase);
    setValidationError(null);
  };

  const executePipeline = () => {
    const resolvedCase = selectedDemoCase || matchCanonicalCase(bidFiles);

    if (!resolvedCase) {
      setValidationError(
        "Select a demonstration submission or upload a bidder PDF whose filename contains its BID identifier before running verification.",
      );
      return;
    }

    setValidationError(null);
    setIsProcessing(true);
    setIsComplete(false);
    setCurrentStage(1);

    // Step through the 6 stages to visually prove technical separation.
    // The local prototype resolves to the selected submission's verification result.
    const interval = setInterval(() => {
      setCurrentStage((prev) => {
        if (prev >= 6) {
          clearInterval(interval);
          setIsComplete(true);
          setTimeout(() => {
            navigate(`/verification/VERIF-${resolvedCase.tender_id}-${resolvedCase.bid_id}`);
          }, 2200);
          return 6;
        }
        return prev + 1;
      });
    }, 450);
  };

  const completedVerification = selectedDemoCase
    ? SEEDED_DEMO_VERIFICATIONS.find((verification) => verification.bid_id === selectedDemoCase.bid_id)
    : null;

  const totalRequirements = completedVerification?.verification_results.length ?? 0;
  const failedRequirements = completedVerification
    ? completedVerification.verification_results.filter((result) => result.status === "FAIL").length
    : 0;
  const integrityFindings = completedVerification?.contradictions.length ?? 0;
  const reviewItems = completedVerification?.human_review_items.length ?? 0;
  const reviewRequired = completedVerification?.review_required ?? false;

  const complianceTone = completedVerification?.compliance_status === "PASS"
    ? "emerald"
    : completedVerification?.compliance_status === "FAIL"
      ? "rose"
      : "amber";
  const integrityTone = completedVerification?.integrity_status === "CONSISTENT" ? "emerald" : "rose";

  return (
    <div className="mx-auto max-w-5xl space-y-6 font-sans select-none">
      <div className="border-b border-slate-200 pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-950 text-white"><Shield className="h-4 w-4" /></div>
          <div>
            <h1 className="text-xl font-bold tracking-tight text-slate-900">New Bid Verification & Ingestion</h1>
            <p className="mt-1 text-xs text-slate-500">Select or upload a bidder submission, run the verification pipeline, and inspect the resulting evidence-grounded decision.</p>
          </div>
        </div>
      </div>

      {validationError && (
        <div className="flex items-center gap-2.5 rounded-md border border-rose-200 bg-rose-50 p-3.5 text-xs text-rose-800"><AlertCircle className="h-4 w-4 shrink-0 text-rose-600" /><span>{validationError}</span></div>
      )}

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between"><h3 className="text-sm font-bold text-slate-900">Tender Specification PDF</h3><span className="font-mono text-[11px] text-slate-400">Single File</span></div>
          <p className="text-xs text-slate-500">Official GeM Bid document defining all GTC, STC, and ATC eligibility requirements.</p>
          {!tenderFile ? (
            <div onDragOver={(e) => e.preventDefault()} onDrop={handleTenderDrop} className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 p-6 text-center transition-all hover:border-blue-500 hover:bg-blue-50/20">
              <UploadCloud className="mx-auto mb-2 h-8 w-8 text-slate-400" /><p className="text-xs font-semibold text-slate-700">Drag & drop Tender PDF</p><p className="mt-1 text-[11px] text-slate-400">or browse locally</p>
              <label className="mt-3 inline-block cursor-pointer rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50">Browse PDF<input type="file" accept=".pdf" className="hidden" onChange={handleTenderSelect} /></label>
            </div>
          ) : (
            <div className="flex items-center justify-between rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex min-w-0 items-center gap-2.5"><FileText className="h-5 w-5 shrink-0 text-blue-600" /><div className="min-w-0"><span className="block truncate text-xs font-semibold text-slate-800">{tenderFile.name}</span><span className="block font-mono text-[10px] text-slate-400">{(tenderFile.size / 1024).toFixed(1)} KB</span></div></div>
              <button type="button" onClick={() => setTenderFile(null)} className="rounded p-1 text-slate-500 hover:bg-slate-200"><X className="h-4 w-4" /></button>
            </div>
          )}
        </div>

        <div className="space-y-3 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between"><h3 className="text-sm font-bold text-slate-900">Bidder Submissions & Annexures</h3><span className="font-mono text-[11px] text-slate-400">Multi-File Supported</span></div>
          <p className="text-xs text-slate-500">Technical proposal, CA turnover certificates, OEM authorization, and EMD receipts.</p>
          <div onDragOver={(e) => e.preventDefault()} onDrop={handleBidFilesDrop} className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 p-6 text-center transition-all hover:border-blue-500 hover:bg-blue-50/20">
            <UploadCloud className="mx-auto mb-2 h-8 w-8 text-slate-400" /><p className="text-xs font-semibold text-slate-700">Drag & drop Bidder PDFs</p><p className="mt-1 text-[11px] text-slate-400">Multi-file upload (max 25MB each)</p>
            <label className="mt-3 inline-block cursor-pointer rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm hover:bg-slate-50">Browse Files<input type="file" accept=".pdf" multiple className="hidden" onChange={handleBidSelect} /></label>
          </div>
          {bidFiles.length > 0 && <div className="max-h-36 space-y-1.5 overflow-y-auto border-t border-slate-200 pt-2">{bidFiles.map((bf, idx) => <div key={`${bf.name}-${idx}`} className="flex items-center justify-between rounded border border-slate-200 bg-slate-50 p-2 text-xs"><div className="flex min-w-0 items-center gap-2"><FileText className="h-4 w-4 shrink-0 text-slate-600" /><span className="truncate font-medium text-slate-800">{bf.name}</span></div><button type="button" onClick={() => removeBidFile(idx)} className="rounded p-1 text-slate-500 hover:bg-slate-200"><X className="h-3.5 w-3.5" /></button></div>)}</div>}
        </div>
      </div>

      {selectedDemoCase && (
        <div className="flex flex-col gap-3 rounded-lg border border-blue-200 bg-blue-50/70 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3"><div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white text-blue-700 shadow-sm"><CheckCircle2 className="h-4 w-4" /></div><div><p className="text-[10px] font-bold uppercase tracking-[0.15em] text-blue-700">Submission selected</p><p className="mt-0.5 text-sm font-bold text-slate-900">{selectedDemoCase.company_name}</p><p className="mt-0.5 text-[11px] text-slate-600">{selectedDemoCase.bid_id} · Ready for compliance and integrity verification</p></div></div>
          <div className="flex items-center gap-2 text-[10px] font-mono font-bold uppercase tracking-wider text-blue-800"><Cpu className="h-3.5 w-3.5" />Verification profile ready</div>
        </div>
      )}

      <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div><span className="block text-xs font-bold text-slate-900">Architectural Engine Pipeline</span><span className="font-mono text-[11px] text-slate-500">Deterministic Step 4 & Step 5 Rule Execution (Zero LLM Decision Authority)</span></div>
          <button type="button" disabled={isProcessing} onClick={executePipeline} className={`flex items-center gap-2 rounded-md px-5 py-2.5 text-xs font-semibold transition-all ${isProcessing ? "cursor-wait bg-slate-900 text-white" : "cursor-pointer bg-blue-600 text-white shadow-sm hover:bg-blue-700"}`}>
            {isProcessing ? <><Loader2 className="h-4 w-4 animate-spin text-blue-400" /><span>{isComplete ? "Verification complete" : `Executing ${selectedDemoCase?.bid_id || "Verification"} (${currentStage}/6)...`}</span></> : <><Play className="h-4 w-4" /><span>Run Verification Pipeline</span></>}
          </button>
        </div>

        {isProcessing && (
          <div className="space-y-3 border-t border-slate-100 pt-3">
            <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
              {PIPELINE_STAGES.map((st) => {
                const isDone = currentStage > st.step;
                const isCurrent = currentStage === st.step && !isComplete;
                return <div key={st.step} className={`rounded border p-2 text-[10px] font-mono transition-all ${isDone || isComplete ? "border-emerald-300 bg-emerald-50 text-emerald-900" : isCurrent ? "border-blue-500 bg-blue-50 font-bold text-blue-900 ring-1 ring-blue-400" : "border-slate-200 bg-slate-50 text-slate-400"}`}><div className="mb-1 flex items-center justify-between"><span>Step {st.step}</span>{isDone || isComplete ? <CheckCircle2 className="h-3 w-3 text-emerald-600" /> : isCurrent ? <Loader2 className="h-3 w-3 animate-spin text-blue-600" /> : null}</div><div className="truncate font-sans font-medium">{st.label}</div><div className="mt-0.5 truncate text-[9px] text-slate-500">{st.layer}</div></div>;
              })}
            </div>

            {isComplete && selectedDemoCase && completedVerification && (
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex items-start gap-3">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-50 text-emerald-600"><CheckCircle2 className="h-5 w-5" /></div>
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-700">Verification complete</p>
                      <p className="mt-0.5 text-sm font-bold text-slate-900">{selectedDemoCase.company_name} · {selectedDemoCase.bid_id}</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">The verification run has produced an evidence-grounded result.</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-600"><Cpu className="h-3.5 w-3.5" />Run complete</div>
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
                  <div className={`rounded-lg border p-3 ${complianceTone === "emerald" ? "border-emerald-200 bg-emerald-50/70" : complianceTone === "rose" ? "border-rose-200 bg-rose-50/70" : "border-amber-200 bg-amber-50/70"}`}>
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Compliance</div>
                    <div className={`mt-1 text-sm font-black ${complianceTone === "emerald" ? "text-emerald-700" : complianceTone === "rose" ? "text-rose-700" : "text-amber-700"}`}>{completedVerification.compliance_status}</div>
                  </div>
                  <div className={`rounded-lg border p-3 ${integrityTone === "emerald" ? "border-emerald-200 bg-emerald-50/70" : "border-rose-200 bg-rose-50/70"}`}>
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Integrity</div>
                    <div className={`mt-1 text-sm font-black ${integrityTone === "emerald" ? "text-emerald-700" : "text-rose-700"}`}>{completedVerification.integrity_status}</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Requirements</div>
                    <div className="mt-1 text-sm font-black text-slate-900">{totalRequirements} evaluated</div>
                  </div>
                  <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                    <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Failures</div>
                    <div className="mt-1 text-sm font-black text-slate-900">{failedRequirements}</div>
                  </div>
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px]">
                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 font-semibold text-slate-600">Integrity findings: {integrityFindings}</span>
                  <span className={`rounded-full border px-2.5 py-1 font-semibold ${reviewRequired ? "border-amber-200 bg-amber-50 text-amber-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}>
                    {reviewRequired ? <><UserRound className="mr-1 inline h-3 w-3" />Officer review required · {reviewItems} item{reviewItems === 1 ? "" : "s"}</> : <>No officer review required</>}
                  </span>
                  {completedVerification.overall_status === "FAIL" && <span className="rounded-full border border-rose-200 bg-rose-50 px-2.5 py-1 font-semibold text-rose-800"><AlertTriangle className="mr-1 inline h-3 w-3" />Overall result: FAIL</span>}
                  {completedVerification.overall_status === "PASS" && <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 font-semibold text-emerald-800">Overall result: PASS</span>}
                </div>

                <div className="mt-4 flex items-center justify-end border-t border-slate-100 pt-3 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-500">
                  <span>Opening verification workbench...</span>
                  <ArrowRight className="ml-2 h-3.5 w-3.5" />
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-slate-300/80 bg-slate-100/80 p-5">
        <div className="mb-3 flex items-center justify-between gap-3"><div><h3 className="text-sm font-bold text-slate-900">Available Demonstration Submissions</h3><p className="mt-0.5 text-xs text-slate-600">Use a representative submission to walk through the complete local verification flow.</p></div><span className="rounded bg-blue-100 px-2 py-0.5 font-mono text-[11px] font-bold text-blue-700">LOCAL DEMO</span></div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {CANONICAL_DEMO_CASES.map((c) => {
            const isSelected = selectedDemoCase?.bid_id === c.bid_id;
            return <button key={c.bid_id} type="button" onClick={() => selectDemoCase(c)} className={`group flex items-start justify-between rounded-lg border p-3.5 text-left shadow-sm transition-all ${isSelected ? "border-blue-500 bg-blue-50 ring-1 ring-blue-400" : "border-slate-200 bg-white hover:border-blue-400 hover:bg-blue-50/30"}`}><div className="min-w-0"><div className="flex items-center gap-2"><span className="font-mono text-xs font-bold text-slate-800">{c.bid_id}</span><span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-bold text-slate-600">Submission</span></div><div className="mt-1 text-xs font-bold text-slate-900">{c.company_name}</div><div className="mt-0.5 line-clamp-2 text-[11px] text-slate-500">{c.description}</div></div>{isSelected ? <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-blue-600" /> : <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-slate-400 group-hover:text-blue-600" />}</button>;
          })}
        </div>
        <div className="mt-4 flex items-start gap-2 rounded border border-slate-200 bg-white/70 px-3 py-2.5 text-[10px] leading-4 text-slate-500"><Scale className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-400" /><span><strong className="text-slate-700">Local demo:</strong> uploaded bidder PDFs are matched to an available submission when the filename contains its BID identifier. The selected submission is then processed through the local verification flow.</span></div>
      </div>
    </div>
  );
};