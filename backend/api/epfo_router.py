# -*- coding: utf-8 -*-
"""
FastAPI Router for API Setu / EPFO Verification.
Endpoints:
- GET  /api/v1/integrations/epfo/status
- POST /api/v1/integrations/epfo/verify/uan-card
- POST /api/v1/integrations/epfo/verify/scheme-certificate
- POST /api/v1/integrations/epfo/verify/pension-certificate
- GET  /api/v1/integrations/epfo/audit-logs

CRITICAL SCOPE NOTICE:
These endpoints perform EPFO DOCUMENT/CERTIFICATE VERIFICATION ONLY.
They do NOT perform general employer EPFO establishment compliance verification.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.integrations.epfo import (
    APISetuEPFOClient,
    APISetuEPFOEvidenceAdapter,
    EPFOEndpointType,
    EPFOVerificationConfig,
    EPFOVerificationResponse,
    EPFOVerificationStatus,
    PensionCertificateRequest,
    SchemeCertificateRequest,
    UANCardRequest,
    default_epfo_audit_logger,
    is_valid_dob_format,
    is_valid_ppono_format,
    is_valid_scno_format,
    is_valid_uan_format,
)

router = APIRouter(prefix="/api/v1/integrations/epfo", tags=["EPFO Verification"])


def get_epfo_client() -> APISetuEPFOClient:
    config = EPFOVerificationConfig.from_env()
    return APISetuEPFOClient(config=config, audit_logger=default_epfo_audit_logger)


class EPFOStatusResponse(BaseModel):
    enabled: bool
    configured: bool
    environment: str
    base_url: str
    uan_card_endpoint: str
    scheme_cert_endpoint: str
    pension_cert_endpoint: str
    client_id: str
    scope_notice: str


class UANCardAPIRequest(BaseModel):
    uan: str = Field(..., description="10-12 digit Universal Account Number (e.g. 1234567890)")
    dob: str = Field(..., description="Date of birth in DD-MM-YYYY format (e.g. 31-12-1980)")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier")
    expected_entity_name: Optional[str] = Field(None, description="Claimed member name for cross-check")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact")


class SchemeCertAPIRequest(BaseModel):
    scno: str = Field(..., description="Scheme Certificate Number (e.g. APSID00040466)")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier")
    expected_entity_name: Optional[str] = Field(None, description="Claimed beneficiary name for cross-check")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact")


class PensionCertAPIRequest(BaseModel):
    ppono: str = Field(..., description="Pension Payment Order Number (e.g. DLCPM00052882)")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier")
    expected_entity_name: Optional[str] = Field(None, description="Claimed pensioner name for cross-check")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact")


class EPFOVerificationAPIResponse(BaseModel):
    endpoint_type: str
    identifier: str
    txn_id: str
    status: str
    http_status: int
    format: str
    member_name: Optional[str] = None
    dob: Optional[str] = None
    certificate_number: Optional[str] = None
    pdf_size_bytes: Optional[int] = None
    response_hash: Optional[str] = None
    latency_ms: float = 0.0
    is_live: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    is_employer_compliance: bool = False
    scope_notice: str
    bidder_fact: Optional[Dict[str, Any]] = None
    adapter_response: Optional[Dict[str, Any]] = None


@router.get("/status", response_model=EPFOStatusResponse)
async def get_epfo_status(client: APISetuEPFOClient = Depends(get_epfo_client)):
    """
    Returns current configuration status of API Setu EPFO integration.
    Never exposes API key.
    """
    return EPFOStatusResponse(
        enabled=client.config.enabled,
        configured=client.config.is_configured(),
        environment=client.config.environment,
        base_url=client.config.base_url,
        uan_card_endpoint=client.config.uan_card_url,
        scheme_cert_endpoint=client.config.scheme_cert_url,
        pension_cert_endpoint=client.config.pension_cert_url,
        client_id=client.config.client_id,
        scope_notice="EPFO_DOCUMENT_CERTIFICATE_VERIFICATION_ONLY: Does not constitute comprehensive employer establishment compliance verification.",
    )


@router.post("/verify/uan-card", response_model=EPFOVerificationAPIResponse)
async def verify_uan_card(
    req: UANCardAPIRequest,
    client: APISetuEPFOClient = Depends(get_epfo_client),
):
    """
    Verifies UAN Card (PDF) against API Setu endpoint.
    """
    if not is_valid_uan_format(req.uan):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid UAN format '{req.uan}'. Expected 10-12 numeric digits.",
        )
    if not is_valid_dob_format(req.dob):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid DOB format '{req.dob}'. Expected DD-MM-YYYY.",
        )

    verify_req = UANCardRequest(uan=req.uan, dob=req.dob)
    resp = client.verify_uan_card(verify_req)

    bidder_fact_dict = None
    if resp.status == EPFOVerificationStatus.VERIFIED and req.convert_to_bidder_fact:
        fact = APISetuEPFOEvidenceAdapter.to_bidder_fact(resp, bid_id=req.bid_id or "API-EPFO-REQ")
        bidder_fact_dict = fact.to_dict()

    adapter_resp = APISetuEPFOEvidenceAdapter.to_adapter_response(resp, expected_entity_name=req.expected_entity_name)

    return EPFOVerificationAPIResponse(
        endpoint_type=resp.endpoint_type.value,
        identifier=resp.identifier,
        txn_id=resp.txn_id,
        status=resp.status.value,
        http_status=resp.http_status,
        format=resp.format,
        member_name=resp.member_name,
        dob=resp.dob,
        certificate_number=resp.certificate_number,
        pdf_size_bytes=resp.pdf_size_bytes,
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


@router.post("/verify/scheme-certificate", response_model=EPFOVerificationAPIResponse)
async def verify_scheme_certificate(
    req: SchemeCertAPIRequest,
    client: APISetuEPFOClient = Depends(get_epfo_client),
):
    """
    Verifies Scheme Certificate (XML) against API Setu endpoint.
    """
    if not is_valid_scno_format(req.scno):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Scheme Certificate number format '{req.scno}'.",
        )

    verify_req = SchemeCertificateRequest(scno=req.scno)
    resp = client.verify_scheme_certificate(verify_req)

    bidder_fact_dict = None
    if resp.status == EPFOVerificationStatus.VERIFIED and req.convert_to_bidder_fact:
        fact = APISetuEPFOEvidenceAdapter.to_bidder_fact(resp, bid_id=req.bid_id or "API-EPFO-REQ")
        bidder_fact_dict = fact.to_dict()

    adapter_resp = APISetuEPFOEvidenceAdapter.to_adapter_response(resp, expected_entity_name=req.expected_entity_name)

    return EPFOVerificationAPIResponse(
        endpoint_type=resp.endpoint_type.value,
        identifier=resp.identifier,
        txn_id=resp.txn_id,
        status=resp.status.value,
        http_status=resp.http_status,
        format=resp.format,
        member_name=resp.member_name,
        dob=resp.dob,
        certificate_number=resp.certificate_number,
        pdf_size_bytes=resp.pdf_size_bytes,
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


@router.post("/verify/pension-certificate", response_model=EPFOVerificationAPIResponse)
async def verify_pension_certificate(
    req: PensionCertAPIRequest,
    client: APISetuEPFOClient = Depends(get_epfo_client),
):
    """
    Verifies Pension Certificate (XML) against API Setu endpoint.
    """
    if not is_valid_ppono_format(req.ppono):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid PPO number format '{req.ppono}'.",
        )

    verify_req = PensionCertificateRequest(ppono=req.ppono)
    resp = client.verify_pension_certificate(verify_req)

    bidder_fact_dict = None
    if resp.status == EPFOVerificationStatus.VERIFIED and req.convert_to_bidder_fact:
        fact = APISetuEPFOEvidenceAdapter.to_bidder_fact(resp, bid_id=req.bid_id or "API-EPFO-REQ")
        bidder_fact_dict = fact.to_dict()

    adapter_resp = APISetuEPFOEvidenceAdapter.to_adapter_response(resp, expected_entity_name=req.expected_entity_name)

    return EPFOVerificationAPIResponse(
        endpoint_type=resp.endpoint_type.value,
        identifier=resp.identifier,
        txn_id=resp.txn_id,
        status=resp.status.value,
        http_status=resp.http_status,
        format=resp.format,
        member_name=resp.member_name,
        dob=resp.dob,
        certificate_number=resp.certificate_number,
        pdf_size_bytes=resp.pdf_size_bytes,
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
async def get_epfo_audit_logs(
    endpoint_type: Optional[str] = Query(None, description="Filter by UAN_CARD, SCHEME_CERTIFICATE, or PENSION_CERTIFICATE"),
    limit: int = Query(50, ge=1, le=1000),
    client: APISetuEPFOClient = Depends(get_epfo_client),
):
    """
    Returns sanitized in-memory audit logs for EPFO queries.
    API keys are hashed, identifiers masked.
    """
    events = client.audit_logger.get_events(endpoint_type=endpoint_type)
    return events[-limit:]
