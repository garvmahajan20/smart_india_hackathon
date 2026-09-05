import json
import jsonschema
from jsonschema import validate

def load_schema(schema_name):
    with open(f"contracts/{schema_name}", "r", encoding="utf-8") as f:
        return json.load(f)

req_schema = load_schema("requirement.schema.json")
fact_schema = load_schema("bidder_fact.schema.json")
verif_schema = load_schema("verification_result.schema.json")

# Category mapping lookup for SIH clause_types
CATEGORY_MAP = {
    "financial_capacity": "FINANCIAL_CAPACITY",
    "technical_spec": "TECHNICAL_SPECIFICATION",
    "experience": "EXPERIENCE_PAST_PERFORMANCE",
    "certification": "CERTIFICATION",
    "eligibility": "STATUTORY_ELIGIBILITY"
}

def test_sih_tenders_to_requirement_schema():
    with open("data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/metadata/tenders.jsonl", "r", encoding="utf-8") as f:
        count = 0
        for line in f:
            tender = json.loads(line)
            t_id = tender["tender_id"]
            for clause in tender["clauses"]:
                # Map to canonical requirement contract
                canonical_req = {
                    "requirement_id": clause["clause_id"],
                    "tender_id": t_id,
                    "category": CATEGORY_MAP.get(clause["clause_type"], "OTHER"),
                    "description": clause["requirement_text"],
                    "field": clause["field"],
                    "operator": clause["operator"],
                    "expected_value": clause["expected_value"],
                    "normalized_expected_value": clause["expected_value"],
                    "unit": clause.get("unit") or None,
                    "mandatory": True,
                    "source_type": "UNSPECIFIED",
                    "source_clause": clause["clause_id"].split("/")[-1],
                    "source_page": 1,
                    "source_priority": 0,
                    "applicability": {
                        "mse_exemption_allowed": True,
                        "startup_exemption_allowed": True
                    },
                    "extraction_confidence": "HIGH"
                }
                validate(instance=canonical_req, schema=req_schema)
                count += 1
            if count >= 100:
                break
        print(f"? Validated {count} SIH tender clauses against requirement.schema.json")

def test_sih_clause_pairs_to_fact_and_verif_schema():
    with open("data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/text/clause_pairs.jsonl", "r", encoding="utf-8") as f:
        count = 0
        for line in f:
            pair = json.loads(line)
            
            # Map fact
            canonical_fact = {
                "fact_id": f"FACT-{pair['pair_id']}",
                "bid_id": pair["bid_id"],
                "bidder_id": pair["bid_id"],
                "field": pair["field"],
                "value": pair["extracted_value"],
                "normalized_value": pair["extracted_value"],
                "source_document": f"{pair['bid_id']}.pdf",
                "page": pair.get("page", 1) or 1,
                "bbox": pair.get("bbox"),
                "raw_text_snippet": pair.get("bid_text", ""),
                "extraction_confidence": "HIGH",
                "extraction_method": "LLM_STRUCTURED_EXTRACTION"
            }
            validate(instance=canonical_fact, schema=fact_schema)

            # Map verification result
            canonical_verif = {
                "verification_id": f"VERIF-{pair['pair_id']}",
                "requirement_id": pair["clause_id"],
                "bid_id": pair["bid_id"],
                "fact_id": canonical_fact["fact_id"],
                "status": "PASS" if pair["compliance_status"] == "PASS" else "FAIL",
                "severity": "CRITICAL" if pair["compliance_status"] == "FAIL" else "INFO",
                "expected": f"{pair['operator']} {pair['expected_value']}",
                "actual": str(pair["extracted_value"]),
                "operator_used": pair["operator"],
                "reason": f"Evaluated {pair['extracted_value']} {pair['operator']} {pair['expected_value']}",
                "evidence": [
                    {
                        "document": f"{pair['bid_id']}.pdf",
                        "page": pair.get("page", 1) or 1,
                        "bbox": pair.get("bbox"),
                        "snippet": pair.get("bid_text", ""),
                        "source_type": "BIDDER_SUBMISSION"
                    }
                ],
                "requires_human_review": pair.get("ground_truth_issue", False)
            }
            validate(instance=canonical_verif, schema=verif_schema)
            count += 1
            if count >= 100:
                break
        print(f"? Validated {count} SIH clause pairs against bidder_fact and verification_result schemas")

def test_layer2_real_world_requirements():
    layer2_examples = [
        {
            "requirement_id": "L2-NCPOR-GEM821-FIN-01",
            "tender_id": "GEM/2026/B/7743020",
            "category": "FINANCIAL_CAPACITY",
            "description": "Minimum Average Annual Turnover of the bidder (For 3 Years) shall be 5 Lakh INR.",
            "field": "bidder_turnover_lakh",
            "operator": ">=",
            "expected_value": 5.0,
            "normalized_expected_value": 500000,
            "unit": "INR_LAKH",
            "mandatory": True,
            "source_type": "GTC",
            "source_clause": "Bid Details Item 1",
            "source_page": 1,
            "source_priority": 1,
            "applicability": {
                "mse_exemption_allowed": True,
                "startup_exemption_allowed": True
            },
            "extraction_confidence": "HIGH"
        },
        {
            "requirement_id": "L2-NCPOR-GEM821-EPBG-01",
            "tender_id": "GEM/2026/B/7743020",
            "category": "COMMERCIAL_TERMS",
            "description": "ePBG Percentage 5.00% with duration of 14 months.",
            "field": "epbg_percentage",
            "operator": ">=",
            "expected_value": 5.0,
            "normalized_expected_value": 5.0,
            "unit": "PERCENT",
            "mandatory": True,
            "source_type": "STC",
            "source_clause": "ePBG Detail (a)",
            "source_page": 3,
            "source_priority": 2,
            "extraction_confidence": "HIGH"
        },
        {
            "requirement_id": "L2-NCPOR-GEM821-MSE-01",
            "tender_id": "GEM/2026/B/7743020",
            "category": "MSE_MII_PREFERENCE",
            "description": "MSE Purchase Preference available up to price within L1+15% for 25% of quantity.",
            "field": "mse_purchase_preference",
            "operator": "==",
            "expected_value": True,
            "normalized_expected_value": True,
            "unit": "BOOLEAN",
            "mandatory": False,
            "source_type": "GTC",
            "source_clause": "MSE Purchase Preference",
            "source_page": 4,
            "source_priority": 1,
            "extraction_confidence": "HIGH"
        },
        {
            "requirement_id": "L2-NCPOR-GEM821-DOC-01",
            "tender_id": "GEM/2026/B/7743020",
            "category": "CERTIFICATION",
            "description": "OEM Authorization Certificate required from seller.",
            "field": "oem_authorization_certificate",
            "operator": "EXISTS",
            "expected_value": True,
            "normalized_expected_value": True,
            "unit": "BOOLEAN",
            "mandatory": True,
            "source_type": "ATC",
            "source_clause": "Document required from seller",
            "source_page": 2,
            "source_priority": 3,
            "extraction_confidence": "HIGH"
        }
    ]
    for req in layer2_examples:
        validate(instance=req, schema=req_schema)
    print(f"? Validated {len(layer2_examples)} real-world Layer 2 requirements against requirement.schema.json")

if __name__ == "__main__":
    test_sih_tenders_to_requirement_schema()
    test_sih_clause_pairs_to_fact_and_verif_schema()
    test_layer2_real_world_requirements()
    print("All dataset mapping tests PASSED successfully!")
