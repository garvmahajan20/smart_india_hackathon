# GSTINAPI Private GST Provider Integration

**Platform:** SIH26100 GeM Bid Compliance Verification Platform  
**Component:** Backend Statutory Identification & GST Compliance Layer  
**Status:** IMPLEMENTED, LIVE SANDBOX VALIDATED & TEST SUITE VERIFIED  
**Package:** `backend.integrations.gst`  
**Provider Documentation:** [https://www.gstinapi.in/docs](https://www.gstinapi.in/docs)  

---

## 1. Architectural Overview & Design Principles

The GSTINAPI integration layer delivers automated, authoritative GST registration verification, taxpayer profiling, and multi-year return filing history for bidders participating in Government e-Marketplace (GeM) tenders.

### Core Architectural Principles:
1. **Real HTTP & Production-Grade Sandbox Support:** Communicates with the official GSTINAPI REST endpoints (`https://www.gstinapi.in/v1/gstin/...`). Supports non-billable test GSTINs (`00AAAAA0000A1ZT`) with 0 credit deduction, as well as live production lookups.
2. **Authority Separation & Deterministic Compliance:** The external GSTINAPI provider functions solely as an **authoritative evidence provider**. It NEVER makes the final qualification or compliance decision. Deterministic rule engines evaluate eligibility facts against tender criteria.
3. **Credit Conservation & Pre-Flight Validation:** Pre-flight statutory regex checks (`^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$`) reject malformed GSTIN inputs before any network socket is opened, preventing credit waste and unnecessary billable hits.
4. **Strict Zero Secret Leakage:** The API key is loaded strictly from environment variable `GSTINAPI_API_KEY`. It is NEVER hardcoded, logged in plain text, stored in database fields, or exposed in exceptions. HTTP headers are systematically scrubbed (`redact_sensitive_headers`) and API keys are represented in audit logs as truncated SHA-256 digests.
5. **No Fake Bounding Boxes:** Digital registry evidence is recorded with `source_type="GSTINAPI_REGISTRY"`, `extraction_method="GSTINAPI_REST_LOOKUP"`, and bounding box coordinates set to `[0.0, 0.0, 0.0, 0.0]`.
6. **Strict Invariant: No Positive Facts on Failure:** Upstream HTTP 404, 401, 402, 429, 502, timeouts, and network unreachable errors MUST NOT manufacture positive `BidderFact` records. They yield an empty list of facts and trigger appropriate review statuses.
7. **Strict Acyclic Provenance:** `GSTINAPIEvidenceAdapter.integrate_with_dag` connects external registry records to derived facts while enforcing directed acyclic graph (DAG) topological invariants validated via Kahn\'s algorithm.
8. **Replay Invariance:** During verification replay and offline audit checks, cached responses and hashes are reused with zero outgoing network calls.
9. **Backend-Only Isolation:** All code is strictly localized to `backend/`, `tests/`, and `docs/`. The frontend (`frontend/`) remains untouched for frontend owner Utsav.

---

## 2. Supported Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/gstin/{gstin}` | Core taxpayer identity, status (Active/Cancelled), legal name, state |
| `GET` | `/v1/gstin/{gstin}?include=profile` | Enriched taxpayer profile (nature of business, constitution) |
| `GET` | `/v1/gstin/{gstin}/returns?fy=YYYY-YY` | Filing history (GSTR-1, GSTR-3B) with ARN, period, status |
| `GET` | `/v1/gstin/{gstin}/filing-preference?fy=YYYY-YY` | QRMP filing preference (Monthly vs Quarterly) |
| `GET` | `/v1/gstin/{gstin}/compliance?fy=YYYY-YY` | Filing count summary by return type |
| `GET` | `/v1/gstin/stats/me` | Account diagnostics & credit balance check |

---

## 3. Configuration & Environment Variables

| Variable | Type | Default | Description |
|---|---|---|---|
| `GSTINAPI_API_KEY` | `string` | `""` | Authoritative GSTINAPI API key (Header `x-api-key`) |
| `GSTINAPI_BASE_URL` | `string` | `https://www.gstinapi.in` | Provider base URL |
| `GSTINAPI_ENABLED` | `bool` | `true` (if key set) | Integration kill-switch |
| `GSTINAPI_ENVIRONMENT` | `string` | `production` | Environment tag (sandbox / production) |
| `GSTINAPI_TIMEOUT_SECONDS` | `int` | `10` | HTTP request timeout |
| `GSTINAPI_MAX_RETRIES` | `int` | `2` | Retry attempts for 429 and 502 |

---

## 4. Retry & Rate Limiting Policy

- **429 Rate Limit (60 req/min):** Retries up to 2 times with exponential backoff (`0.5s * 2^attempt`).
- **502 Bad Gateway:** Retries up to 2 times with exponential backoff.
- **400 Bad Request:** **Never retries**. Fails immediately to preserve credits.
- **401/403 Authentication Error:** **Never retries**. Logs audit alert.
- **402 Payment Required / Credits Exhausted:** **Never retries**. Fails immediately and signals manual review.
- **404 Not Found:** **Never retries**. Flags taxpayer as `NOT_VERIFIED` / unregistered.

---

## 5. Response & Fact Mapping

A verified response (`GSTVerificationStatus.VERIFIED`) generates the following canonical `BidderFact` items:

1. `GSTIN`: Verified 15-character GSTIN
2. `LEGAL_ENTITY_NAME`: Authoritative registered company name
3. `GST_STATUS`: Active status confirmed in GST portal
4. `TAXPAYER_TYPE`: Regular / Composition / SEZ
5. `GST_REGISTRATION_DATE`: Date of registration
6. `PAN`: Embedded 10-character PAN extracted from characters 3–12
7. `GST_FILING_COMPLIANCE`: Return count summary for specified financial year

---

## 6. FastAPI Surface

- `GET  /api/v1/integrations/gst/status` - Current status, environment, base URL, masked key
- `POST /api/v1/integrations/gst/verify` - Full verification with optional profile and returns
- `GET  /api/v1/integrations/gst/{gstin}/returns` - Direct filing history for financial year
- `GET  /api/v1/integrations/gst/{gstin}/compliance` - Filing compliance summary
- `GET  /api/v1/integrations/gst/audit-logs` - Sanitized, non-repudiable audit events

---

## 7. Verification Proof

- **Live Sandbox Test:** Verified against `https://www.gstinapi.in/v1/gstin/00AAAAA0000A1ZT?include=profile`. Succeeded with HTTP 200, `"test": true`, `"billed_to": "test"`, `"status": "Active"`, 0 credits deducted.
- **Integration Test Suite:** `tests/integrations/test_gstinapi.py` (15/15 tests passing with mocked HTTP).
- **Adversarial & Regression Test Suite:** Full suite (562 tests, 140/140 adversarial attacks) passing at 100%.
