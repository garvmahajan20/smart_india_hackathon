# -*- coding: utf-8 -*-
"""
Mock Income Tax Department (ITD) / ITR Verification Adapter.
Source Type: INTERNAL_MOCK_REGISTRY
Registry ID: MOCK_ITD
Dataset Version: MOCK_REGISTRY_DATASET_V1
"""

from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .mock_gst import _normalize_company_name
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key


class MockITDAdapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for Income Tax Returns (ITR).
    Queries the deterministic in-memory synthetic ITD database.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockITDAdapter"

    @property
    def source_name(self) -> str:
        return "MOCK_ITD"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResponse:
        clean_id = _clean_key(identifier)
        expected_entity_name = expected_entity_name or kwargs.get("expected_name")
        record = self.registry.itd_records.get(clean_id)

        if not record:
            return AdapterResponse(
                status=VerificationStatus.NOT_FOUND,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"Income Tax Return record for '{identifier}' not found in mock ITD registry.",
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

        reg_name = record.get("taxpayer_name", "")
        pan = record.get("pan", identifier)
        filing_status = record.get("filing_status", "UNKNOWN")
        ay = record.get("assessment_year", "2024-25")
        ack = record.get("ack_number")

        base_evidence = {
            "source_type": "INTERNAL_MOCK_REGISTRY",
            "dataset_version": self.registry.DATASET_VERSION,
            "registry": self.source_name,
            "pan": pan,
            "assessment_year": ay,
            "filing_status": filing_status,
            "ack_number": ack,
            "turnover_cr": record.get("turnover_cr"),
            "is_mock": True,
        }

        # Check filing status
        if filing_status == "NOT_FILED":
            return AdapterResponse(
                status=VerificationStatus.INACTIVE,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"ITR for PAN '{pan}' (AY {ay}) is NOT FILED in synthetic Income Tax records.",
                matched_entity=record,
                registered_entity_name=reg_name,
                registration_status="NOT_FILED",
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
                        f"ITR for PAN '{pan}' is filed by '{reg_name}', "
                        f"which does not match claimed bidder '{expected_entity_name}'."
                    ),
                    matched_entity=record,
                    registered_entity_name=reg_name,
                    registration_status=filing_status,
                    evidence=[base_evidence],
                    timestamp=timestamp,
                    is_mock=True,
                )

        return AdapterResponse(
            status=VerificationStatus.VERIFIED,
            adapter_name=self.adapter_name,
            queried_identifier=identifier,
            source=self.source_name,
            reason=f"ITR for PAN '{pan}' (AY {ay}) is verified FILED by '{reg_name}'. Acknowledgement: {ack}.",
            matched_entity=record,
            registered_entity_name=reg_name,
            registration_status=filing_status,
            evidence=[base_evidence],
            timestamp=timestamp,
            is_mock=True,
        )
