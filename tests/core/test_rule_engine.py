# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date
from decimal import Decimal
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    OperatorType,
    Severity,
    SourceType,
    TenderRequirement,
)
from backend.core.normalization import (
    normalize_boolean,
    normalize_categorical,
    normalize_currency,
    normalize_date,
    normalize_duration,
    normalize_existence,
    normalize_numeric,
)
from backend.core.operators import evaluate_operator
from backend.core.precedence import resolve_precedence
from backend.core.rule_engine import DeterministicRuleEngine

def test_numeric_normalization_and_comparison():
    val1, _ = normalize_numeric("₹31 lakh")
    val2, _ = normalize_numeric("3000000")
    assert val1 == Decimal("3100000")
    assert val2 == Decimal("3000000")

    # 31 lakh >= 30 lakh -> PASS
    res1 = evaluate_operator(">=", "₹31 lakh", "30 lakh")
    assert res1.status == ComplianceStatus.PASS

    # 29 lakh >= 30 lakh -> FAIL
    res2 = evaluate_operator(">=", "₹29 lakh", "30 lakh")
    assert res2.status == ComplianceStatus.FAIL

    # 31,00,000 >= 3.1 million -> PASS (equality)
    res3 = evaluate_operator(">=", "31,00,000", "3.1 million")
    assert res3.status == ComplianceStatus.PASS

def test_currency_equivalences():
    c1, _ = normalize_currency("₹31,00,000")
    c2, _ = normalize_currency("INR 3100000")
    c3, _ = normalize_currency("Rs. 31 lakh")
    assert c1 == c2 == c3 == Decimal("3100000")

    # Strict Decimal comparison (no floating point errors)
    assert evaluate_operator("==", "₹31,00,000", "INR 3100000").status == ComplianceStatus.PASS
    assert evaluate_operator("==", "Rs. 31 lakh", "31,00,000").status == ComplianceStatus.PASS

def test_duration_comparison():
    # 36 months >= 3 years -> PASS
    res1 = evaluate_operator(">=", "36 months", "3 years")
    assert res1.status == ComplianceStatus.PASS

    # 24 months >= 3 years -> FAIL
    res2 = evaluate_operator(">=", "24 months", "3 years")
    assert res2.status == ComplianceStatus.FAIL

    # word numbers: 'three years' == '36 months'
    res3 = evaluate_operator("==", "three years", "36 months")
    assert res3.status == ComplianceStatus.PASS

def test_date_operators():
    ref_date = date(2026, 8, 15)

    # VALID_ON
    # Active certificate
    cert_active = {"issue_date": "2025-01-01", "expiry_date": "2026-12-31", "valid": True}
    res_val = evaluate_operator("VALID_ON", cert_active, ref_date)
    assert res_val.status == ComplianceStatus.PASS

    # Expired certificate
    cert_expired = {"issue_date": "2024-01-01", "expiry_date": "2026-08-01", "valid": True}
    res_exp = evaluate_operator("VALID_ON", cert_expired, ref_date)
    assert res_exp.status == ComplianceStatus.FAIL

    # Boundary date (expires on the exact reference date)
    cert_boundary = {"issue_date": "2025-01-01", "expiry_date": "2026-08-15", "valid": True}
    res_bound = evaluate_operator("VALID_ON", cert_boundary, ref_date)
    assert res_bound.status == ComplianceStatus.PASS

    # BEFORE
    assert evaluate_operator("BEFORE", "2026-08-14", "2026-08-15").status == ComplianceStatus.PASS
    assert evaluate_operator("BEFORE", "2026-08-15", "2026-08-15").status == ComplianceStatus.FAIL

    # AFTER
    assert evaluate_operator("AFTER", "2026-08-16", "2026-08-15").status == ComplianceStatus.PASS
    assert evaluate_operator("AFTER", "2026-08-15", "2026-08-15").status == ComplianceStatus.FAIL

def test_boolean_normalization():
    for true_val in ["Yes", "yes", "true", "True", "Y", "y", "1", 1, True]:
        assert normalize_boolean(true_val) is True
    for false_val in ["No", "no", "false", "False", "N", "n", "0", 0, False]:
        assert normalize_boolean(false_val) is False

    assert evaluate_operator("==", "Yes", True).status == ComplianceStatus.PASS
    assert evaluate_operator("==", "No", True).status == ComplianceStatus.FAIL

