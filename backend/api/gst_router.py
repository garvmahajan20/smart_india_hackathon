# -*- coding: utf-8 -*-
"""
FastAPI Router for GSTINAPI GST Verification & Return History.
Endpoints:
- GET  /api/v1/integrations/gst/status
- POST /api/v1/integrations/gst/verify
- GET  /api/v1/integrations/gst/{gstin}/returns
- GET  /api/v1/integrations/gst/{gstin}/compliance
- GET  /api/v1/integrations/gst/audit-logs
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.integrations.gst import (
    GSTINAPIClient,
    GSTINAPIConfig,
    GSTINAPIEvidenceAdapter,
    GSTVerificationRequest,
    GSTVerificationStatus,
    default_gst_audit_logger,
    is_valid_gstin_format,
)

router = APIRouter(prefix="/api/v1/integrations/gst", tags=["GST Verification (GSTINAPI)"])


def get_gst_client() -> GSTINAPIClient:
    config = GSTINAPIConfig.from_env()
    return GSTINAPIClient(config=config, audit_logger=default_gst_audit_logger)


# ----------------------------------------------------------------------
# Request & Response Schemas
# ----------------------------------------------------------------------
class GSTStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    environment: str
    base_url: str
    api_key_configured: bool
    masked_key: str


class GSTVerificationAPIRequest(BaseModel):
    gstin: str = Field(..., description="15-character GSTIN (e.g., 27AABCU9603R1ZM)")
    include_profile: bool = Field(True, description="Enrich response with taxpayer profile")
    check_returns: bool = Field(False, description="Fetch filing return history")
    fy: Optional[str] = Field(None, description="Financial year for returns/compliance (e.g. 2024-25)")
    expected_entity_name: Optional[str] = Field(None, description="Bidder company name for identity cross-check")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier to bind extracted BidderFacts")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFacts")


class GSTVerificationAPIResponse(BaseModel):
    txn_id: str
    status: str
    http_status: int
    gstin: str
    data: Optional[Dict[str, Any]] = None
    returns: Optional[List[Dict[str, Any]]] = None
    filing_preference: Optional[List[Dict[str, Any]]] = None
    compliance: Optional[Dict[str, Any]] = None
    fy: Optional[str] = None
    response_hash: Optional[str] = None
    latency_ms: float = 0.0
    is_live: bool = True
    is_test: bool = False
    credits_remaining: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    bidder_facts: Optional[List[Dict[str, Any]]] = None
    adapter_response: Optional[Dict[str, Any]] = None


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@router.get("/status", response_model=GSTStatusResponse)
async def get_gst_status(client: GSTINAPIClient = Depends(get_gst_client)):
    """
    Returns current status and mode of GSTINAPI integration.
    Never exposes API key.
    """
    cfg = client.config
    key = cfg.api_key or ""
    masked = (key[:4] + "..." + key[-4:]) if len(key) >= 8 else ("****" if key else "NOT_CONFIGURED")
    return GSTStatusResponse(
        enabled=cfg.enabled,
        configured=cfg.is_configured(),
        environment=cfg.environment,
        base_url=cfg.base_url,
        api_key_configured=bool(cfg.api_key),
        masked_key=masked,
    )


@router.post("/verify", response_model=GSTVerificationAPIResponse)
async def verify_gst(
    request: GSTVerificationAPIRequest,
    client: GSTINAPIClient = Depends(get_gst_client),
):
    """
    Executes GSTIN verification and optional returns check against GSTINAPI.
    Applies pre-flight regex validation to avoid wasted billable requests.
    Returns normalized verification evidence and optional BidderFacts mapping.
    """
    clean_gstin = request.gstin.strip().upper()
    if not is_valid_gstin_format(clean_gstin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid GSTIN format: '{clean_gstin}'. Must match 15-character statutory format.",
        )

    resp = client.verify_gstin(
        gstin=clean_gstin,
        include_profile=request.include_profile,
        check_returns=request.check_returns,
        fy=request.fy,
    )

    facts_dict_list = None
    if resp.status == GSTVerificationStatus.VERIFIED and request.convert_to_bidder_fact:
        bid_id = request.bid_id or "BID-GST-VERIFIED"
        facts = GSTINAPIEvidenceAdapter.to_bidder_facts(resp, bid_id=bid_id)
        facts_dict_list = [f.to_dict() for f in facts]

    adapter_resp = GSTINAPIEvidenceAdapter.to_adapter_response(
        response=resp,
        expected_entity_name=request.expected_entity_name,
    )

    res_dict = resp.to_dict()
    res_dict["bidder_facts"] = facts_dict_list
    res_dict["adapter_response"] = adapter_resp.to_dict()

    return GSTVerificationAPIResponse(**res_dict)


@router.get("/{gstin}/returns")
async def get_gst_returns(
    gstin: str,
    fy: str = Query("2024-25", description="Financial year (YYYY-YY)"),
    client: GSTINAPIClient = Depends(get_gst_client),
):
    """
    Fetches return filing history for the specified GSTIN and financial year.
    """
    clean_gstin = gstin.strip().upper()
    if not is_valid_gstin_format(clean_gstin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid GSTIN format: '{clean_gstin}'. Must match 15-character statutory format.",
        )

    records = client.get_returns(clean_gstin, fy=fy)
    return {
        "gstin": clean_gstin,
        "fy": fy,
        "total_records": len(records),
        "returns": [r.to_dict() for r in records],
    }


@router.get("/{gstin}/compliance")
async def get_gst_compliance(
    gstin: str,
    fy: str = Query("2024-25", description="Financial year (YYYY-YY)"),
    client: GSTINAPIClient = Depends(get_gst_client),
):
    """
    Fetches filing compliance summary (GSTR-1, GSTR-3B filings count) for the given FY.
    """
    clean_gstin = gstin.strip().upper()
    if not is_valid_gstin_format(clean_gstin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid GSTIN format: '{clean_gstin}'. Must match 15-character statutory format.",
        )

    summary = client.get_compliance(clean_gstin, fy=fy)
    return {
        "gstin": clean_gstin,
        "fy": fy,
        "compliance": summary.to_dict() if summary else None,
    }


@router.get("/audit-logs")
async def get_gst_audit_logs(
    event_type: Optional[str] = Query(None),
):
    """
    Retrieves sanitized audit trail for GSTINAPI queries.
    Strictly scrubbed of secret keys and identifiers.
    """
    events = default_gst_audit_logger.get_events(event_type=event_type)
    return {"count": len(events), "events": events}
