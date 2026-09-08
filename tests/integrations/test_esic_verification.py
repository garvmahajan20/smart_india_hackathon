# -*- coding: utf-8 -*-
"""
Dedicated Test Suite for API Setu / ESIC Health Passbook and Pehchan Card Verification.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.api.app import app
from backend.core.provenance_dag import ProvenanceDAG
from backend.integrations.esic import (
    APISetuESICClient,
    APISetuESICEvidenceAdapter,
    ESICAuditEvent,
    ESICAuditLogger,
    ESICDocumentType,
    ESICHealthPassbookRequest,
    ESICPehchanCardRequest,
    ESICVerificationConfig,
    ESICVerificationResponse,
    ESICVerificationStatus,
    ESICXMLParsingError,
    hash_secret,
    is_valid_ip_number,
    mask_ip_number,
    parse_esic_verification_xml,
)
from backend.verification.models import VerificationStatus


class TestESICVerification(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock()
        self.config = ESICVerificationConfig(
            enabled=True,
            environment="sandbox",
            base_url="https://sandbox.api-setu.in",
            api_key="demokey123456ABCD789",
            client_id="in.gov.sandbox",
            timeout_seconds=5,
        )
        self.audit_logger = ESICAuditLogger()
        self.client = APISetuESICClient(
            config=self.config,
            audit_logger=self.audit_logger,
            session=self.mock_session,
        )
        self.sample_esich_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Certificate type="ESICH" number="1199887766" issuer="Employees State Insurance Corporation">
  <CertificateData>
    <HealthPassbook ipNumber="1199887766" insuredPersonName="Ramesh Kumar" employerCode="01000999990001001" employerName="Acme Industrial Works Ltd">
      <InsuredPersonName>Ramesh Kumar</InsuredPersonName>
      <IPNumber>1199887766</IPNumber>
      <EmployerCode>01000999990001001</EmployerCode>
      <EmployerName>Acme Industrial Works Ltd</EmployerName>
      <Dispensary>Okhla Phase 1 ESI Dispensary</Dispensary>
      <UHID>1002003004</UHID>
      <DateOfRegistration>01-08-2015</DateOfRegistration>
    </HealthPassbook>
  </CertificateData>
</Certificate>
"""
        self.sample_phcrd_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Certificate type="PHCRD" number="1199887766" issuer="Employees State Insurance Corporation">
  <CertificateData>
    <PehchanCard ipNumber="1199887766" insuredPersonName="Ramesh Kumar" employerCode="01000999990001001" employerName="Acme Industrial Works Ltd">
      <InsuredPersonName>Ramesh Kumar</InsuredPersonName>
      <IPNumber>1199887766</IPNumber>
      <EmployerCode>01000999990001001</EmployerCode>
      <EmployerName>Acme Industrial Works Ltd</EmployerName>
      <Dispensary>Okhla Phase 1 ESI Dispensary</Dispensary>
      <UHID>1002003004</UHID>
      <DateOfRegistration>01-08-2015</DateOfRegistration>
    </PehchanCard>
  </CertificateData>
