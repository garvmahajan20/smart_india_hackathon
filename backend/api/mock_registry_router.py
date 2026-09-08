# -*- coding: utf-8 -*-
"""
FastAPI Router for Deterministic Government Mock Registries.
Source Type: INTERNAL_MOCK_REGISTRY
Dataset Version: MOCK_REGISTRY_DATASET_V1

Registries supported:
- Income Tax / ITR (MOCK_ITD)
- MCA21 Corporate Registry (MOCK_MCA21)
- NSIC Small Industries Registry (MOCK_NSIC)
- OEM Authorization Registry (MOCK_OEM)
- Make in India / Local Content Registry (MOCK_MII)
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.verification import (
    MockGovernmentRegistry,
    MockITDAdapter,
    MockMCA21Adapter,
    MockNSICAdapter,
    MockOEMAdapter,
    MockMIIAdapter,
    MockRegistryEvidenceAdapter,
    VerificationStatus,
)

router = APIRouter(prefix="/api/v1/integrations/mock", tags=["Government Mock Registries"])


# ----------------------------------------------------------------------
# Request & Response Schemas
# ----------------------------------------------------------------------
class MockRegistriesStatusResponse(BaseModel):
    source_type: str = Field("INTERNAL_MOCK_REGISTRY", description="Always INTERNAL_MOCK_REGISTRY")
    dataset_version: str = Field("MOCK_REGISTRY_DATASET_V1", description="Synthetic dataset version")
    is_live_government_portal: bool = Field(False, description="Strictly False - deterministic mock")
    registries: Dict[str, Dict[str, Any]]


class MockVerifyRequest(BaseModel):
    identifier: str = Field(..., description="Unique certificate, ack, CIN, PAN, or auth number to query")
    expected_entity_name: Optional[str] = Field(None, description="Expected bidder company name for identity matching")
    bid_id: Optional[str] = Field(None, description="Optional bid identifier to bind generated BidderFacts")
    convert_to_bidder_fact: bool = Field(False, description="Whether to transform verified record into BidderFact objects")
    extra_params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional query parameters (e.g. oem_name, product_name)")


class MockVerifyResponse(BaseModel):
    status: str
    adapter_name: str
    queried_identifier: str
    source: str
    source_type: str = "INTERNAL_MOCK_REGISTRY"
    dataset_version: str = "MOCK_REGISTRY_DATASET_V1"
    reason: str
    matched_entity: Optional[Dict[str, Any]] = None
    registered_entity_name: Optional[str] = None
    registration_status: Optional[str] = None
    evidence: List[Dict[str, Any]] = []
    is_mock: bool = True
    bidder_facts: Optional[List[Dict[str, Any]]] = None


# ----------------------------------------------------------------------
# Helper
# ----------------------------------------------------------------------
def _execute_adapter_verification(
    adapter: Any,
    req: MockVerifyRequest,
) -> MockVerifyResponse:
    extra = req.extra_params or {}
    resp = adapter.verify(
        identifier=req.identifier,
        expected_entity_name=req.expected_entity_name,
        **extra,
    )
    facts_data = None
    if req.convert_to_bidder_fact and req.bid_id:
        facts = MockRegistryEvidenceAdapter.to_bidder_facts(resp, bid_id=req.bid_id)
        facts_data = [f.to_dict() for f in facts]

    return MockVerifyResponse(
        status=resp.status.value if hasattr(resp.status, "value") else str(resp.status),
        adapter_name=resp.adapter_name,
        queried_identifier=resp.queried_identifier,
        source=resp.source,
        source_type="INTERNAL_MOCK_REGISTRY",
        dataset_version=MockGovernmentRegistry.DATASET_VERSION,
        reason=resp.reason,
        matched_entity=resp.matched_entity,
        registered_entity_name=resp.registered_entity_name,
        registration_status=resp.registration_status,
        evidence=resp.evidence,
        is_mock=True,
        bidder_facts=facts_data,
    )


# ----------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------
@router.get("/status", response_model=MockRegistriesStatusResponse)
def get_mock_registries_status() -> MockRegistriesStatusResponse:
    """
    Returns inventory and status of all internal deterministic mock government registries.
    Explicitly discloses source_type='INTERNAL_MOCK_REGISTRY'.
    """
    reg = MockGovernmentRegistry.get_instance()
    return MockRegistriesStatusResponse(
        source_type=reg.SOURCE_TYPE,
        dataset_version=reg.DATASET_VERSION,
        is_live_government_portal=False,
        registries={
            "MOCK_ITD": {
                "name": "Income Tax Department (ITR)",
                "adapter": "MockITDAdapter",
                "primary_keys": ["pan", "ack_number"],
                "records_count": len(reg.itd_records),
            },
            "MOCK_MCA21": {
                "name": "Ministry of Corporate Affairs (MCA21)",
                "adapter": "MockMCA21Adapter",
                "primary_keys": ["cin"],
                "records_count": len(reg.mca_records),
            },
            "MOCK_NSIC": {
                "name": "National Small Industries Corporation (NSIC)",
                "adapter": "MockNSICAdapter",
                "primary_keys": ["certificate_number"],
                "records_count": len(reg.nsic_records),
            },
            "MOCK_OEM": {
                "name": "OEM Authorization Registry",
                "adapter": "MockOEMAdapter",
                "primary_keys": ["authorization_number", "oem_name:bidder_name"],
                "records_count": len(reg.oem_records),
            },
            "MOCK_MII": {
                "name": "Make in India / Local Content Registry",
                "adapter": "MockMIIAdapter",
                "primary_keys": ["declaration_id", "manufacturer:product"],
                "records_count": len(reg.mii_records),
            },
        },
    )


@router.post("/itd/verify", response_model=MockVerifyResponse)
def verify_itd_record(req: MockVerifyRequest) -> MockVerifyResponse:
    """Queries synthetic Income Tax Return (ITR) registry."""
    adapter = MockITDAdapter()
    return _execute_adapter_verification(adapter, req)


@router.post("/mca21/verify", response_model=MockVerifyResponse)
def verify_mca21_record(req: MockVerifyRequest) -> MockVerifyResponse:
    """Queries synthetic MCA21 Corporate Registry by CIN."""
    adapter = MockMCA21Adapter()
    return _execute_adapter_verification(adapter, req)


@router.post("/nsic/verify", response_model=MockVerifyResponse)
def verify_nsic_record(req: MockVerifyRequest) -> MockVerifyResponse:
    """Queries synthetic NSIC Certificate Registry."""
    adapter = MockNSICAdapter()
    return _execute_adapter_verification(adapter, req)


@router.post("/oem/verify", response_model=MockVerifyResponse)
def verify_oem_record(req: MockVerifyRequest) -> MockVerifyResponse:
    """Queries synthetic OEM Authorization Registry."""
    adapter = MockOEMAdapter()
    return _execute_adapter_verification(adapter, req)


@router.post("/mii/verify", response_model=MockVerifyResponse)
def verify_mii_record(req: MockVerifyRequest) -> MockVerifyResponse:
    """Queries synthetic Make in India (MII) Local Content Registry."""
    adapter = MockMIIAdapter()
    return _execute_adapter_verification(adapter, req)


@router.post("/verify", response_model=MockVerifyResponse)
def verify_generic_mock(
    registry_name: str = Query(..., description="One of: itd, mca21, nsic, oem, mii"),
    req: MockVerifyRequest = ...,
) -> MockVerifyResponse:
    """Generic router endpoint to query any synthetic mock government registry."""
    key = registry_name.lower().strip()
    adapters = {
        "itd": MockITDAdapter,
        "mock_itd": MockITDAdapter,
        "mca": MockMCA21Adapter,
        "mca21": MockMCA21Adapter,
        "mock_mca21": MockMCA21Adapter,
        "nsic": MockNSICAdapter,
        "mock_nsic": MockNSICAdapter,
        "oem": MockOEMAdapter,
        "mock_oem": MockOEMAdapter,
        "mii": MockMIIAdapter,
        "mock_mii": MockMIIAdapter,
    }
    adapter_cls = adapters.get(key)
    if not adapter_cls:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown mock registry '{registry_name}'. Valid options: itd, mca21, nsic, oem, mii",
        )
    return _execute_adapter_verification(adapter_cls(), req)
