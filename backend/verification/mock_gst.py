# -*- coding: utf-8 -*-
import re
from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key

def _normalize_company_name(name: Optional[str]) -> str:
    if not name:
        return ""
    cleaned = name.upper()
    # Normalize common legal suffixes
    cleaned = re.sub(r"\bPRIVATE LIMITED\b", "PVT LTD", cleaned)
    cleaned = re.sub(r"\bPVT\.?\s*LTD\.?\b", "PVT LTD", cleaned)
    cleaned = re.sub(r"\bLIMITED\b", "LTD", cleaned)
    cleaned = re.sub(r"\bLTD\.?\b", "LTD", cleaned)
    cleaned = re.sub(r"\bL\.?L\.?P\.?\b", "LLP", cleaned)
    return " ".join(cleaned.split())

class MockGSTAdapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for GSTIN.
    Queries the deterministic in-memory mock GST database.
    Adheres to the swap-in ready BaseGovernmentAdapter contract.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockGSTAdapter"

    @property
    def source_name(self) -> str:
        return "MOCK_GST_REGISTRY"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any
    ) -> AdapterResponse:
        clean_gst = _clean_key(identifier)
        record = self.registry.gst_records.get(clean_gst)

        if not record:
            return AdapterResponse(
                status=VerificationStatus.NOT_FOUND,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"GSTIN '{identifier}' was not found in the mock GST registry.",
                matched_entity=None,
                registered_entity_name=None,
                registration_status="NOT_FOUND",
                timestamp=timestamp,
                is_mock=True,
            )

        reg_status = record.get("registration_status", "ACTIVE")
        reg_name = record.get("company_name", "")

        if reg_status != "ACTIVE":
            return AdapterResponse(
                status=VerificationStatus.INACTIVE,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"GSTIN '{identifier}' is registered to '{reg_name}' but status is '{reg_status}'.",
                matched_entity=record,
                registered_entity_name=reg_name,
                registration_status=reg_status,
                timestamp=timestamp,
                is_mock=True,
            )

        # Cross-check entity name if supplied
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
                        f"GSTIN '{identifier}' is registered to '{reg_name}', "
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
            reason=f"GSTIN '{identifier}' is active and verified for '{reg_name}'.",
            matched_entity=record,
            registered_entity_name=reg_name,
            registration_status=reg_status,
            evidence=[{"field": "gstin", "value": identifier, "associated_pan": record.get("pan")}],
            timestamp=timestamp,
            is_mock=True,
        )