</Certificate>
"""

    # 1. IP number format validation
    def test_01_ip_number_validation(self):
        self.assertTrue(is_valid_ip_number("1199887766"))
        self.assertTrue(is_valid_ip_number("1234567890"))
        self.assertFalse(is_valid_ip_number("12345"))
        self.assertFalse(is_valid_ip_number("abcdefghij"))
        self.assertFalse(is_valid_ip_number(""))
        self.assertFalse(is_valid_ip_number(None))

    # 2. Config from env
    def test_02_config_from_env(self):
        with patch.dict(os.environ, {
            "ESIC_VERIFICATION_ENABLED": "true",
            "ESIC_VERIFICATION_ENV": "sandbox",
            "ESIC_VERIFICATION_BASE_URL": "https://custom.api-setu.in",
            "ESIC_VERIFICATION_API_KEY": "secret_key_esic",
            "ESIC_VERIFICATION_CLIENT_ID": "custom.client",
            "ESIC_VERIFICATION_TIMEOUT_SECONDS": "14",
        }):
            cfg = ESICVerificationConfig.from_env()
            self.assertTrue(cfg.enabled)
            self.assertEqual(cfg.base_url, "https://custom.api-setu.in")
            self.assertEqual(cfg.api_key, "secret_key_esic")
            self.assertEqual(cfg.client_id, "custom.client")
            self.assertEqual(cfg.timeout_seconds, 14)
            self.assertEqual(cfg.health_passbook_url, "https://custom.api-setu.in/certificate/v3/esic/esich")
            self.assertEqual(cfg.pehchan_card_url, "https://custom.api-setu.in/certificate/v3/esic/phcrd")
            self.assertTrue(cfg.is_configured())

    # 3. Exact field preservation: 'ipNumber', 'RELATION', 'EmployerName'
    def test_03_request_payload_field_casing(self):
        # Health passbook
        hp_req = ESICHealthPassbookRequest(ip_number="1199887766", relation="SELF")
        hp_payload = hp_req.to_api_payload()
        self.assertIn("certificateParameters", hp_payload)
        self.assertIn("ipNumber", hp_payload["certificateParameters"])
        self.assertIn("RELATION", hp_payload["certificateParameters"])
        self.assertEqual(hp_payload["certificateParameters"]["ipNumber"], "1199887766")
        self.assertEqual(hp_payload["certificateParameters"]["RELATION"], "SELF")

        # Pehchan card
        pc_req = ESICPehchanCardRequest(ip_number="1199887766", employer_name="Acme Industrial Works Ltd")
        pc_payload = pc_req.to_api_payload()
        self.assertIn("certificateParameters", pc_payload)
        self.assertIn("ipNumber", pc_payload["certificateParameters"])
        self.assertIn("EmployerName", pc_payload["certificateParameters"])
        self.assertEqual(pc_payload["certificateParameters"]["ipNumber"], "1199887766")
        self.assertEqual(pc_payload["certificateParameters"]["EmployerName"], "Acme Industrial Works Ltd")

    # 4. XML Parsing success for Health Passbook
    def test_04_xml_parsing_health_passbook(self):
        resp = parse_esic_verification_xml(
            xml_string=self.sample_esich_xml,
            endpoint_type=ESICDocumentType.HEALTH_PASSBOOK,
            txn_id="TXN-ESIC-001",
            http_status=200,
            queried_ip="1199887766",
        )
        self.assertEqual(resp.status, ESICVerificationStatus.VERIFIED)
        self.assertEqual(resp.ip_number, "1199887766")
        self.assertEqual(resp.insured_person_name, "Ramesh Kumar")
        self.assertEqual(resp.employer_name, "Acme Industrial Works Ltd")
        self.assertEqual(resp.dispensary, "Okhla Phase 1 ESI Dispensary")
        self.assertIn("ip_number", resp.xml_field_paths)

    # 5. XML Parsing success for Pehchan Card
    def test_05_xml_parsing_pehchan_card(self):
        resp = parse_esic_verification_xml(
            xml_string=self.sample_phcrd_xml,
            endpoint_type=ESICDocumentType.PEHCHAN_CARD,
            txn_id="TXN-ESIC-002",
            http_status=200,
            queried_ip="1199887766",
        )
        self.assertEqual(resp.status, ESICVerificationStatus.VERIFIED)
        self.assertEqual(resp.ip_number, "1199887766")
        self.assertEqual(resp.insured_person_name, "Ramesh Kumar")
        self.assertEqual(resp.employer_name, "Acme Industrial Works Ltd")

    # 6. XXE Injection protection
    def test_06_xxe_injection_rejection(self):
        xxe_payload = """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<Certificate><CertificateData>&xxe;</CertificateData></Certificate>"""
        with self.assertRaises(ESICXMLParsingError) as ctx:
            parse_esic_verification_xml(xxe_payload, ESICDocumentType.HEALTH_PASSBOOK, txn_id="TXN-XXE")
        self.assertIn("XXE Injection attempt detected", str(ctx.exception))

    # 7. Malformed XML handling
    def test_07_malformed_xml_handling(self):
        with self.assertRaises(ESICXMLParsingError):
            parse_esic_verification_xml("<UnclosedTag>", ESICDocumentType.HEALTH_PASSBOOK, txn_id="TXN-MALFORMED")

    # 8. Client 200 verification calls
    def test_08_client_verify_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = self.sample_esich_xml
        mock_resp.content = self.sample_esich_xml.encode("utf-8")
        mock_resp.headers = {"Content-Type": "application/xml"}
        self.mock_session.post.return_value = mock_resp

        req = ESICHealthPassbookRequest(ip_number="1199887766", relation="SELF")
        res = self.client.verify_health_passbook(req)
        self.assertEqual(res.status, ESICVerificationStatus.VERIFIED)
        self.assertEqual(res.ip_number, "1199887766")
        self.assertEqual(res.insured_person_name, "Ramesh Kumar")

    # 9. HTTP 400 Bad Request
    def test_09_http_400_bad_request(self):
        mock_resp = MagicMock(status_code=400, text='{"error":"missing_ipNumber"}', json=lambda: {"error": "missing_ipNumber"}, content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_health_passbook(ESICHealthPassbookRequest(ip_number="1199887766"))
        self.assertEqual(res.status, ESICVerificationStatus.INVALID_REQUEST)
        self.assertEqual(res.http_status, 400)

    # 10. HTTP 401 Unauthorized
    def test_10_http_401_unauthorized(self):
        mock_resp = MagicMock(status_code=401, text='{"status":false,"error":"invalid_authentication"}', content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_health_passbook(ESICHealthPassbookRequest(ip_number="1199887766"))
        self.assertEqual(res.status, ESICVerificationStatus.ERROR)
        self.assertEqual(res.error_code, "UNAUTHORIZED")

    # 11. HTTP 404 Not Found
    def test_11_http_404_not_found(self):
        mock_resp = MagicMock(status_code=404, text="Not Found", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_health_passbook(ESICHealthPassbookRequest(ip_number="1199887766"))
        self.assertEqual(res.status, ESICVerificationStatus.NOT_VERIFIED)
        self.assertEqual(res.http_status, 404)

    # 12. HTTP 504 Timeout
    def test_12_http_504_gateway_timeout(self):
        mock_resp = MagicMock(status_code=504, text="Gateway Timeout", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_health_passbook(ESICHealthPassbookRequest(ip_number="1199887766"))
        self.assertEqual(res.status, ESICVerificationStatus.UNAVAILABLE)

    # 13. EvidenceReference generation
    def test_13_evidence_reference_generation(self):
        resp = parse_esic_verification_xml(self.sample_esich_xml, ESICDocumentType.HEALTH_PASSBOOK, txn_id="TXN-EV-01")
        ev_ref = APISetuESICEvidenceAdapter.to_evidence_reference(resp)
        self.assertEqual(ev_ref.document, "API_SETU:ESIC:HEALTH_PASSBOOK:1199887766")
        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(ev_ref.extraction_confidence, "HIGH")

    # 14. Fact gating rule & scope disclaimer
    def test_14_bidder_fact_gating_and_disclaimer(self):
        resp_verified = parse_esic_verification_xml(self.sample_esich_xml, ESICDocumentType.HEALTH_PASSBOOK, txn_id="TXN-FACT-01")
        adapter_res = APISetuESICEvidenceAdapter.to_adapter_response(resp_verified)
        self.assertEqual(adapter_res.status, VerificationStatus.VERIFIED)
        self.assertIn("ESIC", adapter_res.reason)

        resp_unavail = ESICVerificationResponse(
            txn_id="TXN-FAIL",
            endpoint_type=ESICDocumentType.HEALTH_PASSBOOK,
            status=ESICVerificationStatus.UNAVAILABLE,
            http_status=504,
            ip_number="1199887766",
        )
        adapter_res_fail = APISetuESICEvidenceAdapter.to_adapter_response(resp_unavail)
        self.assertNotEqual(adapter_res_fail.status, VerificationStatus.VERIFIED)
        self.assertEqual(adapter_res_fail.status, VerificationStatus.REVIEW)

    # 15. Identity mismatch detection
    def test_15_identity_mismatch_detection(self):
        resp = parse_esic_verification_xml(self.sample_esich_xml, ESICDocumentType.HEALTH_PASSBOOK, txn_id="TXN-ID-01")
        res_match = APISetuESICEvidenceAdapter.to_adapter_response(resp, expected_entity_name="Ramesh Kumar")
        self.assertEqual(res_match.status, VerificationStatus.VERIFIED)
        res_mismatch = APISetuESICEvidenceAdapter.to_adapter_response(resp, expected_entity_name="Completely Fraudulent Corp")
        self.assertEqual(res_mismatch.status, VerificationStatus.IDENTITY_MISMATCH)

    # 16. ProvenanceDAG acyclicity
    def test_16_provenance_dag_acyclicity(self):
        resp = parse_esic_verification_xml(self.sample_esich_xml, ESICDocumentType.HEALTH_PASSBOOK, txn_id="TXN-DAG-01")
        fact = APISetuESICEvidenceAdapter.to_bidder_fact(resp, bid_id="BID-ESIC-01")
        dag = ProvenanceDAG(bid_id="BID-ESIC-01")
        APISetuESICEvidenceAdapter.integrate_with_dag(dag, fact, resp)

        dag.validate()
        self.assertIn(f"BLOCK:API_SETU:ESIC:HEALTH_PASSBOOK:{resp.ip_number}", dag.nodes)
        self.assertIn(f"FACT:{fact.fact_id}", dag.nodes)

    # 17. Audit masking and secret hashing
    def test_17_audit_masking_and_hashing(self):
        self.assertEqual(mask_ip_number("1199887766"), "1199****7766")
        self.assertTrue(hash_secret("demokey123456ABCD789").startswith("sha256:"))

    # 18. REST API router endpoints
    def test_18_rest_api_endpoints(self):
        client = TestClient(app)
        with patch.object(APISetuESICClient, "verify_health_passbook") as mock_hp:
            mock_hp.return_value = parse_esic_verification_xml(self.sample_esich_xml, ESICDocumentType.HEALTH_PASSBOOK, txn_id="TXN-API-HP")
            response = client.post(
                "/api/v1/integrations/esic/verify/health-passbook",
                json={"ip_number": "1199887766", "relation": "SELF"},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "VERIFIED")
            self.assertEqual(data["insured_person_name"], "Ramesh Kumar")

        with patch.object(APISetuESICClient, "verify_pehchan_card") as mock_pc:
            mock_pc.return_value = parse_esic_verification_xml(self.sample_phcrd_xml, ESICDocumentType.PEHCHAN_CARD, txn_id="TXN-API-PC")
            response = client.post(
                "/api/v1/integrations/esic/verify/pehchan-card",
                json={"ip_number": "1199887766", "employer_name": "Acme Industrial Works Ltd"},
            )
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "VERIFIED")
            self.assertEqual(data["insured_person_name"], "Ramesh Kumar")


if __name__ == "__main__":
    unittest.main()
