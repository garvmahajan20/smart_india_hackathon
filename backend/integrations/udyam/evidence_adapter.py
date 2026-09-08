# -*- coding: utf-8 -*-
"""
API Setu Udyam Evidence & Provenance Adapter.
Bridges external Udyam verification responses into:
- EvidenceReference (source_type="API_SETU_OFFICIAL_REGISTRY", zero bbox convention)
- BidderFact (strongly typed parameter for deterministic compliance engine)
- ProvenanceDAG (strict acyclic graph with exact XML field paths)
- AdapterResponse (conforming to BaseGovernmentAdapter verification contract)
"""

import difflib
from typing import Any, Dict, Optional

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
from backend.verification.models import AdapterResponse, VerificationStatus
from .models import UdyamVerificationResponse, UdyamVerificationStatus


class APISetuUdyamEvidenceAdapter:
    """
    Transforms authoritative API Setu Udyam responses into deterministic pipeline artifacts.
    """

    @staticmethod
    def to_evidence_reference(response: UdyamVerificationResponse) -> EvidenceReference:
        """
        Creates EvidenceReference model pointing to authoritative API Setu Udyam registry.
        Uses [0.0, 0.0, 0.0, 0.0] bounding box convention for external API registry evidence.
        """
        snippet = (
            f"[API_SETU:UDCER] Authority: {response.issuer or 'Ministry of MSME'} | "
            f"Udyam: {response.udyam_number} | Enterprise: {response.enterprise_name or 'N/A'} | "
            f"Type: {response.enterprise_type or 'N/A'} | Status: {response.status.value} | Txn: {response.txn_id}"
        )
        return EvidenceReference(
            document=f"API_SETU:UDCER:{response.udyam_number}",
            page=1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            snippet=snippet,
            extraction_method="API_SETU_UDCER_REST",
            extraction_confidence="HIGH" if response.status == UdyamVerificationStatus.VERIFIED else "LOW",
            block_id=f"BLOCK:API_SETU:UDCER:{response.udyam_number}",
        )

    @staticmethod
    def to_bidder_fact(
        response: UdyamVerificationResponse,
        bid_id: str = "UNKNOWN_BID",
        fact_id_prefix: str = "FACT-UDYAM",
    ) -> BidderFact:
        """
        Synthesizes a canonical BidderFact from an authoritative Udyam verification response.
        Conforms strictly to contracts/bidder_fact.schema.json.
        """
        ev_ref = APISetuUdyamEvidenceAdapter.to_evidence_reference(response)
        fact_id = f"{fact_id_prefix}-{response.udyam_number}"

        metadata: Dict[str, Any] = {
            "source_provider": "API_SETU",
            "authority": "MINISTRY_OF_MSME",
            "api_endpoint": "certificate/v3/msme/udcer",
            "environment": "sandbox" if response.is_live else "unit_test",
            "transaction_id": response.txn_id,
            "http_status": response.http_status,
            "response_hash": response.response_hash,
            "enterprise_name": response.enterprise_name,
            "enterprise_type": response.enterprise_type,
            "major_activity": response.major_activity,
            "date_of_commencement": response.date_of_commencement,
            "social_category": response.social_category,
            "verification_status": response.status.value,
            "certificate_type": response.certificate_type,
            "certificate_number": response.certificate_number,
            "issuer": response.issuer,
            "xml_field_paths": response.xml_field_paths,
        }

        evidence_dict = {
            "block_id": ev_ref.block_id,
            "document": ev_ref.document,
            "page": 1,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "snippet": ev_ref.snippet,
            "source_type": "API_SETU_OFFICIAL_REGISTRY",
        }

        return BidderFact(
            fact_id=fact_id,
            bid_id=bid_id,
            field="udyam_registration_number",
            value=response.udyam_number,
            source_document=ev_ref.document,
            page=1,
            extraction_confidence="HIGH" if response.status == UdyamVerificationStatus.VERIFIED else "LOW",
            extraction_method="API_SETU_UDCER_REST",
            canonical_field="UDYAM_REGISTRATION_NUMBER",
            raw_text_snippet=ev_ref.snippet,
            metadata=metadata,
            evidence=[evidence_dict],
            field_resolution={
                "raw_field": "udyam_registration_number",
                "canonical_field_id": "UDYAM_REGISTRATION_NUMBER",
                "label": "Udyam Registration Number",
                "category": "STATUTORY_COMPLIANCE",
                "resolution_method": "API_SETU_REGISTRY_MAPPING",
                "resolution_status": "RESOLVED",
                "contradiction_eligible": True,
                "family": "MSME_IDENTIFIERS",
            },
        )

    @staticmethod
    def integrate_with_dag(
        dag: ProvenanceDAG,
        fact: BidderFact,
        response: UdyamVerificationResponse,
    ) -> None:
        """
        Integrates Udyam verification evidence and BidderFact into an existing ProvenanceDAG.
        Connects:
          API_SETU:UDCER -> transaction_id -> response_hash -> xml_path -> BidderFact
        Preserves strict graph acyclicity and validates graph invariants.
        """
        evidence_node_id = f"BLOCK:API_SETU:UDCER:{response.udyam_number}"
        evidence_node = ProvenanceNode(
            node_id=evidence_node_id,
            node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
            label=f"API Setu Udyam Record ({response.udyam_number})",
            properties={
                "document": f"API_SETU:UDCER:{response.udyam_number}",
                "page": 1,
                "source_type": "API_SETU_AUTHORITATIVE",
                "authority": response.issuer or "MINISTRY_OF_MSME",
                "transaction_id": response.txn_id,
                "response_hash": response.response_hash,
                "xml_field_paths": response.xml_field_paths,
                "enterprise_name": response.enterprise_name,
                "enterprise_type": response.enterprise_type,
                "status": response.status.value,
                "verified_by_authority": (response.status == UdyamVerificationStatus.VERIFIED),
            },
        )
        dag.add_node(evidence_node)

        fact_node_id = f"FACT:{fact.fact_id}"
        fact_node = ProvenanceNode(
            node_id=fact_node_id,
            node_type=NodeType.BIDDER_FACT.value,
            label=f"BidderFact: udyam = {fact.value}",
            properties={
                "bid_id": fact.bid_id,
                "field": fact.field,
                "canonical_field": fact.canonical_field,
                "value": fact.value,
                "extraction_confidence": fact.extraction_confidence,
                "extraction_method": fact.extraction_method,
            },
        )
        dag.add_node(fact_node)

        edge_id = make_edge_id(fact_node_id, EdgeType.FACT_GROUNDED_BY.value, evidence_node_id)
        dag.add_edge(ProvenanceEdge(
            edge_id=edge_id,
            source_id=fact_node_id,
            edge_type=EdgeType.FACT_GROUNDED_BY.value,
            target_id=evidence_node_id,
            properties={
                "authority": response.issuer or "MINISTRY_OF_MSME",
                "txn_id": response.txn_id,
            },
        ))

        dag.validate()

    @staticmethod
    def to_adapter_response(
        response: UdyamVerificationResponse,
        expected_entity_name: Optional[str] = None,
    ) -> AdapterResponse:
        """
        Transforms UdyamVerificationResponse into standard AdapterResponse contract
        adhering to BaseGovernmentAdapter interface.
        """
        if response.status == UdyamVerificationStatus.VERIFIED:
            status = VerificationStatus.VERIFIED
            reason = f"Udyam '{response.udyam_number}' verified against Ministry of MSME via API Setu."
        elif response.status == UdyamVerificationStatus.NOT_VERIFIED:
            status = VerificationStatus.NOT_FOUND
            reason = f"Udyam '{response.udyam_number}' not found in MSME records."
        elif response.status == UdyamVerificationStatus.INVALID_REQUEST:
            status = VerificationStatus.UNVERIFIED
            reason = f"Invalid Udyam request: {response.error_message or 'Format or parameter error'}."
        else:
            status = VerificationStatus.REVIEW
            reason = f"Udyam verification external error: {response.error_message or 'Gateway failure'}."

        reg_name = response.enterprise_name or ""

        # Identity cross-check
        if expected_entity_name and reg_name and status == VerificationStatus.VERIFIED:
            sim = difflib.SequenceMatcher(None, expected_entity_name.lower().strip(), reg_name.lower().strip()).ratio()
            if sim < 0.60 and not (expected_entity_name.lower() in reg_name.lower() or reg_name.lower() in expected_entity_name.lower()):
                status = VerificationStatus.IDENTITY_MISMATCH
                reason = (
                    f"Udyam '{response.udyam_number}' is registered to '{reg_name}', "
                    f"which does not match claimed entity '{expected_entity_name}' (similarity: {sim:.2f})."
                )

        return AdapterResponse(
            status=status,
            adapter_name="APISetuUdyamAdapter",
            queried_identifier=response.udyam_number,
            source=response.issuer or "MINISTRY_OF_MSME",
            reason=reason,
            registered_entity_name=reg_name,
            registration_status="ACTIVE" if status == VerificationStatus.VERIFIED else "INACTIVE",
            matched_entity={
                "udyam_number": response.udyam_number,
                "enterprise_name": response.enterprise_name,
                "enterprise_type": response.enterprise_type,
                "major_activity": response.major_activity,
                "date_of_commencement": response.date_of_commencement,
                "social_category": response.social_category,
                "state": response.state,
                "district": response.district,
                "issuer": response.issuer,
                "certificate_type": response.certificate_type,
                "certificate_number": response.certificate_number,
            },
            evidence=[{
                "type": "API_SETU_UDCER",
                "udyam_number": response.udyam_number,
                "txn_id": response.txn_id,
                "response_hash": response.response_hash,
                "xml_field_paths": response.xml_field_paths,
            }],
            is_mock=not response.is_live,
        )
