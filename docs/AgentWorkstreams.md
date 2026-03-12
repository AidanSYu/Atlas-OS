# Agent Workstream Breakdown — Discovery OS Golden Path

**Source plan:** `DiscoveryOS_GoldenPath_Plan.md` v3.1
**Execution model:** 4 sequential waves. Within each wave, all agents run in parallel.
**Gate rule:** No wave starts until every agent in the previous wave has passed its exit gate.

---

## Dependency Map

```
WAVE 0  Shared Types & Utilities (no dependencies)
  └─ A0: TypeScript contract file
  └─ A1: TruncatedPayload utility

WAVE 1  Independent foundations (depends on Wave 0 only)
  └─ B1: discoveryStore.ts (state machine)     ← frontend
  └─ B2: Backend: initialize + schema          ← backend
  └─ B3: Backend: chemistry/domain tools       ← backend
  └─ B4: ExecutionPipeline.tsx                 ← frontend
  └─ B5: JobsQueue component                   ← frontend
  └─ B6: Backend: route_planning + validation  ← backend

WAVE 2  Components (depends on Wave 1)
  └─ C1: MissionControl.tsx                    ← frontend
  └─ C2: CandidateArtifact.tsx                 ← frontend
  └─ C3: CapabilityGapArtifact.tsx             ← frontend
  └─ C4: SpectroscopyArtifact.tsx              ← frontend
  └─ C5: EntityHotspot component               ← frontend
  └─ C6: Backend: generate + screen endpoints  ← backend
  └─ C7: Epoch Navigator + tree viewer         ← frontend

WAVE 3  Wiring & Integration (depends on Wave 2)
  └─ D1: workspace-page layout refactor        ← frontend
  └─ D2: Cross-Store Bridge                    ← frontend + backend
  └─ D3: StructureCompletionSuggestion         ← frontend
  └─ D4: Follow-up taxonomy pills              ← frontend + backend
  └─ D5: Stage 7 feedback loop                 ← backend + frontend
```

---

## WAVE 0 — Shared Contracts
*Run these first. Everything else imports from them.*

---

### Agent A0 — Shared TypeScript Types

**Files to CREATE:**
- `src/frontend/lib/discovery-types.ts`

**Files to READ for context:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (full document)
- `src/frontend/lib/api.ts` (understand existing patterns)

**Files to NOT touch:** Everything else.

**Task:** Create a single barrel file with every interface defined in the plan. Do not implement any logic — pure TypeScript `interface` and `type` declarations only.

**Must export (copy exactly from the plan):**
```typescript
// Domain
export interface DomainSchema { ... }
export interface ProjectTargetParams { ... }
export interface PropertyConstraint { ... }

// Epochs
export interface Epoch { ... }
export type GoldenPathStage = 1 | 2 | 3 | 4 | 5 | 6 | 7;

// Artifacts
export interface CandidateArtifact { ... }
export interface PredictedProperty { ... }
export type StageArtifact = ...
export interface CapabilityGap { ... }
export interface CapabilityGapResolution { ... }
export interface SpectroscopyValidation { ... }
export interface BioassayResult { ... }

// Store
export interface DiscoveryStore { ... }
export interface BackgroundJob { ... }

// Cross-store bridge
export interface StageContextBundle { ... }
export interface StageArtifactSummary { ... }
export interface TruncatedToolInvocation { ... }

// Follow-up taxonomy
export interface FollowUpSuggestions { ... }
```

**Exit gate:** `npx tsc --noEmit` passes with zero errors on this file. All types are exported and importable.

---

### Agent A1 — TruncatedPayload Utility

**Files to CREATE:**
- `src/frontend/lib/truncate-payload.ts`

**Files to READ for context:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Truncation & Blob Protocol section)

**Files to NOT touch:** Everything else.

**Task:** Implement the payload truncation utility described in the plan. Pure functions, no React, no imports from the rest of the codebase.

**Must implement:**
```typescript
export const PIPELINE_RENDER_LIMITS = {
  maxArrayElements: 500,
  maxStringBytes: 65_536,
  maxNestingDepth: 3,
} as const;

export interface TruncatedPayload {
  preview: string;
  fullSizeBytes: number;
  elementCount?: number;
  blob: Blob | null;
  downloadFilename: string;
}

// Takes any JSON value, returns a TruncatedPayload
export function truncatePayload(value: unknown, downloadFilename: string): TruncatedPayload

// Triggers browser download of blob
export function downloadBlob(payload: TruncatedPayload): void
```

**Rules:**
- Array preview must be valid JSON (ends with `]`)
- String preview must end at a UTF-8 boundary, not mid-character
- Binary/base64 fields (strings matching `^[A-Za-z0-9+/]+=*$` over 100 chars) are treated as blobs without decoding
- Blob is lazy — set to `null` initially, created from raw value only when `downloadBlob()` is called

**Exit gate:**
- Unit test: `truncatePayload([...50000 numbers], "test.json")` returns in < 5ms and preview is valid JSON
- Unit test: `truncatePayload("a".repeat(200_000), "test.json")` preview ends at a valid character boundary
- `npx tsc --noEmit` passes

---

## WAVE 1 — Independent Foundations
*Start all of these simultaneously after Wave 0 gates pass.*

---

### Agent B1 — `discoveryStore.ts`

**Files to CREATE:**
- `src/frontend/stores/discoveryStore.ts`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (State Management section)
- `src/frontend/lib/discovery-types.ts` (Wave 0 output)
- `src/frontend/stores/chatStore.ts` (understand existing Zustand patterns)
- `src/frontend/stores/runStore.ts` (understand existing patterns)

