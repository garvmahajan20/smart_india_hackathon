from dataclasses import dataclass, field as dc_field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Union

class SourceType(str, Enum):
    GTC = "GTC"
    STC = "STC"
    ATC = "ATC"
    BUYER_ADDED_SPECIFIC = "BUYER_ADDED_SPECIFIC"
    CORRIGENDUM = "CORRIGENDUM"
    CUSTOM = "CUSTOM"
    INFERRED = "INFERRED"
    UNSPECIFIED = "UNSPECIFIED"
    UNKNOWN = "UNKNOWN"

class ComplianceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    N_A = "N/A"
    REVIEW = "REVIEW"

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    INFO = "INFO"

class OperatorType(str, Enum):
    GTE = ">="
    LTE = "<="
    GT = ">"
    LT = "<"
    EQ = "=="
    NEQ = "!="
    IN = "IN"
    NOT_IN = "NOT_IN"
    CONTAINS = "CONTAINS"
    MATCHES = "MATCHES"
    EXISTS = "EXISTS"
    VALID_ON = "VALID_ON"
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    BETWEEN = "BETWEEN"

@dataclass
class EvidencePointer:
    document: str
    page: int
    bbox: Optional[List[float]] = None
    snippet: Optional[str] = None
    source_type: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        res: Dict[str, Any] = {"document": self.document, "page": self.page}
        if self.bbox is not None:
            res["bbox"] = self.bbox
        if self.snippet is not None:
            res["snippet"] = self.snippet
        if self.source_type is not None:
            res["source_type"] = self.source_type
        return res

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidencePointer":
        return cls(
            document=data.get("document", "UNKNOWN"),
            page=data.get("page", 1),
            bbox=data.get("bbox"),
            snippet=data.get("snippet"),
            source_type=data.get("source_type")
        )

@dataclass
class TenderRequirement:
    requirement_id: str
    tender_id: str
    category: str
    description: str
    operator: str
    mandatory: bool = True
    field: Optional[str] = None
    expected_value: Any = None
    normalized_expected_value: Any = None
    unit: Optional[str] = None
    source_type: str = SourceType.UNSPECIFIED.value
    source_clause: Optional[str] = None
    source_page: Optional[int] = 1
    source_priority: int = 0
    applicability: Dict[str, Any] = dc_field(default_factory=dict)
    evidence: List[Dict[str, Any]] = dc_field(default_factory=list)
    extraction_confidence: str = "HIGH"
    # Precedence resolution annotations
    is_effective: bool = True
    superseded_by: Optional[str] = None
    supersedes: Optional[str] = None
    precedence_notes: Optional[str] = None
    canonical_field: Optional[str] = None
    field_resolution: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.field_resolution is None and self.field:
            from .ontology import resolve_field
            res = resolve_field(self.field)
            if self.canonical_field is None:
                self.canonical_field = res.canonical_field_id
            self.field_resolution = res.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "requirement_id": self.requirement_id,
            "tender_id": self.tender_id,
            "category": self.category,
            "description": self.description,
            "operator": self.operator,
            "mandatory": self.mandatory,
            "source_type": self.source_type,
            "source_priority": self.source_priority,
            "extraction_confidence": self.extraction_confidence,
        }
        if self.field is not None:
            d["field"] = self.field
        if self.expected_value is not None:
            d["expected_value"] = self.expected_value
        if self.normalized_expected_value is not None:
            d["normalized_expected_value"] = self.normalized_expected_value
        if self.unit is not None:
            d["unit"] = self.unit
        if self.source_clause is not None:
            d["source_clause"] = self.source_clause
        if self.source_page is not None:
            d["source_page"] = self.source_page
        if self.applicability:
            d["applicability"] = self.applicability
        if self.evidence:
            d["evidence"] = self.evidence
        if self.canonical_field is not None:
            d["canonical_field"] = self.canonical_field
        if self.field_resolution is not None:
            d["field_resolution"] = self.field_resolution
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TenderRequirement":
        return cls(
            requirement_id=data["requirement_id"],
            tender_id=data["tender_id"],
            category=data["category"],
            description=data["description"],
            operator=data["operator"],
            mandatory=data.get("mandatory", True),
            field=data.get("field"),
            expected_value=data.get("expected_value"),
            normalized_expected_value=data.get("normalized_expected_value"),
            unit=data.get("unit"),
            source_type=data.get("source_type", SourceType.UNSPECIFIED.value),
            source_clause=data.get("source_clause"),
            source_page=data.get("source_page", 1),
            source_priority=data.get("source_priority", 0),
            applicability=data.get("applicability", {}),
            evidence=data.get("evidence", []),
            extraction_confidence=data.get("extraction_confidence", "HIGH"),
            canonical_field=data.get("canonical_field"),
            field_resolution=data.get("field_resolution"),
        )

