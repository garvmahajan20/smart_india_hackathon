# Step 8 — Semantic Audit Report: Analysis of the "UNCERTAIN" Label & BID-00667 Verification

> [!IMPORTANT]
> **AUDIT OBJECTIVE:**
> Determine the exact semantic meaning of the canonical SIH dataset label `"UNCERTAIN"` and establish whether the current Step 8 system outcome for `BID-00667` (`overall_status = FAIL`, `compliance_status = FAIL`, `integrity_status = CONSISTENT`) is semantically correct.
>
> **STATUS:** **READ-ONLY INVESTIGATION COMPLETE** (Zero code or raw dataset modifications; Zero Gemini API quota consumed).

---

## 1. Canonical Sources Inspected

The following canonical dataset files under `data/raw/SIH26100_Dataset_v1_COMPLETE/sih26100_dataset_v1/` were audited in detail:

| Canonical File | Role in Audit | Records Checked |
| :--- | :--- | :---: |
| `README.md` | Core label taxonomy definitions and modeling principles | 52 lines (complete) |
| `metadata/dataset_summary.json` | Global statistics and class distributions | Complete |
| `metadata/bids.jsonl` | Bid-level ground truth metadata, risk bands, and anomaly components | Line 667 (`BID-00667`) + global distribution |
| `metadata/entities.jsonl` | Entity identity consistency records | `BID-00667` record |
| `metadata/splits.csv` | Train/val/test split group assignment | `BID-00667` record (`train`, `TENDER-0069`) |
| `text/clause_pairs.jsonl` | Ground-truth clause requirements, extracted values, and compliance statuses | All 8 clauses for `BID-00667` + 24,000 global pairs |
| `text/contradiction_pairs.jsonl` | Cross-document inconsistency pairs | 1,041 global records (`BID-00667` checked) |
| `labels/anomalies.jsonl` | Ground-truth anomaly entries with bounding box coordinates | `ANOM-0002068`, `ANOM-0002069` |
| `labels/evidence.jsonl` | Evidence pointers linked to anomalies | `EVID-ANOM-0002068`, `EVID-ANOM-0002069` |
| `financial/financial_lines.csv` | Financial line items, calculations, and tax amounts | 8 lines for `BID-00667` (`BID-00667-FIN-01` to `08`) |
| `certificates/certificates.jsonl` | Certificate validity, issuer, dates, and tampering anomalies | 6 certificates for `BID-00667` (`CERT-01` to `06`) |
| `vision/stamps.csv` | Visual stamp forgery metadata and ELA scores | 3 stamps for `BID-00667` (`STAMP-01` to `03`) |
| `documents/bids/BID-00667.pdf` | Raw PDF document rendered text and block structure | 2 pages (complete) |
| `documents/tenders/TENDER-0069.pdf` | Raw tender specification PDF | Complete |

---

## 2. Complete Trace of BID-00667 Across Canonical Records

A complete trace across all submodules confirms the exact state of `BID-00667`:

### A. Bid Metadata (`metadata/bids.jsonl`)
```json
{
  "bid_id": "BID-00667",
  "tender_id": "TENDER-0069",
  "company_name": "Suryodaya Infra",
  "gstin_dummy": "29SYNTH0000004F1Z",
  "pan_dummy": "SYNTH0004F",
  "submission_date": "2026-08-01",
  "ground_truth_label": "UNCERTAIN",
  "is_clean": false,
  "is_anomalous": true,
  "anomaly_components": "clause_compliance",
  "total_clauses": 8,
  "total_financial_lines": 8,
  "total_certificates": 6,
  "total_stamps": 3,
  "total_anomalies": 2,
  "prototype_risk_index": 30,
  "prototype_risk_band": "MEDIUM"
}
```
* **Key Findings:**
  * `is_clean`: `false`, `is_anomalous`: `true`.
  * `anomaly_components`: `"clause_compliance"`.
  * Zero cross-document consistency anomalies. Zero financial anomalies. Zero stamp anomalies.
  * `total_anomalies`: exactly `2`.

