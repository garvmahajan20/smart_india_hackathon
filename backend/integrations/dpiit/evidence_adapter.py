# -*- coding: utf-8 -*-
"""
API Setu DPIIT Evidence & Provenance Adapter.
Bridges external DPIIT verification responses into:
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
from .models import DPIITVerificationResponse, DPIITVerificationStatus


class APISetuDPIITEvidenceAdapter:
    """
    Transforms authoritative API Setu DPIIT responses into deterministic pipeline artifacts.
    """

    @staticmethod
    def to_evidence_reference(response: DPIITVerificationResponse) -> EvidenceReference:
        """
        Creates EvidenceReference model pointing to authoritative API Setu DPIIT registry.
        Uses [0.0, 0.0, 0.0, 0.0] bounding box convention for external API registry evidence.
        """
        snippet = (
            f"[API_SETU:SUIRC] Authority: {response.issuer or 'DPIIT'} | "
            f"Regn: {response.regn_no} | Startup: {response.startup_name or 'N/A'} | "
            f"Status: {response.status.value} | Txn: {response.txn_id}"
        )
        return EvidenceReference(
            document=f"API_SETU:SUIRC:{response.regn_no}",
            page=1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            snippet=snippet,
            extraction_method="API_SETU_SUIRC_REST",
            extraction_confidence="HIGH" if response.status == DPIITVerificationStatus.VERIFIED else "LOW",
            block_id=f"BLOCK:API_SETU:SUIRC:{response.regn_no}",
        )

    @staticmethod
    def to_bidder_fact(
        response: DPIITVerificationResponse,
        bid_id: str = "UNKNOWN_BID",
        fact_id_prefix: str = "FACT-DPIIT",
    ) -> BidderFact:
        """
        Synthesizes a canonical BidderFact from an authoritative DPIIT verification response.
        Conforms strictly to contracts/bidder_fact.schema.json.
        """
        ev_ref = APISetuDPIITEvidenceAdapter.to_evidence_reference(response)
        fact_id = f"{fact_id_prefix}-{response.regn_no}"

        metadata: Dict[str, Any] = {
            "source_provider": "API_SETU",
            "authority": "DPIIT",
            "api_endpoint": "certificate/v3/dpiit/suirc",
            "environment": "sandbox" if response.is_live else "unit_test",
            "transaction_id": response.txn_id,
            "http_status": response.http_status,
            "response_hash": response.response_hash,
            "startup_name": response.startup_name,
            "entity_type": response.entity_type,
            "incorporation_date": response.incorporation_date,
            "recognition_number": response.recognition_number,
            "recognition_date": response.recognition_date,
            "valid_upto": response.valid_upto,
            "industry": response.industry,
            "sector": response.sector,
            "verification_status": response.status.value,
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
            field="dpiit_recognition_number",
            value=response.regn_no,
            source_document=ev_ref.document,
            page=1,
            extraction_confidence="HIGH" if response.status == DPIITVerificationStatus.VERIFIED else "LOW",
            extraction_method="API_SETU_SUIRC_REST",
            canonical_field="DPIIT_RECOGNITION_NUMBER",
            raw_text_snippet=ev_ref.snippet,
            metadata=metadata,
            evidence=[evidence_dict],
            field_resolution={
                "raw_field": "dpiit_recognition_number",
                "canonical_field_id": "DPIIT_RECOGNITION_NUMBER",
                "label": "DPIIT Startup Recognition Number",
                "category": "STATUTORY_COMPLIANCE",
                "resolution_method": "API_SETU_REGISTRY_MAPPING",
                "resolution_status": "RESOLVED",
                "contradiction_eligible": True,
                "family": "STARTUP_IDENTIFIERS",
            },
        )

    @staticmethod
    def integrate_with_dag(
        dag: ProvenanceDAG,
        fact: BidderFact,
        response: DPIITVerificationResponse,
    ) -> None:
        """
        Integrates DPIIT verification evidence and BidderFact into an existing ProvenanceDAG.
        Connects:
          API_SETU:SUIRC -> transaction_id -> response_hash -> xml_path -> BidderFact
        Preserves strict graph acyclicity and validates graph invariants.
        """
        evidence_node_id = f"BLOCK:API_SETU:SUIRC:{response.regn_no}"
        evidence_node = ProvenanceNode(
            node_id=evidence_node_id,
            node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
            label=f"API Setu DPIIT Record ({response.regn_no})",
            properties={
                "document": f"API_SETU:SUIRC:{response.regn_no}",
                "page": 1,
                "source_type": "API_SETU_AUTHORITATIVE",
                "authority": response.issuer or "DPIIT",
                "transaction_id": response.txn_id,
                "response_hash": response.response_hash,
                "xml_field_paths": response.xml_field_paths,
                "startup_name": response.startup_name,
                "status": response.status.value,
                "verified_by_authority": (response.status == DPIITVerificationStatus.VERIFIED),
            },
        )
        dag.add_node(evidence_node)

        fact_node_id = f"FACT:{fact.fact_id}"
        fact_node = ProvenanceNode(
            node_id=fact_node_id,
            node_type=NodeType.BIDDER_FACT.value,
            label=f"BidderFact: dpiit = {fact.value}",
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
                "authority": response.issuer or "DPIIT",
                "txn_id": response.txn_id,
            },
        ))

        dag.validate()

    @staticmethod
    def to_adapter_response(
        response: DPIITVerificationResponse,
        expected_entity_name: Optional[str] = None,
    ) -> AdapterResponse:
        """
        Transforms DPIITVerificationResponse into standard AdapterResponse contract
        adhering to BaseGovernmentAdapter interface.
        """
        if response.status == DPIITVerificationStatus.VERIFIED:
            status = VerificationStatus.VERIFIED
            reason = f"DPIIT registration '{response.regn_no}' verified against DPIIT / Startup India via API Setu."
        elif response.status == DPIITVerificationStatus.NOT_VERIFIED:
            status = VerificationStatus.NOT_FOUND
            reason = f"DPIIT registration '{response.regn_no}' not found in Startup India records."
        elif response.status == DPIITVerificationStatus.INVALID_REQUEST:
            status = VerificationStatus.UNVERIFIED
            reason = f"Invalid DPIIT request: {response.error_message or 'Format or parameter error'}."
        else:
            status = VerificationStatus.REVIEW
            reason = f"DPIIT verification external error: {response.error_message or 'Gateway failure'}."

        reg_name = response.startup_name or ""

        # Identity cross-check
        if expected_entity_name and reg_name and status == VerificationStatus.VERIFIED:
            sim = difflib.SequenceMatcher(None, expected_entity_name.lower().strip(), reg_name.lower().strip()).ratio()
            if sim < 0.60 and not (expected_entity_name.lower() in reg_name.lower() or reg_name.lower() in expected_entity_name.lower()):
                status = VerificationStatus.IDENTITY_MISMATCH
                reason = (
                    f"DPIIT registration '{response.regn_no}' is registered to '{reg_name}', "
                    f"which does not match claimed entity '{expected_entity_name}' (similarity: {sim:.2f})."
                )

        return AdapterResponse(
            status=status,
            adapter_name="APISetuDPIITAdapter",
            queried_identifier=response.regn_no,
            source=response.issuer or "DPIIT",
            reason=reason,
            registered_entity_name=reg_name,
            registration_status="ACTIVE" if status == VerificationStatus.VERIFIED else "INACTIVE",
            matched_entity={
                "regn_no": response.regn_no,
                "startup_name": response.startup_name,
                "entity_type": response.entity_type,
                "incorporation_date": response.incorporation_date,
                "recognition_number": response.recognition_number,
                "recognition_date": response.recognition_date,
                "valid_upto": response.valid_upto,
                "industry": response.industry,
                "sector": response.sector,
                "state": response.state,
                "issuer": response.issuer,
            },
            evidence=[{
                "type": "API_SETU_SUIRC",
                "regn_no": response.regn_no,
                "txn_id": response.txn_id,
                "response_hash": response.response_hash,
                "xml_field_paths": response.xml_field_paths,
            }],
            is_mock=not response.is_live,
        )
