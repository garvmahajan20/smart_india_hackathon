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
    (entities.jsonl, certificates.jsonl) and controlled debarment test fixtures.
    CRITICAL: This is strictly a local MOCK registry for hackathon testing.
    No live government APIs or portals are queried.
    """

    _instance: Optional["MockGovernmentRegistry"] = None

    def __init__(self, entities_path: Optional[str] = None, certificates_path: Optional[str] = None):
        self.gst_records: Dict[str, Dict[str, Any]] = {}
        self.pan_records: Dict[str, Dict[str, Any]] = {}
        self.udyam_records: Dict[str, Dict[str, Any]] = {}
        self.debarment_records: Dict[str, Dict[str, Any]] = {}
        self._is_loaded = False

        # Controlled Mock Debarment Fixture
        self._init_controlled_debarment_fixture()

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
