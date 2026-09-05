import json
import jsonschema
from jsonschema import validate, ValidationError
import sys

def load_schema(schema_name):
    with open(f"contracts/{schema_name}", "r", encoding="utf-8") as f:
        return json.load(f)

# Load schemas
doc_schema = load_schema("document.schema.json")
req_schema = load_schema("requirement.schema.json")
fact_schema = load_schema("bidder_fact.schema.json")
verif_schema = load_schema("verification_result.schema.json")

def test_document_schema():
    valid_doc = {
        "document_id": "DOC-BID001-TECH-01",
        "parent_file": "BID-00001.pdf",
        "document_type": "TECHNICAL_SPECIFICATION",
        "page_start": 1,
        "page_end": 4,
        "source": "BIDDER",
        "extraction_status": "SUCCESS",
        "classification_confidence": "HIGH",
        "text_preview": "Technical specification for Network Switch 24-Port...",
        "metadata": {
            "file_size_bytes": 3793,
            "detected_language": "en",
            "is_scanned": False
        }
    }
    validate(instance=valid_doc, schema=doc_schema)

    # Invalid: missing required parent_file
    invalid_doc = valid_doc.copy()
    del invalid_doc["parent_file"]
    try:
        validate(instance=invalid_doc, schema=doc_schema)
        assert False, "Should have failed missing parent_file"
    except ValidationError:
        pass

def test_requirement_schema():
    valid_req = {
        "requirement_id": "REQ-FIN-001",
        "tender_id": "TENDER-0002",
        "category": "FINANCIAL_CAPACITY",
        "description": "Minimum average annual turnover for the last three financial years shall be INR 14.58 crore.",
        "field": "turnover_cr",
        "operator": ">=",
        "expected_value": 14.58,
        "normalized_expected_value": 145800000,
        "unit": "INR_CRORE",
        "mandatory": True,
        "source_type": "ATC",
        "source_clause": "7.2",
        "source_page": 8,
        "source_priority": 3,
        "applicability": {
            "mse_exemption_allowed": True,
            "startup_exemption_allowed": True
        },
        "evidence": [
            {
                "page": 8,
                "bbox": [56, 105, 283, 573],
                "snippet": "Minimum average annual turnover..."
            }
        ],
        "extraction_confidence": "HIGH"
    }
    validate(instance=valid_req, schema=req_schema)

    # Invalid: invalid operator
    invalid_req = valid_req.copy()
    invalid_req["operator"] = "LIKE_MAYBE"
    try:
        validate(instance=invalid_req, schema=req_schema)
        assert False, "Should have failed invalid operator"
    except ValidationError:
        pass

def test_bidder_fact_schema():
    valid_fact = {
        "fact_id": "FACT-BID001-TURNOVER-01",
        "bid_id": "BID-00001",
        "bidder_id": "Bharat Devices",
        "field": "average_annual_turnover",
        "value": 90000000,
        "normalized_value": 90000000,
        "unit": "INR",
        "source_document": "BID-00001.pdf",
        "page": 12,
        "bbox": [143, 416, 446, 563],
        "raw_text_snippet": "Average annual turnover certified by CA: Rs. 9,00,00,000",
        "extraction_confidence": "HIGH",
        "extraction_method": "LLM_STRUCTURED_EXTRACTION"
    }
    validate(instance=valid_fact, schema=fact_schema)

    # Valid: multi-block evidence preservation
    valid_multiblock_fact = valid_fact.copy()
    valid_multiblock_fact["evidence"] = [
        {
            "block_id": "BLK-01",
            "document": "BID-00001.pdf",
            "document_id": "DOC-BID001",
            "page": 12,
            "bbox": [143.0, 416.0, 446.0, 563.0],
            "snippet": "Average annual turnover certified by CA: Rs. 9,00,00,000",
            "source_type": "BIDDER_SUBMISSION"
        },
        {
            "block_id": "BLK-02",
            "document": "BID-00001.pdf",
            "document_id": "DOC-BID001",
            "page": 13,
            "bbox": [100.0, 50.0, 200.0, 400.0],
            "snippet": "Annexure A financial continuation",
            "source_type": "BIDDER_SUBMISSION"
        }
    ]
    validate(instance=valid_multiblock_fact, schema=fact_schema)

    # Valid: canonical_field and field_resolution metadata
    valid_canonical_fact = valid_fact.copy()
    valid_canonical_fact["canonical_field"] = "AVERAGE_ANNUAL_TURNOVER"
    valid_canonical_fact["field_resolution"] = {
        "raw_field": "average_annual_turnover",
        "canonical_field_id": "AVERAGE_ANNUAL_TURNOVER",
        "label": "Average Annual Turnover",
        "category": "FINANCIAL",
        "resolution_method": "EXACT_ALIAS",
        "resolution_status": "RESOLVED",
        "contradiction_eligible": True,
        "family": "TURNOVER"
    }
    validate(instance=valid_canonical_fact, schema=fact_schema)

    # Invalid: page < 1
    invalid_fact = valid_fact.copy()
    invalid_fact["page"] = 0
    try:
        validate(instance=invalid_fact, schema=fact_schema)
        assert False, "Should have failed page=0"
    except ValidationError:
        pass

def test_verification_result_schema():
    valid_verif = {
        "verification_id": "VERIF-BID001-REQ-FIN-001",
        "requirement_id": "REQ-FIN-001",
        "bid_id": "BID-00001",
        "fact_id": "FACT-BID001-TURNOVER-01",
        "status": "FAIL",
        "severity": "CRITICAL",
        "expected": ">= 14.58 INR Crore (145,800,000 INR)",
        "actual": "9.00 INR Crore (90,000,000 INR)",
        "operator_used": ">=",
        "reason": "Bidder's average annual turnover of 9.00 INR Crore is below the mandatory threshold of 14.58 INR Crore.",
        "evidence": [
            {
                "document": "BID-00001.pdf",
                "page": 12,
                "bbox": [143, 416, 446, 563],
                "snippet": "Average annual turnover: Rs. 9.00 Cr",
                "source_type": "BIDDER_SUBMISSION"
            }
        ],
        "anomaly_refs": ["ANOM-0000001"],
        "requires_human_review": True,
        "officer_override": None
    }
    validate(instance=valid_verif, schema=verif_schema)

    # Invalid: invalid status
    invalid_verif = valid_verif.copy()
    invalid_verif["status"] = "MAYBE"
    try:
        validate(instance=invalid_verif, schema=verif_schema)
        assert False, "Should have failed invalid status"
    except ValidationError:
        pass

if __name__ == "__main__":
    print("Running schema validation tests...")
    test_document_schema()
    print("? document.schema.json passed")
    test_requirement_schema()
    print("? requirement.schema.json passed")
    test_bidder_fact_schema()
    print("? bidder_fact.schema.json passed")
    test_verification_result_schema()
    print("? verification_result.schema.json passed")
    print("All schema unit tests PASSED successfully!")
