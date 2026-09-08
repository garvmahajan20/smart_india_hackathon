# -*- coding: utf-8 -*-
"""
Mock Original Equipment Manufacturer (OEM) Authorization Verification Adapter.
Source Type: INTERNAL_MOCK_REGISTRY
Registry ID: MOCK_OEM
Dataset Version: MOCK_REGISTRY_DATASET_V1
"""

from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .mock_gst import _normalize_company_name
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key


class MockOEMAdapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for OEM Manufacturer Authorization Form (MAF).
    Queries the deterministic in-memory synthetic OEM database.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockOEMAdapter"

    @property
    def source_name(self) -> str:
        return "MOCK_OEM"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResponse:
        clean_id = _clean_key(identifier)
        expected_entity_name = expected_entity_name or kwargs.get("expected_name")
        record = self.registry.oem_records.get(clean_id)

        # Fallback to (OEM:Bidder) lookup if oem_name provided
        oem_name = kwargs.get("oem_name")
        if not record and oem_name and expected_entity_name:
            pair_key = _clean_key(f"{oem_name}:{expected_entity_name}")
            record = self.registry.oem_records.get(pair_key)

        if not record:
            return AdapterResponse(
                status=VerificationStatus.NOT_FOUND,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"OEM authorization certificate/reference '{identifier}' not found in mock OEM registry.",
                matched_entity=None,
                registered_entity_name=None,
                registration_status="NOT_FOUND",
                evidence=[{
                    "source_type": "INTERNAL_MOCK_REGISTRY",
                    "dataset_version": self.registry.DATASET_VERSION,
                    "registry": self.source_name,
                    "queried_identifier": identifier,
                }],
                timestamp=timestamp,
                is_mock=True,
            )

        auth_num = record.get("auth_number", identifier)
        oem = record.get("oem_name", "OEM")
        auth_bidder = record.get("authorized_bidder", "")
        status_val = record.get("status", "ACTIVE")
        expiry = record.get("expiry_date", "N/A")
        prod_cat = record.get("product_category", "All Products")

        base_evidence = {
            "source_type": "INTERNAL_MOCK_REGISTRY",
            "dataset_version": self.registry.DATASET_VERSION,
            "registry": self.source_name,
            "auth_number": auth_num,
            "oem_name": oem,
            "authorized_bidder": auth_bidder,
            "status": status_val,
            "expiry_date": expiry,
            "product_category": prod_cat,
            "is_mock": True,
        }

        # Check expired
        if status_val == "EXPIRED":
            return AdapterResponse(
                status=VerificationStatus.INACTIVE,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"OEM Authorization '{auth_num}' from '{oem}' expired on {expiry}.",
                matched_entity=record,
                registered_entity_name=auth_bidder,
                registration_status="EXPIRED",
                evidence=[base_evidence],
                timestamp=timestamp,
                is_mock=True,
            )

        # Check unauthorized / revoked
        if status_val in ("UNAUTHORIZED", "REVOKED"):
            return AdapterResponse(
                status=VerificationStatus.REVIEW,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"Reseller '{auth_bidder}' is listed as UNAUTHORIZED / REVOKED by OEM '{oem}'.",
                matched_entity=record,
                registered_entity_name=auth_bidder,
                registration_status=status_val,
                evidence=[base_evidence],
                timestamp=timestamp,
                is_mock=True,
            )

        # Identity cross-check
        if expected_entity_name and auth_bidder:
            norm_reg = _normalize_company_name(auth_bidder)
            norm_exp = _normalize_company_name(expected_entity_name)
            if norm_reg != norm_exp and not (norm_reg in norm_exp or norm_exp in norm_reg):
                return AdapterResponse(
                    status=VerificationStatus.IDENTITY_MISMATCH,
                    adapter_name=self.adapter_name,
                    queried_identifier=identifier,
                    source=self.source_name,
                    reason=(
                        f"OEM authorization '{auth_num}' authorizes '{auth_bidder}', "
                        f"which differs from claimed bidder entity '{expected_entity_name}'."
                    ),
                    matched_entity=record,
                    registered_entity_name=auth_bidder,
                    registration_status=status_val,
                    evidence=[base_evidence],
                    timestamp=timestamp,
                    is_mock=True,
                )

        return AdapterResponse(
            status=VerificationStatus.VERIFIED,
            adapter_name=self.adapter_name,
            queried_identifier=identifier,
            source=self.source_name,
            reason=f"OEM authorization '{auth_num}' from '{oem}' is active and valid for bidder '{auth_bidder}'.",
            matched_entity=record,
            registered_entity_name=auth_bidder,
            registration_status=status_val,
            evidence=[base_evidence],
            timestamp=timestamp,
            is_mock=True,
        )
