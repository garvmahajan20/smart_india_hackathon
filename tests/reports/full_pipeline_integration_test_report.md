# SIH26100 Full Verification Pipeline Integration Test Report

**Generated:** 2026-09-08T18:11:11Z  
**Execution Time:** 0.17 seconds  
**Corpus Type:** `CONTROLLED_TEST_FIXTURES`  
**Scenarios Evaluated:** 7  
**Pass Rate:** 7/7 (100.0%)  

---

## 1. Executive Summary & Verification Path

This integration report documents the exhaustive end-to-end verification of the backend pipeline across all 7 canonical procurement scenarios on controlled test fixtures. Every step of the canonical 16-component path was exercised and strictly validated:

```
Tender requirement (PDF Ingestion) 
  -> Bidder document/fact (Physical Grounding)
  -> External / API / Mock Registry Verification (GST, PAN, Udyam, Debarment, MCA21, OEM, MII, ITD)
  -> Identity Reconciliation (Legal Name, Trade Name, Identifier Cross-Check)
  -> Applicability Filtering (Statutory MSE / Startup Exemptions, Precedence)
  -> Deterministic Compliance Rule Engine
  -> Cross-Document Contradiction & Integrity Engine
  -> Pending Requirements Identification with Actionable Remedies
  -> Compliance Scoring with Hard Mandatory Caps
  -> Deterministic Risk Engine
  -> AI Recommendation with Mandatory Procurement Officer Disclaimer
  -> Provenance DAG Construction & Validation (Acyclic, Reachable)
  -> Audit Record Generation
  -> Deterministic Replay Engine (Zero-Drift Reproducibility)
```

---

## 2. Safety Invariants & Governance Audit

| Safety Invariant | Target | Observed | Status |
| :--- | :--- | :--- | :--- |
| Zero Ungrounded Positive Facts | 100% (0 violations) | 0 violations | PASS |
| Zero False-Pass on Debarred Entities | 0 False Passes | 0 False Passes | PASS |
| Zero False-Pass on Unavailable Registries | 0 False Passes | 0 False Passes (Abstains to REVIEW) | PASS |
| Deterministic Replay Reproducibility | 100.0% | 100.0% | PASS |
| Provenance DAG Acyclicity & Validity | 100.0% | 100.0% | PASS |

---

## 3. Scenario-by-Scenario Evaluation Results

| Scenario | Description | Compliance | Integrity | Overall Status | Score | Risk | AI Verdict | Replay Match |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `SCENARIO_01_CLEAN_BIDDER` | Completely compliant bidder with active regis... | `PASS` | `CONSISTENT` | **`PASS`** | 100.0 | `LOW` | `PASS` | `PASS` |
| `SCENARIO_02_MISSING_MANDATORY` | Mandatory OEM Authorization missing from bid ... | `MISSING` | `CONSISTENT` | **`REVIEW`** | 21.1 | `HIGH` | `REVIEW` | `PASS` |
| `SCENARIO_03_CROSS_DOCUMENT_CONTRADICTION` | Turnover declared as 15.0 Cr in technical bid... | `PASS` | `CONTRADICTION` | **`REVIEW`** | 65.0 | `CRITICAL` | `REVIEW` | `PASS` |
| `SCENARIO_04_REGISTRY_MISMATCH` | Bidder claims OEM Authorization which mock OE... | `PASS` | `CONSISTENT` | **`REVIEW`** | 100.0 | `LOW` | `REVIEW` | `PASS` |
| `SCENARIO_05_DEBARRED_ENTITY` | Bidder is actively blacklisted on government ... | `PASS` | `CONSISTENT` | **`FAIL`** | 0.0 | `CRITICAL` | `FAIL` | `PASS` |
| `SCENARIO_06_UNKNOWN_APPLICABILITY` | Bidder claims Startup waiver without verifiab... | `REVIEW` | `CONSISTENT` | **`REVIEW`** | 25.0 | `HIGH` | `REVIEW` | `PASS` |
| `SCENARIO_07_EXTERNAL_UNAVAILABLE` | External GSTIN API unavailable (503/timeout);... | `PASS` | `CONSISTENT` | **`REVIEW`** | 100.0 | `LOW` | `REVIEW` | `PASS` |

---

## 4. Deep Dive per Canonical Scenario

