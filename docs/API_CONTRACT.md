# SIH26100 GeM Bid Compliance Verification Platform — API Contract Specification

> [!NOTE]
> **API Version:** `v1.0.0`
> **Base URL:** `http://localhost:8000`
> **Protocol:** HTTP / JSON (`multipart/form-data` for file uploads)
> **Default Execution Mode:** Offline Deterministic (`MOCK`), Zero Quota Consumed.

---

## 1. System Health Endpoint

### `GET /health`
Returns runtime status, loaded model configurations, and operating mode.

#### Response (`200 OK`):
```json
{
  "status": "HEALTHY",
  "version": "1.0.0",
  "active_model": "gemini-3.8-flash",
  "mode": "MOCK"
}
```

---

## 2. Bid Verification Endpoint

### `POST /api/v1/verify`
Accepts a tender document and one or more bidder submission documents, executes the end-to-end verification pipeline, and returns the aggregated verification result.

#### Request: `multipart/form-data`
| Parameter | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `tender_file` | Binary File | **Yes** | Tender specification PDF (`.pdf` only, max 25 MB). |
| `bid_files` | Binary File(s) | **Yes** | One or more bidder submission PDFs (`.pdf` only, max 25 MB each). |
| `tender_id` | String | No | Canonical Tender ID (e.g. `TENDER-0069`). Inferred if omitted. |
| `bid_id` | String | No | Canonical Bid ID (e.g. `BID-00031`). Inferred if omitted. |
| `company_name`| String | No | Declared legal name of bidder (e.g. `BluePeak Solutions`). |
| `mode` | String | No | Verification mode: `mock` (default), `cached`, or `live`. |

#### Response (`200 OK`):
```json
{
  "verification_id": "VERIF-TENDER-0069-BID-00031",
  "tender_id": "TENDER-0069",
  "bid_id": "BID-00031",
  "overall_status": "PASS",
  "compliance_status": "PASS",
  "integrity_status": "CONSISTENT",
  "verification_results": [
    {
      "verification_id": "VERIF-REQ-turnover_cr-BID-00031",
      "requirement_id": "REQ-turnover_cr",
      "bid_id": "BID-00031",
      "status": "PASS",
      "severity": "CRITICAL",
      "expected": 2.84,
      "actual": "10.36",
      "operator_used": ">=",
      "reason": "Bidder fact value (10.36) satisfies requirement (>= 2.84).",
      "evidence": [
        {
          "document": "BID-00031.pdf",
          "page": 1,
          "bbox": [10.0, 10.0, 20.0, 20.0],
          "snippet": "Turnover declared is 10.36 Crore"
        }
      ],
      "requires_human_review": false
    }
  ],
  "critical_failures": 0,
  "major_failures": 0,
  "review_required": false,
  "evidence_count": 8,
  "anomaly_count": 0,
  "government_checks": [
    {
      "status": "VERIFIED",
      "adapter_name": "MockGSTAdapter",
      "queried_identifier": "29SYNTH0000003F1Z",
      "source": "MOCK_GST_REGISTRY",
      "reason": "GSTIN active and legal entity name verified.",
      "is_mock": true
    }
  ],
  "contradictions": [],
  "human_review_items": [],
  "generated_at": "2026-09-03T08:25:38Z",
  "deterministic_run_id": "RUN-C48B2B706249",
  "processing_metadata": {
    "debarred": false,
    "total_compliance_checks": 8,
    "passed_compliance_checks": 8,
    "contradiction_findings": 0,
    "government_checks_run": 3,
    "extraction_mode": "MOCK",
    "active_model": "gemini-3.8-flash"
  }
}
```

#### Error Responses:
* `400 Bad Request`:
  ```json
  {
    "error": "Unsupported file extension '.txt'. Only .pdf files are accepted.",
    "detail": null
  }
  ```
* `500 Internal Server Error`:
  ```json
  {
    "error": "Internal processing error occurred during verification.",
    "detail": null
  }
  ```

---

## 3. Verification Retrieval Endpoints

### `GET /api/v1/verification/{verification_id}`
Retrieves existing aggregated verification result.

#### Response (`200 OK`):
Same format as `POST /api/v1/verify`.

#### Error Response (`404 Not Found`):
```json
{
  "error": "Verification 'VERIF-UNKNOWN' not found.",
  "detail": null
}
```

---

### `GET /api/v1/verification/{verification_id}/dossier`
Retrieves complete, machine-readable audit dossier for procurement officers and judges.

#### Response (`200 OK`):
```json
{
  "tender": {
    "tender_id": "TENDER-0069",
    "requirements_count": 8,
    "requirements": [...]
  },
  "bidder": {
    "bid_id": "BID-00031",
    "legal_name": "BluePeak Solutions",
    "extracted_facts_count": 8,
    "facts": [...]
  },
  "compliance_summary": {
    "compliance_status": "PASS",
    "overall_status": "PASS",
    "critical_failures": 0,
    "major_failures": 0,
    "total_requirements": 8
  },
  "integrity_summary": {
    "integrity_status": "CONSISTENT",
    "contradictions_count": 0,
    "anomalies_count": 0
  },
  "verification_results": [...],
  "government_checks": [...],
  "evidence": [
    {
      "fact_id": "FACT-BID-00031-001",
      "field": "turnover_cr",
      "value": "10.36",
      "normalized_value": 103600000.0,
      "unit": "INR",
      "document": "BID-00031.pdf",
      "page": 1,
      "bbox": [10.0, 10.0, 20.0, 20.0],
      "snippet": "Turnover declared is 10.36 Crore",
      "confidence": "HIGH"
    }
  ],
  "anomalies": [],
  "human_review_items": [],
  "audit_metadata": {
    "verification_id": "VERIF-TENDER-0069-BID-00031",
    "deterministic_run_id": "RUN-C48B2B706249",
    "generated_at": "2026-09-03T08:25:38Z",
    "processing_time_ms": 24.5,
    "active_model": "gemini-3.8-flash",
    "extraction_mode": "MOCK"
  }
}
```

---

### `GET /api/v1/verification/{verification_id}/review-items`
Retrieves human review queue items specifically flagged for human verification.

#### Response (`200 OK`):
```json
[
  {
    "review_id": "REV-BID-00001-001",
    "bid_id": "BID-00001",
    "tender_id": "TENDER-0069",
    "category": "INTEGRITY_CONTRADICTION",
    "severity": "CRITICAL",
    "reason": "Cross-document contradiction on 'gstin': GSTIN differs across documents: 29SYNTH0000003F1Z vs 29SYNTH0000103F1Z",
    "evidence_references": [
      {"document": "technical_bid.pdf", "page": 10, "bbox": [10, 10, 20, 20], "snippet": "29SYNTH0000003F1Z"},
      {"document": "annexure.pdf", "page": 8, "bbox": [30, 30, 40, 40], "snippet": "29SYNTH0000103F1Z"}
    ],
    "source_documents": ["technical_bid.pdf", "annexure.pdf"],
    "source_pages": [10, 8],
    "related_verification_id": "CONTRA-000001",
    "created_at": "2026-09-03T08:25:38Z",
    "status": "OPEN"
  }
]
```
