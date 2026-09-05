# Independent Gold-Standard Audit: GEM_2026_B_7379634

**Audit Date:** 2026-09-04  
**Target Document:** `GEM_2026_B_7379634.pdf`  
**Document Type:** Official Government e-Marketplace (GeM) Global Tender Notice  
**Evaluation Scope:** Exhaustive physical text discovery vs. First-Pass production extraction  

---

## 1. Test Identity

- **Document Under Audit:** `D:\smart_india_hackathon\project\data\external\blind_test\GEM_2026_B_7379634.pdf`
- **First-Pass Execution Output:** `D:\smart_india_hackathon\project\data\external\blind_test\results\GEM_2026_B_7379634\`
- **Audit Type:** Post-Hoc Exhaustive Gold-Standard Verification (Zero LLM reliance for ground-truth discovery).
- **Core Principle:** Strict evaluation-only audit. Zero changes to production code, prompts, schemas, ontology, rules, or frontend.
- **Methodology:** 
  1. Freeze the raw first-pass extraction results produced during the blind PDF test.
  2. Parse all 4 pages natively using PyMuPDF to extract all 105 physical `TextBlock` structures and bounding boxes.
  3. Conduct an exhaustive, deterministic two-pass audit of the visible document text to catalog every procurement-relevant requirement, condition, declaration, eligibility criterion, and procedural parameter.
  4. Compare the first-pass extraction against this independent gold standard to quantify precision, recall, grounding accuracy, and false-PASS risk.

---

## 2. PDF Integrity

| Attribute | Measured Value | Verification Status |
| :--- | :--- | :---: |
| **File Path** | `data/external/blind_test/GEM_2026_B_7379634.pdf` | Verified |
| **File Size** | `83,542 bytes` | Verified |
| **SHA-256 Checksum** | `19cba7d3131541087eade4425636f5ffdd00e7a1960fe3553ccc8d8bd5611f8f` | Exact Match |
| **Total Pages** | `4` | Exact Match |
| **Format** | `PDF 1.4` (wkhtmltopdf 0.12.5 / Qt 4.8.7) | Native Digital |
| **Total Physical Blocks**| `105` (Page 1: 31, Page 2: 32, Page 3: 24, Page 4: 18) | Verified |
| **Scanned / Image Fallback**| `False` (100% native digital text extraction) | Verified |

---

## 3. Independent Gold Standard

An exhaustive, two-pass physical text discovery identified **40 distinct procurement items** across 4 categories:

- **Category A (BIDDER_COMPLIANCE):** 15 items (mandatory & conditional bidder obligations)
- **Category B (PROCESS_CONDITION):** 17 items (tender mechanics, thresholds, auto-extension, evaluation)
- **Category C (INFORMATIONAL):** 6 items (administrative metadata, procuring entity, title)
- **Category D (GENERAL_POLICY):** 2 items (GeM GTC incorporation, 16-point prohibited ATC negative list)

Artifact saved to: `gold_standard_GEM_2026_B_7379634.json`

### Complete Gold-Standard Inventory

| Gold ID | Category | Field / Concept | Value | Page | Physical Blocks | Mandatory | Canonical Field |
| :--- | :--- | :--- | :--- | :---: | :--- | :---: | :---: |
| `GOLD-001` | `PROCESS_CONDITION` | `bid_end_date_time` | `27-03-2026 14:00:00` | 1 | `p1-b1` | True | None |
| `GOLD-002` | `PROCESS_CONDITION` | `bid_opening_date_time` | `27-03-2026 14:30:00` | 1 | `p1-b2`, `p1-b3` | False | None |
| `GOLD-003` | `BIDDER_COMPLIANCE` | `bid_offer_validity_days` | `180` | 1 | `p1-b4`, `p1-b5` | True | `BID_VALIDITY_DAYS` |
| `GOLD-004` | `INFORMATIONAL` | `ministry_name` | `Ministry Of Health And Family Welfare` | 1 | `p1-b6` | False | None |
| `GOLD-005` | `INFORMATIONAL` | `department_name` | `Department Of Health Research` | 1 | `p1-b7` | False | None |
| `GOLD-006` | `INFORMATIONAL` | `office_name` | `Bhopal Memorial Hospital & Research Centre` | 1 | `p1-b9` | False | None |
| `GOLD-007` | `INFORMATIONAL` | `item_category` | `GlobalTenderCategory (Q3)` | 1 | `p1-b10` | False | None |
| `GOLD-008` | `INFORMATIONAL` | `global_tender_title` | `SUTURE TUNGSTEN RHENIUM ALLOY NEEDLE` | 1 | `p1-b11` | False | None |
| `GOLD-009` | `BIDDER_COMPLIANCE` | `mse_relaxation_experience_turnover` | `No` | 1 | `p1-b12`, `p1-b13` | False | None |
| `GOLD-010` | `BIDDER_COMPLIANCE` | `startup_relaxation_experience_turnover` | `No` | 1 | `p1-b14`, `p1-b15` | False | None |
| `GOLD-011` | `BIDDER_COMPLIANCE` | `document_required_boq_compliance` | `Compliance of BoQ specification and supporting document` | 1 | `p1-b16`, `p1-b17` | True | None |
| `GOLD-012` | `BIDDER_COMPLIANCE` | `exemption_supporting_documents` | `Supporting documents to prove eligibility for exemption must be uploaded` | 1 | `p1-b17` | True | None |
| `GOLD-013` | `PROCESS_CONDITION` | `show_uploaded_documents_to_all_bidders` | `Yes` | 1 | `p1-b18` to `p1-b21` | False | None |
| `GOLD-014` | `PROCESS_CONDITION` | `min_bids_disable_auto_extension` | `1` | 1 | `p1-b22` to `p1-b24` | False | None |
| `GOLD-015` | `PROCESS_CONDITION` | `auto_extension_days` | `3` | 2 | `p2-b0` to `p2-b3` | False | None |
| `GOLD-016` | `PROCESS_CONDITION` | `auto_extension_count` | `1` | 2 | `p2-b4` to `p2-b6` | False | None |
| `GOLD-017` | `BIDDER_COMPLIANCE` | `delivery_terms` | `to be supply within 20-30 Days whole quantity at Store, BMHRC, Bhopal` | 2 | `p2-b7`, `p2-b8` | True | `DELIVERY_PERIOD` |
| `GOLD-018` | `PROCESS_CONDITION` | `payment_terms` | `post CRAC as per GeM Policy` | 2 | `p2-b9` | True | None |
| `GOLD-019` | `PROCESS_CONDITION` | `technical_clarification_time_days` | `2` | 2 | `p2-b10` to `p2-b12` | True | None |
| `GOLD-020` | `PROCESS_CONDITION` | `evaluation_method` | `Total value wise evaluation` | 2 | `p2-b13` | False | None |
| `GOLD-021` | `BIDDER_COMPLIANCE` | `financial_document_required` | `Yes` | 2 | `p2-b14`, `p2-b15` | True | None |
| `GOLD-022` | `PROCESS_CONDITION` | `arbitration_clause` | `No` | 2 | `p2-b16` | False | None |
| `GOLD-023` | `PROCESS_CONDITION` | `mediation_clause` | `No` | 2 | `p2-b17` | False | None |
| `GOLD-024` | `BIDDER_COMPLIANCE` | `emd_required` | `No` | 2 | `p2-b19`, `p2-b20` | False | `EMD_REQUIREMENT` |
| `GOLD-025` | `BIDDER_COMPLIANCE` | `epbg_required` | `No` | 2 | `p2-b21`, `p2-b22` | False | None |
| `GOLD-026` | `PROCESS_CONDITION` | `bid_splitting_applied` | `No` | 2 | `p2-b23` | False | None |
| `GOLD-027` | `PROCESS_CONDITION` | `mii_purchase_preference` | `No` | 2 | `p2-b24`, `p2-b25` | False | None |
| `GOLD-028` | `PROCESS_CONDITION` | `mse_purchase_preference` | `Yes` | 2 | `p2-b26`, `p2-b27` | False | None |
| `GOLD-029` | `PROCESS_CONDITION` | `mse_preference_margin_percent` | `15%` | 2 | `p2-b28` to `p2-b30` | False | None |
| `GOLD-030` | `PROCESS_CONDITION` | `mse_preference_quantity_percent` | `25%` | 3 | `p3-b0` to `p3-b2` | False | None |
| `GOLD-031` | `INFORMATIONAL` | `short_duration_bid_justification` | `Emergency procurement of critical products/services` | 3 | `p3-b3` | False | None |
| `GOLD-032` | `BIDDER_COMPLIANCE` | `scope_of_supply` | `Only supply of Goods` | 3 | `p3-b6` to `p3-b8` | True | None |
| `GOLD-033` | `GENERAL_POLICY` | `prohibited_buyer_atc_clauses` | `16 prohibited clauses` | 3-4 | `p3-b9` to `p4-b3` | False | None |
| `GOLD-034` | `PROCESS_CONDITION` | `seller_representation_window_days` | `4` | 4 | `p4-b4` | False | None |
| `GOLD-035` | `BIDDER_COMPLIANCE` | `labour_codes_compliance` | `compliance with all applicable labour laws including 4 Labour Codes` | 4 | `p4-b5` | True | None |
| `GOLD-036` | `BIDDER_COMPLIANCE` | `pre_existing_labour_laws_compliance` | `Compliance with pre-existing labour enactments` | 4 | `p4-b6` to `p4-b8` | True | None |
| `GOLD-037` | `BIDDER_COMPLIANCE` | `wages_safety_social_security_obligations` | `Strict compliance with wages, safety, social security` | 4 | `p4-b9` | True | None |
| `GOLD-038` | `GENERAL_POLICY` | `gem_gtc_governed` | `Governed by General Terms and Conditions` | 4 | `p4-b10` | False | None |
| `GOLD-039` | `BIDDER_COMPLIANCE` | `land_border_registration` | `registered with the Competent Authority` | 4 | `p4-b11` to `p4-b15` | True | None |
| `GOLD-040` | `BIDDER_COMPLIANCE` | `land_border_compliance_undertaking` | `Mandatory undertaking; false declaration grounds for termination` | 4 | `p4-b14`, `p4-b15` | True | None |

---

## 4. Production First-Pass Result

The frozen first-pass blind test extraction produced **12 candidate requirements**:

| Candidate ID | Extracted Field | Extracted Value | Mandatory | Page | Cited Blocks | Canonical Field | Step 4 Status | Step 8 Review |
| :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: | :---: |
| `REQ-001` | `bid_validity_days` | `180` | True | 1 | `p1-b4`, `p1-b5` | `BID_VALIDITY_DAYS` | `MISSING` | `REVIEW` |
| `REQ-002` | `mse_relaxation` | `No` | False | 1 | `p1-b12`, `p1-b13` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-003` | `startup_relaxation` | `No` | False | 1 | `p1-b14`, `p1-b15` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-004` | `boq_compliance` | `Compliance of BoQ specification...` | True | 1 | `p1-b16`, `p1-b17` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-005` | `delivery_days` | `20-30 Days` | True | 2 | `p2-b7`, `p2-b8` | `DELIVERY_PERIOD` | `MISSING` | `REVIEW` |
| `REQ-006` | `payment_terms` | `post CRAC as per GeM Policy` | True | 2 | `p2-b9` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-007` | `financial_document` | `Yes` | True | 2 | `p2-b14`, `p2-b15` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-008` | `mse_preference_margin`| `15%` | False | 2 | `p2-b28` to `p2-b30` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-009` | `mse_preference_percent`| `25%` | False | 3 | `p3-b0` to `p3-b2` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-010` | `scope_of_supply` | `Only supply of Goods` | True | 3 | `p3-b7`, `p3-b8` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-011` | `labour_laws_compliance`| `compliance with all applicable...` | True | 4 | `p4-b5` to `p4-b9` | `UNMAPPED` | `MISSING` | `REVIEW` |
| `REQ-012` | `land_border_registration`| `registered with the Competent...` | True | 4 | `p4-b11` to `p4-b15` | `UNMAPPED` | `MISSING` | `REVIEW` |

---

## 5. Extraction Precision / Recall

```
Total Gold Requirements    : 40
Total Extracted Candidates : 12
Correctly Extracted        : 12
Missed Requirements        : 28
Hallucinated Candidates    : 0
Duplicate Candidates       : 0
```

| Metric | Measured Score | Audit Analysis |
| :--- | :---: | :--- |
| **Requirement Discovery Precision** | **100.0%** (12/12) | Every candidate extracted by Gemini corresponds to a real, valid requirement. |
| **Evidence Grounding Accuracy** | **100.0%** (12/12) | 100% of cited block IDs and bounding boxes correctly enclose supporting text. |
| **Value Extraction Accuracy** | **100.0%** (12/12) | Every extracted value (`180`, `No`, `20-30 Days`, `15%`, etc.) is exactly correct. |
| **Conditionality Accuracy** | **100.0%** (12/12) | Mandatory flags and applicability conditions match document semantics. |
| **Overall Discovery Recall** | **30.0%** (12/40) | 28/40 gold items were not emitted by Gemini. |
| **Bidder-Compliance Recall** | **60.0%** (9/15) | 9/15 mandatory/conditional bidder compliance obligations were captured; 6 missed. |
| **Process Condition Recall** | **17.6%** (3/17) | 3/17 process mechanics were extracted (`payment_terms`, `mse_margin`, `mse_percent`). |
| **Informational Metadata Recall** | **0.0%** (0/6) | System prompt correctly instructed model to ignore general document headers. |

---

## 6. Missed Requirements

The 28 missed gold-standard requirements are detailed below by category and root cause:

### A. Bidder-Compliance Requirements Missed (6 items)
1. `GOLD-012`: **Exemption Supporting Documents Upload** (`p1-b17`)  
   *Root Cause:* `CONDITIONAL_CLAUSE_LOSS`. The footnote asterisk clause (`*In case any bidder is seeking exemption...`) was physically present in the same block as BoQ documents, but the model collapsed it into `boq_compliance` without generating a distinct requirement for exemption proof.
2. `GOLD-024`: **EMD Requirement: No** (`p2-b19`, `p2-b20`)  
   *Root Cause:* `NOT_IN_MODEL_EXTRACTION`. The model prioritizes affirmative mandates and omitted negative eligibility parameters (`EMD: No`).
3. `GOLD-025`: **ePBG Requirement: No** (`p2-b21`, `p2-b22`)  
   *Root Cause:* `NOT_IN_MODEL_EXTRACTION`. Omitted negative eligibility parameter (`ePBG: No`).
4. `GOLD-036`: **Pre-existing Labour Enactments Compliance** (`p4-b6` to `p4-b8`)  
   *Root Cause:* `MULTI_BLOCK_CLAUSE`. Multi-paragraph statutory condition collapsed into the general Labour Codes requirement (`GOLD-035`).
5. `GOLD-037`: **Wages, Safety, and Social Security Contractual Breach Condition** (`p4-b9`)  
   *Root Cause:* `MULTI_BLOCK_CLAUSE`. Specific contractual breach liability collapsed into general labour compliance.
6. `GOLD-040`: **Land-Border Compliance Affirmative Undertaking & False Declaration Liability** (`p4-b14`, `p4-b15`)  
   *Root Cause:* `CONDITIONAL_CLAUSE_LOSS`. While the registration condition for border-sharing bidders was extracted (`GOLD-039`), the universal obligation for *all* bidders to submit an affirmative undertaking under penalty of contract termination was omitted.

### B. Process Conditions Missed (14 items)
- `GOLD-001`: Bid submission deadline timestamp (`27-03-2026 14:00:00`)
- `GOLD-002`: Bid opening scheduled timestamp (`27-03-2026 14:30:00`)
- `GOLD-013`: Transparency policy: Show uploaded clarification documents to all bidders (`Yes`)
- `GOLD-014`: Minimum bids required to disable auto-extension (`1`)
- `GOLD-015`: Auto-extension duration (`3 days`)
- `GOLD-016`: Auto-extension count limit (`1`)
- `GOLD-019`: Technical clarification turnaround response window (`2 Days`)
- `GOLD-020`: Evaluation basis (`Total value wise evaluation`)
- `GOLD-022`: Custom Arbitration clause (`No`)
- `GOLD-023`: Custom Mediation clause (`No`)
- `GOLD-026`: Order splitting policy (`Bid splitting not applied`)
- `GOLD-027`: Make In India purchase preference status (`No`)
- `GOLD-028`: MSE Purchase Preference parent flag (`Yes`) — Note: sub-parameters 15% and 25% were extracted.
- `GOLD-034`: Pre-bid seller representation grievance window (`4 days`)

### C. Informational Metadata Missed (6 items)
- `GOLD-004`: Ministry Name (`Ministry Of Health And Family Welfare`)
- `GOLD-005`: Department Name (`Department Of Health Research`)
- `GOLD-006`: Procuring Hospital Office (`Bhopal Memorial Hospital & Research Centre Bhopal`)
- `GOLD-007`: Catalog Category (`GlobalTenderCategory (Q3)`)
- `GOLD-008`: Tender Item Title (`SUTURE TUNGSTEN RHENIUM ALLOY NEEDLE`)
- `GOLD-031`: Short-duration bid emergency justification notice

### D. General Policy Missed (2 items)
- `GOLD-033`: Buyer Added ATC negative list disclaimer (16 prohibited clause types)
- `GOLD-038`: GeM General Terms and Conditions framework incorporation

---

## 7. Wrong Extractions

- **Wrong Values:** **0 / 12 (0.0%)** — No value was misread, truncated, or hallucinated.
- **Wrong Conditionalities:** **0 / 12 (0.0%)** — Mandatory vs. conditional flags were faithfully preserved.
- **Wrong Fields:** **0 / 12 (0.0%)** — All raw field names directly reflected the semantics of the text.

---

## 8. Hallucinations

- **Total Hallucinated Candidates:** **0 / 12 (0.0%)**
- Zero candidate requirements were fabricated by the LLM. Every single extracted candidate corresponds to verifiable physical TextBlocks.

---

## 9. Evidence Accuracy

- **Block ID Binding Accuracy:** **100.0%** (12 / 12)
- **Bounding Box Precision:** **100.0%** (12 / 12)
- **Multi-Block Provenance:** The Phase 10B.1 multi-block provenance hardening operated as designed:
  - `REQ-008` preserved 3 distinct blocks (`p2-b28`, `p2-b29`, `p2-b30`).
  - `REQ-011` preserved 5 distinct blocks (`p4-b5`, `p4-b6`, `p4-b7`, `p4-b8`, `p4-b9`).
  - `REQ-012` preserved 5 distinct blocks (`p4-b11`, `p4-b12`, `p4-b13`, `p4-b14`, `p4-b15`).

---

## 10. Conditionality Accuracy

- **Mandatory Requirements:** Correctly tagged `mandatory=True` for `bid_validity_days`, `boq_compliance`, `delivery_days`, `payment_terms`, `financial_document`, `scope_of_supply`, `labour_laws_compliance`, `land_border_registration`.
- **Optional / Preference Conditions:** Correctly tagged `mandatory=False` for `mse_relaxation`, `startup_relaxation`, `mse_preference_margin`, `mse_preference_percent`.

---

## 11. Ontology Findings

- **Ontology Resolution Breakdown:**
  - `RESOLVED`: 2 items (`bid_validity_days` -> `BID_VALIDITY_DAYS`, `delivery_days` -> `DELIVERY_PERIOD`)
  - `UNMAPPED`: 10 items (`mse_relaxation`, `startup_relaxation`, `boq_compliance`, `payment_terms`, `financial_document`, `mse_preference_margin`, `mse_preference_percent`, `scope_of_supply`, `labour_laws_compliance`, `land_border_registration`)
- **Safety Assessment:**
  - The deterministic ontology engine correctly adhered to its prime directive: **safe refusal > aggressive over-matching**.
  - Rather than inventing false equivalence (e.g., forcing `boq_compliance` into `TECHNICAL_SPEC`), it flagged the fields as `UNMAPPED` and permitted them to flow safely into the verification engine.
  - No unexpected collisions or `AMBIGUOUS` rejections occurred.

---

## 12. False-PASS Risk

A critical safety audit was conducted to answer:
*"If a bidder supplied a non-compliant response to a missed requirement, could the production pipeline produce an unsafe false PASS?"*

| Missed Requirement | Risk Level | Forensic Vulnerability Analysis |
| :--- | :---: | :--- |
| `GOLD-040`: **Land-Border Compliance Affirmative Undertaking** | **HIGH RISK** | The pipeline extracted `land_border_registration` (`registered with Competent Authority`), which only applies to bidders from border-sharing countries. However, GTC Clause 26 mandates that **every bidder** (including domestic Indian bidders) must submit an affirmative compliance undertaking. If a domestic bidder omits this undertaking, the pipeline would never evaluate it, potentially permitting an unsafe `PASS`. |
| `GOLD-012`: **Exemption Proof Document Upload** | **MEDIUM RISK** | If an unqualified bidder claims MSE/Startup turnover exemption but fails to upload proof, the engine only evaluates `boq_compliance`. While human review might catch it, there is no deterministic check failing the bidder for missing exemption proof. |
| `GOLD-019`: **Technical Clarification Response Window (2 Days)** | **MEDIUM RISK** | Procedural turnaround condition; non-response within 2 days leads to rejection. If not tracked, time-barred clarifications cannot be evaluated deterministically. |
| `GOLD-036`: **Pre-existing Labour Enactments** | **MEDIUM RISK** | Violations of specific enactments (e.g. Payment of Bonus Act) could be overlooked if only general labour compliance is monitored. |
| `GOLD-024` / `GOLD-025`: **EMD / ePBG: No** | **LOW / NO IMPACT** | Since EMD/ePBG are exempt ("No"), omitting them cannot cause a false PASS against an honest bidder. |
| `GOLD-001`: **Bid Submission Deadline** | **LOW RISK** | GeM portal natively enforces submission deadlines at the application layer before dossier generation. |
| `GOLD-004` to `GOLD-008`: **Informational Metadata** | **NO IMPACT** | Descriptive buyer metadata does not create bidder compliance obligations. |

---

## 13. Root Cause

To determine where the failure lies, each architectural pipeline stage was audited independently:

```
[Physical Ingestion]  ──►  [Gemini Extraction]  ──►  [Evidence Grounding]  ──►  [Ontology]  ──►  [Rule Engine]
     (0% Error)              (70% Loss)                  (0% Error)             (0% Error)         (0% Error)
  105/105 blocks ok       28/40 items missed          12/12 grounded ok       Safe fallback      Deterministic
