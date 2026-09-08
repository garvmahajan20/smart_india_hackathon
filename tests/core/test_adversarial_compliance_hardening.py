# -*- coding: utf-8 -*-
"""
Adversarial Compliance & Risk Hardening Test Suite (SIH26100).

Validates anti-tampering invariants across:
1. Score capping invariants (Mandatory Fail <= 40, Mandatory Missing <= 55, Critical Contradiction <= 65, Debarment = 0)
2. AI recommendation decision boundary enforcement (No PASS on failure, missing, or high risk)
3. Cross-document contradiction detection & risk escalation (always CRITICAL)
4. Applicability exemption abuse prevention (no exemption without verified proof)
5. EPFO statutory threshold exemption abuse with large workforce
6. Debarment zero-score & disqualification invariants
7. Procurement Officer authority notice & decision-support-only invariants
"""

import unittest
from typing import List

from backend.core.models import (
    BidderFact,
    ComplianceStatus,
    Severity,
    TenderRequirement,
    VerificationResult,
)
from backend.core.applicability import (
    ApplicabilityEvaluator,
    ApplicabilityStatus,
)
from backend.core.pending_requirements import (
    PendingRequirement,
    PendingRequirementExtractor,
)
from backend.core.scoring import (
    ComplianceScoringEngine,
    ComplianceScoreBreakdown,
)
from backend.core.risk_engine import (
    DeterministicRiskEngine,
    RiskAssessment,
    RiskFactor,
    RiskLevel,
)
from backend.core.recommendation_engine import (
    AIRecommendationEngine,
    RecommendationVerdict,
)
from backend.verification.models import IntegrityFinding


