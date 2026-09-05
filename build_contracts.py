import json
import os

os.makedirs('contracts', exist_ok=True)
os.makedirs('tests/contracts', exist_ok=True)

# 1. document.schema.json
document_schema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://gem-compliance.sih26100.gov.in/contracts/document.schema.json",
  "title": "DocumentSegment",
  "description": "Represents an individual document or logical page segment within an uploaded tender or bidder submission package.",
  "type": "object",
  "required": [
    "document_id",
    "parent_file",
    "document_type",
    "page_start",
    "page_end",
    "source",
    "extraction_status"
  ],
  "properties": {
    "document_id": {
      "type": "string",
      "description": "Unique identifier for the document or segment (e.g., DOC-BID001-TECH-01)."
    },
    "parent_file": {
      "type": "string",
      "description": "Name or relative path of the parent container file (e.g., BID-00001.pdf or tender_spec.pdf)."
    },
    "document_type": {
      "type": "string",
      "description": "Functional classification of the document segment.",
      "enum": [
        "TENDER_DOCUMENT",
        "TECHNICAL_SPECIFICATION",
        "FINANCIAL_DOCUMENT",
        "BALANCE_SHEET",
        "ANNUAL_REPORT",
        "CA_TURNOVER_CERTIFICATE",
        "CERTIFICATE",
        "ISO_CERTIFICATE",
        "EXPERIENCE_CERTIFICATE",
        "PAST_PERFORMANCE_DOCUMENT",
        "PURCHASE_ORDER",
        "COMPLETION_CERTIFICATE",
        "GST_REGISTRATION",
        "PAN_CARD",
        "UDYAM_CERTIFICATE",
        "OEM_AUTHORIZATION",
        "UNDERTAKING",
        "NON_BLACKLISTING_DECLARATION",
        "LOCAL_CONTENT_DECLARATION",
        "MAKE_IN_INDIA_CERTIFICATE",
        "EMD_DOCUMENT",
        "EPBG_DOCUMENT",
        "BOQ_COMPLIANCE",
        "ANNEXURE",
        "OTHER",
        "UNKNOWN"
      ]
    },
    "page_start": {
      "type": "integer",
      "minimum": 1,
      "description": "Starting 1-indexed page number within the parent container file."
    },
    "page_end": {
      "type": "integer",
      "minimum": 1,
      "description": "Ending 1-indexed page number within the parent container file (must be >= page_start)."
    },
    "source": {
      "type": "string",
      "description": "Origin of the document within the procurement lifecycle.",
      "enum": [
        "TENDER",
        "BIDDER",
        "GOVERNMENT_REGISTRY",
        "EXTERNAL"
      ]
    },
    "extraction_status": {
      "type": "string",
      "description": "Current processing/extraction status of the document.",
      "enum": [
        "SUCCESS",
        "PARTIAL",
        "FAILED",
        "PENDING",
        "NOT_ATTEMPTED"
      ]
    },
    "classification_confidence": {
      "type": "string",
      "description": "Confidence level in the document type classification.",
      "enum": ["HIGH", "MEDIUM", "LOW"],
      "default": "HIGH"
    },
    "text_preview": {
      "type": "string",
      "description": "First few hundred characters or summary extracted from the segment."
    },
    "metadata": {
      "type": "object",
      "description": "Arbitrary key-value metadata (e.g. file_size, mime_type, sha256_hash, language).",
      "properties": {
        "file_size_bytes": { "type": "integer", "minimum": 0 },
        "mime_type": { "type": "string" },
        "sha256": { "type": "string" },
        "detected_language": { "type": "string", "default": "en" },
        "is_scanned": { "type": "boolean" },
        "total_pages": { "type": "integer", "minimum": 1 }
      },
      "additionalProperties": True
    }
  },
  "additionalProperties": False
}

