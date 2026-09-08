# -*- coding: utf-8 -*-
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from backend.core.contradiction_engine import CrossDocumentContradictionEngine
from backend.core.models import BidderFact, TenderRequirement, VerificationResult
from backend.core.rule_engine import DeterministicRuleEngine
from backend.extraction.cache import LLMCache
from backend.extraction.fact_extractor import LLMBidderFactExtractor
from backend.extraction.gemini_provider import GeminiProvider
from backend.extraction.mock_provider import MockLLMProvider
from backend.extraction.models import LLMMode
from backend.extraction.provider import BaseLLMProvider
from backend.extraction.requirement_extractor import TenderRequirementExtractor
from backend.extraction.schema_validator import SchemaValidator
from backend.ingestion.pipeline import DocumentIngestionPipeline
from backend.verification.base import BaseGovernmentAdapter
from backend.verification.mock_debarment import MockDebarmentAdapter
from backend.verification.mock_gst import MockGSTAdapter
from backend.verification.mock_pan import MockPANAdapter
from backend.verification.mock_udyam import MockUdyamAdapter
from backend.verification.models import AdapterResponse, IntegrityFinding
from .aggregator import VerificationAggregator
from .models import AggregatedVerification, VerificationDossier

class VerificationOrchestrator:
    """
    Central End-to-End Verification Orchestrator.
    Coordinates document ingestion, requirement extraction, fact extraction,
    compliance verification, contradiction detection, government adapters,
    aggregation, human review routing, and dossier generation.
    """

    def __init__(
        self,
        mode: Union[LLMMode, str] = LLMMode.MOCK,
        provider: Optional[BaseLLMProvider] = None,
        cache_dir: str = "data/cache/verifications",
        llm_cache_dir: str = "data/cache/llm",
        gst_adapter: Optional[BaseGovernmentAdapter] = None,
    ):
        if isinstance(mode, str):
            mode = LLMMode(mode.upper())
        self.mode = mode
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

        self.llm_cache = LLMCache(cache_dir=llm_cache_dir)
        self.validator = SchemaValidator()

        # Provider initialization
        if provider:
            self.provider = provider
        elif self.mode == LLMMode.LIVE:
            self.provider = GeminiProvider()
        else:
            self.provider = MockLLMProvider()

        # Internal Pipelines & Engines
        self.ingestion = DocumentIngestionPipeline()
        self.requirement_extractor = TenderRequirementExtractor(
            provider=self.provider,
            cache=self.llm_cache,
            mode=self.mode,
            schema_validator=self.validator,
        )
        self.fact_extractor = LLMBidderFactExtractor(
            provider=self.provider,
            cache=self.llm_cache,
            mode=self.mode,
            schema_validator=self.validator,
        )
        self.rule_engine = DeterministicRuleEngine()
        self.contradiction_engine = CrossDocumentContradictionEngine()
        self.aggregator = VerificationAggregator()

        # Government Adapters (Mock by default, pluggable)
        self.gst_adapter = gst_adapter or MockGSTAdapter()
        self.pan_adapter = MockPANAdapter()
        self.udyam_adapter = MockUdyamAdapter()
        self.debarment_adapter = MockDebarmentAdapter()

        # In-memory session store
        self._verifications: Dict[str, AggregatedVerification] = {}
        self._dossiers: Dict[str, VerificationDossier] = {}

    def verify_submission(
        self,
        tender_document_path: str,
        bid_document_paths: List[str],
        tender_id: Optional[str] = None,
        bid_id: Optional[str] = None,
        company_name_hint: Optional[str] = None,
    ) -> Tuple[AggregatedVerification, VerificationDossier]:
        """
        Executes complete verification pipeline for a tender document and bid documents.
        """
        t0 = time.perf_counter()

        # 1. Infer Identifiers if not provided
        t_base = os.path.basename(tender_document_path)
        b_base = os.path.basename(bid_document_paths[0]) if bid_document_paths else "BID-UNKNOWN"
        tender_id = tender_id or (t_base.split(".")[0] if "TENDER" in t_base else "TENDER-0001")
        bid_id = bid_id or (b_base.split(".")[0] if "BID" in b_base else "BID-00001")

        # 2. Ingestion & Requirement Extraction (Tender)
        t_ingest_res = self.ingestion.ingest_file(tender_document_path)
        if t_ingest_res.overall_method.value == "FAILED" or len(t_ingest_res.pages) == 0:
            raise ValueError(f"Invalid or unreadable tender document '{tender_document_path}': {t_ingest_res.errors}")

        requirements = self.requirement_extractor.extract_requirements(t_ingest_res)

        # 3. Ingestion & Fact Extraction (Bid Documents)
        all_facts: List[BidderFact] = []
        grounding_warnings: List[str] = []

        for b_path in bid_document_paths:
            b_ingest_res = self.ingestion.ingest_file(b_path)
            if b_ingest_res.overall_method.value == "FAILED" or len(b_ingest_res.pages) == 0:
                raise ValueError(f"Invalid or unreadable bidder document '{b_path}': {b_ingest_res.errors}")
            facts = self.fact_extractor.extract_facts(b_ingest_res, bid_id=bid_id)
            all_facts.extend(facts)

        # 4. Step 4: Deterministic Compliance Rule Verification
        compliance_results = self.rule_engine.verify_bid(requirements, all_facts)

        # 5. Step 5: Cross-Document Contradiction & Integrity Verification
        integrity_findings = self.contradiction_engine.detect_contradictions_in_bid(bid_id, all_facts)

        # 6. Government Registry Verification
        # Extract legal name, GSTIN, PAN, Udyam from facts or hints
        facts_by_field = {f.field.lower(): f.value for f in all_facts if f.field}
        facts_by_canonical = {f.canonical_field: f.value for f in all_facts if f.canonical_field}
        legal_name = company_name_hint or facts_by_field.get("company_name", facts_by_field.get("entity_name")) or facts_by_canonical.get("LEGAL_ENTITY_NAME")
        gstin_val = facts_by_field.get("gstin") or facts_by_canonical.get("GSTIN")
        pan_val = facts_by_field.get("pan") or facts_by_canonical.get("PAN")
        udyam_val = (
            facts_by_field.get("udyam")
            or facts_by_field.get("udyam_registration")
            or facts_by_canonical.get("UDYAM_REGISTRATION")
        )

        # Derive PAN from GSTIN if PAN not submitted directly (chars 3-12 of 15-char GSTIN)
        if not pan_val and gstin_val and len(str(gstin_val)) == 15:
            pan_val = str(gstin_val)[2:12]

        gov_responses: List[AdapterResponse] = []

        if gstin_val:
            gov_responses.append(self.gst_adapter.verify(str(gstin_val), expected_name=str(legal_name) if legal_name else None))

        if pan_val:
            gov_responses.append(self.pan_adapter.verify(str(pan_val), expected_name=str(legal_name) if legal_name else None))

        if udyam_val:
            gov_responses.append(self.udyam_adapter.verify(str(udyam_val), expected_name=str(legal_name) if legal_name else None))

        # Debarment Check (check PAN, GSTIN, and legal name)
        debar_val = pan_val or gstin_val or legal_name
        if debar_val:
            gov_responses.append(self.debarment_adapter.verify(str(debar_val)))

        # 7. Aggregation & Decision Logic
        total_time_ms = (time.perf_counter() - t0) * 1000.0
        extraction_meta = {
            "mode": self.mode.value if hasattr(self.mode, 'value') else str(self.mode),
            "model": self.provider.model_name,
            "latency_ms": total_time_ms,
        }

        aggregated = self.aggregator.aggregate(
            tender_id=tender_id,
            bid_id=bid_id,
            compliance_results=compliance_results,
            integrity_findings=integrity_findings,
            government_responses=gov_responses,
            grounding_warnings=grounding_warnings,
            extraction_metadata=extraction_meta,
            requirements=requirements,
            facts=all_facts,
        )

        # 8. Compile Verification Dossier
        dossier = self._generate_dossier(
            tender_id=tender_id,
            bid_id=bid_id,
            legal_name=legal_name,
            requirements=requirements,
            facts=all_facts,
            compliance_results=compliance_results,
            integrity_findings=integrity_findings,
            aggregated=aggregated,
            total_time_ms=total_time_ms,
        )

        # Cache results
        self._verifications[aggregated.verification_id] = aggregated
        self._dossiers[aggregated.verification_id] = dossier

        # Save to disk cache
        self._save_to_disk(aggregated, dossier)

        return aggregated, dossier

    def get_verification(self, verification_id: str) -> Optional[AggregatedVerification]:
        if verification_id in self._verifications:
            return self._verifications[verification_id]
        return self._load_from_disk(verification_id)

    def get_dossier(self, verification_id: str) -> Optional[VerificationDossier]:
        if verification_id in self._dossiers:
            return self._dossiers[verification_id]
        verif = self.get_verification(verification_id)
        if verif and verification_id in self._dossiers:
            return self._dossiers[verification_id]
        return None

    def _generate_dossier(
        self,
        tender_id: str,
        bid_id: str,
        legal_name: Optional[Any],
        requirements: List[TenderRequirement],
        facts: List[BidderFact],
        compliance_results: List[VerificationResult],
        integrity_findings: List[IntegrityFinding],
        aggregated: AggregatedVerification,
        total_time_ms: float,
    ) -> VerificationDossier:
        evidence_list = []
        for f in facts:
            ev_item = {
                "fact_id": f.fact_id,
                "field": f.field,
                "value": f.value,
                "normalized_value": f.normalized_value,
                "unit": f.unit,
                "document": f.source_document,
                "page": f.page,
                "bbox": f.bbox,
                "snippet": f.raw_text_snippet,
                "confidence": f.extraction_confidence,
            }
            if getattr(f, "evidence", None):
                ev_item["evidence"] = f.evidence
                ev_item["bboxes"] = [e["bbox"] for e in f.evidence if e.get("bbox")]
            evidence_list.append(ev_item)

        # Construct deterministic provenance DAG
        from backend.core.provenance_dag import ProvenanceDAGBuilder
        dag = ProvenanceDAGBuilder.build(
            requirements=requirements,
            facts=facts,
            results=compliance_results,
            integrity_findings=integrity_findings,
            human_review_items=aggregated.human_review_items,
            adjudications=getattr(aggregated, "adjudications", None),
            bid_id=bid_id,
            tender_id=tender_id,
        )

        return VerificationDossier(
            tender={
                "tender_id": tender_id,
                "requirements_count": len(requirements),
                "requirements": [r.to_dict() for r in requirements],
            },
            bidder={
                "bid_id": bid_id,
                "legal_name": str(legal_name) if legal_name else "UNKNOWN",
                "extracted_facts_count": len(facts),
                "facts": [f.to_dict() for f in facts],
            },
            compliance_summary={
                "compliance_status": aggregated.compliance_status,
                "overall_status": aggregated.overall_status,
                "critical_failures": aggregated.critical_failures,
                "major_failures": aggregated.major_failures,
                "total_requirements": len(requirements),
            },
            integrity_summary={
                "integrity_status": aggregated.integrity_status,
                "contradictions_count": len(aggregated.contradictions),
                "anomalies_count": aggregated.anomaly_count,
            },
            verification_results=aggregated.verification_results,
            government_checks=aggregated.government_checks,
            evidence=evidence_list,
            anomalies=aggregated.contradictions,
            human_review_items=aggregated.human_review_items,
            audit_metadata={
                "verification_id": aggregated.verification_id,
                "deterministic_run_id": aggregated.deterministic_run_id,
                "generated_at": aggregated.generated_at,
                "processing_time_ms": total_time_ms,
                "active_model": self.provider.model_name,
                "extraction_mode": self.mode.value if hasattr(self.mode, 'value') else str(self.mode),
            },
            provenance_graph=dag.to_dict(),
            compliance_score=aggregated.compliance_score_breakdown,
            risk_assessment=aggregated.risk_assessment,
            recommendation=aggregated.recommendation,
            pending_requirements=aggregated.pending_requirements,
            adjudications=getattr(aggregated, "adjudications", []),
        )

    def _save_to_disk(self, aggregated: AggregatedVerification, dossier: VerificationDossier) -> None:
        try:
            verif_file = os.path.join(self.cache_dir, f"{aggregated.verification_id}.json")
            with open(verif_file, "w", encoding="utf-8") as f:
                json.dump({
                    "verification": aggregated.to_dict(),
                    "dossier": dossier.to_dict()
                }, f, indent=2)
        except Exception:
            pass

    def _load_from_disk(self, verification_id: str) -> Optional[AggregatedVerification]:
        try:
            verif_file = os.path.join(self.cache_dir, f"{verification_id}.json")
            if os.path.exists(verif_file):
                with open(verif_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                verif = AggregatedVerification.from_dict(data["verification"])
                dossier = VerificationDossier.from_dict(data["dossier"])
                self._verifications[verification_id] = verif
                self._dossiers[verification_id] = dossier
                return verif
        except Exception:
            pass
        return None

    def adjudicate(
        self,
        verification_id: str,
        request: Any,
    ) -> Tuple[AggregatedVerification, VerificationDossier, Any]:
        """
        Applies a procurement officer adjudication / override to an existing verification.
        Deterministically recalculates compliance score, risk assessment, and recommendation,
        updates provenance DAG, appends to immutable audit trail, and persists to cache.
        """
        from backend.core.adjudication import ProcurementOfficerAdjudicationEngine

        aggregated = self.get_verification(verification_id)
        if not aggregated:
            raise KeyError(f"Verification '{verification_id}' not found.")

        dossier = self.get_dossier(verification_id)
        if not dossier:
            raise KeyError(f"Dossier for verification '{verification_id}' not found.")

        updated_agg, updated_dos, record = ProcurementOfficerAdjudicationEngine.apply_adjudication(
            aggregated=aggregated,
            dossier=dossier,
            request=request,
        )

        # Update session store and disk cache
        self._verifications[verification_id] = updated_agg
        self._dossiers[verification_id] = updated_dos
        self._save_to_disk(updated_agg, updated_dos)

        return updated_agg, updated_dos, record

    def get_audit_trail(self, verification_id: str) -> Dict[str, Any]:
        """
        Retrieves the complete audit trail and adjudication records for a verification.
        """
        aggregated = self.get_verification(verification_id)
        if not aggregated:
            raise KeyError(f"Verification '{verification_id}' not found.")
        dossier = self.get_dossier(verification_id)

        adjudications = getattr(aggregated, "adjudications", [])
        return {
            "verification_id": verification_id,
            "deterministic_run_id": aggregated.deterministic_run_id,
            "tender_id": aggregated.tender_id,
            "bid_id": aggregated.bid_id,
            "generated_at": aggregated.generated_at,
            "adjudications_count": len(adjudications),
            "adjudications": adjudications,
            "human_review_items": aggregated.human_review_items,
            "provenance_node_count": len(dossier.provenance_graph.get("nodes", [])) if (dossier and dossier.provenance_graph) else 0,
            "provenance_edge_count": len(dossier.provenance_graph.get("edges", [])) if (dossier and dossier.provenance_graph) else 0,
        }

    def replay_verification(self, verification_id: str) -> Dict[str, Any]:
        """
        Performs an independent deterministic replay verification against the verification state
        using DeterministicReplayEngine, verifying zero-drift reproducibility.
        """
        from backend.core.replay_engine import DeterministicReplayEngine
        from backend.core.snapshot import SnapshotBuilder

        aggregated = self.get_verification(verification_id)
        if not aggregated:
            raise KeyError(f"Verification '{verification_id}' not found.")
        dossier = self.get_dossier(verification_id)
        if not dossier:
            raise KeyError(f"Dossier for verification '{verification_id}' not found.")

        # Reconstruct requirements and facts from dossier
        from backend.core.models import TenderRequirement, BidderFact, VerificationResult
        reqs = [TenderRequirement.from_dict(r) if isinstance(r, dict) else r for r in dossier.tender.get("requirements", [])]
        facts = [BidderFact.from_dict(f) if isinstance(f, dict) else f for f in dossier.bidder.get("facts", [])]
        results = [VerificationResult.from_dict(r) if isinstance(r, dict) else r for r in dossier.verification_results]

        snapshot = SnapshotBuilder.build(
            tender_id=aggregated.tender_id,
            bid_id=aggregated.bid_id,
            requirements=reqs,
            facts=facts,
            compliance_results=results,
            human_review_items=aggregated.human_review_items,
            aggregated_status={
                "compliance_status": aggregated.compliance_status,
                "integrity_status": aggregated.integrity_status,
                "overall_status": aggregated.overall_status,
                "critical_failures": aggregated.critical_failures,
                "major_failures": aggregated.major_failures,
                "anomaly_count": aggregated.anomaly_count,
                "review_required": aggregated.review_required,
            },
            provenance_graph=dossier.provenance_graph,
        )

        replay_engine = DeterministicReplayEngine()
        replay_result = replay_engine.replay(snapshot)
        return replay_result.to_dict(include_transient_metrics=True)

