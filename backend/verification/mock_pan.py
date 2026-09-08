# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .mock_gst import _normalize_company_name
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key

class MockPANAdapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for PAN.
    Queries the deterministic in-memory mock PAN database.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockPANAdapter"

    @property
    def source_name(self) -> str:
        return "MOCK_PAN_REGISTRY"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any
    ) -> AdapterResponse:
        expected_entity_name = expected_entity_name or kwargs.get("expected_name")
        clean_pan = _clean_key(identifier)
        record = self.registry.pan_records.get(clean_pan)

        if not record:
            return AdapterResponse(
                status=VerificationStatus.NOT_FOUND,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"PAN '{identifier}' was not found in the mock PAN registry.",
                matched_entity=None,
                registered_entity_name=None,
                registration_status="NOT_FOUND",
                timestamp=timestamp,
                is_mock=True,
            )

        reg_name = record.get("company_name", "")
        reg_status = record.get("registration_status", "ACTIVE")

        if expected_entity_name:
            norm_reg = _normalize_company_name(reg_name)
            norm_exp = _normalize_company_name(expected_entity_name)

            if norm_reg != norm_exp and not (norm_reg in norm_exp or norm_exp in norm_reg):
                return AdapterResponse(
                    status=VerificationStatus.IDENTITY_MISMATCH,
                    adapter_name=self.adapter_name,
                    queried_identifier=identifier,
                    source=self.source_name,
                    reason=(
                        f"PAN '{identifier}' is registered to '{reg_name}', "
                        f"which does not match claimed bidder '{expected_entity_name}'."
                    ),
                    matched_entity=record,
                    registered_entity_name=reg_name,
                    registration_status=reg_status,
                    timestamp=timestamp,
                    is_mock=True,
                )

        return AdapterResponse(
            status=VerificationStatus.VERIFIED,
            adapter_name=self.adapter_name,
            queried_identifier=identifier,
            source=self.source_name,
            reason=f"PAN '{identifier}' is valid and verified for '{reg_name}'.",
            matched_entity=record,
            registered_entity_name=reg_name,
            registration_status=reg_status,
            evidence=[{"field": "pan", "value": identifier, "associated_gstin": record.get("gstin")}],
            timestamp=timestamp,
            is_mock=True,
        )
