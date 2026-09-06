# -*- coding: utf-8 -*-
"""
DigiLocker Evidence & Verification Adapter.
Bridges pulled government artifacts (PDFs & XML certificates) into:
- EvidenceReference (grounding with source_type="DIGILOCKER")
- BidderFact (strongly typed parameters for deterministic evaluation)
- AdapterResponse (conforming to BaseGovernmentAdapter interface)
- ProvenanceDAG (strict acyclic evidence tracing)
"""

import hashlib
from typing import Any, Dict, List, Optional

from backend.core.models import BidderFact
from backend.core.provenance_dag import (
    EdgeType,
    NodeType,
    ProvenanceDAG,
    ProvenanceEdge,
    ProvenanceNode,
    make_block_node_id,
    make_edge_id,
)
from backend.ingestion.models import EvidenceReference
from backend.verification.models import AdapterResponse, VerificationStatus
from .models import DigiLockerParsedCertificate, DigiLockerPulledDocument


# Field mapping dictionary: DigiLocker Certificate Type -> Domain fields
FIELD_MAPPINGS = {
    "UDYAM": {
        "field": "msme_registration_number",
        "canonical_field": "MSME_REGISTRATION",
        "label": "Udyam MSME Registration Certificate",
    },
    "GST": {
        "field": "gstin",
        "canonical_field": "GSTIN",
        "label": "Goods and Services Tax Registration",
    },
    "PAN": {
        "field": "pan",
        "canonical_field": "PAN",
        "label": "Permanent Account Number",
    },
    "INCORPORATION": {
        "field": "certificate_of_incorporation",
        "canonical_field": "INCORPORATION_CERTIFICATE",
        "label": "MCA Certificate of Incorporation",
    },
    "EXPERIENCE": {
        "field": "past_experience_certificate",
        "canonical_field": "EXPERIENCE_CRITERIA",
        "label": "Past Performance / Experience Certificate",
    },
    "COMPLETION": {
        "field": "contract_completion_certificate",
        "canonical_field": "WORK_COMPLETION_CERTIFICATE",
        "label": "Work Delivery & Completion Certificate",
    },
}


