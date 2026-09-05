# Step 6 — Document Ingestion & PDF Extraction Pipeline

> [!IMPORTANT]
> **ARCHITECTURAL SCOPE & BOUNDARIES:**
> * **OCR is a fallback, not default:** Text-stream PDFs are extracted natively via PyMuPDF without running unnecessary OCR.
> * **Extraction confidence is a quality heuristic:** It measures visual/character extraction clarity; it is NOT an AI confidence score, compliance score, or fraud probability.
> * **Step 6 does not make compliance decisions or determine fraud:** It creates the structured document/evidence foundation that Step 4 and Step 5 consume.
> * **Layer 2 documents are not ground truth:** They serve solely as real-world format robustness and generalization benchmarks.

---

## 1. System Architecture

The Document Ingestion Pipeline (`backend/ingestion/`) converts raw bid and tender PDFs into structured, coordinate-aware evidence blocks:

```
+-------------------------------------------------------------------------+
|                                PDF Input                                |
|          (SIH Bids / Tenders / Real-World GeM & NCPOR Layer 2)          |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                       DocumentIngestionPipeline                         |
|   1. Safe file opening, size check, SHA-256 computation                |
|   2. Document classification (TENDER, BID, TECHNICAL_BID, etc.)         |
|   3. Page-by-page PyMuPDF native extraction                             |
|   4. Bounding box canonicalization: [y0, x0, y1, x1] -> [ymin..xmax]   |
|   5. Quality heuristic evaluation (character count, printable ratio)   |
|   6. Selective OCR fallback for empty/image-only pages                  |
+-------------------------------------------------------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                           ExtractionResult                              |
|   - DocumentMetadata (ID, hash, file size, page count)                 |
|   - ExtractedPage[] (dimensions, text, quality_score, method)          |
|   - TextBlock[] (coordinates [ymin, xmin, ymax, xmax], raw text)       |
+-------------------------------------------------------------------------+
                                     |
        +----------------------------+----------------------------+
        |                                                         |
        v                                                         v
+-------------------------------+       +---------------------------------+
|      Evidence Generation      |       |   Future FactExtractor Interface|
|   EvidenceReference pointers  |       |   RuleBasedFactExtractor        |
|   (document, page, bbox)      |       |   (Regex parameter extraction)  |
+-------------------------------+       +---------------------------------+
        |                                                         |
        +----------------------------+----------------------------+
                                     |
                                     v
+-------------------------------------------------------------------------+
|                         Downstream Consumers                            |
|   - Step 4: Deterministic Compliance Rule Engine (TenderRequirement)   |
|   - Step 5: Cross-Document Contradiction Engine (IntegrityFinding)     |
+-------------------------------------------------------------------------+
```

---

## 2. Ingestion Pipeline Components

### 2.1 PyMuPDF Native Extraction (`pdf_extractor.py`, `pipeline.py`)
* Extracts page dimensions (`width`, `height`), text streams, and structural blocks (`get_text("blocks")`).
* Preserves raw extracted source text without aggressive destructive alterations.
* High-speed throughput: **~2.9 ms per page** on standard GeM submissions.

### 2.2 Bounding Box Canonicalization (`bbox.py`)
* **Critical Contract Convention:** The canonical contract (`bidder_fact.schema.json`) enforces `[ymin, xmin, ymax, xmax]`.
* **PyMuPDF Coordinate System:** Native extraction produces `[x0, y0, x1, y1]` (left, top, right, bottom).
* **Mapping Rule:**
  $$\text{ymin} = y_0, \quad \text{xmin} = x_0, \quad \text{ymax} = y_1, \quad \text{xmax} = x_1$$
* **Boundary Validation:** Clamps coordinates to `[0, width]` and `[0, height]`, enforces $ymin \le ymax$ and $xmin \le xmax$, and rejects negative coordinates.

### 2.3 Extraction Quality Heuristic (`confidence.py`)
* **Deterministic Signals:**
  1. Character count per page (pages with $< 20$ characters flagged as low-text).
  2. Text block count.
  3. Printable character ratio (flags font encoding anomalies or corrupted glyphs).
