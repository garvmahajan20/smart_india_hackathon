# -*- coding: utf-8 -*-
"""
Mock Registry Evidence & Provenance Adapter.
Transforms authoritative mock registry responses (ITD, MCA21, NSIC, OEM, MII) into:
- EvidenceReference (source_type="INTERNAL_MOCK_REGISTRY", [0,0,0,0] bbox)
- BidderFact (strongly-typed facts consumed by rule and contradiction engines)
- ProvenanceDAG (strict acyclic graph linking mock registry evidence to facts)

Critical Governance Invariants:
1. Failed, not found, or inactive responses MUST NOT manufacture positive BidderFacts.
2. Only VERIFIED status produces authoritative BidderFacts.
3. Provenance DAG nodes explicitly record source_type="INTERNAL_MOCK_REGISTRY" and dataset_version="MOCK_REGISTRY_DATASET_V1".
"""

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
from .models import AdapterResponse, VerificationStatus


class MockRegistryEvidenceAdapter:
    """
    Transforms AdapterResponse from mock registries into deterministic pipeline artifacts.
    """

    @staticmethod
    def to_evidence_reference(response: AdapterResponse) -> EvidenceReference:
        """
        Creates EvidenceReference pointing to the mock government registry record.
        Uses [0.0, 0.0, 0.0, 0.0] bounding box convention for registry evidence.
        """
        doc_id = f"{response.source}:{response.queried_identifier}"
        snippet = (
            f"[{response.source}] Identifier: {response.queried_identifier} | "
            f"Status: {response.status.value} | Reason: {response.reason}"
        )
        return EvidenceReference(
            document=doc_id,
            page=1,
            bbox=[0.0, 0.0, 0.0, 0.0],
            snippet=snippet,
            extraction_method="INTERNAL_MOCK_REGISTRY_LOOKUP",
            extraction_confidence="HIGH" if response.status == VerificationStatus.VERIFIED else "LOW",
            block_id=f"BLOCK:{response.source}:{response.queried_identifier}",
        )

    @staticmethod
    def to_bidder_facts(
        response: AdapterResponse,
        bid_id: str,
        fact_id_prefix: Optional[str] = None,
    ) -> List[BidderFact]:
        """
        Transforms verified mock response into authoritative BidderFacts.
        CRITICAL INVARIANT: Returns EMPTY list on non-verified or error outcomes.
        """
        if response.status != VerificationStatus.VERIFIED or not response.matched_entity:
            return []

        ent = response.matched_entity
        ev_ref = MockRegistryEvidenceAdapter.to_evidence_reference(response)
        prefix = fact_id_prefix or f"FACT-{response.source}"
        facts: List[BidderFact] = []

        base_meta = {
            "source_type": "INTERNAL_MOCK_REGISTRY",
            "dataset_version": "MOCK_REGISTRY_DATASET_V1",
            "registry": response.source,
            "queried_identifier": response.queried_identifier,
            "is_mock": True,
        }

        evidence_item = {
            "block_id": ev_ref.block_id,
            "document": ev_ref.document,
            "page": 1,
            "bbox": [0.0, 0.0, 0.0, 0.0],
            "snippet": ev_ref.snippet,
            "source_type": "INTERNAL_MOCK_REGISTRY",
        }

        # -------------------------------------------------------------
        # A. MOCK_ITD Facts
        # -------------------------------------------------------------
        if response.source == "MOCK_ITD":
            pan = ent.get("pan", response.queried_identifier)
            facts.append(BidderFact(
                fact_id=f"{prefix}-ITR-STATUS-{pan}",
                bid_id=bid_id,
                field="itr_filing_status",
                value="FILED",
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_ITD_REGISTRY",
                canonical_field="ITR_FILING_STATUS",
                raw_text_snippet=f"ITR Filing Status: FILED (AY: {ent.get('assessment_year')})",
                metadata={**base_meta, "assessment_year": ent.get("assessment_year"), "ack_number": ent.get("ack_number")},
                evidence=[evidence_item],
            ))
            if ent.get("ack_number"):
                facts.append(BidderFact(
                    fact_id=f"{prefix}-ITR-ACK-{pan}",
                    bid_id=bid_id,
                    field="itr_ack_number",
                    value=ent.get("ack_number"),
                    source_document=ev_ref.document,
                    page=1,
                    extraction_confidence="HIGH",
                    extraction_method="MOCK_ITD_REGISTRY",
                    canonical_field="ITR_ACKNOWLEDGEMENT",
                    raw_text_snippet=f"ITR Ack: {ent.get('ack_number')}",
                    metadata=base_meta,
                    evidence=[evidence_item],
                ))
            if ent.get("turnover_cr") is not None:
                facts.append(BidderFact(
                    fact_id=f"{prefix}-TURNOVER-{pan}",
                    bid_id=bid_id,
                    field="turnover_cr",
                    value=float(ent.get("turnover_cr")),
                    source_document=ev_ref.document,
                    page=1,
                    extraction_confidence="HIGH",
                    extraction_method="MOCK_ITD_REGISTRY",
                    canonical_field="ANNUAL_TURNOVER",
                    raw_text_snippet=f"Turnover: {ent.get('turnover_cr')} Cr",
                    metadata={**base_meta, "currency": "INR", "unit": "CRORE"},
                    evidence=[evidence_item],
                ))

        # -------------------------------------------------------------
        # B. MOCK_MCA21 Facts
        # -------------------------------------------------------------
        elif response.source == "MOCK_MCA21":
            cin = ent.get("cin", response.queried_identifier)
            cname = ent.get("company_name", "")
            facts.append(BidderFact(
                fact_id=f"{prefix}-CIN-{cin}",
                bid_id=bid_id,
                field="cin",
                value=cin,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_MCA21_REGISTRY",
                canonical_field="CIN",
                raw_text_snippet=f"CIN: {cin}",
                metadata=base_meta,
                evidence=[evidence_item],
            ))
            if cname:
                facts.append(BidderFact(
                    fact_id=f"{prefix}-LEGAL-NAME-{cin}",
                    bid_id=bid_id,
                    field="legal_name",
                    value=cname,
                    source_document=ev_ref.document,
                    page=1,
                    extraction_confidence="HIGH",
                    extraction_method="MOCK_MCA21_REGISTRY",
                    canonical_field="LEGAL_ENTITY_NAME",
                    raw_text_snippet=f"Company Name: {cname}",
                    metadata=base_meta,
                    evidence=[evidence_item],
                ))
            facts.append(BidderFact(
                fact_id=f"{prefix}-STATUS-{cin}",
                bid_id=bid_id,
                field="mca_status",
                value="ACTIVE",
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_MCA21_REGISTRY",
                canonical_field="REGULATORY_STATUS",
                raw_text_snippet="MCA Status: ACTIVE",
                metadata=base_meta,
                evidence=[evidence_item],
            ))

        # -------------------------------------------------------------
        # C. MOCK_NSIC Facts
        # -------------------------------------------------------------
        elif response.source == "MOCK_NSIC":
            cnum = ent.get("certificate_number", response.queried_identifier)
            facts.append(BidderFact(
                fact_id=f"{prefix}-CERT-{cnum}",
                bid_id=bid_id,
                field="nsic_registration",
                value=cnum,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_NSIC_REGISTRY",
                canonical_field="NSIC_REGISTRATION",
                raw_text_snippet=f"NSIC Certificate: {cnum}",
                metadata=base_meta,
                evidence=[evidence_item],
            ))
            facts.append(BidderFact(
                fact_id=f"{prefix}-IS-MSE-{cnum}",
                bid_id=bid_id,
                field="is_mse",
                value=True,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_NSIC_REGISTRY",
                canonical_field="IS_MSE",
                raw_text_snippet=f"MSE Registered via NSIC ({ent.get('category', 'MSE')})",
                metadata={**base_meta, "category": ent.get("category")},
                evidence=[evidence_item],
            ))

        # -------------------------------------------------------------
        # D. MOCK_OEM Facts
        # -------------------------------------------------------------
        elif response.source == "MOCK_OEM":
            auth_num = ent.get("auth_number", response.queried_identifier)
            oem = ent.get("oem_name", "")
            facts.append(BidderFact(
                fact_id=f"{prefix}-AUTH-{auth_num}",
                bid_id=bid_id,
                field="oem_authorization",
                value=auth_num,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_OEM_REGISTRY",
                canonical_field="OEM_AUTHORIZATION",
                raw_text_snippet=f"OEM Authorization: {auth_num} (OEM: {oem})",
                metadata={**base_meta, "oem_name": oem, "product_category": ent.get("product_category")},
                evidence=[evidence_item],
            ))
            facts.append(BidderFact(
                fact_id=f"{prefix}-AUTHORIZED-{auth_num}",
                bid_id=bid_id,
                field="oem_authorized",
                value=True,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_OEM_REGISTRY",
                canonical_field="OEM_VERIFIED_STATUS",
                raw_text_snippet=f"Authorized Reseller for {oem}",
                metadata=base_meta,
                evidence=[evidence_item],
            ))

        # -------------------------------------------------------------
        # E. MOCK_MII Facts
        # -------------------------------------------------------------
        elif response.source == "MOCK_MII":
            decl_id = ent.get("declaration_id", response.queried_identifier)
            lc_pct = float(ent.get("local_content_percentage", 0.0))
            facts.append(BidderFact(
                fact_id=f"{prefix}-PERCENT-{decl_id}",
                bid_id=bid_id,
                field="local_content_percent",
                value=lc_pct,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_MII_REGISTRY",
                canonical_field="LOCAL_CONTENT_PERCENT",
                raw_text_snippet=f"Local Content: {lc_pct}%",
                metadata={**base_meta, "declaration_id": decl_id, "supplier_class": ent.get("supplier_class")},
                evidence=[evidence_item],
            ))
            facts.append(BidderFact(
                fact_id=f"{prefix}-DECL-{decl_id}",
                bid_id=bid_id,
                field="mii_declaration",
                value=decl_id,
                source_document=ev_ref.document,
                page=1,
                extraction_confidence="HIGH",
                extraction_method="MOCK_MII_REGISTRY",
                canonical_field="MII_DECLARATION",
                raw_text_snippet=f"MII Declaration: {decl_id}",
                metadata=base_meta,
                evidence=[evidence_item],
            ))

        return facts

    @staticmethod
    def integrate_with_dag(
        dag: ProvenanceDAG,
        facts: List[BidderFact],
        response: AdapterResponse,
    ) -> None:
        """
        Integrates mock registry facts into ProvenanceDAG with strict acyclicity.
        Connects:
          MOCK_REGISTRY -> Identifier -> BidderFact
        """
        if not facts:
            return

        evidence_node_id = f"BLOCK:{response.source}:{response.queried_identifier}"
        evidence_node = ProvenanceNode(
            node_id=evidence_node_id,
            node_type=NodeType.PHYSICAL_TEXT_BLOCK.value,
            label=f"{response.source} Record ({response.queried_identifier})",
            properties={
                "document": f"{response.source}:{response.queried_identifier}",
                "page": 1,
                "source_type": "INTERNAL_MOCK_REGISTRY",
                "dataset_version": "MOCK_REGISTRY_DATASET_V1",
                "registry": response.source,
                "status": response.status.value,
                "is_mock": True,
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
                    "source": response.source,
                    "is_mock": True,
                },
            )
            dag.add_node(fact_node)

            edge_id = make_edge_id(fact_node_id, EdgeType.FACT_GROUNDED_BY.value, evidence_node_id)
            dag.add_edge(ProvenanceEdge(
                edge_id=edge_id,
                source_id=fact_node_id,
                edge_type=EdgeType.FACT_GROUNDED_BY.value,
                target_id=evidence_node_id,
                properties={"registry": response.source, "identifier": response.queried_identifier},
            ))

        dag.validate()