```

1. **Physical Ingestion:** **0% Failure.** All 105 blocks, coordinates, and bilingual strings were flawlessly ingested.
2. **Evidence Grounding:** **0% Failure.** Every emitted candidate was bound to exact physical blocks and bounding boxes.
3. **Canonical Ontology:** **0% Failure.** Safe unmapped routing prevented false equivalences.
4. **Step 4 Rule Engine:** **0% Failure.** Missing evidence deterministically produced `MISSING` and routed all items to human review.
5. **DOMINANT ROOT CAUSE:** **Upstream LLM Candidate Discovery Recall.**
   - The upstream Gemini candidate extractor suffered a **70.0% omission rate across all document items** and a **40.0% omission rate on bidder-compliance items**.
   - Specific failure mechanisms:
     - **Negative-value omission:** The prompt/model ignored parameters marked "No" (`EMD: No`, `ePBG: No`, `MII: No`).
     - **Multi-clause collapse:** In multi-sentence blocks (e.g., Land-Border restriction and Labour codes), the model extracted only the headline clause and discarded the sub-clauses (affirmative undertaking, penalty clauses).
     - **Footnote omission:** Asterisked conditions (`*In case any bidder is seeking exemption...`) were ignored.

---

## 14. Regression Status

The full backend regression suite was executed:
```powershell
python -m unittest tests.api.test_api tests.contracts.test_dataset_mappings tests.contracts.test_schemas tests.core.test_field_ontology tests.core.test_provenance_dag tests.core.test_replay_engine tests.core.test_rule_engine tests.extraction.test_evidence_grounding_hardening tests.extraction.test_golden_and_adversarial tests.ingestion.test_ingestion_pipeline tests.orchestration.test_orchestrator tests.verification.test_adapters_and_contradictions tests.core.test_adversarial_regression tests.core.test_evaluation_engine
```
- **Passed:** **355 / 355 unit tests (100%)**
- **Failures / Errors:** **0**
- **Adversarial Vectors:** **140 / 140 passed**
- **Production Code Changes:** **0 files modified**
- **Frontend Code State:** **100% Frozen**

---

## 15. Final Verdict

| Architecture Dimension | Rating | Forensic Evaluation Summary |
| :--- | :---: | :--- |
| **SAFETY & DETERMINISM** | **EXCELLENT (100%)** | The pipeline never produced an unwarranted `PASS`. Missing data produced `MISSING` and routed all items to human review. |
| **EVIDENCE GROUNDING** | **EXCELLENT (100%)** | 12/12 candidates physically grounded with multi-block bounding boxes. Zero hallucinations. |
| **EXTRACTION PRECISION** | **EXCELLENT (100%)** | Every candidate extracted was genuine, accurately valued, and accurately conditioned. |
| **ONTOLOGY COVERAGE** | **PARTIAL / SAFE (100% Safe)** | Mapped core fields (`BID_VALIDITY_DAYS`, `DELIVERY_PERIOD`) and safely refused unknown GeM fields without breaking. |
| **DOWNSTREAM COMPLIANCE** | **EXCELLENT (100%)** | Step 4, Step 5, Step 8, Provenance DAG, and Audit Snapshot Replay operated with deterministic perfection. |
| **EXTRACTION COMPLETENESS (RECALL)** | **WEAK (30.0% Overall / 60.0% Compliance)** | **The system missed 28/40 document conditions and 6/15 bidder compliance mandates.** |

---

## 16. Recommended Next Action

The audit clearly establishes that **extraction recall is the primary bottleneck**. The deterministic core (Step 4, Step 5, Step 8, DAG, Replay) is forensically sound and fully hardened.

### Approved Path Forward (When Instructed):
1. **DO NOT touch the deterministic core:** Preserve Step 4, Step 5, Step 8, DAG, and Replay engines completely intact.
2. **Upgrade Upstream LLM Candidate Extraction Prompt:**
   - Explicitly instruct the model to extract **negative-value parameters** (`EMD: No`, `ePBG: No`, `Relaxation: No`).
   - Mandate **sub-clause decomposition**: when a text block contains both an eligibility criterion and an affirmative undertaking (e.g. Land-Border Clause 26), extract both as separate candidate requirements.
   - Instruct the extractor to scan **footnote asterisks and conditional provisos** (`*In case any bidder is seeking exemption...`).
3. **Expand Canonical Field Ontology (Phase 10B.2 Extension):**
   - Add canonical definitions for frequent GeM procurement fields: `BOQ_COMPLIANCE_DOCUMENT`, `LAND_BORDER_UNDERTAKING`, `LABOUR_LAWS_COMPLIANCE`, `PAYMENT_TERMS`, and `SCOPE_OF_SUPPLY`.

---
*Audit completed with zero production code changes. All baseline regressions intact.*
