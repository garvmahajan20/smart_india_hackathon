# -*- coding: utf-8 -*-
"""
Dedicated Test Suite for API Setu / DPIIT Startup India Recognition Certificate Verification.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.api.app import app
from backend.core.provenance_dag import ProvenanceDAG
from backend.integrations.dpiit import (
    APISetuDPIITClient,
    APISetuDPIITEvidenceAdapter,
    DPIITAuditEvent,
    DPIITAuditLogger,
    DPIITVerificationConfig,
    DPIITVerificationRequest,
    DPIITVerificationResponse,
    DPIITVerificationStatus,
    DPIITXMLParsingError,
    hash_secret,
    is_valid_dpiit_format,
    mask_mobile,
    mask_registration,
    parse_dpiit_verification_xml,
)
from backend.verification.models import VerificationStatus


class TestDPIITVerification(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock()
        self.config = DPIITVerificationConfig(
            enabled=True,
            environment="sandbox",
            base_url="https://sandbox.api-setu.in",
            api_key="demokey123456ABCD789",
            client_id="in.gov.sandbox",
            timeout_seconds=5,
        )
        self.audit_logger = DPIITAuditLogger()
        self.client = APISetuDPIITClient(
            config=self.config,
            audit_logger=self.audit_logger,
            session=self.mock_session,
        )
        self.sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Certificate type="SUIRC" number="DIPP12345" issuer="Department for Promotion of Industry and Internal Trade">
  <CertificateData>
    <StartupRegistration regnNo="DIPP12345" startupName="Innovatech Solutions Pvt Ltd">
      <StartupName>Innovatech Solutions Pvt Ltd</StartupName>
      <RegnNo>DIPP12345</RegnNo>
      <IncorporationDate>15-06-2020</IncorporationDate>
      <RecognitionDate>10-09-2021</RecognitionDate>
      <Industry>Information Technology</Industry>
      <Sector>Artificial Intelligence</Sector>
      <EntityType>Private Limited Company</EntityType>
    </StartupRegistration>
  </CertificateData>
</Certificate>
"""

    # 1. Format validation
    def test_01_format_validation(self):
        self.assertTrue(is_valid_dpiit_format("DIPP12345"))
        self.assertTrue(is_valid_dpiit_format("DPIIT123456"))
        self.assertTrue(is_valid_dpiit_format("dipp999"))
        self.assertFalse(is_valid_dpiit_format("INVALID_DPIIT"))
        self.assertFalse(is_valid_dpiit_format(""))
        self.assertFalse(is_valid_dpiit_format(None))

    # 2. Config from env
    def test_02_config_from_env(self):
        with patch.dict(os.environ, {
            "DPIIT_VERIFICATION_ENABLED": "true",
            "DPIIT_VERIFICATION_ENV": "sandbox",
            "DPIIT_VERIFICATION_BASE_URL": "https://custom.api-setu.in",
            "DPIIT_VERIFICATION_API_KEY": "secret_key_dpiit",
            "DPIIT_VERIFICATION_CLIENT_ID": "custom.client",
            "DPIIT_VERIFICATION_TIMEOUT_SECONDS": "12",
        }):
            cfg = DPIITVerificationConfig.from_env()
            self.assertTrue(cfg.enabled)
            self.assertEqual(cfg.base_url, "https://custom.api-setu.in")
            self.assertEqual(cfg.api_key, "secret_key_dpiit")
            self.assertEqual(cfg.client_id, "custom.client")
            self.assertEqual(cfg.timeout_seconds, 12)
            self.assertEqual(cfg.endpoint_url, "https://custom.api-setu.in/certificate/v3/dpiit/suirc")
            self.assertTrue(cfg.is_configured())

    # 3. Exact field preservation 'REGN_NO', 'MobileNumber'
    def test_03_request_payload_field_casing(self):
        req = DPIITVerificationRequest(
            regn_no="DIPP12345",
            mobile_number="9876543210",
        )
        payload = req.to_api_payload()
        self.assertIn("certificateParameters", payload)
        self.assertIn("REGN_NO", payload["certificateParameters"])
        self.assertIn("MobileNumber", payload["certificateParameters"])
        self.assertEqual(payload["certificateParameters"]["REGN_NO"], "DIPP12345")
        self.assertEqual(payload["certificateParameters"]["MobileNumber"], "9876543210")
        self.assertEqual(payload["format"], "xml")
        self.assertIn("consentArtifact", payload)

    # 4. XML Parsing success
    def test_04_xml_parsing_success(self):
        resp = parse_dpiit_verification_xml(
            xml_string=self.sample_xml,
            txn_id="TXN-DPIIT-001",
            http_status=200,
            queried_regn="DIPP12345",
        )
        self.assertEqual(resp.status, DPIITVerificationStatus.VERIFIED)
        self.assertEqual(resp.regn_no, "DIPP12345")
        self.assertEqual(resp.startup_name, "Innovatech Solutions Pvt Ltd")
        self.assertEqual(resp.incorporation_date, "15-06-2020")
        self.assertEqual(resp.recognition_date, "10-09-2021")
        self.assertEqual(resp.industry, "Information Technology")
        self.assertEqual(resp.sector, "Artificial Intelligence")
        self.assertEqual(resp.entity_type, "Private Limited Company")
        self.assertIn("regn_no", resp.xml_field_paths)

    # 5. XXE Injection protection
    def test_05_xxe_injection_rejection(self):
        xxe_payload = """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<Certificate><CertificateData>&xxe;</CertificateData></Certificate>"""
        with self.assertRaises(DPIITXMLParsingError) as ctx:
            parse_dpiit_verification_xml(xxe_payload, txn_id="TXN-XXE")
        self.assertIn("XXE Injection attempt detected", str(ctx.exception))

    # 6. Malformed XML handling
    def test_06_malformed_xml_handling(self):
        with self.assertRaises(DPIITXMLParsingError):
            parse_dpiit_verification_xml("<UnclosedTag>", txn_id="TXN-MALFORMED")

    # 7. Client 200 verification call
    def test_07_client_verify_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = self.sample_xml
        mock_resp.content = self.sample_xml.encode("utf-8")
        mock_resp.headers = {"Content-Type": "application/xml"}
        self.mock_session.post.return_value = mock_resp

        req = DPIITVerificationRequest(regn_no="DIPP12345", mobile_number="9876543210")
        res = self.client.verify_dpiit(req)
        self.assertEqual(res.status, DPIITVerificationStatus.VERIFIED)
        self.assertEqual(res.regn_no, "DIPP12345")
        self.assertEqual(res.startup_name, "Innovatech Solutions Pvt Ltd")

    # 8. HTTP 400 Bad Request
    def test_08_http_400_bad_request(self):
        mock_resp = MagicMock(status_code=400, text='{"error":"missing_parameter"}', json=lambda: {"error": "missing_parameter"}, content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_dpiit(DPIITVerificationRequest(regn_no="DIPP12345"))
        self.assertEqual(res.status, DPIITVerificationStatus.INVALID_REQUEST)
        self.assertEqual(res.http_status, 400)

    # 9. HTTP 401 Unauthorized
    def test_09_http_401_unauthorized(self):
        mock_resp = MagicMock(status_code=401, text='{"status":false,"error":"invalid_authentication"}', content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_dpiit(DPIITVerificationRequest(regn_no="DIPP12345"))
        self.assertEqual(res.status, DPIITVerificationStatus.ERROR)
        self.assertEqual(res.error_code, "UNAUTHORIZED")

    # 10. HTTP 404 Not Found
    def test_10_http_404_not_found(self):
        mock_resp = MagicMock(status_code=404, text="Not Found", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_dpiit(DPIITVerificationRequest(regn_no="DIPP12345"))
        self.assertEqual(res.status, DPIITVerificationStatus.NOT_VERIFIED)
        self.assertEqual(res.http_status, 404)

    # 11. HTTP 504 Timeout
    def test_11_http_504_gateway_timeout(self):
        mock_resp = MagicMock(status_code=504, text="Gateway Timeout", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_dpiit(DPIITVerificationRequest(regn_no="DIPP12345"))
        self.assertEqual(res.status, DPIITVerificationStatus.UNAVAILABLE)

    # 12. EvidenceReference generation
    def test_12_evidence_reference_generation(self):
        resp = parse_dpiit_verification_xml(self.sample_xml, txn_id="TXN-EV-01")
        ev_ref = APISetuDPIITEvidenceAdapter.to_evidence_reference(resp)
        self.assertEqual(ev_ref.document, "API_SETU:SUIRC:DIPP12345")
        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(ev_ref.extraction_confidence, "HIGH")

    # 13. Fact gating rule
    def test_13_bidder_fact_gating(self):
        resp_verified = parse_dpiit_verification_xml(self.sample_xml, txn_id="TXN-FACT-01")
        adapter_res = APISetuDPIITEvidenceAdapter.to_adapter_response(resp_verified)
        self.assertEqual(adapter_res.status, VerificationStatus.VERIFIED)

        resp_unavail = DPIITVerificationResponse(
            txn_id="TXN-FAIL",
            status=DPIITVerificationStatus.UNAVAILABLE,
            http_status=504,
            regn_no="DIPP12345",
        )
        adapter_res_fail = APISetuDPIITEvidenceAdapter.to_adapter_response(resp_unavail)
        self.assertNotEqual(adapter_res_fail.status, VerificationStatus.VERIFIED)
        self.assertEqual(adapter_res_fail.status, VerificationStatus.REVIEW)

    # 14. Identity mismatch detection
    def test_14_identity_mismatch_detection(self):
        resp = parse_dpiit_verification_xml(self.sample_xml, txn_id="TXN-ID-01")
        res_match = APISetuDPIITEvidenceAdapter.to_adapter_response(resp, expected_entity_name="Innovatech Solutions Pvt Ltd")
        self.assertEqual(res_match.status, VerificationStatus.VERIFIED)
        res_mismatch = APISetuDPIITEvidenceAdapter.to_adapter_response(resp, expected_entity_name="Completely Fraudulent Corp")
        self.assertEqual(res_mismatch.status, VerificationStatus.IDENTITY_MISMATCH)

    # 15. ProvenanceDAG acyclicity
    def test_15_provenance_dag_acyclicity(self):
        resp = parse_dpiit_verification_xml(self.sample_xml, txn_id="TXN-DAG-01")
        fact = APISetuDPIITEvidenceAdapter.to_bidder_fact(resp, bid_id="BID-DPIIT-01")
        dag = ProvenanceDAG(bid_id="BID-DPIIT-01")
        APISetuDPIITEvidenceAdapter.integrate_with_dag(dag, fact, resp)

        dag.validate()
        self.assertIn(f"BLOCK:API_SETU:SUIRC:{resp.regn_no}", dag.nodes)
        self.assertIn(f"FACT:{fact.fact_id}", dag.nodes)

    # 16. Audit masking and secret hashing
    def test_16_audit_masking_and_hashing(self):
        self.assertEqual(mask_registration("DIPP12345"), "DIPP****2345")
        self.assertEqual(mask_mobile("9876543210"), "******3210")
        self.assertTrue(hash_secret("demokey123456ABCD789").startswith("sha256:"))

    # 17. REST API router endpoint
    def test_17_rest_api_endpoint(self):
        client = TestClient(app)
        with patch.object(APISetuDPIITClient, "verify_recognition_certificate") as mock_v:
            mock_v.return_value = parse_dpiit_verification_xml(self.sample_xml, txn_id="TXN-API-01")
            response = client.post(
                "/api/v1/integrations/dpiit/verify",
                json={"regn_no": "DIPP12345", "mobile_number": "9876543210"},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "VERIFIED")
            self.assertEqual(data["startup_name"], "Innovatech Solutions Pvt Ltd")


if __name__ == "__main__":
    unittest.main()
