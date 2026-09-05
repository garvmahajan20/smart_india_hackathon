# -*- coding: utf-8 -*-
"""
Unit and Integration Tests for Phase 10B.6 Evaluation Engine & Benchmarking.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

from backend.core.dataset_evaluator import DatasetEvaluator, wilson_score_interval
from backend.core.evaluation_models import (
    AnomalyMetrics,
    BidMetrics,
    ContradictionMetrics,
    DatasetMetrics,
    EvaluationCase,
    EvaluationRun,
    EvidenceMetrics,
    FailureAnalysis,
    ProvenanceMetrics,
    ReplayMetrics,
    RequirementMetrics,
    canonical_json_str,
    compute_model_hash,
)


class TestEvaluationModelsAndEngine(unittest.TestCase):
    """Verifies all Phase 10B.6 evaluation models, metric calculations, and safety gates."""

    @classmethod
    def setUpClass(cls):
        cls.evaluator = DatasetEvaluator()

    def test_01_canonical_json_and_model_hash(self):
        """Verifies deterministic JSON serialization and hashing."""
        data_a = {"b": 2, "a": 1, "c": [3, 2, 1]}
        data_b = {"a": 1, "c": [3, 2, 1], "b": 2}
        self.assertEqual(canonical_json_str(data_a), canonical_json_str(data_b))
        self.assertEqual(compute_model_hash(data_a), compute_model_hash(data_b))

    def test_02_wilson_score_interval(self):
        """Verifies Wilson score confidence interval calculation."""
        res = wilson_score_interval(k=95, n=100, confidence=0.95)
        self.assertEqual(res["proportion"], 0.95)
        self.assertTrue(0.88 <= res["lower"] <= 0.92)
        self.assertTrue(0.97 <= res["upper"] <= 0.99)

        # Edge cases: 0 and 1
        res_zero = wilson_score_interval(k=0, n=100)
        self.assertEqual(res_zero["proportion"], 0.0)
        self.assertEqual(res_zero["lower"], 0.0)

        res_one = wilson_score_interval(k=100, n=100)
        self.assertEqual(res_one["proportion"], 1.0)
        self.assertEqual(res_one["upper"], 1.0)

    def test_03_dataset_manifest_generation(self):
        """Verifies manifest cardinalities and file hashes."""
        manifest = self.evaluator.generate_manifest()
        self.assertEqual(manifest.dataset_id, "SIH26100")
        self.assertEqual(manifest.dataset_version, "1.0")
        self.assertEqual(manifest.tender_count, 100)
        self.assertEqual(manifest.bid_count, 3000)
        self.assertEqual(manifest.entity_count, 15)
        self.assertEqual(manifest.requirement_count, 800)
        self.assertEqual(manifest.clause_count, 24000)
        self.assertEqual(manifest.contradiction_count, 1041)
        self.assertEqual(manifest.anomaly_count, 9218)
        self.assertTrue(len(manifest.manifest_hash) == 64)

    def test_04_contradiction_exact_matches(self):
        """Verifies 1,041 contradiction cases evaluate at 100% exact match."""
        cm = self.evaluator._evaluate_contradictions()
        self.assertEqual(cm.total_cases, 1041)
        self.assertEqual(cm.exact_matches, 1041)
        self.assertEqual(cm.mismatches, 0)
        self.assertEqual(cm.exact_match_rate, 100.0)
        self.assertEqual(cm.detected_contradictions, 671)
        self.assertEqual(cm.correct_consistent, 152)

    def test_05_anomaly_structural_mapping(self):
        """Verifies 9,218 anomaly records are structurally mapped without loss."""
        am = self.evaluator._evaluate_anomalies()
        self.assertEqual(am.total_anomalies, 9218)
        self.assertEqual(am.mapped_correctly, 9218)
        self.assertEqual(am.unmapped, 0)
        self.assertEqual(am.incorrectly_mapped, 0)

    def test_06_evidence_and_multi_block_completeness(self):
        """Verifies multi-block evidence preservation completeness."""
        em = self.evaluator._evaluate_evidence_completeness()
        self.assertEqual(em.block_preservation_rate, 1.0)
        self.assertEqual(em.bbox_preservation_rate, 1.0)
        self.assertEqual(em.document_preservation_rate, 1.0)
        self.assertEqual(em.snippet_preservation_rate, 1.0)
        self.assertEqual(em.multi_block_completeness, 1.0)
        self.assertEqual(em.false_evidence_support_rate, 0.0)

    def test_07_provenance_dag_invariants(self):
        """Verifies DAG acyclicity, zero phantom edges, zero orphans on sample."""
        dm = self.evaluator._evaluate_provenance_dags(sample_size=10)
        self.assertEqual(dm.cycle_count, 0)
        self.assertEqual(dm.cycle_rate, 0.0)
        self.assertEqual(dm.phantom_edge_count, 0)
        self.assertEqual(dm.phantom_edge_rate, 0.0)
        self.assertEqual(dm.provenance_completeness_rate, 1.0)

    def test_08_replay_and_repeat_determinism(self):
        """Verifies deterministic replay across sample bids."""
        rm = self.evaluator._evaluate_replay(sample_size=10, repeat_runs=5)
        self.assertEqual(rm.replay_match_rate, 100.0)
        self.assertEqual(rm.deterministic_replay_rate, 100.0)
        self.assertEqual(rm.mismatch_count, 0)

    def test_09_safety_gates_and_invariants(self):
        """Verifies critical safety gates: FALSE_PASS_RATE == 0 and REVIEW_ESCAPE_RATE == 0."""
        req_metrics, _, failures, abstentions = self.evaluator._evaluate_requirements()
        self.assertEqual(req_metrics.false_pass_rate, 0.0)
        self.assertEqual(req_metrics.review_escape_rate, 0.0)
        self.assertEqual(len(failures["false_pass_cases"]), 0)
        self.assertEqual(len(abstentions), 310)


if __name__ == "__main__":
    unittest.main()