def test_categorical_operators():
    # IN
    assert evaluate_operator("IN", "Class 1", ["Class 1", "Class 2"]).status == ComplianceStatus.PASS
    assert evaluate_operator("IN", "Class 3", ["Class 1", "Class 2"]).status == ComplianceStatus.FAIL

    # NOT_IN
    assert evaluate_operator("NOT_IN", "Class 3", ["Class 1", "Class 2"]).status == ComplianceStatus.PASS
    assert evaluate_operator("NOT_IN", "Class 1", ["Class 1", "Class 2"]).status == ComplianceStatus.FAIL

    # == case & whitespace normalization
    assert evaluate_operator("==", " ISO  14001:2015 ", "iso 14001:2015").status == ComplianceStatus.PASS
    assert evaluate_operator("!=", "ISO 9001", "ISO 14001").status == ComplianceStatus.PASS

def test_existence_operator():
    assert evaluate_operator("EXISTS", "OEM Authorization Letter").status == ComplianceStatus.PASS
    assert evaluate_operator("EXISTS", "").status == ComplianceStatus.MISSING
    assert evaluate_operator("EXISTS", None).status == ComplianceStatus.MISSING
    assert evaluate_operator("EXISTS", "Not available").status == ComplianceStatus.MISSING

def test_text_operators():
    # CONTAINS
    assert evaluate_operator("CONTAINS", "Supply of 24 Port Gigabit Switch", "Gigabit").status == ComplianceStatus.PASS
    assert evaluate_operator("CONTAINS", "Supply of 24 Port Gigabit Switch", "Wireless").status == ComplianceStatus.FAIL

    # MATCHES regex
    assert evaluate_operator("MATCHES", "29SYNTH0000003F1Z", r"^29SYNTH\d{7}[A-Z\d]{3}$").status == ComplianceStatus.PASS
    assert evaluate_operator("MATCHES", "INVALID_GSTIN", r"^\d{2}[A-Z]{5}\d{4}").status == ComplianceStatus.FAIL

def test_between_operator():
    assert evaluate_operator("BETWEEN", "15", [10, 20]).status == ComplianceStatus.PASS
    assert evaluate_operator("BETWEEN", "10", [10, 20]).status == ComplianceStatus.PASS # lower boundary
    assert evaluate_operator("BETWEEN", "20", [10, 20]).status == ComplianceStatus.PASS # upper boundary
    assert evaluate_operator("BETWEEN", "25", [10, 20]).status == ComplianceStatus.FAIL
    assert evaluate_operator("BETWEEN", "5", [10, 20]).status == ComplianceStatus.FAIL

def test_invalid_data_handling():
    # Non-numeric against numeric requirement: must NEVER return PASS
    res_nan = evaluate_operator(">=", "Invalid Text", "1000000")
    assert res_nan.status == ComplianceStatus.REVIEW
    assert res_nan.requires_human_review is True

    # Invalid date: must NEVER return PASS
    res_bad_date = evaluate_operator("BEFORE", "not-a-date", "2026-08-01")
    assert res_bad_date.status == ComplianceStatus.REVIEW
    assert res_bad_date.requires_human_review is True

    # Malformed regex: must NEVER return PASS
    res_bad_regex = evaluate_operator("MATCHES", "sample", "[unclosed-bracket")
    assert res_bad_regex.status == ComplianceStatus.REVIEW
    assert res_bad_regex.requires_human_review is True

    # Unsupported operator: must NEVER return PASS
    res_bad_op = evaluate_operator("UNKNOWN_OP", 10, 20)
    assert res_bad_op.status == ComplianceStatus.REVIEW
    assert res_bad_op.requires_human_review is True

