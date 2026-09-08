# API Setu / Income Tax Department PAN Verification Sandbox Integration

**Platform:** SIH26100 GeM Bid Compliance Verification Platform  
**Component:** Backend Statutory Identification & Tax Compliance Layer  
**Status:** IMPLEMENTED & GATEWAY VALIDATED (UPSTREAM TIMEOUT 504; FACT GATING ENFORCED)  
**Package:** `backend.integrations.pan`  

---

## 1. Architectural Overview & Design Principles

The API Setu PAN Verification Record (PANCR) integration layer provides authoritative, automated tax identity validation for bidders participating in Government e-Marketplace (GeM) tenders.

### Core Architectural Principles:
1. **Real HTTP Sandbox Integration:** Communicates with the official API Setu sandbox endpoint using live HTTP POST requests. Does not use mock adapters or hardcoded `"verified": true` shortcuts.
2. **Authority Separation:** The external PAN API acts strictly as an **authoritative evidence provider**. The deterministic compliance engine remains the sole authority for tender compliance verdicts.
3. **No Fake Bounding Boxes:** Digital registry evidence is marked with `source_type="API_SETU_OFFICIAL_REGISTRY"`, `extraction_method="API_SETU_PANCR_REST"`, and bounding boxes set to canonical `[0.0, 0.0, 0.0, 0.0]`. It is never falsely presented as coming from a PDF document page.
4. **Strict Zero Secret Leakage:** Client ID and API keys are completely isolated behind environment variables (`PAN_VERIFICATION_API_KEY`, `PAN_VERIFICATION_CLIENT_ID`). Credentials are scrubbed from logs and replaced with deterministic SHA-256 digests (`sha256:...`).
5. **Exact Field-Path Provenance:** For XML responses, exact XPath-style field pointers (e.g. `/Certificate/CertificateData/PAN/@num`, `/Certificate/IssuedTo/Person/@name`) are preserved in the `ProvenanceDAG`.
6. **Backend-Only Isolation:** Implemented entirely in `backend/` without modifying frontend code owned by Utsav.

---

## 2. Official Specification & Endpoints

