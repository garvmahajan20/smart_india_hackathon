# -*- coding: utf-8 -*-
"""
SIH26100 Compliance Engine Coverage & Targeted Hardening Test Suite.
Validates:
1. Fail-closed UNKNOWN_REVIEW applicability resolution.
2. Low-confidence exemption claim containment.
3. Scoring deduction and review escalation on uncertain applicability.
4. Core SIH26100 compliance scenarios (Missing, Debarred, Contradiction, Clean Pass).
"""

import unittest
from typing import List

from backend.core.applicability import (
    ApplicabilityEvaluator,
    ApplicabilityResolution,
    ApplicabilityStatus,
)
from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    Severity,
    TenderRequirement,
    VerificationResult,
)
from backend.core.pending_requirements import PendingRequirementExtractor
from backend.core.recommendation_engine import (
    AIRecommendationEngine,
    RecommendationVerdict,
)
from backend.core.risk_engine import (
    DeterministicRiskEngine,
    RiskAssessment,
    RiskLevel,
)
from backend.core.scoring import (
    ComplianceScoringEngine,
    ComplianceScoreBreakdown,
)
from backend.verification.models import IntegrityFinding


class TestSIHComplianceCoverageAudit(unittest.TestCase):
    """Verifies targeted hardening and SIH26100 compliance scenarios."""

    def setUp(self):
        self.req_turnover = TenderRequirement(
            requirement_id="REQ-TO-01",
            tender_id="T1",
            category="TURNOVER",
            description="Annual turnover >= 5 Cr",
            operator=">=",
            expected_value=5.0,
            mandatory=True,
            applicability={"mse_exemption_allowed": True, "startup_exemption_allowed": True},
        )
        self.req_oem = TenderRequirement(
            requirement_id="REQ-OEM-01",
            tender_id="T1",
            category="OEM_AUTHORIZATION",
            description="Manufacturer Authorization Form (MAF)",
            operator="==",
            expected_value=True,
            mandatory=True,
        )
        self.req_epfo = TenderRequirement(
            requirement_id="REQ-EPFO-01",
            tender_id="T1",
            category="EPFO_COMPLIANCE",
            description="EPFO Registration & ECR Proof",
            operator="==",
            expected_value=True,
            mandatory=True,
        )
        self.req_role_specific = TenderRequirement(
            requirement_id="REQ-ROLE-01",
            tender_id="T1",
            category="TECHNICAL",
            description="OEM Quality Management System",
            operator="==",
            expected_value=True,
            mandatory=True,
            applicability={"applicable_bidder_roles": ["OEM", "MANUFACTURER"]},
        )

    # -------------------------------------------------------------------------
    # 1. UNKNOWN_REVIEW APPLICABILITY HARDENING
    # -------------------------------------------------------------------------
    def test_01_unknown_review_explicit_tender_specification(self):
        req = TenderRequirement(
            requirement_id="REQ-UNCERTAIN",
            tender_id="T1",
            category="SPECIAL",
            description="Special Site Clearance",
            operator="==",
            expected_value=True,
            mandatory=True,
            applicability={"status": "UNKNOWN_REVIEW", "reason": "Depends on buyer site location survey"},
        )
        res = ApplicabilityEvaluator.evaluate_applicability(req, facts=[])
        self.assertEqual(res.status, ApplicabilityStatus.UNKNOWN_REVIEW)
        self.assertEqual(res.applicability_rule, "TENDER_SPECIFICATION_UNCERTAIN")

    def test_02_unknown_review_unstated_bidder_role(self):
        # Requirement applies only to OEM/MANUFACTURER, but bidder role is unstated
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_role_specific, facts=[])
        self.assertEqual(res.status, ApplicabilityStatus.UNKNOWN_REVIEW)
        self.assertEqual(res.applicability_rule, "BIDDER_ROLE_UNVERIFIED")

    def test_03_unknown_review_low_confidence_oem_claim(self):
        fact_oem_low = BidderFact(
            fact_id="F-OEM-LOW",
            bid_id="B1",
            field="bidder_role",
            value="OEM",
            source_document="bid_letter.pdf",
            page=1,
            extraction_confidence="LOW",
            canonical_field="BIDDER_ROLE",
        )
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_oem, facts=[fact_oem_low])
        self.assertEqual(res.status, ApplicabilityStatus.UNKNOWN_REVIEW)
        self.assertEqual(res.applicability_rule, "OEM_STATUS_UNCERTAIN")

    def test_04_unknown_review_corrupted_employee_count_for_epfo(self):
        fact_emp_corrupt = BidderFact(
            fact_id="F-EMP-CORRUPT",
            bid_id="B1",
            field="employee_count",
            value="approx twenty-five",
            source_document="profile.pdf",
            page=1,
            canonical_field="EMPLOYEE_COUNT",
        )
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_epfo, facts=[fact_emp_corrupt])
        self.assertEqual(res.status, ApplicabilityStatus.UNKNOWN_REVIEW)
        self.assertEqual(res.applicability_rule, "STATUTORY_THRESHOLD_UNVERIFIED")

    def test_05_unknown_review_low_confidence_mse_exemption(self):
        fact_mse_low = BidderFact(
            fact_id="F-MSE-LOW",
            bid_id="B1",
            field="is_mse",
            value=True,
            source_document="cover.pdf",
            page=1,
            extraction_confidence="LOW",
            canonical_field="IS_MSE",
        )
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_turnover, facts=[fact_mse_low])
        self.assertEqual(res.status, ApplicabilityStatus.UNKNOWN_REVIEW)
        self.assertEqual(res.applicability_rule, "EXEMPTION_EVIDENCE_AMBIGUOUS")

    # -------------------------------------------------------------------------
    # 2. FAIL-CLOSED SCORING ON UNKNOWN_REVIEW
    # -------------------------------------------------------------------------
    def test_06_scoring_unknown_review_deduction_and_review_flag(self):
        # When applicability is UNKNOWN_REVIEW, even a nominal PASS status cannot earn full unreserved points
        fact_mse_low = BidderFact(
            fact_id="F-MSE-LOW",
            bid_id="B1",
            field="is_mse",
            value=True,
            source_document="cover.pdf",
            page=1,
            extraction_confidence="LOW",
            canonical_field="IS_MSE",
        )
        v_res = VerificationResult(
            verification_id="V1",
            requirement_id="REQ-TO-01",
            bid_id="B1",
            status=ComplianceStatus.PASS.value,
            severity=Severity.CRITICAL.value,
            expected=">= 5.0",
            actual="6.0",
            operator_used=">=",
            reason="Nominal pass",
            requires_human_review=False,
        )
        score = ComplianceScoringEngine.calculate_score(
            requirements=[self.req_turnover],
            compliance_results=[v_res],
            facts=[fact_mse_low],
        )
        self.assertEqual(score.under_review, 1)
        self.assertLess(score.final_score, 100.0)
        self.assertEqual(score.final_score, 50.0)
        self.assertTrue(any("UNKNOWN_REVIEW" in d.status for d in score.deductions))

    # -------------------------------------------------------------------------
    # 3. SIH-SPECIFIC COMPLIANCE SCENARIOS
    # -------------------------------------------------------------------------
    def test_07_scenario_mandatory_missing_capped_and_review(self):
        v_missing = VerificationResult(
            verification_id="V-TO",
            requirement_id="REQ-TO-01",
            bid_id="B1",
            status=ComplianceStatus.MISSING.value,
            severity=Severity.CRITICAL.value,
            expected=">= 5.0",
            actual="MISSING",
            operator_used=">=",
            reason="Turnover balance sheet missing",
            requires_human_review=True,
        )
        pending = PendingRequirementExtractor.extract_pending_requirements(
            requirements=[self.req_turnover],
            compliance_results=[v_missing],
            facts=[],
        )
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].deficiency_type, "MISSING_DOCUMENT")
        self.assertTrue(pending[0].requires_human_review)

    def test_08_scenario_debarment_fatal_disqualification(self):
        v = VerificationResult(
            verification_id="V1",
            requirement_id="REQ-TO-01",
            bid_id="B1",
            status=ComplianceStatus.PASS.value,
            severity=Severity.INFO.value,
            expected=">= 5.0",
            actual="10.0",
            operator_used=">=",
            reason="Passed",
            requires_human_review=False,
        )
        score = ComplianceScoringEngine.calculate_score(
            requirements=[self.req_turnover],
            compliance_results=[v],
            is_debarred=True,
        )
        self.assertEqual(score.final_score, 0.0)
        self.assertIn("DEBARMENT", score.cap_reason)

        risk = DeterministicRiskEngine.assess_risk(
            compliance_results=[v],
            is_debarred=True,
            debarment_reason="Blacklisted on CPPP",
        )
        self.assertEqual(risk.level, RiskLevel.CRITICAL)
        self.assertGreaterEqual(risk.risk_score, 0.90)

        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[v],
            pending_requirements=[],
            is_debarred=True,
        )
        self.assertEqual(rec.verdict, RecommendationVerdict.FAIL)
        self.assertIn("DISQUALIFICATION", rec.headline)

    def test_09_scenario_critical_contradiction_escalation(self):
        finding = IntegrityFinding(
            finding_id="INT-01",
            bid_id="B1",
            finding_type="GSTIN_CONTRADICTION",
            field="gstin",
            severity="CRITICAL",
            status="CONTRADICTION",
            description="GSTIN differs between invoice and certificate",
            value_a="07AAAAA0000A1Z5",
            value_b="27BBBBB1111B2Z6",
            evidence_a={},
            evidence_b={},
            requires_human_review=True,
        )
        risk = DeterministicRiskEngine.assess_risk(
            compliance_results=[],
            integrity_findings=[finding],
        )
        self.assertEqual(risk.level, RiskLevel.CRITICAL)

        score = ComplianceScoreBreakdown(
            total_requirements=1, total_applicable=1, passed=1, failed=0, missing=0,
            under_review=0, not_verified=0, not_applicable=0, raw_score=100.0,
            final_score=65.0, is_capped=True, cap_reason="CRITICAL_CONTRADICTION_CAP (65.0)",
        )
        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[],
            pending_requirements=[],
            integrity_findings=[finding],
        )
        self.assertNotEqual(rec.verdict, RecommendationVerdict.PASS)
        self.assertEqual(rec.verdict, RecommendationVerdict.REVIEW)

    def test_10_scenario_clean_bidder_unreserved_pass(self):
        v = VerificationResult(
            verification_id="V1",
            requirement_id="REQ-TO-01",
            bid_id="B1",
            status=ComplianceStatus.PASS.value,
            severity=Severity.INFO.value,
            expected=">= 5.0",
            actual="8.0",
            operator_used=">=",
            reason="Clean verified turnover",
            requires_human_review=False,
        )
        score = ComplianceScoringEngine.calculate_score(
            requirements=[self.req_turnover],
            compliance_results=[v],
        )
        self.assertEqual(score.final_score, 100.0)
        self.assertFalse(score.is_capped)

        risk = DeterministicRiskEngine.assess_risk(compliance_results=[v])
        self.assertEqual(risk.level, RiskLevel.LOW)

        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[v],
            pending_requirements=[],
        )
        self.assertEqual(rec.verdict, RecommendationVerdict.PASS)
        self.assertIn("QUALIFICATION", rec.headline)


if __name__ == "__main__":
    unittest.main()
