# -*- coding: utf-8 -*-
"""
Dedicated Test Suite for Compliance Hardening, Scoring, Risk, and AI Recommendation.
Phases 2-9, 14, 15:
- Compliance status and applicability resolution
- Pending requirements extraction
- Deterministic compliance score and capping invariants
- Deterministic risk assessment and escalation triggers
- AI Recommendation Engine and procurement officer authority boundaries
- Consistency invariants between score, risk, and recommendation
- End-to-end aggregator and dossier enrichment
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath("."))

from backend.core.applicability import (
    ApplicabilityEvaluator,
    ApplicabilityResolution,
    ApplicabilityStatus,
)
from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    OperatorType,
    Severity,
    TenderRequirement,
    VerificationResult,
)
from backend.core.pending_requirements import (
    PendingRequirement,
    PendingRequirementExtractor,
)
from backend.core.recommendation_engine import (
    AIRecommendation,
    AIRecommendationEngine,
    RecommendationVerdict,
)
from backend.core.risk_engine import (
    DeterministicRiskEngine,
    RiskAssessment,
    RiskFactor,
    RiskLevel,
)
from backend.core.scoring import (
    ComplianceScoreBreakdown,
    ComplianceScoringEngine,
    ScoreDeduction,
)
from backend.orchestration.aggregator import VerificationAggregator
from backend.verification.models import AdapterResponse, IntegrityFinding, VerificationStatus


class TestComplianceCompletion(unittest.TestCase):
    def setUp(self):
        self.req_turnover = TenderRequirement(
            requirement_id="REQ-TO-01",
            tender_id="TENDER-001",
            category="FINANCIAL_CAPACITY",
            description="Annual turnover >= INR 5 Crore",
            operator=OperatorType.GTE.value,
            expected_value=5.0,
            field="turnover",
            mandatory=True,
            applicability={"mse_exemption_allowed": True, "startup_exemption_allowed": True},
        )
        self.req_oem = TenderRequirement(
            requirement_id="REQ-OEM-01",
            tender_id="TENDER-001",
            category="OEM_AUTHORIZATION",
            description="Valid OEM Authorization certificate required",
            operator=OperatorType.EXISTS.value,
            expected_value=True,
            field="oem_authorization",
            mandatory=True,
            applicability={"applicable_bidder_roles": ["RESELLER", "TRADER"]},
        )
        self.req_epfo = TenderRequirement(
            requirement_id="REQ-EPFO-01",
            tender_id="TENDER-001",
            category="EPFO_COMPLIANCE",
            description="Valid EPFO registration and return filings",
            operator=OperatorType.EXISTS.value,
            expected_value=True,
            field="epfo_registration",
            mandatory=True,
            applicability={"mandate_for_all_sizes": False},
        )
        self.req_warranty = TenderRequirement(
            requirement_id="REQ-WAR-01",
            tender_id="TENDER-001",
            category="TECHNICAL_SPECIFICATIONS",
            description="Comprehensive on-site warranty >= 36 months",
            operator=OperatorType.GTE.value,
            expected_value=36,
            field="warranty_months",
            mandatory=False,
        )

    # -------------------------------------------------------------------------
    # 1. APPLICABILITY TESTS (PHASE 3)
    # -------------------------------------------------------------------------
    def test_01_applicability_standard_applicable(self):
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_turnover, facts=[])
        self.assertEqual(res.status, ApplicabilityStatus.APPLICABLE)
        self.assertEqual(res.applicability_rule, "STANDARD_APPLICABLE")

    def test_02_applicability_mse_exemption(self):
        fact_mse = BidderFact(
            fact_id="F-MSE",
            bid_id="B-01",
            field="is_mse",
            value=True,
            source_document="udyam.pdf",
            page=1,
            canonical_field="IS_MSE",
        )
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_turnover, facts=[fact_mse])
        self.assertEqual(res.status, ApplicabilityStatus.NOT_APPLICABLE)
        self.assertEqual(res.applicability_rule, "MSE_STATUTORY_EXEMPTION")

    def test_03_applicability_oem_self_manufacturer(self):
        fact_role = BidderFact(
            fact_id="F-ROLE",
            bid_id="B-01",
            field="bidder_role",
            value="OEM",
            source_document="profile.pdf",
            page=1,
            canonical_field="BIDDER_ROLE",
        )
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_oem, facts=[fact_role])
        self.assertEqual(res.status, ApplicabilityStatus.NOT_APPLICABLE)
        self.assertEqual(res.applicability_rule, "OEM_SELF_MANUFACTURER")

    def test_04_applicability_epfo_small_establishment(self):
        fact_emp = BidderFact(
            fact_id="F-EMP",
            bid_id="B-01",
            field="employee_count",
            value=8,
            source_document="declaration.pdf",
            page=1,
            canonical_field="EMPLOYEE_COUNT",
        )
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_epfo, facts=[fact_emp])
        self.assertEqual(res.status, ApplicabilityStatus.NOT_APPLICABLE)
        self.assertEqual(res.applicability_rule, "STATUTORY_THRESHOLD_EPFO")

    # -------------------------------------------------------------------------
    # 2. PENDING REQUIREMENTS TESTS (PHASE 4)
    # -------------------------------------------------------------------------
    def test_05_pending_requirements_extraction(self):
        v_res_missing = VerificationResult(
            verification_id="V-TO-01",
            requirement_id="REQ-TO-01",
            bid_id="B-01",
            status=ComplianceStatus.MISSING.value,
            severity=Severity.CRITICAL.value,
            expected=">= 5.0",
            actual="MISSING",
            operator_used=">=",
            reason="Turnover document missing",
            requires_human_review=True,
        )
        pending = PendingRequirementExtractor.extract_pending_requirements(
            requirements=[self.req_turnover],
            compliance_results=[v_res_missing],
            facts=[],
        )
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].requirement_id, "REQ-TO-01")
        self.assertEqual(pending[0].compliance_result, "MISSING")
        self.assertEqual(pending[0].deficiency_type, "MISSING_DOCUMENT")
        self.assertTrue(pending[0].mandatory)

    # -------------------------------------------------------------------------
    # 3. SCORING ENGINE TESTS & CAPPING INVARIANTS (PHASE 6)
    # -------------------------------------------------------------------------
    def test_06_scoring_perfect_compliance(self):
        v1 = VerificationResult(
            verification_id="V1", requirement_id="REQ-TO-01", bid_id="B1",
            status=ComplianceStatus.PASS.value, severity=Severity.CRITICAL.value,
            expected=">= 5.0", actual="12.0", operator_used=">=", reason="Passed",
            requires_human_review=False
        )
        v2 = VerificationResult(
            verification_id="V2", requirement_id="REQ-WAR-01", bid_id="B1",
            status=ComplianceStatus.PASS.value, severity=Severity.MINOR.value,
            expected=">= 36", actual="48", operator_used=">=", reason="Passed",
            requires_human_review=False
        )
        score = ComplianceScoringEngine.calculate_score(
            requirements=[self.req_turnover, self.req_warranty],
            compliance_results=[v1, v2],
        )
        self.assertEqual(score.final_score, 100.0)
        self.assertFalse(score.is_capped)
        self.assertEqual(score.passed, 2)
        self.assertEqual(score.failed, 0)

    def test_07_scoring_critical_mandatory_failure_capped_at_40(self):
        # Even if 99 minor clauses pass, 1 mandatory FAIL must be capped at 40!
        v_fail = VerificationResult(
            verification_id="V1", requirement_id="REQ-TO-01", bid_id="B1",
            status=ComplianceStatus.FAIL.value, severity=Severity.CRITICAL.value,
            expected=">= 5.0", actual="1.2", operator_used=">=", reason="Turnover below requirement",
            requires_human_review=True
        )
        # Create 10 optional passing clauses
        reqs = [self.req_turnover]
        v_results = [v_fail]
        for i in range(10):
            r_opt = TenderRequirement(
                requirement_id=f"OPT-{i}", tender_id="T1", category="OPTIONAL",
                description=f"Optional feature {i}", operator="==", expected_value=True,
                mandatory=False
            )
            v_opt = VerificationResult(
                verification_id=f"V-OPT-{i}", requirement_id=f"OPT-{i}", bid_id="B1",
                status=ComplianceStatus.PASS.value, severity=Severity.MINOR.value,
                expected="==", actual="True", operator_used="==", reason="Passed",
                requires_human_review=False
            )
            reqs.append(r_opt)
            v_results.append(v_opt)

        score = ComplianceScoringEngine.calculate_score(requirements=reqs, compliance_results=v_results)
        self.assertTrue(score.is_capped)
        self.assertLessEqual(score.final_score, 40.0)
        self.assertIn("MANDATORY_FAILURE_CAP", score.cap_reason)

    def test_08_scoring_mandatory_missing_capped_at_55(self):
        v_missing = VerificationResult(
            verification_id="V1", requirement_id="REQ-TO-01", bid_id="B1",
            status=ComplianceStatus.MISSING.value, severity=Severity.CRITICAL.value,
            expected=">= 5.0", actual="MISSING", operator_used=">=", reason="Missing",
            requires_human_review=True
        )
        # Add 10 optional passing clauses so raw score without cap would be ~85%
        reqs = [self.req_turnover]
        v_results = [v_missing]
        for i in range(10):
            r_opt = TenderRequirement(
                requirement_id=f"OPT-{i}", tender_id="T1", category="OPTIONAL",
                description=f"Optional feature {i}", operator="==", expected_value=True,
                mandatory=False
            )
            v_opt = VerificationResult(
                verification_id=f"V-OPT-{i}", requirement_id=f"OPT-{i}", bid_id="B1",
                status=ComplianceStatus.PASS.value, severity=Severity.MINOR.value,
                expected="==", actual="True", operator_used="==", reason="Passed",
                requires_human_review=False
            )
            reqs.append(r_opt)
            v_results.append(v_opt)

        score = ComplianceScoringEngine.calculate_score(
            requirements=reqs,
            compliance_results=v_results,
        )
        self.assertTrue(score.is_capped)
        self.assertLessEqual(score.final_score, 55.0)
        self.assertIn("MANDATORY_MISSING_CAP", score.cap_reason)

    def test_09_scoring_debarment_score_zero(self):
        score = ComplianceScoringEngine.calculate_score(
            requirements=[self.req_turnover],
            compliance_results=[],
            is_debarred=True,
        )
        self.assertEqual(score.final_score, 0.0)
        self.assertTrue(score.is_capped)
        self.assertIn("DEBARMENT", score.cap_reason)

    # -------------------------------------------------------------------------
    # 4. RISK ASSESSMENT TESTS (PHASE 7)
    # -------------------------------------------------------------------------
    def test_10_risk_clean_bidder_low_risk(self):
        v = VerificationResult(
            verification_id="V1", requirement_id="REQ-TO-01", bid_id="B1",
            status=ComplianceStatus.PASS.value, severity=Severity.INFO.value,
            expected=">= 5.0", actual="10.0", operator_used=">=", reason="OK",
            requires_human_review=False
        )
        risk = DeterministicRiskEngine.assess_risk(compliance_results=[v])
        self.assertEqual(risk.level, RiskLevel.LOW)
        self.assertLess(risk.risk_score, 0.30)

    def test_11_risk_debarment_critical_risk(self):
        risk = DeterministicRiskEngine.assess_risk(
            compliance_results=[],
            is_debarred=True,
            debarment_reason="Debarred by Ministry of Commerce for bid rigging",
        )
        self.assertEqual(risk.level, RiskLevel.CRITICAL)
        self.assertGreaterEqual(risk.risk_score, 0.90)

    def test_12_risk_cross_document_identity_contradiction_critical_risk(self):
        finding = IntegrityFinding(
            finding_id="INT-01",
            bid_id="B1",
            finding_type="GSTIN_CONTRADICTION",
            field="gstin",
            severity="HIGH",
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

    # -------------------------------------------------------------------------
    # 5. AI RECOMMENDATION ENGINE & AUTHORITY BOUNDARIES (PHASES 8 & 9)
    # -------------------------------------------------------------------------
    def test_13_recommendation_clean_pass(self):
        score = ComplianceScoreBreakdown(
            total_requirements=2, total_applicable=2, passed=2, failed=0, missing=0,
            under_review=0, not_verified=0, not_applicable=0, raw_score=100.0,
            final_score=100.0, is_capped=False
        )
        risk = RiskAssessment(level=RiskLevel.LOW, risk_score=0.10)
        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[],
            pending_requirements=[],
        )
        self.assertEqual(rec.verdict, RecommendationVerdict.PASS)
        self.assertIn("DECISION_SUPPORT_ONLY", rec.authority_notice)

    def test_14_recommendation_mandatory_fail_forces_fail_verdict(self):
        score = ComplianceScoreBreakdown(
            total_requirements=10, total_applicable=10, passed=9, failed=1, missing=0,
            under_review=0, not_verified=0, not_applicable=0, raw_score=90.0,
            final_score=40.0, is_capped=True, cap_reason="MANDATORY_FAILURE_CAP"
        )
        risk = RiskAssessment(level=RiskLevel.HIGH, risk_score=0.75)
        v_fail = VerificationResult(
            verification_id="V1", requirement_id="REQ-MAND", bid_id="B1",
            status=ComplianceStatus.FAIL.value, severity=Severity.CRITICAL.value,
            expected="True", actual="False", operator_used="==", reason="Failed critical check",
            requires_human_review=True
        )
        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[v_fail],
            pending_requirements=[],
        )
        # Even though 9/10 passed, recommendation MUST be FAIL!
        self.assertEqual(rec.verdict, RecommendationVerdict.FAIL)
        self.assertIn("DISQUALIFICATION RECOMMENDED", rec.headline)

    def test_15_recommendation_missing_mandatory_forces_review(self):
        score = ComplianceScoreBreakdown(
            total_requirements=5, total_applicable=5, passed=4, failed=0, missing=1,
            under_review=0, not_verified=0, not_applicable=0, raw_score=80.0,
            final_score=55.0, is_capped=True
        )
        risk = RiskAssessment(level=RiskLevel.HIGH, risk_score=0.68)
        p_missing = PendingRequirement(
            requirement_id="REQ-TO-01", description="Turnover", category="FINANCIAL",
            mandatory=True, applicability="APPLICABLE", evidence_expected=">= 5 Cr",
            evidence_found=None, government_verification_expected=None,
            government_verification_result=None, compliance_result="MISSING",
            reason="Missing turnover", requires_human_review=True,
            deficiency_type="MISSING_DOCUMENT", suggested_bidder_action="Submit document"
        )
        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[],
            pending_requirements=[p_missing],
        )
        self.assertEqual(rec.verdict, RecommendationVerdict.REVIEW)

    # -------------------------------------------------------------------------
    # 6. END-TO-END AGGREGATOR ENRICHMENT (PHASE 10 & 14)
    # -------------------------------------------------------------------------
    def test_16_aggregator_enrichment_backward_compatibility(self):
        v = VerificationResult(
            verification_id="V1", requirement_id="REQ-TO-01", bid_id="B1",
            status=ComplianceStatus.PASS.value, severity=Severity.CRITICAL.value,
            expected=">= 5.0", actual="10.0", operator_used=">=", reason="OK",
            requires_human_review=False
        )
        agg = VerificationAggregator().aggregate(
            tender_id="T-100",
            bid_id="B-200",
            compliance_results=[v],
            integrity_findings=[],
            government_responses=[],
        )
        self.assertIsNotNone(agg.compliance_score)
        self.assertIn(agg.risk_level, ["LOW", "MEDIUM", "HIGH", "CRITICAL"])
        self.assertIn("verdict", agg.recommendation)
        self.assertIsInstance(agg.pending_requirements, list)
        self.assertIn("compliance_score", agg.to_dict())
        self.assertIn("risk_level", agg.to_dict())
        self.assertIn("recommendation", agg.to_dict())


if __name__ == "__main__":
    unittest.main()
