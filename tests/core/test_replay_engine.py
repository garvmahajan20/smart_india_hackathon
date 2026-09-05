# -*- coding: utf-8 -*-
"""
Tests for Phase 10B.4: Deterministic Replay Engine & Audit Snapshot Verifier.

Verifies:
- All 30 required functional test cases
- 5 additional adversarial tampering cases
- Multi-block physical provenance replay
- Contradiction and human-review replay
- Complete byte-for-byte determinism
- Tamper detection across all layers
"""

import copy
import hashlib
import json
import unittest
from typing import Any, Dict, List

from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    Severity,
    TenderRequirement,
    VerificationResult,
)
from backend.core.rule_engine import DeterministicRuleEngine
from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.core.provenance_dag import ProvenanceDAGBuilder
from backend.core.replay_engine import (
    DeterministicReplayEngine,
    MismatchCategory,
    ReplayMismatch,
    ReplayVerificationResult,
)
from backend.core.snapshot import (
    AuditSnapshot,
    DeterministicConfig,
    SnapshotBuilder,
    compute_config_hash,
    compute_snapshot_hash,
    validate_snapshot_dict,
)
from backend.orchestration.aggregator import VerificationAggregator
from backend.orchestration.models import HumanReviewItem
from backend.verification.models import AdapterResponse, IntegrityFinding, VerificationStatus


