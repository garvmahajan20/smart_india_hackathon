# -*- coding: utf-8 -*-
from dataclasses import asdict, dataclass
import dataclasses as dc
from enum import Enum
import time
from typing import Any, Dict, List, Optional

class OverallStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"

class ComplianceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    REVIEW = "REVIEW"

class IntegrityStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    CONTRADICTION = "CONTRADICTION"
    REVIEW = "REVIEW"
    INCOMPLETE = "INCOMPLETE"

class ReviewItemStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

class ReviewCategory(str, Enum):
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    GROUNDING_FAILURE = "GROUNDING_FAILURE"
    INTEGRITY_CONTRADICTION = "INTEGRITY_CONTRADICTION"
    GOVERNMENT_MISMATCH = "GOVERNMENT_MISMATCH"
    AMBIGUOUS_COMPLIANCE = "AMBIGUOUS_COMPLIANCE"
    DEBARMENT_ALERT = "DEBARMENT_ALERT"
    MANUAL_INSPECTION = "MANUAL_INSPECTION"

@dataclass
class HumanReviewItem:
    review_id: str
    bid_id: str
    tender_id: str
    category: str
    severity: str  # CRITICAL, MAJOR, MEDIUM, LOW, INFO
    reason: str
    evidence_references: List[Dict[str, Any]] = dc.field(default_factory=list)
    source_documents: List[str] = dc.field(default_factory=list)
    source_pages: List[int] = dc.field(default_factory=list)
    related_verification_id: Optional[str] = None
    created_at: str = dc.field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    status: str = ReviewItemStatus.OPEN.value

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HumanReviewItem":
        return cls(**data)

@dataclass
class AggregatedVerification:
    verification_id: str
    tender_id: str
    bid_id: str
    overall_status: str        # PASS, FAIL, REVIEW
    compliance_status: str     # PASS, FAIL, PARTIAL, MISSING, REVIEW
    integrity_status: str      # CONSISTENT, CONTRADICTION, REVIEW, INCOMPLETE
    verification_results: List[Dict[str, Any]] = dc.field(default_factory=list)
    critical_failures: int = 0
    major_failures: int = 0
    review_required: bool = False
    evidence_count: int = 0
    anomaly_count: int = 0
    government_checks: List[Dict[str, Any]] = dc.field(default_factory=list)
    contradictions: List[Dict[str, Any]] = dc.field(default_factory=list)
    human_review_items: List[Dict[str, Any]] = dc.field(default_factory=list)
    generated_at: str = dc.field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    deterministic_run_id: str = ""
    processing_metadata: Dict[str, Any] = dc.field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AggregatedVerification":
        return cls(**data)

@dataclass
class VerificationDossier:
    tender: Dict[str, Any]
    bidder: Dict[str, Any]
    compliance_summary: Dict[str, Any]
    integrity_summary: Dict[str, Any]
    verification_results: List[Dict[str, Any]]
    government_checks: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    human_review_items: List[Dict[str, Any]]
    audit_metadata: Dict[str, Any]
    provenance_graph: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationDossier":
        return cls(**data)
