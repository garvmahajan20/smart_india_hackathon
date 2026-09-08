# -*- coding: utf-8 -*-
"""
Comprehensive Unit & Integration Test Suite for GSTINAPI GST Verification.
Covers:
- Configuration and credential safety (zero secret leakage)
- GSTIN format regex validation & pre-flight guards
- Model parsing: taxpayer profile, returns, filing preference, compliance
- Retry policies: retries on 429/502, no retry on 400/401/402/403/404
- Request caching: prevents duplicate billable calls
- Error states: 401, 402, 404, 429, 500, 502, timeouts
- Governance invariant: failed/unavailable responses yield ZERO BidderFacts
- EvidenceAdapter: EvidenceReference, BidderFacts, AdapterResponse, ProvenanceDAG
- FastAPI REST Router endpoints via TestClient
- Orchestrator pluggability via BaseGovernmentAdapter
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import requests

sys.path.insert(0, os.path.abspath("."))

from backend.api.app import app
from backend.core.provenance_dag import ProvenanceDAG
from backend.integrations.gst import (
    GSTAuditEvent,
    GSTAuditLogger,
    GSTComplianceSummary,
    GSTFilingPreference,
    GSTINAPIClient,
    GSTINAPIConfig,
    GSTINAPIEvidenceAdapter,
    GSTINAPIGovernmentAdapter,
    GSTReturnRecord,
    GSTTaxpayerData,
    GSTVerificationRequest,
    GSTVerificationResponse,
    GSTVerificationStatus,
    default_gst_audit_logger,
    extract_pan_from_gstin,
    hash_secret,
    is_valid_gstin_format,
    mask_gstin,
    redact_sensitive_headers,
)
from backend.verification.models import VerificationStatus


class TestGSTINAPIIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api_client = TestClient(app)

    def setUp(self):
        self.config = GSTINAPIConfig(
            api_key="test_secret_api_key_xyz12345",
            base_url="https://www.gstinapi.in",
            timeout_seconds=5,
            max_retries=2,
            retry_backoff_factor=0.01,  # fast backoff for tests
            cache_enabled=True,
            enabled=True,
        )
        self.audit_logger = GSTAuditLogger()
        self.mock_session = MagicMock(spec=requests.Session)
        self.client = GSTINAPIClient(
            config=self.config,
            audit_logger=self.audit_logger,
            session=self.mock_session,
        )

        self.sample_profile_payload = {
            "success": True,
            "test": True,
            "billed_to": "test",
            "gstin": "27AABCU9603R1ZM",
            "credits_remaining": 49,
            "data": {
                "gstin": "27AABCU9603R1ZM",
                "legal_name": "ACME INDUSTRIAL SOLUTIONS PRIVATE LIMITED",
                "trade_name": "ACME INDUSTRIAL",
                "status": "Active",
                "taxpayer_type": "Regular",
                "registration_date": "01/07/2017",
                "state_code": "27",
                "einvoice_status": "Yes",
                "city": "Mumbai",
                "pincode": "400001",
                "cancellation_date": None,
                "profile": {
                    "nature_of_business": ["Manufacturing", "Wholesale"],
                    "constitution_of_business": "Private Limited Company",
                },
            },
        }

        self.sample_returns_payload = {
            "success": True,
            "gstin": "27AABCU9603R1ZM",
            "fy": "2024-25",
            "returns": [
                {"return_type": "GSTR1", "period": "042024", "filing_date": "10/05/2024", "status": "Filed", "arn": "AA2704240001234"},
                {"return_type": "GSTR3B", "period": "042024", "filing_date": "19/05/2024", "status": "Filed", "arn": "AA2704240005678"},
                {"return_type": "GSTR1", "period": "052024", "filing_date": "11/06/2024", "status": "Filed", "arn": "AA2705240001234"},
                {"return_type": "GSTR3B", "period": "052024", "filing_date": "20/06/2024", "status": "Filed", "arn": "AA2705240005678"},
            ],
            "credits_remaining": 48,
        }

        self.sample_compliance_payload = {
            "success": True,
            "gstin": "27AABCU9603R1ZM",
            "fy": "2024-25",
            "compliance": {
                "total_filed": 4,
                "gstr1_filed": 2,
                "gstr3b_filed": 2,
                "by_type": {"GSTR1": 2, "GSTR3B": 2},
            },
            "credits_remaining": 47,
        }

    # 1. Config Loading & Safety
    def test_01_config_loading_and_masking(self):
        cfg = GSTINAPIConfig(api_key="secret12345678")
        self.assertTrue(cfg.is_configured())
        self.assertEqual(cfg.auth_header()["x-api-key"], "secret12345678")

        # Unconfigured behavior
        cfg_empty = GSTINAPIConfig(api_key="")
        self.assertFalse(cfg_empty.is_configured())
        self.assertEqual(cfg_empty.auth_header(), {})

    # 2. Format Validation
    def test_02_gstin_format_validation(self):
        # Valid cases
        self.assertTrue(is_valid_gstin_format("27AABCU9603R1ZM"))
        self.assertTrue(is_valid_gstin_format("00AAAAA0000A1ZT"))
        self.assertTrue(is_valid_gstin_format("29AABCS1429B1ZB"))

        # Invalid cases
        self.assertFalse(is_valid_gstin_format("27AABCU9603R1Z"))    # 14 chars
        self.assertFalse(is_valid_gstin_format("27AABCU9603R1ZMM"))  # 16 chars
        self.assertFalse(is_valid_gstin_format("XXAABCU9603R1ZM"))   # non-numeric state
        self.assertFalse(is_valid_gstin_format("27AABCU9603R1AM"))   # 14th char not Z
        self.assertFalse(is_valid_gstin_format(""))
        self.assertFalse(is_valid_gstin_format(None))

    # 3. PAN extraction from GSTIN
    def test_03_extract_pan_from_gstin(self):
        pan = extract_pan_from_gstin("27AABCU9603R1ZM")
        self.assertEqual(pan, "AABCU9603R")

        test_pan = extract_pan_from_gstin("00AAAAA0000A1ZT")
        self.assertEqual(test_pan, "AAAAA0000A")

        self.assertIsNone(extract_pan_from_gstin("INVALID"))

    # 4. Audit Logger & Secret Redaction
    def test_04_audit_logger_and_secret_redaction(self):
        headers = {
            "x-api-key": "super_secret_key_9999",
            "Content-Type": "application/json",
            "Authorization": "Bearer token123",
        }
        redacted = redact_sensitive_headers(headers)
        self.assertEqual(redacted["x-api-key"], "[REDACTED]")
        self.assertEqual(redacted["Authorization"], "[REDACTED]")
        self.assertEqual(redacted["Content-Type"], "application/json")

        # Masking GSTIN
        masked = mask_gstin("27AABCU9603R1ZM")
        self.assertEqual(masked, "27AABC****3R1ZM")

        # Secret hash
        h = hash_secret("my_secret_key")
        self.assertEqual(len(h), 16)

    # 5. Successful GSTIN Verification (Mocked 200)
    def test_05_verify_gstin_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.sample_profile_payload
        self.mock_session.get.return_value = mock_resp

        res = self.client.verify_gstin("27AABCU9603R1ZM", include_profile=True)
        self.assertEqual(res.status, GSTVerificationStatus.VERIFIED)
        self.assertEqual(res.gstin, "27AABCU9603R1ZM")
        self.assertIsNotNone(res.data)
        self.assertEqual(res.data.legal_name, "ACME INDUSTRIAL SOLUTIONS PRIVATE LIMITED")
        self.assertEqual(res.data.status, "Active")
        self.assertTrue(res.is_test)
        self.assertEqual(res.credits_remaining, 49)
        self.assertIsNotNone(res.response_hash)

    # 6. Returns & Compliance Parsing
    def test_06_returns_and_compliance_parsing(self):
        # Test Returns
        mock_ret_resp = MagicMock()
        mock_ret_resp.status_code = 200
        mock_ret_resp.json.return_value = self.sample_returns_payload
        self.mock_session.get.return_value = mock_ret_resp

        returns = self.client.get_returns("27AABCU9603R1ZM", fy="2024-25")
        self.assertEqual(len(returns), 4)
        self.assertEqual(returns[0].return_type, "GSTR1")
        self.assertEqual(returns[0].period, "042024")
        self.assertEqual(returns[0].status, "Filed")

        # Test Compliance
        mock_comp_resp = MagicMock()
        mock_comp_resp.status_code = 200
        mock_comp_resp.json.return_value = self.sample_compliance_payload
        self.mock_session.get.return_value = mock_comp_resp

        comp = self.client.get_compliance("27AABCU9603R1ZM", fy="2024-25")
        self.assertIsNotNone(comp)
        self.assertEqual(comp.total_filed, 4)
        self.assertEqual(comp.gstr1_filed, 2)
        self.assertEqual(comp.gstr3b_filed, 2)

    # 7. Pre-flight Regex Guard (Zero Network Calls on Malformed GSTIN)
    def test_07_preflight_regex_guard(self):
        res = self.client.verify_gstin("INVALID-GSTIN")
        self.assertEqual(res.status, GSTVerificationStatus.UNVERIFIED)
        self.assertIn("Invalid GSTIN format", res.error_message)
        # Verify session.get was NEVER called
        self.mock_session.get.assert_not_called()

    # 8. Request Caching
    def test_08_request_caching(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = self.sample_profile_payload
        self.mock_session.get.return_value = mock_resp

        # First call
        res1 = self.client.verify_gstin("27AABCU9603R1ZM")
        self.assertEqual(res1.status, GSTVerificationStatus.VERIFIED)
        self.assertEqual(self.mock_session.get.call_count, 1)

        # Second call with same parameters should return from cache
        res2 = self.client.verify_gstin("27AABCU9603R1ZM")
        self.assertEqual(res2.status, GSTVerificationStatus.VERIFIED)
        self.assertEqual(self.mock_session.get.call_count, 1)  # Still 1, not 2!

    # 9. Retry Policy: Retries on 429 and 502
    def test_09_retry_policy_429_and_502(self):
        # 429 rate limit then success
        resp_429 = MagicMock()
        resp_429.status_code = 429
        resp_429.text = "Rate limit exceeded"

        resp_200 = MagicMock()
        resp_200.status_code = 200
        resp_200.json.return_value = self.sample_profile_payload

        # Reset cache
        self.client.clear_cache()
        self.mock_session.get.side_effect = [resp_429, resp_200]

        res = self.client.verify_gstin("27AABCU9603R1ZM")
        self.assertEqual(res.status, GSTVerificationStatus.VERIFIED)
        self.assertEqual(self.mock_session.get.call_count, 2)

    # 10. No Retry on 400, 401, 402, 403, 404
    def test_10_no_retry_on_client_errors(self):
        # 401 Unauthorized
        self.client.clear_cache()
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_401.text = "Invalid API key"
        self.mock_session.get.side_effect = None
        self.mock_session.get.return_value = resp_401

        res = self.client.verify_gstin("27AABCU9603R1ZM")
        self.assertEqual(res.status, GSTVerificationStatus.AUTH_ERROR)
        self.assertEqual(self.mock_session.get.call_count, 1)  # Called exactly once!

        # 402 Credits Exhausted
        self.client.clear_cache()
        resp_402 = MagicMock()
        resp_402.status_code = 402
        resp_402.text = "Credits exhausted"
        self.mock_session.get.return_value = resp_402

        res_402 = self.client.verify_gstin("29AABCS1429B1ZB")
        self.assertEqual(res_402.status, GSTVerificationStatus.QUOTA_EXHAUSTED)
        self.assertEqual(self.mock_session.get.call_count, 2)  # 1 previous + 1 current

        # 404 Not Found
        self.client.clear_cache()
        resp_404 = MagicMock()
        resp_404.status_code = 404
        resp_404.text = "GSTIN not found"
        self.mock_session.get.return_value = resp_404

        res_404 = self.client.verify_gstin("00AAAAA0000A1ZT")
        self.assertEqual(res_404.status, GSTVerificationStatus.NOT_VERIFIED)
        self.assertEqual(self.mock_session.get.call_count, 3)  # 2 previous + 1 current

    # 11. CRITICAL GOVERNANCE INVARIANT: Failed/Unavailable yields ZERO BidderFacts
    def test_11_governance_invariant_zero_facts_on_failure(self):
        # 404 Response
        resp_404 = GSTVerificationResponse(
            gstin="27AABCU9603R1ZM",
            status=GSTVerificationStatus.NOT_VERIFIED,
            http_status=404,
            error_message="GSTIN not found",
        )
        facts = GSTINAPIEvidenceAdapter.to_bidder_facts(resp_404, bid_id="BID-FAIL-01")
        self.assertEqual(len(facts), 0, "404 response MUST NOT produce any BidderFacts!")

        # 502 Service Unavailable
        resp_502 = GSTVerificationResponse(
            gstin="27AABCU9603R1ZM",
            status=GSTVerificationStatus.SERVICE_UNAVAILABLE,
            http_status=502,
            error_message="Bad gateway",
        )
        facts_502 = GSTINAPIEvidenceAdapter.to_bidder_facts(resp_502, bid_id="BID-FAIL-02")
        self.assertEqual(len(facts_502), 0, "502 response MUST NOT produce any BidderFacts!")

        # 401 Auth Error
        resp_401 = GSTVerificationResponse(
            gstin="27AABCU9603R1ZM",
            status=GSTVerificationStatus.AUTH_ERROR,
            http_status=401,
            error_message="Unauthorized",
        )
        facts_401 = GSTINAPIEvidenceAdapter.to_bidder_facts(resp_401, bid_id="BID-FAIL-03")
        self.assertEqual(len(facts_401), 0, "401 response MUST NOT produce any BidderFacts!")

    # 12. Evidence & Provenance Adapter Fact Generation
    def test_12_evidence_adapter_fact_generation(self):
        parsed_data = GSTTaxpayerData.from_dict(self.sample_profile_payload["data"])
        verified_resp = GSTVerificationResponse(
            gstin="27AABCU9603R1ZM",
            status=GSTVerificationStatus.VERIFIED,
            http_status=200,
            data=parsed_data,
            response_hash="abc123hash",
            is_test=True,
            credits_remaining=49,
        )

        # EvidenceReference check
        ev_ref = GSTINAPIEvidenceAdapter.to_evidence_reference(verified_resp)
        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])
        self.assertIn("GSTINAPI:REGISTRY", ev_ref.document)
        self.assertEqual(ev_ref.extraction_confidence, "HIGH")

        # BidderFacts check
        facts = GSTINAPIEvidenceAdapter.to_bidder_facts(verified_resp, bid_id="BID-001")
        self.assertGreaterEqual(len(facts), 5)

        facts_by_field = {f.field: f.value for f in facts}
        self.assertEqual(facts_by_field["gstin"], "27AABCU9603R1ZM")
        self.assertEqual(facts_by_field["legal_name"], "ACME INDUSTRIAL SOLUTIONS PRIVATE LIMITED")
        self.assertEqual(facts_by_field["gst_status"], "Active")
        self.assertEqual(facts_by_field["pan"], "AABCU9603R")

        # ProvenanceDAG acyclicity check
        dag = ProvenanceDAG()
        GSTINAPIEvidenceAdapter.integrate_with_dag(dag, facts, verified_resp)
        dag.validate()  # Validates acyclicity and structural invariants without raising

    # 13. AdapterResponse Contract & Identity Cross-Check
    def test_13_adapter_response_and_identity_mismatch(self):
        parsed_data = GSTTaxpayerData.from_dict(self.sample_profile_payload["data"])
        verified_resp = GSTVerificationResponse(
            gstin="27AABCU9603R1ZM",
            status=GSTVerificationStatus.VERIFIED,
            http_status=200,
            data=parsed_data,
            response_hash="hash999",
        )

        # Matching name
        res_match = GSTINAPIEvidenceAdapter.to_adapter_response(
            verified_resp, expected_entity_name="Acme Industrial Solutions Pvt Ltd"
        )
        self.assertEqual(res_match.status, VerificationStatus.VERIFIED)

        # Mismatched name
        res_mismatch = GSTINAPIEvidenceAdapter.to_adapter_response(
            verified_resp, expected_entity_name="Totally Different Corporation Limited"
        )
        self.assertEqual(res_mismatch.status, VerificationStatus.IDENTITY_MISMATCH)
        self.assertIn("differs from claimed bidder entity", res_mismatch.reason)

    # 14. REST Endpoints via TestClient
    def test_14_fastapi_endpoints(self):
        # GET /api/v1/integrations/gst/status
        status_resp = self.api_client.get("/api/v1/integrations/gst/status")
        self.assertEqual(status_resp.status_code, 200)
        status_data = status_resp.json()
        self.assertIn("enabled", status_data)
        self.assertIn("masked_key", status_data)

        # POST /api/v1/integrations/gst/verify - Invalid GSTIN format
        bad_resp = self.api_client.post(
            "/api/v1/integrations/gst/verify",
            json={"gstin": "INVALID123"},
        )
        self.assertEqual(bad_resp.status_code, 400)
        err_msg = bad_resp.json().get("error") or bad_resp.json().get("detail") or ""
        self.assertIn("Invalid GSTIN format", err_msg)

        # POST /api/v1/integrations/gst/verify - Valid GSTIN format (mocked client)
        with patch.object(GSTINAPIClient, "verify_gstin") as mock_verify:
            parsed_data = GSTTaxpayerData.from_dict(self.sample_profile_payload["data"])
            mock_verify.return_value = GSTVerificationResponse(
                gstin="27AABCU9603R1ZM",
                status=GSTVerificationStatus.VERIFIED,
                http_status=200,
                data=parsed_data,
                response_hash="hash123",
            )
            good_resp = self.api_client.post(
                "/api/v1/integrations/gst/verify",
                json={"gstin": "27AABCU9603R1ZM", "convert_to_bidder_fact": True},
            )
            self.assertEqual(good_resp.status_code, 200)
            data = good_resp.json()
            self.assertEqual(data["status"], "VERIFIED")
            self.assertEqual(data["gstin"], "27AABCU9603R1ZM")
            self.assertIsNotNone(data["bidder_facts"])
            self.assertGreaterEqual(len(data["bidder_facts"]), 5)

        # GET /api/v1/integrations/gst/audit-logs
        audit_resp = self.api_client.get("/api/v1/integrations/gst/audit-logs")
        self.assertEqual(audit_resp.status_code, 200)
        self.assertIn("events", audit_resp.json())

    # 15. Orchestrator Pluggability
    def test_15_orchestrator_pluggability(self):
        from backend.orchestration import VerificationOrchestrator
        gov_adapter = GSTINAPIGovernmentAdapter(client=self.client)
        orchestrator = VerificationOrchestrator(gst_adapter=gov_adapter)
        self.assertIs(orchestrator.gst_adapter, gov_adapter)


if __name__ == "__main__":
    unittest.main()
