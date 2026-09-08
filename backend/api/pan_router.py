# -*- coding: utf-8 -*-
"""
FastAPI Router for API Setu / Income Tax Department PAN Verification.
Endpoints:
- GET  /api/v1/integrations/pan/status
- POST /api/v1/integrations/pan/verify
- GET  /api/v1/integrations/pan/audit-logs
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.integrations.pan import (
    APISetuPANClient,
    APISetuPANEvidenceAdapter,
    PANVerificationConfig,
    PANVerificationRequest,
    PANVerificationStatus,
    default_pan_audit_logger,
    is_valid_pan_format,
)

router = APIRouter(prefix="/api/v1/integrations/pan", tags=["PAN Verification"])


def get_pan_client() -> APISetuPANClient:
    config = PANVerificationConfig.from_env()
    return APISetuPANClient(config=config, audit_logger=default_pan_audit_logger)


# ----------------------------------------------------------------------
# Request & Response Schemas
# ----------------------------------------------------------------------
class PANStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    environment: str
    base_url: str
    endpoint: str
    client_id: str


class PANVerificationAPIRequest(BaseModel):
    pan: str = Field(..., description="10-character Permanent Account Number (e.g., ABCDE1234F)")
    full_name: Optional[str] = Field(None, description="Optional cardholder / entity name for cross-check")
    dob: Optional[str] = Field(None, description="Date of birth / incorporation in DD-MM-YYYY format")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier to bind extracted BidderFact")
    expected_entity_name: Optional[str] = Field(None, description="Bidder company name for identity matching")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact")


class PANVerificationAPIResponse(BaseModel):
    txn_id: str
    status: str
    http_status: int
    pan: str
    verified_name: Optional[str] = None
    verified_dob: Optional[str] = None
    issuer: Optional[str] = None
    certificate_type: Optional[str] = None
    certificate_number: Optional[str] = None
    verified_on: Optional[str] = None
    response_hash: Optional[str] = None
    latency_ms: float = 0.0
    is_live: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    bidder_fact: Optional[Dict[str, Any]] = None
    adapter_response: Optional[Dict[str, Any]] = None


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@router.get("/status", response_model=PANStatusResponse)
async def get_pan_status(client: APISetuPANClient = Depends(get_pan_client)):
    """
    Returns current status and mode of API Setu PAN Verification integration.
    Never exposes API key.
    """
    cfg = client.config
    return PANStatusResponse(
        enabled=cfg.enabled,
        configured=cfg.is_configured(),
        environment=cfg.environment,
        base_url=cfg.base_url,
        endpoint=cfg.endpoint_path,
        client_id=cfg.client_id,
    )


@router.post("/verify", response_model=PANVerificationAPIResponse)
async def verify_pan(
    request: PANVerificationAPIRequest,
    client: APISetuPANClient = Depends(get_pan_client),
):
    """
    Executes real PAN verification against official API Setu / Income Tax Department sandbox.
    Returns normalized verification evidence and optional BidderFact mapping.
    """
    clean_pan = request.pan.strip().upper()
    if not is_valid_pan_format(clean_pan):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PAN syntax format: '{clean_pan}'. Must be 5 letters, 4 digits, 1 letter.",
        )

    req_obj = PANVerificationRequest(
        pan=clean_pan,
        full_name=request.full_name,
        dob=request.dob,
    )

    resp = client.verify_pan(req_obj)

    bidder_fact_dict = None
    adapter_resp_dict = None

    if resp.status == PANVerificationStatus.VERIFIED and request.convert_to_bidder_fact:
        bid_id = request.bid_id or "BID-PAN-PULLED"
        fact = APISetuPANEvidenceAdapter.to_bidder_fact(resp, bid_id=bid_id)
        bidder_fact_dict = fact.to_dict()

    if request.expected_entity_name or resp.status == PANVerificationStatus.VERIFIED:
        adapter_res = APISetuPANEvidenceAdapter.to_adapter_response(
            response=resp,
            expected_entity_name=request.expected_entity_name,
        )
        adapter_resp_dict = adapter_res.to_dict()

    res_dict = resp.to_dict(include_raw=False)
    res_dict["bidder_fact"] = bidder_fact_dict
    res_dict["adapter_response"] = adapter_resp_dict

    return PANVerificationAPIResponse(**res_dict)


@router.get("/audit-logs")
async def get_pan_audit_logs(
    event_type: Optional[str] = Query(None),
):
    """
    Retrieves sanitized audit trail for PAN verification queries.
    Enforces strict zero secret leakage.
    """
    events = default_pan_audit_logger.get_events(event_type=event_type)
    return {"count": len(events), "events": events}
