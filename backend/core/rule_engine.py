from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional

from .models import (
    BidderFact,
    ComplianceStatus,
    EvidencePointer,
    OperatorType,
    Severity,
    TenderRequirement,
    VerificationResult,
)
from .normalization import (
    normalize_boolean,
    normalize_categorical,
    normalize_currency,
    normalize_date,
    normalize_duration,
    normalize_numeric,
)
from .operators import evaluate_operator
from .precedence import resolve_precedence

class DeterministicRuleEngine:
    """
    Pure Python Deterministic Compliance Rule Engine.
    Zero external dependencies, zero LLM calls, zero network operations.
    Fully reproducible and audit-traceable.
    """

    def __init__(self, default_evaluation_date: Optional[date] = None):
        self.default_evaluation_date = default_evaluation_date

    def verify_bid(
        self,
        requirements: List[TenderRequirement],
        facts: List[BidderFact],
        tender_metadata: Optional[Dict[str, Any]] = None,
        evaluation_date: Optional[date] = None,
    ) -> List[VerificationResult]:
        """
        Executes full deterministic verification pipeline:
        1. Precedence resolution (GTC < STC < ATC)
        2. Indexing facts & profiling exemptions (MSE / Startup)
        3. Conditional exemption evaluation
        4. Operator execution
        5. Evidence propagation and severity assignment
        """
        tender_meta = tender_metadata or {}
        ref_date = (
            evaluation_date
            or normalize_date(tender_meta.get("closing_date"))
            or normalize_date(tender_meta.get("submission_date"))
            or self.default_evaluation_date
            or date(2026, 9, 1) # Standard deterministic fallback date
        )

        # Step 1: Resolve Precedence (GTC < STC < ATC)
        precedence_res = resolve_precedence(requirements)

        # Step 2: Index facts by field and canonical identity
        facts_by_field: Dict[str, List[BidderFact]] = defaultdict(list)
        facts_by_canonical: Dict[str, List[BidderFact]] = defaultdict(list)
        bid_id = "UNKNOWN_BID"
        for f in facts:
            if f.bid_id:
                bid_id = f.bid_id
            facts_by_field[f.field.lower()].append(f)
            if f.canonical_field:
                facts_by_canonical[f.canonical_field.lower()].append(f)

        # Index bidder profile for statutory exemptions
        is_mse = self._check_exemption_status(facts_by_field, ["is_mse", "mse_registered", "udyam_registration"])
        is_startup = self._check_exemption_status(facts_by_field, ["is_startup", "startup_recognized", "dpiit_recognized"])

        results: List[VerificationResult] = []

        # Step 3: Evaluate each requirement
        for req in precedence_res.all_requirements:
            verif_id = f"VERIF-{bid_id}-{req.requirement_id}"

            # 3A. Check if superseded by precedence
            if not req.is_effective:
                results.append(
                    VerificationResult(
                        verification_id=verif_id,
                        requirement_id=req.requirement_id,
                        bid_id=bid_id,
                        status=ComplianceStatus.N_A.value,
                        severity=Severity.INFO.value,
                        expected=str(req.expected_value),
                        actual="N/A (Superseded)",
                        operator_used=req.operator,
                        reason=req.precedence_notes or "Requirement superseded by higher-priority clause.",
                        requires_human_review=False,
                        precedence_chain={
                            "status": "SUPERSEDED",
                            "superseded_by": req.superseded_by,
                            "source_type": req.source_type,
                            "source_priority": req.source_priority,
                        }
                    )
                )
                continue

            # 3B. Check Conditional Exemptions
            exemption_result = self._evaluate_conditional_exemption(req, is_mse, is_startup, bid_id, verif_id)
            if exemption_result is not None:
                results.append(exemption_result)
                continue

            # 3C. Find matching facts
            field_key = (req.field or "").lower()
            matching_facts = facts_by_field.get(field_key, [])

            # Fallback to canonical matching if raw field didn't match directly
            if not matching_facts and req.field:
                req_canonical = req.canonical_field
                if not req_canonical:
                    from .ontology import resolve_field
                    cf_res = resolve_field(req.field)
                    if cf_res.resolution_status == "RESOLVED":
                        req_canonical = cf_res.canonical_field_id
                if req_canonical:
                    matching_facts = facts_by_canonical.get(req_canonical.lower(), [])

            if not matching_facts:
                # No fact submitted
                if req.operator == OperatorType.EXISTS.value:
                    status = ComplianceStatus.MISSING.value
                    reason = f"Mandatory requirement '{req.description}' not satisfied: document/evidence is missing."
                else:
                    status = ComplianceStatus.MISSING.value
                    reason = f"No bidder evidence submitted for '{req.field or req.description}'."

                severity = Severity.CRITICAL.value if req.mandatory else Severity.MINOR.value
                results.append(
                    VerificationResult(
                        verification_id=verif_id,
                        requirement_id=req.requirement_id,
                        bid_id=bid_id,
                        status=status,
                        severity=severity,
                        expected=f"{req.operator} {req.expected_value} {req.unit or ''}".strip(),
                        actual="MISSING",
                        operator_used=req.operator,
                        reason=reason,
                        requires_human_review=req.mandatory,
                        evidence=[],
                        precedence_chain={
                            "status": "EFFECTIVE",
                            "source_type": req.source_type,
                            "source_priority": req.source_priority,
                        }
                    )
                )
                continue

            # 3D. Execute Deterministic Operator
            # Use primary matching fact
            fact = matching_facts[0]
            actual_val = fact.normalized_value if fact.normalized_value is not None else fact.value
            expected_val = req.normalized_expected_value if req.normalized_expected_value is not None else req.expected_value

            # If operator is VALID_ON, pass reference date as expected
            if req.operator == OperatorType.VALID_ON.value:
                expected_val = ref_date

            op_result = evaluate_operator(req.operator, actual_val, expected_val, req.field or "")

            # Assemble evidence pointer(s) preserving multi-block provenance
            evidence_list = []
            if getattr(fact, "evidence", None):
                for ev_item in fact.evidence:
                    ev_dict = {
                        "document": ev_item.get("document", fact.source_document),
                        "page": ev_item.get("page", fact.page),
                        "bbox": ev_item.get("bbox", fact.bbox),
                        "snippet": ev_item.get("snippet", fact.raw_text_snippet),
                        "source_type": ev_item.get("source_type", "BIDDER_SUBMISSION"),
                    }
                    if "block_id" in ev_item:
                        ev_dict["block_id"] = ev_item["block_id"]
                    evidence_list.append(ev_dict)
            elif fact.source_document and fact.page:
                ev = EvidencePointer(
                    document=fact.source_document,
                    page=fact.page,
                    bbox=fact.bbox,
                    snippet=fact.raw_text_snippet,
                    source_type="BIDDER_SUBMISSION"
                )
                evidence_list.append(ev.to_dict())

            # Determine severity
            if op_result.status == ComplianceStatus.PASS:
                sev = Severity.INFO.value
            elif op_result.status == ComplianceStatus.FAIL:
                sev = Severity.CRITICAL.value if req.mandatory else Severity.MAJOR.value
            elif op_result.status in [ComplianceStatus.REVIEW, ComplianceStatus.PARTIAL]:
                sev = Severity.MAJOR.value
            else:
                sev = Severity.MINOR.value

            needs_review = (
                op_result.requires_human_review
                or op_result.status in [ComplianceStatus.REVIEW, ComplianceStatus.PARTIAL]
                or fact.extraction_confidence == "LOW"
            )

            results.append(
                VerificationResult(
                    verification_id=verif_id,
                    requirement_id=req.requirement_id,
                    bid_id=bid_id,
                    fact_id=fact.fact_id,
                    status=op_result.status.value,
                    severity=sev,
                    expected=f"{req.operator} {req.expected_value} {req.unit or ''}".strip(),
                    actual=f"{fact.value} {fact.unit or ''}".strip(),
                    operator_used=req.operator,
                    reason=op_result.reason,
                    requires_human_review=needs_review,
                    evidence=evidence_list,
                    anomaly_refs=fact.metadata.get("anomaly_refs", []),
                    precedence_chain={
                        "status": "EFFECTIVE",
                        "source_type": req.source_type,
                        "source_priority": req.source_priority,
                    }
                )
            )

        return results

    def _check_exemption_status(self, facts_by_field: Dict[str, List[BidderFact]], field_candidates: List[str]) -> Optional[bool]:
        for candidate in field_candidates:
            if candidate in facts_by_field:
                fact = facts_by_field[candidate][0]
                val = normalize_boolean(fact.value)
                if val is not None:
                    return val
        return None

    def _evaluate_conditional_exemption(
        self,
        req: TenderRequirement,
        is_mse: Optional[bool],
        is_startup: Optional[bool],
        bid_id: str,
        verif_id: str,
    ) -> Optional[VerificationResult]:
        applicability = req.applicability or {}

        # 1. MSE Exemption
        if applicability.get("mse_exemption_allowed"):
            if is_mse is True:
                return VerificationResult(
                    verification_id=verif_id,
                    requirement_id=req.requirement_id,
                    bid_id=bid_id,
                    status=ComplianceStatus.N_A.value,
                    severity=Severity.INFO.value,
                    expected=f"{req.operator} {req.expected_value} (Exemption Eligible)",
                    actual="EXEMPTED (MSE Verified)",
                    operator_used=req.operator,
                    reason=f"Requirement not applicable (N/A): Statutory exemption applied under GeM MSE policy for '{req.description}'. Exemptions must NEVER return PASS.",
                    requires_human_review=False,
                    precedence_chain={"status": "EXEMPTION_APPLIED", "exemption_type": "MSE"}
                )
            elif is_mse is None and applicability.get("require_explicit_claim"):
                # Missing evidence on claimed exemption
                return VerificationResult(
                    verification_id=verif_id,
                    requirement_id=req.requirement_id,
                    bid_id=bid_id,
                    status=ComplianceStatus.REVIEW.value,
                    severity=Severity.MAJOR.value,
                    expected=f"{req.operator} {req.expected_value}",
                    actual="Exemption Claimed / Unverified",
                    operator_used=req.operator,
                    reason="MSE exemption is allowed by tender, but bidder MSE registration evidence is missing or unverified.",
                    requires_human_review=True,
                    precedence_chain={"status": "EXEMPTION_REVIEW", "exemption_type": "MSE"}
                )

        # 2. Startup Exemption
        if applicability.get("startup_exemption_allowed"):
            if is_startup is True:
                return VerificationResult(
                    verification_id=verif_id,
                    requirement_id=req.requirement_id,
                    bid_id=bid_id,
                    status=ComplianceStatus.N_A.value,
                    severity=Severity.INFO.value,
                    expected=f"{req.operator} {req.expected_value} (Exemption Eligible)",
                    actual="EXEMPTED (DPIIT Startup Verified)",
                    operator_used=req.operator,
                    reason=f"Requirement not applicable (N/A): Statutory exemption applied under Startup India / GeM policy for '{req.description}'. Exemptions must NEVER return PASS.",
                    requires_human_review=False,
                    precedence_chain={"status": "EXEMPTION_APPLIED", "exemption_type": "STARTUP"}
                )

        return None
