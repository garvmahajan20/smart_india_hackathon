# -*- coding: utf-8 -*-
"""
Tests for Phase 10B.3: In-Memory Provenance DAG & Deterministic Explainability Trace.

Verifies:
- All 26 core required test cases
- 3 adversarial tests (concept isolation, multi-block non-loss, malformed rejection)
- Bidirectional traversal (decision -> evidence, evidence -> decisions, fact -> provenance, integrity -> evidence)
- Byte-for-byte serialization determinism
"""

import unittest
import json
from typing import Dict, Any, List

from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    Severity,
    TenderRequirement,
    VerificationResult,
)
from backend.core.provenance_dag import (
    CycleDetectedError,
    EdgeType,
    GraphValidationError,
    NodeType,
    ProvenanceDAG,
    ProvenanceDAGBuilder,
    ProvenanceEdge,
    ProvenanceNode,
    make_block_node_id,
    make_edge_id,
)
from backend.verification.models import IntegrityFinding
from backend.orchestration.models import HumanReviewItem, VerificationDossier


class TestProvenanceDAG(unittest.TestCase):
    """Core suite verifying the in-memory provenance DAG and explainability trace."""

    def setUp(self):
        self.req1 = TenderRequirement(
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
                    "document": "TENDER-101.pdf",
                    "page": 4,
                    "bbox": [50.0, 100.0, 150.0, 500.0],
                    "snippet": "Minimum annual turnover shall be INR 10.0 Crore",
                }
            ],
        )

        self.fact1 = BidderFact(
            fact_id="FACT-TO-01",
            bid_id="BID-202",
            field="turnover_amount",
            canonical_field="ANNUAL_TURNOVER",
            value=12.5,
            normalized_value=125000000,
            unit="INR",
            source_document="audited_balance_sheet.pdf",
            page=8,
            bbox=[120.0, 150.0, 220.0, 480.0],
            raw_text_snippet="Annual turnover certified: INR 12.50 Cr",
            evidence=[
                {
                    "block_id": "B-BLK-01",
                    "document": "audited_balance_sheet.pdf",
                    "document_id": "DOC-FIN-01",
                    "page": 8,
                    "bbox": [120.0, 150.0, 220.0, 480.0],
                    "snippet": "Annual turnover certified: INR 12.50 Cr",
                    "source_type": "BIDDER_SUBMISSION",
                },
                {
                    "block_id": "B-BLK-02",
                    "document": "audited_balance_sheet.pdf",
                    "document_id": "DOC-FIN-01",
                    "page": 9,
                    "bbox": [50.0, 60.0, 150.0, 300.0],
                    "snippet": "CA Membership and UDIN seal verification continuation",
                    "source_type": "BIDDER_SUBMISSION",
                }
            ],
        )

        self.res1 = VerificationResult(
            verification_id="VERIF-BID202-REQ-TO-01",
            requirement_id="REQ-TO-01",
            bid_id="BID-202",
            status=ComplianceStatus.PASS.value,
            severity=Severity.INFO.value,
            expected=">= 10.0",
            actual=12.5,
            operator_used=">=",
            reason="Actual value (12.5) meets or exceeds threshold (10.0).",
            requires_human_review=False,
            fact_id="FACT-TO-01",
            evidence=self.fact1.evidence,
        )

    def test_01_graph_builds_from_clean_case(self):
        dag = ProvenanceDAGBuilder.build(
            requirements=[self.req1],
            facts=[self.fact1],
            results=[self.res1],
            bid_id="BID-202",
            tender_id="TENDER-101",
        )
        self.assertGreater(len(dag.nodes), 0)
        self.assertGreater(len(dag.edges), 0)
        dag.validate()

    def test_02_expected_node_types_exist(self):
        inf = IntegrityFinding(
            finding_id="INT-BID202-TURNOVER-001",
            bid_id="BID-202",
            finding_type="TURNOVER_CONTRADICTION",
            field="annual_turnover",
            raw_field_a="turnover_amount",
            raw_field_b="turnover_cr",
            canonical_field="ANNUAL_TURNOVER",
            severity="HIGH",
            status="CONTRADICTION",
            description="Turnover differs across documents",
            value_a=12.5,
            value_b=8.0,
            evidence_a={"document": "docA.pdf", "page": 1, "bbox": [10, 20, 30, 40], "snippet": "12.5 Cr"},
            evidence_b={"document": "docB.pdf", "page": 2, "bbox": [50, 60, 70, 80], "snippet": "8.0 Cr"},
            requires_human_review=True,
        )
        rev = HumanReviewItem(
            review_id="REV-BID202-001",
            bid_id="BID-202",
            tender_id="TENDER-101",
            category="INTEGRITY_CONTRADICTION",
            severity="CRITICAL",
            reason="Review turnover discrepancy",
            related_verification_id="INT-BID202-TURNOVER-001",
        )
        dag = ProvenanceDAGBuilder.build(
            requirements=[self.req1],
            facts=[self.fact1],
            results=[self.res1],
            integrity_findings=[inf],
            human_review_items=[rev],
            bid_id="BID-202",
            tender_id="TENDER-101",
        )
        types_present = {n.node_type for n in dag.nodes.values()}
        for expected in [
            NodeType.TENDER_REQUIREMENT.value,
            NodeType.BIDDER_FACT.value,
            NodeType.PHYSICAL_TEXT_BLOCK.value,
            NodeType.CANONICAL_FIELD.value,
            NodeType.VERIFICATION_RESULT.value,
            NodeType.INTEGRITY_FINDING.value,
            NodeType.HUMAN_REVIEW_ITEM.value,
        ]:
            self.assertIn(expected, types_present)

    def test_03_expected_edge_types_exist(self):
        inf = IntegrityFinding(
            finding_id="INT-BID202-TURNOVER-001",
            bid_id="BID-202",
            finding_type="TURNOVER_CONTRADICTION",
            field="annual_turnover",
            raw_field_a="turnover_amount",
            raw_field_b="turnover_cr",
            canonical_field="ANNUAL_TURNOVER",
            severity="HIGH",
            status="CONTRADICTION",
            description="Turnover differs",
            value_a=12.5,
            value_b=8.0,
            evidence_a={"document": "docA.pdf", "page": 1, "bbox": [10, 20, 30, 40], "snippet": "12.5"},
            evidence_b={"document": "docB.pdf", "page": 2, "bbox": [50, 60, 70, 80], "snippet": "8.0"},
            requires_human_review=True,
        )
        rev = HumanReviewItem(
            review_id="REV-BID202-001",
            bid_id="BID-202",
            tender_id="TENDER-101",
            category="AMBIGUOUS_COMPLIANCE",
            severity="MAJOR",
            reason="Review requirement",
            related_verification_id=self.res1.verification_id,
        )
        dag = ProvenanceDAGBuilder.build(
            requirements=[self.req1],
            facts=[self.fact1],
            results=[self.res1],
            integrity_findings=[inf],
            human_review_items=[rev],
            bid_id="BID-202",
            tender_id="TENDER-101",
        )
        edge_types = {e.edge_type for e in dag.edges.values()}
        self.assertIn(EdgeType.REQUIREMENT_HAS_EVIDENCE.value, edge_types)
        self.assertIn(EdgeType.FACT_GROUNDED_BY.value, edge_types)
        self.assertIn(EdgeType.FACT_CANONICALIZED_AS.value, edge_types)
        self.assertIn(EdgeType.RESULT_EVALUATES_REQUIREMENT.value, edge_types)
        self.assertIn(EdgeType.RESULT_EVALUATES_FACT.value, edge_types)
        self.assertIn(EdgeType.RESULT_SUPPORTED_BY.value, edge_types)
        self.assertIn(EdgeType.FACT_SATISFIES_REQUIREMENT.value, edge_types)
        self.assertIn(EdgeType.REVIEW_ITEM_FOR_RESULT.value, edge_types)

    def test_04_stable_node_ids(self):
        dag1 = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        dag2 = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        self.assertEqual(sorted(dag1.nodes.keys()), sorted(dag2.nodes.keys()))
        self.assertIn("REQ:REQ-TO-01", dag1.nodes)
        self.assertIn("FACT:FACT-TO-01", dag1.nodes)
        self.assertIn("FIELD:ANNUAL_TURNOVER", dag1.nodes)
        self.assertIn("RESULT:VERIF-BID202-REQ-TO-01", dag1.nodes)

    def test_05_stable_edge_ids(self):
        dag1 = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        dag2 = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        self.assertEqual(sorted(dag1.edges.keys()), sorted(dag2.edges.keys()))

    def test_06_repeated_construction_is_identical(self):
        dag1 = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        dag2 = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        self.assertEqual(dag1.to_json(), dag2.to_json())

    def test_07_duplicate_edges_are_deduplicated(self):
        dag = ProvenanceDAG()
        n1 = ProvenanceNode("N1", NodeType.BIDDER_FACT.value, "Fact 1", {})
        n2 = ProvenanceNode("N2", NodeType.CANONICAL_FIELD.value, "Field 1", {})
        dag.add_node(n1)
        dag.add_node(n2)
        e1 = ProvenanceEdge("E1", "N1", EdgeType.FACT_CANONICALIZED_AS.value, "N2")
        e2 = ProvenanceEdge("E1", "N1", EdgeType.FACT_CANONICALIZED_AS.value, "N2")
        dag.add_edge(e1)
        dag.add_edge(e2)
        self.assertEqual(len(dag.edges), 1)

    def test_08_dangling_endpoints_are_rejected(self):
        dag = ProvenanceDAG()
        n1 = ProvenanceNode("N1", NodeType.BIDDER_FACT.value, "Fact 1", {})
        dag.add_node(n1)
        e_bad = ProvenanceEdge("E1", "N1", EdgeType.FACT_CANONICALIZED_AS.value, "NON_EXISTENT_TARGET")
        with self.assertRaises(GraphValidationError):
            dag.add_edge(e_bad)

    def test_09_cycles_are_rejected(self):
        dag = ProvenanceDAG()
        n1 = ProvenanceNode("N1", NodeType.BIDDER_FACT.value, "N1", {})
        n2 = ProvenanceNode("N2", NodeType.BIDDER_FACT.value, "N2", {})
        dag.add_node(n1)
        dag.add_node(n2)
        dag.add_edge(ProvenanceEdge("E1", "N1", EdgeType.FACT_SATISFIES_REQUIREMENT.value, "N2"))
        # Adding edge N2 -> N1 must be rejected as a cycle!
        with self.assertRaises(CycleDetectedError):
            dag.add_edge(ProvenanceEdge("E2", "N2", EdgeType.FACT_SATISFIES_REQUIREMENT.value, "N1"))

    def test_10_single_block_fact_provenance(self):
        fact_single = BidderFact(
            fact_id="FACT-SINGLE",
            bid_id="BID-01",
            field="gstin",
            canonical_field="GSTIN",
            value="29SYNTH0000003F1Z",
            source_document="pan_copy.pdf",
            page=1,
            bbox=[10.0, 20.0, 30.0, 40.0],
            raw_text_snippet="GSTIN: 29SYNTH0000003F1Z",
        )
        dag = ProvenanceDAGBuilder.build([], [fact_single], [])
        grounded_edges = [
            e for e in dag.edges.values()
            if e.source_id == "FACT:FACT-SINGLE" and e.edge_type == EdgeType.FACT_GROUNDED_BY.value
        ]
        self.assertEqual(len(grounded_edges), 1)

    def test_11_multi_block_fact_provenance(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        grounded_edges = [
            e for e in dag.edges.values()
            if e.source_id == "FACT:FACT-TO-01" and e.edge_type == EdgeType.FACT_GROUNDED_BY.value
        ]
        self.assertEqual(len(grounded_edges), 2, "Both supporting blocks B-BLK-01 and B-BLK-02 must have edges!")

    def test_12_all_multi_block_bboxes_preserved(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        block_nodes = [n for n in dag.nodes.values() if n.node_type == NodeType.PHYSICAL_TEXT_BLOCK.value]
        bboxes = [b.properties.get("bbox") for b in block_nodes if b.properties.get("bbox")]
        self.assertIn([120.0, 150.0, 220.0, 480.0], bboxes)
        self.assertIn([50.0, 60.0, 150.0, 300.0], bboxes)

    def test_13_canonical_field_edge_exists_for_resolved_field(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        cf_edges = [
            e for e in dag.edges.values()
            if e.source_id == "FACT:FACT-TO-01" and e.edge_type == EdgeType.FACT_CANONICALIZED_AS.value
        ]
        self.assertEqual(len(cf_edges), 1)
        self.assertEqual(cf_edges[0].target_id, "FIELD:ANNUAL_TURNOVER")

    def test_14_unmapped_field_has_no_fake_canonical_node(self):
        unmapped_fact = BidderFact(
            fact_id="FACT-UNMAPPED",
            bid_id="BID-01",
            field="custom_unregistered_feature_xyz",
            value="SpecialFeature",
            source_document="doc.pdf",
            page=1,
        )
        dag = ProvenanceDAGBuilder.build([], [unmapped_fact], [])
        self.assertIsNone(unmapped_fact.canonical_field)
        field_nodes = [n for n in dag.nodes.values() if n.node_type == NodeType.CANONICAL_FIELD.value]
        self.assertEqual(len(field_nodes), 0, "Unmapped field MUST NOT receive a fake canonical node")

    def test_15_ambiguous_field_has_no_fake_canonical_node(self):
        ambiguous_fact = BidderFact(
            fact_id="FACT-AMBIGUOUS",
            bid_id="BID-01",
            field="experience",
            value=5,
            source_document="doc.pdf",
            page=1,
        )
        dag = ProvenanceDAGBuilder.build([], [ambiguous_fact], [])
        self.assertIsNone(ambiguous_fact.canonical_field)
        field_nodes = [n for n in dag.nodes.values() if n.node_type == NodeType.CANONICAL_FIELD.value]
        self.assertEqual(len(field_nodes), 0, "Ambiguous field MUST NOT receive a fake canonical node")

    def test_16_raw_field_remains_preserved(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        fact_node = dag.nodes["FACT:FACT-TO-01"]
        self.assertEqual(fact_node.properties["raw_field"], "turnover_amount")
        self.assertEqual(fact_node.properties["canonical_field"], "ANNUAL_TURNOVER")

    def test_17_decision_to_evidence_traversal(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        trace = dag.trace_decision(self.res1.verification_id)
        self.assertEqual(trace["status"], "PASS")
        self.assertEqual(len(trace["requirements"]), 1)
        self.assertEqual(len(trace["facts"]), 1)
        self.assertEqual(len(trace["canonical_fields"]), 1)
        self.assertEqual(trace["canonical_fields"][0]["canonical_field_id"], "ANNUAL_TURNOVER")
        self.assertGreaterEqual(len(trace["evidence_blocks"]), 2)

    def test_18_evidence_to_decision_traversal(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        trace = dag.trace_evidence_to_decisions("B-BLK-01")
        self.assertIn("evidence_block", trace)
        self.assertEqual(len(trace["facts"]), 1)
        self.assertEqual(len(trace["verification_results"]), 1)
        self.assertEqual(trace["verification_results"][0]["verification_id"], self.res1.verification_id)

    def test_19_integrity_finding_to_evidence_traversal(self):
        inf = IntegrityFinding(
            finding_id="INT-BID202-01",
            bid_id="BID-202",
            finding_type="TURNOVER_CONTRADICTION",
            field="turnover_cr",
            raw_field_a="turnover_amount",
            raw_field_b="turnover_cr",
            canonical_field="ANNUAL_TURNOVER",
            severity="HIGH",
            status="CONTRADICTION",
            description="Mismatch",
            value_a=12.5,
            value_b=8.0,
            evidence_a={"document": "docA.pdf", "page": 1, "bbox": [1, 2, 3, 4], "snippet": "12.5"},
            evidence_b={"document": "docB.pdf", "page": 2, "bbox": [5, 6, 7, 8], "snippet": "8.0"},
            requires_human_review=True,
        )
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1], integrity_findings=[inf])
        trace = dag.trace_integrity("INT-BID202-01")
        self.assertEqual(trace["finding"]["finding_id"], "INT-BID202-01")
        self.assertGreaterEqual(len(trace["evidence_blocks"]), 2)

    def test_20_human_review_item_provenance(self):
        rev = HumanReviewItem(
            review_id="REV-01",
            bid_id="BID-202",
            tender_id="TENDER-101",
            category="AMBIGUOUS_COMPLIANCE",
            severity="MAJOR",
            reason="Review needed",
            related_verification_id=self.res1.verification_id,
            evidence_references=[{"document": "audited_balance_sheet.pdf", "page": 8, "block_id": "B-BLK-01"}],
        )
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1], human_review_items=[rev])
        self.assertIn("REVIEW:REV-01", dag.nodes)
        edges_out = dag.adj["REVIEW:REV-01"]
        self.assertGreaterEqual(len(edges_out), 1)

    def test_21_explanation_is_deterministic(self):
        dag1 = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        dag2 = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        trace1 = dag1.trace_decision(self.res1.verification_id)
        trace2 = dag2.trace_decision(self.res1.verification_id)
        self.assertEqual(json.dumps(trace1, sort_keys=True), json.dumps(trace2, sort_keys=True))

    def test_22_explanation_does_not_contain_model_generated_reasoning(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        trace = dag.trace_decision(self.res1.verification_id)
        json_dump = json.dumps(trace)
        self.assertNotIn("Gemini", json_dump)
        self.assertNotIn("LLM reasoning", json_dump)
        self.assertNotIn("AI thought", json_dump)

    def test_23_graph_does_not_alter_compliance_result(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        res_node = dag.nodes["RESULT:VERIF-BID202-REQ-TO-01"]
        self.assertEqual(res_node.properties["status"], ComplianceStatus.PASS.value)

    def test_24_graph_does_not_alter_integrity_result(self):
        inf = IntegrityFinding(
            finding_id="INT-TEST-01",
            bid_id="BID-01",
            finding_type="GSTIN_CONTRADICTION",
            field="gstin",
            severity="HIGH",
            status="CONTRADICTION",
            description="GSTIN differs",
            value_a="A",
            value_b="B",
            evidence_a={},
            evidence_b={},
            requires_human_review=True,
        )
        dag = ProvenanceDAGBuilder.build([], [], [], integrity_findings=[inf])
        inf_node = dag.nodes["INTEGRITY:INT-TEST-01"]
        self.assertEqual(inf_node.properties["status"], "CONTRADICTION")

    def test_25_graph_does_not_alter_severity(self):
        dag = ProvenanceDAGBuilder.build([self.req1], [self.fact1], [self.res1])
        res_node = dag.nodes["RESULT:VERIF-BID202-REQ-TO-01"]
        self.assertEqual(res_node.properties["severity"], Severity.INFO.value)

    def test_26_existing_dossier_output_remains_compatible(self):
        dossier = VerificationDossier(
            tender={"tender_id": "T1"},
            bidder={"bid_id": "B1"},
            compliance_summary={"status": "PASS"},
            integrity_summary={"status": "CONSISTENT"},
            verification_results=[],
            government_checks=[],
            evidence=[],
            anomalies=[],
            human_review_items=[],
            audit_metadata={"verification_id": "V1"},
        )
        d = dossier.to_dict()
        self.assertIn("tender", d)
        self.assertIn("bidder", d)
        self.assertIn("audit_metadata", d)
        self.assertIn("provenance_graph", d)
        self.assertIsNone(d["provenance_graph"])

    # ==================== ADVERSARIAL TESTS ====================

    def test_adversarial_A_distinct_canonical_concepts_not_merged_in_graph(self):
        """
        Adversarial Test A:
        Two facts with distinct concepts:
        Fact 1: annual_turnover -> ANNUAL_TURNOVER
        Fact 2: average_annual_turnover -> AVERAGE_ANNUAL_TURNOVER
        Graph MUST contain two separate CANONICAL_FIELD nodes and two separate edges.
        """
        fact_single = BidderFact(
            fact_id="FACT-ADV-TO",
            bid_id="BID-ADV",
            field="annual_turnover",
            canonical_field="ANNUAL_TURNOVER",
            value=12.0,
            source_document="p1.pdf",
            page=1,
        )
        fact_avg = BidderFact(
            fact_id="FACT-ADV-AVGTO",
            bid_id="BID-ADV",
            field="average_annual_turnover",
            canonical_field="AVERAGE_ANNUAL_TURNOVER",
            value=8.0,
            source_document="p2.pdf",
            page=1,
        )
        dag = ProvenanceDAGBuilder.build([], [fact_single, fact_avg], [])
        self.assertIn("FIELD:ANNUAL_TURNOVER", dag.nodes)
        self.assertIn("FIELD:AVERAGE_ANNUAL_TURNOVER", dag.nodes)
        self.assertNotEqual(
            dag.nodes["FIELD:ANNUAL_TURNOVER"].node_id,
            dag.nodes["FIELD:AVERAGE_ANNUAL_TURNOVER"].node_id
        )

    def test_adversarial_B_multi_block_fact_never_loses_blocks(self):
        """
        Adversarial Test B:
        Fact referencing 5 distinct blocks across 3 pages.
        The graph MUST contain all 5 distinct PHYSICAL_TEXT_BLOCK nodes and 5 FACT_GROUNDED_BY edges.
        """
        blocks = [
            {"block_id": f"BLK-ADV-{i}", "document": "bid.pdf", "page": (i // 2) + 1, "bbox": [10.0 * i, 20.0, 30.0, 40.0], "snippet": f"Part {i}"}
            for i in range(5)
        ]
        fact_multi = BidderFact(
            fact_id="FACT-MULTI-5",
            bid_id="BID-ADV",
            field="turnover_cr",
            canonical_field="ANNUAL_TURNOVER",
            value=15.0,
            source_document="bid.pdf",
            page=1,
            evidence=blocks,
        )
        dag = ProvenanceDAGBuilder.build([], [fact_multi], [])
        grounded_edges = [
            e for e in dag.edges.values()
            if e.source_id == "FACT:FACT-MULTI-5" and e.edge_type == EdgeType.FACT_GROUNDED_BY.value
        ]
        self.assertEqual(len(grounded_edges), 5)
        for b in blocks:
            self.assertTrue(any(b["block_id"] in e.target_id for e in grounded_edges))

    def test_adversarial_C_malformed_edge_fails_validation(self):
        """
        Adversarial Test C:
        A manually constructed malformed edge pointing to a non-existent node
        MUST raise GraphValidationError upon addition or validation.
        """
        dag = ProvenanceDAG()
        n1 = ProvenanceNode("N1", NodeType.BIDDER_FACT.value, "Fact", {})
        dag.add_node(n1)
        with self.assertRaises(GraphValidationError):
            dag.add_edge(ProvenanceEdge("E1", "N1", EdgeType.FACT_CANONICALIZED_AS.value, "MISSING_NODE"))


if __name__ == "__main__":
    unittest.main()
