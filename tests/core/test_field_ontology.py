# -*- coding: utf-8 -*-
"""
Tests for Phase 10B.2: Deterministic Canonical Field Ontology & Synonym Resolver.

Validates all 18 required behaviors, 3+ adversarial collision prevention cases,
BidderFact & TenderRequirement integration, and Contradiction Engine explainability.
"""

import unittest
from typing import Dict, Any

from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    Severity,
    TenderRequirement,
)
from backend.core.ontology import (
    CANONICAL_FIELDS,
    CanonicalCategory,
    CanonicalFieldResult,
    ResolutionMethod,
    ResolutionStatus,
    get_canonical_field,
    list_canonical_fields,
    normalize_field_key,
    resolve_field,
)
from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.core.rule_engine import DeterministicRuleEngine


class TestCanonicalFieldOntology(unittest.TestCase):
    """Core ontology unit tests covering resolution and normalization."""

    def test_01_exact_canonical_field_resolves(self):
        res = resolve_field("ANNUAL_TURNOVER")
        self.assertEqual(res.resolution_status, ResolutionStatus.RESOLVED.value)
        self.assertEqual(res.resolution_method, ResolutionMethod.EXACT_CANONICAL.value)
        self.assertEqual(res.canonical_field_id, "ANNUAL_TURNOVER")
        self.assertEqual(res.raw_field, "ANNUAL_TURNOVER")
        self.assertTrue(res.contradiction_eligible)

    def test_02_exact_alias_resolves(self):
        res = resolve_field("annual_turnover")
        self.assertEqual(res.resolution_status, ResolutionStatus.RESOLVED.value)
        self.assertEqual(res.resolution_method, ResolutionMethod.EXACT_ALIAS.value)
        self.assertEqual(res.canonical_field_id, "ANNUAL_TURNOVER")
        self.assertEqual(res.category, CanonicalCategory.FINANCIAL.value)

    def test_03_normalized_alias_resolves(self):
        res = resolve_field("  Annual Turnover  ")
        self.assertEqual(res.resolution_status, ResolutionStatus.RESOLVED.value)
        self.assertEqual(res.resolution_method, ResolutionMethod.NORMALIZED_ALIAS.value)
        self.assertEqual(res.canonical_field_id, "ANNUAL_TURNOVER")

    def test_04_case_differences_resolve_safely(self):
        variations = [
            "TuRnOvEr_AmOuNt",
            "TURNOVER_CR",
            "Gstin",
            "WaRrAnTy_YeArS",
            "dElIvErY_dAyS",
        ]
        expected_canonicals = [
            "ANNUAL_TURNOVER",
            "ANNUAL_TURNOVER",
            "GSTIN",
            "WARRANTY_DURATION",
            "DELIVERY_PERIOD",
        ]
        for var, exp in zip(variations, expected_canonicals):
            res = resolve_field(var)
            self.assertEqual(res.resolution_status, ResolutionStatus.RESOLVED.value, f"Failed for {var}")
            self.assertEqual(res.canonical_field_id, exp, f"Mismatch for {var}")

    def test_05_separator_normalization_resolves_safely(self):
        variations = [
            "annual--turnover",
            "annual  turnover",
            "annual/turnover",
            "turnover__amount",
            "delivery-period",
            "lead_time_days",
        ]
        for var in variations:
            res = resolve_field(var)
            self.assertEqual(res.resolution_status, ResolutionStatus.RESOLVED.value, f"Failed on separator: {var}")
            self.assertIsNotNone(res.canonical_field_id)

    def test_06_unknown_field_returns_unmapped(self):
        res = resolve_field("some_completely_fictional_unregistered_metric_xyz")
        self.assertEqual(res.resolution_status, ResolutionStatus.UNMAPPED.value)
        self.assertIsNone(res.canonical_field_id)
        self.assertIsNone(res.resolution_method)
        self.assertEqual(res.raw_field, "some_completely_fictional_unregistered_metric_xyz")

        # Also test None and empty string
        res_none = resolve_field(None)
        self.assertEqual(res_none.resolution_status, ResolutionStatus.UNMAPPED.value)
        res_empty = resolve_field("   ")
        self.assertEqual(res_empty.resolution_status, ResolutionStatus.UNMAPPED.value)

    def test_07_ambiguous_field_returns_ambiguous(self):
        ambiguous_candidates = [
            "experience",
            "EXPERIENCE",
            "  experience  ",
            "certificate",
            "financials",
            "financial_capacity",
            "validity",
            "security",
            "deposit",
            "turnover_ratio",
        ]
        for cand in ambiguous_candidates:
            res = resolve_field(cand)
            self.assertEqual(
                res.resolution_status,
                ResolutionStatus.AMBIGUOUS.value,
                f"Failed to flag '{cand}' as AMBIGUOUS"
            )
            self.assertIsNone(res.canonical_field_id, f"'{cand}' must have None canonical_id")
            self.assertFalse(res.contradiction_eligible)

    def test_08_semantically_similar_distinct_fields_do_not_collapse(self):
        # 1. annual_turnover vs average_annual_turnover
        res_to = resolve_field("annual_turnover")
        res_aato = resolve_field("average_annual_turnover")
        self.assertNotEqual(res_to.canonical_field_id, res_aato.canonical_field_id)
        self.assertEqual(res_to.canonical_field_id, "ANNUAL_TURNOVER")
        self.assertEqual(res_aato.canonical_field_id, "AVERAGE_ANNUAL_TURNOVER")

        # 2. experience_years vs similar_projects
        res_exp = resolve_field("experience_years")
        res_proj = resolve_field("similar_projects")
        self.assertNotEqual(res_exp.canonical_field_id, res_proj.canonical_field_id)
        self.assertEqual(res_exp.canonical_field_id, "PAST_EXPERIENCE_DURATION")
        self.assertEqual(res_proj.canonical_field_id, "SIMILAR_PROJECTS_COUNT")

        # 3. emd_required vs emd_amount
        res_emd_flag = resolve_field("emd_required")
        res_emd_amt = resolve_field("emd_amount")
        self.assertNotEqual(res_emd_flag.canonical_field_id, res_emd_amt.canonical_field_id)
        self.assertEqual(res_emd_flag.canonical_field_id, "EMD_REQUIREMENT")
        self.assertEqual(res_emd_amt.canonical_field_id, "EMD_AMOUNT")

        # 4. epbg_percentage vs epbg_amount
        res_epbg_pct = resolve_field("epbg_percentage")
        res_epbg_amt = resolve_field("epbg_amount")
        self.assertNotEqual(res_epbg_pct.canonical_field_id, res_epbg_amt.canonical_field_id)
        self.assertEqual(res_epbg_pct.canonical_field_id, "EPBG_PERCENTAGE")
        self.assertEqual(res_epbg_amt.canonical_field_id, "EPBG_AMOUNT")

    def test_09_annual_turnover_vs_turnover_amount_canonicalize(self):
        res1 = resolve_field("annual_turnover")
        res2 = resolve_field("turnover_amount")
        res3 = resolve_field("turnover_cr")
        self.assertEqual(res1.canonical_field_id, "ANNUAL_TURNOVER")
        self.assertEqual(res2.canonical_field_id, "ANNUAL_TURNOVER")
        self.assertEqual(res3.canonical_field_id, "ANNUAL_TURNOVER")

    def test_10_raw_field_name_remains_preserved(self):
        raw = "My_Custom_Vendor_Annual_Turnover_Claim"
        res = resolve_field(raw)
        self.assertEqual(res.raw_field, raw)

        raw2 = "turnover_amount"
        fact = BidderFact(
            fact_id="F-01",
            bid_id="B-01",
            field=raw2,
            value=10000000,
            source_document="doc.pdf",
            page=1,
        )
        self.assertEqual(fact.field, raw2)
        self.assertEqual(fact.canonical_field, "ANNUAL_TURNOVER")
        self.assertEqual(fact.field_resolution["raw_field"], raw2)

    def test_11_resolution_metadata_is_serialized(self):
        fact = BidderFact(
            fact_id="F-02",
            bid_id="B-01",
            field="turnover_cr",
            value=15.5,
            source_document="audit.pdf",
            page=4,
        )
        d = fact.to_dict()
        self.assertIn("canonical_field", d)
        self.assertEqual(d["canonical_field"], "ANNUAL_TURNOVER")
        self.assertIn("field_resolution", d)
        self.assertEqual(d["field_resolution"]["raw_field"], "turnover_cr")
        self.assertEqual(d["field_resolution"]["canonical_field_id"], "ANNUAL_TURNOVER")
        self.assertEqual(d["field_resolution"]["resolution_status"], "RESOLVED")

    def test_12_contradiction_engine_compares_differently_named_equivalent_fields(self):
        engine = CrossDocumentContradictionEngine()

        # Doc A: "annual_turnover" says 10 Crore
        # Doc B: "turnover_amount" says 5 Crore
        fact_a = BidderFact(
            fact_id="F-A",
            bid_id="BID-ONT-01",
            field="annual_turnover",
            value="10.0 crore",
            source_document="technical_proposal.pdf",
            page=2,
        )
        fact_b = BidderFact(
            fact_id="F-B",
            bid_id="BID-ONT-01",
            field="turnover_amount",
            value="5.0 crore",
            source_document="financial_sheet.pdf",
            page=1,
        )

        findings = engine.detect_contradictions_in_bid("BID-ONT-01", [fact_a, fact_b])
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.status, "CONTRADICTION")
        self.assertEqual(finding.field, "ANNUAL_TURNOVER")
        self.assertEqual(finding.raw_field_a, "annual_turnover")
        self.assertEqual(finding.raw_field_b, "turnover_amount")
        self.assertEqual(finding.canonical_field, "ANNUAL_TURNOVER")
        self.assertIn("annual_turnover", finding.description)
        self.assertIn("turnover_amount", finding.description)

    def test_13_unrelated_fields_do_not_become_contradictions(self):
        engine = CrossDocumentContradictionEngine()

        # Doc A: annual_turnover = 10 Crore
        # Doc B: net_worth_cr = 5 Crore
        fact_to = BidderFact(
            fact_id="F-1",
            bid_id="BID-ONT-02",
            field="annual_turnover",
            value=10.0,
            source_document="doc1.pdf",
            page=1,
        )
        fact_nw = BidderFact(
            fact_id="F-2",
            bid_id="BID-ONT-02",
            field="net_worth_cr",
            value=5.0,
            source_document="doc2.pdf",
            page=1,
        )

        findings = engine.detect_contradictions_in_bid("BID-ONT-02", [fact_to, fact_nw])
        self.assertEqual(len(findings), 0, "Unrelated fields must NOT group together")

    def test_14_existing_contradiction_fixtures_remain_unchanged(self):
        engine = CrossDocumentContradictionEngine()
        # Same exact field names across documents
        fact_1 = BidderFact(
            fact_id="F-1",
            bid_id="BID-03",
            field="turnover_cr",
            value=12.24,
            source_document="doc1.pdf",
            page=1,
        )
        fact_2 = BidderFact(
            fact_id="F-2",
            bid_id="BID-03",
            field="turnover_cr",
            value=17.02,
            source_document="doc2.pdf",
            page=1,
        )
        findings = engine.detect_contradictions_in_bid("BID-03", [fact_1, fact_2])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].status, "CONTRADICTION")
        self.assertEqual(findings[0].severity, "HIGH")

    def test_15_ontology_does_not_alter_compliance_results(self):
        engine = DeterministicRuleEngine()

        req = TenderRequirement(
            requirement_id="REQ-01",
            tender_id="TENDER-01",
            category="FINANCIAL_CAPACITY",
            description="Annual turnover >= 10 Crore",
            field="annual_turnover",
            operator=">=",
            expected_value=10.0,
        )

        # Fact submitted with alias "turnover_amount" = 12.0
        fact = BidderFact(
            fact_id="F-01",
            bid_id="B-01",
            field="turnover_amount",
            value=12.0,
            source_document="bid.pdf",
            page=1,
        )

        results = engine.verify_bid([req], [fact])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, ComplianceStatus.PASS.value)
        self.assertEqual(results[0].severity, Severity.INFO.value)

    def test_16_ontology_does_not_alter_evidence_grounding(self):
        fact = BidderFact(
            fact_id="F-01",
            bid_id="B-01",
            field="turnover_cr",
            value=15.0,
            source_document="audit.pdf",
            page=3,
            bbox=[100.0, 200.0, 300.0, 400.0],
            raw_text_snippet="Annual turnover certified: 15.0 Cr",
            evidence=[
                {
                    "block_id": "BLK-01",
                    "document": "audit.pdf",
                    "page": 3,
                    "bbox": [100.0, 200.0, 300.0, 400.0],
                    "snippet": "Annual turnover certified: 15.0 Cr",
                }
            ],
        )
        self.assertEqual(fact.page, 3)
        self.assertEqual(fact.bbox, [100.0, 200.0, 300.0, 400.0])
        self.assertEqual(len(fact.evidence), 1)
        self.assertEqual(fact.evidence[0]["block_id"], "BLK-01")

    def test_17_ontology_does_not_alter_severity_assignment(self):
        engine = CrossDocumentContradictionEngine()
        fact_gst1 = BidderFact(
            fact_id="F-G1",
            bid_id="B-01",
            field="gstin",
            value="29SYNTH0000003F1Z",
            source_document="d1.pdf",
            page=1,
        )
        fact_gst2 = BidderFact(
            fact_id="F-G2",
            bid_id="B-01",
            field="gst_number",
            value="29SYNTH0000103F1Z",
            source_document="d2.pdf",
            page=2,
        )
        findings = engine.detect_contradictions_in_bid("B-01", [fact_gst1, fact_gst2])
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, "HIGH")

    def test_18_deterministic_repeated_resolution_gives_identical_output(self):
        for _ in range(50):
            res1 = resolve_field("annual_turnover")
            res2 = resolve_field("annual_turnover")
            self.assertEqual(res1.to_dict(), res2.to_dict())

            res_amb1 = resolve_field("experience")
            res_amb2 = resolve_field("experience")
            self.assertEqual(res_amb1.to_dict(), res_amb2.to_dict())

    # ==================== ADVERSARIAL COLLISION PREVENTION TESTS ====================

    def test_adversarial_01_annual_vs_average_turnover_do_not_contradict(self):
        """
        Adversarial case 1:
        Technical sheet states 'annual_turnover' = 12 Cr (for FY 2024-25).
        CA audit states 'average_annual_turnover' = 8 Cr (3-year average).
        A naive synonym engine would collapse both to 'turnover' and falsely flag a CONTRADICTION!
        Our ontology MUST maintain them as distinct canonical fields.
        """
        engine = CrossDocumentContradictionEngine()
        fact_single_year = BidderFact(
            fact_id="F-ADV-01",
            bid_id="BID-ADV-01",
            field="annual_turnover",
            value=12.0,
            source_document="fy2025_statement.pdf",
            page=1,
        )
        fact_3yr_avg = BidderFact(
            fact_id="F-ADV-02",
            bid_id="BID-ADV-01",
            field="average_annual_turnover",
            value=8.0,
            source_document="ca_3yr_certificate.pdf",
            page=1,
        )

        findings = engine.detect_contradictions_in_bid("BID-ADV-01", [fact_single_year, fact_3yr_avg])
        self.assertEqual(len(findings), 0, "Annual turnover and Average 3-year turnover MUST NOT falsely contradict!")

    def test_adversarial_02_bare_experience_rejected_as_ambiguous(self):
        """
        Adversarial case 2:
        Bidder declares 'experience = 3'.
        Does '3' mean 3 years of experience, or 3 similar completed projects?
        The system must refuse to guess and return AMBIGUOUS with canonical_field_id = None.
        """
        res = resolve_field("experience")
        self.assertEqual(res.resolution_status, ResolutionStatus.AMBIGUOUS.value)
        self.assertIsNone(res.canonical_field_id)

    def test_adversarial_03_duration_vs_count_do_not_collide(self):
        """
        Adversarial case 3:
        Doc A states 'experience_years = 5'.
        Doc B states 'similar_projects = 3'.
        Naive matcher might map both to 'experience'.
        Our ontology maps to PAST_EXPERIENCE_DURATION and SIMILAR_PROJECTS_COUNT.
        """
        engine = CrossDocumentContradictionEngine()
        fact_duration = BidderFact(
            fact_id="F-DUR",
            bid_id="BID-ADV-03",
            field="experience_years",
            value=5,
            source_document="company_profile.pdf",
            page=2,
        )
        fact_count = BidderFact(
            fact_id="F-CNT",
            bid_id="BID-ADV-03",
            field="similar_projects",
            value=3,
            source_document="project_list.pdf",
            page=1,
        )

        findings = engine.detect_contradictions_in_bid("BID-ADV-03", [fact_duration, fact_count])
        self.assertEqual(len(findings), 0, "Experience years and project count MUST NOT falsely collide!")


if __name__ == "__main__":
    unittest.main()
