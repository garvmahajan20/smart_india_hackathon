# Canonical Contract Mapping: SIH26100 Dataset

This document details how the synthetic canonical dataset (`SIH26100_Dataset_v1_COMPLETE`) maps into the 4 core JSON contracts:
1. `document.schema.json`
2. `requirement.schema.json`
3. `bidder_fact.schema.json`
4. `verification_result.schema.json`

---

## 1. Document Contract (`document.schema.json`)

SIH26100 stores bids as monolithic PDFs (e.g. `BID-00001.pdf`). Logical sections/documents are derived via page indices from certificates, financial lines, and contradiction pairs.

| Canonical Field | SIH Source | Mapping Logic | Transformation / Derived Data |
| --------------- | ---------- | ------------- | ----------------------------- |
| `document_id` | `certificates.jsonl`, `contradiction_pairs.jsonl` | `certificate_id` or generated `DOC-{bid_id}-{type}-{idx}` | Direct assignment or deterministic prefixing |
| `parent_file` | `bids.jsonl` | `{bid_id}.pdf` | Formatted string |
| `document_type` | `certificates.jsonl` (`cert_type`), `contradiction_pairs.jsonl` (`document_a`, `document_b`) | Mapped to enum (e.g. "GST Registration" -> `GST_REGISTRATION`, "technical_bid" -> `TECHNICAL_SPECIFICATION`) | Standardized enum lookup |
| `page_start` | `certificates.jsonl` (`page`), `financial_lines.csv` (`page`) | Direct page number integer | 1-indexed integer |
| `page_end` | Inferred | Equals `page_start` or segment boundary | Default to `page_start` for single-page certificates |
| `source` | Static | Always `"BIDDER"` (for bid docs) or `"TENDER"` (for tender docs) | Enum constant |
| `extraction_status` | Derived | `"SUCCESS"` if parsed, `"PARTIAL"` if OCR uncertain | Default `"SUCCESS"` |
| `classification_confidence` | Static | `"HIGH"` | Default enum |
| `metadata` | File system | File size, page counts, MD5 hash | Calculated at ingestion time |

---

## 2. Requirement Contract (`requirement.schema.json`)

Extracted from `metadata/tenders.jsonl` clauses array.

| Canonical Field | SIH Source (`tenders.jsonl` -> `clauses`) | Mapping Logic | Transformation / Derived Data |
| --------------- | ---------------------------------------- | ------------- | ----------------------------- |
| `requirement_id` | `clause_id` | Direct (e.g. `TENDER-0002/TC-01`) | String |
| `tender_id` | `tenders.jsonl` -> `tender_id` | Direct (e.g. `TENDER-0002`) | String |
| `category` | `clause_type` | `financial_capacity` -> `FINANCIAL_CAPACITY`, `technical_spec` -> `TECHNICAL_SPECIFICATION`, `certification` -> `CERTIFICATION`, `experience` -> `EXPERIENCE_PAST_PERFORMANCE`, `eligibility` -> `STATUTORY_ELIGIBILITY` | Uppercase enum mapping |
| `description` | `requirement_text` | Direct full requirement string | String |
| `field` | `field` | Direct (e.g. `turnover_cr`, `warranty_years`, `iso_cert`) | String identifier |
| `operator` | `operator` | Direct (`>=`, `<=`, `==`, `!=`, `IN`) | Validated against schema enum |
| `expected_value` | `expected_value` | Direct (number, string, boolean) | Preserves original type |
| `normalized_expected_value` | Derived from `expected_value` + `unit` | e.g. `14.58` with `INR crore` -> `145800000` | Normalized to standard SI/INR units |
| `unit` | `unit` | Standardized unit string (e.g. `INR_CRORE`, `YEARS`, `DAYS`, `BOOLEAN`) | Uppercase string |
| `mandatory` | Derived / Static | True by default in public procurement | Boolean |
| `source_type` | Not specified in SIH dataset | `"UNSPECIFIED"` (or `"UNKNOWN"`) | PROVENANCE SAFETY: SIH raw data contains no GTC/STC/ATC tags; provenance must NOT be fabricated as ATC |
| `source_clause` | `clause_id` | e.g. `"TC-01"` | Extracted from clause ID suffix |
| `source_page` | Inferred / Monolithic container default | Default `1` | 1-indexed integer |
| `source_priority` | Derived from `source_type` | `0` (unranked / unspecified baseline) | GTC=1, STC=2, ATC=3 are reserved for controlled fixtures with established provenance |
| `applicability` | Inferred | e.g. `mse_exemption_allowed: true` for turnover/experience | Configurable object |
| `extraction_confidence` | Static | `"HIGH"` | Enum |

