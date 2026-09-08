# -*- coding: utf-8 -*-
"""
Mock Ministry of Corporate Affairs (MCA21) Verification Adapter.
Source Type: INTERNAL_MOCK_REGISTRY
Registry ID: MOCK_MCA21
Dataset Version: MOCK_REGISTRY_DATASET_V1
"""

from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .mock_gst import _normalize_company_name
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key


class MockMCA21Adapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for Corporate Registrations (CIN).
    Queries the deterministic in-memory synthetic MCA21 database.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockMCA21Adapter"

    @property
    def source_name(self) -> str:
        return "MOCK_MCA21"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResponse:
        clean_id = _clean_key(identifier)
        expected_entity_name = expected_entity_name or kwargs.get("expected_name")
        record = self.registry.mca_records.get(clean_id)

        if not record:
            return AdapterResponse(
                status=VerificationStatus.NOT_FOUND,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"Corporate registration for '{identifier}' not found in mock MCA21 registry.",
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

        reg_name = record.get("company_name", "")
        cin = record.get("cin", identifier)
        status_val = record.get("status", "ACTIVE")

        base_evidence = {
            "source_type": "INTERNAL_MOCK_REGISTRY",
            "dataset_version": self.registry.DATASET_VERSION,
            "registry": self.source_name,
            "cin": cin,
            "status": status_val,
            "company_type": record.get("company_type"),
            "incorporation_date": record.get("incorporation_date"),
            "is_mock": True,
        }

        # Check active status
        if status_val in ("INACTIVE", "STRIKE_OFF", "UNDER_LIQUIDATION"):
            return AdapterResponse(
                status=VerificationStatus.INACTIVE,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"Corporate entity '{cin}' has status '{status_val}' in MCA21 registry.",
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
                        f"CIN '{cin}' is registered to '{reg_name}', "
                        f"which differs from claimed bidder entity '{expected_entity_name}'."
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
            reason=f"CIN '{cin}' is active and valid for corporate entity '{reg_name}'.",
            matched_entity=record,
            registered_entity_name=reg_name,
            registration_status=status_val,
            evidence=[base_evidence],
            timestamp=timestamp,
            is_mock=True,
        )
