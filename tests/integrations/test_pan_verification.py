# -*- coding: utf-8 -*-
"""
Comprehensive Unit & Integration Test Suite for API Setu PAN Verification.
Covers all 36 required test items:
1-7:   Format, Request Model, Txn ID, Endpoint, Headers, Body, Config
8-17:  Sandbox Response, XML/JSON parsing, PAN, Name, DOB, Issuer, Cert Type, Status, Timestamp
18-24: Response Hashing, EvidenceReference, ProvenanceDAG, Field Paths, No Fake BBoxes, Contradiction, Replay
25-36: 400, 401, 404, 500, 502, 503, 504, Timeout, Network Error, Malformed Payload, Secret Redaction, No False PASS
"""

import hashlib
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.api.app import app
from backend.core.provenance_dag import ProvenanceDAG
from backend.integrations.pan import (
    APISetuPANClient,
    APISetuPANEvidenceAdapter,
    PANAuditLogger,
    PANVerificationConfig,
    PANVerificationRequest,
    PANVerificationResponse,
    PANVerificationStatus,
    is_valid_pan_format,
    parse_pan_verification_xml,
    PANXMLParsingError,
)
from backend.verification.models import VerificationStatus


class TestAPISetuPANIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api_client = TestClient(app)

    def setUp(self):
        self.config = PANVerificationConfig(
            enabled=True,
            environment="sandbox",
            base_url="https://sandbox.api-setu.in",
            api_key="test_secret_api_key_12345",
            client_id="in.gov.sandbox",
            timeout_seconds=10,
        )
        self.audit_logger = PANAuditLogger()
        self.mock_session = MagicMock()
        self.client = APISetuPANClient(
            config=self.config,
            audit_logger=self.audit_logger,
            session=self.mock_session,
        )

        self.sample_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <Certificate name="PAN Verification Record" type="PANCR" number="ABCDE1234F"
                     status="A" issueDate="2023-01-15" verifiedOn="2023-01-15">
            <IssuedBy>
                <Organization name="Income Tax Department" code="ITD"/>
            </IssuedBy>
            <IssuedTo>
                <Person name="Bharat Electronics Ltd" dob="15-08-1990"/>
            </IssuedTo>
            <CertificateData>
                <PAN num="ABCDE1234F"/>
            </CertificateData>
        </Certificate>"""

    # 1. PAN format validation
    def test_01_pan_format_validation(self):
        self.assertTrue(is_valid_pan_format("ABCDE1234F"))
        self.assertTrue(is_valid_pan_format("abcde1234f"))
        self.assertFalse(is_valid_pan_format("ABCD12345F"))   # 4 letters
        self.assertFalse(is_valid_pan_format("ABCDEF1234"))   # 6 letters
        self.assertFalse(is_valid_pan_format("ABCDE123AF"))   # letter in digits
        self.assertFalse(is_valid_pan_format(""))
        self.assertFalse(is_valid_pan_format(None))

    # 2. Request model validation
    def test_02_request_model_validation(self):
        req = PANVerificationRequest(
            pan="ABCDE1234F",
            full_name="Test Entity",
            dob="01-01-2000",
        )
        self.assertEqual(req.clean_pan(), "ABCDE1234F")
        self.assertEqual(req.full_name, "Test Entity")

    # 3. Transaction UUID generation
    def test_03_transaction_uuid_generation(self):
        req1 = PANVerificationRequest(pan="ABCDE1234F")
        req2 = PANVerificationRequest(pan="ABCDE1234F")
        self.assertNotEqual(req1.txn_id, req2.txn_id)
        self.assertEqual(len(req1.txn_id), 36)

    # 4. Exact endpoint
    def test_04_exact_endpoint(self):
        self.assertEqual(self.config.endpoint_url, "https://sandbox.api-setu.in/certificate/v3/pan/pancr")

    # 5. Exact required headers
    def test_05_exact_required_headers(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/xml"}
        mock_resp.text = self.sample_xml
        mock_resp.content = self.sample_xml.encode("utf-8")
        self.mock_session.post.return_value = mock_resp

        req = PANVerificationRequest(pan="ABCDE1234F")
        self.client.verify_pan(req)

        self.mock_session.post.assert_called_once()
        _, kwargs = self.mock_session.post.call_args
        headers = kwargs.get("headers", {})
        self.assertEqual(headers.get("Content-Type"), "application/json")
        self.assertEqual(headers.get("X-APISETU-APIKEY"), "test_secret_api_key_12345")
        self.assertEqual(headers.get("X-APISETU-CLIENTID"), "in.gov.sandbox")

    # 6. Request body
    def test_06_request_body_structure(self):
        req = PANVerificationRequest(
            pan="ABCDE1234F",
            full_name="Apex Corp",
            dob="10-10-1995",
            uid="123456789012",
        )
        payload = req.to_api_payload()
        self.assertEqual(payload["txnId"], req.txn_id)
        self.assertEqual(payload["format"], "xml")
        self.assertIn("certificateParameters", payload)
        params = payload["certificateParameters"]
        self.assertEqual(params["panno"], "ABCDE1234F")
        self.assertEqual(params["FullName"], "Apex Corp")
        self.assertEqual(params["DOB"], "10-10-1995")
        self.assertIn("consentArtifact", payload)

    # 7. Configured API key handling
    def test_07_configured_api_key_handling(self):
        cfg = PANVerificationConfig(enabled=True, api_key="my_key", client_id="my_id")
        self.assertTrue(cfg.is_configured())
        cfg_disabled = PANVerificationConfig(enabled=False, api_key="my_key", client_id="my_id")
        self.assertFalse(cfg_disabled.is_configured())

    # 8. Successful sandbox response
    def test_08_successful_sandbox_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/xml"}
        mock_resp.text = self.sample_xml
        mock_resp.content = self.sample_xml.encode("utf-8")
        self.mock_session.post.return_value = mock_resp

        req = PANVerificationRequest(pan="ABCDE1234F")
        res = self.client.verify_pan(req)
        self.assertEqual(res.status, PANVerificationStatus.VERIFIED)
        self.assertEqual(res.pan, "ABCDE1234F")
        self.assertEqual(res.http_status, 200)

    # 9. XML response parsing
    def test_09_xml_response_parsing(self):
        res = parse_pan_verification_xml(
            xml_string=self.sample_xml,
            txn_id="TXN-001",
            http_status=200,
            queried_pan="ABCDE1234F",
        )
        self.assertEqual(res.status, PANVerificationStatus.VERIFIED)
        self.assertEqual(res.pan, "ABCDE1234F")
        self.assertEqual(res.verified_name, "Bharat Electronics Ltd")
        self.assertEqual(res.verified_dob, "15-08-1990")
        self.assertEqual(res.issuer, "Income Tax Department")

    # 10. JSON response handling
    def test_10_json_response_handling(self):
        json_payload = {
            "certificateData": {
                "panno": "XYZPK9999Z",
                "name": "Reliance Enterprises",
                "dob": "01-01-1980",
                "issuer": "Income Tax Department",
            }
        }
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.json.return_value = json_payload
        mock_resp.text = str(json_payload)
        mock_resp.content = b'{"test": 1}'
        self.mock_session.post.return_value = mock_resp

        req = PANVerificationRequest(pan="XYZPK9999Z")
        res = self.client.verify_pan(req)
        self.assertEqual(res.status, PANVerificationStatus.VERIFIED)
        self.assertEqual(res.pan, "XYZPK9999Z")
        self.assertEqual(res.verified_name, "Reliance Enterprises")

    # 11-17: Detailed field extractions
    def test_11_to_17_field_extractions(self):
        res = parse_pan_verification_xml(
            xml_string=self.sample_xml,
            txn_id="TXN-FIELD-CHECK",
            http_status=200,
            queried_pan="ABCDE1234F",
        )
        self.assertEqual(res.pan, "ABCDE1234F")                     # 11. PAN
        self.assertEqual(res.verified_name, "Bharat Electronics Ltd")# 12. Name
        self.assertEqual(res.verified_dob, "15-08-1990")           # 13. DOB
        self.assertEqual(res.issuer, "Income Tax Department")       # 14. Issuer
        self.assertEqual(res.certificate_type, "PANCR")             # 15. Type
        self.assertEqual(res.certificate_status, "A")               # 16. Status
        self.assertEqual(res.verified_on, "2023-01-15")             # 17. VerifiedOn

    # 18. Response hashing
    def test_18_response_hashing(self):
        content = self.sample_xml.encode("utf-8")
        expected_hash = hashlib.sha256(content).hexdigest()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/xml"}
        mock_resp.text = self.sample_xml
        mock_resp.content = content
        self.mock_session.post.return_value = mock_resp

        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.response_hash, expected_hash)

    # 19. Evidence creation
    def test_19_evidence_reference_creation(self):
        res = parse_pan_verification_xml(self.sample_xml, txn_id="TXN-EV", http_status=200)
        ev_ref = APISetuPANEvidenceAdapter.to_evidence_reference(res)
        self.assertEqual(ev_ref.document, "API_SETU:PANCR:ABCDE1234F")
        self.assertEqual(ev_ref.page, 1)
        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(ev_ref.extraction_method, "API_SETU_PANCR_REST")
        self.assertEqual(ev_ref.extraction_confidence, "HIGH")

    # 20. Provenance DAG integration
    def test_20_provenance_dag_integration(self):
        res = parse_pan_verification_xml(self.sample_xml, txn_id="TXN-DAG", http_status=200)
        fact = APISetuPANEvidenceAdapter.to_bidder_fact(res, bid_id="BID-001")
        dag = ProvenanceDAG(bid_id="BID-001", tender_id="TENDER-001")

        APISetuPANEvidenceAdapter.integrate_with_dag(dag, fact, res)

        self.assertIn("FACT:FACT-PAN-ABCDE1234F", dag.nodes)
        self.assertIn("BLOCK:API_SETU:PANCR:ABCDE1234F", dag.nodes)
        dag.validate()  # Validates acyclicity

    # 21. XML field path provenance
    def test_21_xml_field_paths(self):
        res = parse_pan_verification_xml(self.sample_xml, txn_id="TXN-PATHS", http_status=200)
        paths = res.xml_field_paths
        self.assertEqual(paths.get("pan"), "/Certificate/CertificateData/PAN/@num")
        self.assertEqual(paths.get("verified_name"), "/Certificate/IssuedTo/Person/@name")
        self.assertEqual(paths.get("verified_dob"), "/Certificate/IssuedTo/Person/@dob")

    # 22. No fake physical evidence
    def test_22_no_fake_physical_evidence(self):
        res = parse_pan_verification_xml(self.sample_xml, txn_id="TXN-NO-FAKE", http_status=200)
        ev_ref = APISetuPANEvidenceAdapter.to_evidence_reference(res)
        # Bbox must be strictly zero coordinates (not manufactured PDF bounding box)
        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])
        self.assertIn("API_SETU:PANCR", ev_ref.snippet)

    # 23. Contradiction / Identity mismatch with claimed bidder name
    def test_23_contradiction_with_bidder_identity(self):
        res = parse_pan_verification_xml(self.sample_xml, txn_id="TXN-MISMATCH", http_status=200)
        # Name in cert is 'Bharat Electronics Ltd'
        adapter_match = APISetuPANEvidenceAdapter.to_adapter_response(res, expected_entity_name="Bharat Electronics Ltd")
        self.assertEqual(adapter_match.status, VerificationStatus.VERIFIED)

        adapter_mismatch = APISetuPANEvidenceAdapter.to_adapter_response(res, expected_entity_name="Completely Fraudulent Co")
        self.assertEqual(adapter_mismatch.status, VerificationStatus.IDENTITY_MISMATCH)

    # 24. Deterministic replay
    def test_24_deterministic_replay(self):
        res1 = parse_pan_verification_xml(self.sample_xml, txn_id="TXN-FIXED", http_status=200)
        res2 = parse_pan_verification_xml(self.sample_xml, txn_id="TXN-FIXED", http_status=200)
        self.assertEqual(res1.to_dict(), res2.to_dict())

    # 25-31: HTTP Error mappings (400, 401, 404, 500, 502, 503, 504)
    def test_25_400_bad_request(self):
        mock_resp = MagicMock(status_code=400, text='{"error": "missing_parameter"}', json=lambda: {"error": "missing_parameter"}, content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.INVALID_REQUEST)
        self.assertEqual(res.http_status, 400)

    def test_26_401_unauthorized(self):
        mock_resp = MagicMock(status_code=401, text="Unauthorized", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.ERROR)
        self.assertEqual(res.error_code, "UNAUTHORIZED")

    def test_27_404_not_found(self):
        mock_resp = MagicMock(status_code=404, text="Not Found", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.NOT_VERIFIED)

    def test_28_500_server_error(self):
        mock_resp = MagicMock(status_code=500, text="Internal Error", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.ERROR)

    def test_29_502_bad_gateway(self):
        mock_resp = MagicMock(status_code=502, text="Bad Gateway", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.ERROR)

    def test_30_503_service_unavailable(self):
        mock_resp = MagicMock(status_code=503, text="Service Unavailable", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.ERROR)

    def test_31_504_gateway_timeout(self):
        mock_resp = MagicMock(status_code=504, text="Gateway Timeout", content=b"err")
        self.mock_session.post.return_value = mock_resp
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.ERROR)

    # 32. Timeout handling
    def test_32_timeout_handling(self):
        import requests
        self.mock_session.post.side_effect = requests.exceptions.Timeout("Read timeout")
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.UNAVAILABLE)
        self.assertEqual(res.http_status, 504)

    # 33. Network failure handling
    def test_33_network_failure_handling(self):
        import requests
        self.mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        res = self.client.verify_pan(PANVerificationRequest(pan="ABCDE1234F"))
        self.assertEqual(res.status, PANVerificationStatus.ERROR)
        self.assertEqual(res.http_status, 502)

    # 34. Malformed XML handling & XXE rejection
    def test_34_malformed_xml_and_xxe_handling(self):
        with self.assertRaises(PANXMLParsingError):
            parse_pan_verification_xml("<Invalid<XML", txn_id="TXN-BAD")

        xxe = """<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><Certificate><IssuedBy><Organization name="&xxe;"/></IssuedBy></Certificate>"""
        with self.assertRaises(PANXMLParsingError):
            parse_pan_verification_xml(xxe, txn_id="TXN-XXE")

    # 35. Secret redaction in audit logs
    def test_35_secret_redaction(self):
        logger = PANAuditLogger()
        logger.log(
            event_type="PAN_TEST",
            status="SUCCESS",
            details={
                "api_key": "super_secret_sandbox_key",
                "pan": "ABCDE1234F",
                "public_field": "ok",
            }
        )
        events = logger.get_events()
        self.assertEqual(len(events), 1)
        ev_str = str(events[0])
        self.assertNotIn("super_secret_sandbox_key", ev_str)
        self.assertIn("api_key_hash", events[0]["details"])
        self.assertIn("ABCDE***4F", events[0]["details"]["pan"])

    # 36. No PASS on external API failure
    def test_36_no_pass_on_external_api_failure(self):
        err_res = PANVerificationResponse(
            txn_id="TXN-FAIL",
            status=PANVerificationStatus.ERROR,
            http_status=500,
            pan="ABCDE1234F",
            error_message="Gateway crash",
        )
        adapter_res = APISetuPANEvidenceAdapter.to_adapter_response(err_res)
        # External error MUST NEVER convert to VERIFIED
        self.assertNotEqual(adapter_res.status, VerificationStatus.VERIFIED)
        self.assertEqual(adapter_res.status, VerificationStatus.REVIEW)


class TestPANFastAPIRouter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_37_pan_status_endpoint(self):
        resp = self.client.get("/api/v1/integrations/pan/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("enabled", data)
        self.assertIn("base_url", data)
        self.assertIn("endpoint", data)

    def test_38_pan_verify_endpoint_invalid_format(self):
        payload = {"pan": "INVALID_PAN_FORMAT"}
        resp = self.client.post("/api/v1/integrations/pan/verify", json=payload)
        self.assertEqual(resp.status_code, 400)

    @patch.object(APISetuPANClient, "verify_pan")
    def test_39_pan_verify_endpoint_success(self, mock_verify):
        mock_verify.return_value = PANVerificationResponse(
            txn_id="TXN-API-TEST",
            status=PANVerificationStatus.VERIFIED,
            http_status=200,
            pan="ABCDE1234F",
            verified_name="National Systems",
            issuer="Income Tax Department",
            certificate_status="ACTIVE",
        )

        payload = {
            "pan": "ABCDE1234F",
            "full_name": "National Systems",
            "convert_to_bidder_fact": True,
        }
        resp = self.client.post("/api/v1/integrations/pan/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(data["pan"], "ABCDE1234F")
        self.assertIn("bidder_fact", data)
        self.assertEqual(data["bidder_fact"]["field"], "pan")

    @patch("backend.integrations.pan.client.APISetuPANClient.verify_pan")
    def test_40_pan_verify_endpoint_unverified_no_bidder_fact(self, mock_verify):
        mock_verify.return_value = PANVerificationResponse(
            txn_id="TXN-API-FAIL",
            status=PANVerificationStatus.NOT_VERIFIED,
            http_status=404,
            pan="ABCDE9999Z",
            error_message="PAN not found",
        )

        payload = {
            "pan": "ABCDE9999Z",
            "convert_to_bidder_fact": True,
        }
        resp = self.client.post("/api/v1/integrations/pan/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "NOT_VERIFIED")
        self.assertIsNone(data["bidder_fact"], "Unverified PAN must NEVER produce a BidderFact")


if __name__ == "__main__":
    unittest.main()