**Files to NOT touch:** Everything else.

**Task:** Implement the Zustand store for the Epoch-based discovery state machine.

**Implementation requirements:**
- Use `zustand` with `immer` middleware (check existing stores for the pattern already used)
- `epochs` must be a `Map<string, Epoch>` — not an array
- `initializeSession()` creates the root Epoch (parentEpochId: null), sets `rootEpochId` and `activeEpochId`, returns the new epoch ID
- `forkEpoch()` deep-clones `targetParams` from parent, applies `paramOverrides`, creates a new Epoch with `currentStage = startStage ?? 2`, adds it to `epochs` Map, does NOT set `activeEpochId` (caller decides whether to switch)
- `switchToEpoch()` sets `activeEpochId`
- `activeEpoch` and `activeStageArtifact` are computed via Zustand `get()` — not stored as state
- All stage actions (`approveHit`, `rejectHit`, etc.) operate on the `activeEpochId` epoch — throw if `activeEpochId` is null
- Store must be persisted to `localStorage` (use Zustand persist middleware, key: `atlas-discovery-store`)

**Exit gate:**
- `initializeSession()` → `forkEpoch()` → `switchToEpoch()` sequence produces correct tree structure
- `activeEpoch` getter returns the correct epoch after `switchToEpoch()`
- Persisted to localStorage and rehydrates on reload
- `npx tsc --noEmit` passes

---

### Agent B2 — Backend: Initialize & Schema Endpoints

**Files to MODIFY:**
- `src/backend/app/api/routes.py`

**Files to CREATE:**
- `src/backend/app/services/discovery_session.py`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Backend Endpoints Required section, Component 1 types)
- `src/backend/app/api/routes.py` (understand existing route patterns)
- `src/backend/app/core/database.py` (understand models)
- `src/backend/app/services/` (understand existing service patterns)

**Files to NOT touch:** Frontend files, other backend services.

**Task:** Implement two endpoints.

**Endpoint 1: `GET /api/discovery/schema`**
- Returns a hardcoded (for now) `DomainSchema` for organic chemistry
- Response: `{ "domain": "organic_chemistry", "target_schema": ["biologicalTarget", "propertyConstraints", "forbiddenSubstructures"] }`
- Future: will read from a config file per project, but hardcode for now

**Endpoint 2: `POST /api/discovery/initialize`**
- Request body (Pydantic model): `ProjectTargetParams` — `domain`, `objective`, `propertyConstraints` (list), `domainSpecificConstraints` (dict), `corpusDocumentIds` (list of str)
- Stores the params in a new `DiscoverySession` row in SQLite (create the model in `database.py` or store as JSON in the Project table's metadata — use your judgment)
- Returns: `{ "session_id": "<uuid>", "epoch_id": "<uuid>", "status": "initialized" }`
- Validation: `corpusDocumentIds` must reference existing documents in the DB; return 422 if any are missing

**Exit gate:**
- `GET /api/discovery/schema` returns 200 with correct shape
- `POST /api/discovery/initialize` with valid body returns 200 with `session_id` and `epoch_id`
- `POST /api/discovery/initialize` with nonexistent `corpusDocumentIds` returns 422
- No existing routes are broken

---

### Agent B3 — Backend: Domain Render & Capability Gap Endpoints

**Files to MODIFY:**
- `src/backend/app/api/routes.py`

**Files to CREATE:**
- `src/backend/app/services/domain_tools.py`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 2 CandidateArtifact, Component 4 CapabilityGap, Backend Endpoints table)
- `src/backend/app/api/routes.py`

**Files to NOT touch:** Frontend files, other backend services.

**Task:** Implement three endpoints.

**Endpoint 1: `GET /api/domain/render`**
- Query params: `data` (URL-encoded string), `type` (one of: `molecule_2d`, `crystal_3d`, `polymer_chain`, `data_table`)
- For `molecule_2d`: attempt to render SMILES using RDKit (`from rdkit import Chem; from rdkit.Chem.Draw import rdMolDraw2D`). If RDKit not available, return a placeholder SVG with the SMILES text displayed.
- For other render types: return a placeholder SVG with the type and data preview labeled (full implementation deferred)
- Returns: `Content-Type: image/svg+xml` with the SVG string

**Endpoint 2: `POST /api/discovery/capability-gap`**
- Request body: `{ "run_id": str, "stage": int, "required_function": str, "input_schema": dict, "output_schema": dict, "standard_reference": str | None }`
- Stores the gap in SQLite (JSON column on the DiscoverySession, or a new `CapabilityGap` table — use judgment)
- Returns: `{ "gap_id": "<uuid>" }`

**Endpoint 3: `POST /api/tools/register`**
- Request body: `{ "gap_id": str, "method": "local_script" | "api_endpoint" | "plugin" | "skip", "config": dict }`
- Updates the CapabilityGap record with the resolution
- For `local_script`: validates that `config.path` exists on the filesystem
- For `api_endpoint`: validates that `config.url` is a valid URL
- Returns: `{ "status": "resolved", "gap_id": str }`

**Exit gate:**
- `GET /api/domain/render?data=CCO&type=molecule_2d` returns a valid SVG
- `POST /api/discovery/capability-gap` creates a record and returns a gap_id
- `POST /api/tools/register` with method=skip resolves the gap
- `npx tsc --noEmit` not applicable; run `python -m pytest tests/` and confirm no regressions

---

### Agent B4 — `ExecutionPipeline.tsx`

