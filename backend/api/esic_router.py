# -*- coding: utf-8 -*-
"""
FastAPI Router for API Setu / ESIC Verification.
Endpoints:
- GET  /api/v1/integrations/esic/status
- POST /api/v1/integrations/esic/verify/health-passbook
- POST /api/v1/integrations/esic/verify/pehchan-card
- GET  /api/v1/integrations/esic/audit-logs

CRITICAL SCOPE NOTICE:
These endpoints perform ESIC DOCUMENT/CERTIFICATE VERIFICATION ONLY.
They do NOT perform general employer establishment ESIC compliance verification.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.integrations.esic import (
    APISetuESICClient,
    APISetuESICEvidenceAdapter,
    ESICEndpointType,
    ESICHealthPassbookRequest,
    ESICPehchanCardRequest,
    ESICVerificationConfig,
    ESICVerificationResponse,
    ESICVerificationStatus,
    default_esic_audit_logger,
    is_valid_ip_number,
)

router = APIRouter(prefix="/api/v1/integrations/esic", tags=["ESIC Verification"])


def get_esic_client() -> APISetuESICClient:
    config = ESICVerificationConfig.from_env()
    return APISetuESICClient(config=config, audit_logger=default_esic_audit_logger)


class ESICStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    environment: str
    base_url: str
    health_passbook_endpoint: str
    pehchan_card_endpoint: str
    client_id: str
    scope_notice: str


class HealthPassbookAPIRequest(BaseModel):
    ip_number: str = Field(..., description="10-17 digit Insured Person (IP) Number (e.g. 1199900090)")
    relation: str = Field("Self", description="Relation (Self, Spouse, Dependant mother, etc.)")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier")
    expected_entity_name: Optional[str] = Field(None, description="Claimed insured person name for cross-check")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact")


class PehchanCardAPIRequest(BaseModel):
    ip_number: str = Field(..., description="10-17 digit Insured Person (IP) Number (e.g. 1199900090)")
    employer_name: str = Field("Name", description="Employer name")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier")
    expected_entity_name: Optional[str] = Field(None, description="Claimed employer name for cross-check")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact")


class ESICVerificationAPIResponse(BaseModel):
    endpoint_type: str
    ip_number: str
    txn_id: str
    status: str
    http_status: int
    format: str
    insured_person_name: Optional[str] = None
    employer_name: Optional[str] = None
    dispensary: Optional[str] = None
    date_of_registration: Optional[str] = None
    relation: Optional[str] = None
    certificate_number: Optional[str] = None
    response_hash: Optional[str] = None
    latency_ms: float = 0.0
    is_live: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    is_employer_compliance: bool = False
    scope_notice: str
    bidder_fact: Optional[Dict[str, Any]] = None
    adapter_response: Optional[Dict[str, Any]] = None


@router.get("/status", response_model=ESICStatusResponse)
async def get_esic_status(client: APISetuESICClient = Depends(get_esic_client)):
    """
    Returns current configuration status of API Setu ESIC integration.
    Never exposes API key.
    """
    return ESICStatusResponse(
        enabled=client.config.enabled,
        configured=client.config.is_configured(),
        environment=client.config.environment,
        base_url=client.config.base_url,
        health_passbook_endpoint=client.config.health_passbook_url,
        pehchan_card_endpoint=client.config.pehchan_card_url,
        client_id=client.config.client_id,
        scope_notice="ESIC_DOCUMENT_CERTIFICATE_VERIFICATION_ONLY: Verifies supplied Health Passbook / Pehchan Card record; does not independently establish complete employer ESIC compliance.",
    )


@router.post("/verify/health-passbook", response_model=ESICVerificationAPIResponse)
async def verify_health_passbook(
    req: HealthPassbookAPIRequest,
    client: APISetuESICClient = Depends(get_esic_client),
):
    """
    Verifies ESIC Health Passbook against API Setu endpoint.
    """
    if not is_valid_ip_number(req.ip_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ESIC IP number format '{req.ip_number}'. Expected 10-17 digits.",
        )

    verify_req = ESICHealthPassbookRequest(ip_number=req.ip_number, relation=req.relation)
    resp = client.verify_health_passbook(verify_req)

    bidder_fact_dict = None
    if resp.status == ESICVerificationStatus.VERIFIED and req.convert_to_bidder_fact:
        fact = APISetuESICEvidenceAdapter.to_bidder_fact(resp, bid_id=req.bid_id or "API-ESIC-REQ")
        bidder_fact_dict = fact.to_dict()

    adapter_resp = APISetuESICEvidenceAdapter.to_adapter_response(resp, expected_entity_name=req.expected_entity_name)

    return ESICVerificationAPIResponse(
        endpoint_type=resp.endpoint_type.value,
        ip_number=resp.ip_number,
        txn_id=resp.txn_id,
        status=resp.status.value,
        http_status=resp.http_status,
        format=resp.format,
        insured_person_name=resp.insured_person_name,
        employer_name=resp.employer_name,
        dispensary=resp.dispensary,
        date_of_registration=resp.date_of_registration,
        relation=resp.relation,
        certificate_number=resp.certificate_number,
        response_hash=resp.response_hash,
        latency_ms=resp.latency_ms or 0.0,
        is_live=resp.is_live,
        error_code=resp.error_code,
        error_message=resp.error_message,
        is_employer_compliance=resp.is_employer_compliance,
        scope_notice=resp.scope_notice,
        bidder_fact=bidder_fact_dict,
        adapter_response=adapter_resp.to_dict(),
    )


@router.post("/verify/pehchan-card", response_model=ESICVerificationAPIResponse)
async def verify_pehchan_card(
    req: PehchanCardAPIRequest,
    client: APISetuESICClient = Depends(get_esic_client),
):
    """
    Verifies ESIC Pehchan Card against API Setu endpoint.
    """
    if not is_valid_ip_number(req.ip_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ESIC IP number format '{req.ip_number}'. Expected 10-17 digits.",
        )

    verify_req = ESICPehchanCardRequest(ip_number=req.ip_number, employer_name=req.employer_name)
    resp = client.verify_pehchan_card(verify_req)

    bidder_fact_dict = None
    if resp.status == ESICVerificationStatus.VERIFIED and req.convert_to_bidder_fact:
        fact = APISetuESICEvidenceAdapter.to_bidder_fact(resp, bid_id=req.bid_id or "API-ESIC-REQ")
        bidder_fact_dict = fact.to_dict()

    adapter_resp = APISetuESICEvidenceAdapter.to_adapter_response(resp, expected_entity_name=req.expected_entity_name)

    return ESICVerificationAPIResponse(
        endpoint_type=resp.endpoint_type.value,
        ip_number=resp.ip_number,
        txn_id=resp.txn_id,
        status=resp.status.value,
        http_status=resp.http_status,
        format=resp.format,
        insured_person_name=resp.insured_person_name,
        employer_name=resp.employer_name,
        dispensary=resp.dispensary,
        date_of_registration=resp.date_of_registration,
        relation=resp.relation,
        certificate_number=resp.certificate_number,
        response_hash=resp.response_hash,
        latency_ms=resp.latency_ms or 0.0,
        is_live=resp.is_live,
        error_code=resp.error_code,
        error_message=resp.error_message,
        is_employer_compliance=resp.is_employer_compliance,
        scope_notice=resp.scope_notice,
        bidder_fact=bidder_fact_dict,
        adapter_response=adapter_resp.to_dict(),
    )


@router.get("/audit-logs", response_model=List[Dict[str, Any]])
async def get_esic_audit_logs(
    endpoint_type: Optional[str] = Query(None, description="Filter by HEALTH_PASSBOOK or PEHCHAN_CARD"),
    limit: int = Query(50, ge=1, le=1000),
    client: APISetuESICClient = Depends(get_esic_client),
):
    """
    Returns sanitized in-memory audit logs for ESIC queries.
    API keys are hashed, IP numbers masked.
    """
    events = client.audit_logger.get_events(endpoint_type=endpoint_type)
    return events[-limit:]
