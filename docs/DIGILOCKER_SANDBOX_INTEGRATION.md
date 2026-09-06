# DigiLocker & API Setu Sandbox Integration Specification

**Platform:** SIH26100 GeM Bid Compliance Verification Platform  
**Component:** Backend Government Document & Statutory Verification Layer  
**Status:** INTEGRATION IMPLEMENTED & SPECIFICATION VALIDATED (LIVE DOCUMENT RETRIEVAL BLOCKED BY ACCESS/POLICY RESTRICTIONS; OFFLINE FIXTURE/SCHEMA VALIDATED)  
**Package:** `backend.integrations.digilocker`  

---

## 1. Architectural Overview & Design Principles

The DigiLocker / API Setu integration layer bridges official government digital document repositories into the deterministic bid evaluation and compliance pipeline of the GeM platform.

### Core Architectural Principles:
1. **RFC 7636 PKCE Client Implementation:** The integration provides a production-grade OAuth 2.0 PKCE client and API Setu XML/PDF parser. However, live document retrieval against the public sandbox is subject to official partner policy restrictions.
2. **Authoritative Status Distinction:** The platform explicitly distinguishes client implementation and schema validation from live government retrieval. No fixture is ever represented as live government evidence.
2. **Authority Separation:** DigiLocker acts strictly as an **authoritative evidence source**. The deterministic compliance engine remains the sole authority for pass/fail decisions against tender clauses.
3. **No Fake Bounding Boxes:** Unlike scanned/physical PDF text segmentation, digital registry proof is marked with `source_type="DIGILOCKER"`, explicit digital origin markers, and bounding boxes set to canonical zero coordinates `[0.0, 0.0, 0.0, 0.0]`.
4. **Strict Zero Secret Leakage:** Never logs, exposes, or commits OAuth client secrets, raw authorization codes, PKCE verifiers, or access tokens. Uses SHA-256 digests (`sha256:...`) in audit trails for end-to-end trace correlation.
5. **Backend-Only Isolation:** Implemented entirely in `backend/` without modifying frontend code owned by Utsav.

---

## 2. Official Sandbox References & Specification

