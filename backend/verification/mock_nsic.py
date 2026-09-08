# -*- coding: utf-8 -*-
"""
Mock National Small Industries Corporation (NSIC) Verification Adapter.
Source Type: INTERNAL_MOCK_REGISTRY
Registry ID: MOCK_NSIC
Dataset Version: MOCK_REGISTRY_DATASET_V1
"""

from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .mock_gst import _normalize_company_name
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key


class MockNSICAdapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for NSIC Certificates.
    Queries the deterministic in-memory synthetic NSIC database.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockNSICAdapter"

    @property
    def source_name(self) -> str:
        return "MOCK_NSIC"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResponse:
        clean_id = _clean_key(identifier)
        expected_entity_name = expected_entity_name or kwargs.get("expected_name")
        record = self.registry.nsic_records.get(clean_id)

        if not record:
            return AdapterResponse(
                status=VerificationStatus.NOT_FOUND,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"NSIC registration certificate '{identifier}' not found in mock NSIC registry.",
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

        cnum = record.get("certificate_number", identifier)
        reg_name = record.get("enterprise_name", "")
        status_val = record.get("status", "ACTIVE")
        expiry = record.get("expiry_date", "N/A")
        cat = record.get("category", "MSE")

        base_evidence = {
            "source_type": "INTERNAL_MOCK_REGISTRY",
            "dataset_version": self.registry.DATASET_VERSION,
            "registry": self.source_name,
            "certificate_number": cnum,
            "enterprise_name": reg_name,
            "status": status_val,
            "category": cat,
            "expiry_date": expiry,
            "is_mock": True,
        }

        # Check expired or inactive status
        if status_val == "EXPIRED":
            return AdapterResponse(
                status=VerificationStatus.INACTIVE,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"NSIC certificate '{cnum}' expired on {expiry}.",
                matched_entity=record,
                registered_entity_name=reg_name,
                registration_status="EXPIRED",
                evidence=[base_evidence],
                timestamp=timestamp,
                is_mock=True,
            )

        if status_val in ("INACTIVE", "SUSPENDED"):
            return AdapterResponse(
                status=VerificationStatus.INACTIVE,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"NSIC certificate '{cnum}' is suspended/inactive in NSIC registry.",
                matched_entity=record,
                registered_entity_name=reg_name,
                registration_status=status_val,
                evidence=[base_evidence],
                timestamp=timestamp,
                is_mock=True,
            )

        # Identity cross-check
        if expected_entity_name and reg_name:
            norm_reg = _normalize_company_name(reg_name)
            norm_exp = _normalize_company_name(expected_entity_name)
            if norm_reg != norm_exp and not (norm_reg in norm_exp or norm_exp in norm_reg):
                return AdapterResponse(
                    status=VerificationStatus.IDENTITY_MISMATCH,
                    adapter_name=self.adapter_name,
                    queried_identifier=identifier,
                    source=self.source_name,
                    reason=(
                        f"NSIC certificate '{cnum}' is registered to '{reg_name}', "
                        f"which differs from claimed bidder '{expected_entity_name}'."
                    ),
                    matched_entity=record,
                    registered_entity_name=reg_name,
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
            reason=f"NSIC certificate '{cnum}' is active and valid for '{reg_name}' (Category: {cat}).",
            matched_entity=record,
            registered_entity_name=reg_name,
            registration_status=status_val,
            evidence=[base_evidence],
            timestamp=timestamp,
            is_mock=True,
        )