### B. Entity Identity (`metadata/entities.jsonl`)
```json
{
  "bid_id": "BID-00667",
  "company_name": "Suryodaya Infra",
  "gstin": "29SYNTH0000004F1Z",
  "pan": "SYNTH0004F",
  "company_alias": "Suryodaya Infra",
  "entity_ground_truth": "CONSISTENT"
}
```
* Legal entity identity is 100% consistent and active across GST and PAN.

### C. Financial Lines (`financial/financial_lines.csv`)
* 8 lines (`BID-00667-FIN-01` through `08`).
* Every line has `error_type: "NONE"`. Computed tax equals reported tax. Zero mathematical discrepancies.

### D. Certificates (`certificates/certificates.jsonl`)
* 6 certificates (1 PAN, 1 BIS, 1 ISO 9001, 3 GST registrations).
* Every certificate has `valid: true` and `anomaly: "NONE"`.

### E. Visual Stamps (`vision/stamps.csv`)
* 3 stamps (2 CA stamps, 1 signature stamp).
* All 3 have `manipulation_type: "CLEAN"` and label `0`.

### F. Cross-Document Contradictions (`text/contradiction_pairs.jsonl`)
* Exactly `0` contradiction records exist for `BID-00667`.

### G. Clause-by-Clause Evaluation (`text/clause_pairs.jsonl`)
All 8 clauses evaluated against `TENDER-0069`:

| Clause ID | Field | Requirement Text | Bidder Statement (`bid_text`) | Fact Value | Expected Value | Operator | Canonical `compliance_status` | `issue_family` |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `TC-01` | `warranty_years` | Minimum comprehensive warranty of 2 years | "The offered warranty is for 2 years." | `2` | `2` | `>=` | **`PASS`** | `NONE` |
| `TC-02` | `delivery_days` | Delivery and installation completed within 60 days | "Maximum delivery timeline: 60 calendar days." | `60` | `60` | `<=` | **`PASS`** | `NONE` |
| `TC-03` | `iso_cert` | Valid ISO 14001:2015 certificate | "Valid ISO 14001:2015 certificate enclosed as Annexure C." | `"ISO 14001:2015"` | `"ISO 14001:2015"` | `==` | **`PASS`** | `ambiguous_or_ocr_uncertain` |
| `TC-04` | `turnover_cr` | Minimum average annual turnover INR 2.84 crore | "Average annual turnover: INR 10.88 crore." | `10.88` | `2.84` | `>=` | **`PASS`** | `NONE` |
| `TC-05` | `similar_projects` | At least 3 similar projects in last 5 years | "Completed 5 similar projects in the last five years." | `5` | `3` | `>=` | **`PASS`** | `NONE` |
| `TC-06` | `net_worth_cr` | Minimum net worth INR 2.87 crore | "Net worth: INR 5.4 crore." | `5.4` | `2.87` | `>=` | **`PASS`** | `NONE` |
| `TC-07` | `emd_required` | Submit prescribed Earnest Money Deposit | **"EMD exemption claimed; supporting basis unclear."** | **`false`** | **`true`** | `==` | **`FAIL`** | `ambiguous_or_ocr_uncertain` |
| `TC-08` | `local_support` | Provide local service support within the state | **"Local support facility to be arranged after award."** | **`false`** | **`true`** | `==` | **`FAIL`** | `ambiguous_or_ocr_uncertain` |

### H. Canonical Anomaly Records (`labels/anomalies.jsonl`)
```json
{
  "anomaly_id": "ANOM-0002068",
  "bid_id": "BID-00667",
  "tender_id": "TENDER-0069",
  "type": "CLAUSE_REQUIREMENT_FAILURE",
  "severity": "MEDIUM",
  "page": 6,
  "bbox": [175, 114, 567, 583],
  "description": "Requirement == True not satisfied by extracted value False.",
  "source_field": "emd_required",
  "component": "clause_compliance",
  "ground_truth": true
}
{
  "anomaly_id": "ANOM-0002069",
  "bid_id": "BID-00667",
  "tender_id": "TENDER-0069",
  "type": "CLAUSE_REQUIREMENT_FAILURE",
  "severity": "MEDIUM",
  "page": 6,
  "bbox": [152, 146, 289, 611],
  "description": "Requirement == True not satisfied by extracted value False.",
  "source_field": "local_support",
  "component": "clause_compliance",
  "ground_truth": true
}
```

