# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite for DigiLocker / API Setu Sandbox Integration.
Covers:
- PKCE generation, validation, S256 challenge, state management, and TTL expiry
- Official API Setu XML parsing (PullDocResponse, direct Certificate, DocContent Base64 PDF, XXE safety)
- Sandbox HTTP client operations (authorization URL, token exchange, user info, document listing, pull, revoke)
- Evidence adaptation to BidderFact and EvidenceReference schemas
- ProvenanceDAG acyclicity and invariant validation
- Deterministic audit logger with strict zero secret leakage
- FastAPI endpoints via TestClient
"""

import base64
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.api.app import app
from backend.core.provenance_dag import ProvenanceDAG
from backend.integrations.digilocker import (
    DigiLockerAuditEvent,
    DigiLockerAuditLogger,
    DigiLockerAuthError,
    DigiLockerClientError,
    DigiLockerConfig,
    DigiLockerEvidenceAdapter,
    DigiLockerNetworkError,
    DigiLockerParsedCertificate,
    DigiLockerPulledDocument,
    DigiLockerSandboxClient,
    DigiLockerTokenResponse,
    DigiLockerUserDetails,
    DigiLockerXMLParsingError,
    PKCEStateStore,
    default_audit_logger,
    default_pkce_store,
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
    hash_token,
    mask_sensitive_id,
    parse_digilocker_certificate_xml,
    parse_pull_doc_response,
    verify_code_challenge,
)
from backend.verification.models import VerificationStatus


class TestDigiLockerPKCE(unittest.TestCase):
    """Tests for RFC 7636 PKCE cryptographic implementation."""

    def test_01_code_verifier_length_constraints(self):
        verifier_64 = generate_code_verifier(64)
        self.assertEqual(len(verifier_64), 64)

        verifier_43 = generate_code_verifier(43)
        self.assertEqual(len(verifier_43), 43)

        verifier_128 = generate_code_verifier(128)
        self.assertEqual(len(verifier_128), 128)

        # Rejects length < 43 or > 128
        with self.assertRaises(ValueError):
            generate_code_verifier(42)
        with self.assertRaises(ValueError):
            generate_code_verifier(129)

    def test_02_code_challenge_derivation(self):
        verifier = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        # Known S256 transformation: SHA256 base64url without padding '='
        challenge = generate_code_challenge(verifier)
        self.assertNotIn("=", challenge)
        self.assertNotIn("+", challenge)
        self.assertNotIn("/", challenge)
        self.assertTrue(verify_code_challenge(verifier, challenge))

    def test_03_code_challenge_verification_negative(self):
        verifier = generate_code_verifier(64)
        challenge = generate_code_challenge(verifier)
        # Tampered verifier must fail constant-time comparison
        tampered = verifier[:-1] + ("A" if verifier[-1] != "A" else "B")
        self.assertFalse(verify_code_challenge(tampered, challenge))
        self.assertFalse(verify_code_challenge("", challenge))
        self.assertFalse(verify_code_challenge(verifier, ""))

    def test_04_pkce_state_store_lifecycle(self):
        store = PKCEStateStore(ttl_seconds=2)
        state = generate_state()
        verifier = generate_code_verifier(64)

        store.store(state, verifier, metadata={"scope": "openid"})
        # Peek does not consume
        entry = store.peek(state)
        self.assertIsNotNone(entry)
        self.assertEqual(entry["verifier"], verifier)

        # Pop consumes state (one-time use)
        popped = store.pop(state)
        self.assertEqual(popped, verifier)
        self.assertIsNone(store.pop(state))

    def test_05_pkce_state_store_expiry(self):
        store = PKCEStateStore(ttl_seconds=0.01)
        state = generate_state()
        store.store(state, "some_verifier")
        import time
        time.sleep(0.05)
        # Should be expired
        self.assertIsNone(store.pop(state))


class TestDigiLockerXMLParser(unittest.TestCase):
    """Tests for official API Setu and DigiLocker XML specifications."""

    def setUp(self):
        self.sample_cert_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <Certificate name="Udyam Registration" type="UDYAM" number="UDYAM-MH-01-0099887"
                     status="A" issueDate="2023-01-15" validFromDate="2023-01-15" expiryDate="2030-12-31">
            <IssuedBy>
                <Organization name="Ministry of Micro, Small and Medium Enterprises" code="MSME"/>
            </IssuedBy>
            <IssuedTo>
                <Person name="Sunita Sharma" uid="XXXX-XXXX-9876"/>
                <Organization name="TechnoCraft Solutions Pvt Ltd" type="PRIVATE_LIMITED"/>
            </IssuedTo>
            <CertificateData>
                <EnterpriseType>SMALL</EnterpriseType>
                <MajorActivity>MANUFACTURING</MajorActivity>
                <IncorporationDate>2019-03-10</IncorporationDate>
            </CertificateData>
        </Certificate>
        """

    def test_06_parse_certificate_xml(self):
        cert = parse_digilocker_certificate_xml(self.sample_cert_xml)
        self.assertEqual(cert.certificate_type, "UDYAM")
        self.assertEqual(cert.certificate_number, "UDYAM-MH-01-0099887")
        self.assertEqual(cert.status, "A")
        self.assertTrue(cert.is_valid)
        self.assertEqual(cert.issuer_name, "Ministry of Micro, Small and Medium Enterprises")
        self.assertEqual(cert.recipient_name, "Sunita Sharma")
        self.assertEqual(cert.recipient_organization, "TechnoCraft Solutions Pvt Ltd")
        self.assertEqual(cert.certificate_data.get("EnterpriseType"), "SMALL")
        self.assertEqual(cert.certificate_data.get("MajorActivity"), "MANUFACTURING")

    def test_07_parse_pull_doc_response_envelope(self):
        # Create dummy PDF bytes
        dummy_pdf = b"%PDF-1.5 test content for DigiLocker"
        b64_pdf = base64.b64encode(dummy_pdf).decode("ascii")
        b64_xml = base64.b64encode(self.sample_cert_xml.encode("utf-8")).decode("ascii")

        envelope_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <PullDocResponse xmlns="http://tempuri.org/">
            <ResponseStatus status="1" ts="2026-09-06T12:00:00Z" txn="TXN-12345">Success</ResponseStatus>
            <DocDetails>
                <DocContent>{b64_pdf}</DocContent>
                <DataContent>{b64_xml}</DataContent>
            </DocDetails>
        </PullDocResponse>
        """

        pdf_bytes, cert, metadata = parse_pull_doc_response(envelope_xml)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertIsNotNone(cert)
        self.assertEqual(cert.certificate_number, "UDYAM-MH-01-0099887")
        self.assertEqual(metadata.get("response_status"), "1")
        self.assertEqual(metadata.get("txn"), "TXN-12345")

    def test_08_xxe_attack_prevention(self):
        xxe_xml = """<?xml version="1.0" encoding="ISO-8859-1"?>
        <!DOCTYPE foo [ <!ELEMENT foo ANY >
        <!ENTITY xxe SYSTEM "file:///etc/passwd" >]>
        <Certificate name="Attack" type="UDYAM" number="123">
            <IssuedBy><Organization name="&xxe;" code="MSME"/></IssuedBy>
        </Certificate>
        """
        with self.assertRaises(DigiLockerXMLParsingError) as ctx:
            parse_digilocker_certificate_xml(xxe_xml)
        self.assertIn("DOCTYPE", str(ctx.exception))

    def test_09_malformed_xml_handling(self):
        with self.assertRaises(DigiLockerXMLParsingError):
            parse_digilocker_certificate_xml("<IncompleteXmlTag")
        with self.assertRaises(DigiLockerXMLParsingError):
            parse_pull_doc_response("")


class TestDigiLockerSandboxClient(unittest.TestCase):
    """Tests for DigiLockerSandboxClient HTTP requests and error handling."""

    def setUp(self):
        self.config = DigiLockerConfig(
            enabled=True,
            environment="sandbox",
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8000/api/v1/integrations/digilocker/callback",
            base_url="https://sandbox.api-setu.in",
        )
        self.audit_logger = DigiLockerAuditLogger()
        self.mock_session = MagicMock()
        self.client = DigiLockerSandboxClient(
            config=self.config,
            audit_logger=self.audit_logger,
            session=self.mock_session,
        )

    def test_10_authorization_url_construction(self):
        res = self.client.get_authorization_url(scope="openid profile")
        url = res["url"]
        self.assertTrue(url.startswith("https://sandbox.api-setu.in/api/v1/digilocker/oauth/authorize"))
        self.assertIn("client_id=test_client_id", url)
        self.assertIn("response_type=code", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn(f"state={res['state']}", url)
        self.assertIn(f"code_challenge={res['code_challenge']}", url)

    def test_11_exchange_code_success(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "mock_access_token_12345",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "openid",
            "digilockerid": "DL-USER-8888",
        }
        self.mock_session.post.return_value = mock_resp

        token_resp = self.client.exchange_code(code="test_code", code_verifier="test_verifier_string_43chars_min_length_here_now")
        self.assertEqual(token_resp.access_token, "mock_access_token_12345")
        self.assertEqual(token_resp.token_type, "Bearer")
        self.assertEqual(token_resp.digilocker_id, "DL-USER-8888")

        # Verify audit log recorded without leaking token
        events = self.audit_logger.get_events("OAUTH_TOKEN_EXCHANGED")
        self.assertEqual(len(events), 1)
        self.assertNotIn("mock_access_token_12345", str(events[0]))
        self.assertIn("access_token_hash", events[0]["details"])

    def test_12_exchange_code_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = '{"error": "invalid_grant"}'
        self.mock_session.post.return_value = mock_resp

        with self.assertRaises(DigiLockerAuthError):
            self.client.exchange_code(code="invalid_code", code_verifier="verifier")

    def test_13_get_user_details(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "digilockerid": "DL-USR-9999",
            "name": "Rajesh Sharma",
            "dob": "1985-05-12",
            "gender": "M",
            "mobile": "9876543210",
        }
        self.mock_session.get.return_value = mock_resp

        user = self.client.get_user_details("test_access_token")
        self.assertEqual(user.digilocker_id, "DL-USR-9999")
        self.assertEqual(user.name, "Rajesh Sharma")
        self.assertEqual(user.dob, "1985-05-12")

    def test_14_get_issued_documents(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "uri": "in.gov.msme-UDYAM-001",
                    "name": "Udyam Registration",
                    "type": "UDYAM",
                    "date": "2023-01-10",
                    "issuer": "Ministry of MSME",
                }
            ]
        }
        self.mock_session.get.return_value = mock_resp

        docs = self.client.get_issued_documents("test_access_token")
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0].uri, "in.gov.msme-UDYAM-001")
        self.assertEqual(docs[0].doc_type, "UDYAM")

    def test_15_pull_document_xml(self):
        cert_xml = """<Certificate name="GST" type="GST" number="27AAAAA0000A1Z5" status="A">
            <IssuedBy><Organization name="GSTN" code="GSTN"/></IssuedBy>
            <IssuedTo><Organization name="Bharat Electronics Ltd"/></IssuedTo>
        </Certificate>"""

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"Content-Type": "application/xml"}
        mock_resp.text = cert_xml
        mock_resp.content = cert_xml.encode("utf-8")
        self.mock_session.post.return_value = mock_resp

        pulled = self.client.pull_document("test_token", "in.gov.gstn-GST-001")
        self.assertIsNotNone(pulled.certificate)
        self.assertEqual(pulled.certificate.certificate_type, "GST")
        self.assertEqual(pulled.certificate.certificate_number, "27AAAAA0000A1Z5")

    def test_16_revoke_token(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        self.mock_session.post.return_value = mock_resp

        revoked = self.client.revoke_token("test_token_to_revoke")
        self.assertTrue(revoked)


class TestDigiLockerEvidenceAdapterAndDAG(unittest.TestCase):
    """Tests for EvidenceAdapter, BidderFact synthesis, and ProvenanceDAG integration."""

    def setUp(self):
        self.cert = DigiLockerParsedCertificate(
            certificate_type="UDYAM",
            certificate_name="Udyam Registration Certificate",
            certificate_number="UDYAM-DL-02-0011223",
            issue_date="2022-06-01",
            status="A",
            issuer_name="Ministry of MSME",
            issuer_code="MSME",
            recipient_name="Apex Technologies",
            recipient_organization="Apex Technologies",
            certificate_data={"EnterpriseType": "MICRO"},
        )

    def test_17_certificate_to_evidence_reference(self):
        ev_ref = DigiLockerEvidenceAdapter.certificate_to_evidence_reference(self.cert)
        self.assertEqual(ev_ref.page, 1)
        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])
        self.assertIn("Apex Technologies", ev_ref.snippet)
        self.assertIn("UDYAM-DL-02-0011223", ev_ref.document)
        self.assertEqual(ev_ref.extraction_method, "DIGILOCKER_AUTHORITATIVE_API")

    def test_18_certificate_to_bidder_fact(self):
        fact = DigiLockerEvidenceAdapter.certificate_to_bidder_fact(self.cert, bid_id="BID-001")
        self.assertEqual(fact.bid_id, "BID-001")
        self.assertEqual(fact.field, "msme_registration_number")
        self.assertEqual(fact.value, "UDYAM-DL-02-0011223")
        self.assertEqual(fact.canonical_field, "MSME_REGISTRATION")
        self.assertEqual(fact.extraction_confidence, "HIGH")
        self.assertEqual(len(fact.evidence), 1)
        self.assertEqual(fact.evidence[0]["source_type"], "DIGILOCKER_OFFICIAL_REGISTRY")

    def test_19_dag_integration_and_acyclicity(self):
        dag = ProvenanceDAG(bid_id="BID-001", tender_id="TENDER-001")
        fact = DigiLockerEvidenceAdapter.certificate_to_bidder_fact(self.cert, bid_id="BID-001")

        # Register into DAG
        DigiLockerEvidenceAdapter.integrate_with_dag(dag, fact, self.cert)

        # Invariant checks:
        # Fact node and External block node must exist
        self.assertIn(f"FACT:{fact.fact_id}", dag.nodes)
        self.assertIn(f"BLOCK:DIGILOCKER:UDYAM:{self.cert.certificate_number}", dag.nodes)

        # Graph must be valid and acyclic
        dag.validate()

    def test_20_to_adapter_response(self):
        resp = DigiLockerEvidenceAdapter.to_adapter_response(
            self.cert,
            queried_identifier="UDYAM-DL-02-0011223",
            expected_entity_name="Apex Technologies",
        )
        self.assertEqual(resp.status, VerificationStatus.VERIFIED)
        self.assertFalse(resp.is_mock)
        self.assertEqual(resp.registered_entity_name, "Apex Technologies")

        # Mismatch entity check
        mismatch_resp = DigiLockerEvidenceAdapter.to_adapter_response(
            self.cert,
            queried_identifier="UDYAM-DL-02-0011223",
            expected_entity_name="Completely Different Corp",
        )
        self.assertEqual(mismatch_resp.status, VerificationStatus.IDENTITY_MISMATCH)


class TestDigiLockerAuditSecurity(unittest.TestCase):
    """Tests for zero secret leakage in audit logger."""

    def test_21_zero_secret_leakage(self):
        logger = DigiLockerAuditLogger()
        raw_secret = "super_secret_client_key_99999"
        raw_token = "eyJhGciOi...BearerTokenHere..."
        raw_verifier = "random_pkce_verifier_long_string_abc"

        logger.log(
            event_type="OAUTH_TOKEN_EXCHANGED",
            status="SUCCESS",
            details={
                "client_secret": raw_secret,
                "access_token": raw_token,
                "code_verifier": raw_verifier,
                "public_info": "safe_data",
            }
        )

        events = logger.get_events()
        self.assertEqual(len(events), 1)
        event_str = str(events[0])

        # Raw secrets MUST NOT be present
        self.assertNotIn(raw_secret, event_str)
        self.assertNotIn(raw_token, event_str)
        self.assertNotIn(raw_verifier, event_str)

        # Hashes MUST be present for correlation
        self.assertIn("client_secret_hash", events[0]["details"])
        self.assertIn("access_token_hash", events[0]["details"])
        self.assertIn("code_verifier_hash", events[0]["details"])


class TestDigiLockerFastAPIRouter(unittest.TestCase):
    """Tests for FastAPI endpoints under /api/v1/integrations/digilocker/."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_22_status_endpoint(self):
        resp = self.client.get("/api/v1/integrations/digilocker/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("enabled", data)
        self.assertIn("environment", data)
        self.assertIn("base_url", data)

    def test_23_authorize_endpoint(self):
        resp = self.client.get("/api/v1/integrations/digilocker/authorize")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("authorization_url", data)
        self.assertIn("state", data)
        self.assertIn("code_challenge", data)
        self.assertIn("sandbox.api-setu.in", data["authorization_url"])

        # Check state was stored in PKCEStateStore
        self.assertIsNotNone(default_pkce_store.peek(data["state"]))

    def test_24_callback_endpoint_invalid_state(self):
        # Passing an invalid state must return HTTP 400
        resp = self.client.get("/api/v1/integrations/digilocker/callback?code=testcode&state=nonexistent_state")
        self.assertEqual(resp.status_code, 400)
        err_msg = (resp.json().get("error") or resp.json().get("detail") or "").lower()
        self.assertIn("state", err_msg)

    def test_25_callback_endpoint_error_from_provider(self):
        resp = self.client.get("/api/v1/integrations/digilocker/callback?error=access_denied&error_description=User+denied+consent")
        self.assertEqual(resp.status_code, 400)
        err_msg = (resp.json().get("error") or resp.json().get("detail") or "").lower()
        self.assertIn("denied", err_msg)

    @patch.object(DigiLockerSandboxClient, "exchange_code")
    def test_26_callback_endpoint_success(self, mock_exchange):
        # Register a state in store
        state = generate_state()
        verifier = generate_code_verifier(64)
        default_pkce_store.store(state, verifier)

        mock_exchange.return_value = DigiLockerTokenResponse(
            access_token="mock_valid_token_xyz",
            token_type="Bearer",
            expires_in=3600,
            scope="openid",
            digilocker_id="DL-00123",
        )

        resp = self.client.get(f"/api/v1/integrations/digilocker/callback?code=validcode&state={state}")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertEqual(data["digilocker_id"], "DL-00123")
        self.assertEqual(data["access_token"], "mock_valid_token_xyz")

    @patch.object(DigiLockerSandboxClient, "get_user_details")
    def test_27_user_endpoint(self, mock_get_user):
        mock_get_user.return_value = DigiLockerUserDetails(
            digilocker_id="DL-7777",
            name="Pooja Verma",
            dob="1990-01-01",
        )

        resp = self.client.get(
            "/api/v1/integrations/digilocker/user",
            headers={"Authorization": "Bearer mock_token_abc"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["name"], "Pooja Verma")
        self.assertEqual(data["digilocker_id"], "DL-7777")

    @patch.object(DigiLockerSandboxClient, "pull_document")
    def test_28_pull_endpoint_with_fact_conversion(self, mock_pull):
        cert = DigiLockerParsedCertificate(
            certificate_type="GST",
            certificate_name="GST Registration",
            certificate_number="07AAAAA1111A1Z1",
            issuer_name="GSTN",
            recipient_name="Test Company",
            status="A",
        )
        mock_pull.return_value = DigiLockerPulledDocument(
            doc_uri="in.gov.gstn-001",
            doc_type="GST",
            certificate=cert,
        )

        payload = {
            "doc_uri": "in.gov.gstn-001",
            "doc_type": "GST",
            "token": "test_token",
            "bid_id": "BID-999",
            "convert_to_bidder_fact": True,
        }

        resp = self.client.post("/api/v1/integrations/digilocker/pull", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["doc_uri"], "in.gov.gstn-001")
        self.assertIn("bidder_fact", data)
        self.assertEqual(data["bidder_fact"]["field"], "gstin")
        self.assertEqual(data["bidder_fact"]["value"], "07AAAAA1111A1Z1")

    def test_29_audit_logs_endpoint(self):
        resp = self.client.get("/api/v1/integrations/digilocker/audit-logs")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("count", data)
        self.assertIn("events", data)


if __name__ == "__main__":
    unittest.main()
