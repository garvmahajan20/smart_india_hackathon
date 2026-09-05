# -*- coding: utf-8 -*-
"""
Phase 10B.4 Real-Dataset Deterministic Replay Benchmark.

Validates:
1. Full Audit Snapshot creation on 4 canonical SIH dataset cases:
   - BID-00031 (BluePeak Solutions - CLEAN / PASS)
   - BID-00733 (Pragati Technologies - NON_COMPLIANT / FAIL)
   - BID-00001 (Bharat Devices - MANIPULATED / CONTRADICTION)
   - BID-00667 (Suryodaya Infra - UNCERTAIN / REVIEW)
2. Structural validation of snapshots.
3. Cryptographic SHA-256 hashing determinism.
4. Independent deterministic replay without Gemini, network, or filesystem dependencies.
5. Performance profiling: Snapshot build time, serialization time, hashing time, replay time, overhead ratio.
6. Adversarial tamper detection on real dataset snapshots.
"""

import sys
sys.stdout.reconfigure(encoding="utf-8")
import copy
import hashlib
import json
import os
import time

sys.path.insert(0, os.path.abspath("."))

from backend.core.models import BidderFact, TenderRequirement
from backend.core.rule_engine import DeterministicRuleEngine
from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.orchestration.aggregator import VerificationAggregator
from backend.core.provenance_dag import ProvenanceDAGBuilder
from backend.core.snapshot import (
    AuditSnapshot,
    SnapshotBuilder,
    canonical_json,
    compute_snapshot_hash,
    compute_config_hash,
    validate_snapshot_dict,
)
from backend.core.replay_engine import (
    DeterministicReplayEngine,
    MismatchCategory,
)
from backend.verification.mock_gst import MockGSTAdapter
from backend.verification.mock_pan import MockPANAdapter
from backend.verification.mock_debarment import MockDebarmentAdapter


