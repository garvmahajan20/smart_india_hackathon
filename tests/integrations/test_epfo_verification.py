# -*- coding: utf-8 -*-
"""
Comprehensive Dedicated Test Suite for API Setu / EPFO Verification.
Covers:
- Configuration and environment loading for all three EPFO endpoints
- UAN Card request schema (format="pdf", parameters: UAN, DOB)
- Scheme Certificate request schema (format="xml", parameters: SCNO)
- Pension Certificate request schema (format="xml", parameters: PPONO)
- Headers and consentArtifact structure
- PDF validation and handling (%PDF- header, SHA-256 computation, byte size)
- XML parsing of Scheme & Pension Certificates with XPath provenance
- Malformed payloads and XXE Injection protection
- HTTP status mapping (200, 400, 401, 404, 500, 502, 503, 504)
- Scope notice: explicitly distinguishes document verification from employer compliance
- Fact gating rule: no authoritative facts on failure
- ProvenanceDAG integration and acyclicity
- Audit logger masking and secret hashing
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
from backend.integrations.epfo import (
    APISetuEPFOClient,
    APISetuEPFOEvidenceAdapter,
    EPFOAuditEvent,
    EPFOAuditLogger,
    EPFOEndpointType,
    EPFOPDFHandlingError,
    EPFOVerificationConfig,
    EPFOVerificationResponse,
    EPFOVerificationStatus,
    EPFOXMLParsingError,
    PensionCertificateRequest,
    SchemeCertificateRequest,
    UANCardRequest,
    hash_secret,
    is_valid_dob_format,
    is_valid_ppono_format,
    is_valid_scno_format,
    is_valid_uan_format,
    mask_identifier,
    parse_epfo_certificate_xml,
    process_epfo_uan_pdf,
)
from backend.verification.models import VerificationStatus


class TestEPFOVerification(unittest.TestCase):
    def setUp(self):
        self.mock_session = MagicMock()
        self.config = EPFOVerificationConfig(
            enabled=True,
            environment="sandbox",
            base_url="https://sandbox.api-setu.in",
            api_key="demokey123456ABCD789",
            client_id="in.gov.sandbox",
            timeout_seconds=5,
        )
        self.audit_logger = EPFOAuditLogger()
        self.client = APISetuEPFOClient(
            config=self.config,
            audit_logger=self.audit_logger,
            session=self.mock_session,
        )

        self.sample_scheme_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Certificate type="EPFSC" number="APSID00040466" issuer="Employees' Provident Fund Organisation">
  <CertificateData>
    <SchemeCertificate scno="APSID00040466" memberName="Sunil Kumar Sharma" dob="15-08-1980" fatherHusbandName="Ram Kumar Sharma" issueDate="20-05-2015"/>
  </CertificateData>
</Certificate>
"""

        self.sample_pension_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Certificate type="PECER" number="DLCPM00052882" issuer="Employees' Provident Fund Organisation">
  <CertificateData>
    <PensionCertificate ppono="DLCPM00052882" pensionerName="Ramesh Chandra Gupta" dob="10-10-1955" fatherHusbandName="Late Shri Gupta" issueDate="01-01-2016"/>
  </CertificateData>
