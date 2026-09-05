# Step 5 — Manual Acceptance Test Report

> [!IMPORTANT]
> **AUDIT PRINCIPLE:** This report documents an independent, procurement-officer-grade manual acceptance test of the Step 5 implementation (Mock Government Verification Adapters and Cross-Document Contradiction Engine).
> **MOCK NOTICE:** Government verification is strictly mocked for the hackathon prototype. No live government APIs are accessed.

---

## 1. Test Objective

To independently exercise and verify the Step 5 implementation across:
1. **Mock Government Adapters:** GST, PAN, Udyam (MSME), and Debarment/Blacklist.
2. **Deterministic Cross-Document Contradiction Engine:** Multi-document consistency, normalization, and evidence propagation.
3. **Core Architectural Separation:** Ensuring that compliance decisions (Step 4 `PASS`/`FAIL`/`N/A`) and integrity findings (Step 5 `CONTRADICTION`/`REVIEW`/`CONSISTENT`) remain strictly decoupled.
4. **Data Integrity & Determinism:** Verifying zero modification to raw SIH datasets and 100% reproducible bitwise results.

---

## 2. Test Environment

* **Operating System:** Windows (PowerShell Shell environment)
* **Python Runtime:** Python 3.13 (64-bit)
* **Project Directory:** `D:\smart_india_hackathon\project`
* **Dataset Under Test:** `SIH26100_Dataset_v1_COMPLETE` (9,117 files, 0 modifications against zip archive)
* **Execution Timestamp:** 2026-09-03T12:50:00+05:30 (Caller-supplied; zero internal system clock calls)

---

## 3. Manual Acceptance Scorecard

