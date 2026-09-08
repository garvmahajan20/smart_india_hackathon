# Government Mock Registries Documentation (SIH26100)

## 1. Executive Summary & Governance Notice

> **CRITICAL GOVERNANCE INVARIANT**
> All registries detailed in this document are strictly **`INTERNAL_MOCK_REGISTRY`** implementations designed for hackathon demonstration, reproducible local testing, and deterministic evaluation where official, free, self-service Government of India APIs are unavailable without production departmental credentials.
> - **Source Type**: `INTERNAL_MOCK_REGISTRY`
> - **Dataset Version**: `MOCK_REGISTRY_DATASET_V1`
> - **Live Government Verified**: `False` (Explicitly marked and disclosed)
> - **Network Calls**: `0` (Zero external network dependencies, 100% in-memory deterministic replay)

---

## 2. Integration Architecture & Registry Inventory

| Registry Code | Authority / Source Domain | Primary Query Keys | Synthetic Scenarios Covered | Adapter Class |
| :--- | :--- | :--- | :--- | :--- |
| **`MOCK_ITD`** | Income Tax Department (ITR) | `pan`, `ack_number` | Active return (25 Cr), Defaulter/Unfiled, Name mismatch, Turnover contradiction | `MockITDAdapter` |
| **`MOCK_MCA21`** | Ministry of Corporate Affairs | `cin`, `company_name` | Active Private Ltd, Inactive/Liquidation, CIN name mismatch | `MockMCA21Adapter` |
| **`MOCK_NSIC`** | National Small Industries Corp | `certificate_number`, `enterprise_name` | Active Micro enterprise, Expired certificate, Name mismatch | `MockNSICAdapter` |
| **`MOCK_OEM`** | OEM Manufacturer Auth (MAF) | `auth_number`, `oem:bidder` | Valid active auth, Expired auth, Unauthorized/Revoked | `MockOEMAdapter` |
| **`MOCK_MII`** | Make in India / Local Content | `declaration_id`, `mfg:product` | Class-I (65% LC), Class-II (35% LC), Expired declaration | `MockMIIAdapter` |

*Note on BIS*: Explicit code audit confirmed zero Bureau of Indian Standards rules/requirements in the platform, hence BIS was omitted to prevent dead code.

---

## 3. Strict Compliance Invariants

1. **Fact Gating Rule**:
   - Only adapter responses with `VerificationStatus.VERIFIED` produce authoritative `BidderFact` items.
   - Non-verified, missing, or inactive outcomes strictly return `[]` (empty list of facts), preventing false positives in the deterministic rule engine.
2. **Separation of Evidence vs Compliance (MII)**:
   - `MockMIIAdapter` extracts factual evidence (e.g., `local_content_percentage: 35.0%`, `supplier_class: CLASS_2`) without hardcoding pass/fail. Compliance against tender thresholds is evaluated exclusively by `DeterministicRuleEngine`.
3. **DAG Acyclicity Guarantee**:
   - All synthetic mock registry facts are integrated into `ProvenanceDAG` as grounded physical text blocks (`BLOCK:MOCK_...`) linked via `FACT_GROUNDED_BY` edges.
   - Every graph modification is strictly verified using Kahn's topological sort algorithm (`dag.validate()`).

---

## 4. REST API Surface

- `GET /api/v1/integrations/mock/status`
- `POST /api/v1/integrations/mock/itd/verify`
- `POST /api/v1/integrations/mock/mca21/verify`
- `POST /api/v1/integrations/mock/nsic/verify`
- `POST /api/v1/integrations/mock/oem/verify`
- `POST /api/v1/integrations/mock/mii/verify`
- `POST /api/v1/integrations/mock/verify?registry_name={itd|mca21|nsic|oem|mii}`

---

## 5. Verification Status

All 5 mock adapters, evidence conversion, DAG integration, REST endpoints, and replay consistency are covered by `tests/integrations/test_mock_registries.py` (36 tests, 100% passing).
