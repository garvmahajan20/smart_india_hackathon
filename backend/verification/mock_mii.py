# -*- coding: utf-8 -*-
"""
Mock Make in India (MII) / Local Content Verification Adapter.
Source Type: INTERNAL_MOCK_REGISTRY
Registry ID: MOCK_MII
Dataset Version: MOCK_REGISTRY_DATASET_V1
"""

from typing import Any, Dict, Optional

from .base import BaseGovernmentAdapter
from .mock_gst import _normalize_company_name
from .models import AdapterResponse, VerificationStatus
from .registry import MockGovernmentRegistry, _clean_key


class MockMIIAdapter(BaseGovernmentAdapter):
    """
    Mock Government Verification Adapter for Make in India Local Content Declarations.
    Queries the deterministic in-memory synthetic MII database.
    Supplies factual local content evidence; deterministic rule engine evaluates tender thresholds.
    """

    def __init__(self, registry: Optional[MockGovernmentRegistry] = None):
        self.registry = registry or MockGovernmentRegistry.get_instance()

    @property
    def adapter_name(self) -> str:
        return "MockMIIAdapter"

    @property
    def source_name(self) -> str:
        return "MOCK_MII"

    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any,
    ) -> AdapterResponse:
        clean_id = _clean_key(identifier)
        expected_entity_name = expected_entity_name or kwargs.get("expected_name")
        record = self.registry.mii_records.get(clean_id)

        # Fallback to (Manufacturer:Product)
        product_name = kwargs.get("product_name")
        if not record and expected_entity_name and product_name:
            key_prod = _clean_key(f"{expected_entity_name}:{product_name}")
            record = self.registry.mii_records.get(key_prod)

        if not record:
            return AdapterResponse(
                status=VerificationStatus.NOT_FOUND,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"Make in India declaration/certificate '{identifier}' not found in mock MII registry.",
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

        decl_id = record.get("declaration_id", identifier)
        mfg = record.get("manufacturer_name", "")
        status_val = record.get("status", "VALID")
        lc_pct = record.get("local_content_percentage", 0.0)
        supplier_class = record.get("supplier_class", "CLASS_2")
        valid_until = record.get("valid_until", "N/A")

        base_evidence = {
            "source_type": "INTERNAL_MOCK_REGISTRY",
            "dataset_version": self.registry.DATASET_VERSION,
            "registry": self.source_name,
            "declaration_id": decl_id,
            "manufacturer_name": mfg,
            "local_content_percentage": lc_pct,
            "supplier_class": supplier_class,
            "status": status_val,
            "valid_until": valid_until,
            "is_mock": True,
        }

        # Check expired or invalid
        if status_val in ("EXPIRED", "INVALID"):
            return AdapterResponse(
                status=VerificationStatus.INACTIVE,
                adapter_name=self.adapter_name,
                queried_identifier=identifier,
                source=self.source_name,
                reason=f"MII declaration '{decl_id}' is {status_val} (Valid until: {valid_until}).",
                matched_entity=record,
                registered_entity_name=mfg,
                registration_status=status_val,
                evidence=[base_evidence],
                timestamp=timestamp,
                is_mock=True,
            )

        # Identity cross-check
        if expected_entity_name and mfg:
            norm_reg = _normalize_company_name(mfg)
            norm_exp = _normalize_company_name(expected_entity_name)
            if norm_reg != norm_exp and not (norm_reg in norm_exp or norm_exp in norm_reg):
                return AdapterResponse(
                    status=VerificationStatus.IDENTITY_MISMATCH,
                    adapter_name=self.adapter_name,
                    queried_identifier=identifier,
                    source=self.source_name,
                    reason=(
                        f"MII declaration '{decl_id}' is issued to '{mfg}', "
                        f"which differs from claimed bidder entity '{expected_entity_name}'."
                    ),
                    matched_entity=record,
                    registered_entity_name=mfg,
                    registration_status=status_val,
                    evidence=[base_evidence],
                    timestamp=timestamp,
                    is_mock=True,
                )

        # Verified outcome supplies authoritative percentage evidence
        return AdapterResponse(
            status=VerificationStatus.VERIFIED,
            adapter_name=self.adapter_name,
            queried_identifier=identifier,
            source=self.source_name,
            reason=f"MII declaration '{decl_id}' verified for '{mfg}': Local Content = {lc_pct}%, Class = {supplier_class}.",
            matched_entity=record,
            registered_entity_name=mfg,
            registration_status=status_val,
            evidence=[base_evidence],
            timestamp=timestamp,
            is_mock=True,
        )
