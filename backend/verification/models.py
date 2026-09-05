# -*- coding: utf-8 -*-
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_FOUND = "NOT_FOUND"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    INACTIVE = "INACTIVE"
    DEBARRED = "DEBARRED"
    NOT_DEBARRED = "NOT_DEBARRED"
    REVIEW = "REVIEW"
    UNVERIFIED = "UNVERIFIED"

@dataclass
class AdapterResponse:
    """
    Standardized response returned by all Government Verification Adapters.
    Designed for seamless swap-in: mock adapters and future live APIs adhere to this identical contract.
    """
    status: VerificationStatus
    adapter_name: str
    queried_identifier: str
    source: str
    reason: str
    matched_entity: Optional[Dict[str, Any]] = None
    registered_entity_name: Optional[str] = None
    registration_status: Optional[str] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: Optional[str] = None
    is_mock: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "adapter_name": self.adapter_name,
            "queried_identifier": self.queried_identifier,
            "source": self.source,
            "reason": self.reason,
            "matched_entity": self.matched_entity,
            "registered_entity_name": self.registered_entity_name,
            "registration_status": self.registration_status,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
            "is_mock": self.is_mock,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdapterResponse":
        return cls(
            status=VerificationStatus(data["status"]),
            adapter_name=data["adapter_name"],
            queried_identifier=data["queried_identifier"],
            source=data["source"],
            reason=data.get("reason", ""),
            matched_entity=data.get("matched_entity"),
            registered_entity_name=data.get("registered_entity_name"),
            registration_status=data.get("registration_status"),
            evidence=data.get("evidence", []),
            timestamp=data.get("timestamp"),
            is_mock=data.get("is_mock", True),
        )

@dataclass
class IntegrityFinding:
    """
    Represents an integrity anomaly or cross-document consistency finding.
    Distinct from compliance: integrity findings evaluate truthfulness,
    consistency, and tampering suspicions without mutating deterministic compliance PASS/FAIL.
    """
    finding_id: str
    bid_id: str
    finding_type: str
    field: str
    severity: str
    status: str
    description: str
    value_a: Any
    value_b: Any
    evidence_a: Dict[str, Any]
    evidence_b: Dict[str, Any]
    requires_human_review: bool
    source: str = "CROSS_DOCUMENT_CONTRADICTION_ENGINE"
    raw_field_a: Optional[str] = None
    raw_field_b: Optional[str] = None
    canonical_field: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "finding_id": self.finding_id,
            "bid_id": self.bid_id,
            "finding_type": self.finding_type,
            "field": self.field,
            "severity": self.severity,
            "status": self.status,
            "description": self.description,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "evidence_a": self.evidence_a,
            "evidence_b": self.evidence_b,
            "requires_human_review": self.requires_human_review,
            "source": self.source,
        }
        if self.raw_field_a is not None:
            d["raw_field_a"] = self.raw_field_a
        if self.raw_field_b is not None:
            d["raw_field_b"] = self.raw_field_b
        if self.canonical_field is not None:
            d["canonical_field"] = self.canonical_field
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntegrityFinding":
        return cls(
            finding_id=data["finding_id"],
            bid_id=data["bid_id"],
            finding_type=data["finding_type"],
            field=data["field"],
            severity=data["severity"],
            status=data["status"],
            description=data["description"],
            value_a=data.get("value_a"),
            value_b=data.get("value_b"),
            evidence_a=data.get("evidence_a", {}),
            evidence_b=data.get("evidence_b", {}),
            requires_human_review=data.get("requires_human_review", True),
            source=data.get("source", "CROSS_DOCUMENT_CONTRADICTION_ENGINE"),
            raw_field_a=data.get("raw_field_a"),
            raw_field_b=data.get("raw_field_b"),
            canonical_field=data.get("canonical_field"),
        )