- **API Setu Official Sandbox Portal:** [https://sandbox.api-setu.in/](https://sandbox.api-setu.in/)
- **DigiLocker Integration Guide:** [https://sandbox.api-setu.in/digilocker-steps](https://sandbox.api-setu.in/digilocker-steps)
- **API Setu XML Specification:** [https://docs.apisetu.gov.in/document-central/dl-xml-format/XML%20Format.html](https://docs.apisetu.gov.in/document-central/dl-xml-format/XML%20Format.html)

### Standard Sandbox Endpoints:
| Function | Sandbox Path | HTTP Method |
|---|---|---|
| **OAuth Authorize** | `/api/v1/digilocker/oauth/authorize` | `GET` |
| **OAuth Token Exchange** | `/api/v1/digilocker/oauth/token` | `POST` |
| **User Profile** | `/api/v1/digilocker/user` | `GET` |
| **Issued Documents** | `/api/v1/digilocker/documents/issued` | `GET` |
| **Document Pull** | `/api/v1/digilocker/documents/pull` | `POST` |
| **Token Revocation** | `/api/v1/digilocker/oauth/revoke` | `POST` |

---

## 3. OAuth 2.0 + PKCE Implementation (RFC 7636)

The authorization workflow enforces RFC 7636 Proof Key for Code Exchange (PKCE) to protect authorization codes from interception:

1. **Code Verifier:** Generated using `secrets.token_urlsafe(64)` (64 characters, within the RFC 7636 bounds of 43 to 128 chars).
2. **Code Challenge:** Derived via S256:
   $$\text{code\_challenge} = \text{Base64URL}(\text{SHA256}(\text{code\_verifier})) \quad \text{(without '=' padding)}$$
3. **CSRF State Token:** High-entropy cryptographically random state generated via `secrets.token_urlsafe(32)`.
4. **State Store (`PKCEStateStore`):** Thread-safe in-memory cache holding pending `(state -> verifier)` associations with automated 10-minute TTL expiry and one-time pop consumption.
5. **Token Exchange:** Backend sends `code`, `client_id`, `client_secret`, `redirect_uri`, `grant_type=authorization_code`, and the original `code_verifier` directly to the token endpoint.

---

## 4. XML Parsing & Security Architecture

The XML parser (`backend.integrations.digilocker.xml_parser`) processes official API Setu payloads:

### Envelope Specification (`<PullDocResponse>`):
```xml
<PullDocResponse xmlns="...">
    <ResponseStatus status="1" ts="..." txn="...">Success</ResponseStatus>
    <DocDetails>
        <DocContent><!-- Base64-encoded PDF --></DocContent>
        <DataContent><!-- Base64-encoded or raw Certificate XML --></DataContent>
    </DocDetails>
</PullDocResponse>
```

### Digital Certificate Specification (`<Certificate>`):
```xml
<Certificate name="Udyam Registration" type="UDYAM" number="UDYAM-MH-01-0012345" status="A" issueDate="2022-04-15">
    <IssuedBy>
        <Organization name="Ministry of Micro, Small and Medium Enterprises" code="MSME"/>
    </IssuedBy>
    <IssuedTo>
        <Person name="Sunita Sharma" uid="XXXX-XXXX-1234"/>
        <Organization name="TechnoCraft Solutions Pvt Ltd" type="PRIVATE_LIMITED"/>
    </IssuedTo>
    <CertificateData>
        <EnterpriseType>SMALL</EnterpriseType>
        <MajorActivity>MANUFACTURING</MajorActivity>
    </CertificateData>
</Certificate>
```

### Security Defenses:
- **XXE Prevention:** Explicitly detects and rejects payloads containing `<!DOCTYPE` or `<!ENTITY` declarations before parsing.
- **Malformed XML Resilience:** Traps `ET.ParseError` and raises typed `DigiLockerXMLParsingError` without unhandled system crashes.
- **Embedded PDF Extraction:** Decodes base64 bytes from `<DocContent>`, validates the `%PDF-` magic header, and returns clean PDF bytes.

---

## 5. Evidence Grounding & Provenance DAG Integration

Authority artifacts retrieved from DigiLocker are translated by `DigiLockerEvidenceAdapter` into our platform's canonical models:

### 1. `EvidenceReference`
- `document`: `"DIGILOCKER:{certificate_type}:{certificate_number}"`
- `page`: `1`
- `bbox`: `[0.0, 0.0, 0.0, 0.0]`
- `snippet`: Authoritative summary string with issuer, certificate number, status, and recipient.
- `extraction_method`: `"DIGILOCKER_AUTHORITATIVE_API"`
- `extraction_confidence`: `"HIGH"`

### 2. `BidderFact`
- Mapped to canonical field ontology:
  - `UDYAM` $\rightarrow$ `field="msme_registration_number"`, `canonical_field="MSME_REGISTRATION"`
  - `GST` $\rightarrow$ `field="gstin"`, `canonical_field="GSTIN"`
  - `PAN` $\rightarrow$ `field="pan"`, `canonical_field="PAN"`
  - `INCORPORATION` $\rightarrow$ `field="certificate_of_incorporation"`, `canonical_field="INCORPORATION_CERTIFICATE"`
- Contains complete audit metadata including issuer details, active status, and recipient identifiers.

### 3. `ProvenanceDAG` Invariant Safety
- Injects a `NodeType.PHYSICAL_TEXT_BLOCK` node representing the external government authority document.
- Injects a `NodeType.BIDDER_FACT` node representing the verified parameter.
- Creates a directed edge of type `EdgeType.FACT_GROUNDED_BY` connecting the fact to the evidence block.
- Executes `dag.validate()` ensuring acyclicity (Kahn's topological sort) and endpoint integrity.

---

## 6. Zero Secret Leakage Audit Logging

The `DigiLockerAuditLogger` maintains a thread-safe ring buffer of events with cryptographic scrubbing:

- **Tokens & Secrets Scrubbed:** Any key containing `"token"`, `"secret"`, `"code"`, `"verifier"` is hashed using SHA-256 (`sha256:<12-chars>`).
- **PII Scrubbed:** Government IDs (Aadhaar, UID, PAN) are masked to the last 4 characters (`***1234`).
- **Audit Access:** Real-time queryable via `/api/v1/integrations/digilocker/audit-logs`.

---

## 7. FastAPI Endpoints

Mounted under `/api/v1/integrations/digilocker/`:

| Endpoint | Method | Description |
|---|---|---|
| `/status` | `GET` | Reports integration enabled status, environment (`sandbox`/`production`), and base URL. |
| `/authorize` | `GET` | Generates PKCE parameters, caches state, and returns sandbox redirect URL. |
| `/callback` | `GET` | Receives OAuth redirect, validates CSRF state, exchanges code for access token. |
| `/user` | `GET` | Fetches authenticated user profile (`Authorization: Bearer <token>`). |
| `/documents` | `GET` | Lists issued documents in user's repository. |
| `/pull` | `POST` | Pulls document/certificate by URI, decodes PDF/XML, optionally synthesizes `BidderFact`. |
| `/revoke` | `POST` | Revokes access or refresh token. |
| `/audit-logs` | `GET` | Returns sanitized audit trail of all transactions. |

---

## 8. Configuration & Deployment

Environment variables in `.env` (template in `.env.example`):

```bash
# Enable or disable integration
DIGILOCKER_ENABLED=false

# Environment: "sandbox" or "production"
DIGILOCKER_ENV=sandbox

# API Setu Sandbox Credentials
DIGILOCKER_CLIENT_ID=your_api_setu_sandbox_client_id_here
DIGILOCKER_CLIENT_SECRET=your_api_setu_sandbox_client_secret_here

# Redirect Callback URI
DIGILOCKER_REDIRECT_URI=http://localhost:8000/api/v1/integrations/digilocker/callback

# API Setu Base URL
DIGILOCKER_BASE_URL=https://sandbox.api-setu.in
DIGILOCKER_TIMEOUT_SECONDS=30
```

---

## 9. Verification & Test Suite

The test suite in `tests/integrations/test_digilocker.py` covers 29 comprehensive test cases:
- **PKCE:** Verifier constraints, S256 test vectors, constant-time verification, state store TTL.
- **XML Parsing:** Certificate parsing, envelope decoding, XXE injection prevention, malformed XML resilience.
- **Client & Networking:** Authorize URL builder, code exchange, user profile, document pull, token revocation, error handling.
- **Evidence & DAG:** `EvidenceReference` generation, `BidderFact` creation, `ProvenanceDAG` acyclicity verification.
- **Security:** Zero secret leakage audit assertions.
- **FastAPI Routes:** Status, authorize, callback (valid/invalid/error states), user profile, pull, revoke, and audit logs.

All 29 tests pass with 100% success rate, alongside 78 full-system regression tests.

---

## 10. Live Sandbox Truth Audit & Operational Distinctions

To ensure complete institutional auditability and truthfulness, the platform explicitly distinguishes the four levels of integration maturity:

| Maturity Dimension | Status | Audit Findings & Verifiable Evidence |
|---|---|---|
| **A. Client & Parser Implementation** | **VERIFIED IN REPOSITORY** | Complete RFC 7636 PKCE OAuth 2.0 client, secure XML/PDF parser with XXE defense, DAG integration, and FastAPI endpoints exist in `backend/integrations/digilocker/`. |
| **B. API Specification & Discovery** | **VERIFIED LIVE** | Reached official API Setu sandbox discovery gateway; successfully validated OpenAPI 3.0 specification. |
| **C. Live Document Retrieval** | **BLOCKED BY POLICY** | Actual live requests to DigiLocker OAuth token exchange and document pull endpoints return **HTTP 403 Forbidden**. Official live access requires institutional partner onboarding, formal MoU execution, and IP/client whitelisting by DigiLocker/NIC. |
| **D. Fixture & Schema Validation** | **VERIFIED OFFLINE** | Document pull parsing and `BidderFact` generation were verified using official API Setu `<PullDocResponse>` XML schema test fixtures and local synthetic PDF vectors. |

> **AUDIT INVARIANT**:  
> The platform does **NOT** claim live government document retrieval from DigiLocker.  
> Document retrieval remains blocked by official DigiLocker access/policy restrictions until production institutional credentials are provisioned.  
> Offline test fixtures are never represented as live government evidence.