@dataclass
class BidderFact:
    fact_id: str
    bid_id: str
    field: str
    value: Any
    source_document: str
    page: int
    extraction_confidence: str = "HIGH"
    bidder_id: Optional[str] = None
    normalized_value: Any = None
    unit: Optional[str] = None
    bbox: Optional[List[float]] = None
    raw_text_snippet: Optional[str] = None
    extraction_method: str = "LLM_STRUCTURED_EXTRACTION"
    evidence: List[Dict[str, Any]] = dc_field(default_factory=list)
    metadata: Dict[str, Any] = dc_field(default_factory=dict)
    canonical_field: Optional[str] = None
    field_resolution: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.field_resolution is None and self.field:
            from .ontology import resolve_field
            res = resolve_field(self.field)
            if self.canonical_field is None:
                self.canonical_field = res.canonical_field_id
            self.field_resolution = res.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "fact_id": self.fact_id,
            "bid_id": self.bid_id,
            "field": self.field,
            "value": self.value,
            "source_document": self.source_document,
            "page": self.page,
            "extraction_confidence": self.extraction_confidence,
            "extraction_method": self.extraction_method,
        }
        if self.bidder_id is not None:
            d["bidder_id"] = self.bidder_id
        if self.normalized_value is not None:
            d["normalized_value"] = self.normalized_value
        if self.unit is not None:
            d["unit"] = self.unit
        if self.bbox is not None:
            d["bbox"] = self.bbox
        if self.raw_text_snippet is not None:
            d["raw_text_snippet"] = self.raw_text_snippet
        if self.evidence:
            d["evidence"] = self.evidence
        if self.metadata:
            d["metadata"] = self.metadata
        if self.canonical_field is not None:
            d["canonical_field"] = self.canonical_field
        if self.field_resolution is not None:
            d["field_resolution"] = self.field_resolution
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BidderFact":
        return cls(
            fact_id=data["fact_id"],
            bid_id=data["bid_id"],
            field=data["field"],
            value=data["value"],
            source_document=data["source_document"],
            page=data["page"],
            extraction_confidence=data.get("extraction_confidence", "HIGH"),
            bidder_id=data.get("bidder_id"),
            normalized_value=data.get("normalized_value"),
            unit=data.get("unit"),
            bbox=data.get("bbox"),
            raw_text_snippet=data.get("raw_text_snippet"),
            extraction_method=data.get("extraction_method", "LLM_STRUCTURED_EXTRACTION"),
            evidence=data.get("evidence", []),
            metadata=data.get("metadata", {}),
            canonical_field=data.get("canonical_field"),
            field_resolution=data.get("field_resolution"),
        )

@dataclass
class VerificationResult:
    verification_id: str
    requirement_id: str
    bid_id: str
    status: str
    severity: str
    expected: Any
    actual: Any
    operator_used: str
    reason: str
    requires_human_review: bool
    fact_id: Optional[str] = None
    evidence: List[Dict[str, Any]] = dc_field(default_factory=list)
    anomaly_refs: List[str] = dc_field(default_factory=list)
    officer_override: Optional[Dict[str, Any]] = None
    precedence_chain: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        ev_list = [e.to_dict() if hasattr(e, "to_dict") else e for e in self.evidence]
        d = {
            "verification_id": self.verification_id,
            "requirement_id": self.requirement_id,
            "bid_id": self.bid_id,
            "status": self.status,
            "severity": self.severity,
            "expected": self.expected,
            "actual": self.actual,
            "operator_used": self.operator_used,
            "reason": self.reason,
            "evidence": ev_list,
            "requires_human_review": self.requires_human_review,
        }
        if self.fact_id is not None:
            d["fact_id"] = self.fact_id
        if self.anomaly_refs:
            d["anomaly_refs"] = self.anomaly_refs
        if self.officer_override is not None:
            d["officer_override"] = self.officer_override
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        return cls(
            verification_id=data["verification_id"],
            requirement_id=data["requirement_id"],
            bid_id=data["bid_id"],
            status=data["status"],
            severity=data.get("severity", Severity.INFO.value),
            expected=data.get("expected"),
            actual=data.get("actual"),
            operator_used=data.get("operator_used", ""),
            reason=data.get("reason", ""),
            requires_human_review=data.get("requires_human_review", False),
            fact_id=data.get("fact_id"),
            evidence=data.get("evidence", []),
            anomaly_refs=data.get("anomaly_refs", []),
            officer_override=data.get("officer_override"),
            precedence_chain=data.get("precedence_chain"),
        )
