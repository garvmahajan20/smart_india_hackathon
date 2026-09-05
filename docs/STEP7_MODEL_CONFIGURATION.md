# Step 7 — Production Model Configuration & Fallback Architecture

> [!IMPORTANT]
> **PRODUCTION MODEL:** **`gemini-3.8-flash`** (Primary)
> **SAFE FALLBACK:** **`gemini-3.7-flash`** (Bounded Single Fallback)
> **QUOTA POLICY:** Zero API consumption for ordinary automated tests. All unit/regression tests operate strictly offline via `MockLLMProvider` or disk cache.

---

## 1. Production Model Selection

* **Primary Model:** **`gemini-3.8-flash`**
* **Rationale for Selection:**
  1. **Empirical Availability:** Verified operational via live API testing (`generateContent` returned HTTP 200 OK with valid structured JSON).
  2. **Specification Match:** Matches the target model tier specified for the SIH26100 procurement platform.
  3. **High Efficiency:** Features high token throughput, low latency, and native support for strict JSON schema extraction (`responseMimeType: "application/json"`, `responseSchema`).

---

## 2. Bounded Safe Fallback Mechanism

To ensure reliability during launch-window high-demand spikes (e.g. transient HTTP 503) without burning through scarce API quota, `GeminiProvider` implements an **explicit, bounded single fallback**:

* **Fallback Model:** **`gemini-3.7-flash`** (Configurable via `GEMINI_FALLBACK_MODEL`).
* **Trigger Conditions:** Triggered **only** when the primary model returns a model-level availability error:
  * `HTTP 404` (`NOT_FOUND` / Model Deprecated)
  * `HTTP 503` (`UNAVAILABLE` / High Demand)
* **Safety Boundaries:**
  * **Zero Cascading:** Attempts at most **one** fallback model call.
  * **No Trigger on Semantic Failures:** Does **not** fallback on client errors (`HTTP 400`), permission errors (`HTTP 403`), or prompt syntax errors.
  * **Audit Transparency:** The response metadata (`LLMProviderResponse.model_name`) honestly reports the fallback model name when fallback occurs.

---

## 3. Configuration & Environment Management

Model selection is strictly configuration-driven:

```env
# D:\smart_india_hackathon\project\.env
GEMINI_API_KEY=<secure_local_key>
GEMINI_MODEL=gemini-3.8-flash
GEMINI_FALLBACK_MODEL=gemini-3.7-flash
```

* **Dynamic Resolution:** `GeminiProvider` reads `GEMINI_MODEL` from `os.environ` (loaded securely via `backend/config.py`).
* **Explicit Override:** Programmatic overrides are supported:
  ```python
  provider = GeminiProvider(model_name="gemini-3.8-flash", fallback_model="gemini-3.7-flash")
  ```

---

## 4. Strict Mode Separation & Quota Policy

To protect the user's free-tier quota, the system strictly separates execution modes:

```
+-------------------------------------------------------------------------+
|                               Mode Hierarchy                            |
+-------------------------------------------------------------------------+
|  1. MOCK (Default in CI/Tests) : Zero network calls. Pure Python stubs. |
|  2. CACHED (Demo / Judging)    : Reads SHA-256 disk cache. 0 API calls. |
|  3. LIVE (Controlled Testing)  : Authenticated requests to Gemini API.  |
+-------------------------------------------------------------------------+
```

* **Automated Unit & Regression Tests:** **NEVER** make live API calls. They utilize `MockLLMProvider` or `LLMMode.MOCK`.
* **Cache Replay:** Successful live extractions are indexed by prompt SHA-256 hash under `data/cache/llm/` for offline judging demonstrations.

---

## 5. Developer Guide: Running Tests & Smoke Tests

### A. Run Local Regression Suite (Zero API Quota Used)
```powershell
python tests\contracts\test_schemas.py
python tests\contracts\test_dataset_mappings.py
python tests\core\test_rule_engine.py
python tests\verification\test_adapters_and_contradictions.py
python tests\ingestion\test_ingestion_pipeline.py
python tests\extraction\test_golden_and_adversarial.py
```

### B. Run Deterministic Benchmark (Zero API Quota Used)
```powershell
python tests\extraction\validate_sih_extraction_benchmark.py
```

### C. Run Minimal Live Smoke Test (Consumes Exactly 1 Live Call)
```python
from backend.config import load_dotenv
from backend.extraction.gemini_provider import GeminiProvider

load_dotenv()
prov = GeminiProvider(model_name="gemini-3.8-flash")
resp = prov.generate_structured("Extract turnover from: 'Annual turnover is Rs. 10 Cr'")
print(f"Model: {resp.model_name}, Status: {resp.content}")
```