**Files to CREATE:**
- `src/frontend/components/ExecutionPipeline.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 3, Truncation & Blob Protocol)
- `src/frontend/lib/discovery-types.ts` (Wave 0 output)
- `src/frontend/lib/truncate-payload.ts` (Wave 0 output)
- `src/frontend/stores/runStore.ts` (the Run and ToolInvocation types)
- `src/frontend/components/AgentWorkbench.tsx` (understand existing telemetry UI patterns)
- `src/frontend/components/DiscoveryWorkbench.tsx` (understand existing telemetry UI patterns)

**Files to NOT touch:** Everything else.

**Task:** Build the always-visible right panel that renders the CI/CD-style pipeline trace.

**UI requirements:**
- Renders a list of stage nodes (GENERATE, SCREEN, SYNTHESIS_PLAN, etc.)
- Each node shows: stage name, elapsed time, status icon (running/complete/failed/pending)
- Each node is expandable: click to reveal tool invocations underneath
- Each tool invocation shows: tool name, input payload, output payload
- Input/output payloads are rendered via `truncatePayload()` — never raw. If `fullSizeBytes > PIPELINE_RENDER_LIMITS.maxStringBytes`, show preview + "Download" button
- "Download" button calls `downloadBlob()`
- Copy button on header copies run ID to clipboard
- "View full JSON log" button opens a `<dialog>` with the full serialized `Run.events` array (also truncated per limits)
- "Export run report" button downloads `run_<id>_report.json`
- Props: `run: Run | null` — if null, shows "No run selected" empty state

**Styling rules (from CLAUDE.md):** Use the project's existing CSS variables. No inline styles except for dynamic values. Follow the existing component styling patterns you see in `AgentWorkbench.tsx`.

**Exit gate:**
- Component renders without errors when passed a mock `Run` object with 10 tool invocations
- A mock tool invocation with a 100,000-element array output renders in < 16ms (use `performance.now()` in a test)
- Download button triggers a file download
- `npx tsc --noEmit` passes

---

### Agent B5 — `JobsQueue` Sidebar Component

**Files to CREATE:**
- `src/frontend/components/JobsQueue.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 8 JobsQueue)
- `src/frontend/lib/discovery-types.ts` (Wave 0 — BackgroundJob type)
- `src/frontend/stores/runStore.ts` (understand Run and BackgroundJob)
- `src/frontend/stores/discoveryStore.ts` (Wave 1 — backgroundJobs)
- `src/frontend/app/project/workspace-page.tsx` (understand where the sidebar lives)

**Files to NOT touch:** workspace-page.tsx (just read it), everything else.

**Task:** Build the Jobs queue sidebar widget.

**UI requirements:**
- Reads `backgroundJobs` from `discoveryStore`
- Each job row shows: job name/description, epoch ID it belongs to, elapsed time (live counting for running jobs), status dot (green=running, checkmark=done, red=error)
- Running jobs: elapsed time counts up in real-time using `useEffect` + `setInterval`
- Completed jobs: show result summary (e.g., "3 candidates survived")
- Failed jobs: show "see log" link that opens the `ExecutionPipeline` panel for that run
- "View all runs" link at the bottom (navigates to run history — just render a placeholder for now)
- Maximum 5 jobs visible before scrolling
- Component is `position: relative` — never `position: fixed` or modal

**Exit gate:**
- Component renders without errors with mock `BackgroundJob` data
- Running job elapsed time updates every second
- `npx tsc --noEmit` passes

---

### Agent B6 — Backend: Route Planning & Spectroscopy Validation Endpoints

**Files to MODIFY:**
- `src/backend/app/api/routes.py`

**Files to CREATE:**
- `src/backend/app/services/spectroscopy.py`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 5 SpectroscopyArtifact, Backend Endpoints table)
- `src/backend/app/api/routes.py`
- `src/backend/app/services/` (existing service patterns)

**Files to NOT touch:** Frontend files.

**Task:** Implement two endpoints.

**Endpoint 1: `POST /api/domain/route-planning` (SSE)**
- Request body: `{ "candidate_id": str, "smiles": str, "epoch_id": str }`
- For now: stream back a mock retrosynthesis tree as SSE events: `{ "type": "progress", "step": 1, "message": "Analyzing target molecule..." }` × 3 steps, then `{ "type": "complete", "result": { "routes": [{"steps": [], "score": 0.7}] } }`
- When AiZynthFinder is available, replace mock with real call (add a TODO comment)
- Use the same SSE streaming pattern as existing routes in `routes.py`

**Endpoint 2: `POST /api/domain/validate-spectroscopy`**
- Request body: `{ "hit_id": str, "file_content": str, "file_type": "jdx" | "csv" | "txt" }`
- For `.jdx`: parse JCAMP-DX format to extract peaks (implement a minimal parser: find `##XYDATA=` block, extract `(X++(Y..Y))` table)
- Compare observed peaks against predicted peaks (for now: predicted peaks are a stub — return them as `[]` with a TODO comment for when the NMR predictor is available)
- Return: `{ "verdict": "no_prediction_available", "observed_peaks": [...], "predicted_peaks": [], "matches": [], "missing": [] }`
- When NMR prediction is available, the verdict can be `"full_match"`, `"partial_match"`, or `"no_match"`

**Exit gate:**
- `POST /api/domain/route-planning` streams 4 SSE events and terminates cleanly
- `POST /api/domain/validate-spectroscopy` with a minimal valid `.jdx` string returns the response shape
- No existing routes broken

---

## WAVE 2 — Components
*Start all simultaneously after all Wave 1 agents pass their gates.*