| Test ID | Test Category | Target / Scenario | Expected Result | Actual Result | Status | Key Evidence / Rationale |
| :--- | :--- | :--- | :--- | :--- | :---: | :--- |
| **A1** | GST Verification | Existing GSTIN + matching entity | `VERIFIED` | `VERIFIED` | **PASS** | `29SYNTH0000003F1Z` registered to `Bharat Devices` (`is_mock=True`, `source="MOCK_GST_REGISTRY"`). |
| **A2** | GST Verification | Existing GSTIN + mismatched entity | `IDENTITY_MISMATCH` | `IDENTITY_MISMATCH` | **PASS** | Claimed `Fraudulent Shell Corp` rejected with explanatory reason. |
| **A3** | GST Verification | Unknown GSTIN | `NOT_FOUND` | `NOT_FOUND` | **PASS** | `99UNKNOWN000000X9Z` correctly identified as absent from registry. |
| **A4** | GST Verification | Inactive / Suspended GSTIN | `INACTIVE` | `NOT REPRESENTED` | **N/A** | All 3,000 raw SIH entities are active. Flagged as *Not Represented by Current Fixture*. |
| **B1** | PAN Verification | Existing PAN + matching entity | `VERIFIED` | `VERIFIED` | **PASS** | `SYNTH0003F` registered to `Bharat Devices` (`source="MOCK_PAN_REGISTRY"`). |
| **B2** | PAN Verification | Existing PAN + wrong entity | `IDENTITY_MISMATCH` | `IDENTITY_MISMATCH` | **PASS** | Claimed `Incorrect Bidder Name` rejected with explicit mismatch reason. |
| **B3** | PAN Verification | Unknown PAN | `NOT_FOUND` | `NOT_FOUND` | **PASS** | `UNKNOWN00X` returned `NOT_FOUND`. |
| **C1** | Udyam / MSME | Valid Udyam cert + matching entity | `VERIFIED` (MSE fact) | `VERIFIED` (MSE fact) | **PASS** | `CERT953698` issued to `Bharat Devices` emitted `is_mse: True` (`MICRO`). |
| **C2** | Udyam / MSME | Udyam cert + name mismatch | `IDENTITY_MISMATCH` / `REVIEW` | `IDENTITY_MISMATCH` | **PASS** | Unmatched bidder prevents automatic MSE exemption grant. |
| **C3** | Udyam / MSME | Altered / Tampered Udyam cert | `REVIEW` | `REVIEW` | **PASS** | `CERT131405` with flag `NAME_MISMATCH` safely held for officer review. |
| **C4-A**| Exemption Bridge| Verified MSE fed to Step 4 engine | `N/A` (EXEMPTED) | `N/A` | **PASS** | Turnover ₹20L < ₹50L evaluated to `N/A` (`actual: "EXEMPTED (MSE Verified)"`). Never returns `PASS`. |
| **C4-B**| Exemption Bridge| Unverified MSE fed to Step 4 | `FAIL` | `FAIL` | **PASS** | Turnover ₹20L < ₹50L evaluated to `FAIL`. Exemption NOT silently granted. |
| **D1** | Debarment | Known clean bidder | `NOT_DEBARRED` | `NOT_DEBARRED` | **PASS** | `SYNTH0003F` (`Bharat Devices`) confirmed free of active sanctions. |
| **D2** | Debarment | Known debarred entity fixture | `DEBARRED` | `DEBARRED` | **PASS** | `DEBAR0001D` (`Fraudulent Tech Supplies`) matched bid rigging order #2025/MOC/88. |
| **E1** | Contradictions | Same GSTIN across documents | `CONSISTENT` | `CONSISTENT` | **PASS** | `29SYNTH0000003F1Z` matched in `tech.pdf` and `annex.pdf` (`review=False`). |
| **E2** | Contradictions | Different GSTIN across documents | `CONTRADICTION` | `CONTRADICTION` | **PASS** | Discrepancy flagged with `severity=HIGH`; both `evidence_a` and `evidence_b` preserved. |
| **E3** | Contradictions | Same PAN across documents | `CONSISTENT` | `CONSISTENT` | **PASS** | `SYNTH0003F` matched across documents. |
| **E4** | Contradictions | Different PAN across documents | `CONTRADICTION` | `CONTRADICTION` | **PASS** | `SYNTH0003F` vs `SYNTH9999X` flagged with `severity=HIGH`. |
| **E5** | Contradictions | Same Udyam number | `CONSISTENT` | `CONSISTENT` | **PASS** | `UDYAM-KR-03-0012345` matched across documents. |
| **E6** | Contradictions | Different Udyam numbers | `CONTRADICTION` | `CONTRADICTION` | **PASS** | `UDYAM-KR-03-0012345` vs `UDYAM-DL-01-0099999` flagged with `severity=HIGH`. |
| **F1** | Normalization | Money: "₹12.24 Crore" vs "1224 Lakhs"| `CONSISTENT` | `CONSISTENT` | **PASS** | Both normalized to `Decimal("122400000")`. Zero floating point drift. |
| **F2** | Normalization | Money: "₹12.24 Crore" vs "₹17.02 Crore"| `CONTRADICTION` | `CONTRADICTION` | **PASS** | Discrepancy correctly detected between differing financial representations. |
| **F3** | Normalization | Duration: "3 years" vs "36 months" | `CONSISTENT` | `CONSISTENT` | **PASS** | Both standardized to `Decimal("36")` months. |
| **F4** | Normalization | Duration: "3 years" vs "24 months" | `CONTRADICTION` | `CONTRADICTION` | **PASS** | Discrepancy correctly detected. |
| **F5** | Normalization | Name: "ABC PRIVATE LIMITED" vs "ABC PVT LTD" | `CONSISTENT` | `CONSISTENT` | **PASS** | Legal suffixes normalized to canonical form (`BENIGN_NAME_VARIANT`). |
| **F6** | Normalization | Casing/Whitespace around GSTIN | `CONSISTENT` | `CONSISTENT` | **PASS** | `" 29synth... "` normalized to `"29SYNTH..."`. |
| **G**  | Ambiguous Name | "ABC INFRASTRUCTURE PVT LTD" vs "ABC INFRASTRUCTURE SERVICES PVT LTD" | `REVIEW` / `CONTRADICTION` | `CONTRADICTION` (`review=True`)| **PASS** (Safe) | Detected as two distinct legal entities (`COMPANY_NAME_CONTRADICTION`) with `requires_human_review=True`. |
| **H**  | Evidence Integrity| Document A present, Document B missing | `INCOMPLETE_EVIDENCE` | `INCOMPLETE_EVIDENCE` | **PASS** | `status=REVIEW`, `evidence_b={}`. No fabricated evidence. |
| **I**  | Separation Test| Compliant turnover with cross-doc discrepancy | Compliance: `PASS`<br>Integrity: `CONTRADICTION` | Compliance: `PASS`<br>Integrity: `CONTRADICTION` | **PASS** | Compliance status remains strictly `PASS`. Integrity anomaly displayed independently. |
| **J**  | Mock Provenance| All adapters state `is_mock=True` | `True` for all | `True` for all | **PASS** | Explicit source tags: `MOCK_GST_REGISTRY`, `MOCK_PAN_REGISTRY`, etc. |
| **K**  | Determinism | 3 consecutive runs identical | `True` | `True` | **PASS** | Bitwise identical outputs (3,595 bytes serialized JSON across all runs). |
| **L**  | Real SIH Record| Dataset-backed record BID-00001 | `VERIFIED` & `CONTRADICTION` | `VERIFIED` & `CONTRADICTION` | **PASS** | Evaluated real SIH entity and real contradiction pair `CONTRA-000001`. |
| **M**  | Raw Data Safety| Zero modifications to raw SIH files | Unmodified | Unmodified | **PASS** | All 9,117 files verified byte-for-byte against zip archive. |
| **N**  | Regression | All Step 4 & Step 5 automated tests | All pass | All pass | **PASS** | 26/26 verification tests pass; 14/14 Step 4 unit tests pass. |

