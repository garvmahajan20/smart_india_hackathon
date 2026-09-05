# -*- coding: utf-8 -*-
from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .mock_gst import _normalize_company_name
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key

class MockUdyamAdapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for Udyam / MSME Registration.
    Verifies MSE statutory claims to provide verified facts consumed by
    the Step 4 conditional exemption engine.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockUdyamAdapter"

    @property
    def source_name(self) -> str:
        return "MOCK_UDYAM_REGISTRY"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any
    ) -> AdapterResponse:
        clean_id = _clean_key(identifier)
        record = self.registry.udyam_records.get(clean_id)

        # Also search by expected_entity_name if identifier was cert number and not found directly
        if not record and expected_entity_name:
            record = self.registry.udyam_records.get(_clean_key(expected_entity_name))

        if not record:
            return AdapterResponse(
                status=VerificationStatus.NOT_FOUND,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"Udyam registration '{identifier}' was not found in the mock MSME registry.",
                matched_entity=None,
                registered_entity_name=None,
                registration_status="NOT_FOUND",
                timestamp=timestamp,
                is_mock=True,
            )

        holder = record.get("holder_name", "")
        status = record.get("status", "ACTIVE")
        is_valid = record.get("is_valid", True)
        anomaly = record.get("anomaly", "NONE")
        ent_type = record.get("enterprise_type", "MICRO")

        if not is_valid or anomaly != "NONE" or status != "ACTIVE":
            return AdapterResponse(
                status=VerificationStatus.REVIEW,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=(
                    f"Udyam certificate '{record.get('cert_number')}' has integrity flag '{anomaly}' "
                    f"or status '{status}'. Officer review required before exemption grant."
                ),
                matched_entity=record,
                registered_entity_name=holder,
                registration_status=status,
                evidence=[{"cert_number": record.get("cert_number"), "anomaly": anomaly}],
                timestamp=timestamp,
                is_mock=True,
            )

        if expected_entity_name:
            norm_holder = _normalize_company_name(holder)
            norm_exp = _normalize_company_name(expected_entity_name)
            if norm_holder != norm_exp and not (norm_holder in norm_exp or norm_exp in norm_holder):
                return AdapterResponse(
                    status=VerificationStatus.IDENTITY_MISMATCH,
                    adapter_name=self.adapter_name,
                    queried_identifier=identifier,
                    source=self.source_name,
                    reason=(
                        f"Udyam registration '{record.get('cert_number')}' is issued to '{holder}', "
                        f"which does not match claimed bidder '{expected_entity_name}'."
                    ),
                    matched_entity=record,
                    registered_entity_name=holder,
                    registration_status=status,
                    timestamp=timestamp,
                    is_mock=True,
                )

        return AdapterResponse(
            status=VerificationStatus.VERIFIED,
            adapter_name=self.adapter_name,
            queried_identifier=identifier,
            source=self.source_name,
            reason=f"Udyam certificate verified for '{holder}' ({ent_type} Enterprise). Valid for MSE statutory exemption.",
            matched_entity=record,
            registered_entity_name=holder,
            registration_status="ACTIVE",
            evidence=[{
                "cert_number": record.get("cert_number"),
                "enterprise_type": ent_type,
                "is_mse": True,
            }],
            timestamp=timestamp,
            is_mock=True,
        )
