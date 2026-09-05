# Layer 2 Real-World Tender Validation

This document validates the canonical contracts against real-world Indian public procurement tender documents acquired from the **National Centre for Polar and Ocean Research (NCAOR)** and **GeM (Government e-Marketplace)**.

---

## 1. Validated Real-World Tender Clauses

We inspected multi-page GeM tender documents (such as `gem_821_010626.PDF`, `gem_072_110726.PDF`, and `gem_538_060826.PDF`) and validated how representative clauses map into `requirement.schema.json`.

### Example A: Bidder Minimum Average Annual Turnover
* **Source Tender:** GeM Bid `GEM/2026/B/7743020` (Page 1)
* **Raw Tender Text:** "Minimum Average Annual Turnover of the bidder (For 3 Years): 5 Lakh INR. Documentary evidence in the form of certified Audited Balance Sheets... to be submitted."
* **Mapped Canonical Contract:**
```json
{
  "requirement_id": "REQ-GEM7743020-FIN-01",
  "tender_id": "GEM/2026/B/7743020",
  "category": "FINANCIAL_CAPACITY",
  "description": "Minimum Average Annual Turnover of the bidder for 3 years must be at least 5 Lakh INR.",
  "field": "bidder_turnover_lakh",
  "operator": ">=",
  "expected_value": 5.0,
  "normalized_expected_value": 500000,
  "unit": "INR_LAKH",
  "mandatory": true,
  "source_type": "GTC",
  "source_clause": "Bid Details Item 1",
  "source_page": 1,
  "source_priority": 1,
  "applicability": {
    "mse_exemption_allowed": true,
    "startup_exemption_allowed": true
  },
  "extraction_confidence": "HIGH"
}
```

### Example B: ePBG (Performance Security) Provision
* **Source Tender:** GeM Bid `GEM/2026/B/7743020` (Page 3)
* **Raw Tender Text:** "ePBG Detail: Advisory Bank: State Bank of India. ePBG Percentage: 5.00%. Duration of ePBG required: 14 Months."
* **Mapped Canonical Contract:**
```json
{
  "requirement_id": "REQ-GEM7743020-EPBG-01",
  "tender_id": "GEM/2026/B/7743020",
  "category": "COMMERCIAL_TERMS",
  "description": "ePBG of 5.00% valid for 14 months required from Advisory Bank.",
  "field": "epbg_percentage",
  "operator": ">=",
  "expected_value": 5.0,
  "normalized_expected_value": 5.0,
  "unit": "PERCENT",
  "mandatory": true,
  "source_type": "STC",
  "source_clause": "ePBG Detail",
  "source_page": 3,
  "source_priority": 2,
  "extraction_confidence": "HIGH"
}
```

### Example C: MSE Purchase Preference & Exemption
* **Source Tender:** GeM Bid `GEM/2026/B/7743020` (Page 4)
* **Raw Tender Text:** "MSE Purchase Preference: Yes. Purchase Preference to MSE OEMs/Service Providers available up to price within L1+15% for 25% of quantity."
* **Mapped Canonical Contract:**
```json
{
  "requirement_id": "REQ-GEM7743020-MSE-01",
  "tender_id": "GEM/2026/B/7743020",
  "category": "MSE_MII_PREFERENCE",
  "description": "MSE Purchase Preference available up to price within L1+15% for 25% quantity.",
  "field": "mse_purchase_preference",
  "operator": "==",
  "expected_value": true,
  "normalized_expected_value": true,
  "unit": "BOOLEAN",
  "mandatory": false,
  "source_type": "GTC",
  "source_clause": "MSE Purchase Preference",
  "source_page": 4,
  "source_priority": 1,
  "applicability": {
    "conditions_text": "L1+15% margin of purchase preference"
  },
  "extraction_confidence": "HIGH"
}
```

### Example D: OEM Authorization Requirement
* **Source Tender:** GeM Bid `GEM/2026/B/7743020` (Page 2)
* **Raw Tender Text:** "Document required from seller: OEM Authorization Certificate, Past Performance, Bidder Turnover."
* **Mapped Canonical Contract:**
```json
{
  "requirement_id": "REQ-GEM7743020-DOC-OEM",
  "tender_id": "GEM/2026/B/7743020",
  "category": "CERTIFICATION",
  "description": "OEM Authorization Certificate must be uploaded by seller.",
  "field": "oem_authorization_certificate",
  "operator": "EXISTS",
  "expected_value": true,
  "normalized_expected_value": true,
  "unit": "BOOLEAN",
  "mandatory": true,
  "source_type": "ATC",
  "source_clause": "Document required from seller",
  "source_page": 2,
  "source_priority": 3,
  "extraction_confidence": "HIGH"
}
```

---

## 2. Key Findings from Real-World Validation
1. **Multi-Unit Normalization**: Real tenders specify turnover in Lakhs (`5 Lakh INR`) or Crores (`14.58 Crore INR`). The dual `expected_value` and `normalized_expected_value` fields allow the UI to preserve natural language while the deterministic rule engine checks raw numeric values in base INR.
2. **Clause Precedence (GTC < STC < ATC)**: GeM explicitly divides clauses into General Terms (GTC), Special Terms (STC), and Buyer Added Additional Terms (ATC). Priority integers (1, 2, 3) seamlessly model that ATC buyer conditions override standard GTC terms.
3. **Exemption Policies**: GeM routinely specifies turnover/experience exemptions for MSEs and Startups. The `applicability` sub-object in `TenderRequirement` accommodates these conditional rules cleanly.