def test_conditional_exemptions():
    engine = DeterministicRuleEngine()

    req = TenderRequirement(
        requirement_id="REQ-TURNOVER-01",
        tender_id="TENDER-001",
        category="FINANCIAL_CAPACITY",
        description="Minimum turnover ₹50 Lakh",
        field="turnover_cr",
        operator=">=",
        expected_value=5000000,
        applicability={"mse_exemption_allowed": True}
    )

    # 1. Condition established: bidder is MSE with verified status
    # Statutory exemptions return N/A (Not Applicable), NEVER PASS
    facts_mse = [
        BidderFact(
            fact_id="F1", bid_id="B1", field="is_mse", value=True,
            source_document="udyam.pdf", page=1
        ),
        BidderFact(
            fact_id="F2", bid_id="B1", field="turnover_cr", value=2000000, # below 50L
            source_document="balance_sheet.pdf", page=12
        )
    ]
    res_exempt = engine.verify_bid([req], facts_mse)
    assert len(res_exempt) == 1
    assert res_exempt[0].status == ComplianceStatus.N_A.value
    assert "exemption applied" in res_exempt[0].reason.lower()

    # 2. Condition NOT established: bidder is NOT MSE
    facts_non_mse = [
        BidderFact(
            fact_id="F1", bid_id="B2", field="is_mse", value=False,
            source_document="declaration.pdf", page=1
        ),
        BidderFact(
            fact_id="F2", bid_id="B2", field="turnover_cr", value=2000000, # below 50L
            source_document="balance_sheet.pdf", page=12
        )
    ]
    res_no_exempt = engine.verify_bid([req], facts_non_mse)
    assert len(res_no_exempt) == 1
    assert res_no_exempt[0].status == ComplianceStatus.FAIL.value
    assert "below threshold" in res_no_exempt[0].reason

def test_precedence_resolution_chain():
    """
    Controlled GTC/STC/ATC Precedence Test:
    GTC: turnover >= ₹50 lakh (priority 1)
    STC: turnover >= ₹40 lakh (priority 2)
    ATC: turnover >= ₹30 lakh (priority 3)
    Effective requirement: turnover >= ₹30 lakh (ATC)
    Chain preserved: GTC -> superseded by STC -> superseded by ATC
    Non-conflicting warranty clause remains active.
    """
    gtc_req = TenderRequirement(
        requirement_id="REQ-GTC-01",
        tender_id="TENDER-001",
        category="FINANCIAL_CAPACITY",
        description="GTC: Turnover >= 50 Lakh",
        field="turnover",
        operator=">=",
        expected_value=5000000,
        source_type=SourceType.GTC.value,
        source_priority=1
    )
    stc_req = TenderRequirement(
        requirement_id="REQ-STC-01",
        tender_id="TENDER-001",
        category="FINANCIAL_CAPACITY",
        description="STC: Turnover >= 40 Lakh",
        field="turnover",
        operator=">=",
        expected_value=4000000,
        source_type=SourceType.STC.value,
        source_priority=2
    )
    atc_req = TenderRequirement(
        requirement_id="REQ-ATC-01",
        tender_id="TENDER-001",
        category="FINANCIAL_CAPACITY",
        description="ATC: Turnover >= 30 Lakh",
        field="turnover",
        operator=">=",
        expected_value=3000000,
        source_type=SourceType.ATC.value,
        source_priority=3
    )
    # Non-conflicting clause
    warranty_req = TenderRequirement(
        requirement_id="REQ-WARRANTY-01",
        tender_id="TENDER-001",
        category="TECHNICAL_SPECIFICATION",
        description="Warranty >= 2 years",
        field="warranty_years",
        operator=">=",
        expected_value=2,
        source_type=SourceType.GTC.value,
        source_priority=1
    )

    pres_res = resolve_precedence([gtc_req, stc_req, atc_req, warranty_req])

    # Effective requirements: ATC turnover (prio 3) + Warranty (prio 1)
    effective_ids = [r.requirement_id for r in pres_res.effective_requirements]
    assert "REQ-ATC-01" in effective_ids
    assert "REQ-WARRANTY-01" in effective_ids
    assert len(pres_res.effective_requirements) == 2

    # Superseded requirements: GTC and STC
    superseded_ids = [r.requirement_id for r in pres_res.superseded_requirements]
    assert "REQ-GTC-01" in superseded_ids
    assert "REQ-STC-01" in superseded_ids
    assert len(pres_res.superseded_requirements) == 2

    # All 4 requirements preserved (none deleted!)
    assert len(pres_res.all_requirements) == 4

    # Run through rule engine
    engine = DeterministicRuleEngine()
    facts = [
        BidderFact(fact_id="F1", bid_id="B1", field="turnover", value=3500000, source_document="doc.pdf", page=1), # 35L (satisfies ATC 30L, would have failed GTC 50L & STC 40L)
        BidderFact(fact_id="F2", bid_id="B1", field="warranty_years", value=3, source_document="doc.pdf", page=2)
    ]
    results = engine.verify_bid([gtc_req, stc_req, atc_req, warranty_req], facts)

    res_by_id = {r.requirement_id: r for r in results}

    # ATC turnover must PASS because 35L >= 30L
    assert res_by_id["REQ-ATC-01"].status == ComplianceStatus.PASS.value

    # GTC and STC must be marked N/A with superseded explanation
    assert res_by_id["REQ-GTC-01"].status == ComplianceStatus.N_A.value
    assert "Superseded by REQ-ATC-01" in res_by_id["REQ-GTC-01"].reason
    assert res_by_id["REQ-STC-01"].status == ComplianceStatus.N_A.value
    assert "Superseded by REQ-ATC-01" in res_by_id["REQ-STC-01"].reason

    # Non-conflicting warranty must PASS
    assert res_by_id["REQ-WARRANTY-01"].status == ComplianceStatus.PASS.value

