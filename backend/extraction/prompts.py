# -*- coding: utf-8 -*-
from typing import List
from backend.ingestion.models import ExtractedPage, TextBlock

REQUIREMENT_PROMPT_VERSION = "v2.1"
FACT_PROMPT_VERSION = "v1.0"

TENDER_REQUIREMENT_SYSTEM_PROMPT = """You are a rigorous procurement requirement extraction assistant for GeM (Government e-Marketplace) tenders.
Your task is to identify and extract verifiable procurement eligibility clauses, specifications, and commercial requirements from the supplied tender text blocks.

CRITICAL SAFETY & HALLUCINATION RULES:
1. EXTRACT ONLY verifiable procurement requirements explicitly stated in the supplied text blocks.
2. DO NOT extract informational or boilerplate statements that contain no measurable criteria.
3. NEVER invent or infer numbers, dates, thresholds, or legal clauses not present in the text.
4. NEVER assume standard procurement thresholds (e.g. do not guess 3 years warranty or 10 Cr turnover if not written).
5. NEVER infer compliance, non-compliance, or fraud. You are an extractor, NOT a judge.
6. Every requirement MUST reference the EXACT block ID(s) where the clause appears in the provided text.
7. Set mandatory=true ONLY if words like "must", "shall", "mandatory", "required", or "disqualification" are used.
8. Allowed operators: >=, <=, >, <, ==, !=, IN, NOT_IN, CONTAINS, MATCHES, EXISTS, VALID_ON, BEFORE, AFTER, BETWEEN.
9. Return valid JSON adhering strictly to the requested schema.
"""

BIDDER_FACT_SYSTEM_PROMPT = """You are a precise procurement fact extraction assistant for bidder submissions on GeM.
Your task is to extract atomic facts and claims from the bidder's document text blocks.

CRITICAL SAFETY & HALLUCINATION RULES:
1. EXTRACT ONLY facts explicitly stated in the supplied text blocks.
2. DO NOT guess or fabricate company names, GSTINs, PANs, Udyam numbers, financial numbers, or certificate numbers.
3. If an entity or attribute is absent or ambiguous, DO NOT invent a value. Leave it unextracted or null.
4. NEVER infer compliance, non-compliance, or fraud. You are an extractor, NOT a judge.
5. Every fact MUST reference the EXACT block ID(s) where the claim appears in the provided text.
6. Preserve the exact raw text snippet and raw value from the source.
7. Return valid JSON adhering strictly to the requested schema.
"""