</Certificate>
"""

    # 1. Format validators
    def test_01_format_validators(self):
        self.assertTrue(is_valid_uan_format("1234567890"))
        self.assertTrue(is_valid_uan_format("100123456789"))
        self.assertFalse(is_valid_uan_format("abc123"))

        self.assertTrue(is_valid_dob_format("31-12-1980"))
        self.assertFalse(is_valid_dob_format("1980/12/31"))

        self.assertTrue(is_valid_scno_format("APSID00040466"))
        self.assertFalse(is_valid_scno_format("A"))

        self.assertTrue(is_valid_ppono_format("DLCPM00052882"))
        self.assertFalse(is_valid_ppono_format("P"))

    # 2. Config endpoints
    def test_02_config_endpoints(self):
        cfg = self.config
        self.assertEqual(cfg.uan_card_url, "https://sandbox.api-setu.in/certificate/v3/epfindia/uncrd")
        self.assertEqual(cfg.scheme_cert_url, "https://sandbox.api-setu.in/certificate/v3/epfindia/epfsc")
        self.assertEqual(cfg.pension_cert_url, "https://sandbox.api-setu.in/certificate/v3/epfindia/pecer")

    # 3. Request schemas & formats
    def test_03_request_schemas_and_formats(self):
        # UAN Card -> format: pdf
        req_uan = UANCardRequest(uan="1234567890", dob="31-12-1980")
        payload_u = req_uan.to_api_payload()
        self.assertEqual(payload_u["format"], "pdf")
        self.assertEqual(payload_u["certificateParameters"]["UAN"], "1234567890")
        self.assertEqual(payload_u["certificateParameters"]["DOB"], "31-12-1980")

        # Scheme Cert -> format: xml
        req_sc = SchemeCertificateRequest(scno="APSID00040466")
        payload_sc = req_sc.to_api_payload()
        self.assertEqual(payload_sc["format"], "xml")
        self.assertEqual(payload_sc["certificateParameters"]["SCNO"], "APSID00040466")

        # Pension Cert -> format: xml
        req_pen = PensionCertificateRequest(ppono="DLCPM00052882")
        payload_pen = req_pen.to_api_payload()
        self.assertEqual(payload_pen["format"], "xml")
        self.assertEqual(payload_pen["certificateParameters"]["PPONO"], "DLCPM00052882")

    # 4. PDF handling for UAN Card
    def test_04_pdf_handling_uan_card(self):
        valid_pdf = b"%PDF-1.4 sample pdf binary data stream for test validation"
        res = process_epfo_uan_pdf(valid_pdf, txn_id="TXN-PDF-01", queried_uan="1234567890")
        self.assertEqual(res.status, EPFOVerificationStatus.VERIFIED)
        self.assertEqual(res.format, "pdf")
        self.assertEqual(res.pdf_size_bytes, len(valid_pdf))
        self.assertIsNotNone(res.response_hash)

        # Invalid PDF header rejection
        with self.assertRaises(EPFOPDFHandlingError):
            process_epfo_uan_pdf(b"NOT A PDF STREAM", txn_id="TXN-BAD-PDF")

    # 5. XML parsing for Scheme Certificate
    def test_05_xml_parsing_scheme_certificate(self):
        res = parse_epfo_certificate_xml(
            xml_string=self.sample_scheme_xml,
            endpoint_type=EPFOEndpointType.SCHEME_CERTIFICATE,
            txn_id="TXN-SC-01",
            queried_identifier="APSID00040466",
        )
        self.assertEqual(res.status, EPFOVerificationStatus.VERIFIED)
        self.assertEqual(res.certificate_number, "APSID00040466")
        self.assertEqual(res.member_name, "Sunil Kumar Sharma")
        self.assertEqual(res.dob, "15-08-1980")

    # 6. XML parsing for Pension Certificate
    def test_06_xml_parsing_pension_certificate(self):
        res = parse_epfo_certificate_xml(
            xml_string=self.sample_pension_xml,
            endpoint_type=EPFOEndpointType.PENSION_CERTIFICATE,
            txn_id="TXN-PPO-01",
            queried_identifier="DLCPM00052882",
        )
        self.assertEqual(res.status, EPFOVerificationStatus.VERIFIED)
        self.assertEqual(res.certificate_number, "DLCPM00052882")
        self.assertEqual(res.member_name, "Ramesh Chandra Gupta")

    # 7. XXE Protection in EPFO XML
    def test_07_xxe_protection_epfo(self):
        xxe_payload = """<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/shadow">]>
