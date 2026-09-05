# -*- coding: utf-8 -*-
"""
Deterministic Audit Snapshot Model & Canonical Serialization.
Phase 10B.4: Core reproducibility data structure.

The audit snapshot captures the complete, grounded, deterministic verification state
required to independently reproduce and verify compliance decisions, integrity findings,
and provenance graphs without probabilistic extraction, external APIs, or network access.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field as dc_field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

SNAPSHOT_VERSION = "1.0.0"
REPLAY_ENGINE_VERSION = "1.0.0"
SUPPORTED_SNAPSHOT_VERSIONS = {"1.0.0"}


@dataclass(frozen=True)
class DeterministicConfig:
    """
    Immutable deterministic configuration fingerprint.
    Defines the exact algorithmic versions and policies governing verification.
    """
    rule_engine_version: str = "1.0.0"
    contradiction_engine_version: str = "1.0.0"
    aggregator_version: str = "1.0.0"
    ontology_version: str = "1.0.0"
    precedence_policy: str = "GTC_STC_ATC"
    default_evaluation_date: str = "2026-09-01"
    replay_engine_version: str = REPLAY_ENGINE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_engine_version": self.rule_engine_version,
            "contradiction_engine_version": self.contradiction_engine_version,
            "aggregator_version": self.aggregator_version,
            "ontology_version": self.ontology_version,
            "precedence_policy": self.precedence_policy,
            "default_evaluation_date": self.default_evaluation_date,
            "replay_engine_version": self.replay_engine_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeterministicConfig":
        return cls(
            rule_engine_version=data.get("rule_engine_version", "1.0.0"),
            contradiction_engine_version=data.get("contradiction_engine_version", "1.0.0"),
            aggregator_version=data.get("aggregator_version", "1.0.0"),
            ontology_version=data.get("ontology_version", "1.0.0"),
            precedence_policy=data.get("precedence_policy", "GTC_STC_ATC"),
            default_evaluation_date=data.get("default_evaluation_date", "2026-09-01"),
            replay_engine_version=data.get("replay_engine_version", REPLAY_ENGINE_VERSION),
        )


def canonicalize_value(val: Any) -> Any:
    """Recursively normalizes data structures for deterministic serialization."""
    if isinstance(val, dict):
        # Sort dictionary keys alphabetically
        return {k: canonicalize_value(val[k]) for k in sorted(val.keys())}
    elif isinstance(val, (list, tuple)):
        # Normalize list elements
        return [canonicalize_value(x) for x in val]
    elif isinstance(val, float):
        # Round floats to 6 decimal places to prevent platform precision drift
        return round(val, 6)
    return val


def canonical_json(data: Any, indent: Optional[int] = None) -> str:
    """Produces byte-for-byte deterministic JSON serialization."""
    normalized = canonicalize_value(data)
    if indent is not None:
        return json.dumps(
            normalized,
            sort_keys=True,
            indent=indent,
            ensure_ascii=False,
            separators=(", ", ": "),
        )
    return json.dumps(
        normalized,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def compute_config_hash(config_dict: Dict[str, Any]) -> str:
    """Computes SHA-256 fingerprint for deterministic configuration."""
    clean_dict = {
        "rule_engine_version": str(config_dict.get("rule_engine_version", "")),
        "contradiction_engine_version": str(config_dict.get("contradiction_engine_version", "")),
        "aggregator_version": str(config_dict.get("aggregator_version", "")),
        "ontology_version": str(config_dict.get("ontology_version", "")),
        "precedence_policy": str(config_dict.get("precedence_policy", "")),
        "default_evaluation_date": str(config_dict.get("default_evaluation_date", "")),
        "replay_engine_version": str(config_dict.get("replay_engine_version", "")),
    }
    raw = canonical_json(clean_dict)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_snapshot_hash(snapshot_dict: Dict[str, Any]) -> str:
    """
    Computes a canonical cryptographic SHA-256 hash of the audit snapshot.
    Excludes the 'snapshot_hash' field itself to eliminate self-referential cycles.
    """
    copy_dict = dict(snapshot_dict)
    copy_dict.pop("snapshot_hash", None)

    # Sort key entity lists by deterministic primary identifiers
    if "requirements" in copy_dict and isinstance(copy_dict["requirements"], list):
        copy_dict["requirements"] = sorted(
            copy_dict["requirements"],
            key=lambda x: str(x.get("requirement_id", "")),
        )

    if "bidder_facts" in copy_dict and isinstance(copy_dict["bidder_facts"], list):
        copy_dict["bidder_facts"] = sorted(
            copy_dict["bidder_facts"],
            key=lambda x: str(x.get("fact_id", "")),
        )

    if "captured_government_responses" in copy_dict and isinstance(copy_dict["captured_government_responses"], list):
        copy_dict["captured_government_responses"] = sorted(
            copy_dict["captured_government_responses"],
            key=lambda x: f"{x.get('adapter_name', '')}:{x.get('queried_identifier', '')}",
        )

    if "contradiction_inputs" in copy_dict and isinstance(copy_dict["contradiction_inputs"], list):
        copy_dict["contradiction_inputs"] = sorted(
            copy_dict["contradiction_inputs"],
            key=lambda x: str(x.get("contradiction_id", "")),
        )

    if "original_results" in copy_dict and isinstance(copy_dict["original_results"], dict):
        orig = dict(copy_dict["original_results"])
        if "compliance_results" in orig and isinstance(orig["compliance_results"], list):
            orig["compliance_results"] = sorted(
                orig["compliance_results"],
                key=lambda x: str(x.get("verification_id", "")),
            )
        if "integrity_findings" in orig and isinstance(orig["integrity_findings"], list):
            orig["integrity_findings"] = sorted(
                orig["integrity_findings"],
                key=lambda x: str(x.get("finding_id", "")),
            )
        if "human_review_items" in orig and isinstance(orig["human_review_items"], list):
            orig["human_review_items"] = sorted(
                orig["human_review_items"],
                key=lambda x: str(x.get("review_id", "")),
            )
        copy_dict["original_results"] = orig

    raw_json = canonical_json(copy_dict)
    return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


@dataclass
class AuditSnapshot:
    """
    Complete, self-contained, versioned deterministic audit snapshot.
    """
    snapshot_version: str
    replay_engine_version: str
    snapshot_id: str
    tender_id: str
    bid_id: str
    requirements: List[Dict[str, Any]]
    bidder_facts: List[Dict[str, Any]]
    captured_government_responses: List[Dict[str, Any]]
    contradiction_inputs: List[Dict[str, Any]]
    tender_metadata: Dict[str, Any]
    evaluation_date: Optional[str]
    deterministic_config: Dict[str, Any]
    verification_config_hash: str
    original_results: Dict[str, Any]
    snapshot_hash: str = ""

    def __post_init__(self):
        if not self.snapshot_hash:
            self.snapshot_hash = compute_snapshot_hash(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_version": self.snapshot_version,
            "replay_engine_version": self.replay_engine_version,
            "snapshot_id": self.snapshot_id,
            "tender_id": self.tender_id,
            "bid_id": self.bid_id,
            "requirements": self.requirements,
            "bidder_facts": self.bidder_facts,
            "captured_government_responses": self.captured_government_responses,
            "contradiction_inputs": self.contradiction_inputs,
            "tender_metadata": self.tender_metadata,
            "evaluation_date": self.evaluation_date,
            "deterministic_config": self.deterministic_config,
            "verification_config_hash": self.verification_config_hash,
            "original_results": self.original_results,
            "snapshot_hash": self.snapshot_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return canonical_json(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditSnapshot":
        return cls(
            snapshot_version=data["snapshot_version"],
            replay_engine_version=data.get("replay_engine_version", REPLAY_ENGINE_VERSION),
            snapshot_id=data["snapshot_id"],
            tender_id=data["tender_id"],
            bid_id=data["bid_id"],
            requirements=data.get("requirements", []),
            bidder_facts=data.get("bidder_facts", []),
            captured_government_responses=data.get("captured_government_responses", []),
            contradiction_inputs=data.get("contradiction_inputs", []),
            tender_metadata=data.get("tender_metadata", {}),
            evaluation_date=data.get("evaluation_date"),
            deterministic_config=data.get("deterministic_config", {}),
            verification_config_hash=data.get("verification_config_hash", ""),
            original_results=data.get("original_results", {}),
            snapshot_hash=data.get("snapshot_hash", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "AuditSnapshot":
        data = json.loads(json_str)
        return cls.from_dict(data)


def validate_snapshot_dict(data: Dict[str, Any]) -> List[str]:
    """
    Performs comprehensive structural validation on an audit snapshot dictionary.
    Returns a list of error strings. If empty, the snapshot is structurally valid.
    """
    errors: List[str] = []

    # 1. Top-level required fields
    required_fields = [
        "snapshot_version",
        "snapshot_id",
        "tender_id",
        "bid_id",
        "requirements",
        "bidder_facts",
        "captured_government_responses",
        "deterministic_config",
        "verification_config_hash",
        "original_results",
        "snapshot_hash",
    ]
    for rf in required_fields:
        if rf not in data or data[rf] is None:
            errors.append(f"Missing required field '{rf}' in audit snapshot.")

    if errors:
        return errors

    # 2. Version validation
    ver = data.get("snapshot_version")
    if ver not in SUPPORTED_SNAPSHOT_VERSIONS:
        errors.append(
            f"Unsupported snapshot_version '{ver}'. Supported versions: {sorted(list(SUPPORTED_SNAPSHOT_VERSIONS))}"
        )

    # 3. ID format & non-emptiness
    bid_id = str(data.get("bid_id", "")).strip()
    tender_id = str(data.get("tender_id", "")).strip()
    if not bid_id:
        errors.append("Empty or missing 'bid_id'.")
    if not tender_id:
        errors.append("Empty or missing 'tender_id'.")

    # 4. Requirements validation
    reqs = data.get("requirements", [])
    if not isinstance(reqs, list):
        errors.append("'requirements' must be a list.")
    else:
        for idx, r in enumerate(reqs):
            if not isinstance(r, dict):
                errors.append(f"Requirement at index {idx} must be a dictionary.")
                continue
            if not r.get("requirement_id"):
                errors.append(f"Requirement at index {idx} missing 'requirement_id'.")
            if not r.get("operator"):
                errors.append(f"Requirement '{r.get('requirement_id', idx)}' missing 'operator'.")

    # 5. Bidder facts validation
    facts = data.get("bidder_facts", [])
    if not isinstance(facts, list):
        errors.append("'bidder_facts' must be a list.")
    else:
        for idx, f in enumerate(facts):
            if not isinstance(f, dict):
                errors.append(f"Bidder fact at index {idx} must be a dictionary.")
                continue
            if not f.get("fact_id"):
                errors.append(f"Bidder fact at index {idx} missing 'fact_id'.")
            if not f.get("field"):
                errors.append(f"Bidder fact '{f.get('fact_id', idx)}' missing 'field'.")
            if not f.get("source_document"):
                errors.append(f"Bidder fact '{f.get('fact_id', idx)}' missing 'source_document'.")

    # 6. Original results validation
    orig = data.get("original_results")
    if not isinstance(orig, dict):
        errors.append("'original_results' must be a dictionary.")
    else:
        orig_required = [
            "compliance_results",
            "integrity_findings",
            "compliance_status",
            "integrity_status",
            "overall_status",
            "provenance_graph",
        ]
        for orf in orig_required:
            if orf not in orig:
                errors.append(f"Missing '{orf}' inside 'original_results'.")

        # Provenance graph must have nodes and edges
        p_graph = orig.get("provenance_graph")
        if not isinstance(p_graph, dict):
            errors.append("'provenance_graph' inside 'original_results' must be a dictionary.")
        else:
            if "nodes" not in p_graph or not isinstance(p_graph["nodes"], (dict, list)):
                errors.append("Invalid or missing 'nodes' in provenance_graph.")
            if "edges" not in p_graph or not isinstance(p_graph["edges"], (dict, list)):
                errors.append("Invalid or missing 'edges' in provenance_graph.")

    return errors


class SnapshotBuilder:
    """
    Factory for creating canonical AuditSnapshot instances from verification objects.
    """

    @staticmethod
    def build(
        tender_id: str,
        bid_id: str,
        requirements: List[Any],
        facts: List[Any],
        compliance_results: List[Any],
        integrity_findings: Optional[List[Any]] = None,
        government_responses: Optional[List[Any]] = None,
        human_review_items: Optional[List[Any]] = None,
        aggregated_status: Optional[Dict[str, Any]] = None,
        provenance_graph: Optional[Dict[str, Any]] = None,
        contradiction_inputs: Optional[List[Dict[str, Any]]] = None,
        tender_metadata: Optional[Dict[str, Any]] = None,
        evaluation_date: Optional[str] = None,
        config: Optional[DeterministicConfig] = None,
    ) -> AuditSnapshot:
        integrity_findings = integrity_findings or []
        government_responses = government_responses or []
        human_review_items = human_review_items or []
        contradiction_inputs = contradiction_inputs or []
        tender_metadata = tender_metadata or {}
        config = config or DeterministicConfig()

        # Serialize requirements
        s_reqs = [
            r.to_dict() if hasattr(r, "to_dict") else dict(r)
            for r in requirements
        ]

        # Serialize facts
        s_facts = [
            f.to_dict() if hasattr(f, "to_dict") else dict(f)
            for f in facts
        ]

        # Serialize compliance results
        s_comp = [
            c.to_dict() if hasattr(c, "to_dict") else dict(c)
            for c in compliance_results
        ]

        # Serialize integrity findings
        s_integ = [
            inf.to_dict() if hasattr(inf, "to_dict") else dict(inf)
            for inf in integrity_findings
        ]

        # Serialize government responses
        s_gov = [
            g.to_dict() if hasattr(g, "to_dict") else dict(g)
            for g in government_responses
        ]

        # Serialize human review items
        s_reviews = [
            h.to_dict() if hasattr(h, "to_dict") else dict(h)
            for h in human_review_items
        ]

        agg = aggregated_status or {}
        comp_status = agg.get("compliance_status", "PASS")
        integ_status = agg.get("integrity_status", "CONSISTENT")
        overall_status = agg.get("overall_status", "PASS")

        # If provenance graph not explicitly provided, build it now
        if not provenance_graph:
            from .provenance_dag import ProvenanceDAGBuilder
            dag = ProvenanceDAGBuilder.build(
                requirements=requirements,
                facts=facts,
                results=compliance_results,
                integrity_findings=integrity_findings,
                human_review_items=human_review_items,
                bid_id=bid_id,
                tender_id=tender_id,
            )
            provenance_graph = dag.to_dict()

        orig_results = {
            "compliance_results": s_comp,
            "integrity_findings": s_integ,
            "human_review_items": s_reviews,
            "compliance_status": comp_status,
            "integrity_status": integ_status,
            "overall_status": overall_status,
            "critical_failures": agg.get("critical_failures", 0),
            "major_failures": agg.get("major_failures", 0),
            "anomaly_count": agg.get("anomaly_count", len(s_integ)),
            "review_required": agg.get("review_required", len(s_reviews) > 0),
            "provenance_graph": provenance_graph,
        }

        conf_dict = config.to_dict()
        conf_hash = compute_config_hash(conf_dict)
        snapshot_id = f"SNAP-{tender_id}-{bid_id}"

        snap = AuditSnapshot(
            snapshot_version=SNAPSHOT_VERSION,
            replay_engine_version=REPLAY_ENGINE_VERSION,
            snapshot_id=snapshot_id,
            tender_id=tender_id,
            bid_id=bid_id,
            requirements=s_reqs,
            bidder_facts=s_facts,
            captured_government_responses=s_gov,
            contradiction_inputs=contradiction_inputs,
            tender_metadata=tender_metadata,
            evaluation_date=evaluation_date or config.default_evaluation_date,
            deterministic_config=conf_dict,
            verification_config_hash=conf_hash,
            original_results=orig_results,
        )
        return snap
