# -*- coding: utf-8 -*-
"""
Phase 10B.6 Evaluation Data Models.

Provides structured, deterministic, and serializable data models for
comprehensive dataset-wide verification benchmarking and failure analysis.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def canonical_json_str(data: Any) -> str:
    """Produces deterministic, byte-for-byte reproducible JSON string."""
    return json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=True, default=str)


def compute_model_hash(data: Any) -> str:
    """Computes SHA-256 hash over canonical JSON representation."""
    return hashlib.sha256(canonical_json_str(data).encode('utf-8')).hexdigest()


@dataclass
class EvaluationCase:
    """Detailed record of an individual evaluated item (clause, bid, contradiction, etc.)."""
    case_id: str
    case_type: str  # 'REQUIREMENT', 'BID', 'CONTRADICTION', 'ANOMALY', 'REPLAY'
    entity_id: str
    field: str
    expected_status: str
    predicted_status: str
    is_match: bool
    requires_human_review: bool
    error_category: Optional[str] = None
    severity: str = 'INFO'  # 'CRITICAL', 'MAJOR', 'MINOR', 'INFO'
    evidence_provenance: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RequirementMetrics:
    """Requirement-level classification and compliance metrics."""
    total_evaluated: int = 0
    tp: int = 0
    tn: int = 0
    fp: int = 0
    fn: int = 0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    specificity: float = 0.0
    false_pass_rate: float = 0.0
    false_fail_rate: float = 0.0
    safe_abstention_rate: float = 0.0
    review_escape_rate: float = 0.0
    pass_matches: int = 0
    fail_matches: int = 0
    partial_matches: int = 0
    missing_matches: int = 0
    review_cases: int = 0
    confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    per_status_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    field_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BidMetrics:
    """Bid-level compliance and verification metrics."""
    total_bids: int = 0
    correct_bids: int = 0
    incorrect_bids: int = 0
    accuracy: float = 0.0
    false_pass_bids: int = 0
    false_fail_bids: int = 0
    review_required_bids: int = 0
    correctly_reviewed_bids: int = 0
    review_escape_bids: int = 0
    bid_confusion_matrix: Dict[str, Dict[str, int]] = field(default_factory=dict)
    difficulty_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    ranked_failures: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ContradictionMetrics:
    """Cross-document contradiction evaluation metrics."""
    total_cases: int = 0
    exact_matches: int = 0
    mismatches: int = 0
    exact_match_rate: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    detected_contradictions: int = 0
    correct_consistent: int = 0
    false_contradictions: int = 0
    missed_contradictions: int = 0
    type_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnomalyMetrics:
    """Dataset anomaly mapping and coverage metrics."""
    total_anomalies: int = 0
    mapped_correctly: int = 0
    unmapped: int = 0
    incorrectly_mapped: int = 0
    duplicate_mappings: int = 0
    orphan_mappings: int = 0
    type_breakdown: Dict[str, int] = field(default_factory=dict)
    component_breakdown: Dict[str, int] = field(default_factory=dict)
    severity_breakdown: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceMetrics:
    """Physical evidence grounding and multi-block preservation metrics."""
    total_grounded_facts: int = 0
    supported_facts: int = 0
    unsupported_facts: int = 0
    missing_evidence_facts: int = 0
    multi_block_facts: int = 0
    multi_document_facts: int = 0
    grounding_precision: float = 0.0
    grounding_recall: float = 0.0
    unsupported_claim_rejection_rate: float = 0.0
    false_supported_claim_rate: float = 0.0
    false_evidence_support_rate: float = 0.0
    block_preservation_rate: float = 1.0
    bbox_preservation_rate: float = 1.0
    document_preservation_rate: float = 1.0
    snippet_preservation_rate: float = 1.0
    multi_block_completeness: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceMetrics:
    """Provenance DAG dataset-wide structural audit metrics."""
    total_dags_audited: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    avg_nodes_per_bid: float = 0.0
    avg_edges_per_bid: float = 0.0
    node_type_counts: Dict[str, int] = field(default_factory=dict)
    edge_type_counts: Dict[str, int] = field(default_factory=dict)
    provenance_completeness_rate: float = 1.0
    evidence_to_decision_traceability_rate: float = 1.0
    decision_to_evidence_traceability_rate: float = 1.0
    orphan_node_count: int = 0
    orphan_node_rate: float = 0.0
    phantom_edge_count: int = 0
    phantom_edge_rate: float = 0.0
    cycle_count: int = 0
    cycle_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayMetrics:
    """Deterministic snapshot replay metrics."""
    total_replay_cases: int = 0
    complete_match_count: int = 0
    mismatch_count: int = 0
    invalid_snapshot_count: int = 0
    configuration_mismatch_count: int = 0
    provenance_mismatch_count: int = 0
    aggregation_mismatch_count: int = 0
    verification_mismatch_count: int = 0
    replay_match_rate: float = 1.0
    repeat_determinism_runs: int = 0
    repeat_determinism_cases: int = 0
    deterministic_replay_rate: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailureAnalysis:
    """Taxonomy and severity analysis of false decisions and safe abstentions."""
    severity_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)
    error_taxonomy: Dict[str, int] = field(default_factory=dict)
    false_pass_cases: List[Dict[str, Any]] = field(default_factory=list)
    false_fail_cases: List[Dict[str, Any]] = field(default_factory=list)
    safe_abstention_cases: List[Dict[str, Any]] = field(default_factory=list)
    root_cause_summaries: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DatasetMetrics:
    """Overall dataset card and cardinality metrics."""
    dataset_id: str
    dataset_version: str
    source_identifier: str
    tender_count: int
    bid_count: int
    entity_count: int
    requirement_count: int
    bidder_fact_count: int
    evidence_block_count: int
    contradiction_count: int
    anomaly_count: int
    clause_count: int
    ground_truth_count: int
    dataset_hashes: Dict[str, Dict[str, Any]]
    manifest_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationRun:
    """Complete evaluation run container."""
    evaluation_version: str
    dataset_version: str
    engine_versions: Dict[str, str]
    dataset_hashes: Dict[str, Dict[str, Any]]
    configuration_hash: str
    run_hash: str = ''
    timestamp: str = ''
    dataset_metrics: Optional[DatasetMetrics] = None
    requirement_metrics: Optional[RequirementMetrics] = None
    bid_metrics: Optional[BidMetrics] = None
    contradiction_metrics: Optional[ContradictionMetrics] = None
    anomaly_metrics: Optional[AnomalyMetrics] = None
    evidence_metrics: Optional[EvidenceMetrics] = None
    provenance_metrics: Optional[ProvenanceMetrics] = None
    replay_metrics: Optional[ReplayMetrics] = None
    failure_analysis: Optional[FailureAnalysis] = None
    global_invariants: Dict[str, bool] = field(default_factory=dict)
    performance: Dict[str, Any] = field(default_factory=dict)

    def finalize_hash(self) -> str:
        """Computes and assigns run_hash based on all canonical contents."""
        d = self.to_dict()
        d['run_hash'] = ''
        self.run_hash = compute_model_hash(d)
        return self.run_hash

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