---

### Agent C1 — `MissionControl.tsx`

**Files to CREATE:**
- `src/frontend/components/MissionControl.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 1)
- `src/frontend/lib/discovery-types.ts`
- `src/frontend/stores/discoveryStore.ts`
- `src/frontend/lib/api.ts` (to call `/api/discovery/initialize` and `/api/discovery/schema`)

**Files to NOT touch:** Everything else.

**Task:** Build the session initialization modal that appears when a project has no active discovery session.

**UI requirements:**
- Fetches `DomainSchema` from `/api/discovery/schema` on mount to populate field labels
- Domain selector dropdown (currently only `organic_chemistry` — but render it as a dropdown for future extensibility)
- Text input for "Target Objective"
- Dynamic property constraint builder: shows constraint chips (e.g., `MW < 500 Da`), "+ Add constraint" button opens an inline form with property name, operator, and value fields
- Domain-specific constraints textarea (free text, interpreted as key-value pairs)
- File upload area for corpus (drag-and-drop): calls existing document upload API, shows ingestion status per file
- "Initialize Discovery Session →" button: disabled until objective + at least 1 corpus doc is ingested; calls `POST /api/discovery/initialize`, then calls `discoveryStore.initializeSession()` with the returned params
- Error state: if initialization fails, show inline error with the backend error message

**Styling:** Follow CLAUDE.md guidelines. The modal should feel like a focused, high-stakes onboarding step — use generous spacing, clear labels, no decorative clutter.

**Exit gate:**
- Component renders without errors
- "Initialize" button is disabled with no objective text
- After successful mock API call, `discoveryStore.initializeSession()` is called
- `npx tsc --noEmit` passes

---

### Agent C2 — `CandidateArtifact.tsx`

**Files to CREATE:**
- `src/frontend/components/CandidateArtifact.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 2)
- `src/frontend/lib/discovery-types.ts`
- `src/frontend/stores/discoveryStore.ts`

**Files to NOT touch:** Everything else.

**Task:** Build the polymorphic candidate artifact card.

**UI requirements:**
- Accepts `hit: CandidateArtifact` as prop
- Header row: rank badge, score badge (color-coded: green > 0.8, yellow 0.5–0.8, red < 0.5), action buttons
- **"Approve → Synthesis Plan"** button: the primary CTA. Large, visually prominent. Calls `discoveryStore.approveHit(hit.id)` — which will trigger `forkEpoch()` in a later wiring step.
- "Reject" button: calls `discoveryStore.rejectHit(hit.id)`. Visually recessive.
- "Flag for Review" button: sets `hit.status = 'flagged'`
- Structure viewer area: renders based on `hit.renderType`:
  - `molecule_2d`: fetches SVG from `/api/domain/render?data=<smiles>&type=molecule_2d` and renders as `<img>`
  - Other render types: placeholder with type label (full implementation deferred)
- Properties table: each `PredictedProperty` row, with colored pass/warn/fail indicators based on `passesConstraint`
- Source reasoning: collapsible section, shows `hit.sourceReasoning` text
- Footer actions: "View in Graph", "Find Similar in Corpus", "Export Data"
- Rejected hits render with reduced opacity and a "Rejected" overlay — not removed from the grid

**Exit gate:**
- Renders correctly with mock `CandidateArtifact` data for each `renderType`
- SVG image loads from mock API endpoint
- Approve/Reject correctly call store actions
- `npx tsc --noEmit` passes

---

### Agent C3 — `CapabilityGapArtifact.tsx`

**Files to CREATE:**
- `src/frontend/components/CapabilityGapArtifact.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 4)
- `src/frontend/lib/discovery-types.ts`
- `src/frontend/stores/discoveryStore.ts`
- `src/frontend/lib/api.ts`

**Files to NOT touch:** Everything else.

**Task:** Build the pipeline halt artifact that appears when a required ML tool is missing.

**UI requirements:**
- Accepts `gap: CapabilityGap` as prop
- Header: "CAPABILITY GAP DETECTED" with run ID and stage label
- Function spec box: shows `requiredFunction`, `inputSchema`, `outputSchema`, `standardReference` in a monospace bordered box
- Four resolution options (A, B, C, D) as described in the plan:
  - **Option A (local script):** shows a file path input + "Browse" button
  - **Option B (API endpoint):** shows a URL input with basic URL validation
  - **Option C (plugin):** shows "Browse Registry" button (placeholder — not implemented yet, show a disabled button with "Coming soon" tooltip)
  - **Option D (skip):** always available. Shows a warning: "This property will show 'Not evaluated' on all candidate cards."
- "Confirm Resolution" button: disabled until a valid option is configured; calls `POST /api/tools/register` then `discoveryStore.resolveCapabilityGap(gap.id, resolution)`
- After resolution, component shows a "Resolved ✓" state with the chosen method

**Exit gate:**
- All four option UI paths render correctly
- Option D can always be submitted
- After mock API success, `resolveCapabilityGap` is called
- `npx tsc --noEmit` passes

---

### Agent C4 — `SpectroscopyArtifact.tsx`

**Files to CREATE:**
- `src/frontend/components/SpectroscopyArtifact.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 5)
- `src/frontend/lib/discovery-types.ts`
- `src/frontend/lib/api.ts`

**Files to NOT touch:** Everything else.

**Task:** Build the spectroscopy validation artifact.