# 2. requirement.schema.json
requirement_schema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://gem-compliance.sih26100.gov.in/contracts/requirement.schema.json",
  "title": "TenderRequirement",
  "description": "Represents an individual procurement requirement/clause extracted from a GeM tender document with provenance and precedence.",
  "type": "object",
  "required": [
    "requirement_id",
    "tender_id",
    "category",
    "description",
    "operator",
    "mandatory",
    "source_type",
    "source_priority"
  ],
  "properties": {
    "requirement_id": {
      "type": "string",
      "description": "Unique identifier for the requirement (e.g., REQ-FIN-001, TENDER-0002/TC-01)."
    },
    "tender_id": {
      "type": "string",
      "description": "Identifier of the tender this requirement originates from."
    },
    "category": {
      "type": "string",
      "description": "Procurement domain classification of the requirement.",
      "enum": [
        "FINANCIAL_CAPACITY",
        "TECHNICAL_SPECIFICATION",
        "EXPERIENCE_PAST_PERFORMANCE",
        "CERTIFICATION",
        "STATUTORY_ELIGIBILITY",
        "LEGAL_UNDERTAKING",
        "COMMERCIAL_TERMS",
        "DELIVERY_LOGISTICS",
        "MSE_MII_PREFERENCE",
        "OTHER"
      ]
    },
    "description": {
      "type": "string",
      "description": "Full text or human-readable description of the clause requirement."
    },
    "field": {
      "type": "string",
      "description": "Normalized target parameter key (e.g., turnover_cr, warranty_years, iso_cert, gstin, delivery_days)."
    },
    "operator": {
      "type": "string",
      "description": "Deterministic comparison operator to evaluate against bidder facts.",
      "enum": [
        ">=",
        "<=",
        ">",
        "<",
        "==",
        "!=",
        "IN",
        "NOT_IN",
        "CONTAINS",
        "MATCHES",
        "EXISTS",
        "VALID_ON",
        "BEFORE",
        "AFTER",
        "BETWEEN"
      ]
    },
    "expected_value": {
      "description": "Expected threshold or target value in its raw representation (number, string, boolean, array, object)."
    },
    "normalized_expected_value": {
      "description": "Normalized threshold converted into standard base units (e.g. INR number, ISO date string, integer days/years)."
    },
    "unit": {
      "type": ["string", "null"],
      "description": "Standardized unit of measurement (e.g., INR, INR_CRORE, INR_LAKH, YEARS, MONTHS, DAYS, PERCENT, COUNT, BOOLEAN)."
    },
    "mandatory": {
      "type": "boolean",
      "description": "Whether failure of this requirement constitutes a non-negotiable tender disqualification."
    },
    "source_type": {
      "type": "string",
      "description": "Hierarchy level and type of the clause origin.",
      "enum": [
        "GTC",
        "STC",
        "ATC",
        "BUYER_ADDED_SPECIFIC",
        "CORRIGENDUM",
        "CUSTOM",
        "INFERRED",
        "UNSPECIFIED",
        "UNKNOWN"
      ]
    },
    "source_clause": {
      "type": ["string", "null"],
      "description": "Specific clause or section reference (e.g., '7.2', 'Clause 3.1.4', 'ATC-01')."
    },
    "source_page": {
      "type": ["integer", "null"],
      "minimum": 1,
      "description": "Page number in the tender PDF where the requirement is specified."
    },
    "source_priority": {
      "type": "integer",
      "minimum": 0,
      "maximum": 10,
      "description": "Precedence integer where higher numbers override lower numbers (GTC=1, STC=2, ATC=3, CORRIGENDUM=4; 0 indicates UNRANKED / UNSPECIFIED / UNKNOWN provenance)."
    },
    "applicability": {
      "type": "object",
      "description": "Exemption and special eligibility rules governing when this requirement applies.",
      "properties": {
        "mse_exemption_allowed": { "type": "boolean", "default": False },
        "startup_exemption_allowed": { "type": "boolean", "default": False },
        "mii_local_content_min_percent": { "type": ["number", "null"] },
        "conditions_text": { "type": "string" }
      },
      "additionalProperties": True
    },
    "evidence": {
      "type": "array",
      "description": "Snippet or coordinates from the tender PDF proving the clause provenance.",
      "items": {
        "type": "object",
        "properties": {
          "page": { "type": "integer", "minimum": 1 },
          "bbox": {
            "type": "array",
            "items": { "type": "number" },
            "minItems": 4,
            "maxItems": 4,
            "description": "[ymin, xmin, ymax, xmax] or [x0, y0, x1, y1]"
          },
          "snippet": { "type": "string" }
        },
        "required": ["page"]
      }
    },
    "extraction_confidence": {
      "type": "string",
      "description": "AI extraction confidence score.",
      "enum": ["HIGH", "MEDIUM", "LOW"],
      "default": "HIGH"
    }
  },
  "additionalProperties": False
}

