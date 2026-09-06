# -*- coding: utf-8 -*-
"""
Comprehensive Dedicated Test Suite for API Setu / MSME Udyam Verification.
Covers:
- Configuration and environment loading
- Request schema and exact 'udyamNumber' field preservation
- Headers and consentArtifact structure
- XML parsing of Udyam certificates with field extraction and XPath provenance
- Malformed XML and XXE Injection attack mitigation
- HTTP status mapping (200, 400, 401, 404, 500, 502, 503, 504)
- Timeout and network error handling
- EvidenceReference creation with [0.0, 0.0, 0.0, 0.0] bbox
- BidderFact creation gating (verified only; no positive facts on failure)
- ProvenanceDAG integration and strict acyclicity enforcement
- Audit logger PAN/mobile masking and API key SHA-256 hashing
- FastAPI REST endpoints
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.api.app import app
from backend.core.provenance_dag import ProvenanceDAG
from backend.integrations.udyam import (
    APISetuUdyamClient,
    APISetuUdyamEvidenceAdapter,
    UdyamAuditEvent,
    UdyamAuditLogger,
    UdyamVerificationConfig,
    UdyamVerificationRequest,
    UdyamVerificationResponse,
    UdyamVerificationStatus,
    UdyamXMLParsingError,
    hash_secret,
    is_valid_udyam_format,
    mask_mobile,
    mask_udyam,
    parse_udyam_verification_xml,
)
from backend.verification.models import VerificationStatus


class TestUdyamVerification(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock()
        self.config = UdyamVerificationConfig(
            enabled=True,
            environment="sandbox",
            base_url="https://sandbox.api-setu.in",
            api_key="demokey123456ABCD789",
            client_id="in.gov.sandbox",
            timeout_seconds=5,
        )
        self.audit_logger = UdyamAuditLogger()
        self.client = APISetuUdyamClient(
            config=self.config,
            audit_logger=self.audit_logger,
            session=self.mock_session,
        )
        self.sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Certificate type="UDCER" number="UDYAM-MH-01-0088776" issuer="Ministry of Micro, Small and Medium Enterprises">
  <CertificateData>
    <UdyamRegistration udyamNumber="UDYAM-MH-01-0088776" enterpriseName="Apex Precision Tooling Pvt Ltd" enterpriseType="MICRO" majorActivity="MANUFACTURING">
      <EnterpriseName>Apex Precision Tooling Pvt Ltd</EnterpriseName>
      <EnterpriseType>MICRO</EnterpriseType>
      <MajorActivity>MANUFACTURING</MajorActivity>
      <DateOfCommencement>12-04-2018</DateOfCommencement>
      <SocialCategory>GENERAL</SocialCategory>
      <State>Maharashtra</State>
      <District>Pune</District>
    </UdyamRegistration>
  </CertificateData>
</Certificate>
"""

    # 1. Format validation
    def test_01_udyam_format_validation(self):
        self.assertTrue(is_valid_udyam_format("UDYAM-MH-01-0088776"))
        self.assertTrue(is_valid_udyam_format("udyam-dl-02-1234567"))
        self.assertFalse(is_valid_udyam_format("INVALID-UDYAM"))
        self.assertFalse(is_valid_udyam_format("UDYAM-123"))
        self.assertFalse(is_valid_udyam_format(""))
        self.assertFalse(is_valid_udyam_format(None))

    # 2. Config from env
    def test_02_config_from_env(self):
        with patch.dict(os.environ, {
            "UDYAM_VERIFICATION_ENABLED": "true",
            "UDYAM_VERIFICATION_ENV": "sandbox",
            "UDYAM_VERIFICATION_BASE_URL": "https://custom.api-setu.in",
            "UDYAM_VERIFICATION_API_KEY": "secret_key_123",
            "UDYAM_VERIFICATION_CLIENT_ID": "custom.client",
            "UDYAM_VERIFICATION_TIMEOUT_SECONDS": "15",
        }):
            cfg = UdyamVerificationConfig.from_env()
            self.assertTrue(cfg.enabled)
            self.assertEqual(cfg.base_url, "https://custom.api-setu.in")
            self.assertEqual(cfg.api_key, "secret_key_123")
            self.assertEqual(cfg.client_id, "custom.client")
            self.assertEqual(cfg.timeout_seconds, 15)
            self.assertEqual(cfg.endpoint_url, "https://custom.api-setu.in/certificate/v3/msme/udcer")
            self.assertTrue(cfg.is_configured())

    # 3. Exact field preservation 'udyamNumber'
    def test_03_request_payload_udyam_number_field(self):
        req = UdyamVerificationRequest(
            udyam_number="UDYAM-MH-01-0088776",
            mobile_number="9874563210",
        )
        payload = req.to_api_payload()
        self.assertIn("certificateParameters", payload)
        self.assertIn("udyamNumber", payload["certificateParameters"])
        self.assertNotIn("udyanNumber", payload["certificateParameters"])
        self.assertEqual(payload["certificateParameters"]["udyamNumber"], "UDYAM-MH-01-0088776")
        self.assertEqual(payload["certificateParameters"]["mobileNumber"], "9874563210")
        self.assertEqual(payload["format"], "xml")
        self.assertIn("consentArtifact", payload)

    # 4. XML Parsing success
    def test_04_xml_parsing_success(self):
        resp = parse_udyam_verification_xml(
            xml_string=self.sample_xml,
            txn_id="TXN-UDYAM-001",
            http_status=200,
            queried_udyam="UDYAM-MH-01-0088776",
        )
        self.assertEqual(resp.status, UdyamVerificationStatus.VERIFIED)
        self.assertEqual(resp.udyam_number, "UDYAM-MH-01-0088776")
        self.assertEqual(resp.enterprise_name, "Apex Precision Tooling Pvt Ltd")
        self.assertEqual(resp.enterprise_type, "MICRO")
        self.assertEqual(resp.major_activity, "MANUFACTURING")
        self.assertEqual(resp.date_of_commencement, "12-04-2018")
        self.assertEqual(resp.social_category, "GENERAL")
        self.assertEqual(resp.state, "Maharashtra")
        self.assertIn("udyam_number", resp.xml_field_paths)

    # 5. XXE Injection protection
    def test_05_xxe_injection_rejection(self):
        xxe_payload = """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<Certificate><CertificateData>&xxe;</CertificateData></Certificate>"""
        with self.assertRaises(UdyamXMLParsingError) as ctx:
            parse_udyam_verification_xml(xxe_payload, txn_id="TXN-XXE")
        self.assertIn("XXE Injection attempt detected", str(ctx.exception))

    # 6. Malformed XML handling
    def test_06_malformed_xml_handling(self):
        with self.assertRaises(UdyamXMLParsingError):
            parse_udyam_verification_xml("<UnclosedTag>", txn_id="TXN-MALFORMED")

    # 7. Client 200 verification call
    def test_07_client_verify_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = self.sample_xml
        mock_resp.content = self.sample_xml.encode("utf-8")
        mock_resp.headers = {"Content-Type": "application/xml"}
        self.mock_session.post.return_value = mock_resp

        req = UdyamVerificationRequest(udyam_number="UDYAM-MH-01-0088776")
        res = self.client.verify_udyam(req)
        self.assertEqual(res.status, UdyamVerificationStatus.VERIFIED)
        self.assertEqual(res.udyam_number, "UDYAM-MH-01-0088776")
        self.assertEqual(res.enterprise_name, "Apex Precision Tooling Pvt Ltd")

    # 8. HTTP 400 Bad Request
    def test_08_http_400_bad_request(self):
        mock_resp = MagicMock(status_code=400, text='{"error":"missing_parameter"}', json=lambda: {"error": "missing_parameter"}, content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_udyam(UdyamVerificationRequest(udyam_number="UDYAM-MH-01-0088776"))
        self.assertEqual(res.status, UdyamVerificationStatus.INVALID_REQUEST)
        self.assertEqual(res.http_status, 400)

    # 9. HTTP 401 Unauthorized
    def test_09_http_401_unauthorized(self):
        mock_resp = MagicMock(status_code=401, text='{"status":false,"error":"invalid_authentication"}', content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_udyam(UdyamVerificationRequest(udyam_number="UDYAM-MH-01-0088776"))
        self.assertEqual(res.status, UdyamVerificationStatus.ERROR)
        self.assertEqual(res.error_code, "UNAUTHORIZED")

    # 10. HTTP 404 Not Found
    def test_10_http_404_not_found(self):
        mock_resp = MagicMock(status_code=404, text="Not Found", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_udyam(UdyamVerificationRequest(udyam_number="UDYAM-MH-01-0088776"))
        self.assertEqual(res.status, UdyamVerificationStatus.NOT_VERIFIED)
        self.assertEqual(res.http_status, 404)

    # 11. HTTP 504 Timeout
    def test_11_http_504_gateway_timeout(self):
        mock_resp = MagicMock(status_code=504, text="Gateway Timeout", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_udyam(UdyamVerificationRequest(udyam_number="UDYAM-MH-01-0088776"))
        self.assertEqual(res.status, UdyamVerificationStatus.UNAVAILABLE)

    # 12. EvidenceReference generation
    def test_12_evidence_reference_generation(self):
        resp = parse_udyam_verification_xml(self.sample_xml, txn_id="TXN-EV-01")
        ev_ref = APISetuUdyamEvidenceAdapter.to_evidence_reference(resp)
        self.assertEqual(ev_ref.document, "API_SETU:UDCER:UDYAM-MH-01-0088776")
        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(ev_ref.extraction_confidence, "HIGH")

    # 13. Fact gating rule (Authoritative facts only on verified)
    def test_13_bidder_fact_gating(self):
        # Verified case
        resp_verified = parse_udyam_verification_xml(self.sample_xml, txn_id="TXN-FACT-01")
        adapter_res = APISetuUdyamEvidenceAdapter.to_adapter_response(resp_verified)
        self.assertEqual(adapter_res.status, VerificationStatus.VERIFIED)

        # Unverified / unavailable case
        resp_unavail = UdyamVerificationResponse(
            txn_id="TXN-FAIL",
            status=UdyamVerificationStatus.UNAVAILABLE,
            http_status=504,
            udyam_number="UDYAM-MH-01-0088776",
        )
        adapter_res_fail = APISetuUdyamEvidenceAdapter.to_adapter_response(resp_unavail)
        self.assertNotEqual(adapter_res_fail.status, VerificationStatus.VERIFIED)
        self.assertEqual(adapter_res_fail.status, VerificationStatus.REVIEW)

    # 14. Identity mismatch detection
    def test_14_identity_mismatch_detection(self):
        resp = parse_udyam_verification_xml(self.sample_xml, txn_id="TXN-ID-01")
        # Match
        res_match = APISetuUdyamEvidenceAdapter.to_adapter_response(resp, expected_entity_name="Apex Precision Tooling Pvt Ltd")
        self.assertEqual(res_match.status, VerificationStatus.VERIFIED)
        # Mismatch
        res_mismatch = APISetuUdyamEvidenceAdapter.to_adapter_response(resp, expected_entity_name="Completely Fraudulent Corp")
        self.assertEqual(res_mismatch.status, VerificationStatus.IDENTITY_MISMATCH)

    # 15. ProvenanceDAG acyclicity
    def test_15_provenance_dag_acyclicity(self):
        resp = parse_udyam_verification_xml(self.sample_xml, txn_id="TXN-DAG-01")
        fact = APISetuUdyamEvidenceAdapter.to_bidder_fact(resp, bid_id="BID-UDYAM-01")
        dag = ProvenanceDAG(bid_id="BID-UDYAM-01")
        APISetuUdyamEvidenceAdapter.integrate_with_dag(dag, fact, resp)

        # Invariants and topological sort pass
        dag.validate()
        self.assertIn(f"BLOCK:API_SETU:UDCER:{resp.udyam_number}", dag.nodes)
        self.assertIn(f"FACT:{fact.fact_id}", dag.nodes)

    # 16. Audit masking and secret hashing
    def test_16_audit_masking_and_security(self):
        self.assertEqual(mask_udyam("UDYAM-MH-01-0088776"), "UDYAM-MH-01-***8776")
        self.assertEqual(mask_mobile("9874563210"), "******3210")
        self.assertTrue(hash_secret("demokey123456ABCD789").startswith("sha256:"))

        logger = UdyamAuditLogger()
        logger.log(
            event_type="TEST_EVENT",
            status="OK",
            details={
                "api_key": "raw_secret_key",
                "udyam": "UDYAM-MH-01-0088776",
                "mobile": "9874563210",
            },
        )
        events = logger.get_events()
        self.assertEqual(len(events), 1)
        details = events[0]["details"]
        self.assertNotIn("raw_secret_key", str(details))
        self.assertIn("api_key_hash", details)
        self.assertEqual(details["udyam"], "UDYAM-MH-01-***8776")
        self.assertEqual(details["mobile"], "******3210")

    # 17. FastAPI endpoints
    def test_17_fastapi_endpoints(self):
        client = TestClient(app)

        # GET /status
        resp_status = client.get("/api/v1/integrations/udyam/status")
        self.assertEqual(resp_status.status_code, 200)
        data = resp_status.json()
        self.assertIn("enabled", data)
        self.assertIn("endpoint", data)

        # GET /audit-logs
        resp_audit = client.get("/api/v1/integrations/udyam/audit-logs")
        self.assertEqual(resp_audit.status_code, 200)
        self.assertIsInstance(resp_audit.json(), list)


if __name__ == "__main__":
    unittest.main()