**UI requirements:**
- Accepts `validation: SpectroscopyValidation` as prop (define `SpectroscopyValidation` in `discovery-types.ts` if not already there: `{ id, hitId, verdict: 'full_match'|'partial_match'|'no_match'|'no_prediction_available', observedPeaks: Peak[], predictedPeaks: Peak[], matches: PeakMatch[], missing: Peak[] }`)
- Spectrum chart: use a minimal SVG or `<canvas>` line chart. X-axis = chemical shift / frequency, Y-axis = intensity. Render observed peaks as solid bars, predicted peaks as outlined bars (overlaid). If `predictedPeaks` is empty, show only observed with a "No prediction available — upload will be processed when NMR predictor is configured" notice.
- Peak table: two columns (Predicted | Observed), each row is a peak. Match status icon on each row.
- Verdict box: color-coded (green=full, yellow=partial, red=no_match, gray=no_prediction). Human-readable verdict text.
- Footer: "Proceed to Stage 7", "Flag for re-evaluation", "Export validation report" buttons (Proceed calls `advanceToStage(7)` on the store)
- "Export" downloads a JSON file of the full validation object

**Exit gate:**
- Renders with mock `SpectroscopyValidation` with 4 peaks (3 matched, 1 missing)
- Chart renders without crashing
- Export downloads a file
- `npx tsc --noEmit` passes

---

### Agent C5 — `EntityHotspot` Component

**Files to CREATE:**
- `src/frontend/components/EntityHotspot.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 6)
- `src/frontend/lib/discovery-types.ts`
- `src/frontend/stores/discoveryStore.ts`

**Files to NOT touch:** Everything else. Do NOT touch the PDF viewer yet — that wiring happens in Wave 3.

**Task:** Build the entity hotspot component that wraps a detected entity string in a document.

**The component is a wrapper, not a detector.** The detection logic (running regex over PDF text) is a Wave 3 task. This agent builds the UI widget only.

**UI requirements:**
- `<EntityHotspot entity={string} entityType={'smiles'|'alloy'|'generic'} domain={DomainSchema}>` component
- Renders `children` with an underline style and a small icon (`⬡` for smiles, `⚙` for alloy/generic)
- On hover: shows a `<Tooltip>` that:
  - For `smiles`: shows a `<img>` fetched from `/api/domain/render?data=<smiles>&type=molecule_2d` (128×128)
  - For others: shows the raw entity string in a monospace box
- On click: shows a dropdown menu with the action list from the plan:
  - "Run Property Screen" → calls `discoveryStore.` (stub for now, logs to console — full wiring in Wave 3)
  - "Add to Candidate List" → stub
  - "Find Similar in Corpus" → stub
  - "Copy" → copies entity string to clipboard
- Dropdown must close on outside click and on Escape key

**Exit gate:**
- Renders in isolation with a test SMILES string
- SVG preview loads from mock API
- Copy button works
- Dropdown closes on outside click
- `npx tsc --noEmit` passes

---

### Agent C6 — Backend: Generate & Screen Endpoints

**Files to MODIFY:**
- `src/backend/app/api/routes.py`

**Files to CREATE:**
- `src/backend/app/services/candidate_generation.py`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Backend Endpoints table, Component 2 CandidateArtifact type)
- `src/backend/app/api/routes.py`
- `src/backend/app/services/swarm.py` (understand existing LangGraph/LLM patterns)
- `src/backend/app/services/retrieval.py`

**Files to NOT touch:** Frontend files.

**Task:** Implement two SSE endpoints for the core discovery pipeline.

**Endpoint 1: `POST /api/discovery/generate-candidates` (SSE)**
- Request body: `{ "session_id": str, "epoch_id": str }`
- Loads `ProjectTargetParams` from the session record
- Calls the LLM with a structured prompt: "Given the following research objective and corpus context, propose [N] candidate structures as SMILES strings..." (use existing retrieval service to get corpus context)
- Streams SSE events: `{ type: "progress", message: "..." }` during generation, then `{ type: "candidates", smiles: [...] }`, then `{ type: "complete" }`
- Stores the generated SMILES list in the session record

**Endpoint 2: `POST /api/discovery/screen` (SSE)**
- Request body: `{ "session_id": str, "epoch_id": str, "smiles_list": list[str] }`
- For each SMILES: run RDKit property calculations (MW, LogP, TPSA, HBD, HBA, RotBonds) — these are deterministic, no ML required
- Stream progress: `{ type: "screen_progress", smiles: "...", properties: {...}, passes_constraints: bool }`
- Apply `propertyConstraints` from `ProjectTargetParams` to filter
- Final event: `{ type: "complete", surviving_candidates: [CandidateArtifact, ...] }`
- Each `CandidateArtifact` in the output has `renderType: 'molecule_2d'`, `renderData: <smiles>`, and `properties` populated from RDKit calculations

**Exit gate:**
- Generate endpoint returns at least 1 mock candidate (can be hardcoded during development if LLM isn't available in test env — add `?mock=true` query param that returns hardcoded SMILES)
- Screen endpoint correctly filters based on MW constraint (test: `CCO` (ethanol, MW 46) must fail MW < 40 constraint)
- No existing routes broken

---

### Agent C7 — Epoch Navigator Component

**Files to CREATE:**
- `src/frontend/components/EpochNavigator.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Epoch Navigator UI section)
- `src/frontend/lib/discovery-types.ts`
- `src/frontend/stores/discoveryStore.ts`

**Files to NOT touch:** Everything else.

**Task:** Build the Stage header breadcrumb + epoch tree viewer.

