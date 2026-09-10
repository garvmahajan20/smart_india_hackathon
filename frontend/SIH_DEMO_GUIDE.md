# ProcureSure Frontend — SIH Demo Guide

## Purpose

This frontend is the SIH demonstration surface for an evidence-first procurement compliance and integrity workbench. It is designed to show how a government procurement officer can move from a bidder submission to a traceable compliance decision and, when necessary, human adjudication.

The current frontend is a **local prototype**. Its seeded cases and processing animation provide a deterministic demonstration without requiring the backend to be running. A typed API client is already present so the UI can be connected to the verification backend when integration is enabled.

## Recommended evaluator journey

Use this order for the strongest short demonstration:

1. **Dashboard — Command Center**
   - Show the verification pulse and attention-required cases.
   - Point out that the dashboard prioritizes anomalous or failed bids rather than forcing an officer to inspect every submission.

2. **Open Bharat Devices — high-signal investigation**
   - Select `BID-00001` / Bharat Devices.
   - The workbench opens directly on **Registries & Contradictions** because this case contains a cross-document contradiction.

3. **Explain the contradiction**
   - Show the side-by-side evidence comparison.
   - Technical Schedule: GSTIN `29SYNTH0000003F1Z` on page 1.
   - Financial Annexure: GSTIN `29SYNTH0000103F1Z` on page 2.
   - Use **View in document** for both sides to demonstrate physical evidence grounding.

4. **Show the forensic evidence layer**
   - Point to the document/page, bounding box, verbatim snippet and grounding state.
   - Explain that the finding is not presented as an unsupported AI accusation; the officer can inspect the exact source evidence.

5. **Show the recommended action**
   - The contradiction recommends **Human Review / Hold for adjudication**.
   - Use **Route to Review**.

6. **Review Queue — Human Adjudication**
   - Open the corresponding review item.
   - Demonstrate the decision options: confirm discrepancy, dismiss finding, or request clarification.
   - Explain that the final adjudication remains with the officer.

7. **Optional second case: Suryodaya Infra**
   - Use `BID-00667` to demonstrate uncertainty rather than contradiction.
   - It has two officer-review signals: an ambiguous EMD exemption and a conditional local-support commitment.
   - This is useful for explaining why not every non-pass result should be treated as fraud.

8. **Optional clean case: BluePeak Solutions**
   - Use `BID-00031` to show the positive path: all 8 requirements pass and no officer review is required.

## Canonical demo cases

| Bid | Case | Overall | Best demonstration point |
|---|---|---|---|
| `BID-00031` | BluePeak Solutions | PASS | Clean end-to-end verification |
| `BID-00733` | Pragati Technologies | FAIL | Deterministic compliance failures |
| `BID-00667` | Suryodaya Infra | FAIL | Ambiguity routed to human review |
| `BID-00001` | Bharat Devices | FAIL | Cross-document contradiction + evidence grounding |

**Recommended hero case:** Bharat Devices. It best communicates the differentiator of the prototype: a finding is connected to concrete document evidence and then routed to an officer rather than treated as an automatic fraud verdict.

## Screen responsibilities

### Dashboard
Command center for triage. It surfaces evaluated submissions, compliant bids, mandatory failures, review signals and high-priority cases.

### New Verification
Intake and processing surface. The prototype accepts PDF submissions, validates selected files, lets the officer choose a ruleset/demo case and presents a staged analysis sequence before opening the workbench.

### Verification Workbench
Forensic investigation surface. It combines the requirement matrix, document view, evidence inspector, registry/contradiction workspace and machine-readable dossier view.

### Review Queue
Human adjudication surface. It converts review signals into an officer decision workflow instead of hiding uncertainty behind an automated verdict.

## Technical story to explain during SIH

The frontend is intentionally aligned to the backend contract rather than pretending that the browser is the verification engine.

Conceptually:

```text
Tender + Bid Documents
        ↓
AI / extraction pipeline (upstream)
        ↓
Structured facts + evidence pointers
        ↓
Deterministic compliance / integrity evaluation
        ↓
Aggregated verification result
        ↓
ProcureSure frontend
        ├── Dashboard / triage
        ├── Requirement matrix
        ├── Evidence grounding
        ├── Contradiction inspection
        └── Human review / adjudication
```

The frontend's typed API boundary exposes operations for health, verification retrieval, dossier retrieval, review items and bid verification. The local demonstration currently uses seeded verification objects so the evaluator can run the complete journey without backend availability.

## Evidence-grounding explanation

When asked “How do you know this finding is real?”, demonstrate the chain:

**Finding → document → page → bounding box → verbatim snippet → officer decision**

For the Bharat Devices contradiction, the document canvas contains seeded physical text blocks representing extracted document evidence. Selecting Evidence A or Evidence B focuses the corresponding block and loads it into the forensic inspector.

The UI labels this as physical evidence grounding. This is a prototype representation of the intended extraction/evidence contract; it should not be described as live OCR/PDF processing during the local demo.

## What is simulated vs integrated

### Currently demonstrated locally

- Seeded canonical tender/bid cases.
- Deterministic-looking verification results and rule traces.
- PDF intake UI and file validation.
- Staged processing animation.
- Document/evidence navigation using seeded physical text blocks.
- Contradiction comparison.
- Human review queue and local decision interaction.

### Backend integration boundary

The frontend contains a typed API client using `VITE_API_BASE_URL` when configured. The available contract covers:

- `GET /health`
- `GET /api/v1/verification/{verificationId}`
- `GET /api/v1/verification/{verificationId}/dossier`
- `GET /api/v1/verification/{verificationId}/review-items`
- `POST /api/v1/verify`

Do **not** claim that the current local demo is executing these backend endpoints unless backend integration has actually been enabled and verified.

## Local run

From the `frontend/` directory:

```bash
npm install
npm run dev
```

For the production build check:

```bash
npm run build
```

The project uses React, TypeScript and Vite. The build script runs TypeScript compilation followed by the Vite production build.

## Demo-day checklist

Before presenting:

- [ ] Pull the latest `frontend-dev` branch.
- [ ] Run `npm install` if dependencies changed.
- [ ] Run `npm run build` and confirm it completes successfully.
- [ ] Run `npm run dev`.
- [ ] Open Dashboard.
- [ ] Test Bharat Devices contradiction path.
- [ ] Test both Evidence A and Evidence B document actions.
- [ ] Test **Route to Review**.
- [ ] Test one Review Queue decision.
- [ ] Test New Verification with no file selected and with a canonical demo case.
- [ ] Keep the browser window at a comfortable desktop size for the workbench.

## Presentation language

Prefer:

- “evidence-grounded finding”
- “deterministic rule evaluation”
- “officer review”
- “traceable source evidence”
- “human adjudication”
- “prototype / local demo” where applicable

Avoid saying:

- “the AI proved fraud”
- “the frontend itself verifies the tender”
- “live government registry verification” unless the corresponding backend adapter is actually running
- “cryptographic run ID” — the current run ID is an identifier, not a cryptographic seal

## Scope and branch discipline

This guide belongs to the frontend implementation and is maintained on `frontend-dev`.

The frontend work should remain isolated from `main` and `backend-dev`. Do not merge, rebase or modify those branches as part of frontend demo preparation.
