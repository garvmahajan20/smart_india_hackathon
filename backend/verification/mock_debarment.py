# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key

class MockDebarmentAdapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for Debarment / Blacklisting.
    Queries the deterministic in-memory mock debarment registry.
    CRITICAL: This represents a synthetic MOCK fixture for testing.
    It does not claim to represent a live government blacklist.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockDebarmentAdapter"

    @property
    def source_name(self) -> str:
        return "MOCK_DEBARMENT_REGISTRY"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any
    ) -> AdapterResponse:
        clean_id = _clean_key(identifier)
        clean_exp = _clean_key(expected_entity_name) if expected_entity_name else ""

        # Check by identifier (PAN, GSTIN, or Entity Name)
        record = self.registry.debarment_records.get(clean_id)
        if not record and clean_exp:
            record = self.registry.debarment_records.get(clean_exp)

        if record:
            ent_name = record.get("entity_name", identifier)
            reason = record.get("reason", "Debarred under procurement guidelines.")
            authority = record.get("issuing_authority", "Central Procurement Portal")
            period = record.get("debarment_period", "Active")

            return AdapterResponse(
                status=VerificationStatus.DEBARRED,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"CRITICAL: Bidder '{ent_name}' is actively DEBARRED by {authority}. Reason: {reason} (Period: {period}).",
                matched_entity=record,
                registered_entity_name=ent_name,
                registration_status="DEBARRED",
                evidence=[{"debarment_period": period, "authority": authority, "reason": reason}],
                timestamp=timestamp,
                is_mock=True,
            )

        # Entity not found in debarment blacklist -> Clean / Not Debarred
        return AdapterResponse(
            status=VerificationStatus.NOT_DEBARRED,
            adapter_name=self.adapter_name,
            queried_identifier=identifier,
            source=self.source_name,
            reason=f"No active debarment or blacklist order found for '{identifier}' in mock debarment registry.",
            matched_entity=None,
            registered_entity_name=expected_entity_name or identifier,
            registration_status="NOT_DEBARRED",
            evidence=[],
            timestamp=timestamp,
            is_mock=True,
        )