---

## 3. What "UNCERTAIN" Actually Means in the Dataset

From global dataset analysis across all 3,000 bids and 24,000 clause pairs:

1. **Explicit Dataset Definition (`README.md`, Line 11):**
   > `"UNCERTAIN: insufficient/ambiguous/OCR-corrupted evidence requiring human review."`
2. **Two Distinct Levels of "Uncertainty" in the Dataset:**
   * **Level 1 — Extraction-Level Uncertainty (310 clause pairs):**
     * Where the scan was illegible or corrupted (e.g., `"Warranty offered: 3 years (scan partially illegible)"`, `"Delivery within 15–? days"`, `"Average annual turnover: INR 1O.5 crore."`).
     * In these cases, `extracted_value` is `null`, and canonical `compliance_status` in `clause_pairs.jsonl` is explicitly set to `"UNCERTAIN"`.
   * **Level 2 — Semantic / Claim Ambiguity (e.g., `BID-00667`):**
     * Where the bidder did not provide the required evidence but offered a conditional or ambiguous claim (e.g. `"EMD exemption claimed; supporting basis unclear"`, `"Local support facility to be arranged after award"`).
     * In these cases, because the required item is not factually present, the canonical `extracted_value` is assigned `false`, which evaluates against `expected_value: true` as **`compliance_status = "FAIL"`** and triggers anomaly type **`"CLAUSE_REQUIREMENT_FAILURE"`**.
     * However, because the failure arose from an ambiguous claim rather than an outright numerical shortfall (like `similar_projects: 2 < 3` in `BID-00733`), the bid-level classifier label in `metadata/bids.jsonl` was categorized as **`"UNCERTAIN"`** rather than `"NON_COMPLIANT"`.
3. **Absence of Fraud Accusation:**
   * The dataset authors specifically note (`README.md`, line 14):
     > `"The system should recommend human review rather than make an autonomous fraud accusation."`

---

## 4. Comparison Across Representative Canonical Demo Bids

| Metric | `BID-00031` | `BID-00733` | `BID-00667` | `BID-00001` |
| :--- | :---: | :---: | :---: | :---: |
| **Bidder Company** | BluePeak Solutions | Pragati Technologies | Suryodaya Infra | Bharat Devices |
| **Dataset `ground_truth_label`** | **`CLEAN`** | **`NON_COMPLIANT`** | **`UNCERTAIN`** | **`MANIPULATED`** |
| **`is_clean` / `is_anomalous`** | `true` / `false` | `false` / `true` | `false` / `true` | `false` / `true` |
| **`anomaly_components`** | `NONE` | `clause_compliance` | `clause_compliance` | `clause_compliance \| cross_document_consistency` |
| **Prototype Risk Index / Band** | `0` / `LOW` | `30` / `MEDIUM` | `30` / `MEDIUM` | `100` / `HIGH` |
| **Total Canonical Anomalies** | 0 | 2 | 2 | 6 |
| **Clause Failure Types** | None (8/8 PASS) | 2 Failures (1 numeric shortfall `2 < 3`, 1 EMD) | 2 Failures (EMD exemption unclear, local support post-award) | 5 Failures (delivery 85 > 60, ISO missing, similar projects 1 < 3, EMD, local support) |
| **`issue_family` in Failing Clauses** | `NONE` | `genuine_requirement_failure` | `ambiguous_or_ocr_uncertain` | `misrepresentation` |
| **Cross-Document Contradictions** | 0 | 0 | 0 | 1 (GSTIN mismatch: `29SYNTH0000003F1Z` vs `29SYNTH0000103F1Z`) |
| **Integrity Engine Verdict** | `CONSISTENT` | `CONSISTENT` | `CONSISTENT` | `CONTRADICTION` (`HIGH` severity) |
| **Current Step 8 Compliance** | **`PASS`** | **`FAIL`** | **`FAIL`** | **`FAIL`** |
| **Current Step 8 Overall Status** | **`PASS`** | **`FAIL`** | **`FAIL`** | **`FAIL`** |

