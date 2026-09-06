# -*- coding: utf-8 -*-
"""
FastAPI Router for API Setu / MSME Udyam Certificate Verification.
Endpoints:
- GET  /api/v1/integrations/udyam/status
- POST /api/v1/integrations/udyam/verify
- GET  /api/v1/integrations/udyam/audit-logs
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.integrations.udyam import (
    APISetuUdyamClient,
    APISetuUdyamEvidenceAdapter,
    UdyamVerificationConfig,
    UdyamVerificationRequest,
    UdyamVerificationStatus,
    default_udyam_audit_logger,
    is_valid_udyam_format,
)

router = APIRouter(prefix="/api/v1/integrations/udyam", tags=["Udyam Verification"])


def get_udyam_client() -> APISetuUdyamClient:
    config = UdyamVerificationConfig.from_env()
    return APISetuUdyamClient(config=config, audit_logger=default_udyam_audit_logger)


class UdyamStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    environment: str
    base_url: str
    endpoint: str
    client_id: str


class UdyamVerificationAPIRequest(BaseModel):
    udyam_number: str = Field(..., description="Udyam Registration Number (e.g. UDYAM-MH-01-0088776)")
    mobile_number: str = Field("9874563210", description="Linked mobile number")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier to bind extracted BidderFact")
    expected_entity_name: Optional[str] = Field(None, description="Bidder company name for identity cross-check")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact")


class UdyamVerificationAPIResponse(BaseModel):
    txn_id: str
    status: str
    http_status: int
    udyam_number: str
    enterprise_name: Optional[str] = None
    enterprise_type: Optional[str] = None
    major_activity: Optional[str] = None
    date_of_commencement: Optional[str] = None
    social_category: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    issuer: Optional[str] = None
    response_hash: Optional[str] = None
    latency_ms: float = 0.0
    is_live: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    bidder_fact: Optional[Dict[str, Any]] = None
    adapter_response: Optional[Dict[str, Any]] = None


@router.get("/status", response_model=UdyamStatusResponse)
async def get_udyam_status(client: APISetuUdyamClient = Depends(get_udyam_client)):
    """
    Returns current status and mode of API Setu Udyam Verification integration.
    Never exposes API key.
    """
    return UdyamStatusResponse(
        enabled=client.config.enabled,
        configured=client.config.is_configured(),
        environment=client.config.environment,
        base_url=client.config.base_url,
        endpoint=client.config.endpoint_url,
        client_id=client.config.client_id,
    )


@router.post("/verify", response_model=UdyamVerificationAPIResponse)
async def verify_udyam_record(
    req: UdyamVerificationAPIRequest,
    client: APISetuUdyamClient = Depends(get_udyam_client),
):
    """
    Verifies Udyam Certificate against API Setu sandbox endpoint.
    Deterministic gating: non-verified/error states never produce authoritative BidderFacts.
    """
    if not is_valid_udyam_format(req.udyam_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Udyam number format '{req.udyam_number}'. Expected format: UDYAM-XX-00-0000000.",
        )

    verify_req = UdyamVerificationRequest(
        udyam_number=req.udyam_number,
        mobile_number=req.mobile_number,
    )

    resp = client.verify_udyam(verify_req)

    bidder_fact_dict = None
    adapter_resp_dict = None

    if resp.status == UdyamVerificationStatus.VERIFIED and req.convert_to_bidder_fact:
        bid_id = req.bid_id or "API-MANUAL-REQ"
        fact = APISetuUdyamEvidenceAdapter.to_bidder_fact(resp, bid_id=bid_id)
        bidder_fact_dict = fact.to_dict()

    adapter_resp = APISetuUdyamEvidenceAdapter.to_adapter_response(
        resp,
        expected_entity_name=req.expected_entity_name,
    )
    adapter_resp_dict = adapter_resp.to_dict()

    return UdyamVerificationAPIResponse(
        txn_id=resp.txn_id,
        status=resp.status.value,
        http_status=resp.http_status,
        udyam_number=resp.udyam_number,
        enterprise_name=resp.enterprise_name,
        enterprise_type=resp.enterprise_type,
        major_activity=resp.major_activity,
        date_of_commencement=resp.date_of_commencement,
        social_category=resp.social_category,
        state=resp.state,
        district=resp.district,
        issuer=resp.issuer,
        response_hash=resp.response_hash,
        latency_ms=resp.latency_ms or 0.0,
        is_live=resp.is_live,
        error_code=resp.error_code,
        error_message=resp.error_message,
        bidder_fact=bidder_fact_dict,
        adapter_response=adapter_resp_dict,
    )


@router.get("/audit-logs", response_model=List[Dict[str, Any]])
async def get_udyam_audit_logs(
    limit: int = Query(50, ge=1, le=1000),
    client: APISetuUdyamClient = Depends(get_udyam_client),
):
    """
    Returns sanitized in-memory audit logs for Udyam queries.
    API keys are hashed, Udyam/mobile numbers masked.
    """
    events = client.audit_logger.get_events()
    return events[-limit:]
