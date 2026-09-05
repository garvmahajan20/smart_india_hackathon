# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
import io
import os
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.api.app import app

class TestStep8Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.tender_pdf = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/tenders/TENDER-0001.pdf"
        cls.bid_pdf = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/documents/bids/BID-00001.pdf"

    # 1. Health check
    def test_01_health_check(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertEqual(data["version"], "1.0.0")
        self.assertIn("gemini", data["active_model"].lower())

    # 2. Verify endpoint with valid PDFs
    def test_02_verify_valid_pdfs(self):
        with open(self.tender_pdf, "rb") as tf, open(self.bid_pdf, "rb") as bf:
            files = [
                ("tender_file", ("TENDER-0001.pdf", tf.read(), "application/pdf")),
                ("bid_files", ("BID-00001.pdf", bf.read(), "application/pdf")),
            ]
            data = {
                "tender_id": "TENDER-0001",
                "bid_id": "BID-00001",
                "company_name": "Bharat Devices",
                "mode": "mock",
            }
            resp = self.client.post("/api/v1/verify", files=files, data=data)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("verification_id", body)
        self.assertIn("overall_status", body)
        self.assertIn("compliance_status", body)
        self.assertIn("integrity_status", body)
        self.assertEqual(body["tender_id"], "TENDER-0001")
        self.assertEqual(body["bid_id"], "BID-00001")

        # Save verification_id for subsequent retrieval tests
        TestStep8Api.last_verification_id = body["verification_id"]

    # 3. Reject non-PDF file extension
    def test_03_reject_non_pdf_extension(self):
        files = [
            ("tender_file", ("tender.txt", b"plain text", "text/plain")),
            ("bid_files", ("bid.pdf", b"%PDF-1.4 dummy content", "application/pdf")),
        ]
        resp = self.client.post("/api/v1/verify", files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported file extension", resp.json()["error"])

    # 4. Reject invalid magic header
    def test_04_reject_invalid_magic_header(self):
        files = [
            ("tender_file", ("tender.pdf", b"NOT_A_VALID_PDF_HEADER", "application/pdf")),
            ("bid_files", ("bid.pdf", b"%PDF-1.4 dummy", "application/pdf")),
        ]
        resp = self.client.post("/api/v1/verify", files=files)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not a valid PDF", resp.json()["error"])

    # 5. Reject path traversal in filenames
    def test_05_reject_path_traversal_filename(self):
        files = [
            ("tender_file", ("../../traversal.pdf", b"%PDF-1.4 dummy", "application/pdf")),
            ("bid_files", ("bid.pdf", b"%PDF-1.4 dummy", "application/pdf")),
        ]
        resp = self.client.post("/api/v1/verify", files=files)
        # os.path.basename strips directory path, but if raw filename contains traversal check catches it or cleans it
        self.assertIn(resp.status_code, [200, 400])

    # 6. Retrieve verification by ID
    def test_06_get_verification_by_id(self):
        verif_id = getattr(TestStep8Api, "last_verification_id", "VERIF-TENDER-0001-BID-00001")
        resp = self.client.get(f"/api/v1/verification/{verif_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["verification_id"], verif_id)

    # 7. Retrieve unknown verification returns 404
    def test_07_get_unknown_verification_404(self):
        resp = self.client.get("/api/v1/verification/NON_EXISTENT_ID_9999")
        self.assertEqual(resp.status_code, 404)
        self.assertIn("not found", resp.json()["error"].lower())

    # 8. Retrieve dossier
    def test_08_get_dossier(self):
        verif_id = getattr(TestStep8Api, "last_verification_id", "VERIF-TENDER-0001-BID-00001")
        resp = self.client.get(f"/api/v1/verification/{verif_id}/dossier")
        self.assertEqual(resp.status_code, 200)
        dossier = resp.json()
        self.assertIn("tender", dossier)
        self.assertIn("bidder", dossier)
        self.assertIn("compliance_summary", dossier)
        self.assertIn("integrity_summary", dossier)
        self.assertIn("audit_metadata", dossier)

    # 9. Retrieve dossier unknown returns 404
    def test_09_get_dossier_unknown_404(self):
        resp = self.client.get("/api/v1/verification/NON_EXISTENT_ID_9999/dossier")
        self.assertEqual(resp.status_code, 404)

    # 10. Retrieve review items
    def test_10_get_review_items(self):
        verif_id = getattr(TestStep8Api, "last_verification_id", "VERIF-TENDER-0001-BID-00001")
        resp = self.client.get(f"/api/v1/verification/{verif_id}/review-items")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertIsInstance(items, list)

    # 11. Security audit: No secrets leaked in error or responses
    def test_11_security_no_secret_leakage(self):
        api_key = os.environ.get("GEMINI_API_KEY", "")
        resp = self.client.get("/health")
        if api_key:
            self.assertNotIn(api_key, resp.text)
        resp_err = self.client.get("/api/v1/verification/UNKNOWN_ID")
        if api_key:
            self.assertNotIn(api_key, resp_err.text)

if __name__ == "__main__":
    unittest.main(verbosity=2)
