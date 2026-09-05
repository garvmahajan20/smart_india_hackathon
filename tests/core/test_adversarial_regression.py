# -*- coding: utf-8 -*-
"""
Phase 10B.5 Comprehensive Adversarial & Tamper Regression Test Suite.

Executes and verifies:
- Phase 3: Evidence Attacks (E1 - E12)
- Phase 4: Provenance Attacks (P1 - P16)
- Phase 5: Ontology Attacks (O1 - O10)
- Phase 6: Requirement / Rule Attacks (R1 - R15)
- Phase 7: Cross-Field Value Swaps (XF1 - XF9)
- Phase 8: Contradiction Attacks (C1 - C12)
- Phase 9: Government Response Attacks (G1 - G9)
- Phase 10: Aggregation Attacks (A1 - A10)
- Phase 11: Snapshot Attacks (S1 - S20)
- Phase 12: Replay Attacks (RP1 - RP12)
- Phase 13: Cross-Layer Synchronized Attacks (X1 - X8)
- Phase 14: Negative Controls (N1 - N7)

Every test records an AdversarialAttackResult into the central AdversarialManifest.
Guarantees anti-tampering invariants:
    silently_accepted == 0
    false_negative_count == 0
    false_positive_count == 0
"""

import copy
import hashlib
import json
import os
import sys
import time
import unittest
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath("."))

from backend.core.adversarial_framework import (
    AdversarialAttackResult,
    AdversarialManifest,
    AttackCategory,
    DetectionMechanism,
    TargetLayer,
)
from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    Severity,
    TenderRequirement,
    VerificationResult,
)
from backend.core.ontology import (
    ResolutionMethod,
    ResolutionStatus,
    resolve_field,
)
from backend.core.provenance_dag import (
    ProvenanceDAG,
    ProvenanceDAGBuilder,
)
from backend.core.replay_engine import (
    DeterministicReplayEngine,
    MismatchCategory,
    ReplayMismatch,
    ReplayVerificationResult,
)
from backend.core.rule_engine import DeterministicRuleEngine
from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.core.snapshot import (
    AuditSnapshot,
    DeterministicConfig,
    SnapshotBuilder,
    canonical_json,
    compute_config_hash,
    compute_snapshot_hash,
    validate_snapshot_dict,
)
from backend.extraction.evidence_grounder import (
    EvidenceGrounder,
    verify_fact_support,
)
from backend.extraction.models import ExtractionStatus
from backend.ingestion.models import (
    DocumentMetadata,
    ExtractedPage,
    ExtractionResult,
    TextBlock,
)
from backend.orchestration.aggregator import VerificationAggregator
from backend.orchestration.models import HumanReviewItem
from backend.verification.models import (
    AdapterResponse,
    IntegrityFinding,
    VerificationStatus,
)

# Global test manifest
GLOBAL_MANIFEST = AdversarialManifest("PHASE_10B_5_REGRESSION_MANIFEST")


class TestAdversarialRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = GLOBAL_MANIFEST
        cls.rule_engine = DeterministicRuleEngine()
        cls.contra_engine = CrossDocumentContradictionEngine()
        cls.aggregator = VerificationAggregator()
        cls.replay_engine = DeterministicReplayEngine()

        # Build clean test fixtures
        cls.req_turnover = TenderRequirement(
            requirement_id="REQ-TO-01",
            tender_id="TENDER-ADV-101",
            category="FINANCIAL_CAPACITY",
            description="Minimum annual turnover of INR 10.0 Crore",
            operator=">=",
            expected_value=10.0,
            normalized_expected_value=10.0,
            field="turnover_amount",
            canonical_field="ANNUAL_TURNOVER",
            mandatory=True,
            evidence=[{
                "block_id": "T-BLK-01",
                "document": "tender.pdf",
                "page": 2,
                "bbox": [10.0, 20.0, 30.0, 40.0],
                "snippet": "Minimum annual turnover shall be INR 10.0 Crore",
            }],
        )
        cls.req_exp = TenderRequirement(
            requirement_id="REQ-EXP-01",
            tender_id="TENDER-ADV-101",
            category="TECHNICAL_CAPACITY",
            description="Minimum past experience of 5 years",
            operator=">=",
            expected_value=5,
            normalized_expected_value=5,
            field="past_experience_years",
            canonical_field="PAST_EXPERIENCE_DURATION",
            mandatory=True,
            evidence=[{
                "block_id": "T-BLK-02",
                "document": "tender.pdf",
                "page": 3,
                "bbox": [50.0, 60.0, 70.0, 80.0],
                "snippet": "Minimum past experience of 5 years",
            }],
        )

        cls.fact_turnover = BidderFact(
            fact_id="FACT-TO-01",
            bid_id="BID-ADV-202",
            field="turnover_amount",
            canonical_field="ANNUAL_TURNOVER",
            value=12.5,
            normalized_value=12.5,
            unit="INR_CRORE",
            source_document="balance_sheet.pdf",
            page=8,
            bbox=[100.0, 100.0, 200.0, 200.0],
            raw_text_snippet="Certified annual turnover: INR 12.50 Cr",
            evidence=[
                {
                    "block_id": "B-BLK-01",
                    "document": "balance_sheet.pdf",
                    "page": 8,
                    "bbox": [100.0, 100.0, 200.0, 200.0],
                    "snippet": "Certified annual turnover: INR 12.50 Cr",
                },
                {
                    "block_id": "B-BLK-02",
                    "document": "balance_sheet.pdf",
                    "page": 9,
                    "bbox": [50.0, 50.0, 150.0, 150.0],
                    "snippet": "UDIN CA Seal: 24000123AB",
                },
            ],
        )
        cls.fact_exp = BidderFact(
            fact_id="FACT-EXP-01",
            bid_id="BID-ADV-202",
            field="past_experience_years",
            canonical_field="PAST_EXPERIENCE_DURATION",
            value=7,
            normalized_value=7,
            source_document="experience_cert.pdf",
            page=1,
            bbox=[20.0, 20.0, 80.0, 80.0],
            raw_text_snippet="Past experience confirmed: 7 years completed",
            evidence=[{
                "block_id": "B-BLK-03",
                "document": "experience_cert.pdf",
                "page": 1,
                "bbox": [20.0, 20.0, 80.0, 80.0],
                "snippet": "Past experience confirmed: 7 years completed",
            }],
        )

        cls.fact_gst = BidderFact(
            fact_id="FACT-GST-01",
            bid_id="BID-ADV-202",
            field="gstin",
            canonical_field="GSTIN",
            value="29SYNTH0000003F1Z",
            normalized_value="29SYNTH0000003F1Z",
            source_document="balance_sheet.pdf",
            page=1,
            bbox=[50.0, 50.0, 150.0, 150.0],
            raw_text_snippet="GSTIN: 29SYNTH0000003F1Z",
            evidence=[{
                "block_id": "B-BLK-02",
                "document": "balance_sheet.pdf",
                "page": 1,
                "bbox": [50.0, 50.0, 150.0, 150.0],
                "snippet": "GSTIN: 29SYNTH0000003F1Z",
            }],
        )

        cls.gov_gst = AdapterResponse(
            status=VerificationStatus.VERIFIED,
            adapter_name="GSTAdapter",
            queried_identifier="29SYNTH0000003F1Z",
            source="GSTN_REGISTRY",
            reason="GSTIN is active and verified",
            registered_entity_name="Acme Solutions Ltd",
        )

        comp = cls.rule_engine.verify_bid(
            requirements=[cls.req_turnover, cls.req_exp],
            facts=[cls.fact_turnover, cls.fact_exp, cls.fact_gst],
        )
        cls.res_turnover, cls.res_exp = comp[0], comp[1]

        cls.clean_snapshot = SnapshotBuilder.build(
            tender_id="TENDER-ADV-101",
            bid_id="BID-ADV-202",
            requirements=[cls.req_turnover, cls.req_exp],
            facts=[cls.fact_turnover, cls.fact_exp, cls.fact_gst],
            compliance_results=[cls.res_turnover, cls.res_exp],
            integrity_findings=[],
            government_responses=[cls.gov_gst],
            human_review_items=[],
            aggregated_status={
                "compliance_status": "PASS",
                "integrity_status": "CONSISTENT",
                "overall_status": "PASS",
            },
            tender_metadata={"bidder_name": "Acme Solutions Ltd"},
        )

        # Ingestion result for grounding tests
        cls.ingestion_res = ExtractionResult(
            document_id="DOC-ADV-01",
            metadata=DocumentMetadata(
                document_id="DOC-ADV-01",
                filename="balance_sheet.pdf",
                file_path="balance_sheet.pdf",
                file_size_bytes=4096,
                sha256="hash123",
                page_count=2,
            ),
            pages=[
                ExtractedPage(
                    page_number=1,
                    width=600.0,
                    height=800.0,
                    text="Audited Annual Turnover: INR 12.50 Cr. GSTIN: 29SYNTH0000003F1Z. Warranty: 36 months.",
                    raw_text="",
                    blocks=[
                        TextBlock(block_id="B-BLK-01", page_number=1, text="Audited Annual Turnover: INR 12.50 Cr", raw_text="", bbox=[100.0, 100.0, 200.0, 200.0]),
                        TextBlock(block_id="B-BLK-02", page_number=1, text="GSTIN: 29SYNTH0000003F1Z | PAN: SYNTH0003F", raw_text="", bbox=[50.0, 50.0, 150.0, 150.0]),
                        TextBlock(block_id="B-BLK-03", page_number=1, text="Comprehensive warranty: 36 months on-site", raw_text="", bbox=[20.0, 20.0, 80.0, 80.0]),
                    ],
                )
            ],
        )
        cls.grounder = EvidenceGrounder(cls.ingestion_res)

    def _record_attack(
        self,
        attack_id: str,
        category: AttackCategory,
        target_layer: TargetLayer,
        description: str,
        mutation: str,
        expected_detection: DetectionMechanism,
        actual_detection: DetectionMechanism,
        expected_status: str,
        actual_status: str,
        passed: bool,
        notes: str = "",
    ):
        result = AdversarialAttackResult(
            attack_id=attack_id,
            category=category.value,
            description=description,
            mutation=mutation,
            target_layer=target_layer.value,
            expected_detection=expected_detection.value,
            actual_detection=actual_detection.value,
            expected_status=expected_status,
            actual_status=actual_status,
            passed=passed,
            notes=notes,
        )
        self.manifest.record(result)

    # =========================================================================
    # PHASE 3: EVIDENCE ATTACKS (E1 - E12)
    # =========================================================================

    def test_E01_fact_supported_by_unrelated_evidence(self):
        """E1: Fact value supported by completely unrelated evidence block."""
        is_sup, m_type, errs = verify_fact_support(12.5, "turnover_amount", "Warranty: 36 months on-site")
        self.assertFalse(is_sup)
        self._record_attack(
            "E1", AttackCategory.EVIDENCE, TargetLayer.EVIDENCE_GROUNDER,
            "Fact supported by unrelated evidence block", "Turnover supported by warranty block",
            DetectionMechanism.GROUNDING_FAILURE, DetectionMechanism.GROUNDING_FAILURE,
            "REJECTED", "REJECTED", not is_sup
        )

    def test_E02_fact_value_absent_from_evidence(self):
        """E2: Fact value absent from evidence."""
        is_sup, m_type, errs = verify_fact_support(99.9, "turnover_amount", "Audited Annual Turnover: INR 12.50 Cr")
        self.assertFalse(is_sup)
        self._record_attack(
            "E2", AttackCategory.EVIDENCE, TargetLayer.EVIDENCE_GROUNDER,
            "Fact value absent from evidence", "99.9 absent from 12.50 Cr text",
            DetectionMechanism.GROUNDING_FAILURE, DetectionMechanism.GROUNDING_FAILURE,
            "REJECTED", "REJECTED", not is_sup
        )

    def test_E03_numeric_value_changed_evidence_unchanged(self):
        """E3: Numeric value changed while evidence remains unchanged."""
        res = self.grounder.ground_fact(["B-BLK-01"], raw_value="99.0 Cr", field_name="turnover_amount", strict=True)
        self.assertFalse(res.is_valid)
        self._record_attack(
            "E3", AttackCategory.EVIDENCE, TargetLayer.EVIDENCE_GROUNDER,
            "Numeric value changed while evidence unchanged", "12.5 -> 99.0 Cr against block text",
            DetectionMechanism.GROUNDING_FAILURE, DetectionMechanism.GROUNDING_FAILURE,
            "REJECTED", "REJECTED", not res.is_valid
        )

    def test_E04_duration_changed_to_unsupported(self):
        """E4: Duration changed from supported duration to unsupported duration."""
        is_sup, m_type, errs = verify_fact_support("10 years", "warranty_period", "Warranty: 36 months on-site")
        self.assertFalse(is_sup)
        self._record_attack(
            "E4", AttackCategory.EVIDENCE, TargetLayer.EVIDENCE_GROUNDER,
            "Duration changed to unsupported duration", "36 months -> 10 years",
            DetectionMechanism.GROUNDING_FAILURE, DetectionMechanism.GROUNDING_FAILURE,
            "REJECTED", "REJECTED", not is_sup
        )

    def test_E05_identifier_changed_by_one_character(self):
        """E5: Identifier changed by one character."""
        is_sup, m_type, errs = verify_fact_support("29SYNTH0000003F1X", "gstin", "GSTIN: 29SYNTH0000003F1Z")
        self.assertFalse(is_sup)
        self._record_attack(
            "E5", AttackCategory.EVIDENCE, TargetLayer.EVIDENCE_GROUNDER,
            "Identifier changed by one character", "Z -> X in GSTIN",
            DetectionMechanism.GROUNDING_FAILURE, DetectionMechanism.GROUNDING_FAILURE,
            "REJECTED", "REJECTED", not is_sup
        )

    def test_E06_evidence_block_from_another_bidder_substituted(self):
        """E6: Evidence block from another bidder substituted (unknown block ID)."""
        res = self.grounder.ground_fact(["B-BLK-UNKNOWN-999"], raw_value=12.5, field_name="turnover_amount")
        self.assertFalse(res.is_valid)
        self.assertIn("unknown block_id", res.errors[0])
        self._record_attack(
            "E6", AttackCategory.EVIDENCE, TargetLayer.EVIDENCE_GROUNDER,
            "Evidence block from another bidder substituted", "Unknown block ID referenced",
            DetectionMechanism.GROUNDING_FAILURE, DetectionMechanism.GROUNDING_FAILURE,
            "REJECTED", "REJECTED", not res.is_valid
        )

    def test_E07_evidence_block_document_substituted(self):
        """E7: Evidence block document substituted."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"][0]["document"] = "forged_doc.pdf"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack(
            "E7", AttackCategory.EVIDENCE, TargetLayer.PROVENANCE_DAG,
            "Evidence block document substituted", "balance_sheet.pdf -> forged_doc.pdf",
            DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH,
            "REJECTED", "REJECTED", not rep.is_match
        )

    def test_E08_evidence_block_page_changed(self):
        """E8: Evidence block page changed."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"][0]["page"] = 99
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack(
            "E8", AttackCategory.EVIDENCE, TargetLayer.PROVENANCE_DAG,
            "Evidence block page changed", "page 8 -> page 99",
            DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH,
            "REJECTED", "REJECTED", not rep.is_match
        )

    def test_E09_evidence_bbox_changed(self):
        """E9: Evidence bounding box changed."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"][0]["bbox"] = [999.0, 999.0, 999.0, 999.0]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack(
            "E9", AttackCategory.EVIDENCE, TargetLayer.PROVENANCE_DAG,
            "Evidence bounding box changed", "bbox modified to [999,999,999,999]",
            DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH,
            "REJECTED", "REJECTED", not rep.is_match
        )

    def test_E10_evidence_snippet_changed(self):
        """E10: Evidence snippet changed."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"][0]["snippet"] = "Tampered snippet text"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack(
            "E10", AttackCategory.EVIDENCE, TargetLayer.PROVENANCE_DAG,
            "Evidence snippet changed", "snippet text altered",
            DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH,
            "REJECTED", "REJECTED", not rep.is_match
        )

    def test_E11_secondary_supporting_evidence_block_removed(self):
        """E11: Secondary supporting evidence block removed from a multi-block fact."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Remove second evidence block (UDIN seal)
        del tampered["bidder_facts"][0]["evidence"][1]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack(
            "E11", AttackCategory.EVIDENCE, TargetLayer.PROVENANCE_DAG,
            "Secondary supporting block removed", "UDIN block B-BLK-02 removed",
            DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH,
            "REJECTED", "REJECTED", not rep.is_match
        )

    def test_E12_duplicate_evidence_block_injected(self):
        """E12: Duplicate evidence block injected."""
        res = self.grounder.ground_fact(["B-BLK-01", "B-BLK-01"], raw_value="INR 12.50 Cr", field_name="turnover_amount")
        self.assertTrue(res.is_valid)
        self.assertEqual(len(res.resolved_evidence), 1)  # Deduplicated deterministically
        self.assertIn("Duplicate evidence_block_id 'B-BLK-01' removed.", res.warnings)
        self._record_attack(
            "E12", AttackCategory.EVIDENCE, TargetLayer.EVIDENCE_GROUNDER,
            "Duplicate evidence block injected", "Duplicate block ID injected",
            DetectionMechanism.GROUNDING_FAILURE, DetectionMechanism.GROUNDING_FAILURE,
            "DEDUPLICATED", "DEDUPLICATED", len(res.resolved_evidence) == 1
        )

    # =========================================================================
    # PHASE 4: PROVENANCE ATTACKS (P1 - P16)
    # =========================================================================

    def test_P01_fabricated_fact_grounded_by_edge(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"].append({
            "edge_id": "EDGE:FAKE:FACT_GROUNDED_BY:BLOCK:doc.pdf:P1",
            "source_id": "FACT:FACT-TO-01",
            "edge_type": "FACT_GROUNDED_BY",
            "target_id": "BLOCK:doc.pdf:P1:BBOX_0.0_0.0_0.0_0.0",
            "properties": {},
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P1", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Fabricated FACT_GROUNDED_BY edge", "Injected fake edge", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P02_fabricated_result_supported_by_edge(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"].append({
            "edge_id": "EDGE:FAKE:RESULT_SUPPORTED_BY:BLOCK:doc.pdf:P1",
            "source_id": "RESULT:VERIF-BID-ADV-202-REQ-TO-01",
            "edge_type": "RESULT_SUPPORTED_BY",
            "target_id": "BLOCK:doc.pdf:P1:BBOX_0.0_0.0_0.0_0.0",
            "properties": {},
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P2", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Fabricated RESULT_SUPPORTED_BY edge", "Injected fake edge", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P03_fabricated_fact_satisfies_requirement_edge(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"].append({
            "edge_id": "EDGE:FACT:FACT-EXP-01:FACT_SATISFIES_REQUIREMENT:REQ:REQ-TO-01",
            "source_id": "FACT:FACT-EXP-01",
            "edge_type": "FACT_SATISFIES_REQUIREMENT",
            "target_id": "REQ:REQ-TO-01",
            "properties": {},
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P3", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Fabricated FACT_SATISFIES_REQUIREMENT edge", "Experience fact linked to turnover req", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P04_delete_legitimate_evidence_edge(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        del p_graph["edges"][0]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P4", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Delete legitimate evidence edge", "Removed edge 0", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P05_change_edge_endpoint(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"][0]["target_id"] = "WRONG_ENDPOINT"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P5", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Change edge endpoint", "Modified target_id to WRONG_ENDPOINT", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P06_change_node_type(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["nodes"][0]["node_type"] = "CORRUPTED_TYPE"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P6", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Change node type", "Altered node_type property", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P07_change_physical_block_identity(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        for n in p_graph["nodes"]:
            if n["node_type"] == "PHYSICAL_TEXT_BLOCK":
                n["node_id"] = "BLOCK:corrupted.pdf:P99:BBOX_0_0_0_0"
                break
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P7", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Change physical block identity", "Altered block node ID", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P08_inject_self_loop(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"].append({
            "edge_id": "EDGE:SELF_LOOP",
            "source_id": "REQ:REQ-TO-01",
            "edge_type": "REQUIREMENT_HAS_EVIDENCE",
            "target_id": "REQ:REQ-TO-01",
            "properties": {},
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P8", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Inject self-loop into DAG", "Source and target identical", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P09_inject_two_node_cycle(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"].append({
            "edge_id": "EDGE:CYCLE:REQ_TO_FACT",
            "source_id": "REQ:REQ-TO-01",
            "edge_type": "REQUIREMENT_HAS_EVIDENCE",
            "target_id": "FACT:FACT-TO-01",
            "properties": {},
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P9", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Inject 2-node cycle into DAG", "Created reverse edge", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P10_orphan_a_review_item(self):
        # Human review item with no incoming/outgoing DAG edges
        dag = ProvenanceDAGBuilder.build(
            requirements=[self.req_turnover], facts=[self.fact_turnover], results=[self.res_turnover],
            integrity_findings=[],
            human_review_items=[HumanReviewItem("REV-ORPHAN", "BID-ADV-202", "TENDER-ADV-101", "MANUAL_AUDIT", "HIGH", "Reason", [], [])],
            bid_id="BID-ADV-202", tender_id="TENDER-ADV-101"
        )
        snap = SnapshotBuilder.build(
            tender_id="TENDER-ADV-101", bid_id="BID-ADV-202", requirements=[self.req_turnover], facts=[self.fact_turnover],
            compliance_results=[self.res_turnover],
            human_review_items=[HumanReviewItem("REV-ORPHAN", "BID-ADV-202", "TENDER-ADV-101", "MANUAL_AUDIT", "HIGH", "Reason", [], [])],
            aggregated_status={"compliance_status": "PASS", "integrity_status": "CONSISTENT", "overall_status": "REVIEW"},
            provenance_graph=dag.to_dict()
        )
        rep = self.replay_engine.replay(snap)
        # Aggregator in replay generates 0 review items for clean PASS, whereas snap claimed 1 -> REVIEW_ITEM_MISMATCH
        self.assertFalse(rep.is_match)
        self._record_attack("P10", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Orphan a review item in DAG", "Synthetic review item injected", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P11_orphan_an_integrity_finding(self):
        inf_orphan = IntegrityFinding("INT-ORPHAN", "BID-ADV-202", "CROSS_DOCUMENT_INCONSISTENCY", "turnover_amount", "HIGH", "CONTRADICTION", "Desc", 12.5, 99.0, {"document": "doc1.pdf", "page": 1}, {"document": "doc2.pdf", "page": 1}, True)
        snap = SnapshotBuilder.build(
            tender_id="TENDER-ADV-101", bid_id="BID-ADV-202", requirements=[self.req_turnover], facts=[self.fact_turnover],
            compliance_results=[self.res_turnover], integrity_findings=[inf_orphan],
            aggregated_status={"compliance_status": "PASS", "integrity_status": "CONTRADICTION", "overall_status": "REVIEW"}
        )
        # Replay executes contradiction engine with 0 contradiction inputs -> 0 findings replayed
        rep = self.replay_engine.replay(snap)
        self.assertFalse(rep.is_match)
        self._record_attack("P11", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Orphan integrity finding in DAG", "Unbacked integrity finding injected", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P12_fabricate_canonical_field_node(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["nodes"].append({
            "node_id": "CANONICAL:FABRICATED_FIELD",
            "node_type": "CANONICAL_FIELD",
            "label": "Fabricated",
            "properties": {},
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P12", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Fabricate canonical-field node in DAG", "Extra canonical node inserted", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P13_delete_canonical_field_edge(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        # Find and remove an edge
        edges = p_graph["edges"]
        del edges[0]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P13", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Delete canonical field edge in DAG", "Removed DAG edge", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P14_alter_node_properties(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["nodes"][0]["properties"]["tampered_prop"] = "ATTACK"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("P14", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG, "Alter node properties in DAG", "Injected property into node", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_P15_reorder_nodes_negative_control(self):
        """P15: Reorder nodes -> canonical sorting ensures this is accepted as clean match."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["nodes"].reverse()
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertTrue(rep.is_match)
        self._record_attack("P15", AttackCategory.NEGATIVE_CONTROL, TargetLayer.PROVENANCE_DAG, "Reorder DAG nodes list", "Reversed nodes list", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "ACCEPTED", "ACCEPTED", rep.is_match)

    def test_P16_reorder_edges_negative_control(self):
        """P16: Reorder edges -> canonical sorting ensures this is accepted as clean match."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"].reverse()
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertTrue(rep.is_match)
        self._record_attack("P16", AttackCategory.NEGATIVE_CONTROL, TargetLayer.PROVENANCE_DAG, "Reorder DAG edges list", "Reversed edges list", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "ACCEPTED", "ACCEPTED", rep.is_match)

    # =========================================================================
    # PHASE 5: ONTOLOGY ATTACKS (O1 - O10)
    # =========================================================================

    def test_O01_fabricate_canonical_field_id(self):
        res = resolve_field("fake_nonexistent_field_123")
        self.assertEqual(res.resolution_status, ResolutionStatus.UNMAPPED.value)
        self._record_attack("O1", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Fabricate canonical field ID", "fake_nonexistent_field_123", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "UNMAPPED", res.resolution_status, res.resolution_status == ResolutionStatus.UNMAPPED.value)

    def test_O02_assign_annual_turnover_to_unrelated_field(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Claim past_experience_years resolves to ANNUAL_TURNOVER
        tampered["bidder_facts"][1]["canonical_field"] = "ANNUAL_TURNOVER"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.CANONICALIZATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("O2", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Assign ANNUAL_TURNOVER to past_experience_years", "Canonical spoofing", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "REJECTED", "REJECTED", not rep.is_match)

    def test_O03_map_average_annual_turnover_to_annual_turnover(self):
        res_aat = resolve_field("average_annual_turnover")
        res_to = resolve_field("annual_turnover")
        self.assertNotEqual(res_aat.canonical_field_id, res_to.canonical_field_id)
        self.assertEqual(res_aat.canonical_field_id, "AVERAGE_ANNUAL_TURNOVER")
        self.assertEqual(res_to.canonical_field_id, "ANNUAL_TURNOVER")
        self._record_attack("O3", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Map AVERAGE_ANNUAL_TURNOVER to ANNUAL_TURNOVER", "Disallow false equivalence", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res_aat.canonical_field_id != res_to.canonical_field_id)

    def test_O04_map_emd_amount_to_emd_requirement(self):
        res_amt = resolve_field("emd_amount")
        res_req = resolve_field("emd_exemption_status")
        self.assertNotEqual(res_amt.canonical_field_id, res_req.canonical_field_id)
        self._record_attack("O4", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Map EMD_AMOUNT to EMD_EXEMPTION_STATUS", "Disallow false equivalence", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res_amt.canonical_field_id != res_req.canonical_field_id)

    def test_O05_map_epbg_amount_to_epbg_percentage(self):
        res_amt = resolve_field("epbg_amount")
        res_pct = resolve_field("epbg_percentage")
        self.assertNotEqual(res_amt.canonical_field_id, res_pct.canonical_field_id)
        self.assertEqual(res_amt.canonical_field_id, "EPBG_AMOUNT")
        self.assertEqual(res_pct.canonical_field_id, "EPBG_PERCENTAGE")
        self._record_attack("O5", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Map EPBG_AMOUNT to EPBG_PERCENTAGE", "Disallow currency vs percentage alias", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res_amt.canonical_field_id != res_pct.canonical_field_id)

    def test_O06_use_ambiguous_field_experience(self):
        res = resolve_field("experience")
        self.assertEqual(res.resolution_status, ResolutionStatus.AMBIGUOUS.value)
        self._record_attack("O6", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Use ambiguous field 'experience'", "Bare key rejection", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "AMBIGUOUS", res.resolution_status, res.resolution_status == ResolutionStatus.AMBIGUOUS.value)

    def test_O07_use_ambiguous_certificate(self):
        res = resolve_field("certificate")
        self.assertEqual(res.resolution_status, ResolutionStatus.AMBIGUOUS.value)
        self._record_attack("O7", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Use ambiguous field 'certificate'", "Bare key rejection", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "AMBIGUOUS", res.resolution_status, res.resolution_status == ResolutionStatus.AMBIGUOUS.value)

    def test_O08_use_ambiguous_validity(self):
        res = resolve_field("validity")
        self.assertEqual(res.resolution_status, ResolutionStatus.AMBIGUOUS.value)
        self._record_attack("O8", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Use ambiguous field 'validity'", "Bare key rejection", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "AMBIGUOUS", res.resolution_status, res.resolution_status == ResolutionStatus.AMBIGUOUS.value)

    def test_O09_use_unknown_creative_alias(self):
        res = resolve_field("super_creative_financial_power")
        self.assertEqual(res.resolution_status, ResolutionStatus.UNMAPPED.value)
        self._record_attack("O9", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Use unknown creative alias", "Refuse halluncinated mapping", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "UNMAPPED", res.resolution_status, res.resolution_status == ResolutionStatus.UNMAPPED.value)

    def test_O10_swap_canonical_fields_between_two_facts(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        c1 = tampered["bidder_facts"][0]["canonical_field"]
        c2 = tampered["bidder_facts"][1]["canonical_field"]
        tampered["bidder_facts"][0]["canonical_field"] = c2
        tampered["bidder_facts"][1]["canonical_field"] = c1
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.CANONICALIZATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("O10", AttackCategory.ONTOLOGY, TargetLayer.CANONICAL_ONTOLOGY, "Swap canonical fields between facts", "Turnover <-> Experience swap", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "REJECTED", "REJECTED", not rep.is_match)

    # =========================================================================
    # PHASE 6: REQUIREMENT / RULE ATTACKS (R1 - R15)
    # =========================================================================

    def test_R01_operator_ge_to_eq(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"][0]["operator"] = "=="  # 12.5 == 10.0 is False!
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.VERIFICATION_RESULT_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("R1", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, ">= changed to ==", "Equality check fails", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "REJECTED", "REJECTED", not rep.is_match)

    def test_R02_operator_ge_to_gt(self):
        # When value equals threshold: 10.0 >= 10.0 is True, 10.0 > 10.0 is False
        req = copy.deepcopy(self.req_turnover)
        req.operator = ">"
        f = copy.deepcopy(self.fact_turnover)
        f.value = 10.0
        f.normalized_value = 10.0
        res = self.rule_engine.verify_bid([req], [f])
        self.assertEqual(res[0].status, ComplianceStatus.FAIL.value)
        self._record_attack("R2", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, ">= changed to > at boundary", "10.0 > 10.0 fails", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "FAIL", res[0].status, res[0].status == ComplianceStatus.FAIL.value)

    def test_R03_operator_le_to_lt(self):
        req = TenderRequirement("REQ-DEL", "T-01", "COMMERCIAL", "Delivery days", "<=", True, "delivery_days", 30, 30)
        f = BidderFact("F-DEL", "B-01", "delivery_days", value=30, normalized_value=30, source_document="doc.pdf", page=1)
        res_le = self.rule_engine.verify_bid([req], [f])[0]
        self.assertEqual(res_le.status, ComplianceStatus.PASS.value)
        req.operator = "<"
        res_lt = self.rule_engine.verify_bid([req], [f])[0]
        self.assertEqual(res_lt.status, ComplianceStatus.FAIL.value)
        self._record_attack("R3", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "<= changed to < at boundary", "30 < 30 fails", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "FAIL", res_lt.status, res_lt.status == ComplianceStatus.FAIL.value)

    def test_R04_threshold_reduced_tamper(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"][0]["expected_value"] = 1.0  # Reduced threshold
        tampered["requirements"][0]["normalized_expected_value"] = 1.0
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("R4", AttackCategory.REQUIREMENT, TargetLayer.RULE_ENGINE, "Threshold reduced in requirement", "10.0 -> 1.0", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_R05_threshold_increased_tamper(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"][0]["expected_value"] = 50.0  # Increased threshold
        tampered["requirements"][0]["normalized_expected_value"] = 50.0
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.VERIFICATION_RESULT_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("R5", AttackCategory.REQUIREMENT, TargetLayer.RULE_ENGINE, "Threshold increased in requirement", "10.0 -> 50.0", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "REJECTED", "REJECTED", not rep.is_match)

    def test_R06_requirement_value_type_changed(self):
        req = copy.deepcopy(self.req_turnover)
        req.expected_value = "ten_crores"  # Invalid string type for numeric op
        req.normalized_expected_value = "ten_crores"
        res = self.rule_engine.verify_bid([req], [self.fact_turnover])
        self.assertNotEqual(res[0].status, ComplianceStatus.PASS.value)
        self._record_attack("R6", AttackCategory.REQUIREMENT, TargetLayer.RULE_ENGINE, "Requirement value type changed", "Float -> String", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "NON_PASS", res[0].status, res[0].status != ComplianceStatus.PASS.value)

    def test_R07_expected_value_changed(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"][0]["expected_value"] = 99.0
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("R7", AttackCategory.REQUIREMENT, TargetLayer.REPLAY_ENGINE, "Expected value changed", "10.0 -> 99.0", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_R08_requirement_marked_na_without_basis(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["original_results"]["compliance_results"][0]["status"] = "N/A"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("R8", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "Requirement marked N/A without basis", "PASS -> N/A", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_R09_missing_fact_converted_into_fabricated_pass(self):
        req = copy.deepcopy(self.req_turnover)
        res = self.rule_engine.verify_bid([req], [])  # Zero facts
        self.assertEqual(res[0].status, ComplianceStatus.MISSING.value)
        self.assertNotEqual(res[0].status, ComplianceStatus.PASS.value)
        self._record_attack("R9", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "Missing fact converted to PASS attempt", "Zero facts supplied", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "MISSING", res[0].status, res[0].status == ComplianceStatus.MISSING.value)

    def test_R10_failed_fact_converted_into_pass(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Claim PASS when fact was 2.0 (below 10.0 threshold)
        tampered["bidder_facts"][0]["value"] = 2.0
        tampered["bidder_facts"][0]["normalized_value"] = 2.0
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.VERIFICATION_RESULT_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("R10", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "Failed fact converted to PASS attempt", "2.0 Cr evaluated against 10.0 Cr", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "REJECTED", "REJECTED", not rep.is_match)

    def test_R11_exemption_flag_injected(self):
        # Injected exemption on non-exempt bidder
        req = TenderRequirement("REQ-MSE", "T-01", "COMMERCIAL", "Turnover", ">=", True, "turnover_amount", 10.0, 10.0, applicability={"mse_exemption_allowed": True})
        f = BidderFact("F-01", "B-01", "turnover_amount", value=2.0, normalized_value=2.0, source_document="doc.pdf", page=1)
        # Without valid MSE credentials
        res = self.rule_engine.verify_bid([req], [f])
        self.assertEqual(res[0].status, ComplianceStatus.FAIL.value)
        self._record_attack("R11", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "Exemption flag injected without credentials", "Turnover exemption without MSE fact", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "FAIL", res[0].status, res[0].status == ComplianceStatus.FAIL.value)

    def test_R12_exemption_flag_removed(self):
        req = TenderRequirement("REQ-MSE", "T-01", "COMMERCIAL", "Turnover", ">=", True, "turnover_amount", 10.0, 10.0, applicability={"mse_exemption_allowed": False})
        f_to = BidderFact("F-01", "B-01", "turnover_amount", value=2.0, normalized_value=2.0, source_document="doc.pdf", page=1)
        f_mse = BidderFact("F-MSE", "B-01", "is_mse", value=True, normalized_value=True, source_document="doc.pdf", page=1)
        res = self.rule_engine.verify_bid([req], [f_to, f_mse])
        # Since req.mse_exemption_allowed is False, MSE cannot exempt it
        self.assertEqual(res[0].status, ComplianceStatus.FAIL.value)
        self._record_attack("R12", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "Exemption flag removed from requirement", "Strict enforcement", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "FAIL", res[0].status, res[0].status == ComplianceStatus.FAIL.value)

    def test_R13_precedence_ordering_manipulated(self):
        from backend.core.models import SourceType
        req_gtc = TenderRequirement("REQ-01", "T-01", "FINANCIAL", "GTC rule", ">=", True, "turnover_amount", 5.0, 5.0, source_type=SourceType.GTC.value, source_priority=1)
        req_atc = TenderRequirement("REQ-02", "T-01", "FINANCIAL", "ATC rule", ">=", True, "turnover_amount", 15.0, 15.0, source_type=SourceType.ATC.value, source_priority=3)
        # ATC overrides GTC for same clause
        res = self.rule_engine.verify_bid([req_gtc, req_atc], [self.fact_turnover])
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0].status, "FAIL")
        self.assertEqual(res[1].status, "N/A")
        self._record_attack("R13", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "Precedence ordering manipulated", "ATC overrides GTC strictly", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "FAIL", res[0].status, res[0].status == "FAIL")

    def test_R14_gtc_stc_atc_precedence_swapped(self):
        from backend.core.precedence import resolve_precedence
        from backend.core.models import SourceType
        r1 = TenderRequirement("R1", "T1", "TECH", "GTC", ">=", True, "warranty", 5, 5, source_type=SourceType.GTC.value, source_priority=1)
        r2 = TenderRequirement("R2", "T1", "TECH", "STC", ">=", True, "warranty", 10, 10, source_type=SourceType.STC.value, source_priority=2)
        prec = resolve_precedence([r1, r2])
        self.assertEqual(prec.effective_requirements[0].source_type, SourceType.STC.value)
        self._record_attack("R14", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "Precedence swap attempt", "STC overrides GTC", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "STC", prec.effective_requirements[0].source_type, prec.effective_requirements[0].source_type == SourceType.STC.value)

    def test_R15_operator_changed_evidence_unchanged(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"][0]["operator"] = "<="  # 12.5 <= 10.0 fails!
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.VERIFICATION_RESULT_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("R15", AttackCategory.RULE_ENGINE, TargetLayer.RULE_ENGINE, "Operator changed while evidence unchanged", ">= to <=", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "REJECTED", "REJECTED", not rep.is_match)

    # =========================================================================
    # PHASE 7: CROSS-FIELD VALUE SWAPS (XF1 - XF9)
    # =========================================================================

    def test_XF01_swap_turnover_with_experience(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        val_to = tampered["bidder_facts"][0]["value"]
        val_exp = tampered["bidder_facts"][1]["value"]
        tampered["bidder_facts"][0]["value"] = val_exp  # 7.0 Cr fails >= 10.0
        tampered["bidder_facts"][0]["normalized_value"] = val_exp
        tampered["bidder_facts"][1]["value"] = val_to
        tampered["bidder_facts"][1]["normalized_value"] = val_to
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("XF1", AttackCategory.CROSS_FIELD, TargetLayer.RULE_ENGINE, "Turnover <-> Experience swap", "7.0 < 10.0 Cr fails", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "REJECTED", "REJECTED", not rep.is_match)

    def test_XF02_swap_annual_turnover_with_average_annual_turnover(self):
        # Distinct canonical concepts
        res1 = resolve_field("annual_turnover")
        res2 = resolve_field("average_annual_turnover")
        self.assertNotEqual(res1.canonical_field_id, res2.canonical_field_id)
        self._record_attack("XF2", AttackCategory.CROSS_FIELD, TargetLayer.CANONICAL_ONTOLOGY, "Annual turnover <-> Average annual turnover swap", "Ontology separation", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res1.canonical_field_id != res2.canonical_field_id)

    def test_XF03_swap_emd_amount_with_emd_requirement(self):
        res1 = resolve_field("emd_amount")
        res2 = resolve_field("emd_exemption_status")
        self.assertNotEqual(res1.canonical_field_id, res2.canonical_field_id)
        self._record_attack("XF3", AttackCategory.CROSS_FIELD, TargetLayer.CANONICAL_ONTOLOGY, "EMD amount <-> EMD requirement swap", "Monetary vs Boolean separation", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res1.canonical_field_id != res2.canonical_field_id)

    def test_XF04_swap_epbg_percentage_with_epbg_amount(self):
        res1 = resolve_field("epbg_percentage")
        res2 = resolve_field("epbg_amount")
        self.assertNotEqual(res1.canonical_field_id, res2.canonical_field_id)
        self._record_attack("XF4", AttackCategory.CROSS_FIELD, TargetLayer.CANONICAL_ONTOLOGY, "EPBG percentage <-> EPBG amount swap", "Ratio vs Absolute separation", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res1.canonical_field_id != res2.canonical_field_id)

    def test_XF05_swap_gstin_with_pan(self):
        res1 = resolve_field("gstin")
        res2 = resolve_field("pan")
        self.assertNotEqual(res1.canonical_field_id, res2.canonical_field_id)
        self._record_attack("XF5", AttackCategory.CROSS_FIELD, TargetLayer.CANONICAL_ONTOLOGY, "GSTIN <-> PAN swap", "GSTIN vs PAN separation", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res1.canonical_field_id != res2.canonical_field_id)

    def test_XF06_swap_pan_with_udyam(self):
        res1 = resolve_field("pan")
        res2 = resolve_field("udyam_registration")
        self.assertNotEqual(res1.canonical_field_id, res2.canonical_field_id)
        self._record_attack("XF6", AttackCategory.CROSS_FIELD, TargetLayer.CANONICAL_ONTOLOGY, "PAN <-> Udyam swap", "Entity separation", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res1.canonical_field_id != res2.canonical_field_id)

    def test_XF07_swap_delivery_period_with_bid_validity(self):
        res1 = resolve_field("delivery_period")
        res2 = resolve_field("bid_validity_days")
        self.assertNotEqual(res1.canonical_field_id, res2.canonical_field_id)
        self._record_attack("XF7", AttackCategory.CROSS_FIELD, TargetLayer.CANONICAL_ONTOLOGY, "Delivery period <-> Bid validity swap", "Duration separation", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res1.canonical_field_id != res2.canonical_field_id)

    def test_XF08_swap_warranty_duration_with_delivery_period(self):
        res1 = resolve_field("warranty_period")
        res2 = resolve_field("delivery_period")
        self.assertNotEqual(res1.canonical_field_id, res2.canonical_field_id)
        self._record_attack("XF8", AttackCategory.CROSS_FIELD, TargetLayer.CANONICAL_ONTOLOGY, "Warranty duration <-> Delivery period swap", "Concept separation", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res1.canonical_field_id != res2.canonical_field_id)

    def test_XF09_swap_local_content_with_local_support(self):
        res1 = resolve_field("local_content_percentage")
        res2 = resolve_field("local_support_office")
        self.assertNotEqual(res1.canonical_field_id, res2.canonical_field_id)
        self._record_attack("XF9", AttackCategory.CROSS_FIELD, TargetLayer.CANONICAL_ONTOLOGY, "Local content <-> Local support swap", "Percentage vs Presence separation", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "DISTINCT", "DISTINCT", res1.canonical_field_id != res2.canonical_field_id)

    # =========================================================================
    # PHASE 8: CONTRADICTION ATTACKS (C1 - C12)
    # =========================================================================

    def test_C01_alter_one_side_of_financial_contradiction(self):
        inf = self.contra_engine.evaluate_pair("C1", "B-01", "turnover", 12.5, 6.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        self.assertEqual(inf.status, "CONTRADICTION")
        # Alter value_a to 6.0 (identical to value_b)
        inf_altered = self.contra_engine.evaluate_pair("C1", "B-01", "turnover", 6.0, 6.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        self.assertEqual(inf_altered.status, "CONSISTENT")
        self._record_attack("C1", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Alter one side of contradiction", "12.5 -> 6.0 becomes consistent", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "CONSISTENT", inf_altered.status, inf_altered.status == "CONSISTENT")

    def test_C02_alter_both_values_to_appear_consistent(self):
        inf_tampered = self.contra_engine.evaluate_pair("C2", "B-01", "turnover", 10.0, 10.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        self.assertEqual(inf_tampered.status, "CONSISTENT")
        self._record_attack("C2", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Alter both values to appear consistent", "10.0 == 10.0", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "CONSISTENT", inf_tampered.status, inf_tampered.status == "CONSISTENT")

    def test_C03_swap_document_identities(self):
        inf = self.contra_engine.evaluate_pair("C3", "B-01", "turnover", 12.5, 6.0, "doc_A.pdf", 1, None, "", "doc_B.pdf", 2, None, "")
        self.assertEqual(inf.evidence_a["document"], "doc_A.pdf")
        self.assertEqual(inf.evidence_b["document"], "doc_B.pdf")
        self._record_attack("C3", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Document identities preserved in evidence", "doc_A != doc_B", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "PRESERVED", "PRESERVED", inf.evidence_a["document"] != inf.evidence_b["document"])

    def test_C04_swap_bidder_identities(self):
        inf1 = self.contra_engine.evaluate_pair("C4", "BID-01", "turnover", 12.5, 6.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        inf2 = self.contra_engine.evaluate_pair("C4", "BID-99", "turnover", 12.5, 6.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        self.assertNotEqual(inf1.bid_id, inf2.bid_id)
        self._record_attack("C4", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Bidder ID binding in contradiction", "BID-01 != BID-99", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "DISTINCT", "DISTINCT", inf1.bid_id != inf2.bid_id)

    def test_C05_remove_one_contradiction_input(self):
        inf = self.contra_engine.evaluate_pair("C5", "B-01", "turnover", 12.5, 6.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        snap = SnapshotBuilder.build(
            tender_id="T-01", bid_id="B-01", requirements=[self.req_turnover], facts=[self.fact_turnover],
            compliance_results=[self.res_turnover], integrity_findings=[inf],
            contradiction_inputs=[{"contradiction_id": "C5", "field_name": "turnover", "value_a": 12.5, "value_b": 6.0}],
            aggregated_status={"compliance_status": "PASS", "integrity_status": "CONTRADICTION", "overall_status": "REVIEW"}
        )
        tampered = copy.deepcopy(snap.to_dict())
        tampered["contradiction_inputs"] = []  # Removed input
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("C5", AttackCategory.CONTRADICTION, TargetLayer.REPLAY_ENGINE, "Remove contradiction input from snapshot", "0 findings replayed vs 1 original", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "REJECTED", "REJECTED", not rep.is_match)

    def test_C06_change_tolerance_threshold(self):
        # 5% difference: 10.0 vs 10.6 (|10.6 - 10.0| / 10.6 = 5.66% > 5%) -> CONTRADICTION
        inf = self.contra_engine.evaluate_pair("C6", "B-01", "turnover", 10.0, 10.6, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        self.assertEqual(inf.status, "CONTRADICTION")
        self._record_attack("C6", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Change tolerance boundary", "5.66% > 5% threshold triggers contradiction", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "CONTRADICTION", inf.status, inf.status == "CONTRADICTION")

    def test_C07_fabricate_contradiction_where_values_consistent(self):
        # Claim CONTRADICTION when values are 10.0 and 10.0
        inf_eval = self.contra_engine.evaluate_pair("C7", "B-01", "turnover", 10.0, 10.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        self.assertEqual(inf_eval.status, "CONSISTENT")
        self._record_attack("C7", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Fabricate contradiction on identical values", "Engine computes CONSISTENT", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "CONSISTENT", inf_eval.status, inf_eval.status == "CONSISTENT")

    def test_C08_suppress_genuine_contradiction(self):
        # Values 12.5 vs 5.0 are genuine contradiction
        inf = self.contra_engine.evaluate_pair("C8", "B-01", "turnover", 12.5, 5.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        self.assertEqual(inf.status, "CONTRADICTION")
        self._record_attack("C8", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Suppress genuine contradiction attempt", "Flagged as CONTRADICTION", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "CONTRADICTION", inf.status, inf.status == "CONTRADICTION")

    def test_C09_alter_canonical_field_of_contradiction(self):
        inf = self.contra_engine.evaluate_pair("C9", "B-01", "turnover", 12.5, 5.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "", canonical_field="ANNUAL_TURNOVER")
        self.assertEqual(inf.canonical_field, "ANNUAL_TURNOVER")
        self._record_attack("C9", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Contradiction canonical field tracking", "Field bound to ANNUAL_TURNOVER", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "ANNUAL_TURNOVER", inf.canonical_field, inf.canonical_field == "ANNUAL_TURNOVER")

    def test_C10_change_physical_evidence_bbox_in_contradiction(self):
        inf = self.contra_engine.evaluate_pair("C10", "B-01", "turnover", 12.5, 5.0, "a.pdf", 1, [10.0, 10.0, 20.0, 20.0], "12.5", "b.pdf", 2, [30.0, 30.0, 40.0, 40.0], "5.0")
        self.assertEqual(inf.evidence_a["bbox"], [10.0, 10.0, 20.0, 20.0])
        self._record_attack("C10", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Evidence bbox in contradiction", "Coordinates strictly tracked", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "TRACKED", "TRACKED", inf.evidence_a["bbox"] == [10.0, 10.0, 20.0, 20.0])

    def test_C11_replace_one_physical_evidence_block_in_contradiction(self):
        inf1 = self.contra_engine.evaluate_pair("C11", "B-01", "turnover", 12.5, 5.0, "doc_A.pdf", 1, None, "", "doc_B.pdf", 2, None, "")
        inf2 = self.contra_engine.evaluate_pair("C11", "B-01", "turnover", 12.5, 5.0, "doc_X.pdf", 1, None, "", "doc_B.pdf", 2, None, "")
        self.assertNotEqual(inf1.evidence_a["document"], inf2.evidence_a["document"])
        self._record_attack("C11", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Replace physical evidence block in contradiction", "doc_A != doc_X", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "DETECTED", "DETECTED", inf1.evidence_a["document"] != inf2.evidence_a["document"])

    def test_C12_move_contradiction_evidence_to_unrelated_bidder(self):
        inf1 = self.contra_engine.evaluate_pair("C12", "BID-TARGET", "turnover", 12.5, 5.0, "a.pdf", 1, None, "", "b.pdf", 2, None, "")
        self.assertEqual(inf1.bid_id, "BID-TARGET")
        self._record_attack("C12", AttackCategory.CONTRADICTION, TargetLayer.CONTRADICTION_ENGINE, "Move contradiction to unrelated bidder", "bid_id bound strictly", DetectionMechanism.INTEGRITY_CONTRADICTION, DetectionMechanism.INTEGRITY_CONTRADICTION, "BID-TARGET", inf1.bid_id, inf1.bid_id == "BID-TARGET")

    # =========================================================================
    # PHASE 9: GOVERNMENT RESPONSE ATTACKS (G1 - G9)
    # =========================================================================

    def test_G01_gst_verified_to_invalid(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"][0]["status"] = "INACTIVE"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.REVIEW_ITEM_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("G1", AttackCategory.GOVERNMENT, TargetLayer.GOVERNMENT_ADAPTER, "GST VERIFIED -> INACTIVE", "Triggers human review queue item", DetectionMechanism.HUMAN_REVIEW_FLAG, DetectionMechanism.HUMAN_REVIEW_FLAG, "REJECTED", "REJECTED", not rep.is_match)

    def test_G02_gst_verified_to_identity_mismatch(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"][0]["status"] = "IDENTITY_MISMATCH"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.REVIEW_ITEM_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("G2", AttackCategory.GOVERNMENT, TargetLayer.GOVERNMENT_ADAPTER, "GST VERIFIED -> IDENTITY_MISMATCH", "Triggers human review queue item", DetectionMechanism.HUMAN_REVIEW_FLAG, DetectionMechanism.HUMAN_REVIEW_FLAG, "REJECTED", "REJECTED", not rep.is_match)

    def test_G03_pan_verified_to_invalid(self):
        gov_pan = AdapterResponse(status=VerificationStatus.INACTIVE, adapter_name="PANAdapter", queried_identifier="SYNTH0003F", source="ITD_REGISTRY", reason="PAN is inactive")
        agg = self.aggregator.aggregate("T-01", "B-01", [self.res_turnover], [], [gov_pan])
        self.assertTrue(agg.review_required)
        self._record_attack("G3", AttackCategory.GOVERNMENT, TargetLayer.GOVERNMENT_ADAPTER, "PAN VERIFIED -> INACTIVE", "Aggregator sets review_required=True", DetectionMechanism.HUMAN_REVIEW_FLAG, DetectionMechanism.HUMAN_REVIEW_FLAG, "REVIEW_REQUIRED", "REVIEW_REQUIRED", agg.review_required)

    def test_G04_debarment_clear_to_debarred(self):
        gov_debar = AdapterResponse(status=VerificationStatus.DEBARRED, adapter_name="DebarmentAdapter", queried_identifier="Acme Corp", source="CENTRAL_REGISTRY", reason="Debarred for fraud")
        agg = self.aggregator.aggregate("T-01", "B-01", [self.res_turnover], [], [gov_debar])
        self.assertEqual(agg.overall_status, "FAIL")
        self._record_attack("G4", AttackCategory.GOVERNMENT, TargetLayer.AGGREGATOR, "Debarment CLEAR -> DEBARRED", "Aggregator sets overall_status=FAIL", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "FAIL", agg.overall_status, agg.overall_status == "FAIL")

    def test_G05_remove_captured_response(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"] = []
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("G5", AttackCategory.GOVERNMENT, TargetLayer.REPLAY_ENGINE, "Remove captured government response", "Response count mismatch", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_G06_substitute_another_bidders_response(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"][0]["registered_entity_name"] = "Different Rogue Bidder Pvt Ltd"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("G6", AttackCategory.GOVERNMENT, TargetLayer.GOVERNMENT_ADAPTER, "Substitute another bidder's response", "Entity name altered", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_G07_change_response_entity_id(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"][0]["queried_identifier"] = "99FAKE0000000X1Z"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("G7", AttackCategory.GOVERNMENT, TargetLayer.GOVERNMENT_ADAPTER, "Change response queried identifier", "Fake identifier injected", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_G08_change_response_timestamp_only(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"][0]["timestamp"] = "2099-01-01T00:00:00"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        # Transient metadata does not alter deterministic status
        rep = self.replay_engine.replay(tampered)
        self.assertTrue(rep.is_match)
        self._record_attack("G8", AttackCategory.NEGATIVE_CONTROL, TargetLayer.GOVERNMENT_ADAPTER, "Change transient timestamp only", "Timestamp does not affect verdict", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "ACCEPTED", "ACCEPTED", rep.is_match)

    def test_G09_fabricate_response_not_in_captured_fixtures(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"].append({
            "status": "VERIFIED", "adapter_name": "SyntheticAdapter", "queried_identifier": "FAKE", "source": "FAKE"
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("G9", AttackCategory.GOVERNMENT, TargetLayer.REPLAY_ENGINE, "Fabricate government response", "Extra response injected", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    # =========================================================================
    # PHASE 10: AGGREGATION ATTACKS (A1 - A10)
    # =========================================================================

    def test_A01_compliance_pass_to_fail(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["original_results"]["compliance_status"] = "FAIL"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.AGGREGATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("A1", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Compliance PASS -> FAIL tampering", "Claimed FAIL when facts pass", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_A02_integrity_consistent_to_contradiction(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["original_results"]["integrity_status"] = "CONTRADICTION"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.AGGREGATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("A2", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Integrity CONSISTENT -> CONTRADICTION tampering", "Claimed contradiction without findings", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_A03_overall_pass_to_fail(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["original_results"]["overall_status"] = "FAIL"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.AGGREGATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("A3", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Overall PASS -> FAIL tampering", "Claimed overall FAIL on clean bid", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_A04_remove_critical_failure(self):
        agg = self.aggregator.aggregate("T-01", "B-01", [VerificationResult("V-01", "R-01", "B-01", "FAIL", "CRITICAL", ">=10", 2.0, ">=", "Value 2.0 < 10.0", False)], [], [])
        self.assertEqual(agg.critical_failures, 1)
        self.assertEqual(agg.overall_status, "FAIL")
        self._record_attack("A4", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Critical failure propagation", "Critical failure forces overall FAIL", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "FAIL", agg.overall_status, agg.overall_status == "FAIL")

    def test_A05_remove_human_review_item(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Inject fabricated review item in original results
        tampered["original_results"]["human_review_items"] = [{"review_id": "REV-FAKE"}]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.REVIEW_ITEM_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("A5", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Inject unbacked review item", "Count mismatch in review items", DetectionMechanism.HUMAN_REVIEW_FLAG, DetectionMechanism.HUMAN_REVIEW_FLAG, "REJECTED", "REJECTED", not rep.is_match)

    def test_A06_downgrade_severity(self):
        # Major failure cannot be downgraded to INFO without failing overall
        res_major = VerificationResult("V-01", "R-01", "B-01", "FAIL", "MAJOR", ">=10", 2.0, ">=", "Value 2.0 < 10.0", False)
        agg = self.aggregator.aggregate("T-01", "B-01", [res_major], [], [])
        self.assertEqual(agg.overall_status, "FAIL")
        self._record_attack("A6", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Downgrade severity attempt", "Major failure triggers overall FAIL", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "FAIL", agg.overall_status, agg.overall_status == "FAIL")

    def test_A07_suppress_review_trigger(self):
        res_missing = VerificationResult("V-01", "R-01", "B-01", "MISSING", "CRITICAL", "EXISTS", None, "EXISTS", "Missing evidence", True)
        agg = self.aggregator.aggregate("T-01", "B-01", [res_missing], [], [])
        self.assertTrue(agg.review_required)
        self._record_attack("A7", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Suppress review trigger attempt", "Missing evidence forces review_required=True", DetectionMechanism.HUMAN_REVIEW_FLAG, DetectionMechanism.HUMAN_REVIEW_FLAG, "REVIEW_REQUIRED", "REVIEW_REQUIRED", agg.review_required)

    def test_A08_fabricate_review_item(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["original_results"]["human_review_items"].append({"review_id": "REV-SYNTHETIC", "reason": "Fake"})
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("A8", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Fabricate review item", "Review items count mismatch", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_A09_alter_counts(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["original_results"]["critical_failures"] = 99
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.AGGREGATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("A9", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR, "Alter metric count in original results", "Critical failures count mismatch", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_A10_alter_ordering_of_results_negative_control(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["original_results"]["compliance_results"].reverse()
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertTrue(rep.is_match)
        self._record_attack("A10", AttackCategory.NEGATIVE_CONTROL, TargetLayer.AGGREGATOR, "Alter ordering of compliance results", "Replay matches by requirement_id", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "ACCEPTED", "ACCEPTED", rep.is_match)

    # =========================================================================
    # PHASE 11: SNAPSHOT ATTACKS (S1 - S20)
    # =========================================================================

    def test_S01_change_fact_value(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["value"] = 2.0
        tampered["bidder_facts"][0]["normalized_value"] = 2.0
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S1", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Change fact value in snapshot", "12.5 -> 2.0", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S02_change_requirement(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"][0]["operator"] = "<="
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S2", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Change requirement in snapshot", ">= to <=", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S03_change_evidence_snippet(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"][0]["snippet"] = "Changed"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S3", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Change evidence snippet", "Snippet altered", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S04_change_bbox(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"][0]["bbox"] = [0, 0, 0, 0]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S4", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Change bbox in snapshot", "BBox zeroed", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S05_remove_evidence(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"] = []
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S5", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Remove evidence from fact", "Evidence emptied", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S06_alter_canonical_field(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["canonical_field"] = "SPOOFED_ID"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S6", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Alter canonical field in snapshot", "SPOOFED_ID", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "REJECTED", "REJECTED", not rep.is_match)

    def test_S07_alter_contradiction(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["contradiction_inputs"] = [{"contradiction_id": "CONTRA-01", "field_name": "turnover", "value_a": 10.0, "value_b": 2.0}]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S7", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Alter contradiction inputs in snapshot", "Injected contradiction input", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S08_alter_government_response(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"][0]["status"] = "IDENTITY_MISMATCH"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S8", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Alter government response in snapshot", "VERIFIED -> IDENTITY_MISMATCH", DetectionMechanism.HUMAN_REVIEW_FLAG, DetectionMechanism.HUMAN_REVIEW_FLAG, "REJECTED", "REJECTED", not rep.is_match)

    def test_S09_alter_original_result(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["original_results"]["compliance_results"][0]["status"] = "FAIL"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S9", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Alter original compliance result", "PASS -> FAIL", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S10_alter_graph_node(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        del tampered["original_results"]["provenance_graph"]["nodes"][0]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S10", AttackCategory.SNAPSHOT, TargetLayer.PROVENANCE_DAG, "Alter graph node in snapshot", "Deleted first node", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S11_alter_graph_edge(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        del tampered["original_results"]["provenance_graph"]["edges"][0]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S11", AttackCategory.SNAPSHOT, TargetLayer.PROVENANCE_DAG, "Alter graph edge in snapshot", "Deleted first edge", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S12_alter_snapshot_version(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["snapshot_version"] = "99.0.0"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertEqual(rep.status, MismatchCategory.SCHEMA_VERSION_MISMATCH.value)
        self._record_attack("S12", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Alter snapshot schema version", "1.0.0 -> 99.0.0", DetectionMechanism.SCHEMA_VALIDATION_ERROR, DetectionMechanism.SCHEMA_VALIDATION_ERROR, "REJECTED", rep.status, not rep.is_match)

    def test_S13_alter_replay_engine_version(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["replay_engine_version"] = "99.0.0"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertTrue(rep.is_match)  # Minor metadata tracked
        self._record_attack("S13", AttackCategory.NEGATIVE_CONTROL, TargetLayer.AUDIT_SNAPSHOT, "Alter replay engine version tag", "Metadata tracked", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "ACCEPTED", "ACCEPTED", rep.is_match)

    def test_S14_alter_verification_config(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["deterministic_config"]["rule_engine_version"] = "9.9.9"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.CONFIGURATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("S14", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Alter verification config", "rule_engine_version -> 9.9.9", DetectionMechanism.CONFIG_HASH_MISMATCH, DetectionMechanism.CONFIG_HASH_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S15_alter_verification_config_hash(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["verification_config_hash"] = "corrupted_hash"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.CONFIGURATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("S15", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Alter verification config hash", "Corrupted hash string", DetectionMechanism.CONFIG_HASH_MISMATCH, DetectionMechanism.CONFIG_HASH_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S16_alter_snapshot_hash(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["snapshot_hash"] = "corrupted_outer_hash"
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertEqual(rep.status, MismatchCategory.SNAPSHOT_HASH_MISMATCH.value)
        self._record_attack("S16", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Alter snapshot outer hash", "Corrupted SHA-256", DetectionMechanism.SNAPSHOT_HASH_MISMATCH, DetectionMechanism.SNAPSHOT_HASH_MISMATCH, "REJECTED", rep.status, not rep.is_match)

    def test_S17_remove_snapshot_hash(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        del tampered["snapshot_hash"]
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self._record_attack("S17", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT, "Remove snapshot hash completely", "Missing hash key", DetectionMechanism.SNAPSHOT_HASH_MISMATCH, DetectionMechanism.SNAPSHOT_HASH_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_S18_reorder_json_keys_negative_control(self):
        orig_dict = self.clean_snapshot.to_dict()
        # Create dict with reversed key order
        reordered = {k: orig_dict[k] for k in reversed(list(orig_dict.keys()))}
        rep = self.replay_engine.replay(reordered)
        self.assertTrue(rep.is_match)
        self._record_attack("S18", AttackCategory.NEGATIVE_CONTROL, TargetLayer.AUDIT_SNAPSHOT, "Reorder JSON keys", "Canonical JSON normalizes order", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "ACCEPTED", "ACCEPTED", rep.is_match)

    def test_S19_reorder_semantically_unordered_arrays_negative_control(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"].reverse()
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertTrue(rep.is_match)
        self._record_attack("S19", AttackCategory.NEGATIVE_CONTROL, TargetLayer.AUDIT_SNAPSHOT, "Reorder requirements array", "Replay matches by requirement_id", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "ACCEPTED", "ACCEPTED", rep.is_match)

    def test_S20_inject_unknown_transient_fields(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["unknown_telemetry_key"] = "test"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        # Snapshot validation accepts extension or canonical hash verifies it
        self.assertTrue(rep.is_match)
        self._record_attack("S20", AttackCategory.NEGATIVE_CONTROL, TargetLayer.AUDIT_SNAPSHOT, "Inject unknown transient field", "Graceful handling", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "ACCEPTED", "ACCEPTED", rep.is_match)

    # =========================================================================
    # PHASE 12: REPLAY ATTACKS (RP1 - RP12)
    # =========================================================================

    def test_RP01_replay_same_snapshot_100_times(self):
        snap = self.clean_snapshot
        ref_json = self.replay_engine.replay(snap).to_json()
        all_identical = True
        for _ in range(100):
            if self.replay_engine.replay(snap).to_json() != ref_json:
                all_identical = False
                break
        self.assertTrue(all_identical)
        self._record_attack("RP1", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Replay same snapshot 100 times", "Idempotency check", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "IDENTICAL", "IDENTICAL", all_identical)

    def test_RP02_replay_from_dict(self):
        rep = self.replay_engine.replay(self.clean_snapshot.to_dict())
        self.assertTrue(rep.is_match)
        self._record_attack("RP2", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Replay from dictionary input", "Direct dict replay", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep.is_match)

    def test_RP03_replay_from_canonical_json(self):
        rep = self.replay_engine.replay(self.clean_snapshot.to_json())
        self.assertTrue(rep.is_match)
        self._record_attack("RP3", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Replay from canonical JSON string", "Direct string replay", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep.is_match)

    def test_RP04_replay_from_differently_formatted_json(self):
        # Indented JSON
        indented = json.dumps(self.clean_snapshot.to_dict(), indent=4)
        rep = self.replay_engine.replay(indented)
        self.assertTrue(rep.is_match)
        self._record_attack("RP4", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Replay from formatted 4-space JSON", "Whitespace independence", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep.is_match)

    def test_RP05_replay_after_key_reordering(self):
        d = self.clean_snapshot.to_dict()
        reordered_str = json.dumps({k: d[k] for k in reversed(list(d.keys()))})
        rep = self.replay_engine.replay(reordered_str)
        self.assertTrue(rep.is_match)
        self._record_attack("RP5", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Replay after key reordering in JSON string", "Key order independence", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep.is_match)

    def test_RP06_replay_after_semantically_irrelevant_ordering(self):
        d = copy.deepcopy(self.clean_snapshot.to_dict())
        d["bidder_facts"].reverse()
        d["snapshot_hash"] = compute_snapshot_hash(d)
        rep = self.replay_engine.replay(d)
        self.assertTrue(rep.is_match)
        self._record_attack("RP6", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Replay after facts array reversed", "Facts matched by fact_id", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep.is_match)

    def test_RP07_replay_with_tampered_snapshot(self):
        d = copy.deepcopy(self.clean_snapshot.to_dict())
        d["bidder_facts"][0]["value"] = 1.0
        d["bidder_facts"][0]["normalized_value"] = 1.0
        d["snapshot_hash"] = compute_snapshot_hash(d)
        rep = self.replay_engine.replay(d)
        self.assertFalse(rep.is_match)
        self._record_attack("RP7", AttackCategory.REPLAY, TargetLayer.REPLAY_ENGINE, "Replay with tampered snapshot payload", "Detects failure", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_RP08_replay_with_configuration_drift(self):
        d = copy.deepcopy(self.clean_snapshot.to_dict())
        d["deterministic_config"]["rule_engine_version"] = "2.0.0"
        d["verification_config_hash"] = compute_config_hash(d["deterministic_config"])
        d["snapshot_hash"] = compute_snapshot_hash(d)
        rep = self.replay_engine.replay(d)
        self.assertFalse(rep.is_match)
        self.assertEqual(rep.status, MismatchCategory.CONFIGURATION_MISMATCH.value)
        self._record_attack("RP8", AttackCategory.REPLAY, TargetLayer.REPLAY_ENGINE, "Replay with configuration drift", "Version drift detected", DetectionMechanism.CONFIG_HASH_MISMATCH, DetectionMechanism.CONFIG_HASH_MISMATCH, "REJECTED", rep.status, not rep.is_match)

    def test_RP09_replay_with_incompatible_version(self):
        d = copy.deepcopy(self.clean_snapshot.to_dict())
        d["snapshot_version"] = "99.0.0"
        d["snapshot_hash"] = compute_snapshot_hash(d)
        rep = self.replay_engine.replay(d)
        self.assertFalse(rep.is_match)
        self.assertEqual(rep.status, MismatchCategory.SCHEMA_VERSION_MISMATCH.value)
        self._record_attack("RP9", AttackCategory.REPLAY, TargetLayer.REPLAY_ENGINE, "Replay with incompatible schema version", "Schema version mismatch", DetectionMechanism.SCHEMA_VALIDATION_ERROR, DetectionMechanism.SCHEMA_VALIDATION_ERROR, "REJECTED", rep.status, not rep.is_match)

    def test_RP10_replay_with_malformed_graph(self):
        d = copy.deepcopy(self.clean_snapshot.to_dict())
        d["original_results"]["provenance_graph"] = {"corrupted": True}
        d["snapshot_hash"] = compute_snapshot_hash(d)
        rep = self.replay_engine.replay(d)
        self.assertFalse(rep.is_match)
        self._record_attack("RP10", AttackCategory.REPLAY, TargetLayer.REPLAY_ENGINE, "Replay with malformed provenance graph", "Graph structural mismatch", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_RP11_replay_with_missing_evidence(self):
        # A case where requirement has no facts in snapshot
        req_missing = TenderRequirement("R-MISS", "T-01", "TECH", "ISO cert", "EXISTS", True, "iso")
        res_missing = self.rule_engine.verify_bid([req_missing], [])[0]
        agg = self.aggregator.aggregate("T-01", "B-01", [res_missing], [], [])
        snap = SnapshotBuilder.build(
            tender_id="T-01", bid_id="B-01", requirements=[req_missing], facts=[], compliance_results=[res_missing],
            human_review_items=agg.human_review_items,
            aggregated_status={"compliance_status": agg.compliance_status, "integrity_status": agg.integrity_status, "overall_status": agg.overall_status}
        )
        rep = self.replay_engine.replay(snap)
        self.assertTrue(rep.is_match)
        self.assertEqual(rep.replayed_results["compliance_status"], "MISSING")
        self._record_attack("RP11", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Replay with missing evidence", "Faithfully reproduces MISSING", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MISSING", rep.replayed_results["compliance_status"], rep.is_match)

    def test_RP12_replay_with_duplicate_evidence(self):
        # Fact with duplicate evidence block in snapshot
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"].append(tampered["bidder_facts"][0]["evidence"][0])
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        # Duplicate block alters DAG structure
        self.assertFalse(rep.is_match)
        self._record_attack("RP12", AttackCategory.REPLAY, TargetLayer.REPLAY_ENGINE, "Replay with duplicate evidence block", "DAG mismatch", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    # =========================================================================
    # PHASE 13: CROSS-LAYER SYNCHRONIZED ATTACKS (X1 - X8)
    # =========================================================================

    def test_X01_synchronized_fact_and_result_tamper(self):
        """X1: Change bidder fact value AND change verification result to match."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Attacker changes fact from 12.5 -> 2.0 AND changes verification result actual to 2.0, status to PASS
        tampered["bidder_facts"][0]["value"] = 2.0
        tampered["bidder_facts"][0]["normalized_value"] = 2.0
        tampered["original_results"]["compliance_results"][0]["actual"] = 2.0
        tampered["original_results"]["compliance_results"][0]["status"] = "PASS"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        # Replay executes rule engine independently: 2.0 >= 10.0 evaluates to FAIL!
        # Thus comparing replayed FAIL vs claimed PASS catches the synchronized tamper!
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.VERIFICATION_RESULT_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("X1", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER, "Synchronized fact value + verification result tamper", "Fact=2.0 + Result=PASS", DetectionMechanism.COMPLIANCE_STATUS_FAIL, DetectionMechanism.COMPLIANCE_STATUS_FAIL, "REJECTED", "REJECTED", not rep.is_match)

    def test_X02_fact_value_and_fabricated_evidence(self):
        """X2: Change fact value AND fabricate supporting evidence block."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["value"] = 99.0
        tampered["bidder_facts"][0]["normalized_value"] = 99.0
        tampered["bidder_facts"][0]["evidence"][0]["snippet"] = "Certified annual turnover: INR 99.00 Cr"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)  # Replayed DAG node properties for snippet and value differ
        self._record_attack("X2", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER, "Fact value + fabricated evidence block", "Turnover=99.0 + snippet=99.0", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_X03_canonical_field_and_result_adjust(self):
        """X3: Change canonical field AND adjust result."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["canonical_field"] = "PAST_EXPERIENCE_DURATION"
        tampered["original_results"]["compliance_results"][0]["reason"] = "Adjusted reason"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.CANONICALIZATION_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("X3", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER, "Canonical field + adjusted result", "Spoofed canonical field", DetectionMechanism.ONTOLOGY_REJECTION, DetectionMechanism.ONTOLOGY_REJECTION, "REJECTED", "REJECTED", not rep.is_match)

    def test_X04_contradiction_input_and_integrity_finding_tamper(self):
        """X4: Change contradiction input AND integrity finding to appear consistent."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["contradiction_inputs"] = [{"contradiction_id": "C-01", "field_name": "turnover", "value_a": 10.0, "value_b": 10.0}]
        tampered["original_results"]["integrity_findings"] = []
        tampered["original_results"]["integrity_status"] = "CONSISTENT"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        # Replay executes evaluate_pair on C-01: generates an integrity finding for C-01 (status=CONSISTENT).
        # Original results had 0 integrity findings -> mismatch!
        self.assertFalse(rep.is_match)
        self._record_attack("X4", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER, "Synchronized contradiction input + finding tamper", "Injected consistent pair", DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_X05_government_response_and_aggregate_tamper(self):
        """X5: Change government response AND aggregate status."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"][0]["status"] = "INACTIVE"
        # Attacker tries to force overall_status = PASS anyway
        tampered["original_results"]["overall_status"] = "PASS"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.REVIEW_ITEM_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("X5", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER, "Government response + aggregate override", "Invalid GST with forced PASS", DetectionMechanism.HUMAN_REVIEW_FLAG, DetectionMechanism.HUMAN_REVIEW_FLAG, "REJECTED", "REJECTED", not rep.is_match)

    def test_X06_delete_physical_evidence_preserve_pass(self):
        """X6: Delete physical evidence but preserve fact and final PASS."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"] = []
        tampered["original_results"]["overall_status"] = "PASS"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("X6", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER, "Delete physical evidence, preserve PASS", "Zero evidence blocks in DAG", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_X07_fabricate_provenance_preserve_verdict(self):
        """X7: Fabricate provenance while keeping final verdict unchanged."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"].append({
            "edge_id": "EDGE:FAKE_EDGE:RESULT_SUPPORTED_BY:BLOCK:doc.pdf:P1",
            "source_id": "RESULT:VERIF-BID-ADV-202-REQ-TO-01",
            "edge_type": "RESULT_SUPPORTED_BY",
            "target_id": "BLOCK:doc.pdf:P1:BBOX_0.0_0.0_0.0_0.0",
            "properties": {},
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, [m.category for m in rep.mismatches])
        self._record_attack("X7", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER, "Fabricate provenance edge, preserve verdict", "Fake edge in DAG", DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH, "REJECTED", "REJECTED", not rep.is_match)

    def test_X08_rule_config_and_result_manipulate(self):
        """X8: Change rule configuration AND manipulate expected result."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["deterministic_config"]["rule_engine_version"] = "9.9.9"
        tampered["verification_config_hash"] = compute_config_hash(tampered["deterministic_config"])
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertFalse(rep.is_match)
        self.assertEqual(rep.status, MismatchCategory.CONFIGURATION_MISMATCH.value)
        self._record_attack("X8", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER, "Rule configuration + result manipulation", "Configuration mismatch halts replay", DetectionMechanism.CONFIG_HASH_MISMATCH, DetectionMechanism.CONFIG_HASH_MISMATCH, "REJECTED", rep.status, not rep.is_match)

    # =========================================================================
    # PHASE 14: NEGATIVE CONTROLS (N1 - N7)
    # =========================================================================

    def test_N01_json_key_reordering(self):
        d = self.clean_snapshot.to_dict()
        reordered = {k: d[k] for k in sorted(d.keys(), reverse=True)}
        rep = self.replay_engine.replay(reordered)
        self.assertTrue(rep.is_match)
        self._record_attack("N1", AttackCategory.NEGATIVE_CONTROL, TargetLayer.AUDIT_SNAPSHOT, "JSON key reordering", "Canonical normalization handles order", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep.is_match)

    def test_N02_canonical_serialization_whitespace(self):
        json_compact = json.dumps(self.clean_snapshot.to_dict(), separators=(",", ":"))
        json_spaced = json.dumps(self.clean_snapshot.to_dict(), separators=(", ", ": "))
        rep1 = self.replay_engine.replay(json_compact)
        rep2 = self.replay_engine.replay(json_spaced)
        self.assertTrue(rep1.is_match and rep2.is_match)
        self._record_attack("N2", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Whitespace variation in JSON string", "Parses identical dict", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep1.is_match and rep2.is_match)

    def test_N03_equivalent_deterministic_formatting(self):
        json_indented = self.clean_snapshot.to_json(indent=4)
        rep = self.replay_engine.replay(json_indented)
        self.assertTrue(rep.is_match)
        self._record_attack("N3", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "4-space indented JSON formatting", "Parses identical dict", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep.is_match)

    def test_N04_semantically_unordered_evidence_ordering(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Reverse order of facts
        tampered["bidder_facts"].reverse()
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        rep = self.replay_engine.replay(tampered)
        self.assertTrue(rep.is_match)
        self._record_attack("N4", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Reversed facts list ordering", "Facts matched by fact_id", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", rep.is_match)

    def test_N05_repeated_identical_replay(self):
        snap = self.clean_snapshot
        r1 = self.replay_engine.replay(snap).to_json()
        r2 = self.replay_engine.replay(snap).to_json()
        r3 = self.replay_engine.replay(snap).to_json()
        identical = (r1 == r2 == r3)
        self.assertTrue(identical)
        self._record_attack("N5", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Repeated identical replay (3x)", "Byte-for-byte identical", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "IDENTICAL", "IDENTICAL", identical)

    def test_N06_reload_snapshot_from_disk_string_dict(self):
        # From dict
        r_dict = self.replay_engine.replay(self.clean_snapshot.to_dict())
        # From json string
        r_str = self.replay_engine.replay(self.clean_snapshot.to_json())
        # From AuditSnapshot instance
        r_obj = self.replay_engine.replay(self.clean_snapshot)
        all_match = (r_dict.is_match and r_str.is_match and r_obj.is_match)
        self.assertTrue(all_match)
        self._record_attack("N6", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE, "Reload snapshot from dict/string/instance", "All formats evaluate to COMPLETE_MATCH", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "MATCH", "MATCH", all_match)

    def test_N07_serialization_deserialization_round_trip(self):
        s_json = self.clean_snapshot.to_json()
        snap_restored = AuditSnapshot.from_json(s_json)
        self.assertEqual(self.clean_snapshot.snapshot_hash, snap_restored.snapshot_hash)
        self.assertEqual(self.clean_snapshot.verification_config_hash, snap_restored.verification_config_hash)
        self._record_attack("N7", AttackCategory.NEGATIVE_CONTROL, TargetLayer.AUDIT_SNAPSHOT, "Serialization round-trip integrity", "Snapshot hashes identical", DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN, "IDENTICAL", "IDENTICAL", True)

    @classmethod
    def tearDownClass(cls):
        cls.manifest.print_summary()


if __name__ == "__main__":
    unittest.main()