### Scenario 1: SCENARIO_01_CLEAN_BIDDER
- **Description:** Completely compliant bidder with active registries, no contradictions, and valid evidence
- **Tender ID:** `TENDER-CTRL-001` | **Bid ID:** `BID-CTRL-001`
- **Ingestion:** Tender (1 pages), Bid (1 pages)
- **Discovered Criteria:** 4 requirements, 10 bidder facts (100% physically grounded)
- **Registry Checks:** 7 checks performed (Statuses: `VERIFIED, VERIFIED, NOT_DEBARRED, VERIFIED, VERIFIED, VERIFIED, VERIFIED`)
- **Compliance Outcome:** `PASS` | **Integrity Outcome:** `CONSISTENT`
- **Overall Determination:** **`PASS`** (Score: `100.0`, Risk: `LOW`)
- **AI Recommendation:** Verdict `PASS`
- **Human Review Items:** 0 items queued
- **Pending Requirements:** 0 actionable items generated
- **Provenance DAG:** Valid & Acyclic (`35` nodes, `35` edges)
- **Deterministic Replay:** Reproducible (`True`), mismatches = `0`

### Scenario 2: SCENARIO_02_MISSING_MANDATORY
- **Description:** Mandatory OEM Authorization missing from bid pack; triggers pending requirement and review cap
- **Tender ID:** `TENDER-CTRL-002` | **Bid ID:** `BID-CTRL-002`
- **Ingestion:** Tender (1 pages), Bid (1 pages)
- **Discovered Criteria:** 2 requirements, 4 bidder facts (100% physically grounded)
- **Registry Checks:** 3 checks performed (Statuses: `VERIFIED, VERIFIED, NOT_DEBARRED`)
- **Compliance Outcome:** `MISSING` | **Integrity Outcome:** `CONSISTENT`
- **Overall Determination:** **`REVIEW`** (Score: `21.1`, Risk: `HIGH`)
- **AI Recommendation:** Verdict `REVIEW`
- **Human Review Items:** 1 items queued
- **Pending Requirements:** 1 actionable items generated
- **Provenance DAG:** Valid & Acyclic (`19` nodes, `16` edges)
- **Deterministic Replay:** Reproducible (`True`), mismatches = `0`

### Scenario 3: SCENARIO_03_CROSS_DOCUMENT_CONTRADICTION
- **Description:** Turnover declared as 15.0 Cr in technical bid but 4.5 Cr in financial annexure
- **Tender ID:** `TENDER-CTRL-003` | **Bid ID:** `BID-CTRL-003`
- **Ingestion:** Tender (1 pages), Bid (2 pages)
- **Discovered Criteria:** 1 requirements, 6 bidder facts (100% physically grounded)
- **Registry Checks:** 3 checks performed (Statuses: `VERIFIED, VERIFIED, NOT_DEBARRED`)
- **Compliance Outcome:** `PASS` | **Integrity Outcome:** `CONTRADICTION`
- **Overall Determination:** **`REVIEW`** (Score: `65.0`, Risk: `CRITICAL`)
- **AI Recommendation:** Verdict `REVIEW`
- **Human Review Items:** 1 items queued
- **Pending Requirements:** 0 actionable items generated
- **Provenance DAG:** Valid & Acyclic (`22` nodes, `24` edges)
- **Deterministic Replay:** Reproducible (`True`), mismatches = `0`

### Scenario 4: SCENARIO_04_REGISTRY_MISMATCH
- **Description:** Bidder claims OEM Authorization which mock OEM registry confirms is UNAUTHORIZED / REVOKED
- **Tender ID:** `TENDER-CTRL-004` | **Bid ID:** `BID-CTRL-004`
- **Ingestion:** Tender (1 pages), Bid (1 pages)
- **Discovered Criteria:** 1 requirements, 4 bidder facts (100% physically grounded)
- **Registry Checks:** 3 checks performed (Statuses: `VERIFIED, NOT_DEBARRED, REVIEW`)
- **Compliance Outcome:** `PASS` | **Integrity Outcome:** `CONSISTENT`
- **Overall Determination:** **`REVIEW`** (Score: `100.0`, Risk: `LOW`)
- **AI Recommendation:** Verdict `REVIEW`
- **Human Review Items:** 1 items queued
- **Pending Requirements:** 0 actionable items generated
- **Provenance DAG:** Valid & Acyclic (`14` nodes, `12` edges)
- **Deterministic Replay:** Reproducible (`True`), mismatches = `0`