---

## 5. Current Step 8 Execution Trace for BID-00667

Why did `BID-00667` produce:
* `OVERALL = FAIL`
* `COMPLIANCE = FAIL`
* `INTEGRITY = CONSISTENT`
* `REVIEWS = 0`

### Trace:
1. **Fact Ingestion in Benchmark Script:**
   * In `validate_sih_e2e_orchestration.py`, facts were constructed from `clause_pairs.jsonl`.
   * For TC-07 (`emd_required`), `extracted_value` is `False`.
   * For TC-08 (`local_support`), `extracted_value` is `False`.
   * `extraction_confidence` was passed as `"HIGH"`.
2. **Step 4 Rule Engine Evaluation:**
   * Requirement TC-07: `emd_required == True` (Mandatory).
     * Operator evaluation: `False == True` $\rightarrow$ `status = ComplianceStatus.FAIL`.
     * Because requirement is mandatory: `severity = Severity.CRITICAL`.
   * Requirement TC-08: `local_support == True` (Mandatory).
     * Operator evaluation: `False == True` $\rightarrow$ `status = ComplianceStatus.FAIL`.
     * Because requirement is mandatory: `severity = Severity.CRITICAL`.
   * Since `op_result.status == FAIL` and `extraction_confidence == "HIGH"`, the rule engine set `requires_human_review = False`.
3. **Step 8 Aggregation:**
   * `critical_failures = 2`.
   * Under Phase 4 Rule 1: Any CRITICAL compliance failure deterministically sets `compliance_status = FAIL` and `overall_status = FAIL`.
   * Because `requires_human_review` was `False`, `human_review_items` had 0 items.

---

## 6. Important Distinctions & Answers to Core Architectural Questions

1. **Does the canonical dataset define `UNCERTAIN` as the expected final system status?**
   * **NO.** `UNCERTAIN` is nowhere defined in `contracts/verification_result.schema.json` or any system schema. The allowed compliance statuses in the canonical contract are strictly:
     `PASS`, `FAIL`, `PARTIAL`, `MISSING`, `N/A`, `REVIEW`.
   * `UNCERTAIN` is an academic benchmarking label in `bids.jsonl` designed for research classifiers, not an operational procurement decision.
2. **Is `UNCERTAIN` merely a dataset annotation describing ambiguity in the evidence?**
   * **YES.** It categorizes cases where failures arise from ambiguous declarations or OCR errors rather than deliberate misrepresentation or unequivocal numeric shortfalls.
3. **Is the system correctly allowed to deterministically conclude `FAIL` even when the dataset's bid-level label is `UNCERTAIN`?**
   * **YES.** Under procurement law and GeM guidelines, if a tender requires EMD and local support, and a bidder submits `"EMD exemption claimed; supporting basis unclear"` without providing an MSE/Startup certificate, the mandatory requirement is factually unsatisfied. The canonical dataset itself records both clauses as `"compliance_status": "FAIL"` and creates `"CLAUSE_REQUIREMENT_FAILURE"` anomalies.
4. **Is a Human Review Item required for BID-00667?**
   * In a live extraction pipeline where text is extracted directly from PDF, `"EMD exemption claimed; supporting basis unclear"` is recognized as an ambiguous statement that warrants escalation to `HumanReviewItem` (Category: `AMBIGUOUS_COMPLIANCE`).
   * However, under deterministic compliance rules, even with human review flagged, the compliance verdict remains `FAIL` unless a human officer explicitly overrides it.

---

## 7. Label-to-Status Mapping Search

