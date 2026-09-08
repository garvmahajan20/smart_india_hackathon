# -*- coding: utf-8 -*-
"""
Comprehensive Test Suite for Deterministic Government Mock Registries.
Covers:
- Income Tax Department / ITR (MOCK_ITD)
- MCA21 Corporate Registry (MOCK_MCA21)
- NSIC Small Industries Registry (MOCK_NSIC)
- OEM Authorization Registry (MOCK_OEM)
- Make in India / Local Content Registry (MOCK_MII)
- Evidence and BidderFact Transformation (MockRegistryEvidenceAdapter)
- Provenance DAG Acyclicity and Integration
- FastAPI REST Router Endpoints
- Deterministic Replay (Zero Network Calls)
- Scenarios A through H
"""

import unittest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.models import BidderFact
from backend.core.provenance_dag import ProvenanceDAG
from backend.verification import (
    MockGovernmentRegistry,
    MockITDAdapter,
    MockMCA21Adapter,
    MockNSICAdapter,
    MockOEMAdapter,
    MockMIIAdapter,
    MockRegistryEvidenceAdapter,
    VerificationStatus,
)


class TestMockGovernmentRegistries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = MockGovernmentRegistry.get_instance()

    # ======================================================================
    # 1. Registry Fixture & Dataset Metadata Tests
    # ======================================================================
    def test_registry_metadata(self):
        self.assertEqual(self.registry.SOURCE_TYPE, "INTERNAL_MOCK_REGISTRY")
        self.assertEqual(self.registry.DATASET_VERSION, "MOCK_REGISTRY_DATASET_V1")
        self.assertGreaterEqual(len(self.registry.itd_records), 4)
        self.assertGreaterEqual(len(self.registry.mca_records), 4)
        self.assertGreaterEqual(len(self.registry.nsic_records), 3)
        self.assertGreaterEqual(len(self.registry.oem_records), 3)
        self.assertGreaterEqual(len(self.registry.mii_records), 3)

    # ======================================================================
    # 2. Income Tax Department (MOCK_ITD) Adapter Tests
    # ======================================================================
    def test_itd_adapter_verified_scenario_a(self):
        adapter = MockITDAdapter()
        res = adapter.verify("SYNPA0001A", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.source, "MOCK_ITD")
        self.assertTrue(res.is_mock)
        self.assertEqual(res.registered_entity_name, "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        self.assertEqual(res.registration_status, "FILED")
        self.assertEqual(res.matched_entity["turnover_cr"], 25.0)
        self.assertEqual(res.matched_entity["ack_number"], "ITR-ACK-2024-00019283")
        self.assertGreater(len(res.evidence), 0)
        self.assertEqual(res.evidence[0]["source_type"], "INTERNAL_MOCK_REGISTRY")
        self.assertEqual(res.evidence[0]["dataset_version"], "MOCK_REGISTRY_DATASET_V1")

    def test_itd_adapter_by_ack_number(self):
        adapter = MockITDAdapter()
        res = adapter.verify("ITR-ACK-2024-00019283", expected_entity_name="Synthetic Bharat Systems")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.matched_entity["pan"], "SYNPA0001A")

    def test_itd_adapter_not_filed_scenario_b(self):
        adapter = MockITDAdapter()
        res = adapter.verify("SYNPA0002B", expected_entity_name="SYNTHETIC DEFAULTER ENTERPRISES PRIVATE LIMITED")
        self.assertEqual(res.status, VerificationStatus.INACTIVE)
        self.assertIn("NOT FILED", res.reason)
        self.assertEqual(res.registration_status, "NOT_FILED")

    def test_itd_adapter_identity_mismatch(self):
        adapter = MockITDAdapter()
        res = adapter.verify("SYNPA0001A", expected_entity_name="Totally Different Corporation")
        self.assertEqual(res.status, VerificationStatus.IDENTITY_MISMATCH)
        self.assertIn("does not match", res.reason)

    def test_itd_adapter_not_found(self):
        adapter = MockITDAdapter()
        res = adapter.verify("ZZZZZ9999Z")
        self.assertEqual(res.status, VerificationStatus.NOT_FOUND)
        self.assertIsNone(res.matched_entity)

    # ======================================================================
    # 3. MCA21 Corporate Registry (MOCK_MCA21) Adapter Tests
    # ======================================================================
    def test_mca_adapter_verified(self):
        adapter = MockMCA21Adapter()
        res = adapter.verify("U72900DL2019PTC100001", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.source, "MOCK_MCA21")
        self.assertTrue(res.is_mock)
        self.assertEqual(res.matched_entity["company_name"], "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        self.assertEqual(res.matched_entity["status"], "ACTIVE")

    def test_mca_adapter_inactive_status(self):
        adapter = MockMCA21Adapter()
        res = adapter.verify("U72900WB2015PTC100009")
        self.assertEqual(res.status, VerificationStatus.INACTIVE)

    def test_mca_adapter_identity_mismatch_scenario_c(self):
        adapter = MockMCA21Adapter()
        res = adapter.verify("U72900KA2021PTC100003", expected_entity_name="DIFFERENT CLAIMED BIDDER")
        self.assertEqual(res.status, VerificationStatus.IDENTITY_MISMATCH)
        self.assertIn("differs from claimed", res.reason)

    def test_mca_adapter_not_found(self):
        adapter = MockMCA21Adapter()
        res = adapter.verify("U99999XX9999PTC000000")
        self.assertEqual(res.status, VerificationStatus.NOT_FOUND)

    # ======================================================================
    # 4. NSIC Small Industries Registry (MOCK_NSIC) Adapter Tests
    # ======================================================================
    def test_nsic_adapter_verified(self):
        adapter = MockNSICAdapter()
        res = adapter.verify("NSIC-MUM-2024-001", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.source, "MOCK_NSIC")
        self.assertEqual(res.matched_entity["enterprise_name"], "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        self.assertEqual(res.matched_entity["category"], "MICRO")

    def test_nsic_adapter_expired_scenario_d(self):
        adapter = MockNSICAdapter()
        res = adapter.verify("NSIC-DEL-2021-004", expected_entity_name="SYNTHETIC EXPIRED NSIC WORKSHOP")
        self.assertEqual(res.status, VerificationStatus.INACTIVE)
        self.assertIn("expired", res.reason.lower())

    def test_nsic_adapter_identity_mismatch(self):
        adapter = MockNSICAdapter()
        res = adapter.verify("NSIC-MUM-2024-001", expected_entity_name="EPSILON SYSTEM INC")
        self.assertEqual(res.status, VerificationStatus.IDENTITY_MISMATCH)

    def test_nsic_adapter_not_found(self):
        adapter = MockNSICAdapter()
        res = adapter.verify("NSIC-FAKE-999")
        self.assertEqual(res.status, VerificationStatus.NOT_FOUND)

    # ======================================================================
    # 5. OEM Authorization Registry (MOCK_OEM) Adapter Tests
    # ======================================================================
    def test_oem_adapter_verified(self):
        adapter = MockOEMAdapter()
        res = adapter.verify("OEM-AUTH-HP-2025-001", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.source, "MOCK_OEM")
        self.assertEqual(res.matched_entity["oem_name"], "HEWLETT PACKARD ENTERPRISE INDIA")
        self.assertEqual(res.matched_entity["status"], "ACTIVE")

    def test_oem_adapter_pair_lookup(self):
        adapter = MockOEMAdapter()
        res = adapter.verify("NOT_AN_AUTH_ID", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED", oem_name="HEWLETT PACKARD ENTERPRISE INDIA")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.matched_entity["auth_number"], "OEM-AUTH-HP-2025-001")

    def test_oem_adapter_expired_scenario_e(self):
        adapter = MockOEMAdapter()
        res = adapter.verify("OEM-AUTH-DELL-2023-005", expected_entity_name="SYNTHETIC RESELLER NETWORK LTD")
        self.assertEqual(res.status, VerificationStatus.INACTIVE)
        self.assertIn("expired", res.reason.lower())

    def test_oem_adapter_unauthorized_revoked(self):
        adapter = MockOEMAdapter()
        res = adapter.verify("OEM-AUTH-CISCO-2024-008")
        self.assertEqual(res.status, VerificationStatus.REVIEW)
        self.assertIn("unauthorized", res.reason.lower())

    def test_oem_adapter_not_found(self):
        adapter = MockOEMAdapter()
        res = adapter.verify("OEM-NONEXISTENT")
        self.assertEqual(res.status, VerificationStatus.NOT_FOUND)

    # ======================================================================
    # 6. Make in India / Local Content (MOCK_MII) Adapter Tests
    # ======================================================================
    def test_mii_adapter_verified_class_1(self):
        adapter = MockMIIAdapter()
        res = adapter.verify("MII-DECL-2025-001", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.source, "MOCK_MII")
        self.assertEqual(res.matched_entity["local_content_percentage"], 65.0)
        self.assertEqual(res.matched_entity["supplier_class"], "CLASS_1")

    def test_mii_adapter_below_threshold_scenario_f(self):
        adapter = MockMIIAdapter()
        res = adapter.verify("MII-DECL-2025-006", expected_entity_name="SYNTHETIC LOW CONTENT IMPORTS LTD")
        self.assertEqual(res.status, VerificationStatus.VERIFIED)
        self.assertEqual(res.matched_entity["local_content_percentage"], 35.0)
        self.assertEqual(res.matched_entity["supplier_class"], "CLASS_2")

    def test_mii_adapter_expired(self):
        adapter = MockMIIAdapter()
        res = adapter.verify("MII-DECL-2022-010")
        self.assertEqual(res.status, VerificationStatus.INACTIVE)
        self.assertIn("expired", res.reason.lower())

    def test_mii_adapter_not_found(self):
        adapter = MockMIIAdapter()
        res = adapter.verify("MII-DOES-NOT-EXIST")
        self.assertEqual(res.status, VerificationStatus.NOT_FOUND)

    # ======================================================================
    # 7. Mock Evidence & BidderFact Adapter Tests
    # ======================================================================
    def test_evidence_adapter_reference_metadata(self):
        adapter = MockITDAdapter()
        res = adapter.verify("SYNPA0001A", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        ev_ref = MockRegistryEvidenceAdapter.to_evidence_reference(res)

        self.assertEqual(ev_ref.bbox, [0.0, 0.0, 0.0, 0.0])
        self.assertEqual(ev_ref.page, 1)
        self.assertEqual(ev_ref.document, "MOCK_ITD:SYNPA0001A")
        self.assertEqual(ev_ref.extraction_confidence, "HIGH")
        self.assertEqual(ev_ref.extraction_method, "INTERNAL_MOCK_REGISTRY_LOOKUP")

    def test_evidence_adapter_fact_gating_invariant(self):
        """
        CRITICAL INVARIANT:
        Non-verified or failed adapter responses MUST return 0 facts.
        """
        itd = MockITDAdapter()
        # 1. NOT_FOUND returns []
        not_found_res = itd.verify("ZZZZZ9999Z")
        facts = MockRegistryEvidenceAdapter.to_bidder_facts(not_found_res, bid_id="BID-001")
        self.assertEqual(len(facts), 0)

        # 2. INACTIVE returns []
        inactive_res = itd.verify("SYNPA0002B")
        facts = MockRegistryEvidenceAdapter.to_bidder_facts(inactive_res, bid_id="BID-001")
        self.assertEqual(len(facts), 0)

        # 3. IDENTITY_MISMATCH returns []
        mismatch_res = itd.verify("SYNPA0001A", expected_entity_name="Wrong Company")
        facts = MockRegistryEvidenceAdapter.to_bidder_facts(mismatch_res, bid_id="BID-001")
        self.assertEqual(len(facts), 0)

    def test_evidence_adapter_verified_fact_generation(self):
        itd = MockITDAdapter()
        verified_res = itd.verify("SYNPA0001A", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        facts = MockRegistryEvidenceAdapter.to_bidder_facts(verified_res, bid_id="BID-001")
        self.assertGreaterEqual(len(facts), 2)

        fields = {f.field: f.value for f in facts}
        self.assertEqual(fields.get("itr_filing_status"), "FILED")
        self.assertEqual(fields.get("turnover_cr"), 25.0)

        for f in facts:
            self.assertEqual(f.source_document, "MOCK_ITD:SYNPA0001A")
            self.assertEqual(f.extraction_confidence, "HIGH")
            self.assertEqual(f.metadata["source_type"], "INTERNAL_MOCK_REGISTRY")
            self.assertEqual(f.metadata["dataset_version"], "MOCK_REGISTRY_DATASET_V1")

    def test_evidence_adapter_dag_integration_and_acyclicity(self):
        dag = ProvenanceDAG()
        itd = MockITDAdapter()
        verified_res = itd.verify("SYNPA0001A", expected_entity_name="SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED")
        facts = MockRegistryEvidenceAdapter.to_bidder_facts(verified_res, bid_id="BID-001")

        # Integrate into DAG
        MockRegistryEvidenceAdapter.integrate_with_dag(dag, facts, verified_res)

        # Validate Kahn's algorithm strict acyclicity (validate raises error if cyclic)
        dag.validate()
        self.assertGreaterEqual(len(dag.nodes), 3)  # 1 physical block node + at least 2 fact nodes
        self.assertGreaterEqual(len(dag.edges), 2)

    # ======================================================================
    # 8. Deterministic Replay / Zero Network Calls Test
    # ======================================================================
    def test_deterministic_replay_consistency(self):
        itd = MockITDAdapter()
        mca = MockMCA21Adapter()

        res1_itd = itd.verify("SYNPA0001A")
        res2_itd = itd.verify("SYNPA0001A")
        self.assertEqual(res1_itd.to_dict(), res2_itd.to_dict())

        res1_mca = mca.verify("U72900DL2019PTC100001")
        res2_mca = mca.verify("U72900DL2019PTC100001")
        self.assertEqual(res1_mca.to_dict(), res2_mca.to_dict())


class TestMockRegistriesAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_api_mock_status(self):
        resp = self.client.get("/api/v1/integrations/mock/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["source_type"], "INTERNAL_MOCK_REGISTRY")
        self.assertEqual(data["dataset_version"], "MOCK_REGISTRY_DATASET_V1")
        self.assertFalse(data["is_live_government_portal"])
        self.assertIn("MOCK_ITD", data["registries"])
        self.assertIn("MOCK_MCA21", data["registries"])
        self.assertIn("MOCK_NSIC", data["registries"])
        self.assertIn("MOCK_OEM", data["registries"])
        self.assertIn("MOCK_MII", data["registries"])

    def test_api_mock_itd_verify(self):
        payload = {
            "identifier": "SYNPA0001A",
            "expected_entity_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
            "bid_id": "BID-API-01",
            "convert_to_bidder_fact": True,
        }
        resp = self.client.post("/api/v1/integrations/mock/itd/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(data["source"], "MOCK_ITD")
        self.assertEqual(data["source_type"], "INTERNAL_MOCK_REGISTRY")
        self.assertIsNotNone(data["bidder_facts"])
        self.assertGreaterEqual(len(data["bidder_facts"]), 2)

    def test_api_mock_mca21_verify(self):
        payload = {
            "identifier": "U72900DL2019PTC100001",
            "expected_entity_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
        }
        resp = self.client.post("/api/v1/integrations/mock/mca21/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(data["source"], "MOCK_MCA21")

    def test_api_mock_nsic_verify(self):
        payload = {
            "identifier": "NSIC-MUM-2024-001",
            "expected_entity_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
        }
        resp = self.client.post("/api/v1/integrations/mock/nsic/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(data["source"], "MOCK_NSIC")

    def test_api_mock_oem_verify(self):
        payload = {
            "identifier": "OEM-AUTH-HP-2025-001",
            "expected_entity_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
        }
        resp = self.client.post("/api/v1/integrations/mock/oem/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(data["source"], "MOCK_OEM")

    def test_api_mock_mii_verify(self):
        payload = {
            "identifier": "MII-DECL-2025-001",
            "expected_entity_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
        }
        resp = self.client.post("/api/v1/integrations/mock/mii/verify", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(data["source"], "MOCK_MII")

    def test_api_mock_generic_verify(self):
        payload = {
            "identifier": "SYNPA0001A",
            "expected_entity_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
        }
        resp = self.client.post("/api/v1/integrations/mock/verify?registry_name=itd", json=payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "VERIFIED")
        self.assertEqual(data["source"], "MOCK_ITD")

    def test_api_mock_generic_verify_invalid_registry(self):
        payload = {"identifier": "TEST1234"}
        resp = self.client.post("/api/v1/integrations/mock/verify?registry_name=nonexistent", json=payload)
        self.assertEqual(resp.status_code, 400)
        err_msg = resp.json().get("error") or resp.json().get("detail") or ""
        self.assertIn("Unknown mock registry", err_msg)


if __name__ == "__main__":
    unittest.main()