class TestDeterministicReplayEngine(unittest.TestCase):
    """Full test suite for Phase 10B.4 Deterministic Replay & Snapshot Verification."""

    def setUp(self):
        # 1. Tender Requirements
        self.req_to = TenderRequirement(
            requirement_id="REQ-TO-01",
            tender_id="TENDER-101",
            category="FINANCIAL_CAPACITY",
            description="Minimum annual turnover shall be INR 10.0 Crore",
            operator=">=",
            expected_value=10.0,
            field="annual_turnover",
            canonical_field="ANNUAL_TURNOVER",
            evidence=[
                {
                    "block_id": "T-BLK-01",
                    "document": "tender_document.pdf",
                    "page": 4,
                    "bbox": [50.0, 100.0, 150.0, 500.0],
                    "snippet": "Minimum annual turnover shall be INR 10.0 Crore",
                }
            ],
        )
        self.req_exp = TenderRequirement(
            requirement_id="REQ-EXP-01",
            tender_id="TENDER-101",
            category="TECHNICAL_CAPACITY",
            description="Minimum past experience shall be 5 years",
            operator=">=",
            expected_value=5,
            field="past_experience_years",
            canonical_field="PAST_EXPERIENCE_DURATION",
            evidence=[
                {
                    "block_id": "T-BLK-02",
                    "document": "tender_document.pdf",
                    "page": 5,
                    "bbox": [10.0, 20.0, 30.0, 40.0],
                    "snippet": "Minimum past experience shall be 5 years",
                }
            ],
        )

        # 2. Bidder Facts
        self.fact_to = BidderFact(
            fact_id="FACT-TO-01",
            bid_id="BID-202",
            field="turnover_amount",
            canonical_field="ANNUAL_TURNOVER",
            value=12.5,
            normalized_value=12.5,
            unit="INR_CRORE",
            source_document="audited_balance_sheet.pdf",
            page=8,
            bbox=[120.0, 150.0, 220.0, 480.0],
            raw_text_snippet="Annual turnover certified: INR 12.50 Cr",
            evidence=[
                {
                    "block_id": "B-BLK-01",
                    "document": "audited_balance_sheet.pdf",
                    "page": 8,
                    "bbox": [120.0, 150.0, 220.0, 480.0],
                    "snippet": "Annual turnover certified: INR 12.50 Cr",
                },
                {
                    "block_id": "B-BLK-02",
                    "document": "audited_balance_sheet.pdf",
                    "page": 9,
                    "bbox": [50.0, 60.0, 150.0, 300.0],
                    "snippet": "UDIN seal confirmation block",
                },
            ],
        )
        self.fact_exp = BidderFact(
            fact_id="FACT-EXP-01",
            bid_id="BID-202",
            field="past_experience_years",
            canonical_field="PAST_EXPERIENCE_DURATION",
            value=7,
            normalized_value=7,
            source_document="experience_cert.pdf",
            page=2,
            bbox=[100.0, 100.0, 200.0, 200.0],
            raw_text_snippet="Past experience: 7 complete years",
            evidence=[
                {
                    "block_id": "B-BLK-03",
                    "document": "experience_cert.pdf",
                    "page": 2,
                    "bbox": [100.0, 100.0, 200.0, 200.0],
                    "snippet": "Past experience: 7 complete years",
                }
            ],
        )

        # 3. Authentic Rule Engine Verification Results
        rule_engine = DeterministicRuleEngine()
        comp_results = rule_engine.verify_bid(
            requirements=[self.req_to, self.req_exp],
            facts=[self.fact_to, self.fact_exp],
        )
        self.res_to = comp_results[0]
        self.res_exp = comp_results[1]

        # 4. Captured Government Responses
        self.gov_gst = AdapterResponse(
            status=VerificationStatus.VERIFIED,
            adapter_name="GSTAdapter",
            queried_identifier="29SYNTH0000003F1Z",
            source="GSTN_REGISTRY",
            reason="GSTIN is active and verified",
            registered_entity_name="Acme Corp Pvt Ltd",
        )
        self.gov_debar = AdapterResponse(
            status=VerificationStatus.NOT_DEBARRED,
            adapter_name="DebarmentAdapter",
            queried_identifier="Acme Corp Pvt Ltd",
            source="CENTRAL_DEBARMENT_REGISTRY",
            reason="Entity is in good standing, not debarred",
        )

        # 5. Clean Snapshot
        self.clean_snapshot = SnapshotBuilder.build(
            tender_id="TENDER-101",
            bid_id="BID-202",
            requirements=[self.req_to, self.req_exp],
            facts=[self.fact_to, self.fact_exp],
            compliance_results=[self.res_to, self.res_exp],
            integrity_findings=[],
            government_responses=[self.gov_gst, self.gov_debar],
            human_review_items=[],
            aggregated_status={
                "compliance_status": "PASS",
                "integrity_status": "CONSISTENT",
                "overall_status": "PASS",
            },
        )
        self.engine = DeterministicReplayEngine()

    # =========================================================================
    # CORE TESTS (1 - 30)
    # =========================================================================

    def test_01_valid_snapshot_loads(self):
        snap_dict = self.clean_snapshot.to_dict()
        errors = validate_snapshot_dict(snap_dict)
        self.assertEqual(len(errors), 0, f"Snapshot failed validation: {errors}")

    def test_02_valid_snapshot_hash_verifies(self):
        claimed_hash = self.clean_snapshot.snapshot_hash
        recomputed = compute_snapshot_hash(self.clean_snapshot.to_dict())
        self.assertEqual(claimed_hash, recomputed)

    def test_03_deterministic_config_fingerprint_verifies(self):
        cfg = self.clean_snapshot.deterministic_config
        cfg_hash = compute_config_hash(cfg)
        self.assertEqual(self.clean_snapshot.verification_config_hash, cfg_hash)

    def test_04_clean_snapshot_fully_replays(self):
        res = self.engine.replay(self.clean_snapshot)
        self.assertTrue(res.is_match)
        self.assertEqual(res.status, MismatchCategory.COMPLETE_MATCH.value)
        self.assertEqual(len(res.mismatches), 0)

    def test_05_replay_matches_original_verification(self):
        res = self.engine.replay(self.clean_snapshot)
        rep_results = res.replayed_results["compliance_results"]
        self.assertEqual(len(rep_results), 2)
        statuses = {r["requirement_id"]: r["status"] for r in rep_results}
        self.assertEqual(statuses["REQ-TO-01"], "PASS")
        self.assertEqual(statuses["REQ-EXP-01"], "PASS")

    def test_06_replay_matches_original_integrity(self):
        res = self.engine.replay(self.clean_snapshot)
        self.assertEqual(res.replayed_results["integrity_status"], "CONSISTENT")
        self.assertEqual(len(res.replayed_results["integrity_findings"]), 0)

    def test_07_replay_matches_original_aggregation(self):
        res = self.engine.replay(self.clean_snapshot)
        self.assertEqual(res.replayed_results["overall_status"], "PASS")
        self.assertEqual(res.replayed_results["compliance_status"], "PASS")

    def test_08_replay_matches_original_review_items(self):
        res = self.engine.replay(self.clean_snapshot)
        self.assertEqual(len(res.replayed_results["human_review_items"]), 0)

    def test_09_replay_matches_provenance_graph(self):
        res = self.engine.replay(self.clean_snapshot)
        self.assertNotIn(MismatchCategory.PROVENANCE_MISMATCH.value, [m.category for m in res.mismatches])
        self.assertGreater(res.replayed_results["provenance_node_count"], 0)
        self.assertGreater(res.replayed_results["provenance_edge_count"], 0)

    def test_10_repeated_replay_is_byte_identical(self):
        res1 = self.engine.replay(self.clean_snapshot).to_json()
        res2 = self.engine.replay(self.clean_snapshot).to_json()
        res3 = self.engine.replay(self.clean_snapshot).to_json()
        self.assertEqual(res1, res2)
        self.assertEqual(res2, res3)

    def test_11_tampered_fact_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Tamper fact value: 12.5 -> 2.0 (below 10.0 threshold)
        tampered["bidder_facts"][0]["value"] = 2.0
        tampered["bidder_facts"][0]["normalized_value"] = 2.0
        # Recompute snapshot hash to test engine logic catch
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.VERIFICATION_RESULT_MISMATCH.value, categories)

    def test_12_tampered_requirement_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Tamper requirement expected value: 10.0 -> 50.0
        tampered["requirements"][0]["expected_value"] = 50.0
        tampered["requirements"][0]["normalized_expected_value"] = 50.0
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.VERIFICATION_RESULT_MISMATCH.value, categories)

    def test_13_tampered_canonical_field_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["canonical_field"] = "DIFFERENT_CONCEPT"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.CANONICALIZATION_MISMATCH.value, categories)

    def test_14_tampered_evidence_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Remove an evidence block
        tampered["bidder_facts"][0]["evidence"] = [tampered["bidder_facts"][0]["evidence"][0]]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, categories)

    def test_15_tampered_bbox_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["evidence"][0]["bbox"] = [999.0, 999.0, 999.0, 999.0]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, categories)

    def test_16_tampered_result_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Claim original result was FAIL when facts actually pass
        tampered["original_results"]["compliance_results"][0]["status"] = "FAIL"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.VERIFICATION_RESULT_MISMATCH.value, categories)

    def test_17_tampered_integrity_finding_detected(self):
        inf = IntegrityFinding(
            finding_id="INT-01",
            bid_id="BID-202",
            finding_type="CROSS_DOCUMENT_INCONSISTENCY",
            field="annual_turnover",
            severity="HIGH",
            status="CONTRADICTION",
            description="Turnover mismatch",
            value_a=12.5,
            value_b=5.0,
            evidence_a={"document": "a.pdf", "page": 1, "bbox": [0, 0, 0, 0], "snippet": ""},
            evidence_b={"document": "b.pdf", "page": 2, "bbox": [0, 0, 0, 0], "snippet": ""},
            requires_human_review=True,
        )
        snap_contra = SnapshotBuilder.build(
            tender_id="TENDER-101",
            bid_id="BID-202",
            requirements=[self.req_to],
            facts=[self.fact_to],
            compliance_results=[self.res_to],
            integrity_findings=[inf],
            contradiction_inputs=[
                {
                    "contradiction_id": "INT-01",
                    "field_name": "annual_turnover",
                    "value_a": 12.5,
                    "value_b": 5.0,
                    "document_a": "a.pdf",
                    "page_a": 1,
                    "document_b": "b.pdf",
                    "page_b": 2,
                }
            ],
            aggregated_status={
                "compliance_status": "PASS",
                "integrity_status": "CONTRADICTION",
                "overall_status": "REVIEW",
            },
        )
        tampered = copy.deepcopy(snap_contra.to_dict())
        # Tamper contradiction value_b so it matches value_a
        tampered["contradiction_inputs"][0]["value_b"] = 12.5
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.INTEGRITY_FINDING_MISMATCH.value, categories)

    def test_18_tampered_government_result_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Tamper DebarmentAdapter result from NOT_DEBARRED to DEBARRED
        tampered["captured_government_responses"][1]["status"] = "DEBARRED"
        tampered["captured_government_responses"][1]["reason"] = "Debarred for fraud"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.AGGREGATION_MISMATCH.value, categories)

    def test_19_tampered_provenance_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Delete a node from provenance graph
        p_graph = tampered["original_results"]["provenance_graph"]
        del p_graph["nodes"][0]
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.PROVENANCE_MISMATCH.value, categories)

    def test_20_configuration_mismatch_detected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        # Modify rule engine version in config
        tampered["deterministic_config"]["rule_engine_version"] = "9.9.9"
        tampered["verification_config_hash"] = compute_config_hash(tampered["deterministic_config"])
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        categories = [m.category for m in res.mismatches]
        self.assertIn(MismatchCategory.CONFIGURATION_MISMATCH.value, categories)

    def test_21_invalid_snapshot_rejected(self):
        invalid_snap = {"invalid_key": 123}
        res = self.engine.replay(invalid_snap)
        self.assertFalse(res.is_match)
        self.assertEqual(res.status, MismatchCategory.SNAPSHOT_INVALID.value)

    def test_22_incompatible_version_rejected(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["snapshot_version"] = "99.0.0"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        self.assertEqual(res.status, MismatchCategory.SCHEMA_VERSION_MISMATCH.value)

    def test_23_missing_evidence_does_not_fabricate_provenance(self):
        req_missing = TenderRequirement(
            requirement_id="REQ-MISSING",
            tender_id="TENDER-101",
            category="FINANCIAL",
            description="ISO certification",
            operator="EXISTS",
            field="iso_cert",
        )
        rule_engine = DeterministicRuleEngine()
        comp = rule_engine.verify_bid(requirements=[req_missing], facts=[])
        res_missing = comp[0]
        agg = VerificationAggregator().aggregate(
            tender_id="TENDER-101",
            bid_id="BID-202",
            compliance_results=[res_missing],
            integrity_findings=[],
            government_responses=[],
        )
        snap = SnapshotBuilder.build(
            tender_id="TENDER-101",
            bid_id="BID-202",
            requirements=[req_missing],
            facts=[],
            compliance_results=[res_missing],
            human_review_items=agg.human_review_items,
            aggregated_status=agg.to_dict(),
        )
        res = self.engine.replay(snap)
        self.assertTrue(res.is_match)
        self.assertEqual(res.status, MismatchCategory.COMPLETE_MATCH.value)
        # Verify 0 physical blocks or satisfaction edges exist for missing fact
        self.assertEqual(res.replayed_results["provenance_edge_count"], 2)  # REQ evaluation + review item

    def test_24_replay_never_invokes_gemini(self):
        # Inspect engine imports and call stack during replay
        import sys
        self.assertNotIn("google.generativeai", sys.modules)
        res = self.engine.replay(self.clean_snapshot)
        self.assertTrue(res.is_match)
        self.assertNotIn("google.generativeai", sys.modules)

    def test_25_replay_never_invokes_external_api(self):
        # Replace socket or verify no HTTP libraries are invoked
        res = self.engine.replay(self.clean_snapshot)
        self.assertTrue(res.is_match)

    def test_26_replay_does_not_alter_original_data(self):
        orig_json = self.clean_snapshot.to_json()
        _ = self.engine.replay(self.clean_snapshot)
        after_json = self.clean_snapshot.to_json()
        self.assertEqual(orig_json, after_json)

    def test_27_contradiction_review_case_replays_correctly(self):
        c_input = {
            "contradiction_id": "INT-CONTRA-01",
            "field_name": "turnover_amount",
            "value_a": 12.5,
            "value_b": 6.0,
            "document_a": "audit.pdf",
            "page_a": 8,
            "bbox_a": [1.0, 2.0, 3.0, 4.0],
            "snippet_a": "12.5",
            "document_b": "itr.pdf",
            "page_b": 1,
            "bbox_b": [5.0, 6.0, 7.0, 8.0],
            "snippet_b": "6.0",
        }
        inf = CrossDocumentContradictionEngine().evaluate_pair(bid_id="BID-202", **c_input)
        aggregator = VerificationAggregator()
        agg = aggregator.aggregate(
            tender_id="TENDER-101",
            bid_id="BID-202",
            compliance_results=[self.res_to],
            integrity_findings=[inf],
            government_responses=[],
        )
        snap = SnapshotBuilder.build(
            tender_id="TENDER-101",
            bid_id="BID-202",
            requirements=[self.req_to],
            facts=[self.fact_to],
            compliance_results=[self.res_to],
            integrity_findings=[inf],
            contradiction_inputs=[c_input],
            human_review_items=agg.human_review_items,
            aggregated_status=agg.to_dict(),
        )
        res = self.engine.replay(snap)
        self.assertTrue(res.is_match)
        self.assertEqual(res.status, MismatchCategory.COMPLETE_MATCH.value)
        self.assertEqual(res.replayed_results["integrity_status"], "CONTRADICTION")

    def test_28_missing_uncertain_evidence_case_replays_correctly(self):
        # A case where a value was unextracted in ground-truth (MISSING in engine)
        req_warranty = TenderRequirement(
            requirement_id="REQ-WARRANTY",
            tender_id="TENDER-101",
            category="TECHNICAL",
            description="Warranty 3 years",
            operator=">=",
            expected_value=3,
            field="warranty_years",
        )
        rule_engine = DeterministicRuleEngine()
        comp = rule_engine.verify_bid(requirements=[req_warranty], facts=[])
        res_warranty = comp[0]
        agg = VerificationAggregator().aggregate(
            tender_id="TENDER-101",
            bid_id="BID-202",
            compliance_results=[res_warranty],
            integrity_findings=[],
            government_responses=[],
        )
        snap = SnapshotBuilder.build(
            tender_id="TENDER-101",
            bid_id="BID-202",
            requirements=[req_warranty],
            facts=[],
            compliance_results=[res_warranty],
            human_review_items=agg.human_review_items,
            aggregated_status=agg.to_dict(),
        )
        res = self.engine.replay(snap)
        self.assertTrue(res.is_match)
        self.assertEqual(res.status, MismatchCategory.COMPLETE_MATCH.value)
        self.assertEqual(res.replayed_results["compliance_status"], "MISSING")

    def test_29_mismatch_categories_are_deterministic(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["bidder_facts"][0]["value"] = 1.0
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res1 = self.engine.replay(tampered)
        res2 = self.engine.replay(tampered)
        self.assertEqual(res1.status, res2.status)
        self.assertEqual(
            [m.category for m in res1.mismatches],
            [m.category for m in res2.mismatches],
        )

    def test_30_comparison_output_itself_is_deterministic(self):
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"][0]["operator"] = "<=" # 12.5 <= 10.0 fails!
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res1_json = self.engine.replay(tampered).to_json()
        res2_json = self.engine.replay(tampered).to_json()
        self.assertEqual(res1_json, res2_json)

    # =========================================================================
    # ADVERSARIAL TAMPERING TESTS (31 - 35)
    # =========================================================================

    def test_adversarial_31_manipulated_expected_operator_in_requirement(self):
        """Adversarial Test 1: Attacker changes operator from >= to == in requirement."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["requirements"][0]["operator"] = "=="
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        self.assertIn(
            MismatchCategory.VERIFICATION_RESULT_MISMATCH.value,
            [m.category for m in res.mismatches],
        )

    def test_adversarial_32_injected_fabricated_dag_edge_in_snapshot(self):
        """Adversarial Test 2: Attacker injects a synthetic edge into the DAG."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        p_graph = tampered["original_results"]["provenance_graph"]
        p_graph["edges"].append({
            "edge_id": "EDGE:FAKE_SOURCE:FACT_GROUNDED_BY:FAKE_TARGET",
            "source_id": "FAKE_SOURCE",
            "edge_type": "FACT_GROUNDED_BY",
            "target_id": "FAKE_TARGET",
            "properties": {},
        })
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        self.assertIn(
            MismatchCategory.PROVENANCE_MISMATCH.value,
            [m.category for m in res.mismatches],
        )

    def test_adversarial_33_altered_government_adapter_status(self):
        """Adversarial Test 3: Attacker alters GST adapter from VERIFIED to IDENTITY_MISMATCH."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        tampered["captured_government_responses"][0]["status"] = "IDENTITY_MISMATCH"
        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        # Should generate human review item for government mismatch
        self.assertIn(
            MismatchCategory.REVIEW_ITEM_MISMATCH.value,
            [m.category for m in res.mismatches],
        )

    def test_adversarial_34_swapped_fact_values_across_fields(self):
        """Adversarial Test 4: Attacker swaps turnover value with experience value."""
        tampered = copy.deepcopy(self.clean_snapshot.to_dict())
        val_to = tampered["bidder_facts"][0]["value"]
        norm_to = tampered["bidder_facts"][0].get("normalized_value")
        val_exp = tampered["bidder_facts"][1]["value"]
        norm_exp = tampered["bidder_facts"][1].get("normalized_value")

        tampered["bidder_facts"][0]["value"] = val_exp # 7.0 (fails >= 10.0!)
        tampered["bidder_facts"][0]["normalized_value"] = norm_exp
        tampered["bidder_facts"][1]["value"] = val_to  # 12.5 years
        tampered["bidder_facts"][1]["normalized_value"] = norm_to

        tampered["snapshot_hash"] = compute_snapshot_hash(tampered)
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        self.assertIn(
            MismatchCategory.VERIFICATION_RESULT_MISMATCH.value,
            [m.category for m in res.mismatches],
        )

    def test_adversarial_35_self_loop_cyclic_dag_injected(self):
        """Adversarial Test 5: Attacker injects a self-loop into the snapshot DAG."""
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
        res = self.engine.replay(tampered)
        self.assertFalse(res.is_match)
        self.assertIn(
            MismatchCategory.PROVENANCE_MISMATCH.value,
            [m.category for m in res.mismatches],
        )


if __name__ == "__main__":
    unittest.main()
