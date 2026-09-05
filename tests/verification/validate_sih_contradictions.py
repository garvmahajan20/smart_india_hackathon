# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter
import json
import os

sys.path.insert(0, os.path.abspath("."))

from backend.core.contradiction_engine import CrossDocumentContradictionEngine

def run_sih_contradiction_validation():
    dataset_path = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/text/contradiction_pairs.jsonl"
    if not os.path.exists(dataset_path):
        print(f"Error: dataset path not found: {dataset_path}")
        return

    engine = CrossDocumentContradictionEngine()

    total = 0
    exact_matches = 0
    mismatches = 0

    gt_status_counts = Counter()
    engine_status_counts = Counter()
    mismatch_by_type = Counter()
    sample_mismatches = []

    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            rec = json.loads(line)

            cid = rec.get("contradiction_id", f"PAIR-{total}")
            bid_id = rec.get("bid_id", "")
            field_type = rec.get("type", "")
            val_a = rec.get("value_a")
            val_b = rec.get("value_b")
            doc_a = rec.get("document_a", "")
            page_a = rec.get("page_a", 1)
            doc_b = rec.get("document_b", "")
            page_b = rec.get("page_b", 1)
            gt_status = rec.get("status", "CONTRADICTION")

            gt_status_counts[gt_status] += 1

            finding = engine.evaluate_pair(
                contradiction_id=cid,
                bid_id=bid_id,
                field_name="",
                value_a=val_a,
                value_b=val_b,
                document_a=doc_a,
                page_a=page_a,
                document_b=doc_b,
                page_b=page_b,
                hint_type=field_type,
            )

            engine_status = finding.status
            engine_status_counts[engine_status] += 1

            if engine_status == gt_status:
                exact_matches += 1
            else:
                mismatches += 1
                mismatch_by_type[field_type] += 1
                if len(sample_mismatches) < 5:
                    sample_mismatches.append({
                        "id": cid,
                        "type": field_type,
                        "val_a": val_a,
                        "val_b": val_b,
                        "gt": gt_status,
                        "engine": engine_status,
                        "reason": finding.description,
                    })

    print("================ SIH CONTRADICTION DATASET VALIDATION REPORT ================")
    print(f"Total Contradiction Cases Evaluated : {total}")
    print(f"Exact Status Matches                : {exact_matches} ({(exact_matches/total)*100:.2f}%)")
    print(f"Total Mismatches                    : {mismatches} ({(mismatches/total)*100:.2f}%)")
    print("-----------------------------------------------------------------------------")
    print(f"Ground Truth Status Distribution    : {dict(gt_status_counts)}")
    print(f"Engine Status Distribution          : {dict(engine_status_counts)}")
    print(f"Mismatches by Contradiction Type    : {dict(mismatch_by_type)}")
    if sample_mismatches:
        print("-----------------------------------------------------------------------------")
        print("Sample Mismatches:")
        for s in sample_mismatches:
            print(f"  [{s['id']}] {s['type']}: GT={s['gt']} vs Engine={s['engine']} | a='{s['val_a']}', b='{s['val_b']}'")
            print(f"    Reason: {s['reason']}")
    print("=============================================================================")

if __name__ == "__main__":
    run_sih_contradiction_validation()
