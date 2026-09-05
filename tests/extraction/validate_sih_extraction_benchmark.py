# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import json
import os
import time

sys.path.insert(0, os.path.abspath("."))

from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.core.models import BidderFact, TenderRequirement
from backend.core.rule_engine import DeterministicRuleEngine
from backend.extraction.cache import LLMCache
from backend.extraction.models import LLMMode
from backend.extraction.pipeline import ExtractionPipeline
from backend.ingestion.pipeline import DocumentIngestionPipeline

def run_sih_benchmarks():
    print("================================================================================")
    print("               STEP 7 SIH DATASET EXTRACTION & BENCHMARK VALIDATION             ")
    print("================================================================================")

    cache = LLMCache()
    pipeline = ExtractionPipeline(mode=LLMMode.MOCK)
    rule_engine = DeterministicRuleEngine()
    contra_engine = CrossDocumentContradictionEngine()

    tenders_dir = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/tenders"
    bids_dir = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/bids"

    # 1. Tender Requirements Extraction Benchmark
    tender_sample = [os.path.join(tenders_dir, f"TENDER-{i:04d}.pdf") for i in range(1, 11)]
    t0 = time.perf_counter()
    total_reqs = 0
    tenders_processed = 0

    for t_path in tender_sample:
        if os.path.exists(t_path):
            reqs = pipeline.extract_tender_requirements(t_path)
            total_reqs += len(reqs)
            tenders_processed += 1

    t1 = time.perf_counter()
    req_time = t1 - t0

    print(f"1. TENDER REQUIREMENTS EXTRACTION:")
    print(f"   Tenders Processed             : {tenders_processed}")
    print(f"   Total Requirements Extracted  : {total_reqs}")
    print(f"   Average Reqs per Tender       : {total_reqs / tenders_processed:.1f}")
    print(f"   Elapsed Time                  : {req_time:.3f} s ({(req_time/tenders_processed)*1000:.1f} ms/tender)")

    # 2. Bidder Facts Extraction Benchmark
    bid_sample = [os.path.join(bids_dir, f"BID-{i:05d}.pdf") for i in range(1, 21)]
    t0 = time.perf_counter()
    total_facts = 0
    bids_processed = 0

    for b_path in bid_sample:
        if os.path.exists(b_path):
            facts = pipeline.extract_bidder_facts(b_path)
            total_facts += len(facts)
            bids_processed += 1

    t1 = time.perf_counter()
    fact_time = t1 - t0

    print(f"\n2. BIDDER FACTS EXTRACTION:")
    print(f"   Bids Processed                : {bids_processed}")
    print(f"   Total Facts Extracted         : {total_facts}")
    print(f"   Average Facts per Bid         : {total_facts / bids_processed:.1f}")
    print(f"   Elapsed Time                  : {fact_time:.3f} s ({(fact_time/bids_processed)*1000:.1f} ms/bid)")

    # 3. Downstream Ground-Truth Compliance Evaluation against clause_pairs.jsonl
    print(f"\n3. DOWNSTREAM GROUND-TRUTH COMPLIANCE ALIGNMENT:")
    clause_pairs_path = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/text/clause_pairs.jsonl"
    tested_pairs = 0
    ground_truth_aligned = 0

    with open(clause_pairs_path, "r", encoding="utf-8") as f:
        for line in f:
            if tested_pairs >= 50:
                break
            record = json.loads(line)
            tested_pairs += 1

            # Extract requirement and fact using canonical ground-truth schema
            req_field = record.get("field", "turnover_cr")
            gt_compliance = record.get("compliance_status", "PASS")

            req = TenderRequirement(
                requirement_id=record.get("clause_id", f"REQ-{tested_pairs}"),
                tender_id=record.get("tender_id", "TENDER-0001"),
                category="TECHNICAL_SPECIFICATION",
                description=record.get("requirement_text", ""),
                field=req_field,
                operator=record.get("operator", ">="),
                expected_value=record.get("expected_value", 0),
                mandatory=True
            )

            fact = BidderFact(
                fact_id=f"FACT-CP-{tested_pairs}",
                bid_id=record.get("bid_id", "BID-00001"),
                field=req_field,
                value=record.get("extracted_value"),
                source_document=f"{record.get('bid_id')}.pdf",
                page=record.get("page", 1),
                extraction_confidence="HIGH"
            )

            verif = rule_engine.verify_bid([req], [fact])
            if verif and verif[0].status == gt_compliance:
                ground_truth_aligned += 1

    print(f"   Evaluated Clause Pairs        : {tested_pairs}")
    print(f"   Ground-Truth Status Aligned   : {ground_truth_aligned} / {tested_pairs} ({(ground_truth_aligned/tested_pairs)*100:.1f}%)")

    # 4. Contradiction Benchmark Evaluation against contradiction_pairs.jsonl
    print(f"\n4. CONTRADICTION BENCHMARK REPRODUCTION:")
    contra_path = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/text/contradiction_pairs.jsonl"
    contra_tested = 0
    contra_detected = 0

    with open(contra_path, "r", encoding="utf-8") as f:
        for line in f:
            if contra_tested >= 30:
                break
            record = json.loads(line)
            contra_tested += 1

            finding = contra_engine.evaluate_pair(
                contradiction_id=record.get("contradiction_id", f"C-{contra_tested}"),
                bid_id=record.get("bid_id", "BID-00001"),
                field_name="",
                value_a=record.get("value_a"),
                value_b=record.get("value_b"),
                document_a=record.get("document_a", "doc_a.pdf"),
                page_a=record.get("page_a", 1),
                document_b=record.get("document_b", "doc_b.pdf"),
                page_b=record.get("page_b", 2),
                hint_type=record.get("type", ""),
            )

            if finding.status == record.get("status", "CONTRADICTION"):
                contra_detected += 1

    print(f"   Contradiction Pairs Tested    : {contra_tested}")
    print(f"   Contradictions Accurately Flagged: {contra_detected} / {contra_tested} ({(contra_detected/contra_tested)*100:.1f}%)")

    # 5. Determinism Verification across 3 runs
    print(f"\n5. DETERMINISM VERIFICATION (3 REPEATED RUNS):")
    sample_pdf = tender_sample[0]
    runs = []
    for r in range(3):
        reqs = pipeline.extract_tender_requirements(sample_pdf)
        dump = json.dumps([r.to_dict() for r in reqs], sort_keys=True)
        runs.append(dump)
        print(f"   Run #{r+1}: Extracted {len(reqs)} reqs, {len(dump)} bytes serialized")

    is_deterministic = (runs[0] == runs[1] == runs[2])
    print(f"   Determinism Status (Run 1 == Run 2 == Run 3): {is_deterministic}")
    assert is_deterministic, "Pipeline is not deterministic across repeated runs!"

if __name__ == "__main__":
    run_sih_benchmarks()
