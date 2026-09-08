# -*- coding: utf-8 -*-
"""
GSTINAPI Evidence & Provenance Adapter.
Transforms authoritative GST verification and return history into:
- EvidenceReference (source_type="GSTINAPI_REGISTRY", zero bbox convention)
- BidderFact (strongly typed parameters consumed by rule & contradiction engines)
- ProvenanceDAG (strict acyclic graph linking GST registry to facts)
- AdapterResponse (conforming to BaseGovernmentAdapter contract)

Critical Governance Invariants:
1. Provider errors, 404s, timeouts, and auth failures MUST NOT produce positive BidderFacts.
2. Only VERIFIED responses generate authoritative facts.
3. Does not manufacture contradictions if a field is absent from response.
"""

import difflib
from typing import Any, Dict, List, Optional

from backend.core.models import BidderFact
from backend.core.provenance_dag import (
    EdgeType,
    NodeType,
    ProvenanceDAG,
    ProvenanceEdge,
    ProvenanceNode,
    make_edge_id,
)
from backend.ingestion.models import EvidenceReference
from backend.verification.base import BaseGovernmentAdapter
from backend.verification.models import AdapterResponse, VerificationStatus
from .models import (
    GSTVerificationResponse,
    GSTVerificationStatus,
    extract_pan_from_gstin,
)


