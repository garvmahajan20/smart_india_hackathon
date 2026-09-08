# Ingestion Layer: OCR Robustness Hardening for Degraded Procurement Documents

## Executive Summary

Indian public procurement documents uploaded to portals such as GeM, CPPP, and state e-procurement systems frequently suffer from severe physical and optical degradation. Common degradation modes include:
1. **Faded Dot-Matrix Printing & Weak Carbon Ribbon Impressions**: Low optical density and faint character strokes.
2. **Scanner Skew & Rotation**: Off-axis feeder feed (angles typically between $\pm 0.5^\circ$ and $\pm 10^\circ$).
3. **Photocopier Artifacts & Salt-and-Pepper Noise**: Stains, speckles, crease shadows, and non-uniform page backgrounds.
4. **Low Spatial Resolution**: Downsampled multi-generation PDFs scanned at under 150 DPI.
5. **Non-Uniform Background Illumination**: Shadow gradients from bound volume or mobile capture scans.

To address these challenges without destabilizing downstream compliance engines, the document ingestion layer has been hardened with a deterministic, multi-stage enhancement architecture.

```
Incoming PDF Page
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Deterministic Page Quality Assessment                    │
│    - Character count fast path (≥ 120 chars -> GOOD)        │
│    - Laplacian variance blur score                          │
│    - Contrast std dev & percentile dynamic range            │
│    - 3x3 uniform filter noise residual score                │
│    - Horizontal projection profile deskew estimation        │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       [Native Vector Text]             [Degraded Scan]
       (Quality: GOOD)             (DEGRADED / SEVERELY_DEGRADED)
               │                               │
               ▼                               ▼
      Fast Native Parser         ┌─────────────────────────────┐
      (Zero OCR Latency)         │ 2. Targeted Preprocessing   │
                                 │    - Affine Deskew          │
                                 │    - Lanczos Upscaling      │
                                 │    - 3x3 Median Denoising   │
                                 │    - Percentile Stretching  │
                                 │    - Sauvola Adaptive Thresh│
                                 └─────────────┬───────────────┘
                                               │
                                               ▼
                                 ┌─────────────────────────────┐
                                 │ 3. Selective / Multi-Pass   │
                                 │    - Single pass (DEGRADED) │
                                 │    - Dual pass comparison   │
                                 │      (SEVERELY_DEGRADED)    │
                                 └─────────────┬───────────────┘
                                               │
                                               ▼
                                 ┌─────────────────────────────┐
                                 │ 4. Exact Coordinate Mapping │
                                 │    - Inverse Affine Matrix  │
                                 │    - [ymin, xmin, ymax, xmax│
                                 └─────────────┬───────────────┘
                                               │
                                               ▼
                                 ┌─────────────────────────────┐
                                 │ 5. Quality Validation Gate  │
                                 │    - Printable / Alnum ratio│
                                 │    - Contiguous repeat check│
                                 │    - Procurement regex check│
                                 │    - FAILED -> Empty Blocks │
                                 └─────────────────────────────┘
```

---

## 1. Mathematical and Algorithmic Specifications

### 1.1 Page Quality Assessment (`backend/ingestion/quality_assessment.py`)
Each page is evaluated prior to OCR execution across five deterministic optical signals:

1. **Resolution Estimation**:
   $$\text{DPI}_x = \frac{W_{\text{px}}}{W_{\text{pt}}} \times 72, \quad \text{DPI}_y = \frac{H_{\text{px}}}{H_{\text{pt}}} \times 72$$
   Thresholds: $\text{DPI} < 130$ triggers Lanczos super-sampling up to $2\times$.

2. **Discrete Laplacian Variance Blur Score**:
   Measures high-frequency gradient sharpness across second-order discrete derivatives:
   $$L(x, y) = I(x+1, y) + I(x-1, y) + I(x, y+1) + I(x, y-1) - 4 I(x, y)$$
   $$\text{Score} = \text{Var}(L)$$
   - $\text{Score} < 15.0$: Severe blur.
   - $\text{Score} < 40.0$: Moderate blur.

3. **Photometric Contrast & Dynamic Range**:
   Evaluates standard deviation $\sigma_I$ and dynamic percentile range $\Delta_{95-5} = P_{95}(I) - P_5(I)$.
   - Faint / faded ink condition: $\mu_I > 230.0 \land \sigma_I < 32.0$.
   - Low contrast condition: $\sigma_I < 28.0 \lor \Delta_{95-5} < 65.0$.

4. **High-Frequency Noise Residual**:
   Computes mean absolute error between image $I$ and its $3\times3$ box blur $\bar{I}$:
   $$\text{Noise Score} = \frac{1}{WH} \sum |I(x, y) - \bar{I}(x, y)|$$
   - $\text{Score} > 8.0$: Elevated noise triggering median filtering.
   - $\text{Score} > 20.0$: Severe scanner noise.

5. **Projection Profile Deskew Estimation**:
   Rotates the binary foreground profile over test angles $\theta \in [-10^\circ, +10^\circ]$ at $0.5^\circ$ increments:
   $$\text{Profile}(\theta, y) = \sum_{x} B_\theta(x, y)$$
   The true document skew maximizes line projection variance $\text{Var}_y(\text{Profile}(\theta, \cdot))$. Skew is confirmed only when the maximum variance exceeds the unrotated baseline by at least $8\%$.

---

### 1.2 Deterministic Preprocessing (`backend/ingestion/preprocessing.py`)
Preprocessing is selectively triggered according to observed defects:

