import json
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.abspath("."))

from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    SourceType,
    TenderRequirement,
)
from backend.core.rule_engine import DeterministicRuleEngine

def run_layer2_sanity_validation():
    engine = DeterministicRuleEngine(default_evaluation_date=date(2026, 8, 20))

    # Real-world requirements sampled from NCPOR GeM & Conventional tenders:
    # 1. Minimum Average Annual Turnover (gem_821_010626.PDF, Page 1) - GTC
    # 2. Past Experience Criteria (gem_821_010626.PDF, Page 2) - GTC
    # 3. OEM Authorization Certificate (gem_821_010626.PDF, Page 2) - ATC
    # 4. ePBG Percentage and Duration (gem_821_010626.PDF, Page 3) - STC
    # 5. MSE Purchase Preference Exemption (gem_821_010626.PDF, Page 4) - GTC
    # 6. EMD Exemption for MSE (gem_821_010626.PDF, Page 3) - GTC
    # 7. Local Content / Make in India Percentage (gem_072_110726.PDF, Page 8) - ATC
    # 8. Delivery Period Compliance (gem_538_060826.PDF, Page 1) - STC
    # 9. ISO Certification Requirement (gem_072_110726.PDF, Page 14) - ATC
    # 10. Bid Validity Period (gem_821_010626.PDF, Page 1) - GTC

    layer2_requirements = [
        TenderRequirement(
            requirement_id="L2-REQ-01-TURNOVER",
            tender_id="GEM/2026/B/7743020",
            category="FINANCIAL_CAPACITY",
            description="Minimum Average Annual Turnover of the bidder (For 3 Years) shall be INR 5 Lakh.",
            field="turnover_inr",
            operator=">=",
            expected_value=500000,
            normalized_expected_value=500000,
            unit="INR",
            source_type=SourceType.GTC.value,
            source_clause="Bid Details Item 1",
            source_page=1,
            source_priority=1,
            applicability={"mse_exemption_allowed": True, "startup_exemption_allowed": True}
        ),
        TenderRequirement(
            requirement_id="L2-REQ-02-EXPERIENCE",
            tender_id="GEM/2026/B/7743020",
            category="EXPERIENCE_PAST_PERFORMANCE",
            description="Experience Criteria: Minimum 3 years of similar supply experience.",
            field="experience_years",
            operator=">=",
            expected_value=3,
            normalized_expected_value=3,
            unit="YEARS",
            source_type=SourceType.GTC.value,
            source_clause="Experience Criteria",
            source_page=2,
            source_priority=1,
            applicability={"mse_exemption_allowed": True, "startup_exemption_allowed": True}
        ),
        TenderRequirement(
            requirement_id="L2-REQ-03-OEM-AUTH",
            tender_id="GEM/2026/B/7743020",
            category="CERTIFICATION",
            description="OEM Authorization Certificate required from seller.",
            field="oem_authorization",
            operator="EXISTS",
            expected_value=True,
            source_type=SourceType.ATC.value,
            source_clause="Document required from seller",
            source_page=2,
            source_priority=3,
            mandatory=True
        ),
        TenderRequirement(
            requirement_id="L2-REQ-04-EPBG",
            tender_id="GEM/2026/B/7743020",
            category="COMMERCIAL_TERMS",
            description="ePBG Percentage 5.00% with required duration 14 Months.",
            field="epbg_percentage",
            operator=">=",
            expected_value=5.0,
            unit="PERCENT",
            source_type=SourceType.STC.value,
            source_clause="ePBG Detail",
            source_page=3,
            source_priority=2
        ),
        TenderRequirement(
            requirement_id="L2-REQ-05-EMD-EXEMPTION",
            tender_id="GEM/2026/B/7743020",
            category="STATUTORY_ELIGIBILITY",
            description="EMD Exemption under MSE category for manufacturers/service providers.",
            field="emd_submitted",
            operator="==",
            expected_value=True,
            source_type=SourceType.GTC.value,
            source_clause="EMD Exemption Clause (a)",
            source_page=3,
            source_priority=1,
            applicability={"mse_exemption_allowed": True}
        ),
        TenderRequirement(
            requirement_id="L2-REQ-06-LOCAL-CONTENT",
            tender_id="GEM/2026/B/7883658",
            category="MSE_MII_PREFERENCE",
            description="Class 1 Local Supplier: Minimum 50% Local Content under Make in India.",
            field="local_content_percent",
            operator=">=",
            expected_value=50.0,
            unit="PERCENT",
            source_type=SourceType.ATC.value,
            source_clause="MII Policy Annexure",
            source_page=8,
            source_priority=3
        ),
        TenderRequirement(
            requirement_id="L2-REQ-07-DELIVERY-PERIOD",
            tender_id="GEM/2026/B/7874538",
            category="DELIVERY_LOGISTICS",
            description="Delivery and commissioning completed within 30 days.",
            field="delivery_days",
            operator="<=",
            expected_value=30,
            unit="DAYS",
            source_type=SourceType.STC.value,
            source_clause="Delivery Schedule",
            source_page=1,
            source_priority=2
        ),
        TenderRequirement(
            requirement_id="L2-REQ-08-ISO-CERT",
            tender_id="GEM/2026/B/7883658",
            category="CERTIFICATION",
            description="Valid ISO 9001:2015 certificate on bid opening date.",
            field="iso_cert",
            operator="VALID_ON",
            expected_value="2026-08-20",
            source_type=SourceType.ATC.value,
            source_clause="ATC Document Upload",
            source_page=14,
            source_priority=3
        ),
        TenderRequirement(
            requirement_id="L2-REQ-09-BID-VALIDITY",
            tender_id="GEM/2026/B/7743020",
            category="COMMERCIAL_TERMS",
            description="Bid Offer Validity: Minimum 90 Days from closing date.",
            field="bid_validity_days",
            operator=">=",
            expected_value=90,
            unit="DAYS",
            source_type=SourceType.GTC.value,
            source_clause="Bid Details",
            source_page=1,
            source_priority=1
        ),
        TenderRequirement(
            requirement_id="L2-REQ-10-SUBJECTIVE-DISCRETION",
            tender_id="NCPOR/PS/SOE-50869/GT-07",
            category="TECHNICAL_SPECIFICATION",
            description="User division reserves right to inspect workshop facility prior to award.",
            field="workshop_inspection_right",
            operator="CONTAINS",
            expected_value="accepted",
            source_type=SourceType.CUSTOM.value,
            source_clause="Special Conditions",
            source_page=2,
            source_priority=1
        ),
    ]

    # Test candidate bidder facts
    bidder_facts = [
        BidderFact(fact_id="BF-01", bid_id="BID-L2-01", field="turnover_inr", value="6.5 Lakh", normalized_value=650000, source_document="doc.pdf", page=1),
        BidderFact(fact_id="BF-02", bid_id="BID-L2-01", field="experience_years", value="4 years", normalized_value=4, source_document="exp.pdf", page=3),
        BidderFact(fact_id="BF-03", bid_id="BID-L2-01", field="oem_authorization", value="Enclosed OEM Authorization Letter", source_document="oem.pdf", page=1),
        BidderFact(fact_id="BF-04", bid_id="BID-L2-01", field="epbg_percentage", value="5%", normalized_value=5.0, source_document="bank.pdf", page=1),
        BidderFact(fact_id="BF-05", bid_id="BID-L2-01", field="is_mse", value=True, source_document="udyam.pdf", page=1), # triggers exemption for EMD
        BidderFact(fact_id="BF-06", bid_id="BID-L2-01", field="local_content_percent", value=65.0, source_document="mii_decl.pdf", page=1),
        BidderFact(fact_id="BF-07", bid_id="BID-L2-01", field="delivery_days", value="25 days", source_document="spec.pdf", page=2),
        BidderFact(fact_id="BF-08", bid_id="BID-L2-01", field="iso_cert", value={"issue_date": "2025-01-01", "expiry_date": "2027-01-01", "valid": True}, source_document="iso.pdf", page=1),
        BidderFact(fact_id="BF-09", bid_id="BID-L2-01", field="bid_validity_days", value=90, source_document="form.pdf", page=1),
        # Note: BF-10 for subjective discretion is unsubmitted / ambiguous
    ]

    results = engine.verify_bid(layer2_requirements, bidder_facts, evaluation_date=date(2026, 8, 20))

    represented_count = 0
    review_count = 0
    missing_count = 0

    print("================ LAYER 2 REAL-WORLD SANITY VALIDATION ================")
    for res in results:
        status = res.status
        if status in [ComplianceStatus.PASS.value, ComplianceStatus.FAIL.value, ComplianceStatus.N_A.value]:
            represented_count += 1
            icon = "?"
        elif status == ComplianceStatus.REVIEW.value:
            review_count += 1
            icon = "!"
        else:
            missing_count += 1
            icon = "?"

        print(f"[{icon}] {res.requirement_id:28s}: status={status:7s} (sev={res.severity:8s})")
        print(f"    Reason: {res.reason}")

    print("----------------------------------------------------------------------")
    print(f"Total Layer 2 Requirements Tested : {len(layer2_requirements)}")
    print(f"Successfully Represented / Decided: {represented_count}")
    print(f"Flagged for Human REVIEW          : {review_count}")
    print(f"Unrepresented / MISSING Evidence  : {missing_count}")
    print("======================================================================")

if __name__ == "__main__":
    run_layer2_sanity_validation()