**UI requirements (breadcrumb):**
- `<EpochBreadcrumb />`: reads `activeEpochId`, `epochs`, `activeEpoch` from `discoveryStore`
- Renders ancestry chain: `Epoch 0 (root) → Epoch 2 (Hit #3 approved) · Stage 6: Spectroscopy Validation`
- "← Back to parent" button: calls `switchToEpoch(activeEpoch.parentEpochId)`; hidden if on root epoch
- "View tree" button: opens the tree viewer

**UI requirements (tree viewer):**
- `<EpochTreeViewer />`: modal/dialog that renders the full epoch tree
- Simple indented list — not a graph, just a `<ul>/<li>` tree
- Each item shows: Epoch ID (short), fork reason, current stage, status (running/complete)
- Clicking an epoch calls `switchToEpoch(id)` and closes the dialog
- The active epoch is highlighted

**Exit gate:**
- Breadcrumb renders correctly with a 3-level epoch chain in mock store state
- Tree viewer opens and closes
- `switchToEpoch` is called on item click
- `npx tsc --noEmit` passes

---

## WAVE 3 — Wiring & Integration
*Start all simultaneously after all Wave 2 agents pass their gates.*

---

### Agent D1 — Workspace Layout Refactor

**Files to MODIFY:**
- `src/frontend/app/project/workspace-page.tsx`
- `src/frontend/components/DualAgentChat.tsx` (convert to slide-out panel)

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Architecture Overview)
- `docs/FrontendRedesignPlan.md` (understand current layout coupling)
- All Wave 1 and Wave 2 component files
- `src/frontend/app/project/workspace-page.tsx` (current layout)

**Task:** Restructure `workspace-page.tsx` from its current 5-tab layout to the 2-panel Stage + Pipeline layout.

**Layout target:**
```
[Left sidebar: FileSidebar + JobsQueue]
[Main Stage: scrollable artifact area]
[Right panel: ExecutionPipeline — always visible, fixed width ~320px]
[Bottom: CommandSurface — always visible]
[Floating: Chat slide-out (DualAgentChat, accessible via button)]
```

**Implementation steps:**
1. Add `<JobsQueue />` below `<FileSidebar />` in the left sidebar
2. Replace the 5-tab main area with a Stage container that renders `stageArtifact` from `discoveryStore`
3. Add `<ExecutionPipeline />` as a right panel — always mounted, reads `currentRun` from `runStore`
4. If `discoveryStore.activeEpoch === null`, render `<MissionControl />` in the Stage area
5. If `discoveryStore.activeEpoch !== null`, render the appropriate artifact based on `activeEpoch.currentStage`:
   - Stage 1: corpus viewer (existing PDF viewer component)
   - Stage 2/3: Jobs queue loading state
   - Stage 4: grid of `<CandidateArtifact />` cards from `activeEpoch.candidates`
   - Stage 5: synthesis plan tree (placeholder for now)
   - Stage 6: `<SpectroscopyArtifact />` or file upload prompt
   - Stage 7: knowledge graph view
6. Add `<EpochBreadcrumb />` to the Stage header
7. Convert `DualAgentChat` into a slide-out: add a "Chat" button somewhere accessible (top-right), clicking toggles a right-side drawer containing `DualAgentChat`

**Do NOT break:** Existing functionality of `DualAgentChat` — it just moves to a drawer. All modes (librarian, cortex, moe, discovery) must still work.

**Exit gate:**
- `MissionControl` renders when no active session
- Stage 4 renders `CandidateArtifact` cards when mock epoch has candidates
- `ExecutionPipeline` is visible at all times
- Chat slide-out opens and closes
- `npx tsc --noEmit` passes
- All existing chat modes still functional in the drawer

---

### Agent D2 — Cross-Store Bridge

**Files to MODIFY:**
- `src/frontend/hooks/useRunManager.ts`
- `src/frontend/lib/api.ts`
- `src/backend/app/api/routes.py`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Cross-Store Bridge section, full)
- `src/frontend/lib/discovery-types.ts` (`StageContextBundle`, `StageArtifactSummary`, `TruncatedToolInvocation`)
- `src/frontend/stores/discoveryStore.ts`
- `src/frontend/hooks/useRunManager.ts`
- `src/frontend/lib/api.ts`
- `src/backend/app/api/routes.py`

**Task:** Wire the automatic context injection from `discoveryStore` into every chat/swarm/moe/discovery backend request.

**Frontend changes (useRunManager.ts):**
- Add `getStageContext(): StageContextBundle` method that:
  1. Reads `discoveryStore.getState()` (Zustand outside React)
  2. Reads `runStore.getState()` for the last 10 tool invocations
  3. Returns a `StageContextBundle` (null fields if no active session)
  4. Truncates `inputPreview` and `outputPreview` to 500 chars

**Frontend changes (api.ts):**
- Every method that calls a backend AI endpoint (`chat()`, `streamSwarm()`, `streamMoE()`, `streamMoEHypotheses()`, `streamDiscovery()`) gains an optional `stageContext?: StageContextBundle | null` parameter
- When provided and non-null, adds `stage_context: stageContext` to the request body

**Backend changes (routes.py):**
- All chat/swarm/moe/discovery request Pydantic models gain an optional `stage_context: dict | None = None`
- When `stage_context` is present and non-null, prepend a system message to the LLM prompt:
  ```
  You are assisting a researcher who is currently viewing:
  - Stage {stage} ({stage_name}) of Epoch {epoch_id}
  - Target: {targetParams.objective}
  - Active artifact: {activeArtifact.label}
  [If focusedCandidate is present]:
  - Focused on Candidate (SMILES: {smiles}, score: {score})
  - Properties: {properties summary}
  - Recent tool invocations: {recentToolInvocations}
  Answer their question using this context and the project corpus.
  ```