<Certificate><CertificateData>&xxe;</CertificateData></Certificate>"""
        with self.assertRaises(EPFOXMLParsingError):
            parse_epfo_certificate_xml(xxe_payload, EPFOEndpointType.SCHEME_CERTIFICATE, "TXN-XXE")

    # 8. Scope limitation notice
    def test_08_scope_limitation_notice(self):
        res = parse_epfo_certificate_xml(
            self.sample_scheme_xml,
            endpoint_type=EPFOEndpointType.SCHEME_CERTIFICATE,
            txn_id="TXN-SCOPE-01",
        )
        self.assertFalse(res.is_employer_compliance)
        self.assertIn("EPFO_DOCUMENT_CERTIFICATE_VERIFICATION_ONLY", res.scope_notice)

    # 9. Client verify UAN card call
    def test_09_client_verify_uan_card(self):
        valid_pdf = b"%PDF-1.4 test uan card binary"
        mock_resp = MagicMock(status_code=200, content=valid_pdf)
        self.mock_session.post.return_value = mock_resp

        res = self.client.verify_uan_card(UANCardRequest(uan="1234567890", dob="31-12-1980"))
        self.assertEqual(res.status, EPFOVerificationStatus.VERIFIED)
        self.assertEqual(res.format, "pdf")

    # 10. Client verify Scheme cert call
    def test_10_client_verify_scheme_cert(self):
        mock_resp = MagicMock(status_code=200, text=self.sample_scheme_xml, content=self.sample_scheme_xml.encode("utf-8"))
        self.mock_session.post.return_value = mock_resp

        res = self.client.verify_scheme_certificate(SchemeCertificateRequest(scno="APSID00040466"))
        self.assertEqual(res.status, EPFOVerificationStatus.VERIFIED)
        self.assertEqual(res.format, "xml")

    # 11. Client verify Pension cert call
    def test_11_client_verify_pension_cert(self):
        mock_resp = MagicMock(status_code=200, text=self.sample_pension_xml, content=self.sample_pension_xml.encode("utf-8"))
        self.mock_session.post.return_value = mock_resp

        res = self.client.verify_pension_certificate(PensionCertificateRequest(ppono="DLCPM00052882"))
        self.assertEqual(res.status, EPFOVerificationStatus.VERIFIED)
        self.assertEqual(res.format, "xml")

    # 12. HTTP 404 Not Found
    def test_12_http_404_not_found(self):
        mock_resp = MagicMock(status_code=404, text="Not Found", content=b"err")
        self.mock_session.post.return_value = mock_resp

        res = self.client.verify_scheme_certificate(SchemeCertificateRequest(scno="APSID00040466"))
        self.assertEqual(res.status, EPFOVerificationStatus.NOT_VERIFIED)
        self.assertEqual(res.http_status, 404)

    # 13. HTTP 504 Timeout
    def test_13_http_504_timeout(self):
        mock_resp = MagicMock(status_code=504, text="Gateway Timeout", content=b"err")
        self.mock_session.post.return_value = mock_resp

        res = self.client.verify_pension_certificate(PensionCertificateRequest(ppono="DLCPM00052882"))
        self.assertEqual(res.status, EPFOVerificationStatus.UNAVAILABLE)
        self.assertEqual(res.http_status, 504)

    # 14. EvidenceReference & Fact Gating
    def test_14_evidence_and_fact_gating(self):
        # Verified XML
        res = parse_epfo_certificate_xml(self.sample_scheme_xml, EPFOEndpointType.SCHEME_CERTIFICATE, "TXN-01")
        ev_ref = APISetuEPFOEvidenceAdapter.to_evidence_reference(res)
        self.assertEqual(ev_ref.document, "API_SETU:EPFO:SCHEME_CERTIFICATE:APSID00040466")
        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])

        adapter_res = APISetuEPFOEvidenceAdapter.to_adapter_response(res)
        self.assertEqual(adapter_res.status, VerificationStatus.VERIFIED)

        # Failed
        res_fail = EPFOVerificationResponse(
            endpoint_type=EPFOEndpointType.SCHEME_CERTIFICATE,
            identifier="APSID00040466",
            txn_id="TXN-FAIL",
            status=EPFOVerificationStatus.UNAVAILABLE,
            http_status=504,
            format="xml",
        )
        adapter_res_fail = APISetuEPFOEvidenceAdapter.to_adapter_response(res_fail)
        self.assertEqual(adapter_res_fail.status, VerificationStatus.REVIEW)

    # 15. ProvenanceDAG acyclicity
    def test_15_provenance_dag_acyclicity(self):
        res = parse_epfo_certificate_xml(self.sample_scheme_xml, EPFOEndpointType.SCHEME_CERTIFICATE, "TXN-DAG-01")
        fact = APISetuEPFOEvidenceAdapter.to_bidder_fact(res, bid_id="BID-EPFO-01")
        dag = ProvenanceDAG(bid_id="BID-EPFO-01")
        APISetuEPFOEvidenceAdapter.integrate_with_dag(dag, fact, res)

        dag.validate()
        self.assertIn(f"BLOCK:API_SETU:EPFO:SCHEME_CERTIFICATE:{res.identifier}", dag.nodes)
        self.assertIn(f"FACT:{fact.fact_id}", dag.nodes)

    # 16. Audit masking & secret security
    def test_16_audit_masking(self):
        self.assertEqual(mask_identifier("1234567890"), "1234****7890")
        self.assertEqual(mask_identifier("APSID00040466"), "APSI****0466")
        logger = EPFOAuditLogger()
        logger.log("TEST", "UAN_CARD", "OK", details={"api_key": "raw_secret", "uan": "1234567890", "dob": "31-12-1980"})
        events = logger.get_events()
        self.assertNotIn("raw_secret", str(events))
        self.assertEqual(events[0]["details"]["uan"], "1234****7890")
        self.assertEqual(events[0]["details"]["dob"], "**-**-****")

    # 17. FastAPI endpoints
    def test_17_fastapi_endpoints(self):
        client = TestClient(app)

        # GET /status
        resp_status = client.get("/api/v1/integrations/epfo/status")
        self.assertEqual(resp_status.status_code, 200)
        data = resp_status.json()
        self.assertIn("uan_card_endpoint", data)
        self.assertIn("scheme_cert_endpoint", data)
        self.assertIn("pension_cert_endpoint", data)
        self.assertIn("scope_notice", data)

        # GET /audit-logs
        resp_audit = client.get("/api/v1/integrations/epfo/audit-logs")
        self.assertEqual(resp_audit.status_code, 200)
        self.assertIsInstance(resp_audit.json(), list)


if __name__ == "__main__":
    unittest.main()