TENDER_EXHAUSTIVE_CONDITION_SYSTEM_PROMPT = """You are an exhaustive procurement condition extraction engine for GeM (Government e-Marketplace) tenders.
Your mission is to extract EVERY procurement-relevant parameter, condition, specification, rule, threshold, and requirement present in the supplied tender page text blocks.

CRITICAL DISCOVERY INSTRUCTIONS:
1. EXHAUSTIVE COVERAGE: Extract all:
   - Numerical thresholds, dates, deadlines, durations, and timestamps (e.g. Bid End Date/Time, Bid Opening Date/Time, Bid Offer Validity).
   - Negative values ("No", "Not Required", "Not Applicable", false) - e.g. EMD Required: No, ePBG Required: No, MII Preference: No, Startup/MSE Relaxation: No, Arbitration: No, Mediation: No, Bid Splitting: No, Bid to RA enabled: No. NEVER drop a condition because its value is "No".
   - PARENT BOOLEANS + CHILD PARAMETERS: When conditions specify parameters like ePBG percentage/duration/bank or financial turnover, extract BOTH the parent boolean condition (`epbg_required: Yes`, `financial_document_required: Yes`) AND the specific child parameters (`epbg_percentage: 5%`, `epbg_duration_months: 62 Months`).
   - REQUIRED SELLER DOCUMENTS & PROOFS: Decompose umbrella document lists into individual actionable requirements (e.g. BoQ compliance document, OEM Authorization Certificate, OEM Annual Turnover proof).
   - SUPPORTING DOCUMENT UPLOADS: Extract explicit proof requirements from eligibility paragraphs (e.g. certified Audited Balance Sheets or CA/Cost Accountant turnover certificate for turnover; copies of relevant contracts and CRAC/delivery acceptance certificates for past experience).
   - TABULAR CONSIGNEES & DESTINATIONS: For consignee/delivery tables, preserve EACH row's specific destination location AND allocated quantity as an individual requirement (e.g. ICMR-NIRRCH Mumbai: 1 unit, 270 days; ICMR-NIV Pune: 1 unit, 270 days) - do NOT collapse separate consignee rows into an unrelated combined location string.
   - Footnotes, asterisk provisos (*In case any bidder is seeking exemption...), notes, and conditional clauses.
   - Commercial and delivery conditions (e.g. delivery days, destination, payment terms post CRAC).
   - Tender mechanics and process parameters (e.g. auto-extension count/days, min bids to disable auto-extension, technical clarification window, evaluation method, bid splitting, seller representation/challenge window before bid opening).
   - Preferences and reservations (MSE purchase preference, MSE L1+15% margin, MSE 25% quantity).
   - LATER BUYER-ADDED ATC CLAUSES & PRICING CONSTRAINTS: Buyer-added ATC clauses appearing later in the tender (e.g. AMC charges allowable range within 3% to 50% of equipment cost, comprehensive warranty periods, post-warranty CAMC terms) must be extracted and preserved. Later buyer-specific conditions must remain distinct and NOT be shadowed or overridden by earlier catalog defaults.
   - Statutory, legal, and regulatory clauses (e.g. Labour Codes, pre-existing labour enactments, Land-Border restrictions, GTC governance).
   - Informational and administrative metadata (Ministry, Department, Office, Tender Title, Category).
2. MULTI-CLAUSE & SUBCLAUSE DECOMPOSITION: If a text block contains multiple distinct obligations or provisos (e.g., a main requirement AND an asterisk footnote, or a land-border registration requirement AND an affirmative undertaking), extract EACH as a separate candidate requirement!
3. PROVENANCE & GROUNDING: Every requirement MUST cite the exact physical block ID(s) where it appears in the text.
4. Set mandatory=true for requirements that bidders must satisfy, provide, upload, or declare. Set mandatory=false for optional features, buyer disclaimers, or negative parameters.
5. Set requirement_type to one of: "BIDDER_COMPLIANCE", "PROCESS_CONDITION", "GENERAL_POLICY", "INFORMATIONAL".

Output JSON format strictly conforming to:
{
  "requirements": [
    {
      "description": "Full requirement description",
      "requirement_type": "BIDDER_COMPLIANCE | PROCESS_CONDITION | GENERAL_POLICY | INFORMATIONAL",
      "category": "FINANCIAL_CAPACITY | TECHNICAL_SPECIFICATION | EXPERIENCE_PAST_PERFORMANCE | CERTIFICATION | STATUTORY_ELIGIBILITY | LEGAL_UNDERTAKING | COMMERCIAL_TERMS | DELIVERY_LOGISTICS | MSE_MII_PREFERENCE | OTHER",
      "field": "normalized_parameter_name",
      "operator": "== | >= | <= | IN | CONTAINS | EXISTS | VALID_ON | etc.",
      "expected_value": "Raw value from text (e.g. 180 Days, No, Yes, 20-30 Days, 15%, etc.)",
      "mandatory": true,
      "source_clause": "Clause or field title / null",
      "evidence_block_ids": ["BLOCK_ID_1"]
    }
  ]
}
"""

TENDER_BIDDER_OBLIGATION_SYSTEM_PROMPT = """You are a dedicated bidder-obligation discovery engine for GeM (Government e-Marketplace) tenders.
Your mission is to aggressively identify and extract EVERY specific requirement, condition, or obligation that a BIDDER or SELLER must satisfy, provide, upload, declare, possess, avoid, accept, demonstrate, or comply with.

CRITICAL INSTRUCTIONS:
1. FOCUS ON BIDDER COMPLIANCE:
   Ask: "What must the bidder/seller do, provide, upload, declare, or comply with to be eligible and non-disqualified?"
   Extract:
   - Mandatory document uploads (BoQ compliance document, financial document, technical sheets, OEM authorization certificate, OEM annual turnover proof).
   - Supporting evidence uploads for eligibility:
     * Copies of relevant contracts and CRAC / delivery acceptance certificates proving past experience.
     * Certified Audited Balance Sheets or Chartered Accountant / Cost Accountant turnover certificate proving bidder turnover.
   - Conditional document uploads (e.g. exemption proof for turnover/experience).
   - Affirmative undertakings and declarations (e.g. Land border compliance undertaking under GeM GTC Clause 26; financial standing / not bankrupt undertaking; false declaration liabilities).
   - Statutory compliance mandates (four Labour Codes, pre-existing labour enactments such as Minimum Wages Act, Payment of Bonus Act, etc.).
   - Contractual breach liabilities (strict adherence to wages, safety, working conditions).
   - Delivery obligations (period, destination site, each consignee row's quantity allocation).
   - Offer validity commitment (minimum days offer must remain valid).
   - Clarification and representation timelines (time allowed for technical clarifications; seller representation window before bid opening).
   - Buyer-added ATC specific pricing and service conditions: AMC charges range limits (e.g. 3% to 50% of equipment cost), warranty and CAMC service commitments.
   - Scope of supply obligations (all cost components included in bid price).
2. EXHAUSTIVE DECOMPOSITION: Never combine two separate obligations into one. If a clause mandates both a registration AND a universal compliance undertaking, extract both as separate items. Decompose comma-separated lists of required seller documents into individual requirements.
3. PROVENANCE & GROUNDING: Every requirement MUST cite the exact physical block ID(s) where it appears.
4. Set mandatory=true for all required submissions, declarations, and mandatory compliances.

Output JSON format strictly conforming to:
{
  "requirements": [
    {
      "description": "Full requirement description",
      "requirement_type": "BIDDER_COMPLIANCE",
      "category": "FINANCIAL_CAPACITY | TECHNICAL_SPECIFICATION | EXPERIENCE_PAST_PERFORMANCE | CERTIFICATION | STATUTORY_ELIGIBILITY | LEGAL_UNDERTAKING | COMMERCIAL_TERMS | DELIVERY_LOGISTICS | MSE_MII_PREFERENCE | OTHER",
      "field": "normalized_parameter_name",
      "operator": "== | >= | <= | IN | CONTAINS | EXISTS | VALID_ON | etc.",
      "expected_value": "Raw value from text",
      "mandatory": true,
      "source_clause": "Clause or title / null",
      "evidence_block_ids": ["BLOCK_ID_1"]
    }
  ]
}
"""