- The prepended system message must be marked as non-user-visible in the response (do not include it in the returned message history)

**Exit gate:**
- With an active discovery session focused on a mock candidate, submitting a chat query includes `stage_context` in the request body (verify with network inspector or test)
- Backend correctly prepends the system message without breaking existing chat functionality
- With no active session, `stage_context` is null and requests are identical to pre-bridge behavior
- `npx tsc --noEmit` passes

---

### Agent D3 — `StructureCompletionSuggestion`

**Files to CREATE:**
- `src/frontend/components/StructureCompletionSuggestion.tsx`

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Component 7)
- `src/frontend/lib/discovery-types.ts`
- `src/frontend/stores/discoveryStore.ts`

**Files to NOT touch:** The actual Editor component — just build this as a standalone component. Wiring to editor is a separate task.

**Task:** Build the structural ghost text suggestion component.

**Implementation:**
- A hook `useStructureCompletion(editorText: string, cursorPosition: number)` that:
  - Returns `{ suggestion: string | null, isLoading: boolean }`
  - Debounces 2000ms before triggering
  - Only triggers if cursor is at a structural boundary (end of string, or cursor char is `\n` preceded by an empty line, or cursor is after a recognized heading pattern `^#{1,6} `)
  - Never triggers if cursor is mid-sentence (heuristic: char before cursor is not `.`, `\n`, `#`, or `:`)
  - Calls a new backend endpoint `POST /api/editor/suggest-structure` with `{ text: string, cursor_position: number, stage_context: StageContextBundle | null }`
- A `<StructureCompletionSuggestion suggestion={string}>` component that renders ghost text as a `<span>` with `color: var(--text-muted)` and `opacity: 0.5`
- The hook also handles Tab key acceptance (returns `onAccept: () => void` callback)

**For the backend endpoint** (add to `routes.py`):
- `POST /api/editor/suggest-structure`
- Request: `{ text: str, cursor_position: int, stage_context: dict | None }`
- Returns: `{ suggestion: str | None }` — where suggestion is ONLY one of:
  - A citation block: `[Insert: <filename>, p.<N> — <relevance>% relevance]`
  - A section header: `\n\n## <suggested section name>`
  - A data table placeholder: `[Insert: <table description>]`
  - `null` if no structural suggestion is appropriate
- The LLM prompt must explicitly forbid prose continuation in its system message

**Exit gate:**
- Hook does not trigger when cursor is mid-sentence (test with "The compound was syn|thesized")
- Hook triggers after 2s pause at structural boundary
- Suggestion is never a prose continuation — add a validation in the hook that rejects suggestions containing more than one sentence (heuristic: more than one `.` character)
- `npx tsc --noEmit` passes

---

### Agent D4 — Follow-Up Taxonomy Pills

**Files to MODIFY:**
- `src/frontend/components/chat/ConversationView.tsx`
- `src/backend/app/api/routes.py` (response schema addition)

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Follow-Up Taxonomy section)
- `src/frontend/lib/discovery-types.ts` (`FollowUpSuggestions`)
- `src/frontend/components/chat/ConversationView.tsx`
- `src/frontend/hooks/useRunManager.ts`

**Task:** Add the three-pill follow-up taxonomy to every AI response that completes a Golden Path stage.

**Backend changes:**
- For every endpoint that returns a complete AI response, add `follow_ups: FollowUpSuggestions | None` to the response schema
- The LLM generation prompt for these endpoints gains an appended instruction:
  ```
  After your response, output a JSON block on a new line:
  FOLLOW_UPS: {"depth": {"label": "...", "query": "..."}, "breadth": {"label": "...", "query": "..."}, "opposition": {"label": "...", "query": "..."}}
  ```
- Parse this block server-side, strip it from the visible response text, and return it as the `follow_ups` field

**Frontend changes (ConversationView.tsx):**
- After each assistant message that has `follow_ups` attached, render three pills:
  - `↓ <depth.label>` — muted blue
  - `↔ <breadth.label>` — muted teal
  - `✗ <opposition.label>` — muted amber
- Clicking a pill calls `useRunManager.submitQuery(suggestion.query)` — submits it as a new query
- Pills only appear on the last assistant message in a conversation (not on historical messages)
- Pills disappear once the next query is submitted

**Exit gate:**
- A mock response with `follow_ups` data renders three pills
- Clicking a pill submits the query
- Pills do not appear on historical messages
- If `follow_ups` is null, no pills render (graceful fallback)
- `npx tsc --noEmit` passes

---

### Agent D5 — Stage 7 Feedback Loop

**Files to CREATE:**
- `src/frontend/components/BioassayFeedbackForm.tsx`

**Files to MODIFY:**
- `src/backend/app/api/routes.py`
- `src/backend/app/services/graph.py` (add knowledge graph update method)

**Files to READ:**
- `docs/DiscoveryOS_GoldenPath_Plan.md` (Stage 7 FEEDBACK)
- `src/frontend/lib/discovery-types.ts`
- `src/frontend/stores/discoveryStore.ts`
- `src/backend/app/services/graph.py`
- `src/backend/app/core/database.py`

**Task:** Build Stage 7 — the bioassay result feedback form and the backend graph update endpoint.

