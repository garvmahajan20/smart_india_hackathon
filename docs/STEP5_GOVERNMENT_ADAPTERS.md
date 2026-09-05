# Step 5 — Mock Government Verification Adapters

> [!IMPORTANT]
> **GOVERNMENT VERIFICATION IS MOCKED FOR THE HACKATHON PROTOTYPE. NO LIVE GOVERNMENT API IS ACCESSED.**
> The system does not access live GSTN, Income Tax PAN, Udyam, GeM, or government blacklist databases. All verification queries are executed against a deterministic local in-memory registry derived from the SIH canonical dataset and controlled synthetic fixtures.

---

## 1. Architectural Motivation & Design Principle

In public procurement (GeM), bidder verification requires confirming statutory registrations and identifying potential debarment:
* **Compliance:** Does the bidder satisfy tender criteria (e.g., turnover, experience, warranty)?
* **Integrity / Verification:** Are the bidder''s identity claims (GSTIN, PAN, MSME Udyam status) genuine and unencumbered by debarment?

Rather than making the compliance engine directly dependent on third-party government services, Step 5 introduces a **Swap-In Ready Adapter Layer** (`backend/verification/`). The rest of the platform depends solely on the abstract interface `BaseGovernmentAdapter`.

```
                        +------------------------------+
                        |     Deterministic Pipeline   |
                        +------------------------------+
                                       |
                                       v
                        +------------------------------+
                        |    BaseGovernmentAdapter     |
                        +------------------------------+
                                       |
        +------------------+-----------+-----------+------------------+
        |                  |                       |                  |
        v                  v                       v                  v
+---------------+  +---------------+       +---------------+  +-------------------+
| MockGSTAdapter|  | MockPANAdapter|       |MockUdyamAdapter| |MockDebarmentAdapter|
+---------------+  +---------------+       +---------------+  +-------------------+
        |                  |                       |                  |
        +------------------+-----------+-----------+------------------+
                                       |
                                       v
                        +------------------------------+
                        |   MockGovernmentRegistry     |
                        | (In-memory, Deterministic)   |
                        +------------------------------+
```

When official government APIs (GSTN sandbox, MCA21, Udyam API) become available in production, replacing mock adapters requires zero modification to the compliance rule engine or UI.

---

## 2. Adapter Interface Specification

All adapters inherit from `BaseGovernmentAdapter` and return a standardized `AdapterResponse` dataclass:

```python
class BaseGovernmentAdapter(ABC):
    @property
    @abstractmethod
    def adapter_name(self) -> str: ...

    @property
    @abstractmethod
    def source_name(self) -> str: ...

    @abstractmethod
    def verify(
        self,
        identifier: str,
        expected_entity_name: Optional[str] = None,
        timestamp: Optional[str] = None,
        **kwargs: Any
    ) -> AdapterResponse: ...
```

### Verification Status Enum
* `VERIFIED`: The registration exists, is currently active, and matches the expected entity name.
* `NOT_FOUND`: The identifier does not exist in the registry.
* `IDENTITY_MISMATCH`: The identifier exists, but is registered to a legal entity differing from the bidder.
* `INACTIVE`: The registration exists but is suspended, cancelled, or inactive.
* `DEBARRED`: The bidder is subject to an active blacklist/debarment order.
* `NOT_DEBARRED`: No debarment order found for the queried entity.
* `REVIEW`: Anomaly or ambiguity detected (e.g. altered digits or certificate anomaly).

---

## 3. Implemented Mock Adapters

### 3.1 MockGSTAdapter (`backend/verification/mock_gst.py`)
* **Queries:** In-memory registry loaded from `entities.jsonl` (3,000 entities).
* **Checks:**
  1. Identifier presence in registry (`NOT_FOUND` if absent).
  2. Registration status (`ACTIVE` vs `INACTIVE`).
  3. Identity cross-check against bidder name with legal suffix normalization (e.g. "Private Limited" vs "PVT LTD"). Emits `IDENTITY_MISMATCH` if names materially diverge.
* **Source Label:** `MOCK_GST_REGISTRY` (never claims to be a live GSTN endpoint).

### 3.2 MockPANAdapter (`backend/verification/mock_pan.py`)
* **Queries:** In-memory registry indexed by 10-character alphanumeric PAN.
* **Checks:** Validity, registration status, and legal entity correspondence.
* **Source Label:** `MOCK_PAN_REGISTRY`.

### 3.3 MockUdyamAdapter (`backend/verification/mock_udyam.py`)
* **Queries:** Indexed from `certificates.jsonl` (2,300 Udyam registration certificates).
* **Bridge to Step 4 Exemption Engine:**
  * When a bidder claims MSE relaxation under GeM guidelines, `MockUdyamAdapter` verifies the certificate and its anomaly status (`NONE` vs `ALTERED_DIGITS` / `NAME_MISMATCH`).
  * If verified, emits `is_mse: True` and enterprise category (`MICRO` / `SMALL`), establishing the factual foundation for the Step 4 engine to apply statutory exemptions (`N/A`).
* **Source Label:** `MOCK_UDYAM_REGISTRY`.

### 3.4 MockDebarmentAdapter (`backend/verification/mock_debarment.py`)
* **Queries:** Controlled synthetic debarment fixture containing positive test cases (e.g., bid rigging orders, forged bank guarantee orders) and clean baseline entities.
* **Checks:** Debarment status, issuing authority, debarment order reference, and sanction validity dates.
* **Source Label:** `MOCK_DEBARMENT_REGISTRY`.

---

## 4. Future Official API Replacement Strategy

To upgrade from mock to live government services:
1. Implement official API client class inheriting from `BaseGovernmentAdapter` (e.g., `LiveGSTNAdapter`).
2. Map live JSON responses to the canonical `AdapterResponse` dataclass.
3. Configure dependency injection in backend container to supply `LiveGSTNAdapter` in place of `MockGSTAdapter`.
4. Zero changes required to `DeterministicRuleEngine`, `ContradictionEngine`, or frontend dashboards.
