# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = "HEALTHY"
    version: str = "1.0.0"
    active_model: str
    mode: str

class HumanReviewItemResponse(BaseModel):
    review_id: str
    bid_id: str
    tender_id: str
    category: str
    severity: str
    reason: str
    evidence_references: List[Dict[str, Any]] = []
    source_documents: List[str] = []
    source_pages: List[int] = []
    related_verification_id: Optional[str] = None
    created_at: str
    status: str

class AggregatedVerificationResponse(BaseModel):
    verification_id: str
    tender_id: str
    bid_id: str
    overall_status: str
    compliance_status: str
    integrity_status: str
    verification_results: List[Dict[str, Any]] = []
    critical_failures: int = 0
    major_failures: int = 0
    review_required: bool = False
    evidence_count: int = 0
    anomaly_count: int = 0
    government_checks: List[Dict[str, Any]] = []
    contradictions: List[Dict[str, Any]] = []
    human_review_items: List[Dict[str, Any]] = []
    generated_at: str
    deterministic_run_id: str
    processing_metadata: Dict[str, Any] = {}
    compliance_score: float = 0.0
    compliance_score_breakdown: Dict[str, Any] = {}
    risk_level: str = "LOW"
    risk_assessment: Dict[str, Any] = {}
    recommendation: Dict[str, Any] = {}
    pending_requirements: List[Dict[str, Any]] = []

class VerificationDossierResponse(BaseModel):
    tender: Dict[str, Any]
    bidder: Dict[str, Any]
    compliance_summary: Dict[str, Any]
    integrity_summary: Dict[str, Any]
    verification_results: List[Dict[str, Any]]
    government_checks: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    human_review_items: List[Dict[str, Any]]
    audit_metadata: Dict[str, Any]
    provenance_graph: Optional[Dict[str, Any]] = None
    compliance_score: Optional[Dict[str, Any]] = None
    risk_assessment: Optional[Dict[str, Any]] = None
    recommendation: Optional[Dict[str, Any]] = None
    pending_requirements: List[Dict[str, Any]] = []

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
