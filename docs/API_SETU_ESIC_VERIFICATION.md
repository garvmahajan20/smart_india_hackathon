# API Setu / ESIC Health Passbook & Pehchan Card Sandbox Integration

## 1. Overview
This module integrates the official Government of India **API Setu / Employees' State Insurance Corporation (ESIC) Verification APIs** into the SIH26100 compliance platform.

- **Authority**: Employees' State Insurance Corporation (ESIC), Ministry of Labour and Employment
- **API Spec Reference**: `https://sandbox.api-setu.in/sandbox/specfiles/esic.yaml`
- **Sandbox Base URL**: `https://sandbox.api-setu.in`
- **Endpoints**:
  - Health Passbook: `POST /certificate/v3/esic/esich`
  - Pehchan Card: `POST /certificate/v3/esic/phcrd`
- **Format**: `xml`

---

## 2. Critical Scope Disclaimer
> **IMPORTANT SCOPE NOTICE**: ESIC certificate and document verification (Health Passbook, Pehchan Card) verifies the registration and insured status of an individual employee or insured person under the specified employer/dispensary. It **does NOT** equal comprehensive employer establishment-level compliance, nor does it certify complete organization-wide statutory monthly contribution payment across all employees. Full establishment compliance requires comprehensive employer contribution filings.

---

## 3. Request & Response Specification

### Request Headers
```http
Accept: application/json
Content-Type: application/json
X-APISETU-APIKEY: <configured>
X-APISETU-CLIENTID: in.gov.sandbox
```

### JSON Request Payloads
Field names strictly adhere to official ESIC YAML specification:

#### 1. Health Passbook (`esich`)
- `ipNumber`: Insured Person (IP) 10-digit identification number (e.g. `1199887766`)
- `RELATION`: Beneficiary relation (`SELF`, `SPOUSE`, `SON`, `DAUGHTER`, `FATHER`, `MOTHER`)

#### 2. Pehchan Card (`phcrd`)
- `ipNumber`: Insured Person (IP) 10-digit identification number (e.g. `1199887766`)
- `EmployerName`: Name of the registered employer

### Response Mapping
- `HTTP 200` + XML -> Parsed with XXE protection, fields extracted:
  - `ip_number`
  - `insured_person_name`
  - `employer_code`
  - `employer_name`
  - `dispensary`
  - `uhid`
  - `date_of_registration`
  - Status: `VERIFIED`
- `HTTP 400` -> `INVALID_REQUEST`
- `HTTP 401` -> `ERROR` (Authentication failure)
- `HTTP 404` -> `NOT_VERIFIED` (Record not found in ESIC database)
- `HTTP 500, 502, 503, 504` / Timeout -> `UNAVAILABLE` or `ERROR`

---

## 4. Evidence Grounding & Provenance Invariants
1. **Gating Rule**: An unsuccessful or unavailable response **MUST NEVER** produce an authoritative verified `BidderFact`. Only verified certificates yield facts.
2. **EvidenceReference**: Created with document URI `API_SETU:ESIC:<doc_type>:<ip_number>`, `source_type="API_SETU_OFFICIAL_REGISTRY"`, and bounding box `[0.0, 0.0, 0.0, 0.0]`.
3. **ProvenanceDAG**: Acyclic directed graph node `BLOCK:API_SETU:ESIC:<doc_type>:<ip_number>` grounded via `FACT_GROUNDED_BY` edge.
4. **Zero Secret Leakage**: API keys and auth tokens are hashed with SHA-256 (`hash_secret()`); IP numbers are masked in logs (`mask_ip_number()`).

---

## 5. Live Sandbox Truth Audit & Scope Boundaries

| Audit Parameter | Verified System State |
|---|---|
| **API Endpoints** | Health Passbook: `POST /certificate/v3/esic/esich`<br>Pehchan Card: `POST /certificate/v3/esic/phcrd` |
| **Gateway Reachability** | **CONFIRMED**: API Setu gateway reached successfully. |
| **Upstream Sandbox Result** | Health Passbook: **HTTP 504 Gateway Timeout**<br>Pehchan Card: **HTTP 404 Not Found** |
| **Certificate Retrieval** | **NO CERTIFICATE RETURNED**: Upstream did not deliver certificate XML payloads. |
| **Fact-Gating Enforcement** | **CONFIRMED**: Failed/unavailable responses produced **zero authoritative verified facts**. |
| **Scope Limitation** | Verifies individual employee/insured person insurance records only. It **DOES NOT** verify employer establishment-level ESI compliance, nor does it verify monthly contribution remittances across all establishment workers. |