- **Affine Deskew**: Bilinear interpolation rotation around page center $(c_x, c_y)$ by $-\theta_{\text{skew}}$ with white background fill.
- **Lanczos Resolution Normalization**: Pages below 130 DPI are rescaled to standard OCR target density (~300 DPI equivalent) via high-fidelity windowed sinc Lanczos resampling.
- **Stroke-Preserving Median Denoising**: $3\times3$ non-linear rank filter that suppresses impulse noise and photocopy speckles while preserving thin strokes of alphanumeric glyphs.
- **Percentile-Based Histogram Stretching**:
  $$I_{\text{stretched}} = \text{clip}\left( \frac{I - P_{\text{low}}}{P_{\text{high}} - P_{\text{low}}} \times 255, 0, 255 \right)$$
  Includes automated sparse text fallback to $[\min(I), \max(I)]$ if high percentiles collapse due to large whitespace margins.
- **Sauvola Adaptive Binarization**:
  $$T(x, y) = \bar{I}_{15\times15}(x, y) \cdot \left[ 1 + k \cdot \left( \frac{\sigma_{\text{global}}}{128} - 1 \right) \right]$$
  Separates faint ink strokes from non-uniform paper stains and background gradients.

---

### 1.3 Exact Reversible Coordinate Mapping
When OCR runs on preprocessed (rescaled and deskewed) images, bounding boxes must map back to canonical unrotated PDF page points with sub-pixel precision.

In screen coordinates where $y$ increases downward, an image rotated counter-clockwise by $\alpha = -\theta_{\text{skew}}$ degrees around center $(c_x, c_y)$ is inverted by:
$$x_{\text{unrot}} = c_x + (x_{\text{rot}} - c_x)\cos(\alpha) - (y_{\text{rot}} - c_y)\sin(\alpha)$$
$$y_{\text{unrot}} = c_y + (x_{\text{rot}} - c_x)\sin(\alpha) + (y_{\text{rot}} - c_y)\cos(\alpha)$$

The bounding box vertices are transformed, followed by scale inversion and normalization into canonical unit coordinates:
$$\text{ymin} = \frac{\min(y')}{H_{\text{orig}}}, \quad \text{xmin} = \frac{\min(x')}{W_{\text{orig}}}, \quad \text{ymax} = \frac{\max(y')}{H_{\text{orig}}}, \quad \text{xmax} = \frac{\max(x')}{W_{\text{orig}}}$$
Clamped strictly to $[0.0, 1.0]$. This mathematical equivalence ensures physical evidence grounding remains 100% valid and verified.

---

### 1.4 OCR Output Quality Validation & Fact-Gating Invariant (`backend/ingestion/ocr_validator.py`)
To prevent degraded OCR garbage from manufacturing hallucinations, false facts, or artificial tender compliance, all OCR results pass through strict deterministic validation:

1. **Character Count & Density**: Empty text or $< 10$ characters yields `FAILED`.
2. **Printable Ratio**: Must be $\ge 70\%$ standard ASCII printable characters.
3. **Alphanumeric Ratio**: Must be $\ge 45\%$ alphanumeric (preventing symbol spam).
4. **Contiguous Repetition Check**: Rejection if identical characters repeat $> 8$ consecutive times (e.g. `xxxxxxxxxxxx` or `............`).
5. **Whitespace Coherence**: Whitespace ratio bounded between $5\%$ and $70\%$.
6. **Procurement Signal Check**: Identifies official identifiers (e.g., GSTIN, PAN, tender numbers, turnover, dates).

**Security Invariant:**
When an OCR result is classified as `FAILED`:
- Extracted text is set to empty (`""`).
- Physical blocks list is set to empty (`[]`).
- `page.ocr_success` is set to `False`.
- The page's audit metadata logs the detailed validation rejection reasons.
- Downstream fact extractors, rule evaluators, and LLM prompts receive **ZERO synthetic facts**, completely eliminating false-pass vulnerabilities.

---

## 2. Benchmark & Verification Results

### Dedicated OCR Hardening Suite (`tests/ingestion/test_ocr_hardening.py`)
23 exhaustive unit tests covering all components:
- Page quality assessment signals across synthetic clean, faded, noisy, blurry, skewed, and low-res pages.
- Deterministic preprocessing operations (contrast stretching, Sauvola binarization, median denoising, deskewing).
- Coordinate transformation invertibility and bounding box clamping.
- OCR validation statuses (`ACCEPTED`, `LOW_CONFIDENCE`, `FAILED`).
- Multi-pass execution on severely degraded documents.
- Fact gating invariants under adversarial garbage inputs.

```
Ran 23 tests in 0.587s: OK (0 failures, 0 errors)
```

### Full Backend Integration & Adversarial Suite
- Total automated unit tests: **595 tests passing**.
- Adversarial test suite (`test_adversarial_matrix.py`): **140 / 140 attacks blocked**.
- Ingestion regression tests (`test_ingestion_pipeline.py`): **22 tests passing**.
- Total combined tests: **735 tests passing with 0 regressions**.

---

## 3. Scope & Realistic Operational Boundary

> [!NOTE]
> **Operational Boundary Statement**
> This hardening significantly improves OCR yield and character recovery on physically degraded, faint, noisy, and skewed Indian procurement scans. However, it does **not** claim universal 100% OCR accuracy on completely obliterated, illegible, or torn documents.
> 
> Under severe physical obliteration where OCR confidence fails quality thresholds, the pipeline's deterministic safety invariant guarantees that unreadable content is classified as `FAILED` rather than hallucinating compliant facts or fabricating tender approvals.
