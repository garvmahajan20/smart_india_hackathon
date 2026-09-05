# Gemini API Access & Connectivity Audit Report

> [!IMPORTANT]
> **AUDIT PURPOSE:** Empirical diagnostic verification of the user-configured Gemini API key, live network connectivity to `generativelanguage.googleapis.com`, and discovery of actual model accessibility across Google Gemini Flash model generations.
>
> **CREDENTIAL INTEGRITY NOTICE:** In accordance with strict security policies, the API key value is never logged, echoed, or included anywhere in this report or repository.

---

## 1. Executive Summary

* **API Key Configured:** **YES** (Safely loaded from local `.env` via `backend/config.py`)
* **API Connectivity:** **LIVE SUCCESS** (Base endpoint HTTP 200, returned 50 accessible models)
* **API Project Tier:** Standard Google AI Studio quota tier (non-billing gated; successfully serves inference requests for modern Flash models)
* **Production Model Status:** **NOT CHANGED.** The production default in `backend/extraction/gemini_provider.py` remains unchanged (`gemini-2.5-flash`).
* **Regression Status:** **95 / 95 automated unit and integration tests passing.**

---

## 2. Model Discovery & Live Availability Results

A total of **50 models** and **23 Flash-family variants** were returned by the official `/v1beta/models` endpoint. Candidate testing was conducted via live structured HTTP requests:

| Candidate Model | Access Status | Live Test Result | HTTP Status | Observed Behavior & Safe Diagnostic Reason |
| :--- | :--- | :--- | :---: | :--- |
| **`gemini-3.8-flash`** | **AVAILABLE** | **LIVE SUCCESS** | **200 OK** | **Operational.** Successfully processed prompt and returned structured output. *(An initial test returned HTTP 503 high-demand spike during its launch window, followed immediately by 200 OK on retry).* |
| **`gemini-3.7-flash`** | **AVAILABLE** | **LIVE SUCCESS** | **200 OK** | **Operational.** Responded with structured JSON `{"status": "CONNECTED"}` with low latency. |
| **`gemini-3.6-flash`** | **AVAILABLE** | **LIVE SUCCESS** | **200 OK** | **Operational.** Officially recommended by Google API responses as standard workhorse. |
| **`gemini-3.5-flash`** | **AVAILABLE** | **LIVE SUCCESS** | **200 OK** | **Operational.** Responded with structured JSON `{"status": "CONNECTED"}`. |
| **`gemini-3.1-flash-lite`** | **AVAILABLE** | **LIVE SUCCESS** | **200 OK** | **Operational.** Responded with structured JSON `{"status": "CONNECTED"}`. |
| **`gemini-2.5-flash`** | **NOT AVAILABLE** | **LIVE FAILURE** | **404 Not Found** | `NOT_FOUND`: Deprecated by Google for new API keys: *"This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.6-flash."* |
| **`gemini-2.0-flash`** | **NOT AVAILABLE** | **LIVE FAILURE** | **404 Not Found** | `NOT_FOUND`: Deprecated: *"This model models/gemini-2.0-flash is no longer available. Please update your code to use models/gemini-3.6-flash."* |
| **`gemini-1.5-flash`** | **NOT AVAILABLE** | **LIVE FAILURE** | **404 Not Found** | `NOT_FOUND`: Not supported in this API project. |

---

## 3. Project Quota & Tier Information

* **Google AI Studio Usage Tier:** The user previously observed "Gemini API Usage — Free tier" in Google AI Studio.
* **Empirical Verification:** The API key is fully capable of invoking **Gemini 3.8 Flash**, **Gemini 3.7 Flash**, and **Gemini 3.6 Flash**. Google does not restrict new Flash models solely to paid billing accounts, debunking the misconception that Free Tier accounts are locked to legacy models.
* **Rate Limits:** Standard Google AI Studio requests per minute (RPM) limits apply. The `GeminiProvider` exponential backoff and jitter handle rate spikes cleanly.

---

## 4. Production Configuration & Security Audit

* **Current Production Model Before Audit:** `gemini-2.5-flash`
* **Production Model Status After Audit:** **UNCHANGED.** Neither `gemini_provider.py`, `pipeline.py`, nor any extraction prompt or schema was modified to change the model default.
* **Secret Hygiene Audit:**
  * `.env` is protected by `.gitignore`.
  * Scanned all project files outside `.env` for the configured key: **0 occurrences found (CLEAN)**.
  * No secrets logged to terminal output, documentation, or commits.

---

## 5. Regression Test Results

| Test Suite | Path | Tests Run | Result |
| :--- | :--- | :---: | :---: |
| Contract Schemas | `tests/contracts/test_schemas.py` | 4 | **4 Passed** |
| Dataset Mappings | `tests/contracts/test_dataset_mappings.py` | 3 | **3 Passed** |
| Step 4 Rule Engine | `tests/core/test_rule_engine.py` | 14 | **14 Passed** |
| Step 5 Verification & Contradictions | `tests/verification/test_adapters_and_contradictions.py` | 26 | **26 Passed** |
| Step 6 Ingestion Pipeline | `tests/ingestion/test_ingestion_pipeline.py` | 22 | **22 Passed** |
| Step 7 Golden & Adversarial | `tests/extraction/test_golden_and_adversarial.py` | 26 | **26 Passed** |
| **Total Automated Tests** | | **95** | **95 Passed (100.0%)** |

---

## 6. Recommended Model Choice for Step 7

Based **strictly on observed live API access**:
1. **Primary Choice:** **`gemini-3.8-flash`**
   * Confirmed operational (HTTP 200 OK).
   * Aligns with the project's requested model specification.
2. **Fallback / High-Throughput Alternative:** **`gemini-3.7-flash`** or **`gemini-3.6-flash`**
   * Confirmed operational with immediate response times and zero deprecation warnings.
3. **Action on `gemini-2.5-flash`:** Must be replaced when transitioning from Step 7 setup to production extraction, as Google has permanently deprecated `gemini-2.5-flash` for new API projects (returning HTTP 404).