# 3. bidder_fact.schema.json
bidder_fact_schema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://gem-compliance.sih26100.gov.in/contracts/bidder_fact.schema.json",
  "title": "BidderFact",
  "description": "Represents an individual verifiable parameter or claim extracted from a bidder's submission.",
  "type": "object",
  "required": [
    "fact_id",
    "bid_id",
    "field",
    "value",
    "source_document",
    "page",
    "extraction_confidence"
  ],
  "properties": {
    "fact_id": {
      "type": "string",
      "description": "Unique identifier for the extracted fact (e.g., FACT-BID001-TURNOVER-01)."
    },
    "bid_id": {
      "type": "string",
      "description": "Identifier of the bid this fact belongs to."
    },
    "bidder_id": {
      "type": "string",
      "description": "Identifier of the bidder / submitting company (e.g., company name or entity code)."
    },
    "field": {
      "type": "string",
      "description": "Normalized parameter name (e.g., average_annual_turnover, warranty_years, delivery_days, iso_14001_cert, gstin, pan, local_support)."
    },
    "value": {
      "description": "Raw extracted value (can be numeric, string, boolean, date object, array, or dictionary)."
    },
    "normalized_value": {
      "description": "Standardized canonical value for deterministic evaluation (e.g. numeric INR, integer count, boolean, uppercase string)."
    },
    "unit": {
      "type": ["string", "null"],
      "description": "Unit associated with the value (e.g., INR, INR_CRORE, YEARS, DAYS, PERCENT, COUNT, BOOLEAN)."
    },
    "source_document": {
      "type": "string",
      "description": "Filename or document identifier from which the fact was extracted (e.g., BID-00001.pdf, balance_sheet.pdf)."
    },
    "page": {
      "type": "integer",
      "minimum": 1,
      "description": "1-indexed page number in the source document where the fact appears."
    },
    "bbox": {
      "type": "array",
      "items": { "type": "number" },
      "minItems": 4,
      "maxItems": 4,
      "description": "Bounding box coordinates of the extracted snippet [ymin, xmin, ymax, xmax] or [x0, y0, x1, y1]."
    },
    "raw_text_snippet": {
      "type": "string",
      "description": "Exact text excerpt surrounding the extracted fact for audit trail."
    },
    "extraction_confidence": {
      "type": "string",
      "description": "Confidence level of the extraction model.",
      "enum": ["HIGH", "MEDIUM", "LOW"],
      "default": "HIGH"
    },
    "extraction_method": {
      "type": "string",
      "description": "Pipeline component or method responsible for extraction.",
      "enum": [
        "LLM_STRUCTURED_EXTRACTION",
        "NATIVE_PDF_PARSING",
        "OCR_TEXT_EXTRACTION",
        "TABLE_EXTRACTION",
        "RULE_BASED_REGEX",
        "MOCK_GROUND_TRUTH"
      ],
      "default": "LLM_STRUCTURED_EXTRACTION"
    },
    "metadata": {
      "type": "object",
      "description": "Additional domain-specific attributes (e.g. issuing CA name, certificate number, expiry date).",
      "additionalProperties": True
    }
  },
  "additionalProperties": False
}