class TestAdversarialComplianceHardening(unittest.TestCase):
    """Adversarial stress and tamper tests for the hardened compliance pipeline."""

    def setUp(self):
        self.req_turnover = TenderRequirement(
            requirement_id="REQ-TO-01",
            tender_id="T1",
            category="TURNOVER",
            description="Annual turnover >= 10 Cr",
            operator=">=",
            expected_value=10.0,
            mandatory=True,
        )
        self.req_epfo = TenderRequirement(
            requirement_id="REQ-EPFO-01",
            tender_id="T1",
            category="EPFO",
            description="EPFO Statutory Registration / Compliance",
            operator="==",
            expected_value=True,
            mandatory=True,
        )

    # -------------------------------------------------------------------------
    # ATTACK 1: Hiding mandatory failure behind voluminous passing optional items
    # -------------------------------------------------------------------------
    def test_attack_01_mandatory_failure_hidden_behind_high_passing_score(self):
        """Attacker passes 50 optional requirements hoping to mask a mandatory failure."""
        v_fail = VerificationResult(
            verification_id="V-FAIL-01",
            requirement_id="REQ-TO-01",
            bid_id="B-ATK-01",
            status=ComplianceStatus.FAIL.value,
            severity=Severity.CRITICAL.value,
            expected=">= 10.0",
            actual="2.1",
            operator_used=">=",
            reason="Turnover critically deficient",
            requires_human_review=True,
        )

        reqs: List[TenderRequirement] = [self.req_turnover]
        v_results: List[VerificationResult] = [v_fail]

        # 50 passing optional items
        for i in range(50):
            r = TenderRequirement(
                requirement_id=f"OPT-{i}",
                tender_id="T1",
                category="OPTIONAL",
                description=f"Optional feature {i}",
                operator="==",
                expected_value=True,
                mandatory=False,
            )
            v = VerificationResult(
                verification_id=f"V-OPT-{i}",
                requirement_id=f"OPT-{i}",
                bid_id="B-ATK-01",
                status=ComplianceStatus.PASS.value,
                severity=Severity.MINOR.value,
                expected="==",
                actual="True",
                operator_used="==",
                reason="Passed",
                requires_human_review=False,
            )
            reqs.append(r)
            v_results.append(v)

        score = ComplianceScoringEngine.calculate_score(
            requirements=reqs,
            compliance_results=v_results,
        )

        # Invariant: Score MUST be capped at <= 40.0 despite 50 passing clauses
        self.assertTrue(score.is_capped, "Failure to cap score on mandatory failure")
        self.assertLessEqual(score.final_score, 40.0)
        self.assertIn("MANDATORY_FAILURE_CAP", score.cap_reason)
        # Raw score before cap would have been >80%, demonstrating cap actively engaged
        self.assertGreater(score.raw_score, 80.0)

    # -------------------------------------------------------------------------
    # ATTACK 2: Forcing AI recommendation to PASS when mandatory clause failed
    # -------------------------------------------------------------------------
    def test_attack_02_force_llm_pass_recommendation_when_mandatory_fails(self):
        """AI Recommendation Engine must NEVER output PASS if there is any failed mandatory requirement."""
        score = ComplianceScoreBreakdown(
            total_requirements=10,
            total_applicable=10,
            passed=9,
            failed=1,
            missing=0,
            under_review=0,
            not_verified=0,
            not_applicable=0,
            raw_score=90.0,
            final_score=40.0,
            is_capped=True,
            cap_reason="MANDATORY_FAILURE_CAP (40.0)",
        )
        risk = RiskAssessment(level=RiskLevel.MEDIUM, risk_score=0.45)
        v_fail = VerificationResult(
            verification_id="V-FAIL",
            requirement_id="REQ-TO-01",
            bid_id="B-ATK-02",
            status=ComplianceStatus.FAIL.value,
            severity=Severity.CRITICAL.value,
            expected=">= 10.0",
            actual="2.0",
            operator_used=">=",
            reason="Turnover below threshold",
            requires_human_review=True,
        )

        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[v_fail],
            pending_requirements=[],
            is_debarred=False,
        )

        self.assertEqual(rec.verdict, RecommendationVerdict.FAIL)
        self.assertIn("DISQUALIFICATION", rec.headline.upper())
        self.assertTrue(any("mandatory requirement" in r.lower() for r in rec.key_reasons))

    # -------------------------------------------------------------------------
    # ATTACK 3: Forcing AI recommendation to PASS when mandatory document is missing
    # -------------------------------------------------------------------------
    def test_attack_03_force_llm_pass_recommendation_when_mandatory_missing(self):
        """AI Recommendation Engine must NEVER output PASS if mandatory documents are missing."""
        score = ComplianceScoreBreakdown(
            total_requirements=5,
            total_applicable=5,
            passed=4,
            failed=0,
            missing=1,
            under_review=0,
            not_verified=0,
            not_applicable=0,
            raw_score=80.0,
            final_score=55.0,
            is_capped=True,
            cap_reason="MANDATORY_MISSING_CAP (55.0)",
        )
        risk = RiskAssessment(level=RiskLevel.MEDIUM, risk_score=0.40)
        v_missing = VerificationResult(
            verification_id="V-MISSING",
            requirement_id="REQ-TO-01",
            bid_id="B-ATK-03",
            status=ComplianceStatus.MISSING.value,
            severity=Severity.CRITICAL.value,
            expected=">= 10.0",
            actual="MISSING",
            operator_used=">=",
            reason="Audited balance sheet missing",
            requires_human_review=True,
        )
        pending_list = PendingRequirementExtractor.extract_pending_requirements(
            requirements=[self.req_turnover],
            compliance_results=[v_missing],
            facts=[],
        )

        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[v_missing],
            pending_requirements=pending_list,
            is_debarred=False,
        )

        self.assertNotEqual(rec.verdict, RecommendationVerdict.PASS)
        self.assertEqual(rec.verdict, RecommendationVerdict.REVIEW)
        self.assertTrue(any("missing" in r.lower() for r in rec.key_reasons))

    # -------------------------------------------------------------------------
    # ATTACK 4: Forcing AI recommendation to PASS when Risk Level is CRITICAL
    # -------------------------------------------------------------------------
    def test_attack_04_force_llm_pass_recommendation_when_risk_is_critical(self):
        """Even with 100% passing compliance score, CRITICAL risk must forbid PASS."""
        score = ComplianceScoreBreakdown(
            total_requirements=5,
            total_applicable=5,
            passed=5,
            failed=0,
            missing=0,
            under_review=0,
            not_verified=0,
            not_applicable=0,
            raw_score=100.0,
            final_score=100.0,
            is_capped=False,
        )
        risk = RiskAssessment(
            level=RiskLevel.CRITICAL,
            risk_score=0.95,
            risk_factors=[
                RiskFactor(
                    code="IDENTITY_TAMPER",
                    severity="CRITICAL",
                    category="CONTRADICTION",
                    description="Identity contradiction: PAN name differs from GSTIN legal name",
                    trigger_source="CROSS_DOCUMENT_CONTRADICTION_ENGINE",
                )
            ],
        )

        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[],
            pending_requirements=[],
            is_debarred=False,
        )

        self.assertNotEqual(rec.verdict, RecommendationVerdict.PASS)
        self.assertEqual(rec.verdict, RecommendationVerdict.REVIEW)

    # -------------------------------------------------------------------------
    # ATTACK 5: Cross-document identity contradiction ignored by risk engine
    # -------------------------------------------------------------------------
    def test_attack_05_critical_cross_document_contradiction_escalation(self):
        """Cross-document contradictions in core identifiers (PAN, GSTIN) must escalate risk to CRITICAL."""
        finding = IntegrityFinding(
            finding_id="INT-ATK-01",
            bid_id="B-ATK-05",
            finding_type="PAN_MISMATCH",
            field="pan_number",
            severity="CRITICAL",
            status="CONTRADICTION",
            description="PAN in bid dossier does not match PAN on Udyam registration",
            value_a="ABCDE1234F",
            value_b="XYZPQ9876M",
            evidence_a={"source": "bid_doc.pdf"},
            evidence_b={"source": "udyam_cert.pdf"},
            requires_human_review=True,
        )

        risk = DeterministicRiskEngine.assess_risk(
            compliance_results=[],
            integrity_findings=[finding],
        )

        self.assertEqual(risk.level, RiskLevel.CRITICAL)
        self.assertGreaterEqual(risk.risk_score, 0.85)
        self.assertTrue(any("PAN_MISMATCH" in rf.code or "CONTRADICTION" in rf.category for rf in risk.risk_factors))

    # -------------------------------------------------------------------------
    # ATTACK 6: NOT_APPLICABLE abuse to bypass mandatory requirement without proof
    # -------------------------------------------------------------------------
    def test_attack_06_not_applicable_abuse_without_proof(self):
        """Bidder claims MSE turnover exemption but provides no valid MSE fact."""
        # No facts provided
        res_no_facts = ApplicabilityEvaluator.evaluate_applicability(self.req_turnover, facts=[])
        self.assertEqual(res_no_facts.status, ApplicabilityStatus.APPLICABLE)

        # Irrelevant fact provided
        fact_irrelevant = BidderFact(
            fact_id="F-IRR",
            bid_id="B1",
            field="iso_certification",
            value="ISO 9001:2015",
            source_document="iso.pdf",
            page=1,
            canonical_field="ISO_CERT",
        )
        res_irrelevant = ApplicabilityEvaluator.evaluate_applicability(
            self.req_turnover, facts=[fact_irrelevant]
        )
        self.assertEqual(res_irrelevant.status, ApplicabilityStatus.APPLICABLE)

        # Unverified / False MSE claim
        fact_mse_false = BidderFact(
            fact_id="F-MSE-FALSE",
            bid_id="B1",
            field="is_mse",
            value=False,
            source_document="declaration.pdf",
            page=1,
            canonical_field="IS_MSE",
        )
        res_false_mse = ApplicabilityEvaluator.evaluate_applicability(
            self.req_turnover, facts=[fact_mse_false]
        )
        self.assertEqual(res_false_mse.status, ApplicabilityStatus.APPLICABLE)

    # -------------------------------------------------------------------------
    # ATTACK 7: EPFO statutory threshold exemption abuse with large workforce
    # -------------------------------------------------------------------------
    def test_attack_07_epfo_exemption_abuse_with_large_workforce(self):
        """Bidder claims small-establishment exemption for EPFO but has >= 20 employees."""
        fact_large_team = BidderFact(
            fact_id="F-EMP-50",
            bid_id="B1",
            field="employee_count",
            value=25,
            source_document="payroll.pdf",
            page=1,
            canonical_field="EMPLOYEE_COUNT",
        )
        res = ApplicabilityEvaluator.evaluate_applicability(self.req_epfo, facts=[fact_large_team])
        self.assertEqual(res.status, ApplicabilityStatus.APPLICABLE)

    # -------------------------------------------------------------------------
    # ATTACK 8: Score capping invariant on critical contradiction
    # -------------------------------------------------------------------------
    def test_attack_08_critical_contradiction_score_cap_at_65(self):
        """A critical contradiction must cap overall compliance score at <= 65.0."""
        # 10 passing clauses
        reqs = []
        v_results = []
        for i in range(10):
            r = TenderRequirement(
                requirement_id=f"REQ-{i}", tender_id="T1", category="GENERAL",
                description=f"Requirement {i}", operator="==", expected_value=True,
                mandatory=False,
            )
            v = VerificationResult(
                verification_id=f"V-{i}", requirement_id=f"REQ-{i}", bid_id="B1",
                status=ComplianceStatus.PASS.value, severity=Severity.INFO.value,
                expected="==", actual="True", operator_used="==", reason="Passed",
                requires_human_review=False,
            )
            reqs.append(r)
            v_results.append(v)

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

        score = ComplianceScoringEngine.calculate_score(
            requirements=reqs,
            compliance_results=v_results,
            integrity_findings=[finding],
        )

        self.assertTrue(score.is_capped)
        self.assertLessEqual(score.final_score, 65.0)
        self.assertIn("CRITICAL_CONTRADICTION_CAP", score.cap_reason)

    # -------------------------------------------------------------------------
    # ATTACK 9: Debarred bidder attempting to achieve non-zero score
    # -------------------------------------------------------------------------
    def test_attack_09_debarred_bidder_zero_score_invariant(self):
        """Debarred bidder must receive score 0.0, CRITICAL risk, and FAIL recommendation."""
        req = TenderRequirement(
            requirement_id="REQ-1", tender_id="T1", category="GENERAL",
            description="General requirement", operator="==", expected_value=True,
            mandatory=True,
        )
        v = VerificationResult(
            verification_id="V-1", requirement_id="REQ-1", bid_id="B1",
            status=ComplianceStatus.PASS.value, severity=Severity.INFO.value,
            expected="==", actual="True", operator_used="==", reason="Passed",
            requires_human_review=False,
        )

        # 1. Scoring
        score = ComplianceScoringEngine.calculate_score(
            requirements=[req],
            compliance_results=[v],
            is_debarred=True,
        )
        self.assertEqual(score.final_score, 0.0)
        self.assertTrue(score.is_capped)
        self.assertIn("DEBARMENT", score.cap_reason)

        # 2. Risk
        risk = DeterministicRiskEngine.assess_risk(
            compliance_results=[v],
            is_debarred=True,
            debarment_reason="Debarred on CPPP for fraudulent documents",
        )
        self.assertEqual(risk.level, RiskLevel.CRITICAL)
        self.assertGreaterEqual(risk.risk_score, 0.90)

        # 3. Recommendation
        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[v],
            pending_requirements=[],
            is_debarred=True,
        )
        self.assertEqual(rec.verdict, RecommendationVerdict.FAIL)
        self.assertIn("DISQUALIFICATION", rec.headline.upper())

    # -------------------------------------------------------------------------
    # ATTACK 10: Legal authority boundary assertion
    # -------------------------------------------------------------------------
    def test_attack_10_procurement_officer_authority_disclaimer_invariant(self):
        """The AI recommendation engine MUST explicitly assert Procurement Officer sole authority."""
        score = ComplianceScoreBreakdown(
            total_requirements=1, total_applicable=1, passed=1, failed=0, missing=0,
            under_review=0, not_verified=0, not_applicable=0, raw_score=100.0,
            final_score=100.0, is_capped=False,
        )
        risk = RiskAssessment(level=RiskLevel.LOW, risk_score=0.1)
        rec = AIRecommendationEngine.generate_recommendation(
            compliance_score=score,
            risk_assessment=risk,
            compliance_results=[],
            pending_requirements=[],
        )
        self.assertIn("Procurement Officer", rec.authority_notice)
        self.assertIn("DECISION_SUPPORT_ONLY", rec.authority_notice)


if __name__ == "__main__":
    unittest.main()