class DigiLockerEvidenceAdapter:
    """
    Transforms authoritative DigiLocker artifacts into deterministic pipeline inputs.
    """

    @staticmethod
    def certificate_to_evidence_reference(
        cert: DigiLockerParsedCertificate,
        doc_id: Optional[str] = None,
    ) -> EvidenceReference:
        """
        Creates an EvidenceReference pointing to the official DigiLocker certificate.
        Does NOT invent fake physical bounding boxes: uses authoritative digital evidence indicator.
        """
        identifier = doc_id or cert.certificate_number or "DIGILOCKER_CERT"
        snippet = (
            f"[DIGILOCKER_AUTHORITATIVE_REGISTRY] Type: {cert.certificate_type} | "
            f"Number: {cert.certificate_number} | Issuer: {cert.issuer_name} | "
            f"Recipient: {cert.recipient_name} | Status: {cert.status}"
        )
        return EvidenceReference(
            document=f"DIGILOCKER:{cert.certificate_type}:{cert.certificate_number}",
            page=1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            snippet=snippet,
            extraction_method="DIGILOCKER_AUTHORITATIVE_API",
            extraction_confidence="HIGH",
            block_id=f"BLOCK:DIGILOCKER:{identifier}",
        )

    @staticmethod
    def certificate_to_bidder_fact(
        cert: DigiLockerParsedCertificate,
        bid_id: str,
        fact_id_prefix: str = "FACT-DL",
    ) -> BidderFact:
        """
        Extracts a canonical BidderFact from a parsed DigiLocker certificate.
        """
        mapping = FIELD_MAPPINGS.get(cert.certificate_type.upper(), {
            "field": f"{cert.certificate_type.lower()}_certificate",
            "canonical_field": cert.certificate_type.upper(),
            "label": cert.certificate_name,
        })

        ev_ref = DigiLockerEvidenceAdapter.certificate_to_evidence_reference(cert)
        clean_num = cert.certificate_number.strip()
        fact_id = f"{fact_id_prefix}-{cert.certificate_type}-{clean_num.replace('/', '_')}"

        metadata = {
            "source": "DIGILOCKER_SANDBOX",
            "certificate_name": cert.certificate_name,
            "certificate_type": cert.certificate_type,
            "certificate_number": cert.certificate_number,
            "issuer_name": cert.issuer_name,
            "issuer_code": cert.issuer_code,
            "issue_date": cert.issue_date,
            "valid_from": cert.valid_from,
            "expiry_date": cert.expiry_date,
            "status": cert.status,
            "recipient_name": cert.recipient_name,
            "recipient_uid": cert.recipient_uid,
            "recipient_organization": cert.recipient_organization,
            "certificate_data": cert.certificate_data,
        }

        # Build evidence item adhering to bidder_fact.schema.json
        evidence_dict = {
            "block_id": ev_ref.block_id,
            "document": ev_ref.document,
            "page": 1,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "snippet": ev_ref.snippet,
            "source_type": "DIGILOCKER_OFFICIAL_REGISTRY",
        }

        return BidderFact(
            fact_id=fact_id,
            bid_id=bid_id,
            field=mapping["field"],
            value=cert.certificate_number,
            source_document=ev_ref.document,
            page=1,
            extraction_confidence="HIGH",
            extraction_method="DIGILOCKER_AUTHORITATIVE",
            canonical_field=mapping["canonical_field"],
            raw_text_snippet=ev_ref.snippet,
            metadata=metadata,
            evidence=[evidence_dict],
            field_resolution={
                "raw_field": mapping["field"],
                "canonical_field_id": mapping["canonical_field"],
                "label": mapping["label"],
                "category": "STATUTORY_COMPLIANCE",
                "resolution_method": "DIGILOCKER_REGISTRY_MAPPING",
                "resolution_status": "RESOLVED",
                "contradiction_eligible": True,
                "family": "GOVERNMENT_REGISTRY",
            },
        )

    @staticmethod
    def integrate_with_dag(
        dag: ProvenanceDAG,
        fact: BidderFact,
        cert: DigiLockerParsedCertificate,
    ) -> None:
        """
        Safely registers the DigiLocker evidence and fact into an existing ProvenanceDAG.
        Uses standard NodeType and EdgeType to maintain strict graph invariants and zero cycles.
        """
        # 1. Register Physical Evidence Node (External Authority Document)
        doc_sha = hashlib.sha256((cert.raw_xml or cert.certificate_number).encode("utf-8")).hexdigest()
        evidence_node_id = f"BLOCK:DIGILOCKER:{cert.certificate_type}:{cert.certificate_number}"
        
        evidence_node = ProvenanceNode(
            node_id=evidence_node_id,
            node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
            label=f"DigiLocker {cert.certificate_name} ({cert.certificate_number})",
            properties={
                "document": f"DIGILOCKER:{cert.certificate_type}:{cert.certificate_number}",
                "page": 1,
                "source_type": "DIGILOCKER_SANDBOX",
                "issuer": cert.issuer_name,
                "recipient": cert.recipient_name,
                "status": cert.status,
                "sha256": doc_sha,
                "verified_by_authority": True,
            },
        )
        dag.add_node(evidence_node)

        # 2. Register Bidder Fact Node
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
                "source": "DIGILOCKER_SANDBOX",
            },
        )
        dag.add_node(fact_node)

        # 3. Add Edge: Fact is Grounded By External Authority Block
        edge_id = make_edge_id(fact_node_id, EdgeType.FACT_GROUNDED_BY.value, evidence_node_id)
        dag.add_edge(ProvenanceEdge(
            edge_id=edge_id,
            source_id=fact_node_id,
            edge_type=EdgeType.FACT_GROUNDED_BY.value,
            target_id=evidence_node_id,
            properties={"authority": cert.issuer_name},
        ))

        # Validate graph invariants
        dag.validate()

    @staticmethod
    def to_adapter_response(
        cert: DigiLockerParsedCertificate,
        queried_identifier: str,
        expected_entity_name: Optional[str] = None,
    ) -> AdapterResponse:
        """
        Creates an AdapterResponse adhering to BaseGovernmentAdapter verification contract.
        """
        is_active = (cert.status == "A")
        entity_name = cert.recipient_name or cert.recipient_organization or ""

        status = VerificationStatus.VERIFIED if is_active else VerificationStatus.INACTIVE
        reason = f"Official certificate retrieved from DigiLocker sandbox (Status: {cert.status})."

        # Identity cross-check
        if expected_entity_name and entity_name:
            import difflib
            sim = difflib.SequenceMatcher(None, expected_entity_name.lower().strip(), entity_name.lower().strip()).ratio()
            if sim < 0.60:
                status = VerificationStatus.IDENTITY_MISMATCH
                reason = (
                    f"Entity mismatch: expected '{expected_entity_name}', "
                    f"DigiLocker certificate issued to '{entity_name}' (similarity: {sim:.2f})."
                )

        return AdapterResponse(
            status=status,
            adapter_name="DigiLockerSandboxAdapter",
            queried_identifier=queried_identifier,
            source=cert.issuer_name or "DigiLocker / API Setu Sandbox",
            reason=reason,
            registered_entity_name=entity_name,
            registration_status=cert.status,
            matched_entity={
                "certificate_type": cert.certificate_type,
                "certificate_number": cert.certificate_number,
                "issuer": cert.issuer_name,
                "recipient": entity_name,
                "issue_date": cert.issue_date,
                "valid_from": cert.valid_from,
                "expiry_date": cert.expiry_date,
                "certificate_data": cert.certificate_data,
            },
            evidence=[{
                "type": "DIGILOCKER_XML_CERTIFICATE",
                "certificate_number": cert.certificate_number,
                "issuer": cert.issuer_name,
            }],
            is_mock=False,
        )