# 4. verification_result.schema.json
verification_result_schema = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://gem-compliance.sih26100.gov.in/contracts/verification_result.schema.json",
  "title": "VerificationResult",
  "description": "Represents the deterministic compliance evaluation result of a bidder fact against a tender requirement.",
  "type": "object",
  "required": [
    "verification_id",
    "requirement_id",
    "bid_id",
    "status",
    "severity",
    "expected",
    "actual",
    "operator_used",
    "reason",
    "evidence",
    "requires_human_review"
  ],
  "properties": {
    "verification_id": {
      "type": "string",
      "description": "Unique evaluation run identifier (e.g., VERIF-BID001-REQ001)."
    },
    "requirement_id": {
      "type": "string",
      "description": "Identifier of the tender requirement being evaluated."
    },
    "bid_id": {
      "type": "string",
      "description": "Identifier of the bid under evaluation."
    },
    "fact_id": {
      "type": ["string", "null"],
      "description": "Identifier of the specific bidder fact evaluated (null if fact was missing)."
    },
    "status": {
      "type": "string",
      "description": "Deterministic compliance outcome for the requirement.",
      "enum": [
        "PASS",
        "FAIL",
        "PARTIAL",
        "MISSING",
        "N/A",
        "REVIEW"
      ]
    },
    "severity": {
      "type": "string",
      "description": "Impact of a failure on overall tender compliance.",
      "enum": [
        "CRITICAL",
        "MAJOR",
        "MINOR",
        "INFO"
      ]
    },
    "expected": {
      "description": "Human-readable or structured summary of the requirement threshold (e.g. '>= 10.00 INR crore')."
    },
    "actual": {
      "description": "Human-readable or structured summary of the bidder's submitted fact (e.g. '9.00 INR crore')."
    },
    "operator_used": {
      "type": "string",
      "description": "Deterministic operator executed during comparison (e.g. '>=', '==', 'IN', 'VALID_ON')."
    },
    "reason": {
      "type": "string",
      "description": "Evidence-backed explanatory rationale detailing why the rule passed, failed, or requires review."
    },
    "evidence": {
      "type": "array",
      "description": "Visual and textual proof pointing to the exact locations in submitted documents.",
      "items": {
        "type": "object",
        "required": ["document", "page"],
        "properties": {
          "document": { "type": "string", "description": "Document filename or identifier." },
          "page": { "type": "integer", "minimum": 1, "description": "1-indexed page number." },
          "bbox": {
            "type": "array",
            "items": { "type": "number" },
            "minItems": 4,
            "maxItems": 4,
            "description": "Bounding box coordinates [ymin, xmin, ymax, xmax] or [x0, y0, x1, y1]."
          },
          "snippet": { "type": "string", "description": "Explanatory text excerpt." },
          "source_type": { "type": "string", "description": "Type of evidence (e.g. BIDDER_SUBMISSION, TENDER_CLAUSE, REGISTRY_LOOKUP)." }
        },
        "additionalProperties": True
      }
    },
    "anomaly_refs": {
      "type": "array",
      "items": { "type": "string" },
      "description": "References to any correlated integrity anomaly IDs (e.g., ['ANOM-0000001'])."
    },
    "requires_human_review": {
      "type": "boolean",
      "description": "Flag indicating that officer intervention / confirmation is recommended or mandated."
    },
    "officer_override": {
      "type": ["object", "null"],
      "description": "Optional human-in-the-loop decision record if the procurement officer overrides the result.",
      "properties": {
        "officer_id": { "type": "string" },
        "officer_name": { "type": "string" },
        "decision": { "type": "string", "enum": ["ACCEPTED", "REJECTED", "WAIVED", "CLARIFICATION_REQUESTED"] },
        "justification": { "type": "string" },
        "timestamp": { "type": "string" }
      },
      "required": ["officer_id", "decision", "justification", "timestamp"]
    }
  },
  "additionalProperties": False
}

with open('contracts/document.schema.json', 'w', encoding='utf-8') as f:
    json.dump(document_schema, f, indent=2)

with open('contracts/requirement.schema.json', 'w', encoding='utf-8') as f:
    json.dump(requirement_schema, f, indent=2)

with open('contracts/bidder_fact.schema.json', 'w', encoding='utf-8') as f:
    json.dump(bidder_fact_schema, f, indent=2)

with open('contracts/verification_result.schema.json', 'w', encoding='utf-8') as f:
    json.dump(verification_result_schema, f, indent=2)

print('All 4 JSON schemas created successfully in contracts/')
