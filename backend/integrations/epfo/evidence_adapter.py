# -*- coding: utf-8 -*-
"""
API Setu EPFO Evidence & Provenance Adapter.
Bridges external EPFO verification responses into:
- EvidenceReference (source_type="API_SETU_OFFICIAL_REGISTRY", zero bbox convention)
- BidderFact (strongly typed parameter for deterministic compliance engine)
- ProvenanceDAG (strict acyclic graph)
- AdapterResponse (conforming to BaseGovernmentAdapter verification contract)

CRITICAL SCOPE ENFORCEMENT:
Explicitly distinguishes EPFO DOCUMENT/CERTIFICATE VERIFICATION
from GENERAL EMPLOYER EPFO ESTABLISHMENT COMPLIANCE VERIFICATION.
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
from .models import (
    EPFOEndpointType,
    EPFOVerificationResponse,
    EPFOVerificationStatus,
)


class APISetuEPFOEvidenceAdapter:
    """
    Transforms authoritative API Setu EPFO responses into deterministic pipeline artifacts.
    """

    @staticmethod
    def to_evidence_reference(response: EPFOVerificationResponse) -> EvidenceReference:
        """
        Creates EvidenceReference model pointing to authoritative API Setu EPFO registry.
        Uses [0.0, 0.0, 0.0, 0.0] bounding box convention for external API registry evidence.
        """
        snippet = (
            f"[API_SETU:EPFO:{response.endpoint_type.value}] Authority: {response.issuer} | "
            f"ID: {response.identifier} | Name: {response.member_name or 'N/A'} | "
            f"Format: {response.format} | Status: {response.status.value} | Txn: {response.txn_id}"
        )
        return EvidenceReference(
            document=f"API_SETU:EPFO:{response.endpoint_type.value}:{response.identifier}",
            page=1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            snippet=snippet,
            extraction_method=f"API_SETU_EPFO_{response.format.upper()}",
            extraction_confidence="HIGH" if response.status == EPFOVerificationStatus.VERIFIED else "LOW",
            block_id=f"BLOCK:API_SETU:EPFO:{response.endpoint_type.value}:{response.identifier}",
        )

    @staticmethod
    def to_bidder_fact(
        response: EPFOVerificationResponse,
        bid_id: str = "UNKNOWN_BID",
        fact_id_prefix: str = "FACT-EPFO",
    ) -> BidderFact:
        """
        Synthesizes a canonical BidderFact from an authoritative EPFO verification response.
        Conforms strictly to contracts/bidder_fact.schema.json.
        """
        ev_ref = APISetuEPFOEvidenceAdapter.to_evidence_reference(response)
        fact_id = f"{fact_id_prefix}-{response.endpoint_type.value}-{response.identifier}"

        metadata: Dict[str, Any] = {
            "source_provider": "API_SETU",
            "authority": "EMPLOYEES_PROVIDENT_FUND_ORGANISATION",
            "endpoint_type": response.endpoint_type.value,
            "environment": "sandbox" if response.is_live else "unit_test",
            "transaction_id": response.txn_id,
            "http_status": response.http_status,
            "response_hash": response.response_hash,
            "member_name": response.member_name,
            "dob": response.dob,
            "certificate_number": response.certificate_number,
            "verification_status": response.status.value,
            "format": response.format,
            "pdf_size_bytes": response.pdf_size_bytes,
            "xml_field_paths": response.xml_field_paths,
            "is_employer_compliance": False,  # Explicit scope limitation!
            "scope_notice": response.scope_notice,
        }

        evidence_dict = {
            "block_id": ev_ref.block_id,
            "document": ev_ref.document,
            "page": 1,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "snippet": ev_ref.snippet,
            "source_type": "API_SETU_OFFICIAL_REGISTRY",
        }

        canonical_field = f"EPFO_{response.endpoint_type.value}"

        return BidderFact(
            fact_id=fact_id,
            bid_id=bid_id,
            field=f"epfo_{response.endpoint_type.value.lower()}",
            value=response.identifier,
            source_document=ev_ref.document,
            page=1,
            extraction_confidence="HIGH" if response.status == EPFOVerificationStatus.VERIFIED else "LOW",
            extraction_method=f"API_SETU_EPFO_{response.format.upper()}",
            canonical_field=canonical_field,
            raw_text_snippet=ev_ref.snippet,
            metadata=metadata,
            evidence=[evidence_dict],
            field_resolution={
                "raw_field": f"epfo_{response.endpoint_type.value.lower()}",
                "canonical_field_id": canonical_field,
                "label": f"EPFO {response.endpoint_type.value} Document",
                "category": "STATUTORY_COMPLIANCE",
                "resolution_method": "API_SETU_REGISTRY_MAPPING",
                "resolution_status": "RESOLVED",
                "contradiction_eligible": True,
                "family": "LABOUR_WELFARE_IDENTIFIERS",
            },
        )

    @staticmethod
    def integrate_with_dag(
        dag: ProvenanceDAG,
        fact: BidderFact,
        response: EPFOVerificationResponse,
    ) -> None:
        """
        Integrates EPFO verification evidence and BidderFact into an existing ProvenanceDAG.
        Connects:
          API_SETU:EPFO -> transaction_id -> response_hash -> BidderFact
        Preserves strict graph acyclicity and validates graph invariants.
        """
        evidence_node_id = f"BLOCK:API_SETU:EPFO:{response.endpoint_type.value}:{response.identifier}"
        evidence_node = ProvenanceNode(
            node_id=evidence_node_id,
            node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
            label=f"API Setu EPFO {response.endpoint_type.value} ({response.identifier})",
            properties={
                "document": f"API_SETU:EPFO:{response.endpoint_type.value}:{response.identifier}",
                "page": 1,
                "source_type": "API_SETU_AUTHORITATIVE",
                "authority": response.issuer or "EPFO",
                "endpoint_type": response.endpoint_type.value,
                "transaction_id": response.txn_id,
                "response_hash": response.response_hash,
                "format": response.format,
                "status": response.status.value,
                "verified_by_authority": (response.status == EPFOVerificationStatus.VERIFIED),
                "is_employer_compliance": False,
            },
        )
        dag.add_node(evidence_node)

        fact_node_id = f"FACT:{fact.fact_id}"
        fact_node = ProvenanceNode(
            node_id=fact_node_id,
            node_type=NodeType.BIDDER_FACT.value,
            label=f"BidderFact: {fact.canonical_field} = {fact.value}",
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
                "authority": response.issuer or "EPFO",
                "txn_id": response.txn_id,
                "endpoint_type": response.endpoint_type.value,
            },
        ))

        dag.validate()

    @staticmethod
    def to_adapter_response(
        response: EPFOVerificationResponse,
        expected_entity_name: Optional[str] = None,
    ) -> AdapterResponse:
        """
        Transforms EPFOVerificationResponse into standard AdapterResponse contract
        adhering to BaseGovernmentAdapter interface.
        """
        if response.status == EPFOVerificationStatus.VERIFIED:
            status = VerificationStatus.VERIFIED
            reason = f"EPFO {response.endpoint_type.value} '{response.identifier}' verified against EPFO via API Setu."
        elif response.status == EPFOVerificationStatus.NOT_VERIFIED:
            status = VerificationStatus.NOT_FOUND
            reason = f"EPFO {response.endpoint_type.value} '{response.identifier}' not found in EPFO records."
        elif response.status == EPFOVerificationStatus.INVALID_REQUEST:
            status = VerificationStatus.UNVERIFIED
            reason = f"Invalid EPFO request: {response.error_message or 'Format or parameter error'}."
        else:
            status = VerificationStatus.REVIEW
            reason = f"EPFO verification external error: {response.error_message or 'Gateway failure'}."

        reg_name = response.member_name or ""

        # Identity cross-check
        if expected_entity_name and reg_name and status == VerificationStatus.VERIFIED:
            sim = difflib.SequenceMatcher(None, expected_entity_name.lower().strip(), reg_name.lower().strip()).ratio()
            if sim < 0.60 and not (expected_entity_name.lower() in reg_name.lower() or reg_name.lower() in expected_entity_name.lower()):
                status = VerificationStatus.IDENTITY_MISMATCH
                reason = (
                    f"EPFO {response.endpoint_type.value} '{response.identifier}' is registered to '{reg_name}', "
                    f"which does not match claimed entity '{expected_entity_name}' (similarity: {sim:.2f})."
                )

        return AdapterResponse(
            status=status,
            adapter_name=f"APISetuEPFO_{response.endpoint_type.value}_Adapter",
            queried_identifier=response.identifier,
            source=response.issuer or "EMPLOYEES_PROVIDENT_FUND_ORGANISATION",
            reason=reason,
            registered_entity_name=reg_name,
            registration_status="ACTIVE" if status == VerificationStatus.VERIFIED else "INACTIVE",
            matched_entity={
                "endpoint_type": response.endpoint_type.value,
                "identifier": response.identifier,
                "member_name": response.member_name,
                "dob": response.dob,
                "certificate_number": response.certificate_number,
                "format": response.format,
                "pdf_size_bytes": response.pdf_size_bytes,
                "is_employer_compliance": False,
                "scope_notice": response.scope_notice,
            },
            evidence=[{
                "type": f"API_SETU_EPFO_{response.endpoint_type.value}",
                "identifier": response.identifier,
                "txn_id": response.txn_id,
                "response_hash": response.response_hash,
                "format": response.format,
            }],
            is_mock=not response.is_live,
        )