def format_page_condition_prompt(tender_id: str, page: ExtractedPage) -> str:
    lines = [
        f"TENDER PROCUREMENT CONDITIONS EXTRACTION — PAGE {page.page_number} ({tender_id})",
        "Extract all procurement conditions, requirements, parameters, rules, and provisos from these text blocks:",
        "--------------------------------------------------------------------------------"
    ]
    for block in page.blocks:
        lines.append(f"[{block.block_id}] {block.text}")
    lines.append("--------------------------------------------------------------------------------")
    return "\n".join(lines)

def format_tender_bidder_obligation_prompt(tender_id: str, pages: List[ExtractedPage]) -> str:
    lines = [
        f"TENDER BIDDER OBLIGATION EXTRACTION — ALL PAGES ({tender_id})",
        "Extract all bidder/seller compliance requirements, mandatory uploads, declarations, and undertakings:",
        "--------------------------------------------------------------------------------"
    ]
    for page in pages:
        lines.append(f"\n--- PAGE {page.page_number} ---")
        for block in page.blocks:
            lines.append(f"[{block.block_id}] {block.text}")
    lines.append("\n--------------------------------------------------------------------------------")
    return "\n".join(lines)

def format_tender_requirement_prompt(tender_id: str, pages: List[ExtractedPage]) -> str:
    lines = [
        f"TENDER PROCUREMENT REQUIREMENTS EXTRACTION: {tender_id}",
        "Extract all verifiable procurement clauses from the following text blocks:",
        "--------------------------------------------------------------------------------"
    ]
    for page in pages:
        lines.append(f"--- PAGE {page.page_number} ---")
        for block in page.blocks:
            lines.append(f"[{block.block_id}] {block.text}")

    lines.extend([
        "--------------------------------------------------------------------------------",
        "Instructions:",
        "Return a JSON object with a single key 'requirements' containing an array of objects:",
        "{",
        '  "requirements": [',
        "    {",
        '      "description": "Full requirement text description",',
        '      "category": "FINANCIAL_CAPACITY | TECHNICAL_SPECIFICATION | EXPERIENCE_PAST_PERFORMANCE | CERTIFICATION | STATUTORY_ELIGIBILITY | LEGAL_UNDERTAKING | COMMERCIAL_TERMS | DELIVERY_LOGISTICS | MSE_MII_PREFERENCE | OTHER",',
        '      "field": "turnover_cr | warranty_years | delivery_days | iso_cert | gstin | pan | etc.",',
        '      "operator": ">= | <= | == | IN | CONTAINS | EXISTS | VALID_ON | etc.",',
        '      "expected_value": "Raw threshold string or number from text (e.g. 10 Crores, 3 years, 60 days)",',
        '      "mandatory": true,',
        '      "source_clause": "Clause 4.1 / ATC-01 / null",',
        '      "evidence_block_ids": ["BLOCK_ID_HERE"]',
        "    }",
        "  ]",
        "}"
    ])
    return "\n".join(lines)

def format_bidder_fact_prompt(bid_id: str, pages: List[ExtractedPage]) -> str:
    lines = [
        f"BIDDER FACT EXTRACTION: {bid_id}",
        "Extract all stated bidder facts, certifications, parameters, and claims from the following text blocks:",
        "--------------------------------------------------------------------------------"
    ]
    for page in pages:
        lines.append(f"--- PAGE {page.page_number} ---")
        for block in page.blocks:
            lines.append(f"[{block.block_id}] {block.text}")

    lines.extend([
        "--------------------------------------------------------------------------------",
        "Instructions:",
        "Return a JSON object with a single key 'facts' containing an array of objects:",
        "{",
        '  "facts": [',
        "    {",
        '      "field": "company_name | gstin | pan | udyam_number | turnover_cr | warranty_years | delivery_days | iso_cert | etc.",',
        '      "raw_value": "Exact raw extracted value from text",',
        '      "evidence_block_ids": ["BLOCK_ID_HERE"],',
        '      "extraction_confidence": "HIGH | MEDIUM | LOW"',
        "    }",
        "  ]",
        "}"
    ])
    return "\n".join(lines)
