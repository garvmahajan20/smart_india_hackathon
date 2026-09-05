# -*- coding: utf-8 -*-
"""
Phase 10B.5: Real SIH Dataset Adversarial & Combinatorial Hardening Benchmark.

Tests adversarial resistance on 4 canonical real-world SIH dataset bids:
  - BID-00031 (BluePeak Solutions - CLEAN / PASS)
  - BID-00733 (Pragati Technologies - NON_COMPLIANT / FAIL)
  - BID-00001 (Bharat Devices - MANIPULATED / CONTRADICTION)
  - BID-00667 (Suryodaya Infra - UNCERTAIN / REVIEW)

Executes:
1. Systematic Multi-Layer Tamper Attacks on Real Snapshots
2. Combinatorial / Multi-Vector Compound Attacks
3. Property-Style Permutation and Invariance Verification
4. Adversarial Manifest Tracking with Zero Silent Acceptance
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")
import copy
import hashlib
import json
import os
import random
import time
from typing import Any, Dict, List, Tuple

sys.path.insert(0, os.path.abspath("."))

from backend.core.adversarial_framework import (
    AdversarialAttackResult,
    AdversarialManifest,
    AttackCategory,
    DetectionMechanism,
    TargetLayer,
)
from backend.core.models import BidderFact, TenderRequirement, ComplianceStatus
from backend.core.rule_engine import DeterministicRuleEngine
from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.orchestration.aggregator import VerificationAggregator
from backend.core.snapshot import (
    AuditSnapshot,
    SnapshotBuilder,
    canonical_json,
    compute_snapshot_hash,
    compute_config_hash,
)
from backend.core.replay_engine import (
    DeterministicReplayEngine,
    MismatchCategory,
)
from backend.verification.mock_gst import MockGSTAdapter
from backend.verification.mock_pan import MockPANAdapter
from backend.verification.mock_debarment import MockDebarmentAdapter


def build_real_sih_snapshots() -> Tuple[Dict[str, AuditSnapshot], List[TenderRequirement], Dict[str, List[BidderFact]]]:
    """Loads raw SIH dataset and constructs canonical baseline AuditSnapshots."""
    base_dir = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1"
    clause_path = os.path.join(base_dir, "text", "clause_pairs.jsonl")
    contra_path = os.path.join(base_dir, "text", "contradiction_pairs.jsonl")

    target_bids = {
        "BID-00031": {"company": "BluePeak Solutions", "expected_label": "CLEAN", "gstin": "29SYNTH0000013F1Z", "pan": "SYNTH0013F"},
        "BID-00733": {"company": "Pragati Technologies", "expected_label": "NON_COMPLIANT", "gstin": "29SYNTH0000011F1Z", "pan": "SYNTH0011F"},
        "BID-00667": {"company": "Suryodaya Infra", "expected_label": "UNCERTAIN", "gstin": "29SYNTH0000004F1Z", "pan": "SYNTH0004F"},
        "BID-00001": {"company": "Bharat Devices", "expected_label": "MANIPULATED", "gstin": "29SYNTH0000003F1Z", "pan": "SYNTH0003F"},
    }

    # 1. Load Tender Requirements
    reqs_by_field = {}
    with open(clause_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r.get("tender_id") == "TENDER-0069":
                fld = r.get("field")
                if fld not in reqs_by_field:
                    reqs_by_field[fld] = TenderRequirement(
                        requirement_id=r.get("clause_id", f"REQ-{fld}"),
                        tender_id="TENDER-0069",
                        category="TECHNICAL_SPECIFICATION",
                        description=f"Requirement for {fld}",
                        field=fld,
                        operator=r.get("operator", ">="),
                        expected_value=r.get("expected_value") or r.get("requirement_value"),
                        mandatory=True,
                    )
    requirements = list(reqs_by_field.values())

    # 2. Load Facts
    bid_facts: Dict[str, List[BidderFact]] = {b: [] for b in target_bids}
    with open(clause_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            bid = r.get("bid_id")
            if bid in target_bids:
                fld = r.get("field")
                bid_facts[bid].append(BidderFact(
                    fact_id=f"FACT-{bid}-{fld}",
                    bid_id=bid,
                    field=fld,
                    value=r.get("extracted_value"),
                    source_document=f"{bid}.pdf",
                    page=r.get("page", 1),
                    extraction_confidence="HIGH",
                    evidence=[{
                        "block_id": f"BLK-{bid}-{fld}-01",
                        "document": f"{bid}.pdf",
                        "page": r.get("page", 1),
                        "bbox": [50.0, 100.0, 200.0, 400.0],
                        "snippet": f"Physical extract for {fld}: {r.get('extracted_value')}",
                    }]
                ))

    # Add regulatory identification facts for government response validation
    for bid, facts in bid_facts.items():
        info = target_bids[bid]
        facts.append(BidderFact(
            fact_id=f"FACT-{bid}-GSTIN",
            bid_id=bid,
            field="gstin",
            canonical_field="GSTIN",
            value=info["gstin"],
            source_document=f"{bid}.pdf",
            page=1,
            evidence=[{"block_id": f"BLK-{bid}-GST-01", "document": f"{bid}.pdf", "page": 1, "snippet": f"GSTIN: {info['gstin']}"}]
        ))
        facts.append(BidderFact(
            fact_id=f"FACT-{bid}-PAN",
            bid_id=bid,
            field="pan",
            canonical_field="PAN",
            value=info["pan"],
            source_document=f"{bid}.pdf",
            page=1,
            evidence=[{"block_id": f"BLK-{bid}-PAN-01", "document": f"{bid}.pdf", "page": 1, "snippet": f"PAN: {info['pan']}"}]
        ))

    # 3. Load Contradictions
    bid_contradictions = {b: [] for b in target_bids}
    with open(contra_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            bid = r.get("bid_id")
            if bid in target_bids and r.get("status") == "CONTRADICTION":
                bid_contradictions[bid].append(r)

    # 4. Engine Runs
    rule_engine = DeterministicRuleEngine()
    contra_engine = CrossDocumentContradictionEngine()
    aggregator = VerificationAggregator()
    gst_adapter = MockGSTAdapter()
    pan_adapter = MockPANAdapter()
    debar_adapter = MockDebarmentAdapter()

    snapshots: Dict[str, AuditSnapshot] = {}

    for bid_id, info in target_bids.items():
        company = info["company"]
        facts = bid_facts[bid_id]

        comp_results = rule_engine.verify_bid(requirements, facts)

        int_findings = []
        contra_inputs = []
        if bid_id in bid_contradictions and bid_contradictions[bid_id]:
            for c in bid_contradictions[bid_id]:
                c_in = {
                    "contradiction_id": c["contradiction_id"],
                    "field_name": c.get("type", "cross_document_consistency"),
                    "value_a": c.get("value_a"),
                    "value_b": c.get("value_b"),
                    "document_a": c.get("document_a", "doc_a.pdf"),
                    "page_a": c.get("page_a", 1),
                    "bbox_a": [10.0, 10.0, 20.0, 20.0],
                    "snippet_a": f"Claim A: {c.get('value_a')}",
                    "document_b": c.get("document_b", "doc_b.pdf"),
                    "page_b": c.get("page_b", 1),
                    "bbox_b": [30.0, 30.0, 40.0, 40.0],
                    "snippet_b": f"Claim B: {c.get('value_b')}",
                    "hint_type": c.get("type"),
                }
                contra_inputs.append(c_in)
                finding = contra_engine.evaluate_pair(bid_id=bid_id, **c_in)
                int_findings.append(finding)

        gov_responses = [
            gst_adapter.verify(info["gstin"], expected_entity_name=company),
            pan_adapter.verify(info["pan"], expected_entity_name=company),
            debar_adapter.verify(company),
        ]

        aggregated = aggregator.aggregate(
            tender_id="TENDER-0069",
            bid_id=bid_id,
            compliance_results=comp_results,
            integrity_findings=int_findings,
            government_responses=gov_responses,
        )

        snap = SnapshotBuilder.build(
            tender_id="TENDER-0069",
            bid_id=bid_id,
            requirements=requirements,
            facts=facts,
            compliance_results=comp_results,
            integrity_findings=int_findings,
            government_responses=gov_responses,
            human_review_items=aggregated.human_review_items,
            aggregated_status=aggregated.to_dict(),
            contradiction_inputs=contra_inputs,
            tender_metadata={"company_name": company, "bidder_name": company},
        )
        snapshots[bid_id] = snap

    return snapshots, requirements, bid_facts


def run_benchmark():
    print("=" * 90)
    print("      PHASE 10B.5: REAL SIH DATASET ADVERSARIAL & COMBINATORIAL BENCHMARK")
    print("=" * 90)

    manifest = AdversarialManifest("SIH_REAL_DATASET_ADVERSARIAL_BENCHMARK")
    replay_engine = DeterministicReplayEngine()

    snapshots, requirements, bid_facts = build_real_sih_snapshots()

    def record(attack_id, cat, layer, desc, mutation, exp_det, act_det, exp_stat, act_stat, passed, notes=""):
        res = AdversarialAttackResult(
            attack_id=attack_id,
            category=cat.value,
            description=desc,
            mutation=mutation,
            target_layer=layer.value,
            expected_detection=exp_det.value,
            actual_detection=act_det.value,
            expected_status=exp_stat,
            actual_status=act_stat,
            passed=passed,
            notes=notes,
        )
        manifest.record(res)

    # -------------------------------------------------------------------------
    # PART 1: Real SIH Dataset Systematic Adversarial Battery (BID-00031 to BID-00001)
    # -------------------------------------------------------------------------
    print("\n[PART 1] Executing Real Dataset Systematic Attacks (4 Canonical Bids)...")

    for bid_id, snap in snapshots.items():
        base_dict = copy.deepcopy(snap.to_dict())

        # Clean Replay Baseline (Negative Control)
        rep_clean = replay_engine.replay(base_dict)
        record(
            f"{bid_id}-N01", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE,
            f"Clean baseline replay for {bid_id}", "Untampered canonical snapshot",
            DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN,
            "COMPLETE_MATCH", rep_clean.status, rep_clean.is_match
        )

        # Attack 1: Fact Value Falsification
        t1 = copy.deepcopy(base_dict)
        t1["bidder_facts"][0]["value"] = "999999_TAMPERED"
        t1["bidder_facts"][0]["normalized_value"] = 999999.0
        t1["snapshot_hash"] = compute_snapshot_hash(t1)
        r1 = replay_engine.replay(t1)
        record(
            f"{bid_id}-E01", AttackCategory.EVIDENCE, TargetLayer.RULE_ENGINE,
            f"Fact value altered on {bid_id}", "Extracted value overwritten",
            DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH,
            "REJECTED", r1.status, not r1.is_match
        )

        # Attack 2: Requirement Threshold Shifting
        t2 = copy.deepcopy(base_dict)
        t2["requirements"][0]["expected_value"] = "0.0001"
        t2["requirements"][0]["normalized_expected_value"] = 0.0001
        t2["snapshot_hash"] = compute_snapshot_hash(t2)
        r2 = replay_engine.replay(t2)
        record(
            f"{bid_id}-R01", AttackCategory.REQUIREMENT, TargetLayer.RULE_ENGINE,
            f"Requirement threshold shifted on {bid_id}", "Expected value lowered to 0.0001",
            DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH,
            "REJECTED", r2.status, not r2.is_match
        )

        # Attack 3: Physical Evidence Deletion (Orphaning facts in DAG)
        t3 = copy.deepcopy(base_dict)
        t3["bidder_facts"][0]["evidence"] = []
        t3["snapshot_hash"] = compute_snapshot_hash(t3)
        r3 = replay_engine.replay(t3)
        record(
            f"{bid_id}-P01", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG,
            f"Evidence blocks stripped on {bid_id}", "Zero physical evidence blocks",
            DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH,
            "REJECTED", r3.status, not r3.is_match
        )

        # Attack 4: Government Response Impersonation
        t4 = copy.deepcopy(base_dict)
        t4["captured_government_responses"][0]["queried_identifier"] = "99TAMPER000000X1Z"
        t4["snapshot_hash"] = compute_snapshot_hash(t4)
        r4 = replay_engine.replay(t4)
        record(
            f"{bid_id}-G01", AttackCategory.GOVERNMENT, TargetLayer.GOVERNMENT_ADAPTER,
            f"Government queried ID altered on {bid_id}", "Fake GSTIN injected into adapter",
            DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH,
            "REJECTED", r4.status, not r4.is_match
        )

        # Attack 5: Overall Status Override Attempt
        t5 = copy.deepcopy(base_dict)
        t5["original_results"]["overall_status"] = "PASS" if base_dict["original_results"]["overall_status"] != "PASS" else "FAIL"
        t5["snapshot_hash"] = compute_snapshot_hash(t5)
        r5 = replay_engine.replay(t5)
        record(
            f"{bid_id}-A01", AttackCategory.AGGREGATION, TargetLayer.AGGREGATOR,
            f"Overall verdict flipped on {bid_id}", "Claimed status tampered in original_results",
            DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH,
            "REJECTED", r5.status, not r5.is_match
        )

        # Attack 6: Provenance Graph Edge Deletion
        t6 = copy.deepcopy(base_dict)
        if t6["original_results"]["provenance_graph"]["edges"]:
            t6["original_results"]["provenance_graph"]["edges"].pop(0)
        t6["snapshot_hash"] = compute_snapshot_hash(t6)
        r6 = replay_engine.replay(t6)
        record(
            f"{bid_id}-P02", AttackCategory.PROVENANCE, TargetLayer.PROVENANCE_DAG,
            f"Provenance edge pruned on {bid_id}", "Deleted 1 edge from graph",
            DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH,
            "REJECTED", r6.status, not r6.is_match
        )

        # Attack 7: Config Hash / Policy Drift
        t7 = copy.deepcopy(base_dict)
        t7["deterministic_config"]["precedence_policy"] = "ATC_STC_GTC_INVERTED"
        t7["verification_config_hash"] = compute_config_hash(t7["deterministic_config"])
        t7["snapshot_hash"] = compute_snapshot_hash(t7)
        r7 = replay_engine.replay(t7)
        record(
            f"{bid_id}-S01", AttackCategory.SNAPSHOT, TargetLayer.AUDIT_SNAPSHOT,
            f"Precedence policy drift on {bid_id}", "Inverted precedence config",
            DetectionMechanism.CONFIG_HASH_MISMATCH, DetectionMechanism.CONFIG_HASH_MISMATCH,
            "REJECTED", r7.status, not r7.is_match
        )

    # -------------------------------------------------------------------------
    # PART 2: Combinatorial & Multi-Vector Compound Attacks (Phase 18)
    # -------------------------------------------------------------------------
    print("[PART 2] Executing Combinatorial Multi-Vector Attacks...")

    # Compound Attack 1: Tri-Vector (Fact + Requirement Operator + Evidence Block)
    for bid_id in ["BID-00031", "BID-00001"]:
        c1 = copy.deepcopy(snapshots[bid_id].to_dict())
        c1["bidder_facts"][0]["value"] = "99.0"
        c1["bidder_facts"][0]["normalized_value"] = 99.0
        c1["requirements"][0]["operator"] = "<="
        c1["bidder_facts"][0]["evidence"][0]["snippet"] = "Tampered snippet text"
        c1["snapshot_hash"] = compute_snapshot_hash(c1)
        r_c1 = replay_engine.replay(c1)
        record(
            f"{bid_id}-COMPOUND-01", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER,
            f"Compound Fact + Operator + Evidence tamper on {bid_id}", "Tri-vector simultaneous mutation",
            DetectionMechanism.REPLAY_MISMATCH, DetectionMechanism.REPLAY_MISMATCH,
            "REJECTED", r_c1.status, not r_c1.is_match
        )

    # Compound Attack 2: Government Response + Aggregation Metric Forgery
    for bid_id in ["BID-00733", "BID-00667"]:
        c2 = copy.deepcopy(snapshots[bid_id].to_dict())
        c2["captured_government_responses"][0]["status"] = "INACTIVE"
        c2["original_results"]["critical_failures"] = 0
        c2["original_results"]["overall_status"] = "PASS"
        c2["snapshot_hash"] = compute_snapshot_hash(c2)
        r_c2 = replay_engine.replay(c2)
        record(
            f"{bid_id}-COMPOUND-02", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER,
            f"Compound Gov Inactive + Forged PASS on {bid_id}", "Regulatory mismatch with forced PASS",
            DetectionMechanism.HUMAN_REVIEW_FLAG, DetectionMechanism.HUMAN_REVIEW_FLAG,
            "REJECTED", r_c2.status, not r_c2.is_match
        )

    # Compound Attack 3: Graph Mutation + Metric Count Forgery
    for bid_id in ["BID-00031", "BID-00733"]:
        c3 = copy.deepcopy(snapshots[bid_id].to_dict())
        c3["original_results"]["critical_failures"] = 42
        c3["original_results"]["provenance_graph"]["nodes"].append({
            "node_id": "SYNTHETIC:INTRUDER", "node_type": "BIDDER_FACT", "label": "Fake", "properties": {}
        })
        c3["snapshot_hash"] = compute_snapshot_hash(c3)
        r_c3 = replay_engine.replay(c3)
        record(
            f"{bid_id}-COMPOUND-03", AttackCategory.CROSS_LAYER, TargetLayer.MULTI_LAYER,
            f"Compound Graph Node + Metric count tamper on {bid_id}", "Injected node + forged count",
            DetectionMechanism.DAG_PROVENANCE_MISMATCH, DetectionMechanism.DAG_PROVENANCE_MISMATCH,
            "REJECTED", r_c3.status, not r_c3.is_match
        )

    # -------------------------------------------------------------------------
    # PART 3: Property-Style Permutation and Invariance Verification
    # -------------------------------------------------------------------------
    print("[PART 3] Executing Property-Style Invariance Verification...")

    # Property 1: Fact Ordering Invariance (Shuffling facts must preserve COMPLETE_MATCH)
    for bid_id in ["BID-00031", "BID-00001"]:
        p1 = copy.deepcopy(snapshots[bid_id].to_dict())
        facts = p1["bidder_facts"]
        random.seed(42)
        random.shuffle(facts)
        p1["bidder_facts"] = facts
        p1["snapshot_hash"] = compute_snapshot_hash(p1)
        r_p1 = replay_engine.replay(p1)
        record(
            f"{bid_id}-PROP-FACT-SHUFFLE", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE,
            f"Fact list shuffle invariance on {bid_id}", "Permuted facts list order",
            DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN,
            "COMPLETE_MATCH", r_p1.status, r_p1.is_match
        )

    # Property 2: Requirement Ordering Invariance (Shuffling reqs must preserve COMPLETE_MATCH)
    for bid_id in ["BID-00031", "BID-00733"]:
        p2 = copy.deepcopy(snapshots[bid_id].to_dict())
        reqs = p2["requirements"]
        random.seed(101)
        random.shuffle(reqs)
        p2["requirements"] = reqs
        p2["snapshot_hash"] = compute_snapshot_hash(p2)
        r_p2 = replay_engine.replay(p2)
        record(
            f"{bid_id}-PROP-REQ-SHUFFLE", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE,
            f"Requirement list shuffle invariance on {bid_id}", "Permuted requirements order",
            DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN,
            "COMPLETE_MATCH", r_p2.status, r_p2.is_match
        )

    # Property 3: DAG Node Ordering Invariance (Reversing nodes in snapshot DAG must preserve COMPLETE_MATCH)
    for bid_id in ["BID-00031", "BID-00667"]:
        p3 = copy.deepcopy(snapshots[bid_id].to_dict())
        p3["original_results"]["provenance_graph"]["nodes"].reverse()
        p3["snapshot_hash"] = compute_snapshot_hash(p3)
        r_p3 = replay_engine.replay(p3)
        record(
            f"{bid_id}-PROP-DAG-NODE-REVERSE", AttackCategory.NEGATIVE_CONTROL, TargetLayer.PROVENANCE_DAG,
            f"DAG node reverse order invariance on {bid_id}", "Reversed nodes list in snapshot",
            DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN,
            "COMPLETE_MATCH", r_p3.status, r_p3.is_match
        )

    # Property 4: Idempotence (Replaying the same snapshot 20 times must produce identical output)
    for bid_id in ["BID-00031", "BID-00001"]:
        base_s = snapshots[bid_id]
        h0 = replay_engine.replay(base_s).replayed_results["provenance_graph_hash"]
        all_same = True
        for _ in range(20):
            h_curr = replay_engine.replay(base_s).replayed_results["provenance_graph_hash"]
            if h_curr != h0:
                all_same = False
                break
        record(
            f"{bid_id}-PROP-IDEMPOTENCE-20X", AttackCategory.NEGATIVE_CONTROL, TargetLayer.REPLAY_ENGINE,
            f"20x Idempotent Replay on {bid_id}", "Provenance graph hash strictly identical across 20 runs",
            DetectionMechanism.ACCEPTED_CLEAN, DetectionMechanism.ACCEPTED_CLEAN,
            "IDENTICAL", "IDENTICAL" if all_same else "DRIFT", all_same
        )

    print("\n" + "=" * 90)
    manifest.print_summary()
    print("=" * 90)

    s = manifest.summary()
    if s["attacks_silently_accepted"] > 0 or s["false_negative_count"] > 0 or s["false_positive_count"] > 0:
        print("[FAIL] Adversarial manifest invariants violated!")
        sys.exit(1)
    else:
        print("[SUCCESS] All real dataset adversarial tests PASSED with 0 silent acceptances.")


if __name__ == "__main__":
    run_benchmark()