### Scenario 5: SCENARIO_05_DEBARRED_ENTITY
- **Description:** Bidder is actively blacklisted on government debarment registry; fail-closed hard stop
- **Tender ID:** `TENDER-CTRL-005` | **Bid ID:** `BID-CTRL-005`
- **Ingestion:** Tender (1 pages), Bid (1 pages)
- **Discovered Criteria:** 1 requirements, 4 bidder facts (100% physically grounded)
- **Registry Checks:** 3 checks performed (Statuses: `NOT_FOUND, NOT_FOUND, DEBARRED`)
- **Compliance Outcome:** `PASS` | **Integrity Outcome:** `CONSISTENT`
- **Overall Determination:** **`FAIL`** (Score: `0.0`, Risk: `CRITICAL`)
- **AI Recommendation:** Verdict `FAIL`
- **Human Review Items:** 1 items queued
- **Pending Requirements:** 0 actionable items generated
- **Provenance DAG:** Valid & Acyclic (`15` nodes, `12` edges)
- **Deterministic Replay:** Reproducible (`True`), mismatches = `0`

### Scenario 6: SCENARIO_06_UNKNOWN_APPLICABILITY
- **Description:** Bidder claims Startup waiver without verifiable DPIIT certificate; pipeline abstains to UNKNOWN_REVIEW
- **Tender ID:** `TENDER-CTRL-006` | **Bid ID:** `BID-CTRL-006`
- **Ingestion:** Tender (1 pages), Bid (1 pages)
- **Discovered Criteria:** 1 requirements, 5 bidder facts (100% physically grounded)
- **Registry Checks:** 3 checks performed (Statuses: `IDENTITY_MISMATCH, IDENTITY_MISMATCH, NOT_DEBARRED`)
- **Compliance Outcome:** `REVIEW` | **Integrity Outcome:** `CONSISTENT`
- **Overall Determination:** **`REVIEW`** (Score: `25.0`, Risk: `HIGH`)
- **AI Recommendation:** Verdict `REVIEW`
- **Human Review Items:** 3 items queued
- **Pending Requirements:** 1 actionable items generated
- **Provenance DAG:** Valid & Acyclic (`21` nodes, `13` edges)
- **Deterministic Replay:** Reproducible (`True`), mismatches = `0`

### Scenario 7: SCENARIO_07_EXTERNAL_UNAVAILABLE
- **Description:** External GSTIN API unavailable (503/timeout); system abstains with zero positive fabrication and no false pass
- **Tender ID:** `TENDER-CTRL-007` | **Bid ID:** `BID-CTRL-007`
- **Ingestion:** Tender (1 pages), Bid (1 pages)
- **Discovered Criteria:** 2 requirements, 4 bidder facts (100% physically grounded)
- **Registry Checks:** 3 checks performed (Statuses: `UNVERIFIED, VERIFIED, NOT_DEBARRED`)
- **Compliance Outcome:** `PASS` | **Integrity Outcome:** `CONSISTENT`
- **Overall Determination:** **`REVIEW`** (Score: `100.0`, Risk: `LOW`)
- **AI Recommendation:** Verdict `REVIEW`
- **Human Review Items:** 1 items queued
- **Pending Requirements:** 0 actionable items generated
- **Provenance DAG:** Valid & Acyclic (`19` nodes, `18` edges)
- **Deterministic Replay:** Reproducible (`True`), mismatches = `0`

---

## 5. Architectural Invariants Preserved

1. **Frontend Untouched:** No files in `frontend/` were modified.
2. **Real-World Input PDFs Untouched:** Zero modifications to `data/external/blind_test/`.
3. **Controlled Fixture Discipline:** All new test fixtures in `tests/fixtures/controlled_e2e/` are explicitly watermarked and labeled `CONTROLLED_TEST_FIXTURE`.
4. **Fail-Closed Governance:** Debarred entities, missing mandatory certificates, and unavailable external services never falsely pass.
5. **Authority Disclaimer:** Every recommendation embeds an immutable statutory disclaimer preserving final authority with the Procurement Officer.
