# Step 5 — Cross-Document Contradiction Engine

> [!IMPORTANT]
> **GOVERNMENT VERIFICATION IS MOCKED FOR THE HACKATHON PROTOTYPE. NO LIVE GOVERNMENT API IS ACCESSED.**

---

## 1. Architectural Role & Integrity Philosophy

In public procurement submissions, bidders upload multiple documents (Technical Bid, Financial Statements, OEM Authorization, Self-Declarations, CA Certificates). Unscrupulous bidders or careless errors often lead to internal inconsistencies across these documents.

The **Cross-Document Contradiction Engine** (`backend/core/contradiction_engine.py`) is responsible for:
1. Detecting conflicting claims across documents within the **same bid**.
2. Normalizing values before comparison to avoid false alarms on benign formatting variations.
3. Distinguishing between exact deterministic contradictions, benign representations, and ambiguous variants requiring human review.
4. Preserving complete evidence (document, page, bounding box, text snippet) for **both sides** of any discrepancy.

```
       Document A (Technical Bid)             Document B (Annexure IV)
      "GSTIN: 29SYNTH0000003F1Z"             "GSTIN: 29SYNTH0000103F1Z"
                   \                                     /
                    \                                   /
                     v                                 v
          +---------------------------------------------------------+
          |         CrossDocumentContradictionEngine                |
          |  1. Group facts by field (e.g. 'gstin')                |
          |  2. Normalize comparable representations               |
          |  3. Detect conflict: 29SYNTH0000003F1Z != 29...103F1Z   |
          |  4. Preserve evidence A and evidence B                 |
          +---------------------------------------------------------+
                                     |
                                     v
                       +---------------------------+
                       |     IntegrityFinding      |
                       | Status: CONTRADICTION     |
                       | Severity: HIGH            |
                       | Requires Review: True     |
                       +---------------------------+
```

---

## 2. IntegrityFinding Model

Every detected discrepancy is represented by the canonical `IntegrityFinding` structure:

| Field | Type | Description |
| ----- | ---- | ----------- |
| `finding_id` | `str` | Unique finding identifier (e.g. `INT-BID-0001-GSTIN-001`). |
| `bid_id` | `str` | Bidder submission identifier. |
| `finding_type` | `str` | Categorical classification (`GSTIN_CONTRADICTION`, `WARRANTY_CONTRADICTION`, etc.). |
| `field` | `str` | Compliance dimension (`gstin`, `warranty_years`, `turnover_cr`, etc.). |
| `severity` | `str` | `HIGH` (direct contradiction), `MEDIUM` (variant review), `INFO` (benign). |
| `status` | `str` | `CONTRADICTION`, `REVIEW`, or `CONSISTENT`. |
| `description` | `str` | Plain-English explanation for procurement officers. |
| `value_a` / `value_b` | `Any` | Values extracted from Document A and Document B. |
| `evidence_a` / `evidence_b`| `dict` | Provenance pointers: `{document, page, bbox, snippet}`. |
| `requires_human_review` | `bool` | `True` for `CONTRADICTION` and `REVIEW`; `False` for `CONSISTENT`. |
| `source` | `str` | Originating engine (`CROSS_DOCUMENT_CONTRADICTION_ENGINE`). |

---

## 3. Normalization and Equivalence Rules

To prevent false alarms, the engine applies strict normalization before comparison:

1. **Identifier Normalization (`gstin`, `pan`, `udyam`):**
   * Case folding (uppercase), whitespace collapsing.
   * Discrepancies represent material identity conflicts $\rightarrow$ `CONTRADICTION` (`HIGH`).
2. **Duration / Warranty Normalization (`warranty_years`, `experience`):**
   * Standardizes units to months using `normalize_duration` (e.g., "3 years" $\equiv$ "36 months").
   * Equivalent values $\rightarrow$ `CONSISTENT`. Differing values $\rightarrow$ `CONTRADICTION`.
3. **Financial / Turnover Normalization (`turnover_cr`, `amount`):**
   * Normalizes Lakhs, Crores, Millions, and Rupee symbols to base Decimal values.
   * Equivalent values $\rightarrow$ `CONSISTENT`. Differing numbers $\rightarrow$ `CONTRADICTION`.
4. **Legal Entity Name Normalization (`company_name`):**
   * Strips abbreviation punctuation dots and collapses whitespace.
   * Replaces common legal suffixes: `PRIVATE LIMITED` $\rightarrow$ `PVT LTD`, `LIMITED` $\rightarrow$ `LTD`, `L.L.P.` $\rightarrow$ `LLP`.
   * **Identical normalized name:** `CONSISTENT` (`BENIGN_NAME_VARIANT`).
   * **Substring / Alias expansion (e.g. name with division/operations appended):** `REVIEW` (`COMPANY_NAME_VARIANT`).
   * **Fundamentally distinct names:** `CONTRADICTION` (`HIGH`).

---

## 4. Separation of Compliance and Integrity

> [!CRITICAL]
> **COMPLIANCE AND INTEGRITY ARE SEPARATE SIGNALS.**
> * The **Deterministic Rule Engine (Step 4)** evaluates whether the bidder satisfies the tender requirement (`PASS`, `FAIL`, `N/A`).
> * The **Contradiction Engine (Step 5)** evaluates whether documents are internally consistent (`CONTRADICTION`, `REVIEW`, `CONSISTENT`).
> * An integrity anomaly **NEVER silently changes compliance PASS to FAIL**.
> * An integrity anomaly is flagged as a high-priority risk finding for human procurement officer review. The system explains $\rightarrow$ the human decides.

---

## 5. Scope Limitations

1. **Deterministic vs Semantic:** The contradiction engine handles structured, normalizable data (dates, durations, currencies, identifiers, legal names). Complex narrative semantic differences remain flagged as `REVIEW` rather than evaluated autonomously.
2. **Zero LLM in Core:** No LLM is invoked during contradiction evaluation, ensuring 100% bitwise determinism and instantaneous execution.
3. **No Fraud Allegation:** The engine outputs `CONTRADICTION`, `INCONSISTENCY`, or `REVIEW_REQUIRED`. It never outputs legal conclusions such as "Fraud" or "Forgery".
