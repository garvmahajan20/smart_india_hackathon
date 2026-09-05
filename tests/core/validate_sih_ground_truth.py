import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.abspath("."))

from backend.core.models import BidderFact, ComplianceStatus, SourceType, TenderRequirement
from backend.core.rule_engine import DeterministicRuleEngine

def run_sih_ground_truth_validation(sample_limit=None):
    path = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/text/clause_pairs.jsonl"
    if not os.path.exists(path):
        print(f"Error: {path} not found.")
        return

    engine = DeterministicRuleEngine()

    total_evaluated = 0
    pass_matches = 0
    fail_matches = 0
    partial_matches = 0
    missing_matches = 0
    review_cases = 0
    mismatches = 0

    mismatch_categories = Counter()
    sample_mismatches = []

    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if sample_limit and idx >= sample_limit:
                break

            pair = json.loads(line)
            total_evaluated += 1

            # Provenance-safe requirement: NO fabricated ATC!
            req = TenderRequirement(
                requirement_id=pair["clause_id"],
                tender_id=pair["tender_id"],
                category=pair.get("clause_type", "UNSPECIFIED").upper(),
                description=pair.get("requirement_text", ""),
                field=pair["field"],
                operator=pair["operator"],
                expected_value=pair["expected_value"],
                source_type=SourceType.UNSPECIFIED.value,
                source_priority=0,
                mandatory=True
            )

            fact = BidderFact(
                fact_id=pair["pair_id"],
                bid_id=pair["bid_id"],
                field=pair["field"],
                value=pair["extracted_value"],
                page=pair.get("page", 1) or 1,
                source_document=f"{pair['bid_id']}.pdf",
                raw_text_snippet=pair.get("bid_text", "")
            )

            results = engine.verify_bid([req], [fact])
            res = results[0]
            engine_status = res.status
            gt_status = pair["compliance_status"]

            if engine_status == gt_status:
                if gt_status == "PASS":
                    pass_matches += 1
                elif gt_status == "FAIL":
                    fail_matches += 1
                elif gt_status == "PARTIAL":
                    partial_matches += 1
                elif gt_status == "MISSING":
                    missing_matches += 1
            else:
                if engine_status == "REVIEW":
                    review_cases += 1
                mismatches += 1

                # Categorize mismatch
                val = pair["extracted_value"]
                exp = pair["expected_value"]
                op = pair["operator"]
                field = pair["field"]

                if engine_status == "REVIEW":
                    cat = "engine_review_uncertain_extraction"
                elif val in ["Not available", "NA", None, ""]:
                    cat = "missing_or_unextracted_value"
                elif isinstance(val, str) and not val.replace(".", "", 1).isdigit() and op in [">=", "<=", ">", "<"]:
                    cat = "normalization_non_numeric_comparison"
                elif op == "==" and isinstance(val, (int, float)) and isinstance(exp, str):
                    cat = "type_mismatch_string_vs_number"
                elif "exempt" in str(pair.get("bid_text", "")).lower():
                    cat = "exemption_condition_handling"
                else:
                    cat = "boundary_or_operator_divergence"

                mismatch_categories[cat] += 1
                if len(sample_mismatches) < 5:
                    sample_mismatches.append({
                        "pair_id": pair["pair_id"],
                        "field": field,
                        "op": op,
                        "expected": exp,
                        "extracted": val,
                        "engine_status": engine_status,
                        "gt_status": gt_status,
                        "reason": res.reason,
                        "category": cat
                    })

    accuracy = ((pass_matches + fail_matches + partial_matches + missing_matches) / total_evaluated * 100) if total_evaluated else 0.0

    print("================ SIH GROUND-TRUTH VALIDATION REPORT ================")
    print(f"Total Cases Evaluated : {total_evaluated}")
    print(f"Exact PASS Matches    : {pass_matches}")
    print(f"Exact FAIL Matches    : {fail_matches}")
    print(f"Exact PARTIAL Matches : {partial_matches}")
    print(f"Exact MISSING Matches : {missing_matches}")
    print(f"REVIEW Cases Produced : {review_cases}")
    print(f"Total Mismatches      : {mismatches}")
    print(f"Accuracy Rate         : {accuracy:.2f}%")
    print("--------------------------------------------------------------------")
    print("Mismatch Categories:")
    for cat, cnt in mismatch_categories.most_common():
        pct = (cnt / total_evaluated * 100) if total_evaluated else 0
        print(f"  - {cat:38s}: {cnt:5d} ({pct:.2f}%)")
    print("--------------------------------------------------------------------")
    print("Sample Mismatches (first 5):")
    for s in sample_mismatches:
        print(f"  [{s['category']}] {s['pair_id']} (field: {s['field']}, op: {s['op']})")
        print(f"     expected={s['expected']}, actual={s['extracted']}")
        print(f"     engine={s['engine_status']} vs gt={s['gt_status']}")
        print(f"     reason: {s['reason']}")
    print("====================================================================")

if __name__ == "__main__":
    run_sih_ground_truth_validation()