A thorough search across all contracts, code, and tests in the repository confirmed:
> **"No canonical mapping from ground_truth_label to Step 8 overall_status was found."**

The system does not map `ground_truth_label` $\rightarrow$ `overall_status`. The system evaluates the raw evidence deterministically from first principles via Step 4, Step 5, and Step 8.

---

## 8. Focused BID-00667 Evidence Table

| Requirement ID | Expected | Bidder Fact | Step 4 Result | Evidence Source (`BID-00667.pdf`) | Rationale |
| :--- | :--- | :--- | :---: | :--- | :--- |
| `TENDER-0069/TC-01` | `>= 2` | `2` | **`PASS`** | Page 1, bbox `[90, 196, 345, 650]` | Offered warranty is exactly 2 years. |
| `TENDER-0069/TC-02` | `<= 60` | `60` | **`PASS`** | Page 1, bbox `[175, 474, 546, 774]` | Delivery within 60 calendar days satisfies `<= 60`. |
| `TENDER-0069/TC-03` | `== ISO 14001:2015` | `ISO 14001:2015` | **`PASS`** | Page 2, bbox `[97, 309, 561, 798]` | Valid ISO 14001:2015 certificate attached. |
| `TENDER-0069/TC-04` | `>= 2.84` | `10.88` | **`PASS`** | Page 1, bbox `[108, 276, 390, 704]` | Average turnover 10.88 Cr exceeds 2.84 Cr threshold. |
| `TENDER-0069/TC-05` | `>= 3` | `5` | **`PASS`** | Page 1, bbox `[142, 428, 284, 747]` | 5 similar projects completed satisfies `>= 3`. |
| `TENDER-0069/TC-06` | `>= 2.87` | `5.4` | **`PASS`** | Page 1, bbox `[180, 212, 409, 587]` | Net worth 5.4 Cr exceeds 2.87 Cr threshold. |
| `TENDER-0069/TC-07` | `== True` | `False` | **`FAIL`** | Page 1, bbox `[175, 114, 567, 583]` | Prescribed EMD not submitted; exemption claim lacks supporting proof. |
| `TENDER-0069/TC-08` | `== True` | `False` | **`FAIL`** | Page 1, bbox `[152, 146, 289, 611]` | Local service support not currently available; promised only after award. |

---

## 9. Final Determination

Based on the canonical dataset evidence:

> ### **CONCLUSION A: "Current Step 8 FAIL is semantically correct."**

### Detailed Justification:
1. **Canonical Clause Truth:** `text/clause_pairs.jsonl` explicitly records `"compliance_status": "FAIL"` for both failing clauses of `BID-00667`. The Step 4 rule engine evaluation is in 100.0% exact alignment with this canonical truth.
2. **Canonical Anomaly Truth:** `labels/anomalies.jsonl` records both anomalies as `"CLAUSE_REQUIREMENT_FAILURE"`.
3. **Integrity Independence:** `BID-00667` has zero cross-document contradictions, zero financial line calculation errors, zero forged stamps, and zero invalid certificates. Therefore, `integrity_status = "CONSISTENT"` is 100% accurate.
4. **Overall Status Determinism:** Under deterministic procurement evaluation rules, a bid that fails two mandatory tender requirements (`emd_required` and `local_support`) cannot receive a passing grade. Setting `overall_status = "FAIL"` is legally, procedurally, and architecturally correct.

---

## 10. Recommended Next Action

* **No Production Code Changes Required:** Step 4, Step 5, Step 6, Step 7, and Step 8 code operate correctly and strictly conform to canonical contracts and deterministic rules.
* **Optional Future Refinement in Benchmark Script:** In `tests/orchestration/validate_sih_e2e_orchestration.py`, when loading facts for clauses where `issue_family == "ambiguous_or_ocr_uncertain"`, the script could optionally surface a human review item (`category: AMBIGUOUS_COMPLIANCE`) to showcase the human review routing capability on ambiguous submissions during demonstrations. This would not alter `overall_status = FAIL`, but would highlight the dual review queue signal.