def main():
    print("=" * 115)
    print("           PHASE 10B.4: DETERMINISTIC REPLAY ENGINE & AUDIT SNAPSHOT BENCHMARK            ")
    print("=" * 115)

    base_dir = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1"
    clause_path = os.path.join(base_dir, "text", "clause_pairs.jsonl")
    contra_path = os.path.join(base_dir, "text", "contradiction_pairs.jsonl")

    target_bids = {
        "BID-00031": {"company": "BluePeak Solutions", "expected_label": "CLEAN"},
        "BID-00733": {"company": "Pragati Technologies", "expected_label": "NON_COMPLIANT"},
        "BID-00667": {"company": "Suryodaya Infra", "expected_label": "UNCERTAIN"},
        "BID-00001": {"company": "Bharat Devices", "expected_label": "MANIPULATED"},
    }

    # 1. Load Tender Requirements for TENDER-0069
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

    # 2. Load Facts per Bid
    bid_facts = {b: [] for b in target_bids}
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
                    evidence=[
                        {
                            "block_id": f"BLK-{bid}-{fld}-01",
                            "document": f"{bid}.pdf",
                            "page": r.get("page", 1),
                            "bbox": [50.0, 100.0, 200.0, 400.0],
                            "snippet": f"Physical extract for {fld}: {r.get('extracted_value')}",
                        }
                    ]
                ))

    # 3. Load Contradictions
    bid_contradictions = {b: [] for b in target_bids}
    with open(contra_path, "r", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            bid = r.get("bid_id")
            if bid in target_bids and r.get("status") == "CONTRADICTION":
                bid_contradictions[bid].append(r)

    # Initialise Engines
    rule_engine = DeterministicRuleEngine()
    contra_engine = CrossDocumentContradictionEngine()
    aggregator = VerificationAggregator()
    gst_adapter = MockGSTAdapter()
    pan_adapter = MockPANAdapter()
    debar_adapter = MockDebarmentAdapter()
    replay_engine = DeterministicReplayEngine()

    benchmark_rows = []
    snapshots = {}

    for bid_id, info in target_bids.items():
        company = info["company"]
        expected_label = info["expected_label"]
        facts = bid_facts[bid_id]

        # ---------------------------------------------------------
        # Phase 1: Original Pipeline Execution
        # ---------------------------------------------------------
        t_orig_start = time.perf_counter()

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
            gst_adapter.verify("29SYNTH0000003F1Z", expected_name=company),
            pan_adapter.verify("SYNTH0003F", expected_name=company),
            debar_adapter.verify(company),
        ]

        aggregated = aggregator.aggregate(
            tender_id="TENDER-0069",
            bid_id=bid_id,
            compliance_results=comp_results,
            integrity_findings=int_findings,
            government_responses=gov_responses,
        )

        orig_time_ms = (time.perf_counter() - t_orig_start) * 1000.0

        # ---------------------------------------------------------
        # Phase 2: Audit Snapshot Construction
        # ---------------------------------------------------------
        t_snap_start = time.perf_counter()
        snapshot = SnapshotBuilder.build(
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
        )
        snap_time_ms = (time.perf_counter() - t_snap_start) * 1000.0

        # ---------------------------------------------------------
        # Phase 3: Serialization & Validation
        # ---------------------------------------------------------
        t_ser_start = time.perf_counter()
        snap_json = snapshot.to_json()
        ser_time_ms = (time.perf_counter() - t_ser_start) * 1000.0
        snap_size_kb = len(snap_json.encode("utf-8")) / 1024.0

        t_val_start = time.perf_counter()
        validation_errors = validate_snapshot_dict(snapshot.to_dict())
        val_time_ms = (time.perf_counter() - t_val_start) * 1000.0
        assert len(validation_errors) == 0, f"Snapshot validation errors: {validation_errors}"

        # ---------------------------------------------------------
        # Phase 4: Deterministic Replay Engine Execution
        # ---------------------------------------------------------
        t_replay_start = time.perf_counter()
        replay_result = replay_engine.replay(snapshot)
        replay_time_ms = (time.perf_counter() - t_replay_start) * 1000.0

        assert replay_result.is_match, f"Replay failed for {bid_id}: {replay_result.mismatches}"
        assert replay_result.status == MismatchCategory.COMPLETE_MATCH.value

        # Check Byte-for-byte Determinism
        replay_json_1 = replay_result.to_json()
        replay_json_2 = replay_engine.replay(snapshot).to_json()
        assert replay_json_1 == replay_json_2, "Replay JSON serialization is not byte-for-byte identical!"

        snapshots[bid_id] = snapshot

        overhead_ratio = replay_time_ms / orig_time_ms if orig_time_ms > 0 else 1.0

        benchmark_rows.append({
            "bid_id": bid_id,
            "company": company,
            "gt_label": expected_label,
            "orig_time_ms": orig_time_ms,
            "snap_time_ms": snap_time_ms,
            "ser_time_ms": ser_time_ms,
            "val_time_ms": val_time_ms,
            "replay_time_ms": replay_time_ms,
            "snap_size_kb": snap_size_kb,
            "overhead_ratio": overhead_ratio,
            "replay_status": replay_result.status,
            "dag_nodes": replay_result.replayed_results["provenance_node_count"],
            "dag_edges": replay_result.replayed_results["provenance_edge_count"],
            "snapshot_hash": snapshot.snapshot_hash[:12] + "...",
        })

    # Print Formatted Results Table
    print(f"\n{'BID ID':<11} | {'GT LABEL':<14} | {'ORIG (ms)':<10} | {'SNAP (ms)':<10} | {'REPLAY(ms)':<11} | {'SIZE (KB)':<10} | {'RATIO':<7} | {'STATUS':<15} | {'DAG NODES/EDGES'}")
    print("-" * 115)
    for r in benchmark_rows:
        print(f"{r['bid_id']:<11} | {r['gt_label']:<14} | {r['orig_time_ms']:<10.2f} | {r['snap_time_ms']:<10.2f} | {r['replay_time_ms']:<11.2f} | {r['snap_size_kb']:<10.2f} | {r['overhead_ratio']:<7.2f} | {r['replay_status']:<15} | {r['dag_nodes']}/{r['dag_edges']}")

    print("-" * 115)

    # ---------------------------------------------------------
    # Phase 5: Adversarial Tamper Verification on Real Snapshots
    # ---------------------------------------------------------
    print("\nADVERSARIAL TAMPER VERIFICATION ON REAL DATASET SNAPSHOTS:")
    clean_snap = snapshots["BID-00031"]

    # Tamper 1: Fact Value Modification
    t1 = copy.deepcopy(clean_snap.to_dict())
    t1["bidder_facts"][0]["value"] = "TAMPERED_VALUE"
    t1["snapshot_hash"] = compute_snapshot_hash(t1)
    res_t1 = replay_engine.replay(t1)
    assert not res_t1.is_match
    print(f"  [PASS] Tamper 1 (Fact Value): Detected as {res_t1.status}")

    # Tamper 2: Requirement Threshold Alteration
    t2 = copy.deepcopy(clean_snap.to_dict())
    t2["requirements"][0]["operator"] = "=="
    t2["snapshot_hash"] = compute_snapshot_hash(t2)
    res_t2 = replay_engine.replay(t2)
    assert not res_t2.is_match
    print(f"  [PASS] Tamper 2 (Requirement Operator): Detected as {res_t2.status}")

    # Tamper 3: Provenance DAG Edge Deletion
    t3 = copy.deepcopy(clean_snap.to_dict())
    del t3["original_results"]["provenance_graph"]["edges"][0]
    t3["snapshot_hash"] = compute_snapshot_hash(t3)
    res_t3 = replay_engine.replay(t3)
    assert not res_t3.is_match
    print(f"  [PASS] Tamper 3 (DAG Edge Deletion): Detected as {res_t3.status}")

    # Tamper 4: Government Response Tampering
    t4 = copy.deepcopy(clean_snap.to_dict())
    t4["captured_government_responses"][0]["status"] = "IDENTITY_MISMATCH"
    t4["snapshot_hash"] = compute_snapshot_hash(t4)
    res_t4 = replay_engine.replay(t4)
    assert not res_t4.is_match
    print(f"  [PASS] Tamper 4 (Government Response): Detected as {res_t4.status}")

    # Tamper 5: Config Modification
    t5 = copy.deepcopy(clean_snap.to_dict())
    t5["deterministic_config"]["rule_engine_version"] = "9.9.9"
    t5["verification_config_hash"] = compute_config_hash(t5["deterministic_config"])
    t5["snapshot_hash"] = compute_snapshot_hash(t5)
    res_t5 = replay_engine.replay(t5)
    assert not res_t5.is_match
    print(f"  [PASS] Tamper 5 (Config Hash/Version): Detected as {res_t5.status}")

    # Summary Statistics
    avg_snap_ms = sum(r["snap_time_ms"] for r in benchmark_rows) / len(benchmark_rows)
    avg_replay_ms = sum(r["replay_time_ms"] for r in benchmark_rows) / len(benchmark_rows)
    avg_size_kb = sum(r["snap_size_kb"] for r in benchmark_rows) / len(benchmark_rows)
    avg_ratio = sum(r["overhead_ratio"] for r in benchmark_rows) / len(benchmark_rows)

    print("\nBENCHMARK SUMMARY:")
    print(f"  Total Canonical SIH Cases Tested : {len(benchmark_rows)} / 4 (100% Verified)")
    print(f"  Average Snapshot Build Time      : {avg_snap_ms:.2f} ms")
    print(f"  Average Replay Verification Time : {avg_replay_ms:.2f} ms")
    print(f"  Average Snapshot Size            : {avg_size_kb:.2f} KB")
    print(f"  Average Replay Overhead Ratio    : {avg_ratio:.2f}x")
    print(f"  Determinism (Byte-for-byte)      : 100% Identical Across Runs")
    print(f"  External API Quota Consumed      : 0 calls (Quota Safe)")
    print(f"  Gemini Calls Consumed            : 0 calls (Quota Safe)")
    print("=" * 115)


if __name__ == "__main__":
    main()
