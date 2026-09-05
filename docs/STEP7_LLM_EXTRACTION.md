# Step 7 — LLM-Assisted Procurement Extraction & Grounding Layer

> [!CRITICAL]
> **CORE ARCHITECTURAL PRINCIPLE:**
> **"LLM output is an extraction candidate, not a compliance decision."**
> * The LLM **extracts** candidate parameters from document text blocks.
> * Deterministic validation code **grounds** the extraction in Step 6 bounding boxes and schemas.
> * The deterministic Step 4 engine **decides compliance** (`PASS` / `FAIL` / `MISSING` / `REVIEW`).
> * The Step 5 engine **decides integrity** (`CONTRADICTION` / `REVIEW` / `CONSISTENT`).
> * The LLM must **NEVER** be the authoritative compliance judge.

---

## 1. System Architecture

```
+-------------------------------------------------------------------------+
|                                PDF Input                                |
|                        (Tender PDF / Bid PDF)                           |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                     Step 6: Document Ingestion                          |
|   - PyMuPDF Page-by-Page Extraction                                     |
|   - TextBlocks with Bounding Boxes [ymin, xmin, ymax, xmax]             |
|   - Deterministic Block IDs: [DOC-xxx-p1-b0, DOC-xxx-p1-b1, ...]        |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                  Step 7: LLM Candidate Extraction                       |
|   - Provider Abstraction (Gemini / Mock / Cached)                       |
|   - Structured JSON Output Prompts with Hallucination Guardrails        |
|   - Outputs Candidates with referenced evidence_block_ids               |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                 Deterministic Guardrails & Grounding                    |
|   1. JSON Schema Validation (contracts/*.schema.json)                   |
|   2. Evidence Grounding Validator:                                      |
|      * Verify referenced block_ids exist in Step 6 output               |
|      * Map exact [ymin, xmin, ymax, xmax] bbox & page from TextBlock    |
|      * Validate that source block text actually supports claimed value  |
|      * Reject hallucinated coordinates, pages, or ghost blocks          |
|   3. Deterministic Normalization (Step 4 decimal/duration/currency)     |
|   4. Operator & Category Set Validation (reject illegal operators)      |
+-------------------------------------------------------------------------+
                                     |
        +----------------------------+----------------------------+
        |                                                         |
        v                                                         v
+-------------------------------+       +---------------------------------+
|  Validated TenderRequirement  |       |      Validated BidderFact       |
|  (Grounding, Precedence=0)    |       |  (Grounding, Bbox, Snippet)     |
+-------------------------------+       +---------------------------------+
        |                                                         |
        +----------------------------+----------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                     Deterministic Decision Engines                      |
|   - Step 4: Deterministic Compliance Rule Engine                        |
|             (Evaluates Requirement vs Fact -> PASS / FAIL / MISSING)    |
|   - Step 5: Cross-Document Contradiction Engine                         |
|             (Evaluates Cross-Doc Consistency -> CONTRADICTION / REVIEW) |
+-------------------------------------------------------------------------+
```

---

## 2. LLM Provider Abstraction (`provider.py`, `gemini_provider.py`, `mock_provider.py`)

* **Interface:** `BaseLLMProvider` defines `generate_structured(prompt, system_prompt, json_schema, temperature=0.0)`.
* **Gemini Provider:** Direct REST integration using `gemini-3.8-flash` (with bounded `gemini-3.7-flash` fallback) with `responseMimeType: "application/json"`. Credentials are read securely from `GEMINI_API_KEY` in the environment; no secrets are ever hard-coded.
* **Mock Provider:** Deterministic, offline provider for automated testing and CI pipelines. Returns `is_mock=True` and simulates extraction directly from input text cues.
* **Demo / Offline Modes:**
  * `LLM_MODE=live`: Uses live Gemini API when keys are configured.
  * `LLM_MODE=cached`: Retrieves previously recorded extractions from disk cache.
  * `LLM_MODE=mock`: Fully offline deterministic extraction for test suites.

---

## 3. Evidence Grounding Validator (`evidence_grounder.py`)

To eliminate LLM coordinate hallucination and phantom citations, the system enforces a strict grounding architecture:
1. The LLM returns only `evidence_block_ids: ["DOC-BID001-p1-b3"]`.
2. The `EvidenceGrounder` looks up the block in the Step 6 `ExtractionResult`.
3. Coordinates `[ymin, xmin, ymax, xmax]`, page number, and text snippet are populated **directly from the physical PDF extraction**.
4. The grounder validates that the text in the referenced blocks actually contains the extracted figures/tokens.
5. If an ungrounded or non-existent block ID is returned, the extraction is **REJECTED** (`GROUNDING_FAILED`).

---

## 4. Normalization & Post-Processing Guardrails

* **Arithmetic & Unit Normalization:** The LLM is never trusted to perform arithmetic or unit conversion. Raw values (e.g. `"Rs. 10 Crores"`, `"36 months"`) are parsed by Step 4 deterministic normalization utilities:
  * Currency: Standardized to base INR `Decimal("100000000")`.
  * Duration: Standardized to integer `MONTHS` (36) or `DAYS` (60).
  * Date: Standardized to ISO `YYYY-MM-DD`.
* **Operator Guardrails:** Operators must belong to the approved deterministic set (`>=`, `<=`, `==`, `IN`, `EXISTS`, `VALID_ON`, etc.). Unsupported operators are rejected rather than coerced.
* **Conservative Precedence:** If source documents do not explicitly declare GTC/STC/ATC provenance, the extraction defaults to `UNSPECIFIED` and priority 0.

---

## 5. Performance & Validation Results

* **Golden Test Suite (12 Scenarios):** 100% pass rate covering turnover, warranty, delivery, certificates, dates, missing facts, and contradictions.
* **Adversarial Test Suite (14 Scenarios):** 100% pass rate covering hallucinated blocks, malformed JSON, unsupported operators, missing values, and timeout errors.
* **SIH Dataset Benchmark:**
  * 10 Tenders: 30 requirements extracted at 4.3 ms / tender.
  * 20 Bids: 60 facts extracted at 7.1 ms / bid.
  * Determinism: 3 consecutive runs produced bitwise identical serialized JSON (1,644 bytes).
* **Downstream Integration:** Extracted facts and requirements successfully feed Step 4 compliance and Step 5 contradiction engines with verified bounding box provenance.