---

## 3. Bidder Fact Contract (`bidder_fact.schema.json`)

Constructed from `text/clause_pairs.jsonl`, `certificates/certificates.jsonl`, `financial/financial_lines.csv`, and `metadata/entities.jsonl`.

| Canonical Field | SIH Source | Mapping Logic | Transformation / Derived Data |
| --------------- | ---------- | ------------- | ----------------------------- |
| `fact_id` | `clause_pairs.jsonl` (`pair_id`), `certificates.jsonl` (`certificate_id`) | e.g. `FACT-BID-00001-TC-01` | Unique string |
| `bid_id` | `bid_id` | Direct (e.g. `BID-00001`) | String |
| `bidder_id` | `entities.jsonl` (`company_name`) or `bid_id` | Company name or ID | String |
| `field` | `clause_pairs.jsonl` (`field`) | e.g. `turnover_cr`, `gstin`, `warranty_years` | Normalized identifier |
| `value` | `extracted_value` | Raw extracted value | Native JSON type |
| `normalized_value` | Derived from `value` + unit conversion | Normalized numeric/boolean/ISO date | Base units |
| `unit` | `clause_pairs.jsonl` / `tenders.jsonl` | Standard unit | String |
| `source_document` | Inferred | `{bid_id}.pdf` | Relative file path |
| `page` | `clause_pairs.jsonl` (`page`), `certificates.jsonl` (`page`) | 1-indexed page | Integer |
| `bbox` | `clause_pairs.jsonl` (`bbox`), `evidence.jsonl` (`bbox`) | Array of 4 floats `[ymin, xmin, ymax, xmax]` | Array of 4 numbers |
| `raw_text_snippet` | `clause_pairs.jsonl` (`bid_text`) | Exact extracted excerpt | String |
| `extraction_confidence` | Inferred from anomaly status | `"HIGH"` (clean) / `"LOW"` (uncertain anomaly) | Enum |
| `extraction_method` | Static | `"LLM_STRUCTURED_EXTRACTION"` / `"NATIVE_PDF_PARSING"` | Enum |

---

## 4. Verification Result Contract (`verification_result.schema.json`)

Constructed from deterministic evaluation of `BidderFact` against `TenderRequirement`, verified against `clause_pairs.jsonl` and `anomalies.jsonl`.

| Canonical Field | SIH Source | Mapping Logic | Transformation / Derived Data |
| --------------- | ---------- | ------------- | ----------------------------- |
| `verification_id` | Generated | `VERIF-{bid_id}-{requirement_id}` | Unique string |
| `requirement_id` | `clause_pairs.jsonl` (`clause_id`) | Direct (e.g. `TENDER-0069/TC-01`) | String |
| `bid_id` | `clause_pairs.jsonl` (`bid_id`) | Direct (e.g. `BID-00001`) | String |
| `fact_id` | Generated | Reference to corresponding `BidderFact.fact_id` | String |
| `status` | `clause_pairs.jsonl` (`compliance_status`) | `"PASS"` / `"FAIL"` / `"REVIEW"` / `"MISSING"` | Enum |
| `severity` | `anomalies.jsonl` (`severity`) or Rule | `"CRITICAL"` for mandatory failures, `"MAJOR"`, `"MINOR"`, `"INFO"` | Severity classification |
| `expected` | `clause_pairs.jsonl` | e.g. `">= 2 years"` | Formatted string |
| `actual` | `clause_pairs.jsonl` | e.g. `"2 years"` | Formatted string |
| `operator_used` | `clause_pairs.jsonl` (`operator`) | e.g. `">="`, `"=="` | String |
| `reason` | `anomalies.jsonl` (`description`) or Generated | Deterministic explanation of evaluation | Descriptive string |
| `evidence` | `evidence.jsonl` / `clause_pairs.jsonl` | Document, page, bounding box, text snippet | Array of evidence objects |
| `anomaly_refs` | `anomalies.jsonl` (`anomaly_id`) | Linked integrity anomaly IDs | Array of strings |
| `requires_human_review`| `clause_pairs.jsonl` (`ground_truth_issue`) | Boolean review flag | Boolean |
| `officer_override` | Runtime/Human action | Defaults to `null` until officer interacts | Nullable object |
