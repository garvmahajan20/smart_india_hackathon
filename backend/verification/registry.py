# -*- coding: utf-8 -*-
import json
import os
from typing import Any, Dict, List, Optional

def _clean_key(val: Optional[str]) -> str:
    if not val:
        return ""
    return "".join(val.strip().upper().split())

class MockGovernmentRegistry:
    """
    Deterministic in-memory mock registry loaded from canonical SIH datasets
    (entities.jsonl, certificates.jsonl), controlled debarment test fixtures,
    and synthetic mock government registries (ITD, MCA21, NSIC, OEM, MII).

    CRITICAL GOVERNANCE INVARIANT:
    These are strictly INTERNAL MOCK REGISTRIES for hackathon demonstrations
    where official free/self-service live APIs are unavailable.
    They are NEVER labeled as live government verified.
    Source Type: INTERNAL_MOCK_REGISTRY
    Dataset Version: MOCK_REGISTRY_DATASET_V1
    """

    _instance: Optional["MockGovernmentRegistry"] = None
    DATASET_VERSION = "MOCK_REGISTRY_DATASET_V1"
    SOURCE_TYPE = "INTERNAL_MOCK_REGISTRY"

    def __init__(self, entities_path: Optional[str] = None, certificates_path: Optional[str] = None):
        self.gst_records: Dict[str, Dict[str, Any]] = {}
        self.pan_records: Dict[str, Dict[str, Any]] = {}
        self.udyam_records: Dict[str, Dict[str, Any]] = {}
        self.debarment_records: Dict[str, Dict[str, Any]] = {}

        # Remaining Government Mock Registries
        self.itd_records: Dict[str, Dict[str, Any]] = {}
        self.mca_records: Dict[str, Dict[str, Any]] = {}
        self.nsic_records: Dict[str, Dict[str, Any]] = {}
        self.oem_records: Dict[str, Dict[str, Any]] = {}
        self.mii_records: Dict[str, Dict[str, Any]] = {}

        self._is_loaded = False

        # Controlled Mock Debarment Fixture
        self._init_controlled_debarment_fixture()

        # Synthetic Mock Registries (MOCK_REGISTRY_DATASET_V1)
        self._init_synthetic_government_mock_fixtures()

        # Load from canonical datasets if paths provided or default exists
        base_dir = "data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1"
        ent_path = entities_path or os.path.join(base_dir, "metadata", "entities.jsonl")
        cert_path = certificates_path or os.path.join(base_dir, "certificates", "certificates.jsonl")

        self._load_datasets(ent_path, cert_path)

    @classmethod
    def get_instance(cls) -> "MockGovernmentRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _init_controlled_debarment_fixture(self) -> None:
        """
        Controlled mock debarment records clearly labeled as synthetic test fixtures.
        """
        controlled_debarred = [
            {
                "entity_name": "Fraudulent Tech Supplies Pvt Ltd",
                "pan": "DEBAR0001D",
                "gstin": "29DEBAR0001D1Z1",
                "status": "DEBARRED",
                "reason": "Debarred by Ministry of Commerce for bid rigging (GeM Order #2025/MOC/88).",
                "debarment_period": "2025-01-15 to 2028-01-15",
                "issuing_authority": "Ministry of Commerce & Industry",
            },
            {
                "entity_name": "Blacklisted Infrastructure Corp",
                "pan": "BLACK0002B",
                "gstin": "29BLACK0002B1Z2",
                "status": "DEBARRED",
                "reason": "Debarred for forged performance bank guarantee under Rule 151(iii) GFR 2017.",
                "debarment_period": "2024-06-01 to 2027-06-01",
                "issuing_authority": "Department of Expenditure",
            },
            {
                "entity_name": "Suspended Logistics Ltd",
                "pan": "SUSPN0003S",
                "gstin": "29SUSPN0003S1Z3",
                "status": "DEBARRED",
                "reason": "Suspended pending vigilance investigation into collusive bidding.",
                "debarment_period": "2026-01-01 to 2026-12-31",
                "issuing_authority": "GeM Vigilance Directorate",
            },
        ]
        for rec in controlled_debarred:
            self.debarment_records[_clean_key(rec["entity_name"])] = rec
            self.debarment_records[_clean_key(rec["pan"])] = rec
            self.debarment_records[_clean_key(rec["gstin"])] = rec

    def _init_synthetic_government_mock_fixtures(self) -> None:
        """
        Initializes deterministic synthetic mock registries for remaining government sources:
        - MOCK_ITD: Income Tax Return verification
        - MOCK_MCA21: Corporate entity status and registration
        - MOCK_NSIC: Single Point Registration Scheme certificate
        - MOCK_OEM: OEM Manufacturer Authorization Form (MAF)
        - MOCK_MII: Make in India local content declarations

        All data is strictly synthetic under MOCK_REGISTRY_DATASET_V1.
        """
        # Controlled Synthetic PAN & GSTIN records for MOCK_REGISTRY_DATASET_V1
        synthetic_pan_gst = [
            {
                "pan": "SYNPA0001A",
                "gstin": "07SYNPA0001A1Z5",
                "company_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
                "status": "VALID",
                "registration_status": "ACTIVE",
            },
            {
                "pan": "SYNPA0008H",
                "gstin": "27SYNPA0008H1Z8",
                "company_name": "SYNTHETIC CONTRADICTION MFG LTD",
                "status": "VALID",
                "registration_status": "ACTIVE",
            },
            {
                "pan": "SYNPA0003C",
                "gstin": "29SYNPA0003C1Z3",
                "company_name": "SYNTHETIC DIVERGENT HOLDINGS PRIVATE LIMITED",
                "status": "VALID",
                "registration_status": "ACTIVE",
            },
        ]
        for item in synthetic_pan_gst:
            self.pan_records[_clean_key(item["pan"])] = item
            self.gst_records[_clean_key(item["gstin"])] = item

        # ==============================================================
        # 1. MOCK_ITD (Income Tax Department / ITR Verification)
        # ==============================================================
        itd_data = [
            # SCENARIO_A: Fully Compliant Return
            {
                "pan": "SYNPA0001A",
                "taxpayer_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
                "assessment_year": "2024-25",
                "financial_year": "2023-24",
                "filing_status": "FILED",
                "filing_date": "2024-07-20",
                "ack_number": "ITR-ACK-2024-00019283",
                "form_type": "ITR-6",
                "gross_total_income": 250000000,
                "turnover_cr": 25.0,
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_A",
            },
            # SCENARIO_B: Missing / Defaulter Return (NOT FILED)
            {
                "pan": "SYNPA0002B",
                "taxpayer_name": "SYNTHETIC DEFAULTER ENTERPRISES PRIVATE LIMITED",
                "assessment_year": "2024-25",
                "financial_year": "2023-24",
                "filing_status": "NOT_FILED",
                "filing_date": None,
                "ack_number": None,
                "form_type": None,
                "gross_total_income": None,
                "turnover_cr": None,
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_B",
            },
            # SCENARIO_C: Active ITR for entity C
            {
                "pan": "SYNPA0003C",
                "taxpayer_name": "SYNTHETIC DIVERGENT HOLDINGS PRIVATE LIMITED",
                "assessment_year": "2024-25",
                "financial_year": "2023-24",
                "filing_status": "FILED",
                "filing_date": "2024-08-15",
                "ack_number": "ITR-ACK-2024-00038821",
                "form_type": "ITR-6",
                "turnover_cr": 18.5,
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_C",
            },
            # SCENARIO_H: Contradiction Return (Turnover declared 25 Cr vs bid claimed 5 Cr)
            {
                "pan": "SYNPA0008H",
                "taxpayer_name": "SYNTHETIC CONTRADICTION MFG LTD",
                "assessment_year": "2024-25",
                "financial_year": "2023-24",
                "filing_status": "FILED",
                "filing_date": "2024-09-01",
                "ack_number": "ITR-ACK-2024-00089912",
                "form_type": "ITR-6",
                "gross_total_income": 250000000,
                "turnover_cr": 25.0,  # Contradicts claimed 5.0 Cr
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_H",
            },
        ]
        for rec in itd_data:
            self.itd_records[_clean_key(rec["pan"])] = rec
            if rec.get("ack_number"):
                self.itd_records[_clean_key(rec["ack_number"])] = rec

        # ==============================================================
        # 2. MOCK_MCA21 (Corporate Identity & Ministry of Corporate Affairs)
        # ==============================================================
        mca_data = [
            # SCENARIO_A: Active Company
            {
                "cin": "U72900DL2019PTC100001",
                "company_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
                "status": "ACTIVE",
                "company_type": "PRIVATE_LIMITED",
                "incorporation_date": "2019-03-15",
                "registered_office": "New Delhi, Delhi",
                "authorized_capital": 10000000,
                "paid_up_capital": 5000000,
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_A",
            },
            # SCENARIO_B: Active Defaulter Company
            {
                "cin": "U72900MH2020PTC100002",
                "company_name": "SYNTHETIC DEFAULTER ENTERPRISES PRIVATE LIMITED",
                "status": "ACTIVE",
                "company_type": "PRIVATE_LIMITED",
                "incorporation_date": "2020-06-20",
                "registered_office": "Mumbai, Maharashtra",
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_B",
            },
            # SCENARIO_C: Legal Name Mismatch (Registry has Divergent Holdings, bidder claims Tech Corp)
            {
                "cin": "U72900KA2021PTC100003",
                "company_name": "SYNTHETIC DIVERGENT HOLDINGS PRIVATE LIMITED",
                "status": "ACTIVE",
                "company_type": "PRIVATE_LIMITED",
                "incorporation_date": "2021-01-10",
                "registered_office": "Bengaluru, Karnataka",
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_C",
            },
            # Inactive / Strike-off Company
            {
                "cin": "U72900WB2015PTC100009",
                "company_name": "SYNTHETIC DISSOLVED TRADING PRIVATE LIMITED",
                "status": "INACTIVE",
                "company_type": "PRIVATE_LIMITED",
                "incorporation_date": "2015-05-12",
                "registered_office": "Kolkata, West Bengal",
                "dataset_version": self.DATASET_VERSION,
            },
        ]
        for rec in mca_data:
            self.mca_records[_clean_key(rec["cin"])] = rec
            self.mca_records[_clean_key(rec["company_name"])] = rec

        # ==============================================================
        # 3. MOCK_NSIC (Single Point Registration Scheme)
        # ==============================================================
        nsic_data = [
            # SCENARIO_A: Valid Active NSIC
            {
                "certificate_number": "NSIC-MUM-2024-001",
                "enterprise_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
                "status": "ACTIVE",
                "category": "MICRO",
                "issue_date": "2024-04-01",
                "expiry_date": "2027-03-31",
                "monetary_limit_lakhs": 500.0,
                "stores_details": ["Information Technology Software", "Computer Hardware"],
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_A",
            },
            # SCENARIO_D: Expired NSIC
            {
                "certificate_number": "NSIC-DEL-2021-004",
                "enterprise_name": "SYNTHETIC EXPIRED NSIC WORKSHOP",
                "status": "EXPIRED",
                "category": "SMALL",
                "issue_date": "2021-01-01",
                "expiry_date": "2023-12-31",
                "monetary_limit_lakhs": 150.0,
                "stores_details": ["Fabricated Metal Goods"],
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_D",
            },
            # Inactive NSIC
            {
                "certificate_number": "NSIC-BLR-2022-007",
                "enterprise_name": "SYNTHETIC SUSPENDED WORKSHOP",
                "status": "INACTIVE",
                "category": "MICRO",
                "issue_date": "2022-02-01",
                "expiry_date": "2025-01-31",
                "dataset_version": self.DATASET_VERSION,
            },
        ]
        for rec in nsic_data:
            self.nsic_records[_clean_key(rec["certificate_number"])] = rec
            self.nsic_records[_clean_key(rec["enterprise_name"])] = rec

        # ==============================================================
        # 4. MOCK_OEM (Original Equipment Manufacturer Authorization)
        # ==============================================================
        oem_data = [
            # SCENARIO_A: Valid Active OEM Authorization
            {
                "auth_number": "OEM-AUTH-HP-2025-001",
                "oem_name": "HEWLETT PACKARD ENTERPRISE INDIA",
                "authorized_bidder": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
                "status": "ACTIVE",
                "issue_date": "2025-01-01",
                "expiry_date": "2027-12-31",
                "product_category": "Enterprise Rack Servers & Networking",
                "scope": "Authorized to bid, supply, and warranty in GeM procurement tenders.",
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_A",
            },
            # SCENARIO_E: Expired OEM Authorization
            {
                "auth_number": "OEM-AUTH-DELL-2023-005",
                "oem_name": "DELL INTERNATIONAL SERVICES INDIA",
                "authorized_bidder": "SYNTHETIC RESELLER NETWORK LTD",
                "status": "EXPIRED",
                "issue_date": "2023-01-01",
                "expiry_date": "2024-06-30",
                "product_category": "Data Storage Systems",
                "scope": "GeM Bidding",
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_E",
            },
            # Unauthorized / Revoked Reseller
            {
                "auth_number": "OEM-AUTH-CISCO-2024-008",
                "oem_name": "CISCO SYSTEMS INDIA PRIVATE LIMITED",
                "authorized_bidder": "SYNTHETIC CONTRADICTION MFG LTD",
                "status": "UNAUTHORIZED",
                "issue_date": "2024-01-01",
                "expiry_date": "2024-05-01",
                "product_category": "Enterprise Routers",
                "scope": "Revoked due to commercial default",
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_H",
            },
        ]
        for rec in oem_data:
            self.oem_records[_clean_key(rec["auth_number"])] = rec
            key_pair = _clean_key(f"{rec['oem_name']}:{rec['authorized_bidder']}")
            self.oem_records[key_pair] = rec

        # ==============================================================
        # 5. MOCK_MII (Make in India / Public Procurement Preference)
        # ==============================================================
        mii_data = [
            # SCENARIO_A: Fully Compliant Class-I (65% Local Content)
            {
                "declaration_id": "MII-DECL-2025-001",
                "manufacturer_name": "SYNTHETIC BHARAT SYSTEMS PRIVATE LIMITED",
                "product_name": "Enterprise Rack Server",
                "local_content_percentage": 65.0,
                "supplier_class": "CLASS_1",
                "location_of_value_add": "Bengaluru, Karnataka",
                "valid_until": "2027-12-31",
                "status": "VALID",
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_A",
            },
            # SCENARIO_F: Below Tender Threshold (35% Local Content vs 50% Required)
            {
                "declaration_id": "MII-DECL-2025-006",
                "manufacturer_name": "SYNTHETIC LOW CONTENT IMPORTS LTD",
                "product_name": "High Performance Storage Unit",
                "local_content_percentage": 35.0,
                "supplier_class": "CLASS_2",
                "location_of_value_add": "Noida, Uttar Pradesh",
                "valid_until": "2026-12-31",
                "status": "VALID",
                "dataset_version": self.DATASET_VERSION,
                "scenario": "SCENARIO_F",
            },
            # Expired MII Declaration
            {
                "declaration_id": "MII-DECL-2022-010",
                "manufacturer_name": "SYNTHETIC OBSOLETE SYSTEMS",
                "product_name": "Legacy Network Switch",
                "local_content_percentage": 55.0,
                "supplier_class": "CLASS_1",
                "location_of_value_add": "Pune, Maharashtra",
                "valid_until": "2023-12-31",
                "status": "EXPIRED",
                "dataset_version": self.DATASET_VERSION,
            },
        ]
        for rec in mii_data:
            self.mii_records[_clean_key(rec["declaration_id"])] = rec
            key_prod = _clean_key(f"{rec['manufacturer_name']}:{rec['product_name']}")
            self.mii_records[key_prod] = rec

    def _load_datasets(self, entities_path: str, certificates_path: str) -> None:
        # 1. Load entities.jsonl -> GST & PAN registries
        if os.path.exists(entities_path):
            with open(entities_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    d = json.loads(line)
                    comp_name = d.get("company_name", "")
                    gstin = d.get("gstin", "")
                    pan = d.get("pan", "")
                    bid_id = d.get("bid_id", "")

                    record = {
                        "company_name": comp_name,
                        "gstin": gstin,
                        "pan": pan,
                        "bid_id": bid_id,
                        "registration_status": "ACTIVE",
                        "taxpayer_type": "Regular",
                        "state_jurisdiction": gstin[:2] if len(gstin) >= 2 else "29",
                    }

                    if gstin:
                        self.gst_records[_clean_key(gstin)] = record
                    if pan:
                        self.pan_records[_clean_key(pan)] = record

        # 2. Load certificates.jsonl -> Udyam & Certificate registries
        if os.path.exists(certificates_path):
            with open(certificates_path, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    c = json.loads(line)
                    ctype = c.get("cert_type", "")
                    if ctype == "Udyam Registration":
                        cnum = c.get("cert_number", "")
                        hname = c.get("holder_name", "")
                        bid_id = c.get("bid_id", "")
                        is_valid = c.get("valid", True)
                        anomaly = c.get("anomaly", "NONE")

                        udyam_rec = {
                            "cert_number": cnum,
                            "holder_name": hname,
                            "expected_holder_name": c.get("expected_holder_name", hname),
                            "bid_id": bid_id,
                            "enterprise_type": "MICRO" if int(cnum[-2:]) % 2 == 0 else "SMALL",
                            "status": "ACTIVE" if (is_valid and anomaly == "NONE") else "SUSPICIOUS",
                            "is_valid": is_valid,
                            "anomaly": anomaly,
                            "issue_date": c.get("issue_date"),
                            "expiry_date": c.get("expiry_date"),
                        }

                        if cnum:
                            self.udyam_records[_clean_key(cnum)] = udyam_rec
                        if hname:
                            self.udyam_records[_clean_key(hname)] = udyam_rec
                        if bid_id:
                            self.udyam_records[_clean_key(bid_id)] = udyam_rec

        self._is_loaded = True
