# API Setu / Ministry of MSME Udyam Certificate Sandbox Integration

## 1. Overview
This module integrates the official Government of India **API Setu / Ministry of MSME Udyam Certificate Verification API** (`udcer`) into the SIH26100 compliance platform.

- **Authority**: Ministry of Micro, Small and Medium Enterprises (MSME)
- **API Spec Reference**: `https://sandbox.api-setu.in/api-collection/msme/1`
- **Sandbox Base URL**: `https://sandbox.api-setu.in`
- **Endpoint**: `POST /certificate/v3/msme/udcer`
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
```json
{
  "txnId": "f7f1469c-29b0-4325-9dfc-c567200a70f7",
  "format": "xml",
  "certificateParameters": {
    "udyamNumber": "UDYAM-MH-01-0088776",
    "mobileNumber": "9874563210"
  },
  "consentArtifact": {
    "consent": {
      "consentId": "ea9c43aa-7f5a-4bf3-a0be-e1caa24737ba",
      "timestamp": "2026-09-06T12:00:00.000Z",
      "dataConsumer": { "id": "in.gov.sandbox" },
      "dataProvider": { "id": "in.gov.msme" },
      "purpose": { "description": "GeM Bid Compliance MSME Verification" },
      "user": {
        "idType": "UDYAM",
        "idNumber": "UDYAM-MH-01-0088776",
        "mobile": "9874563210",
        "email": "test@email.com"
      },
      "data": { "id": "in.gov.msme" },
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
  - `udyam_number` (`UDYAM-XX-00-0000000`)
  - `enterprise_name`
  - `enterprise_type` (`MICRO`, `SMALL`, `MEDIUM`)
  - `major_activity` (`MANUFACTURING`, `SERVICES`)
  - `date_of_commencement`
  - `social_category` (`GENERAL`, `OBC`, `SC`, `ST`)
  - Status: `VERIFIED`
- `HTTP 400` -> `INVALID_REQUEST`
- `HTTP 401` -> `ERROR` (Authentication failure)
- `HTTP 404` -> `NOT_VERIFIED` (Record not found in MSME registry)
- `HTTP 500, 502, 503, 504` / Timeout -> `UNAVAILABLE` or `ERROR`

---

## 3. Evidence Grounding & Provenance Invariants
1. **Gating Rule**: An unsuccessful or unavailable response **MUST NEVER** produce an authoritative verified `BidderFact`.
2. **EvidenceReference**: Created with document URI `API_SETU:UDCER:<udyam_number>`, `source_type="API_SETU_OFFICIAL_REGISTRY"`, and bounding box `[0.0, 0.0, 0.0, 0.0]`.
3. **ProvenanceDAG**: Acyclic directed graph node `BLOCK:API_SETU:UDCER:<udyam_number>` grounded via `FACT_GROUNDED_BY` edge.
4. **Zero Secret Leakage**: API keys and auth tokens are hashed with SHA-256 (`hash_secret()`); Udyam numbers and mobile numbers are masked in logs (`mask_udyam()`, `mask_mobile()`).

---

## 4. Live Sandbox Truth Audit & Operational Scope

| Audit Parameter | Verified System State |
|---|---|
| **API Endpoint** | `POST https://sandbox.api-setu.in/certificate/v3/msme/udcer` |
| **Gateway Reachability** | **CONFIRMED**: Gateway contacted successfully via HTTPS. |
| **Upstream Sandbox Result** | **HTTP 404 NOT_FOUND**: Tested identifier returned `"Udyam number not found in external MSME registry"`. |
| **Certificate Retrieval** | **NO CERTIFICATE RETURNED**: Upstream did not return an active XML certificate for test identifier. |
| **Fact-Gating Enforcement** | **CONFIRMED**: Status set to `NOT_VERIFIED`. **Zero authoritative verified facts** were created. |
| **Scope Limitation** | Verifies MSME registration status and enterprise category (Micro/Small/Medium). Does **NOT** replace on-site manufacturing capacity verification or physical plant inspection. |

