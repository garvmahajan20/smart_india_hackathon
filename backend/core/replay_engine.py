# -*- coding: utf-8 -*-
"""
Deterministic Replay Engine & Audit Snapshot Verifier.
Phase 10B.4: Cryptographic and functional verification of audit snapshots.

Principles:
    1. ZERO GEMINI CALLS: Never invokes probabilistic models.
    2. ZERO NETWORK CALLS: Never queries external government registries.
    3. ZERO MUTATION: Preserves original snapshot and produces independent replay.
    4. REUSES CANONICAL LOGIC: Directly invokes Step 4, Step 5, Aggregator, and DAG.
    5. BYTE-FOR-BYTE IDENTICAL: Deterministic hashing, comparison, and reporting.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field as dc_field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .models import BidderFact, TenderRequirement, VerificationResult
from .rule_engine import DeterministicRuleEngine
from .contradiction_engine import CrossDocumentContradictionEngine
from .provenance_dag import ProvenanceDAGBuilder, ProvenanceDAG
from .snapshot import (
    AuditSnapshot,
    DeterministicConfig,
    SNAPSHOT_VERSION,
    REPLAY_ENGINE_VERSION,
    SUPPORTED_SNAPSHOT_VERSIONS,
    canonical_json,
    compute_config_hash,
    compute_snapshot_hash,
    validate_snapshot_dict,
)
from backend.orchestration.aggregator import VerificationAggregator
from backend.verification.models import AdapterResponse, IntegrityFinding


class MismatchCategory(str, Enum):
    SNAPSHOT_INVALID = "SNAPSHOT_INVALID"
    SNAPSHOT_HASH_MISMATCH = "SNAPSHOT_HASH_MISMATCH"
    CONFIGURATION_MISMATCH = "CONFIGURATION_MISMATCH"
    SCHEMA_VERSION_MISMATCH = "SCHEMA_VERSION_MISMATCH"
    REQUIREMENT_MISMATCH = "REQUIREMENT_MISMATCH"
    FACT_MISMATCH = "FACT_MISMATCH"
    CANONICALIZATION_MISMATCH = "CANONICALIZATION_MISMATCH"
    VERIFICATION_RESULT_MISMATCH = "VERIFICATION_RESULT_MISMATCH"
    INTEGRITY_FINDING_MISMATCH = "INTEGRITY_FINDING_MISMATCH"
    REVIEW_ITEM_MISMATCH = "REVIEW_ITEM_MISMATCH"
    AGGREGATION_MISMATCH = "AGGREGATION_MISMATCH"
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    COMPLETE_MATCH = "COMPLETE_MATCH"


@dataclass
class ReplayMismatch:
    """Represents a discrete verified discrepancy between original snapshot and replay."""
    category: str
    item_id: str
    field: str
    original: Any
    replayed: Any
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "item_id": self.item_id,
            "field": self.field,
            "original": self.original,
            "replayed": self.replayed,
            "description": self.description,
        }


@dataclass
class ReplayVerificationResult:
    """
    Structured outcome of an audit snapshot verification pass.
    """
    status: str
    is_match: bool
    snapshot_id: str
    tender_id: str
    bid_id: str
    snapshot_hash: str
    recomputed_snapshot_hash: str
    config_hash: str
    recomputed_config_hash: str
    mismatches: List[ReplayMismatch] = dc_field(default_factory=list)
    replayed_results: Dict[str, Any] = dc_field(default_factory=dict)
    metrics: Dict[str, Any] = dc_field(default_factory=dict)

    def to_dict(self, include_transient_metrics: bool = False) -> Dict[str, Any]:
        d = {
            "status": self.status,
            "is_match": self.is_match,
            "snapshot_id": self.snapshot_id,
            "tender_id": self.tender_id,
            "bid_id": self.bid_id,
            "snapshot_hash": self.snapshot_hash,
            "recomputed_snapshot_hash": self.recomputed_snapshot_hash,
            "config_hash": self.config_hash,
            "recomputed_config_hash": self.recomputed_config_hash,
            "mismatches": [m.to_dict() for m in self.mismatches],
            "replayed_results": self.replayed_results,
        }
        if include_transient_metrics:
            d["metrics"] = self.metrics
        return d

    def to_json(self, indent: int = 2, include_transient_metrics: bool = False) -> str:
        return canonical_json(self.to_dict(include_transient_metrics=include_transient_metrics), indent=indent)


class DeterministicReplayEngine:
    """
    Pure Python Deterministic Replay & Audit Verifier.
    Independently validates and reproduces verification decisions from snapshots.
    """

    def __init__(self, active_config: Optional[DeterministicConfig] = None):
        self.active_config = active_config or DeterministicConfig()
        self.active_config_hash = compute_config_hash(self.active_config.to_dict())

    def replay(self, snapshot_input: Union[AuditSnapshot, Dict[str, Any], str]) -> ReplayVerificationResult:
        """
        Executes an end-to-end replay verification on the given snapshot.
        """
        t0 = time.perf_counter()
        timing_metrics: Dict[str, float] = {}

        # 1. Parse Input
        if isinstance(snapshot_input, str):
            try:
                snap_dict = json.loads(snapshot_input)
            except Exception as ex:
                return ReplayVerificationResult(
                    status=MismatchCategory.SNAPSHOT_INVALID.value,
                    is_match=False,
                    snapshot_id="UNKNOWN",
                    tender_id="UNKNOWN",
                    bid_id="UNKNOWN",
                    snapshot_hash="",
                    recomputed_snapshot_hash="",
                    config_hash="",
                    recomputed_config_hash=self.active_config_hash,
                    mismatches=[
                        ReplayMismatch(
                            category=MismatchCategory.SNAPSHOT_INVALID.value,
                            item_id="SNAPSHOT",
                            field="json_parsing",
                            original="VALID_JSON",
                            replayed="SYNTAX_ERROR",
                            description=f"Failed to parse snapshot JSON: {str(ex)}",
                        )
                    ],
                )
        elif isinstance(snapshot_input, AuditSnapshot):
            snap_dict = snapshot_input.to_dict()
        elif isinstance(snapshot_input, dict):
            snap_dict = dict(snapshot_input)
        else:
            return ReplayVerificationResult(
                status=MismatchCategory.SNAPSHOT_INVALID.value,
                is_match=False,
                snapshot_id="UNKNOWN",
                tender_id="UNKNOWN",
                bid_id="UNKNOWN",
                snapshot_hash="",
                recomputed_snapshot_hash="",
                config_hash="",
                recomputed_config_hash=self.active_config_hash,
                mismatches=[
                    ReplayMismatch(
                        category=MismatchCategory.SNAPSHOT_INVALID.value,
                        item_id="SNAPSHOT",
                        field="type",
                        original="dict_or_AuditSnapshot",
                        replayed=type(snapshot_input).__name__,
                        description=f"Invalid snapshot input type: {type(snapshot_input)}",
                    )
                ],
            )

        snapshot_id = str(snap_dict.get("snapshot_id", "UNKNOWN"))
        tender_id = str(snap_dict.get("tender_id", "UNKNOWN"))
        bid_id = str(snap_dict.get("bid_id", "UNKNOWN"))
        snap_hash = str(snap_dict.get("snapshot_hash", ""))
        claimed_cfg_hash = str(snap_dict.get("verification_config_hash", ""))

        mismatches: List[ReplayMismatch] = []

        # 2. Structural Schema Validation
        t_val = time.perf_counter()
        val_errors = validate_snapshot_dict(snap_dict)
        timing_metrics["validation_ms"] = (time.perf_counter() - t_val) * 1000.0

        if val_errors:
            is_version_err = any("unsupported snapshot_version" in e.lower() for e in val_errors)
            cat = MismatchCategory.SCHEMA_VERSION_MISMATCH.value if is_version_err else MismatchCategory.SNAPSHOT_INVALID.value
            for err in val_errors:
                mismatches.append(
                    ReplayMismatch(
                        category=cat,
                        item_id=snapshot_id,
                        field="schema_validation",
                        original="VALID",
                        replayed="INVALID",
                        description=err,
                    )
                )
            return ReplayVerificationResult(
                status=cat,
                is_match=False,
                snapshot_id=snapshot_id,
                tender_id=tender_id,
                bid_id=bid_id,
                snapshot_hash=snap_hash,
                recomputed_snapshot_hash="",
                config_hash=claimed_cfg_hash,
                recomputed_config_hash=self.active_config_hash,
                mismatches=mismatches,
            )

        # 3. Snapshot Cryptographic Hash Verification
        t_hash = time.perf_counter()
        recomputed_snap_hash = compute_snapshot_hash(snap_dict)
        timing_metrics["hash_computation_ms"] = (time.perf_counter() - t_hash) * 1000.0

        if recomputed_snap_hash != snap_hash:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.SNAPSHOT_HASH_MISMATCH.value,
                    item_id=snapshot_id,
                    field="snapshot_hash",
                    original=snap_hash,
                    replayed=recomputed_snap_hash,
                    description=f"Cryptographic hash mismatch: claimed '{snap_hash}' != recomputed '{recomputed_snap_hash}'. Content has been tampered with or modified.",
                )
            )

        # 4. Configuration Fingerprint Verification
        snap_cfg = snap_dict.get("deterministic_config", {})
        recomputed_cfg_hash = compute_config_hash(snap_cfg)

        if claimed_cfg_hash != recomputed_cfg_hash:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.CONFIGURATION_MISMATCH.value,
                    item_id="CONFIG",
                    field="verification_config_hash",
                    original=claimed_cfg_hash,
                    replayed=recomputed_cfg_hash,
                    description="Configuration dictionary does not match claimed configuration hash.",
                )
            )

        if recomputed_cfg_hash != self.active_config_hash:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.CONFIGURATION_MISMATCH.value,
                    item_id="CONFIG",
                    field="active_config_compatibility",
                    original=recomputed_cfg_hash,
                    replayed=self.active_config_hash,
                    description=f"Snapshot configuration differs from active replay configuration. Original config: {snap_cfg}",
                )
            )

        # 5. Reconstruct Deterministic Models
        t_reconstruct = time.perf_counter()
        try:
            requirements: List[TenderRequirement] = [
                TenderRequirement.from_dict(r) for r in snap_dict.get("requirements", [])
            ]
            facts: List[BidderFact] = [
                BidderFact.from_dict(f) for f in snap_dict.get("bidder_facts", [])
            ]
            captured_gov: List[AdapterResponse] = [
                AdapterResponse.from_dict(g) for g in snap_dict.get("captured_government_responses", [])
            ]
            contra_inputs: List[Dict[str, Any]] = snap_dict.get("contradiction_inputs", [])
            tender_meta = snap_dict.get("tender_metadata", {})
            eval_date_str = snap_dict.get("evaluation_date")
        except Exception as ex:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.SNAPSHOT_INVALID.value,
                    item_id=snapshot_id,
                    field="model_reconstruction",
                    original="SUCCESS",
                    replayed="FAILED",
                    description=f"Failed to reconstruct core domain models: {str(ex)}",
                )
            )
            return ReplayVerificationResult(
                status=MismatchCategory.SNAPSHOT_INVALID.value,
                is_match=False,
                snapshot_id=snapshot_id,
                tender_id=tender_id,
                bid_id=bid_id,
                snapshot_hash=snap_hash,
                recomputed_snapshot_hash=recomputed_snap_hash,
                config_hash=claimed_cfg_hash,
                recomputed_config_hash=recomputed_cfg_hash,
                mismatches=mismatches,
            )

        timing_metrics["reconstruction_ms"] = (time.perf_counter() - t_reconstruct) * 1000.0

        # Parse evaluation date if provided
        from datetime import date
        ref_date: Optional[date] = None
        if eval_date_str:
            try:
                parts = [int(p) for p in eval_date_str.split("-")]
                ref_date = date(parts[0], parts[1], parts[2])
            except Exception:
                ref_date = None

        # 6. Replay Step 4: Deterministic Compliance Engine
        t_rule = time.perf_counter()
        rule_engine = DeterministicRuleEngine(default_evaluation_date=ref_date)
        replayed_compliance = rule_engine.verify_bid(
            requirements=requirements,
            facts=facts,
            tender_metadata=tender_meta,
            evaluation_date=ref_date,
        )
        timing_metrics["rule_engine_ms"] = (time.perf_counter() - t_rule) * 1000.0

        # 7. Replay Step 5: Deterministic Contradiction Engine
        t_contra = time.perf_counter()
        contra_engine = CrossDocumentContradictionEngine()
        replayed_integrity: List[IntegrityFinding] = []

        if contra_inputs:
            for c in contra_inputs:
                finding = contra_engine.evaluate_pair(
                    contradiction_id=c.get("contradiction_id", f"CONTRA-{bid_id}"),
                    bid_id=bid_id,
                    field_name=c.get("field_name", c.get("type", "cross_document_consistency")),
                    value_a=c.get("value_a"),
                    value_b=c.get("value_b"),
                    document_a=c.get("document_a", "doc_a.pdf"),
                    page_a=c.get("page_a", 1),
                    bbox_a=c.get("bbox_a", [0.0, 0.0, 0.0, 0.0]),
                    snippet_a=c.get("snippet_a", ""),
                    document_b=c.get("document_b", "doc_b.pdf"),
                    page_b=c.get("page_b", 1),
                    bbox_b=c.get("bbox_b", [0.0, 0.0, 0.0, 0.0]),
                    snippet_b=c.get("snippet_b", ""),
                    hint_type=c.get("hint_type", c.get("type")),
                    raw_field_a=c.get("raw_field_a"),
                    raw_field_b=c.get("raw_field_b"),
                    canonical_field=c.get("canonical_field"),
                )
                replayed_integrity.append(finding)
        else:
            replayed_integrity = contra_engine.detect_contradictions_in_bid(bid_id=bid_id, facts=facts)

        timing_metrics["contradiction_engine_ms"] = (time.perf_counter() - t_contra) * 1000.0

        # 8. Replay Step 8: Deterministic Aggregation
        t_agg = time.perf_counter()
        aggregator = VerificationAggregator()
        replayed_agg = aggregator.aggregate(
            tender_id=tender_id,
            bid_id=bid_id,
            compliance_results=replayed_compliance,
            integrity_findings=replayed_integrity,
            government_responses=captured_gov,
        )
        timing_metrics["aggregation_ms"] = (time.perf_counter() - t_agg) * 1000.0

        # 9. Reconstruct Provenance DAG
        t_dag = time.perf_counter()
        replayed_dag = ProvenanceDAGBuilder.build(
            requirements=requirements,
            facts=facts,
            results=replayed_compliance,
            integrity_findings=replayed_integrity,
            human_review_items=replayed_agg.human_review_items,
            bid_id=bid_id,
            tender_id=tender_id,
        )
        # Validate acyclicity
        replayed_dag.validate()
        timing_metrics["provenance_dag_ms"] = (time.perf_counter() - t_dag) * 1000.0

        # 10. Multi-Layer Forensic Comparison
        t_comp = time.perf_counter()
        orig_res = snap_dict.get("original_results", {})

        # Layer A: Requirements & Facts Integrity
        orig_reqs = {r.get("requirement_id"): r for r in snap_dict.get("requirements", [])}
        for req in requirements:
            if req.requirement_id not in orig_reqs:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.REQUIREMENT_MISMATCH.value,
                        item_id=req.requirement_id,
                        field="existence",
                        original=None,
                        replayed=req.requirement_id,
                        description=f"Requirement '{req.requirement_id}' was not in original snapshot requirements list.",
                    )
                )

        orig_facts = {f.get("fact_id"): f for f in snap_dict.get("bidder_facts", [])}
        for fact in facts:
            if fact.fact_id not in orig_facts:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.FACT_MISMATCH.value,
                        item_id=fact.fact_id,
                        field="existence",
                        original=None,
                        replayed=fact.fact_id,
                        description=f"Fact '{fact.fact_id}' was not in original snapshot facts list.",
                    )
                )
            else:
                o_f = orig_facts[fact.fact_id]
                # Compare canonical field against deterministic ontology resolution
                from .ontology import resolve_field
                res_ont = resolve_field(fact.field)
                expected_cid = res_ont.canonical_field_id if res_ont.resolution_status == "RESOLVED" else None
                if fact.canonical_field != expected_cid:
                    mismatches.append(
                        ReplayMismatch(
                            category=MismatchCategory.CANONICALIZATION_MISMATCH.value,
                            item_id=fact.fact_id,
                            field="canonical_field",
                            original=fact.canonical_field,
                            replayed=expected_cid,
                            description=f"Canonical field for fact '{fact.fact_id}' ('{fact.canonical_field}') does not match ontology resolution ('{expected_cid}') for field '{fact.field}'.",
                        )
                    )

        # Layer A.2: Government Responses vs Declared Regulatory Facts
        declared_regulatory_ids = set()
        declared_auth_codes = set()
        declared_mii_declarations = set()
        declared_itr_acks = set()
        declared_names = set()
        for f in facts:
            f_field_lower = (f.field or "").lower()
            if f.canonical_field in ["GSTIN", "PAN", "UDYAM_REGISTRATION", "CIN"] or f_field_lower in ["gstin", "pan", "udyam_registration", "cin"]:
                if f.value:
                    declared_regulatory_ids.add(str(f.value).strip().upper())
            if f.canonical_field in ["OEM_AUTHORIZATION_CODE", "AUTHORIZATION_CODE"] or f_field_lower in ["oem_authorization_code", "authorization_code", "oem_auth_code", "maf_code", "oem_authorization"]:
                if f.value:
                    declared_auth_codes.add(str(f.value).strip().upper())
            if f.canonical_field == "MII_DECLARATION" or f_field_lower in ["mii", "mii_declaration", "mii_declaration_number", "mii_certificate"]:
                if f.value:
                    declared_mii_declarations.add(str(f.value).strip().upper())
            if f.canonical_field == "ITR_ACK" or f_field_lower in ["itr", "itr_ack", "itr_acknowledgement_number", "itr_ack_number"]:
                if f.value:
                    declared_itr_acks.add(str(f.value).strip().upper())
            if f.canonical_field in ["BIDDER_NAME", "COMPANY_NAME"] or f_field_lower in ["bidder_name", "company_name", "vendor_name", "registered_name"]:
                if f.value:
                    declared_names.add(str(f.value).strip().lower())
        if tender_meta.get("bidder_name"):
            declared_names.add(str(tender_meta["bidder_name"]).strip().lower())

        if declared_regulatory_ids:
            captured_ids = {str(g.queried_identifier).strip().upper() for g in captured_gov if g.queried_identifier}
            missing_ids = declared_regulatory_ids - captured_ids
            if missing_ids:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.REVIEW_ITEM_MISMATCH.value,
                        item_id="GOVERNMENT_RESPONSES",
                        field="captured_government_responses",
                        original=sorted(list(declared_regulatory_ids)),
                        replayed=sorted(list(captured_ids)),
                        description=f"Declared regulatory identifiers {sorted(list(missing_ids))} missing from captured government responses.",
                    )
                )

        for g in captured_gov:
            if g.adapter_name in ["DebarmentAdapter", "MockDebarmentAdapter"]:
                qid_lower = str(g.queried_identifier).strip().lower() if g.queried_identifier else ""
                qid_upper = str(g.queried_identifier).strip().upper() if g.queried_identifier else ""
                if declared_names or declared_regulatory_ids:
                    name_match = declared_names and qid_lower and any(d in qid_lower or qid_lower in d for d in declared_names)
                    id_match = qid_upper in declared_regulatory_ids
                    if not (name_match or id_match):
                        mismatches.append(
                            ReplayMismatch(
                                category=MismatchCategory.REVIEW_ITEM_MISMATCH.value,
                                item_id=g.adapter_name,
                                field="queried_identifier",
                                original=sorted(list(declared_names)),
                                replayed=g.queried_identifier,
                                description=f"Debarment queried identifier '{g.queried_identifier}' was not declared in bidder names or identifiers.",
                            )
                        )
                continue

            qid = str(g.queried_identifier).strip().upper() if g.queried_identifier else ""
            adapter_upper = g.adapter_name.upper()
            if "OEM" in adapter_upper:
                if declared_auth_codes and qid and qid not in declared_auth_codes:
                    mismatches.append(
                        ReplayMismatch(
                            category=MismatchCategory.REVIEW_ITEM_MISMATCH.value,
                            item_id=g.adapter_name,
                            field="queried_identifier",
                            original=sorted(list(declared_auth_codes)),
                            replayed=qid,
                            description=f"Government response queried OEM code '{qid}' was not declared in bidder facts.",
                        )
                    )
            elif "MII" in adapter_upper:
                if declared_mii_declarations and qid and qid not in declared_mii_declarations:
                    mismatches.append(
                        ReplayMismatch(
                            category=MismatchCategory.REVIEW_ITEM_MISMATCH.value,
                            item_id=g.adapter_name,
                            field="queried_identifier",
                            original=sorted(list(declared_mii_declarations)),
                            replayed=qid,
                            description=f"Government response queried MII declaration '{qid}' was not declared in bidder facts.",
                        )
                    )
            elif "ITD" in adapter_upper:
                if declared_itr_acks and qid and qid not in declared_itr_acks:
                    mismatches.append(
                        ReplayMismatch(
                            category=MismatchCategory.REVIEW_ITEM_MISMATCH.value,
                            item_id=g.adapter_name,
                            field="queried_identifier",
                            original=sorted(list(declared_itr_acks)),
                            replayed=qid,
                            description=f"Government response queried ITR acknowledgement '{qid}' was not declared in bidder facts.",
                        )
                    )
            elif declared_regulatory_ids and qid:
                if qid not in declared_regulatory_ids:
                    mismatches.append(
                        ReplayMismatch(
                            category=MismatchCategory.REVIEW_ITEM_MISMATCH.value,
                            item_id=g.adapter_name,
                            field="queried_identifier",
                            original=sorted(list(declared_regulatory_ids)),
                            replayed=qid,
                            description=f"Government response queried identifier '{qid}' was not declared in bidder facts.",
                        )
                    )
            g_stat = getattr(g, "status", None)
            g_stat_val = g_stat.value if hasattr(g_stat, "value") else str(g_stat)
            if declared_names and getattr(g, "registered_entity_name", None) and g_stat_val == "VERIFIED":
                r_name = str(g.registered_entity_name).strip().lower()
                if not any(d in r_name or r_name in d for d in declared_names):
                    mismatches.append(
                        ReplayMismatch(
                            category=MismatchCategory.REVIEW_ITEM_MISMATCH.value,
                            item_id=g.adapter_name,
                            field="registered_entity_name",
                            original=sorted(list(declared_names)),
                            replayed=g.registered_entity_name,
                            description=f"Government response registered entity name '{g.registered_entity_name}' does not match declared bidder names.",
                        )
                    )

        # Layer B: Verification Results Comparison
        orig_comp_list = orig_res.get("compliance_results", [])
        orig_comp_map = {c.get("requirement_id") or c.get("verification_id"): c for c in orig_comp_list}
        replayed_comp_map = {c.requirement_id: c for c in replayed_compliance}

        for r_id, orig_c in orig_comp_map.items():
            rep_c = replayed_comp_map.get(r_id)
            if not rep_c:
                # Also check by verification_id
                rep_c = next((c for c in replayed_compliance if c.verification_id == r_id), None)

            if not rep_c:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.VERIFICATION_RESULT_MISMATCH.value,
                        item_id=str(r_id),
                        field="missing_result",
                        original=orig_c.get("status"),
                        replayed=None,
                        description=f"Verification result for '{r_id}' missing in replay output.",
                    )
                )
                continue

            # Compare status
            if orig_c.get("status") != rep_c.status:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.VERIFICATION_RESULT_MISMATCH.value,
                        item_id=rep_c.verification_id,
                        field="status",
                        original=orig_c.get("status"),
                        replayed=rep_c.status,
                        description=f"Compliance status mismatch on requirement '{rep_c.requirement_id}': original '{orig_c.get('status')}' != replayed '{rep_c.status}'.",
                    )
                )

            # Compare severity
            if orig_c.get("severity") != rep_c.severity:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.VERIFICATION_RESULT_MISMATCH.value,
                        item_id=rep_c.verification_id,
                        field="severity",
                        original=orig_c.get("severity"),
                        replayed=rep_c.severity,
                        description=f"Severity mismatch on '{rep_c.requirement_id}': original '{orig_c.get('severity')}' != replayed '{rep_c.severity}'.",
                    )
                )

            # Compare operator
            if orig_c.get("operator_used") != rep_c.operator_used:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.VERIFICATION_RESULT_MISMATCH.value,
                        item_id=rep_c.verification_id,
                        field="operator_used",
                        original=orig_c.get("operator_used"),
                        replayed=rep_c.operator_used,
                        description=f"Operator mismatch on '{rep_c.requirement_id}': '{orig_c.get('operator_used')}' != '{rep_c.operator_used}'.",
                    )
                )

            # Compare fact_id
            if orig_c.get("fact_id") != rep_c.fact_id:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.VERIFICATION_RESULT_MISMATCH.value,
                        item_id=rep_c.verification_id,
                        field="fact_id",
                        original=orig_c.get("fact_id"),
                        replayed=rep_c.fact_id,
                        description=f"Fact link mismatch on '{rep_c.requirement_id}': '{orig_c.get('fact_id')}' != '{rep_c.fact_id}'.",
                    )
                )

        # Layer C: Integrity Findings Comparison
        orig_integ_list = orig_res.get("integrity_findings", [])
        orig_integ_map = {inf.get("finding_id"): inf for inf in orig_integ_list}
        replayed_integ_map = {inf.finding_id: inf for inf in replayed_integrity}

        if len(orig_integ_list) != len(replayed_integrity):
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.INTEGRITY_FINDING_MISMATCH.value,
                    item_id="INTEGRITY_FINDINGS_COUNT",
                    field="count",
                    original=len(orig_integ_list),
                    replayed=len(replayed_integrity),
                    description=f"Integrity finding count mismatch: original {len(orig_integ_list)} != replayed {len(replayed_integrity)}.",
                )
            )

        for fid, o_inf in orig_integ_map.items():
            r_inf = replayed_integ_map.get(fid)
            if not r_inf:
                # Try finding by field/status
                r_inf = next((inf for inf in replayed_integrity if inf.field == o_inf.get("field")), None)

            if not r_inf:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.INTEGRITY_FINDING_MISMATCH.value,
                        item_id=fid,
                        field="missing_finding",
                        original=o_inf.get("status"),
                        replayed=None,
                        description=f"Integrity finding '{fid}' missing in replay output.",
                    )
                )
                continue

            if o_inf.get("status") != r_inf.status:
                mismatches.append(
                    ReplayMismatch(
                        category=MismatchCategory.INTEGRITY_FINDING_MISMATCH.value,
                        item_id=r_inf.finding_id,
                        field="status",
                        original=o_inf.get("status"),
                        replayed=r_inf.status,
                        description=f"Integrity status mismatch for '{fid}': '{o_inf.get('status')}' != '{r_inf.status}'.",
                    )
                )

        # Layer D: Human Review Items Comparison
        orig_rev_list = orig_res.get("human_review_items", [])
        replayed_rev_list = replayed_agg.human_review_items

        if len(orig_rev_list) != len(replayed_rev_list):
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.REVIEW_ITEM_MISMATCH.value,
                    item_id="HUMAN_REVIEW_COUNT",
                    field="count",
                    original=len(orig_rev_list),
                    replayed=len(replayed_rev_list),
                    description=f"Human review items count mismatch: original {len(orig_rev_list)} != replayed {len(replayed_rev_list)}.",
                )
            )

        # Layer E: Aggregation Outcomes Comparison
        if orig_res.get("compliance_status") != replayed_agg.compliance_status:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.AGGREGATION_MISMATCH.value,
                    item_id="AGGREGATION",
                    field="compliance_status",
                    original=orig_res.get("compliance_status"),
                    replayed=replayed_agg.compliance_status,
                    description=f"Aggregated compliance status mismatch: '{orig_res.get('compliance_status')}' != '{replayed_agg.compliance_status}'.",
                )
            )

        if orig_res.get("integrity_status") != replayed_agg.integrity_status:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.AGGREGATION_MISMATCH.value,
                    item_id="AGGREGATION",
                    field="integrity_status",
                    original=orig_res.get("integrity_status"),
                    replayed=replayed_agg.integrity_status,
                    description=f"Aggregated integrity status mismatch: '{orig_res.get('integrity_status')}' != '{replayed_agg.integrity_status}'.",
                )
            )

        if orig_res.get("overall_status") != replayed_agg.overall_status:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.AGGREGATION_MISMATCH.value,
                    item_id="AGGREGATION",
                    field="overall_status",
                    original=orig_res.get("overall_status"),
                    replayed=replayed_agg.overall_status,
                    description=f"Overall status mismatch: '{orig_res.get('overall_status')}' != '{replayed_agg.overall_status}'.",
                )
            )

        if "critical_failures" in orig_res and orig_res["critical_failures"] != replayed_agg.critical_failures:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.AGGREGATION_MISMATCH.value,
                    item_id="AGGREGATION",
                    field="critical_failures",
                    original=orig_res.get("critical_failures"),
                    replayed=replayed_agg.critical_failures,
                    description=f"Critical failures count mismatch: {orig_res.get('critical_failures')} != {replayed_agg.critical_failures}.",
                )
            )

        if "major_failures" in orig_res and orig_res["major_failures"] != replayed_agg.major_failures:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.AGGREGATION_MISMATCH.value,
                    item_id="AGGREGATION",
                    field="major_failures",
                    original=orig_res.get("major_failures"),
                    replayed=replayed_agg.major_failures,
                    description=f"Major failures count mismatch: {orig_res.get('major_failures')} != {replayed_agg.major_failures}.",
                )
            )

        if "anomaly_count" in orig_res and orig_res["anomaly_count"] != replayed_agg.anomaly_count:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.AGGREGATION_MISMATCH.value,
                    item_id="AGGREGATION",
                    field="anomaly_count",
                    original=orig_res.get("anomaly_count"),
                    replayed=replayed_agg.anomaly_count,
                    description=f"Anomaly count mismatch: {orig_res.get('anomaly_count')} != {replayed_agg.anomaly_count}.",
                )
            )

        # Layer F: Provenance Graph Structural Comparison
        orig_dag_dict = orig_res.get("provenance_graph", {})
        replayed_dag_dict = replayed_dag.to_dict()

        orig_nodes = orig_dag_dict.get("nodes", {})
        replayed_nodes = replayed_dag_dict.get("nodes", {})

        orig_node_ids = set(orig_nodes.keys() if isinstance(orig_nodes, dict) else [n["node_id"] for n in orig_nodes])
        replayed_node_ids = set(replayed_nodes.keys() if isinstance(replayed_nodes, dict) else [n["node_id"] for n in replayed_nodes])

        if orig_node_ids != replayed_node_ids:
            diff_missing = orig_node_ids - replayed_node_ids
            diff_extra = replayed_node_ids - orig_node_ids
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.PROVENANCE_MISMATCH.value,
                    item_id="PROVENANCE_DAG_NODES",
                    field="node_ids",
                    original=sorted(list(orig_node_ids)),
                    replayed=sorted(list(replayed_node_ids)),
                    description=f"Provenance graph nodes mismatch. Missing: {sorted(list(diff_missing))}, Extra: {sorted(list(diff_extra))}.",
                )
            )

        orig_edges = orig_dag_dict.get("edges", {})
        replayed_edges = replayed_dag_dict.get("edges", {})

        orig_edge_ids = set(orig_edges.keys() if isinstance(orig_edges, dict) else [e["edge_id"] for e in orig_edges])
        replayed_edge_ids = set(replayed_edges.keys() if isinstance(replayed_edges, dict) else [e["edge_id"] for e in replayed_edges])

        if orig_edge_ids != replayed_edge_ids:
            diff_missing_e = orig_edge_ids - replayed_edge_ids
            diff_extra_e = replayed_edge_ids - orig_edge_ids
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.PROVENANCE_MISMATCH.value,
                    item_id="PROVENANCE_DAG_EDGES",
                    field="edge_ids",
                    original=sorted(list(orig_edge_ids)),
                    replayed=sorted(list(replayed_edge_ids)),
                    description=f"Provenance graph edges mismatch. Missing: {sorted(list(diff_missing_e))}, Extra: {sorted(list(diff_extra_e))}.",
                )
            )

        # Graph Canonical Hash Check (sort nodes and edges deterministically by ID so ordering alone causes no false mismatch)
        def _normalize_dag_for_hashing(dag_data: Any) -> Any:
            if not isinstance(dag_data, dict):
                return dag_data
            d = dict(dag_data)
            nodes = d.get("nodes", [])
            if isinstance(nodes, list):
                d["nodes"] = sorted(nodes, key=lambda n: n.get("node_id", "") if isinstance(n, dict) else str(n))
            edges = d.get("edges", [])
            if isinstance(edges, list):
                d["edges"] = sorted(edges, key=lambda e: e.get("edge_id", "") if isinstance(e, dict) else str(e))
            return d

        orig_dag_hash = hashlib.sha256(canonical_json(_normalize_dag_for_hashing(orig_dag_dict)).encode("utf-8")).hexdigest()
        replayed_dag_hash = hashlib.sha256(canonical_json(_normalize_dag_for_hashing(replayed_dag_dict)).encode("utf-8")).hexdigest()

        if orig_dag_hash != replayed_dag_hash and orig_node_ids == replayed_node_ids and orig_edge_ids == replayed_edge_ids:
            mismatches.append(
                ReplayMismatch(
                    category=MismatchCategory.PROVENANCE_MISMATCH.value,
                    item_id="PROVENANCE_DAG_PROPERTIES",
                    field="canonical_dag_hash",
                    original=orig_dag_hash,
                    replayed=replayed_dag_hash,
                    description="Provenance graph node/edge properties differ under canonical hash.",
                )
            )

        timing_metrics["comparison_ms"] = (time.perf_counter() - t_comp) * 1000.0
        timing_metrics["total_replay_time_ms"] = (time.perf_counter() - t0) * 1000.0

        # Formulate Overall Replay Status
        if not mismatches:
            overall_verdict = MismatchCategory.COMPLETE_MATCH.value
            is_match = True
        else:
            overall_verdict = mismatches[0].category
            is_match = False

        replayed_results_payload = {
            "compliance_results": [c.to_dict() for c in replayed_compliance],
            "integrity_findings": [inf.to_dict() for inf in replayed_integrity],
            "human_review_items": [h.to_dict() if hasattr(h, "to_dict") else h for h in replayed_agg.human_review_items],
            "compliance_status": replayed_agg.compliance_status,
            "integrity_status": replayed_agg.integrity_status,
            "overall_status": replayed_agg.overall_status,
            "critical_failures": replayed_agg.critical_failures,
            "major_failures": replayed_agg.major_failures,
            "anomaly_count": replayed_agg.anomaly_count,
            "provenance_node_count": len(replayed_dag.nodes),
            "provenance_edge_count": len(replayed_dag.edges),
            "provenance_graph_hash": replayed_dag_hash,
        }

        return ReplayVerificationResult(
            status=overall_verdict,
            is_match=is_match,
            snapshot_id=snapshot_id,
            tender_id=tender_id,
            bid_id=bid_id,
            snapshot_hash=snap_hash,
            recomputed_snapshot_hash=recomputed_snap_hash,
            config_hash=claimed_cfg_hash,
            recomputed_config_hash=recomputed_cfg_hash,
            mismatches=mismatches,
            replayed_results=replayed_results_payload,
            metrics=timing_metrics,
        )
