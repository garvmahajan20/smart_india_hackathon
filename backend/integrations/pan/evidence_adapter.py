# -*- coding: utf-8 -*-
"""
API Setu PAN Evidence & Provenance Adapter.
Bridges external PAN verification responses into:
- EvidenceReference (with source_type="API_SETU", zero bbox convention)
- BidderFact (strongly typed parameter for deterministic evaluation)
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
from .models import PANVerificationResponse, PANVerificationStatus


class APISetuPANEvidenceAdapter:
    """
    Transforms authoritative API Setu PANCR responses into deterministic pipeline artifacts.
    """

    @staticmethod
    def to_evidence_reference(response: PANVerificationResponse) -> EvidenceReference:
        """
        Creates EvidenceReference model pointing to the authoritative API Setu PAN registry.
        Uses [0.0, 0.0, 0.0, 0.0] bounding box convention for external API registry evidence,
        clearly distinguishing external API proof from physical PDF page segmentation.
        """
        snippet = (
            f"[API_SETU:PANCR] Authority: {response.issuer or 'Income Tax Department'} | "
            f"PAN: {response.pan} | Name: {response.verified_name or 'N/A'} | "
            f"Status: {response.status.value} | Txn: {response.txn_id}"
        )
        return EvidenceReference(
            document=f"API_SETU:PANCR:{response.pan}",
            page=1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            snippet=snippet,
            extraction_method="API_SETU_PANCR_REST",
            extraction_confidence="HIGH" if response.status == PANVerificationStatus.VERIFIED else "LOW",
            block_id=f"BLOCK:API_SETU:PANCR:{response.pan}",
        )

    @staticmethod
    def to_bidder_fact(
        response: PANVerificationResponse,
        bid_id: str,
        fact_id_prefix: str = "FACT-PAN",
    ) -> BidderFact:
        """
        Synthesizes a canonical BidderFact from an authoritative PAN verification response.
        Conforms strictly to contracts/bidder_fact.schema.json.
        """
        ev_ref = APISetuPANEvidenceAdapter.to_evidence_reference(response)
        fact_id = f"{fact_id_prefix}-{response.pan}"

        metadata: Dict[str, Any] = {
            "source_provider": "API_SETU",
            "authority": "INCOME_TAX_DEPARTMENT",
            "api_endpoint": "certificate/v3/pan/pancr",
            "environment": "sandbox" if response.is_live else "unit_test",
            "transaction_id": response.txn_id,
            "http_status": response.http_status,
            "response_hash": response.response_hash,
            "verified_name": response.verified_name,
            "verified_dob": response.verified_dob,
            "verification_status": response.status.value,
            "certificate_type": response.certificate_type,
            "certificate_number": response.certificate_number,
            "issuer": response.issuer,
            "xml_field_paths": response.xml_field_paths,
            "verified_on": response.verified_on,
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
            field="pan",
            value=response.pan,
            source_document=ev_ref.document,
            page=1,
            extraction_confidence="HIGH" if response.status == PANVerificationStatus.VERIFIED else "LOW",
            extraction_method="API_SETU_PANCR_REST",
            canonical_field="PAN",
            raw_text_snippet=ev_ref.snippet,
            metadata=metadata,
            evidence=[evidence_dict],
            field_resolution={
                "raw_field": "pan",
                "canonical_field_id": "PAN",
                "label": "Permanent Account Number",
                "category": "STATUTORY_COMPLIANCE",
                "resolution_method": "API_SETU_REGISTRY_MAPPING",
                "resolution_status": "RESOLVED",
                "contradiction_eligible": True,
                "family": "TAX_IDENTIFIERS",
            },
        )

    @staticmethod
    def integrate_with_dag(
        dag: ProvenanceDAG,
        fact: BidderFact,
        response: PANVerificationResponse,
    ) -> None:
        """
        Integrates PAN verification evidence and BidderFact into an existing ProvenanceDAG.
        Connects:
          API_SETU:PANCR -> transaction_id -> response_hash -> xml_path -> BidderFact
        Preserves strict graph acyclicity and validates graph invariants.
        """
        # 1. Register External Authority Evidence Block
        evidence_node_id = f"BLOCK:API_SETU:PANCR:{response.pan}"
        evidence_node = ProvenanceNode(
            node_id=evidence_node_id,
            node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
            label=f"API Setu PAN Record ({response.pan})",
            properties={
                "document": f"API_SETU:PANCR:{response.pan}",
                "page": 1,
                "source_type": "API_SETU_AUTHORITATIVE",
                "authority": response.issuer or "INCOME_TAX_DEPARTMENT",
                "transaction_id": response.txn_id,
                "response_hash": response.response_hash,
                "xml_field_paths": response.xml_field_paths,
                "verified_name": response.verified_name,
                "status": response.status.value,
                "verified_by_authority": (response.status == PANVerificationStatus.VERIFIED),
            },
        )
        dag.add_node(evidence_node)

        # 2. Register Bidder Fact Node
        fact_node_id = f"FACT:{fact.fact_id}"
        fact_node = ProvenanceNode(
            node_id=fact_node_id,
            node_type=NodeType.BIDDER_FACT.value,
            label=f"BidderFact: pan = {fact.value}",
            properties={
                "bid_id": fact.bid_id,
                "field": fact.field,
                "value": fact.value,
                "canonical_field": fact.canonical_field,
                "confidence": fact.extraction_confidence,
                "source": "API_SETU",
            },
        )
        dag.add_node(fact_node)

        # 3. Add Edge: Fact Grounded By External Authority Block
        edge_id = make_edge_id(fact_node_id, EdgeType.FACT_GROUNDED_BY.value, evidence_node_id)
        dag.add_edge(ProvenanceEdge(
            edge_id=edge_id,
            source_id=fact_node_id,
            edge_type=EdgeType.FACT_GROUNDED_BY.value,
            target_id=evidence_node_id,
            properties={
                "authority": response.issuer or "INCOME_TAX_DEPARTMENT",
                "txn_id": response.txn_id,
            },
        ))

        # Enforce graph invariants
        dag.validate()

    @staticmethod
    def to_adapter_response(
        response: PANVerificationResponse,
        expected_entity_name: Optional[str] = None,
    ) -> AdapterResponse:
        """
        Transforms PANVerificationResponse into standard AdapterResponse contract
        adhering to BaseGovernmentAdapter interface.
        """
        if response.status == PANVerificationStatus.VERIFIED:
            status = VerificationStatus.VERIFIED
            reason = f"PAN '{response.pan}' verified against Income Tax Department via API Setu."
        elif response.status == PANVerificationStatus.NOT_VERIFIED:
            status = VerificationStatus.NOT_FOUND
            reason = f"PAN '{response.pan}' not found in Income Tax Department records."
        elif response.status == PANVerificationStatus.INVALID_REQUEST:
            status = VerificationStatus.UNVERIFIED
            reason = f"Invalid PAN request: {response.error_message or 'Format or parameter error'}."
        else:
            status = VerificationStatus.REVIEW
            reason = f"PAN verification external error: {response.error_message or 'Gateway failure'}."

        reg_name = response.verified_name or ""

        # Identity cross-check
        if expected_entity_name and reg_name and status == VerificationStatus.VERIFIED:
            sim = difflib.SequenceMatcher(None, expected_entity_name.lower().strip(), reg_name.lower().strip()).ratio()
            if sim < 0.60 and not (expected_entity_name.lower() in reg_name.lower() or reg_name.lower() in expected_entity_name.lower()):
                status = VerificationStatus.IDENTITY_MISMATCH
                reason = (
                    f"PAN '{response.pan}' is registered to '{reg_name}', "
                    f"which does not match claimed entity '{expected_entity_name}' (similarity: {sim:.2f})."
                )

        return AdapterResponse(
            status=status,
            adapter_name="APISetuPANAdapter",
            queried_identifier=response.pan,
            source=response.issuer or "INCOME_TAX_DEPARTMENT",
            reason=reason,
            registered_entity_name=reg_name,
            registration_status=response.certificate_status or ("ACTIVE" if status == VerificationStatus.VERIFIED else "INACTIVE"),
            matched_entity={
                "pan": response.pan,
                "name": response.verified_name,
                "dob": response.verified_dob,
                "issuer": response.issuer,
                "certificate_type": response.certificate_type,
                "certificate_number": response.certificate_number,
                "verified_on": response.verified_on,
            },
            evidence=[{
                "type": "API_SETU_PANCR",
                "pan": response.pan,
                "txn_id": response.txn_id,
                "response_hash": response.response_hash,
            }],
            is_mock=False,
        )
