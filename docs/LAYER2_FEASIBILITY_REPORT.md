# LAYER 2 FEASIBILITY REPORT

## 1. Dataset Access

* Dataset: rumourscape/tenders (Hugging Face)
* Access method: Hugging Face Datasets API Server (rows endpoint)
* Full dataset size: ~3.45 GB
* License: Open (Hugging Face dataset)
* Sample size: 100 records

## 2. Field Availability

| Field               | Availability | Quality | Useful For |
| ------------------- | ------------ | ------- | ---------- |
| tender_id           | 100%         | Good    | Unique ID |
| organisation_name   | 100%         | Good    | Context / Analytics |
| title               | 100%         | Good    | Context |
| tender_description  | 100%         | Fair    | Context (mostly repeats title) |
| tender_type         | 99%          | Good    | Tender classification (Works/Goods/Services) |
| tender_document_url | 99%          | Poor    | See below (points to HTML portals, not PDFs) |

## 3. Tender Document URL Test

* URLs present: 99/100
* URLs reachable: 19/20 (sampled)
* Actual documents: 0/20
* PDF documents: 0/20
* Text-extractable documents: 0
* Usable tender documents: 0
* Main failure reasons: The URL provided (`tender_document_url`) points to the eProcurement web portal detail page (e.g., `eproc.punjab.gov.in/nicgep/app...`), NOT directly to a PDF file. Downloading the actual PDF from these pages requires solving CAPTCHAs, handling session tokens, and parsing complex HTML.

## 4. Text Quality

Assess the usefulness of the textual fields for:

* requirement extraction: Not useful (requirements are inside the missing PDFs)
* clause extraction: Not useful
* tender classification: Useful (`tender_type` and title)
* financial requirement detection: Not useful
* experience requirement detection: Not useful
* eligibility requirement detection: Not useful

The text fields are extremely short and mostly consist of just the name of the work/procurement (e.g., "Civil Building Work@Indore").

## 5. Recommended Layer 2 Strategy

**C. Not useful enough; find another dataset**

The entire purpose of our AI pipeline is to extract requirements and clauses from Tender PDFs. Because this dataset only provides high-level metadata and dead-end HTML URLs (requiring CAPTCHA bypass to get the PDFs), it cannot be used to test our extraction pipeline. Without the PDFs or the actual clauses, this dataset provides no value for our core AI capability.

## 6. Recommended Sample Size

0 records. We should not import this dataset for our hackathon MVP.

## 7. Important Risks

* dead URLs / access restrictions: The URLs point to NICGEP portals which block automated scraping and require CAPTCHAs.
* missing fields: No actual clauses, criteria, or eligibility text.
* data quality issues: The descriptions are often just duplicates of the title.

## 8. Decision

DO NOT USE