* **Categorical Rating:** `HIGH` ($\ge 0.80$), `MEDIUM` ($\ge 0.50$), `LOW` ($< 0.50$).
* **Safe Labeling:** Documented as an optical/extraction quality heuristic, avoiding pseudo-scientific AI confidence or fraud claims.

### 2.4 OCR Fallback Engine (`ocr.py`)
* **Selective Fallback:** OCR is triggered **only** when a page is effectively empty or image-only.
* **Tesseract Engine:** Wraps `pytesseract` and renders the page pixmap to extract bounding boxes via `image_to_data`.
* **OCR Unavailable Safety:** If Tesseract is not installed in the operating environment, the pipeline:
  * Does NOT fabricate text.
  * Does NOT crash.
  * Emits an explicit warning: `"Page N has low/empty text, but OCR engine is unavailable."`
  * Preserves native text if any was extracted.
* **Hybrid Classification:** If Page 1 is native text and Page 2 is scanned image, the overall document method is categorized as `HYBRID`.

---

## 3. Evidence Generation & Engine Integration

### 3.1 Contract Compatibility
Extracts atomic `EvidenceReference` objects containing:
* `document`: Source filename.
* `page`: 1-indexed page number.
* `bbox`: Bounding box `[ymin, xmin, ymax, xmax]`.
* `snippet`: Raw text excerpt.
* `extraction_method`: `"NATIVE_PDF_PARSING"` or `"OCR_TEXT_EXTRACTION"`.
* `extraction_confidence`: `"HIGH"`, `"MEDIUM"`, or `"LOW"`.

### 3.2 Integration with Step 4 (Compliance)
The `RuleBasedFactExtractor` maps extracted blocks to `BidderFact` instances. The Step 4 deterministic rule engine verifies requirements (e.g. `delivery_days <= 60`, `turnover_cr >= 10.0`) and propagates the exact extracted bounding box into `VerificationResult.evidence`.

### 3.3 Integration with Step 5 (Contradiction Engine)
Extracted facts across multiple documents (or distinct pages) feed into the Step 5 contradiction engine. For example, if `BID-00001.pdf` contains differing turnover figures across pages, the contradiction engine flags the conflict with verified bounding boxes on both sides.

---

## 4. Benchmark & Validation Summary

### 4.1 SIH Dataset Benchmark (60 PDFs, 110 Pages)
* **Native Extraction Success:** 110 / 110 pages (100.0%).
* **OCR Invocations on Native Text:** 0 (Zero unnecessary OCR).
* **Extraction Failures:** 0.
* **Bounding Box Validation Errors:** 0.
* **Average Page Length:** 949.0 characters / page across 20.0 text blocks.
* **Throughput:** **5.3 ms per PDF (2.9 ms per page)**.

### 4.2 Layer 2 Real-World Generalization (5 PDFs, 149 Pages)
* Tested real GeM tender documents (`gem_821_010626.PDF`, `gem_072_110726.PDF`, etc.).
* **Total Characters Extracted:** 262,694.
* **Extraction Failures:** 0.
* **Bounding Box Validity:** 100% compliant.

### 4.3 Determinism (3 Repeated Runs)
* Repeated ingestion of the same PDFs yielded **100% bitwise identical results** (same character counts, same blocks, same bounding boxes).

---

## 5. Limitations & Future LLM Boundary

1. **Rule-Based vs Semantic Extraction:** Step 6 provides text blocks and bounding boxes, accompanied by a baseline regex fact extractor. Complex, unstructured narrative clauses require the future Step 7 LLM extraction layer.
2. **Table Grid Reconstruction:** Complex nested multi-column tables are extracted as individual text blocks; advanced grid cell reconstruction will be expanded in Step 7.
3. **No Forensic Forgery Detection:** Step 6 extracts document text; it does not analyze image noise, stamp manipulation, or pixel-level tampering.