---

## 4. Deep-Dive Findings on Critical Tests

### 4.1 Test I: Compliance vs Integrity Separation (Architectural Invariant)
* **Tender Requirement:** Minimum Turnover $\ge$ ₹10.0 Crore.
* **Document A (Financial Bid):** Turnover = ₹12.24 Crore (Compliant $\ge$ 10.0 Cr).
* **Document B (CA Certificate):** Turnover = ₹17.02 Crore (Also Compliant $\ge$ 10.0 Cr, but inconsistent with Doc A).
* **Step 4 Evaluation:**
  ```json
  {
    "requirement_id": "REQ-TO-10CR",
    "status": "PASS",
    "actual": 12.24,
    "severity": "INFO",
    "reason": "Actual value (12.24) meets or exceeds threshold (10.0)."
  }
  ```
* **Step 5 Evaluation:**
  ```json
  {
    "finding_id": "INT-BID-SEP-I-TURNOVER_CR-001",
    "status": "CONTRADICTION",
    "severity": "HIGH",
    "requires_human_review": true,
    "description": "Financial turnover differs across documents: '12.24' vs '17.02'."
  }
  ```
* **Separation Invariant:** **PRESERVED.** The presence of `CONTRADICTION` in Step 5 did NOT alter the compliance result from `PASS` to `FAIL`. Both signals are independently recorded and presented to the procurement officer.

### 4.2 Test G: Ambiguous Corporate Entity Matching
* **Comparison:** `"ABC INFRASTRUCTURE PRIVATE LIMITED"` vs `"ABC INFRASTRUCTURE SERVICES PRIVATE LIMITED"`.
* **Behavior:** The engine recognized that neither name is a pure abbreviation or contiguous substring of the other (due to the presence of the distinct corporate division token `"SERVICES"`).
* **Outcome:** The engine classified this as `COMPANY_NAME_CONTRADICTION` with `requires_human_review = True`.
* **Procurement Assessment:** **SAFE.** In Indian corporate law, `"ABC Infrastructure Pvt Ltd"` and `"ABC Infrastructure Services Pvt Ltd"` are distinct corporate entities with separate CINs and PANs. Flagging this as an identity conflict requiring human review prevents one entity from bidding under a sister subsidiary''s credentials.

### 4.3 Test H: Incomplete Evidence Protection
* **Scenario:** Document A claims OEM authorization, but Document B reference is unextracted or absent.
* **Outcome:** The engine produced `finding_type: "INCOMPLETE_EVIDENCE"`, `status: "REVIEW"`, with `evidence_b: {}`.
* **Procurement Assessment:** **SAFE.** The system explicitly documents missing evidence and prompts officer scrutiny rather than fabricating plausible evidence.

---

## 5. Raw Dataset Integrity Check

File integrity was verified by scanning all extracted files in `data/raw/SIH26100_Dataset_v1_COMPLETE/` against the canonical archive `SIH26100_Dataset_v1_COMPLETE.zip`:
* **Total files inspected:** `9,117`
* **Files modified:** `0`
* **Byte discrepancies:** `0`
* **Integrity Status:** **100% UNTOUCHED.**

---

## 6. Regression Test Summary

* **Contract Schemas (`test_schemas.py`):** 4 / 4 PASSED
* **Dataset Mappings (`test_dataset_mappings.py`):** 3 / 3 PASSED (208 clauses)
* **Core Rule Engine (`test_rule_engine.py`):** 14 / 14 PASSED
* **Verification & Contradictions (`test_adapters_and_contradictions.py`):** 26 / 26 PASSED
* **SIH Contradiction Validation (`validate_sih_contradictions.py`):** 1,041 / 1,041 PASSED (100.00% exact match)
* **SIH Anomaly Validation (`validate_sih_anomalies.py`):** 9,218 records structurally verified

---

## 7. Final Acceptance Verdict

### **STEP 5 IS ACCEPTED (PASS)**

* All mock government adapters satisfy the swap-in ready contract.
* The contradiction engine operates deterministically with comprehensive normalization.
* Zero fabricated evidence; both sides of contradictions are faithfully preserved.
* The compliance and integrity signals are strictly separated.
* All raw datasets remain 100% untouched.

**Recommendation:** Proceed to **Step 6 — Document Ingestion, PDF Text Extraction & OCR Parsing Pipeline**.
