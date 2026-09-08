# API Setu / EPFO Verification Sandbox Integration

## 1. Overview & Critical Scope Distinction
This module integrates the official Government of India **API Setu / Employees' Provident Fund Organisation (EPFO) Verification APIs** into the SIH26100 platform.

> [!WARNING]
> **SCOPE NOTICE**:
> These API Setu endpoints provide **EPFO DOCUMENT/CERTIFICATE VERIFICATION ONLY** (UAN Card, Scheme Certificate, Pension Certificate).
> They do **NOT** perform general employer establishment EPFO compliance or monthly remittance verification.
> The platform strictly separates document verification from employer-level compliance declarations.

- **Authority**: Employees' Provident Fund Organisation (EPFO)
- **API Spec Reference**: `https://sandbox.api-setu.in/api-collection/epfindia/2`
- **Sandbox Base URL**: `https://sandbox.api-setu.in`

---

## 2. Supported Endpoints

### Endpoint A: UAN Card (PDF)
- **Method**: `POST`
- **Path**: `/certificate/v3/epfindia/uncrd`
- **Format**: `pdf`
- **Certificate Parameters**:
  - `UAN`: 10-12 digit Universal Account Number (e.g. `1234567890`)
  - `DOB`: Date of birth in `DD-MM-YYYY` (e.g. `31-12-1980`)
- **Handling**: Validates binary PDF `%PDF-` magic header, computes cryptographic SHA-256 digest, and safely records byte size.

### Endpoint B: Scheme Certificate (XML)
- **Method**: `POST`
- **Path**: `/certificate/v3/epfindia/epfsc`
- **Format**: `xml`
- **Certificate Parameters**:
  - `SCNO`: Scheme Certificate Number (e.g. `APSID00040466`)
- **Handling**: Secure XML parser with XXE protection extracting beneficiary and certificate details.

### Endpoint C: Pension Certificate (XML)
- **Method**: `POST`
- **Path**: `/certificate/v3/epfindia/pecer`
- **Format**: `xml`
- **Certificate Parameters**:
  - `PPONO`: Pension Payment Order Number (e.g. `DLCPM00052882`)
- **Handling**: Secure XML parser with XXE protection extracting pensioner and order details.

---

## 3. Security, Provenance, and Deterministic Gating
1. **Deterministic Gating**: Failed or unavailable calls **NEVER** create authoritative verified `BidderFacts`.
2. **EvidenceReference**: Created with document URI `API_SETU:EPFO:<TYPE>:<ID>`, `source_type="API_SETU_OFFICIAL_REGISTRY"`, and bounding box `[0.0, 0.0, 0.0, 0.0]`.
3. **ProvenanceDAG**: Acyclic directed graph nodes registered as `BLOCK:API_SETU:EPFO:<TYPE>:<ID>`.
4. **Zero Secret Leakage**: UANs and PPO/SC numbers are masked, API keys hashed with SHA-256.

---

## 4. Live Sandbox Truth Audit & Scope Boundaries

| Audit Parameter | Verified System State |
|---|---|
| **Supported Endpoints** | `POST /certificate/v3/epfindia/uncrd` (UAN Card)<br>`POST /certificate/v3/epfindia/epfsc` (Scheme Certificate)<br>`POST /certificate/v3/epfindia/pecer` (Pension Certificate) |
| **Non-Existent Endpoint** | `/certificate/v3/epfo/epfcr` is **NOT implemented** and does **NOT exist** in our codebase. |
| **What is Verified** | Individual worker/pensioner certificates only. |
| **What is NOT Verified** | Employer establishment compliance, ECR filing history, monthly contribution remittance, or default history. |
| **Live Sandbox Result** | HTTP 404 / 504 on live sandbox tests. No certificate payloads returned. |
| **Fact-Gating Enforcement** | **CONFIRMED**: Zero authoritative verified facts created for unsuccessful responses. |

