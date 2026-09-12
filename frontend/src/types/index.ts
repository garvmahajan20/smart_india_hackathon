// Canonical domain types matching backend contracts strictly

export type ComplianceStatus = "PASS" | "FAIL" | "PARTIAL" | "MISSING" | "REVIEW";

export type IntegrityStatus = "CONSISTENT" | "CONTRADICTION" | "REVIEW" | "INCOMPLETE";

export type OverallStatus = "PASS" | "FAIL" | "REVIEW";

export type Severity = "CRITICAL" | "MAJOR" | "MEDIUM" | "LOW" | "INFO";

export type ReviewCategory =
  | "MISSING_EVIDENCE"
  | "GROUNDING_FAILURE"
  | "INTEGRITY_CONTRADICTION"
  | "GOVERNMENT_MISMATCH"
  | "AMBIGUOUS_COMPLIANCE"
  | "DEBARMENT_ALERT"
  | "MANUAL_INSPECTION";

export type ReviewItemStatus = "OPEN" | "RESOLVED" | "DISMISSED";

export interface EvidencePointer {
  document: string;
  page: number;
  block_id?: string;
  bbox?: [number, number, number, number]; // [ymin, xmin, ymax, xmax]
  snippet?: string;
  source_type?: string;
}

export interface VerificationResult {
  verification_id: string;
  requirement_id: string;
  bid_id: string;
  fact_id?: string;
  status: ComplianceStatus;
  severity: Severity;
  expected: string | number;
  actual: string;
  operator_used: string;
  reason: string;
  requires_human_review: boolean;
  evidence: EvidencePointer[];
  anomaly_refs?: string[];
  precedence_chain?: {
    status: string;
    superseded_by?: string;
    source_type?: string;
    source_priority?: number;
  };
}

export interface IntegrityFinding {
  finding_id: string;
  bid_id: string;
  field: string;
  status: IntegrityStatus;
  severity: string; // HIGH, MEDIUM, LOW
  description: string;
  evidence_a: Record<string, any>;
  evidence_b: Record<string, any>;
  requires_human_review: boolean;
  hint?: string;
}

export interface GovernmentCheck {
  status: string;
  adapter_name: string;
  queried_identifier: string;
  source: string;
  reason: string;
  is_mock: boolean;
  matched_entity?: Record<string, any>;
}

export interface HumanReviewItem {
  review_id: string;
  bid_id: string;
  tender_id: string;
  category: ReviewCategory | string;
  severity: Severity | string;
  reason: string;
  evidence_references: any[];
  source_documents: string[];
  source_pages: number[];
  related_verification_id?: string | null;
  created_at: string;
  status: ReviewItemStatus | string;
}

export interface ProcessingMetadata {
  debarred?: boolean;
  debarment_reason?: string | null;
  total_compliance_checks?: number;
  passed_compliance_checks?: number;
  contradiction_findings?: number;
  government_checks_run?: number;
  extraction_mode?: string;
  active_model?: string;
}

export interface AggregatedVerification {
  verification_id: string;
  tender_id: string;
  bid_id: string;
  overall_status: OverallStatus;
  compliance_status: ComplianceStatus;
  integrity_status: IntegrityStatus;
  verification_results: VerificationResult[];
  critical_failures: number;
  major_failures: number;
  review_required: boolean;
  evidence_count: number;
  anomaly_count: number;
  government_checks: GovernmentCheck[];
  contradictions: IntegrityFinding[];
  human_review_items: HumanReviewItem[];
  generated_at: string;
  deterministic_run_id: string; // Run ID identifier (not cryptographic seal)
  processing_metadata: ProcessingMetadata;
  compliance_score?: number;
  compliance_score_breakdown?: Record<string, any>;
  risk_level?: string;
  risk_assessment?: Record<string, any>;
  recommendation?: Record<string, any>;
  pending_requirements?: Record<string, any>[];
  adjudications?: Record<string, any>[];
}

export interface VerificationDossier {
  tender: {
    tender_id: string;
    requirements_count?: number;
    requirements: any[];
  };
  bidder: {
    bid_id: string;
    legal_name?: string;
    extracted_facts_count?: number;
    facts: any[];
  };
  compliance_summary: {
    compliance_status: ComplianceStatus;
    overall_status: OverallStatus;
    critical_failures: number;
    major_failures: number;
    total_requirements: number;
  };
  integrity_summary: {
    integrity_status: IntegrityStatus;
    contradictions_count: number;
    anomalies_count: number;
  };
  verification_results: VerificationResult[];
  government_checks: GovernmentCheck[];
  evidence: any[];
  anomalies: any[];
  human_review_items: HumanReviewItem[];
  audit_metadata: {
    verification_id: string;
    deterministic_run_id: string;
    generated_at: string;
    processing_time_ms?: number;
    active_model?: string;
    extraction_mode?: string;
  };
  provenance_graph?: Record<string, any>;
  compliance_score?: Record<string, any>;
  risk_assessment?: Record<string, any>;
  recommendation?: Record<string, any>;
  pending_requirements?: Record<string, any>[];
  adjudications?: Record<string, any>[];
}

export interface HealthResponse {
  status: string;
  version: string;
  active_model: string;
  mode: string;
}

// Canonical Demo Bid Case (Local Demo Metadata)
export interface DemoBidCase {
  bid_id: string;
  tender_id: string;
  company_name: string;
  ground_truth_label: "CLEAN" | "NON_COMPLIANT" | "UNCERTAIN" | "MANIPULATED";
  description: string;
  expected_overall: OverallStatus;
  expected_compliance: ComplianceStatus;
  expected_integrity: IntegrityStatus;
  highlights: string[];
}