**Frontend (`BioassayFeedbackForm.tsx`):**
- Renders in the Stage when `activeEpoch.currentStage === 7`
- Shows the approved candidate's structure (small `<CandidateArtifact>` in a condensed view)
- Form fields (generic, not chemistry-specific): Result Name (text), Result Value (number), Unit (text), Pass/Fail (toggle), Notes (textarea)
- "Submit Feedback" button: calls `POST /api/discovery/feedback`, then calls `discoveryStore.submitExperimentalResult(hitId, result)`
- After submit success: shows "Feedback recorded. Knowledge graph updated." + two action buttons:
  - "Run another generation cycle →" — calls `discoveryStore.forkEpoch(activeEpochId, "New cycle with updated graph", {}, 2)` then navigates to the new epoch
  - "View updated knowledge graph" — sets Stage to knowledge graph view

**Backend (`POST /api/discovery/feedback`):**
- Request body: `{ "hit_id": str, "epoch_id": str, "result_name": str, "result_value": float, "unit": str, "passed": bool, "notes": str }`
- Finds the `CandidateArtifact` (or the SMILES stored for that hit) and creates/updates a `Node` in the knowledge graph with the bioassay result as a property
- If the hit SMILES matches an existing node: update its properties
- If not: create a new node with `label = hit_id`, `properties = { smiles, result_name, result_value, passed }`
- Returns: `{ "status": "ok", "updated_node_ids": [str] }`

**Exit gate:**
- Form renders when `currentStage === 7`
- Submit calls backend and shows success state
- "Run another cycle" forks a new Epoch at Stage 2 and switches to it
- Backend creates/updates the graph node
- `npx tsc --noEmit` passes

---

## Summary Table

| Agent | Wave | Type | File(s) Created/Modified | Depends On |
|---|---|---|---|---|
| A0 | 0 | Frontend | `lib/discovery-types.ts` | — |
| A1 | 0 | Frontend | `lib/truncate-payload.ts` | — |
| B1 | 1 | Frontend | `stores/discoveryStore.ts` | A0 |
| B2 | 1 | Backend | `routes.py`, `services/discovery_session.py` | A0 |
| B3 | 1 | Backend | `routes.py`, `services/domain_tools.py` | A0 |
| B4 | 1 | Frontend | `components/ExecutionPipeline.tsx` | A0, A1 |
| B5 | 1 | Frontend | `components/JobsQueue.tsx` | A0, B1 |
| B6 | 1 | Backend | `routes.py`, `services/spectroscopy.py` | A0 |
| C1 | 2 | Frontend | `components/MissionControl.tsx` | B1, B2 |
| C2 | 2 | Frontend | `components/CandidateArtifact.tsx` | B1, B3 |
| C3 | 2 | Frontend | `components/CapabilityGapArtifact.tsx` | B1, B3 |
| C4 | 2 | Frontend | `components/SpectroscopyArtifact.tsx` | B6 |
| C5 | 2 | Frontend | `components/EntityHotspot.tsx` | B1, B3 |
| C6 | 2 | Backend | `routes.py`, `services/candidate_generation.py` | B2 |
| C7 | 2 | Frontend | `components/EpochNavigator.tsx` | B1 |
| D1 | 3 | Frontend | `workspace-page.tsx` | All Wave 2 |
| D2 | 3 | Full-stack | `useRunManager.ts`, `api.ts`, `routes.py` | B1, C6 |
| D3 | 3 | Full-stack | `components/StructureCompletionSuggestion.tsx`, `routes.py` | B1 |
| D4 | 3 | Full-stack | `ConversationView.tsx`, `routes.py` | A0 |
| D5 | 3 | Full-stack | `BioassayFeedbackForm.tsx`, `routes.py`, `graph.py` | B1, B2 |

---

## Gate Checklist

Before starting each wave, confirm:

**Wave 0 → Wave 1 gate:**
- [ ] `src/frontend/lib/discovery-types.ts` exports all required interfaces, `tsc --noEmit` passes
- [ ] `src/frontend/lib/truncate-payload.ts` passes unit tests for large array and long string cases

**Wave 1 → Wave 2 gate:**
- [ ] `discoveryStore.ts` — `initializeSession` → `forkEpoch` → `switchToEpoch` sequence works, persists to localStorage
- [ ] `GET /api/discovery/schema` returns 200
- [ ] `POST /api/discovery/initialize` returns `session_id` and `epoch_id`
- [ ] `GET /api/domain/render?data=CCO&type=molecule_2d` returns SVG
- [ ] `POST /api/discovery/capability-gap` + `POST /api/tools/register` both return 200
- [ ] `ExecutionPipeline.tsx` renders mock Run data, large payload truncates in < 16ms
- [ ] `JobsQueue.tsx` renders mock jobs, elapsed timer counts up
- [ ] `POST /api/domain/route-planning` streams 4 events, `POST /api/domain/validate-spectroscopy` returns correct shape

**Wave 2 → Wave 3 gate:**
- [ ] `MissionControl.tsx` — Initialize button disabled until valid, calls store on success
- [ ] `CandidateArtifact.tsx` — renders all render types, approve/reject call store
- [ ] `CapabilityGapArtifact.tsx` — Option D can always be submitted, resolves gap on submit
- [ ] `SpectroscopyArtifact.tsx` — renders chart and peak table, export works
- [ ] `EntityHotspot.tsx` — hover shows SVG preview, copy works, closes on outside click
- [ ] `POST /api/discovery/generate-candidates` returns at least 1 candidate (mock mode ok)
- [ ] `POST /api/discovery/screen` correctly filters by constraint
- [ ] `EpochNavigator.tsx` — breadcrumb and tree viewer render, `switchToEpoch` called on click

**Wave 3 done (Definition of Done check):**
- [ ] All 13 items in the plan's Definition of Done pass
