# -*- coding: utf-8 -*-
"""
FastAPI Router for API Setu / DPIIT Startup India Recognition Certificate Verification.
Endpoints:
- GET  /api/v1/integrations/dpiit/status
- POST /api/v1/integrations/dpiit/verify
- GET  /api/v1/integrations/dpiit/audit-logs
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.integrations.dpiit import (
    APISetuDPIITClient,
    APISetuDPIITEvidenceAdapter,
    DPIITVerificationConfig,
    DPIITVerificationRequest,
    DPIITVerificationStatus,
    default_dpiit_audit_logger,
    is_valid_dpiit_regn,
)

router = APIRouter(prefix="/api/v1/integrations/dpiit", tags=["DPIIT Verification"])


def get_dpiit_client() -> APISetuDPIITClient:
    config = DPIITVerificationConfig.from_env()
    return APISetuDPIITClient(config=config, audit_logger=default_dpiit_audit_logger)


class DPIITStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    environment: str
    base_url: str
    endpoint: str
    client_id: str


class DPIITVerificationAPIRequest(BaseModel):
    regn_no: str = Field(..., description="DPIIT / DIPP Registration Number (e.g. DIPP12345 or DIPPXXXX)")
    mobile_number: str = Field("9807654321", description="Registered mobile number")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier")
    expected_entity_name: Optional[str] = Field(None, description="Claimed startup name for cross-check")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact")


class DPIITVerificationAPIResponse(BaseModel):
    txn_id: str
    status: str
    http_status: int
    regn_no: str
    startup_name: Optional[str] = None
    entity_type: Optional[str] = None
    incorporation_date: Optional[str] = None
    recognition_number: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    state: Optional[str] = None
    issuer: Optional[str] = None
    response_hash: Optional[str] = None
    latency_ms: float = 0.0
    is_live: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    bidder_fact: Optional[Dict[str, Any]] = None
    adapter_response: Optional[Dict[str, Any]] = None


@router.get("/status", response_model=DPIITStatusResponse)
async def get_dpiit_status(client: APISetuDPIITClient = Depends(get_dpiit_client)):
    """
    Returns current configuration status of API Setu DPIIT integration.
    Never exposes API key.
    """
    return DPIITStatusResponse(
        enabled=client.config.enabled,
        configured=client.config.is_configured(),
        environment=client.config.environment,
        base_url=client.config.base_url,
        endpoint=client.config.endpoint_url,
        client_id=client.config.client_id,
    )


@router.post("/verify", response_model=DPIITVerificationAPIResponse)
async def verify_dpiit_recognition(
    req: DPIITVerificationAPIRequest,
    client: APISetuDPIITClient = Depends(get_dpiit_client),
):
    """
    Verifies DPIIT Recognition Certificate against API Setu endpoint.
    Deterministic gating: non-verified/error states never produce authoritative BidderFacts.
    """
    if not is_valid_dpiit_regn(req.regn_no):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid DPIIT registration number format '{req.regn_no}'.",
        )

    verify_req = DPIITVerificationRequest(
        regn_no=req.regn_no,
        mobile_number=req.mobile_number,
    )

    resp = client.verify_recognition_certificate(verify_req)

    bidder_fact_dict = None
    if resp.status == DPIITVerificationStatus.VERIFIED and req.convert_to_bidder_fact:
        bid_id = req.bid_id or "API-DPIIT-REQ"
        fact = APISetuDPIITEvidenceAdapter.to_bidder_fact(resp, bid_id=bid_id)
        bidder_fact_dict = fact.to_dict()

    adapter_resp = APISetuDPIITEvidenceAdapter.to_adapter_response(
        resp,
        expected_entity_name=req.expected_entity_name,
    )

    return DPIITVerificationAPIResponse(
        txn_id=resp.txn_id,
        status=resp.status.value,
        http_status=resp.http_status,
        regn_no=resp.regn_no,
        startup_name=resp.startup_name,
        entity_type=resp.entity_type,
        incorporation_date=resp.incorporation_date,
        recognition_number=resp.recognition_number,
        industry=resp.industry,
        sector=resp.sector,
        state=resp.state,
        issuer=resp.issuer,
        response_hash=resp.response_hash,
        latency_ms=resp.latency_ms or 0.0,
        is_live=resp.is_live,
        error_code=resp.error_code,
        error_message=resp.error_message,
        bidder_fact=bidder_fact_dict,
        adapter_response=adapter_resp.to_dict(),
    )


@router.get("/audit-logs", response_model=List[Dict[str, Any]])
async def get_dpiit_audit_logs(
    limit: int = Query(50, ge=1, le=1000),
    client: APISetuDPIITClient = Depends(get_dpiit_client),
):
    """
    Returns sanitized in-memory audit logs for DPIIT queries.
    API keys are hashed, registration/mobile numbers masked.
    """
    events = client.audit_logger.get_events()
    return events[-limit:]