- **Official API Setu Catalog:** [https://sandbox.api-setu.in/api-collection/pan/2](https://sandbox.api-setu.in/api-collection/pan/2)
- **Specification Path:** `/certificate/v3/pan/pancr`
- **Method:** `POST`
- **Sandbox Base URL:** `https://sandbox.api-setu.in`
- **Production Base URL:** `https://apisetu.gov.in`

### Required HTTP Headers:
| Header | Description | Sandbox Example |
|---|---|---|
| `Content-Type` | MIME type | `application/json` |
| `X-APISETU-APIKEY` | API Key issued by API Setu | `demokey123456ABCD789` |
| `X-APISETU-CLIENTID` | Client identifier issued by API Setu | `in.gov.sandbox` |
| `Accept` | Accepted response types | `application/xml, application/json, */*` |

---

## 3. Request Structure

Per official OpenAPI 3.0.0 specification (`pan.yaml`):

```json
{
  "txnId": "f7f1469c-29b0-4325-9dfc-c567200a70f7",
  "format": "xml",
  "certificateParameters": {
    "panno": "ABCDE1234F",
    "FullName": "DEMO USER",
    "PANFullName": "DEMO USER",
    "DOB": "01-01-1999",
    "orgid": "001891"
  },
  "consentArtifact": {
    "consent": {
      "consentId": "ea9c43aa-7f5a-4bf3-a0be-e1caa24737ba",
      "timestamp": "2026-09-06T14:30:00.000Z",
      "dataConsumer": { "id": "in.gov.sandbox" },
      "dataProvider": { "id": "in.gov.pan" },
      "purpose": { "description": "GeM Bid Compliance Verification" },
      "user": {
        "idType": "PAN",
        "idNumber": "ABCDE1234F",
        "mobile": "9876543210",
        "email": "verification@gem-compliance.gov.in"
      },
      "data": { "id": "in.gov.pan" },
      "permission": {
        "access": "VIEW",
        "dateRange": { "from": "2026-09-06T14:30:00.000Z", "to": "2026-09-06T14:30:00.000Z" },
        "frequency": { "unit": "ONETIME", "value": 1, "repeats": 0 }
      }
    },
    "signature": { "signature": "SHA256withRSA_SIGNED_CONSENT" }
  }
}
```

---

## 4. Response Parsing & Security

### Official XML Response Format:
```xml
<Certificate name="PAN Verification Record" type="PANCR" number="ABCDE1234F" status="A" issueDate="2023-01-15">
    <IssuedBy>
        <Organization name="Income Tax Department" code="ITD"/>
    </IssuedBy>
    <IssuedTo>
        <Person name="National Systems Pvt Ltd" dob="15-08-1990"/>
    </IssuedTo>
    <CertificateData>
        <PAN num="ABCDE1234F"/>
    </CertificateData>
</Certificate>
```

### Security Defenses:
- **XXE Prevention:** Explicitly rejects `<!DOCTYPE` and `<!ENTITY>` declarations before XML parsing.
- **Strict TLS Verification:** All outbound network calls require valid server certificates (`verify=True`).
- **Secret Redaction:** `X-APISETU-APIKEY` is masked in memory and redacted from error reports.

---

## 5. Evidence & Provenance DAG Integration

Authority responses are mapped by `APISetuPANEvidenceAdapter` into:

### 1. `EvidenceReference`:
- `document`: `"API_SETU:PANCR:{pan}"`
- `page`: `1`
- `bbox`: `[0.0, 0.0, 0.0, 0.0]`
- `extraction_method`: `"API_SETU_PANCR_REST"`
- `snippet`: Authoritative summary with authority, PAN, name, and transaction ID.

### 2. `BidderFact`:
- `field`: `"pan"`
- `value`: Normalized 10-character PAN
- `canonical_field`: `"PAN"`
- `metadata`: Contains `transaction_id`, `http_status`, `response_hash`, `verified_name`, `verified_dob`, and `xml_field_paths`.

### 3. `ProvenanceDAG`:
Connects:
```
API_SETU:PANCR (External Authority Node)
    ↓ [EdgeType.FACT_GROUNDED_BY]
FACT:FACT-PAN-{pan} (BidderFact Node)
    ↓ [EdgeType.FACT_CANONICALIZED_AS]
CANONICAL:PAN
```
Topological validation guarantees 100% acyclicity and deterministic audit replay.

---

## 6. Sandbox Limitations vs. Production Live Verification

| Dimension | API Setu Sandbox | Live Production Income Tax Department |
|---|---|---|
| **Endpoint** | `https://sandbox.api-setu.in/certificate/v3/pan/pancr` | `https://apisetu.gov.in/certificate/v3/pan/pancr` |
| **API Key** | Test/sandbox key (e.g. `demokey123456ABCD789`) | Production API Key issued post-MOU and security audit |
| **Client ID** | `in.gov.sandbox` | Registered entity client ID (e.g., `in.gov.gem`) |
| **Data Source** | Sandbox test stubs & mock verifier | Real-time NSDL / UTIITSL / Income Tax Department database |
| **Consent** | Simulated / static consent artifact | Legally binding Aadhaar/OTP/e-Sign authenticated consent |
| **Network Policy** | Public internet with API Setu rate limits | Dedicated IP-whitelisted VPN / secure government gateway |

> **IMPORTANT:**  
> Data returned in sandbox testing represents mock or test records provided by the API Setu sandbox gateway.  
> It must **never** be mislabeled as an actual real-world taxpayer verification.

---

## 7. Configuration Reference

Environment variables (template in `.env.example`):
```bash
PAN_VERIFICATION_ENABLED=false
PAN_VERIFICATION_ENV=sandbox
PAN_VERIFICATION_BASE_URL=https://sandbox.api-setu.in
PAN_VERIFICATION_API_KEY=your_api_key_here
PAN_VERIFICATION_CLIENT_ID=in.gov.sandbox
PAN_VERIFICATION_TIMEOUT_SECONDS=10
```

---

## 8. Live Sandbox Truth Audit & Gating Verification

The live PAN integration was audited against the official API Setu sandbox:

| Audit Parameter | Verified System State |
|---|---|
| **API Endpoint** | `POST https://sandbox.api-setu.in/certificate/v3/pan/pancr` |
| **Gateway Reachability** | **CONFIRMED**: DNS, TLS, and HTTP handshake to API Setu gateway succeeded. |
| **Authentication Testing** | **CONFIRMED**: Requests with invalid API keys were rejected with HTTP 401. |
| **Validation Testing** | **CONFIRMED**: Malformed consent or missing required parameters returned HTTP 400. |
| **Upstream Behavior** | **TIMEOUT (HTTP 504)**: Properly formed sandbox requests reached the external Income Tax Department upstream emulator, which timed out with HTTP 504 Gateway Timeout. |
| **Certificate Retrieval** | **NO CERTIFICATE RETURNED**: No actual PAN certificate XML payload was delivered by upstream. |
| **Fact-Gating Enforcement** | **CONFIRMED**: The system strictly gated `BidderFact` creation. **Zero authoritative verified facts** were created for this failed/timed-out call. |
| **Scope Limitation** | Verifies PAN cardholder identity and active status only. It does **NOT** verify annual Income Tax Return (ITR) filings, corporate tax assessment orders, or tax dispute liabilities. |