def test_evidence_propagation():
    engine = DeterministicRuleEngine()
    req = TenderRequirement(
        requirement_id="REQ-ISO-01",
        tender_id="T-01",
        category="CERTIFICATION",
        description="ISO 9001:2015 certificate required",
        field="iso_cert",
        operator="==",
        expected_value="ISO 9001:2015"
    )
    fact = BidderFact(
        fact_id="FACT-CERT-01",
        bid_id="BID-01",
        field="iso_cert",
        value="ISO 9001:2015",
        source_document="iso_certificate.pdf",
        page=3,
        bbox=[100.0, 50.0, 300.0, 500.0],
        raw_text_snippet="Certificate of Registration: ISO 9001:2015 Quality Management",
        extraction_confidence="HIGH",
        metadata={"anomaly_refs": ["ANOM-NONE"]}
    )

    results = engine.verify_bid([req], [fact])
    assert len(results) == 1
    res = results[0]

    assert res.status == ComplianceStatus.PASS.value
    assert res.fact_id == "FACT-CERT-01"
    assert len(res.evidence) == 1
    ev = res.evidence[0]
    assert ev["document"] == "iso_certificate.pdf"
    assert ev["page"] == 3
    assert ev["bbox"] == [100.0, 50.0, 300.0, 500.0]
    assert "Certificate of Registration" in ev["snippet"]

def test_provenance_safety_regression():
    """
    REGRESSION TEST: Verify that raw SIH clauses are NEVER assigned ATC provenance.
    SIH tender clauses do not specify GTC/STC/ATC and must default to UNSPECIFIED / UNKNOWN.
    """
    import json
    with open("data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/metadata/tenders.jsonl", "r", encoding="utf-8") as f:
        tender = json.loads(f.readline())

    for clause in tender["clauses"]:
        req = TenderRequirement(
            requirement_id=clause["clause_id"],
            tender_id=tender["tender_id"],
            category=clause["clause_type"].upper(),
            description=clause["requirement_text"],
            field=clause["field"],
            operator=clause["operator"],
            expected_value=clause["expected_value"],
            source_type=SourceType.UNSPECIFIED.value,
            source_priority=0
        )
        assert req.source_type != SourceType.ATC.value, f"Clause {req.requirement_id} manufactured ATC provenance!"
        assert req.source_priority == 0, f"Clause {req.requirement_id} manufactured priority 3!"

if __name__ == "__main__":
    test_numeric_normalization_and_comparison()
    print("✓ Numeric tests passed")
    test_currency_equivalences()
    print("✓ Currency tests passed")
    test_duration_comparison()
    print("✓ Duration tests passed")
    test_date_operators()
    print("✓ Date tests passed")
    test_boolean_normalization()
    print("✓ Boolean tests passed")
    test_categorical_operators()
    print("✓ Categorical tests passed")
    test_existence_operator()
    print("✓ Existence tests passed")
    test_text_operators()
    print("✓ Text tests passed")
    test_between_operator()
    print("✓ Between tests passed")
    test_invalid_data_handling()
    print("✓ Invalid data tests passed")
    test_conditional_exemptions()
    print("✓ Conditional exemption tests passed")
    test_precedence_resolution_chain()
    print("✓ Precedence resolution chain tests passed")
    test_evidence_propagation()
    print("✓ Evidence propagation tests passed")
    test_provenance_safety_regression()
    print("✓ Provenance safety regression tests passed")
    print("\nALL 14 UNIT TESTS PASSED SUCCESSFULLY!")
