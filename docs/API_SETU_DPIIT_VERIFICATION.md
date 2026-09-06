# API Setu / DPIIT Startup India Recognition Certificate Sandbox Integration

## 1. Overview
This module integrates the official Government of India **API Setu / Department for Promotion of Industry and Internal Trade (DPIIT) Startup India Recognition Certificate Verification API** (`suirc`) into the SIH26100 compliance platform.

- **Authority**: Department for Promotion of Industry and Internal Trade (DPIIT), Ministry of Commerce and Industry
- **API Spec Reference**: `https://sandbox.api-setu.in/sandbox/specfiles/dpiit.yaml`
- **Sandbox Base URL**: `https://sandbox.api-setu.in`
- **Endpoint**: `POST /certificate/v3/dpiit/suirc`
- **Format**: `xml`

---

## 2. Request & Response Specification

### Request Headers
```http
Accept: application/json
Content-Type: application/json
X-APISETU-APIKEY: <configured>
X-APISETU-CLIENTID: in.gov.sandbox
```

### JSON Request Payload
Parameter casing strictly adheres to the official DPIIT YAML specification:
- `REGN_NO`: Startup India recognition / certificate number (e.g. `DIPP12345`)
- `MobileNumber`: Registered mobile number (10 digits)

```json
{
  "txnId": "f7f1469c-29b0-4325-9dfc-c567200a70f7",
  "format": "xml",
  "certificateParameters": {
    "REGN_NO": "DIPP12345",
    "MobileNumber": "9876543210"
  },
  "consentArtifact": {
    "consent": {
      "consentId": "ea9c43aa-7f5a-4bf3-a0be-e1caa24737ba",
      "timestamp": "2026-09-06T12:00:00.000Z",
      "dataConsumer": { "id": "in.gov.sandbox" },
      "dataProvider": { "id": "in.gov.dpiit" },
      "purpose": { "description": "GeM Bid Compliance Startup India Recognition Verification" },
      "user": {
        "idType": "DPIIT_REGN",
        "idNumber": "DIPP12345",
        "mobile": "9876543210",
        "email": "contact@startup.in"
      },
      "data": { "id": "in.gov.dpiit" },
      "permission": {
        "access": "VIEW",
        "dateRange": { "from": "2026-09-06T12:00:00.000Z", "to": "2026-09-06T12:00:00.000Z" },
        "frequency": { "unit": "ONETIME", "value": 1, "repeats": 0 }
      }
    },
    "signature": { "signature": "SHA256withRSA_SIGNED_CONSENT" }
  }
}
```

### Response Mapping
- `HTTP 200` + XML -> Parsed with XXE protection, fields extracted:
  - `certificate_number` / `regn_no`
  - `startup_name`
  - `incorporation_date`
  - `recognition_date`
  - `entity_type` (e.g., `Private Limited Company`, `LLP`)
  - `industry`
  - `sector`
  - Status: `VERIFIED`
- `HTTP 400` -> `INVALID_REQUEST`
- `HTTP 401` -> `ERROR` (Authentication failure)
- `HTTP 404` -> `NOT_VERIFIED` (Recognition record not found in DPIIT registry)
- `HTTP 500, 502, 503, 504` / Timeout -> `UNAVAILABLE` or `ERROR`

---

## 3. Evidence Grounding & Provenance Invariants
1. **Gating Rule**: An unsuccessful or unavailable response **MUST NEVER** produce an authoritative verified `BidderFact`. Only `status == DPIITVerificationStatus.VERIFIED` yields authoritative facts.
2. **EvidenceReference**: Created with document URI `API_SETU:DPIIT:SUIRC:<regn_no>`, `source_type="API_SETU_OFFICIAL_REGISTRY"`, and bounding box `[0.0, 0.0, 0.0, 0.0]`.
3. **ProvenanceDAG**: Acyclic directed graph node `BLOCK:API_SETU:DPIIT:SUIRC:<regn_no>` grounded via `FACT_GROUNDED_BY` edge.
4. **Zero Secret Leakage**: API keys and auth tokens are hashed with SHA-256 (`hash_secret()`); DPIIT registration numbers and mobile numbers are masked in logs (`mask_registration()`, `mask_mobile()`).

---

## 4. Live Sandbox Truth Audit & Operational Scope

| Audit Parameter | Verified System State |
|---|---|
| **API Endpoint** | `POST https://sandbox.api-setu.in/certificate/v3/dpiit/suirc` |
| **Gateway Reachability** | **CONFIRMED**: HTTPS handshake to API Setu gateway verified. |
| **Upstream Sandbox Result** | **HTTP 404 / 504**: Upstream DPIIT sandbox returned record not found / timeout for test parameters. |
| **Certificate Retrieval** | **NO CERTIFICATE RETURNED**: Upstream did not return active XML recognition certificate. |
| **Fact-Gating Enforcement** | **CONFIRMED**: Zero authoritative verified facts created for unsuccessful responses. |
| **Scope Limitation** | Verifies DPIIT recognition certificate validity and entity classification. Does **NOT** verify commercial revenue, financial solvency, or tender product compliance. |