class GSTINAPIEvidenceAdapter:
    """
    Transforms authoritative GSTINAPI responses into deterministic pipeline artifacts.
    """

    @staticmethod
    def to_evidence_reference(response: GSTVerificationResponse) -> EvidenceReference:
        """
        Creates EvidenceReference pointing to the authoritative GSTINAPI registry record.
        Uses [0.0, 0.0, 0.0, 0.0] bounding box convention for external API registry evidence.
        """
        data = response.data
        legal_name = data.legal_name if data else "N/A"
        gst_status = data.status if data else "N/A"
        snippet = (
            f"[GSTINAPI:REGISTRY] GSTIN: {response.gstin} | "
            f"Legal Name: {legal_name} | Status: {gst_status} | "
            f"Verification: {response.status.value}"
        )
        return EvidenceReference(
            document=f"GSTINAPI:REGISTRY:{response.gstin}",
            page=1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            snippet=snippet,
            extraction_method="GSTINAPI_REST_LOOKUP",
            extraction_confidence="HIGH" if response.status == GSTVerificationStatus.VERIFIED else "LOW",
            block_id=f"BLOCK:GSTINAPI:REGISTRY:{response.gstin}",
        )

    @staticmethod
    def to_bidder_facts(
        response: GSTVerificationResponse,
        bid_id: str,
        fact_id_prefix: str = "FACT-GST",
    ) -> List[BidderFact]:
        """
        Transforms verified GST response into authoritative BidderFacts.
        INVARIANT: Returns EMPTY list on failed, unavailable, or non-verified responses.
        """
        if response.status != GSTVerificationStatus.VERIFIED or not response.data:
            return []

        tp = response.data
        ev_ref = GSTINAPIEvidenceAdapter.to_evidence_reference(response)
        facts: List[BidderFact] = []

        base_meta: Dict[str, Any] = {
            "source_provider": "GSTINAPI",
            "authority": "GST_PORTAL_REGISTRY",
            "gstin": response.gstin,
            "response_hash": response.response_hash,
            "is_test": response.is_test,
            "credits_remaining": response.credits_remaining,
        }

        evidence_item = {
            "block_id": ev_ref.block_id,
            "document": ev_ref.document,
            "page": 1,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "snippet": ev_ref.snippet,
            "source_type": "GSTINAPI_REGISTRY",
        }

        # 1. Primary GSTIN Fact
        facts.append(BidderFact(
            fact_id=f"{fact_id_prefix}-GSTIN-{response.gstin}",
            bid_id=bid_id,
            field="gstin",
            value=response.gstin,
            source_document=ev_ref.document,
            page=1,
            extraction_confidence="HIGH",
            extraction_method="GSTINAPI_REGISTRY",
            canonical_field="GSTIN",
            raw_text_snippet=f"GSTIN: {response.gstin}",
            metadata={**base_meta, "field_type": "tax_identifier"},
            evidence=[evidence_item],
            field_resolution={
                "raw_field": "gstin",
                "canonical_field_id": "GSTIN",
                "label": "Goods and Services Tax Identification Number",
                "category": "REGULATORY_IDENTITY",
                "resolution_method": "EXACT_CANONICAL",
                "resolution_status": "RESOLVED",
                "contradiction_eligible": True,
                "family": "GSTIN",
            },
        ))

        # 2. Legal Name Fact
        if tp.legal_name:
            facts.append(BidderFact(
                fact_id=f"{fact_id_prefix}-LEGAL-NAME-{response.gstin}",
                bid_id=bid_id,
                field="legal_name",
                value=tp.legal_name,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="GSTINAPI_REGISTRY",
                canonical_field="LEGAL_ENTITY_NAME",
                raw_text_snippet=f"Legal Name: {tp.legal_name}",
                metadata={**base_meta, "trade_name": tp.trade_name},
                evidence=[evidence_item],
                field_resolution={
                    "raw_field": "legal_name",
                    "canonical_field_id": "LEGAL_ENTITY_NAME",
                    "label": "Legal Entity Name",
                    "category": "REGULATORY_IDENTITY",
                    "resolution_method": "EXACT_CANONICAL",
                    "resolution_status": "RESOLVED",
                    "contradiction_eligible": True,
                    "family": "LEGAL_ENTITY_NAME",
                },
            ))

        # 3. GST Registration Status Fact
        if tp.status:
            facts.append(BidderFact(
                fact_id=f"{fact_id_prefix}-STATUS-{response.gstin}",
                bid_id=bid_id,
                field="gst_status",
                value=tp.status,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="GSTINAPI_REGISTRY",
                canonical_field="GST_STATUS",
                raw_text_snippet=f"GST Status: {tp.status}",
                metadata={**base_meta, "cancellation_date": tp.cancellation_date},
                evidence=[evidence_item],
                field_resolution={
                    "raw_field": "gst_status",
                    "canonical_field_id": "GST_STATUS",
                    "label": "GST Registration Status",
                    "category": "REGULATORY_IDENTITY",
                    "resolution_method": "REGISTRY_MAPPING",
                    "resolution_status": "RESOLVED",
                    "contradiction_eligible": True,
                    "family": "GST_STATUS",
                },
            ))

        # 4. Taxpayer Type Fact
        if tp.taxpayer_type:
            facts.append(BidderFact(
                fact_id=f"{fact_id_prefix}-TAXPAYER-TYPE-{response.gstin}",
                bid_id=bid_id,
                field="taxpayer_type",
                value=tp.taxpayer_type,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="GSTINAPI_REGISTRY",
                canonical_field="TAXPAYER_TYPE",
                raw_text_snippet=f"Taxpayer Type: {tp.taxpayer_type}",
                metadata=base_meta,
                evidence=[evidence_item],
            ))

        # 5. Registration Date Fact
        if tp.registration_date:
            facts.append(BidderFact(
                fact_id=f"{fact_id_prefix}-REGDATE-{response.gstin}",
                bid_id=bid_id,
                field="registration_date",
                value=tp.registration_date,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="GSTINAPI_REGISTRY",
                canonical_field="GST_REGISTRATION_DATE",
                raw_text_snippet=f"GST Registration Date: {tp.registration_date}",
                metadata=base_meta,
                evidence=[evidence_item],
            ))

        # 6. Embedded PAN Fact
        pan = extract_pan_from_gstin(response.gstin)
        if pan:
            facts.append(BidderFact(
                fact_id=f"{fact_id_prefix}-PAN-{pan}",
                bid_id=bid_id,
                field="pan",
                value=pan,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="GSTINAPI_REGISTRY_DERIVED",
                canonical_field="PAN",
                raw_text_snippet=f"Derived PAN from GSTIN: {pan}",
                metadata={**base_meta, "derived_from_gstin": response.gstin},
                evidence=[evidence_item],
                field_resolution={
                    "raw_field": "pan",
                    "canonical_field_id": "PAN",
                    "label": "Permanent Account Number",
                    "category": "REGULATORY_IDENTITY",
                    "resolution_method": "EXACT_CANONICAL",
                    "resolution_status": "RESOLVED",
                    "contradiction_eligible": True,
                    "family": "PAN",
                },
            ))

        # 7. Return Filing Compliance Fact (if return checks performed)
        if response.compliance:
            facts.append(BidderFact(
                fact_id=f"{fact_id_prefix}-COMPLIANCE-{response.gstin}-{response.fy or 'CURRENT'}",
                bid_id=bid_id,
                field="gst_filing_compliance",
                value=f"TOTAL_FILED_{response.compliance.total_filed}",
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="GSTINAPI_RETURNS",
                canonical_field="GST_FILING_COMPLIANCE",
                raw_text_snippet=f"GST Returns FY {response.fy}: {response.compliance.total_filed} returns filed",
                metadata={
                    **base_meta,
                    "fy": response.fy,
                    "total_filed": response.compliance.total_filed,
                    "by_type": response.compliance.by_type,
                },
                evidence=[evidence_item],
            ))

        return facts

    @staticmethod
    def to_adapter_response(
        response: GSTVerificationResponse,
        expected_entity_name: Optional[str] = None,
    ) -> AdapterResponse:
        """
        Transforms GSTVerificationResponse into standard AdapterResponse contract.
        Adheres strictly to BaseGovernmentAdapter interface.
        """
        tp = response.data
        reg_name = tp.legal_name if tp else ""

        if response.status == GSTVerificationStatus.VERIFIED:
            status = VerificationStatus.VERIFIED
            reason = f"GSTIN '{response.gstin}' verified active in registry via GSTINAPI."
        elif response.status == GSTVerificationStatus.CANCELLED:
            status = VerificationStatus.INACTIVE
            reason = f"GSTIN '{response.gstin}' is CANCELLED in GST database (cancellation date: {tp.cancellation_date if tp else 'N/A'})."
        elif response.status == GSTVerificationStatus.SUSPENDED:
            status = VerificationStatus.INACTIVE
            reason = f"GSTIN '{response.gstin}' is SUSPENDED in GST database."
        elif response.status == GSTVerificationStatus.NOT_VERIFIED:
            status = VerificationStatus.NOT_FOUND
            reason = f"GSTIN '{response.gstin}' not found / not registered in GST database."
        elif response.status == GSTVerificationStatus.UNVERIFIED:
            status = VerificationStatus.UNVERIFIED
            reason = f"Invalid GSTIN input: {response.error_message or 'Format validation failed'}."
        elif response.status == GSTVerificationStatus.AUTH_ERROR:
            status = VerificationStatus.REVIEW
            reason = f"GSTINAPI authentication failure: {response.error_message or 'Invalid API key'}."
        elif response.status == GSTVerificationStatus.QUOTA_EXHAUSTED:
            status = VerificationStatus.REVIEW
            reason = "GSTINAPI account credits exhausted; manual verification required."
        elif response.status == GSTVerificationStatus.RATE_LIMITED:
            status = VerificationStatus.REVIEW
            reason = "GSTINAPI rate limit reached; review required."
        else:
            status = VerificationStatus.REVIEW
            reason = f"GST verification provider error: {response.error_message or 'Gateway unavailable'}."

        # Identity cross-check
        if expected_entity_name and reg_name and status == VerificationStatus.VERIFIED:
            sim = difflib.SequenceMatcher(None, expected_entity_name.lower().strip(), reg_name.lower().strip()).ratio()
            # Check substring or high similarity
            is_sub = (expected_entity_name.lower() in reg_name.lower()) or (reg_name.lower() in expected_entity_name.lower())
            if sim < 0.60 and not is_sub:
                status = VerificationStatus.IDENTITY_MISMATCH
                reason = (
                    f"GSTIN '{response.gstin}' is registered to '{reg_name}', "
                    f"which differs from claimed bidder entity '{expected_entity_name}' (similarity: {sim:.2f})."
                )

        # Build matched_entity metadata
        matched_entity = None
        if tp:
            matched_entity = {
                "gstin": tp.gstin,
                "legal_name": tp.legal_name,
                "trade_name": tp.trade_name,
                "status": tp.status,
                "taxpayer_type": tp.taxpayer_type,
                "registration_date": tp.registration_date,
                "state_code": tp.state_code,
                "einvoice_status": tp.einvoice_status,
                "city": tp.city,
                "pincode": tp.pincode,
            }
            if response.returns:
                matched_entity["returns_count"] = len(response.returns)
            if response.compliance:
                matched_entity["compliance"] = response.compliance.to_dict()

        return AdapterResponse(
            status=status,
            adapter_name="GSTINAPIGovernmentAdapter",
            queried_identifier=response.gstin,
            source="GSTINAPI_PROVIDER",
            reason=reason,
            registered_entity_name=reg_name,
            registration_status=tp.status if tp else ("ACTIVE" if status == VerificationStatus.VERIFIED else "INACTIVE"),
            matched_entity=matched_entity,
            evidence=[{
                "type": "GSTINAPI_REGISTRY",
                "gstin": response.gstin,
                "response_hash": response.response_hash,
                "is_test": response.is_test,
                "credits_remaining": response.credits_remaining,
            }],
            is_mock=False,
        )

    @staticmethod
    def integrate_with_dag(
        dag: ProvenanceDAG,
        facts: List[BidderFact],
        response: GSTVerificationResponse,
    ) -> None:
        """
        Integrates GST facts into existing ProvenanceDAG with strict acyclicity.
        Connects:
          GSTINAPI:REGISTRY -> response_hash -> BidderFact
        """
        if not facts:
            return

        evidence_node_id = f"BLOCK:GSTINAPI:REGISTRY:{response.gstin}"
        evidence_node = ProvenanceNode(
            node_id=evidence_node_id,
            node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
            label=f"GSTINAPI Record ({response.gstin})",
            properties={
                "document": f"GSTINAPI:REGISTRY:{response.gstin}",
                "page": 1,
                "source_type": "GSTINAPI_OFFICIAL_REGISTRY",
                "authority": "GST_PORTAL_REGISTRY",
                "response_hash": response.response_hash,
                "status": response.status.value,
                "verified_by_authority": (response.status == GSTVerificationStatus.VERIFIED),
            },
        )
        dag.add_node(evidence_node)

        for fact in facts:
            fact_node_id = f"FACT:{fact.fact_id}"
            fact_node = ProvenanceNode(
                node_id=fact_node_id,
                node_type=NodeType.BIDDER_FACT.value,
                label=f"BidderFact: {fact.field} = {fact.value}",
                properties={
                    "bid_id": fact.bid_id,
                    "field": fact.field,
                    "value": fact.value,
                    "canonical_field": fact.canonical_field,
                    "confidence": fact.extraction_confidence,
                    "source": "GSTINAPI",
                },
            )
            dag.add_node(fact_node)

            edge_id = make_edge_id(fact_node_id, EdgeType.FACT_GROUNDED_BY.value, evidence_node_id)
            dag.add_edge(ProvenanceEdge(
                edge_id=edge_id,
                source_id=fact_node_id,
                edge_type=EdgeType.FACT_GROUNDED_BY.value,
                target_id=evidence_node_id,
                properties={"authority": "GSTINAPI", "gstin": response.gstin},
            ))

        dag.validate()


class GSTINAPIGovernmentAdapter(BaseGovernmentAdapter):
    """
    Direct Government Verification Adapter for GSTIN backed by GSTINAPI.
    Implements BaseGovernmentAdapter for zero-friction swap-in.
    """

    def __init__(self, client=None):
        if client is None:
            from .client import GSTINAPIClient
            self.client = GSTINAPIClient()
        else:
            self.client = client

    @property
    def adapter_name(self) -> str:
        return "GSTINAPIGovernmentAdapter"

    @property
    def source_name(self) -> str:
        return "GSTINAPI_PROVIDER"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResponse:
        include_profile = kwargs.get("include_profile", True)
        resp = self.client.verify_gstin(identifier, include_profile=include_profile)
        adapter_resp = GSTINAPIEvidenceAdapter.to_adapter_response(
            resp, expected_entity_name=expected_entity_name
        )
        if timestamp:
            adapter_resp.timestamp = timestamp
        return adapter_resp
