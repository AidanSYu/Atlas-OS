# Implementation Plan: Discovery OS — The Golden Path

**Version:** 3.1 | **Date:** February 2026
**Supersedes:** `synthetic-zooming-fern-agent-ae035cd.md` (Zero-Prompt Framework Research)
**Depends on:** `FrontendRedesignPlan.md` (Robustness Plan — assumed shipped)

**v3.1 patches** (three structural gaps identified in review):
1. **Truncation & Blob Protocol** — `ExecutionPipeline` never renders payloads > 64 KB into the DOM. Large arrays/blobs are truncated with download links.
2. **Branching Epoch Model** — `discoveryStore` replaces linear `currentStage` with a tree of `Epoch` objects. Researchers fork, branch, and run parallel Golden Path passes.
3. **Cross-Store Bridge** — Supplementary chat auto-bundles the active `stageArtifact` and `epochParams` as immediate LLM context so "this hit" always resolves correctly.

---

## Constraints This Plan Must Respect

Before any architecture decision: five hard constraints derived from critique of prior plans.

| Constraint | Rule |
|---|---|
| **No prose autocomplete** | Ghost text may only suggest structural elements (citation blocks, section headers, scaffold fragments) — never sentence continuations |
| **Async-first UX** | No multi-step pipeline may block the main stage. All workflows run in a background Jobs queue |
| **Strict attention budget** | Passive discovery surfaces (Feed, Graph Insights) are dashboard-only. They never overlay a document or interrupt the stage |
| **Zero-prompt for deterministic tools** | SMILES strings, .jdx files, and other typed artifacts trigger discrete UI hotspots automatically — no prompt required |
| **Hardcoded follow-up taxonomy** | Every AI response generates exactly three follow-up suggestions: one Depth, one Breadth, one Opposition |
| **Payload truncation in pipeline** | The Execution Pipeline never renders raw JSON payloads exceeding a byte threshold into the DOM. Large arrays/blobs are truncated with a download link |
| **Non-linear discovery state** | The Golden Path is not a linear state machine. A project is a tree of Epochs, each with its own parameters and stage position. Researchers can fork and branch |
| **Stage-aware chat context** | Any supplementary chat query automatically bundles the currently active `stageArtifact` and `epochParams` from `discoveryStore` as immediate LLM context |

---

## The Golden Path: 7 Stages of the Discovery Loop

This is the canonical workflow Atlas must execute. Every UI component exists to serve one or more of these stages.

```
Stage 1: PRIME          Mission Control modal → ingest corpus + set domain-specific target parameters
Stage 2: GENERATE       LLM synthesizes corpus → proposes candidate structures (e.g., SMILES, .cif)
Stage 3: SCREEN         Auto-route candidates through deterministic ML property predictors
Stage 4: SURFACE        Surviving "Best Hits" rendered as interactive Candidate Artifacts
Stage 5: SYNTHESIS_PLAN Researcher approves hit → triggers deterministic synthesis/manufacturing route planner
Stage 6: SPECTROSCOPY_VALIDATION Researcher uploads raw data (NMR, XRD) → deterministic validation check
Stage 7: FEEDBACK       Experimental assay results feed back into knowledge graph → primes Stage 2
```

The UI at any moment in a session is a reflection of which stage the project is currently in.

---

## Architecture Overview

### Primary Layout: The Stage + Pipeline

Replace the current 5-tab workspace (document / editor / graph / chat / canvas) with a **2-panel layout**:

```
+-------------------------------------------------------+---------------+
|                                                       |               |
|                   THE STAGE                           |   EXECUTION   |
|                                                       |   PIPELINE    |
|   Renders the current primary artifact:               |               |
|   - Candidate Artifact cards (Stage 4)                |  CI/CD-style  |
|   - Spectroscopy Validation chart (Stage 6)           |  trace panel  |
|   - Synthesis Plan tree (Stage 5)                     |               |
|   - Corpus PDF viewer (Stage 1)                       |  Shows JSON   |
|   - Knowledge graph (Stage 7)                         |  payloads +   |
|                                                       |  tool calls   |
+-------------------------------------------------------+               |
|  COMMAND SURFACE (CommandSurface.tsx, bottom-anchored)|               |
|  Unified input — always visible, context-aware        |               |
+-------------------------------------------------------+---------------+
```

**The Stage** is not a tab — it is the entire main area. The currently active artifact determines what the Stage renders. Multiple artifacts can coexist in a scrollable Stage stack (not tabs).

**The Execution Pipeline** is a persistent right panel showing the live CI/CD-style trace of whatever the current run is doing — or the last completed run if idle. This panel is the primary transparency mechanism. It is always visible, never hidden behind a toggle.

**Unified Chat Utility:** The previous distinct Chat interfaces (Librarian Cortex and MoE) are consolidated into a single supplementary Chat slide-out available as a "nice to have" utility. It exists to support ad-hoc RAG inquiries without disrupting the deterministic discovery pipeline.

**The Command Surface** replaces the primary chat interaction. It is context-aware: its placeholder and available actions change depending on which Stage of the Golden Path the project is in.

### Killed Components

The following concepts from the prior plan are explicitly killed:

- ~~"Smart Chat" as primary interface~~ — replaced by Stage + Command Surface (moved to secondary utility)
- ~~"Literature Review Workflow"~~ — not relevant to the Golden Path
- ~~"Ghost text for prose completion"~~ — replaced by structural scaffold suggestions only
- ~~"Research Feed" popping over documents~~ — sequestered to dashboard-only view
- ~~Generic "Upload a document" empty state~~ — replaced by Mission Control modal

---

## Component Specifications

### Component 1: `MissionControl.tsx` — Stage 1 (PRIME)

**When it appears:** On first project open, or when the Stage has no active artifacts.

**Purpose:** Replace the "blank page" entirely. Forces the researcher to specify the parameters that prime the LangGraph state before any LLM call is made. The fields in this screen are dynamically generated by the backend based on the active DomainSchema (e.g. chemistry, materials science) to ensure cross-domain extensibility.

**UX specification (Example: Chemistry Domain Active):**

```
+----------------------------------------------------------+
|  ATLAS  ·  New Discovery Session                         |
+----------------------------------------------------------+
|  Active Domain: [ Organic Chemistry ▼ ]                  |
|                                                          |
|  Define your target based on domain schema.              |
|                                                          |
|  Target Objective                                        |
|  [ EGFR kinase inhibition — ATP-competitive _________ ]  |
|                                                          |
|  Key Property Constraints (Target Schema Driven)         |
|  [ MW < 500 Da ] [ LogP 2–4 ] [ TPSA < 90 Å² ] [ + ]    |
|                                                          |
|  Domain-Specific Constraints (e.g. Forbidden Substructures)|
|  [ ________________________________________________________________ ] |
|                                                          |
|  Corpus                                                  |
|  [ Drag PDFs here or click to upload ]                   |
|  ┌──────────────────────────────────────────────────┐    |
|  │  📄 Chen_2023_EGFR.pdf          ✓ ingested        │    |
|  │  📄 WO2024112334_patent.pdf     ✓ ingested        │    |
|  └──────────────────────────────────────────────────┘    |
|                                                          |
|  [ Initialize Discovery Session → ]                      |
|                                                          |
+----------------------------------------------------------+
```

**State this produces (`ProjectTargetParams` & `DomainSchema`):**

```typescript
interface DomainSchema {
  domain: string; // e.g., 'organic_chemistry', 'materials_science'
  target_schema: string[]; // e.g., ['band_gap', 'crystal_structure'] or ['biologicalTarget', 'smarts']
}

interface ProjectTargetParams {
  domain: string;
  objective: string;
  propertyConstraints: PropertyConstraint[];
  domainSpecificConstraints: Record<string, any>; // e.g. { forbiddenSubstructures: [...], startingMaterialSmiles: "..." }
  corpusDocumentIds: string[];
}

interface PropertyConstraint {
  property: 'MW' | 'LogP' | 'TPSA' | 'HBD' | 'HBA' | 'RotBonds' | string;
  operator: '<' | '>' | '<=' | '>=' | 'between';
  value: number | [number, number];
}
```

This object is stored in the project record and passed as context in every subsequent LLM call. It is the replacement for "write a prompt."

---

### Component 2: `CandidateArtifact.tsx` (Polymorphic) — Stage 4 (SURFACE)

The primary output unit of the Golden Path. This is an interactive card that receives a generic payload and a `renderType` flag from the backend, making it domain-agnostic.

**Specification (Chemistry Render Example):**

```
+------------------------------------------------------------------+
|  HIT #3  ·  Score: 0.87  ·  [ Approve → Synthesis Plan ]        |
|                           ·  [ Reject ]  ·  [ Flag for Review ]  |
+------------------------------------------------------------------+
|                           |                                      |
|    [Domain specific render]  Predicted Properties               |
|    (e.g., 2D SVG, 3D Lattice, |                                      |
|     Polymer Chain view)       |  MW:        412.3 Da    ✓ < 500      |
|                           |  LogP:       3.1        ✓ 2–4        |
|                           |  TPSA:      74.2 Å²     ✓ < 90       |
|                           |  hERG IC₅₀: 8.2 μM      ⚠ borderline|
|                           |  Mutagenic:  No          ✓           |
|                           |                                      |
|                           |  Raw Data: [SMILES, .cif, etc.]      |
+------------------------------------------------------------------+
|  Source Reasoning:                                               |
|  "Scaffold derived from Chen_2023, Compound 7b. Modified at R3   |
|   to improve TPSA. No prior art found in patent corpus."         |
|                                                                  |
|  [ View in Graph ] [ Find Similar in Corpus ] [ Export Data ]   |
+------------------------------------------------------------------+
```

**Data type (`CandidateArtifact`):**

```typescript
interface CandidateArtifact {
  id: string;
  rank: number;
  score: number;
  renderType: 'molecule_2d' | 'crystal_3d' | 'polymer_chain' | 'data_table'; // UI component flag
  renderData: any; // e.g. SMILES string, .cif string, or raw JSON depending on renderType
  properties: PredictedProperty[];
  sourceReasoning: string;        // LLM explanation of provenance
  sourceDocumentIds: string[];
  status: 'pending' | 'approved' | 'rejected' | 'flagged';
  synthesisPlanRunId?: string;
}

interface PredictedProperty {
  name: string;
  value: number | string | boolean;
  unit?: string;
  passesConstraint: boolean | null;  // null = no constraint set
  model: string;                     // which ML model produced this
}
```

**Stage rendering:** Multiple `MolecularArtifact` cards are stacked in the Stage in a ranked grid (2 columns). The Stage header shows "7 candidates → 3 hits surviving screen."

**Interaction design:** "Approve → Retrosynthesis" is the single most important button in Stage 4. It must be the most visually prominent affordance on the card.

---

### Component 3: `ExecutionPipeline.tsx` — All Stages

The right panel. Always visible. Always shows the current or most recent run trace. This is the primary **scientific integrity** mechanism: researchers can verify exactly what JSON payloads were sent to deterministic models.

**Specification:**

```
EXECUTION PIPELINE                          [run #a4f2] [copy]
─────────────────────────────────────────────────────────────
▶ GENERATE                          2.3s    ✓ complete
  └─ llm_hit_generation
     Input:  { target: "EGFR...", constraints: [...] }
     Output: { smiles: ["CCc1ccc...", "COc1cc..."], count: 7 }

▶ SCREEN                            18.4s   ✓ complete
  └─ predict_mw         ✓  7/7 evaluated
  └─ predict_logp        ✓  7/7 evaluated
  └─ predict_tpsa        ✓  7/7 evaluated
  └─ predict_herg       ✓  7/7 evaluated
  └─ predict_mutagenic  ✓  7/7 evaluated
  └─ apply_constraints             3 passed / 7 total

▶ SYNTHESIS_PLAN                    [pending user approval]
  └─ planner_plugin (e.g. aizynthfinder)
     Waiting for researcher to approve a hit...

─────────────────────────────────────────────────────────────
[ View full JSON log ]  [ Export run report ]
```

Each stage node is **expandable** to show the raw JSON input and output. This is not a summary — it is the actual payload, formatted.

**Key design decision:** Tool calls that invoke deterministic models show both input and output. The researcher must be able to verify: "the LLM passed this exact SMILES string to the property predictor and received this exact value."

**Data source:** Fed directly from the `Run` object's `toolInvocations` array (as defined in `FrontendRedesignPlan.md`).

#### Truncation & Blob Protocol (DOM Crash Prevention)

Deterministic ML models in chemistry and materials science routinely produce massive payloads — a crystallography model can return a full `.cif` lattice array, an NMR simulator can return 50,000+ floats for a spectrum. Rendering these directly into a React component will freeze the browser and crash the tab.

**Hard rule:** The `ExecutionPipeline` component never renders any single JSON value exceeding **64 KB** (configurable) into the DOM tree.

**Truncation behavior by data shape:**

| Payload Shape | Threshold | Rendered As |
|---|---|---|
| JSON array with > 500 elements | 500 items | First 5 items + `[... 49,995 more items — Download full array (2.3 MB)]` |
| JSON string > 64 KB | 64 KB | First 200 chars + `[Truncated — Download full payload (847 KB)]` |
| Binary-encoded field (base64) | Any | `[Binary blob — 1.2 MB — Download]` (never decoded into DOM) |
| Nested object > 3 levels deep | 3 levels | Collapsed with `[Expand nested object]` lazy-load on click |

**Download mechanism:** Truncated payloads are stored as `Blob` objects in memory (not re-fetched from backend). Clicking "Download" triggers `URL.createObjectURL()` and a synthetic `<a>` click. The blob is released after download.

**Implementation type:**

```typescript
interface TruncatedPayload {
  preview: string;           // safe-to-render preview string
  fullSizeBytes: number;
  elementCount?: number;     // for arrays
  blob: Blob | null;         // lazy-created on first download request
  downloadFilename: string;  // e.g. "run_a4f2_predict_herg_output.json"
}

const PIPELINE_RENDER_LIMITS = {
  maxArrayElements: 500,
  maxStringBytes: 65_536,
  maxNestingDepth: 3,
} as const;
```

**Exit criteria for this protocol:**
- A tool invocation returning a 50,000-element float array renders in < 16ms (single frame).
- The downloadable blob contains the complete, untruncated payload.
- The preview is always valid JSON (not mid-string truncation) — arrays end with `]`, objects with `}`.

---

### Component 4: `CapabilityGapArtifact.tsx` — Missing Tool Protocol

**When it appears:** In the Stage, when the Execution Pipeline halts because the LLM requires a deterministic calculation that no registered tool can perform.

**The UX imperative:** The pipeline does not silently fail. It does not produce a hallucinated property. It pauses and surfaces a first-class artifact that communicates exactly what capability is missing.

**Specification:**

```
+------------------------------------------------------------------+
|  ⬡  CAPABILITY GAP DETECTED                                     |
|     Run #a4f2 is paused at stage: SCREEN                         |
+------------------------------------------------------------------+
|                                                                  |
|  To proceed with toxicity screening of the 7 hit candidates,    |
|  Atlas requires a model capable of:                              |
|                                                                  |
|  ┌────────────────────────────────────────────────────────────┐  |
|  │  FUNCTION:  Predict hERG channel inhibition (IC₅₀, μM)    │  |
|  │  INPUT:     SMILES string                                  │  |
|  │  OUTPUT:    Numeric IC₅₀ value + confidence interval       │  |
|  │  STANDARD:  ChEMBL hERG dataset compatible                 │  |
|  └────────────────────────────────────────────────────────────┘  |
|                                                                  |
|  How would you like to resolve this?                             |
|                                                                  |
|  [ A ]  Configure a local script                                 |
|         Point Atlas to a Python executable that accepts          |
|         SMILES via stdin and returns JSON                        |
|                                                                  |
|  [ B ]  Provide an API endpoint                                  |
|         Enter a REST endpoint URL that accepts                   |
|         { smiles: string } and returns { ic50: number }         |
|                                                                  |
|  [ C ]  Install a compatible plugin                              |
|         Browse the Atlas plugin registry for hERG predictors    |
|                                                                  |
|  [ D ]  Skip this screen and continue without hERG data          |
|         (Hit cards will show "hERG: Not evaluated")              |
|                                                                  |
+------------------------------------------------------------------+
```

**Data type (`CapabilityGap`):**

```typescript
interface CapabilityGap {
  id: string;
  runId: string;
  stage: GoldenPathStage;
  requiredFunction: string;
  inputSchema: Record<string, string>;
  outputSchema: Record<string, string>;
  standardReference?: string;
  resolution: CapabilityGapResolution | null;
}

interface CapabilityGapResolution {
  method: 'local_script' | 'api_endpoint' | 'plugin' | 'skip';
  config: Record<string, any>;  // method-specific config
}
```

**Persistence:** Resolved `CapabilityGap` objects are stored in the project. Once a researcher configures a local hERG predictor, that configuration is reused in every future run without prompting.

---

### Component 5: `SpectroscopyArtifact.tsx` (Polymorphic) — Stage 6 (SPECTROSCOPY_VALIDATION)

**When it appears:** After a researcher uploads a raw data file (e.g., NMR `.jdx`, XRD data) and the Stage is in Stage 6.

**Specification (NMR Example):**

```
+------------------------------------------------------------------+
|  SPECTROSCOPY VALIDATION  ·  Hit #3  ·  Run: #b9c1               |
+------------------------------------------------------------------+
|                                                                  |
|  [Interactive spectrum chart — plotted .jdx or raw data]        |
|  Peaks/Signals rendered with predicted vs. observed overlay      |
|                                                                  |
|  Predicted Signal                Observed Signal                |
|  ─────────────────────────       ────────────────────────────   |
|  Signal A (e.g., δ 7.42)         Observed A        ✓ match      |
|  Signal B                        Observed B        ✓ match      |
|  Signal C                        Observed C        ✓ match      |
|  Signal D                        NOT FOUND         ✗ missing    |
|                                                                  |
|  ┌──────────────────────────────────────────────────────────┐    |
|  │  VERDICT:  ⚠  PARTIAL MATCH                             │    |
|  │  3/4 predicted signals confirmed. Missing signal D.      │    |
|  │  Possible impurity or structural anomaly detected.       │    |
|  └──────────────────────────────────────────────────────────┘    |
|                                                                  |
|  [ Proceed to Stage 7: Feedback Loop ]                          |
|  [ Flag for re-evaluation/synthesis ]                            |
|  [ Export validation report ]                                    |
|                                                                  |
+------------------------------------------------------------------+
```

This artifact is produced by a **deterministic algorithm** (peak/signal matching against predicted data from the target schema). The LLM's role is only to generate the human-readable verdict text. The pass/fail determination is never delegated to the LLM.

---

### Component 6: `EntityHotspot` Registry (Domain-Agnostic) — Zero-Prompt Trigger

**When it appears:** Whenever the PDF viewer or any text surface detects an entity matching a domain's designated regex patterns or GLiNER entities (e.g., SMILES in chemistry, alloy nomenclatures like "Ti-6Al-4V" in materials science).

**Behavior (Chemistry SMILES Example):**
1. The recognized entity in the document receives an underline and an icon indicator.
2. On hover: a tooltip shows a domain-specific preview (e.g., 2D structure SVG).
3. On click: a dropdown with **one-click execution paths** driven by the active domain schema:

```
⬡  COc1cc(CC2SC(=O)NC2=O)ccc1O | OR | ⚙  Ti-6Al-4V

  [ Run Property Screen ]     → submits to Stage 3 pipeline
  [ Check Route / Phase Diagram ] → triggers synthesis/manufacturing tool
  [ Add to Candidate List ]   → creates a CandidateArtifact in Stage
  [ Find Similar in Corpus ]  → vector search for similar documents
  [ Copy Entity Data ]
```

**Implementation notes:**
- The backend configures what regex patterns to look for and what context menus to display based on the active domain. Detection runs once on document load.
- Previews are fetched from appropriate backend endpoints dependent on entity type.
- The one-click execution paths bypass all prompt input and directly spawn pipelines in the background.

---

### Component 7: `StructureCompletionSuggestion` — Stage-Aware Ghost Text

**IMPORTANT:** This is not prose completion. This is structure completion.

**What it suggests (allowed):**
- Citation blocks: `[Insert: Chen_2023_EGFR.pdf, p.4 — 78% relevance to current scaffold]`
- Molecular scaffold placeholders: `[R-group suggestion: fluorine at para position — improves metabolic stability]`
- Section headers: `[Insert: ## Selectivity Analysis]`
- Data table placeholders: `[Insert: property comparison table for Hits #1–3]`

**What it never suggests:**
- Continuations of scientific prose or arguments
- Interpretations of data
- Conclusions or claims

**Ghost text trigger:**
- Appears only when the user pauses typing in the Editor for > 2 seconds.
- Appears only when the cursor is at a structural boundary (end of a section, after a heading, after a SMILES string).
- Never appears mid-sentence.

---

### Component 8: `JobsQueue` — Async Background Execution

**The constraint:** A multi-step Golden Path pipeline on 4GB VRAM runs for minutes, not seconds. The main Stage must never be blocked by a running pipeline.

**UX specification:**

When a researcher launches any workflow (hit generation + screening, retrosynthesis, NMR validation), it is immediately moved to a background job:

```
┌─────────────────────────────────────────────────────┐
│  JOBS                                               │
│                                                     │
│  ● EGFR Hit Generation + Screen     [3:42]  running │
│  ✓ Retrosynthesis — Hit #1          [done]  2 paths  │
│  ✗ NMR Validation — Hit #2          [error] see log  │
│                                                     │
│  [ View all runs ]                                  │
└─────────────────────────────────────────────────────┘
```

This panel lives in the **left sidebar**, below the file list. It is **never modal** and never interrupts the Stage.

**Notification contract:**
- When a job completes, a **non-modal toast** appears in the bottom-right corner: "Hit screen complete — 3 candidates survived. [View results]"
- Clicking the toast switches the Stage to show the new `MolecularArtifact` cards.
- If the researcher is mid-scroll in a PDF, the PDF remains open. The toast does not close it.

---

## Follow-Up Taxonomy (Hardcoded)

Every AI response that concludes a stage of the Golden Path generates exactly three follow-up suggestions. The categories are hardcoded — not LLM-generated — to prevent semantic loops.

| Category | Icon | Example after Stage 4 (SURFACE) |
|---|---|---|
| **Depth** | `↓` | "Drill into the hERG binding mode of Hit #3 — show me the docking pose reasoning" |
| **Breadth** | `↔` | "Are there any structurally similar compounds in the corpus that were previously deprioritized?" |
| **Opposition** | `✗` | "Search for evidence that this scaffold class has shown in-vivo toxicity issues" |

The LLM fills in the specific content (compound names, document references), but the framework (one of each type, in this order) is enforced by the frontend before the response renders.

**Data type:**
```typescript
interface FollowUpSuggestions {
  depth: { label: string; query: string };
  breadth: { label: string; query: string };
  opposition: { label: string; query: string };
}
```

These are included in the backend response schema and rendered as three styled pill buttons below every Stage-completing response.

---

## State Management: `discoveryStore.ts`

A new Zustand store dedicated to Golden Path state. This is separate from `chatStore` and `runStore`.

### The Branching Epoch Model

Research is not linear. A researcher may reach Stage 4, reject all candidates, tweak constraints, and re-run generation. They may approve two different hits and run parallel retrosynthesis routes. The state model must support this without destroying history.

**Core concept: An Epoch is a single pass through some portion of the Golden Path with a specific set of parameters.** A project is a tree of Epochs, not a single linear progression.

```
Project
 └─ Epoch 0 (root)          params: { target: "EGFR", MW < 500, LogP 2–4 }
     ├─ Stage 1 ✓  Stage 2 ✓  Stage 3 ✓  Stage 4: 3 hits
     │
     ├─ Epoch 1 (fork: modified constraints)   params: { ...root, MW < 400 }
     │   └─ Stage 2 ✓  Stage 3 ✓  Stage 4: 5 hits
     │       └─ Epoch 3 (fork: Hit #2 approved)
     │           └─ Stage 5 running...
     │
     └─ Epoch 2 (fork: Hit #3 approved from Epoch 0)
         └─ Stage 5 ✓  Stage 6: awaiting .jdx upload
```

**Branching triggers:**
- Researcher clicks "Re-generate with modified constraints" from Stage 4 → forks a new Epoch with updated `targetParams`, starting at Stage 2.
- Researcher approves a hit for retrosynthesis → forks a new child Epoch for that hit, starting at Stage 5.
- Researcher submits Stage 7 feedback and clicks "Run another generation cycle" → forks from the current Epoch back to Stage 2 with the enriched knowledge graph.

The researcher can switch between Epochs freely. The Stage renders whatever Epoch is currently active. Historical Epochs are read-only and browsable.

```typescript
interface Epoch {
  id: string;                          // crypto.randomUUID()
  parentEpochId: string | null;        // null for root
  forkReason: string;                  // human-readable: "Modified constraints: MW < 400"
  targetParams: ProjectTargetParams;   // snapshot — may differ from parent
  currentStage: GoldenPathStage;
  createdAt: number;

  // Artifact collections scoped to this epoch
  candidates: CandidateArtifact[];
  capabilityGaps: CapabilityGap[];
  validations: SpectroscopyValidation[];
  feedbackResults: BioassayResult[];

  // Run IDs for each stage executed in this epoch
  stageRuns: Partial<Record<GoldenPathStage, string>>;
}

interface DiscoveryStore {
  // Epoch tree
  epochs: Map<string, Epoch>;          // all epochs for this project
  activeEpochId: string | null;        // currently displayed epoch
  rootEpochId: string | null;

  // Derived from active epoch (convenience getters)
  activeEpoch: Epoch | null;           // computed
  activeStageArtifact: StageArtifact | null;

  // Jobs (global, not per-epoch — a job references its epoch ID)
  backgroundJobs: BackgroundJob[];

  // Epoch actions
  initializeSession: (params: ProjectTargetParams) => string;  // returns root epoch ID
  forkEpoch: (parentEpochId: string, reason: string, paramOverrides?: Partial<ProjectTargetParams>, startStage?: GoldenPathStage) => string;
  switchToEpoch: (epochId: string) => void;

  // Stage actions (operate on active epoch)
  approveHit: (hitId: string) => void;
  rejectHit: (hitId: string) => void;
  resolveCapabilityGap: (gapId: string, resolution: CapabilityGapResolution) => void;
  advanceToStage: (stage: GoldenPathStage) => void;
  submitRawDataFile: (hitId: string, reportFile: File) => void;
  submitExperimentalResult: (hitId: string, result: BioassayResult) => void;
}

type GoldenPathStage = 1 | 2 | 3 | 4 | 5 | 6 | 7;

type StageArtifact =
  | { type: 'corpus_viewer'; documentId: string }
  | { type: 'hit_grid'; hits: CandidateArtifact[] }
  | { type: 'synthesis_plan_tree'; hitId: string; runId: string }
  | { type: 'spectroscopy_validation'; hitId: string; validationId: string }
  | { type: 'knowledge_graph'; projectId: string }
  | { type: 'capability_gap'; gap: CapabilityGap };
```

### Epoch Navigator UI

The Stage header gains a breadcrumb that shows the current position in the Epoch tree:

```
Epoch 0 (root)  →  Epoch 2 (Hit #3 approved)  ·  Stage 6: Spectroscopy Validation
                                                   [ ← Back to parent ]  [ View tree ]
```

"View tree" opens a compact tree visualization (not a full graph view — a simple indented list) showing all Epochs, their fork reasons, and their current stage. Clicking any Epoch switches the Stage to render that Epoch's artifacts.

**Constraint:** Forking an Epoch is always a cheap, fast operation (snapshot `targetParams` + create new empty artifact collections). The expensive work (running Stage 2, Stage 3) happens asynchronously in the Jobs queue after the fork is created.

---

## Cross-Store Bridge: Chat ↔ Discovery Context

### The Problem

A researcher is looking at Hit #3 on the Stage. They open the supplementary chat and ask: "Why did this hit fail the hERG screen?" If the chat backend only receives the query string and the standard SQLite vector store, it has no idea what "this hit" refers to. It will hallucinate or produce a generic answer about hERG screening.

### The Solution

When a query is submitted from the supplementary Chat (or the Command Surface), the `chatStore` must read the current `discoveryStore` state and bundle it as **immediate context** in the backend request payload. The LLM receives the researcher's screen state, not just their words.

### Context Bundle Specification

```typescript
interface StageContextBundle {
  activeEpochId: string | null;
  activeStage: GoldenPathStage | null;
  targetParams: ProjectTargetParams | null;

  // The artifact currently rendered on the Stage
  activeArtifact: StageArtifactSummary | null;

  // If viewing a specific candidate, include its full data
  focusedCandidateId: string | null;
  focusedCandidate: CandidateArtifact | null;

  // Recent pipeline trace (last 10 tool invocations, truncated payloads)
  recentToolInvocations: TruncatedToolInvocation[];
}

interface TruncatedToolInvocation {
  tool: string;
  inputPreview: string;    // first 500 chars of JSON input
  outputPreview: string;   // first 500 chars of JSON output
  status: 'completed' | 'failed';
}

interface StageArtifactSummary {
  type: StageArtifact['type'];
  label: string;            // e.g. "Hit Grid — 3 candidates from Epoch 2"
  candidateCount?: number;
  validationVerdict?: string;
}
```

### How It Wires

1. **`useRunManager` hook** (from `FrontendRedesignPlan.md`) gains a `getStageContext()` method that reads from `discoveryStore` and assembles a `StageContextBundle`.

2. **Every backend request** (`/api/chat`, `/api/swarm`, `/api/moe`, `/api/discovery`) gains an optional `stage_context` field in the request body:

```typescript
// In api.ts, the chat/swarm/moe methods add:
{
  query: "Why did this hit fail the hERG screen?",
  project_id: "...",
  stage_context: getStageContext()  // auto-bundled, not user-authored
}
```

3. **Backend prompt construction** prepends the stage context as a system message:

```
You are assisting a researcher who is currently viewing:
- Stage 4 (SURFACE) of Epoch 2
- Target: EGFR kinase inhibition, MW < 400
- Focused on Candidate Hit #3 (SMILES: CCc1ccc...)
- Hit #3 properties: MW 412.3, LogP 3.1, hERG IC₅₀ 8.2 μM (borderline)
- The hERG screen was executed by tool 'predict_herg' in run #a4f2

Answer their question using this context and the project corpus.
```

### What Does NOT Cross the Bridge

- Full raw payloads from tool invocations (these are truncated to 500 chars in the bundle — if the LLM needs the full payload, it can reference the run ID and the backend can look it up).
- Epoch tree structure (the chat doesn't need to know about sibling epochs, only the active one).
- Background jobs from other epochs.

### Exit Criteria

- A researcher viewing Hit #3 on Stage asks "Why did this fail hERG?" in the chat. The LLM response references Hit #3's specific SMILES string, its predicted hERG IC₅₀ value, and the tool that produced the prediction — without the researcher specifying any of this in the prompt.
- The `stage_context` field adds < 2 KB to the request payload.
- If `discoveryStore` is empty (no active session), the `stage_context` field is `null` and chat behaves exactly as it does today.

---

## Backend Endpoints Required

These are new or modified endpoints needed to serve the Golden Path UI. Add to `src/backend/app/api/routes.py`.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/discovery/schema` | GET | Returns the active `DomainSchema` (e.g., chemistry, materials) |
| `/api/discovery/initialize` | POST | Accept `ProjectTargetParams`, prime LangGraph state, return session ID |
| `/api/discovery/generate-candidates` | POST (SSE) | Run LLM hit generation → returns stream of proposed structure strings |
| `/api/discovery/screen` | POST (SSE) | Accept candidate list → run deterministic screens → return `CandidateArtifact[]` |
| `/api/domain/render` | GET | `?data=<encoded>&type=<renderType>` → return generic rendered visual (SVG, WebGL, etc.) |
| `/api/domain/route-planning` | POST (SSE) | Accept candidate → run domain-specific route planner (e.g. AiZynthFinder) → stream tree |
| `/api/domain/validate-spectroscopy` | POST | Accept `{ hitId, fileContent, fileType }` → return spectral validation |
| `/api/discovery/feedback` | POST | Accept `BioassayResult` → update knowledge graph, return updated node IDs |
| `/api/discovery/capability-gap` | POST | LLM reports a missing tool → creates `CapabilityGap` record |
| `/api/tools/register` | POST | Researcher provides tool config → validates and stores it |

---

## Attention Budget: What Lives Where

This enforces the constraint that passive discovery surfaces never interrupt focused work.

| Surface | Location | Trigger | Can interrupt Stage? |
|---|---|---|---|
| Candidate Artifact cards | Stage (main area) | Job completion → toast → user click | No |
| Capability Gap Artifact | Stage (replaces content) | Pipeline halt | No (user must click toast first) |
| Spectroscopy Validation Artifact | Stage (main area) | User submits raw data file | No |
| Entity Hotspot | Inline in text | Auto-detected per schema | No (hover-only, no modal) |
| Structure scaffold suggestions | Editor, on pause | 2s typing pause at structural boundary | No |
| Execution Pipeline trace | Right panel (always visible) | Always present | No |
| Jobs Queue | Left sidebar | Always present | No |
| Follow-up taxonomy pills | Below AI response | After run completes | No |
| Knowledge graph insights | Dashboard view only | User navigates to dashboard | Never |
| New connection notifications | Toast (bottom-right) | Background graph update | Toast only, dismissable |

---

## Rollout Sequence

### Phase 1: Foundation

**Deliverables:**
- `MissionControl.tsx` — replace blank empty state
- `discoveryStore.ts` — Epoch-based state machine with branching support
- `Epoch` type, `ProjectTargetParams` type + `/api/discovery/initialize` endpoint
- `ExecutionPipeline.tsx` right panel with **Truncation & Blob Protocol** (read-only, fed from existing `Run` events)
- `TruncatedPayload` utility + `PIPELINE_RENDER_LIMITS` constants
- `JobsQueue` sidebar widget (jobs fed from existing `runStore`)
- Epoch Navigator breadcrumb in Stage header

**Exit gate:**
- A researcher can open a new project, complete Mission Control, and the root Epoch is created with target parameters persisted.
- The Execution Pipeline panel shows the last run's tool calls. A tool invocation returning a 50,000-element array renders in < 16ms with a download link for the full payload.
- Jobs queue shows running/completed jobs without blocking the stage.
- Epoch breadcrumb shows "Epoch 0 (root) · Stage 1".

### Phase 2: Hit Generation + Screening + Epoch Forking

**Deliverables:**
- `CandidateArtifact.tsx` polymorphic card component
- `/api/domain/render` generic endpoint
- `/api/discovery/generate-candidates` + `/api/discovery/screen` endpoints
- `CapabilityGapArtifact.tsx` — pipeline halt UX
- `/api/discovery/capability-gap` + `/api/tools/register` endpoints
- "Re-generate with modified constraints" action on Stage 4 → triggers `forkEpoch()`
- Epoch tree viewer (compact indented list)

**Exit gate:**
- Full Stage 2→3→4 flow runs end-to-end within a single Epoch.
- Property screen results populate `CandidateArtifact.properties` with validation flags.
- When a required ML model is absent, pipeline halts and `CapabilityGapArtifact` renders in Stage.
- Researcher can resolve gap via Option D (skip) and pipeline continues.
- Researcher can reject all hits, modify constraints, and fork a new Epoch. The original Epoch's candidates remain browsable. The new Epoch runs Stage 2 independently in the Jobs queue.

### Phase 3: Route Planning + Spectroscopy Validation + Parallel Epochs

**Deliverables:**
- "Approve → Synthesis Plan" button on `CandidateArtifact` — triggers `forkEpoch()` for each approved hit (parallel retrosynthesis Epochs)
- `/api/domain/route-planning` endpoint wired to domain-specific tools (e.g. AiZynthFinder)
- Planning tree renderer in Stage
- Raw data file upload in `CommandSurface` when stage is 6
- `SpectroscopyArtifact.tsx` with predicted vs. observed table
- `/api/domain/validate-spectroscopy` deterministic signal-matching endpoint

**Exit gate:**
- Stage 5→6 flow runs end-to-end on a test case with known raw data.
- Validation pass/fail determination is produced by deterministic algorithms based on schema, not LLM.
- Verdict text is LLM-generated but clearly labeled as "interpretation" distinct from the pass/fail result.
- Approving two hits from the same Epoch creates two parallel child Epochs, each running Stage 5 independently. The researcher can switch between them via the Epoch Navigator.

### Phase 4: Feedback Loop + Cross-Store Bridge + Zero-Prompt Polish

**Deliverables:**
- Generic experimental assay input form (Stage 7)
- `/api/discovery/feedback` endpoint — updates knowledge graph nodes
- Stage 7 "Run another generation cycle" action → `forkEpoch()` back to Stage 2 with enriched graph
- `EntityHotspot` component wired to backend schema configs
- Follow-up taxonomy pills in `ConversationView`
- `StructureCompletionSuggestion` ghost text (structural triggers only)
- Dashboard view: knowledge graph with Stage 7 feedback visualized
- Consolidate existing Chat tools (Librarian Cortex/MoE) into a unified supplementary Chat Utility sidebar
- **Cross-Store Bridge**: `getStageContext()` method on `useRunManager`, `StageContextBundle` type, `stage_context` field on all backend chat/swarm/moe/discovery request payloads

**Exit gate:**
- Stage 7 feedback updates the knowledge graph and the updated node is visible in the graph view.
- Stage 7 → "Run another cycle" forks a new Epoch at Stage 2 with the same target params but enriched graph context.
- Entities defined by domain schema in uploaded corpus documents are automatically detected and show corresponding hotspot icons.
- Supplementary chat interface is accessible from anywhere but does not disrupt the Golden Path stage.
- A researcher viewing Hit #3 on Stage asks "Why did this fail hERG?" in the supplementary chat. The LLM references Hit #3's SMILES, predicted IC₅₀, and the producing tool — without the researcher specifying any of this.
- If `discoveryStore` has no active session, chat behaves identically to its pre-bridge behavior.
- Every AI response shows exactly three follow-up pills (Depth / Breadth / Opposition).

---

## Definition of Done

This plan is complete when:

1. A researcher can initialize a session via Mission Control and never encounter a blank page.
2. The Golden Path executes end-to-end (Stages 1–7) with no stage blocking the main Stage area.
3. Every deterministic ML model call is visible in the Execution Pipeline with its raw JSON input/output. **Payloads exceeding 64 KB are truncated in the DOM with a downloadable blob link. A 50,000-element array renders in < 16ms.**
4. A missing ML model capability halts the pipeline and surfaces a `CapabilityGapArtifact` — never a hallucinated value.
5. Spectroscopy validation pass/fail is produced by deterministic signal-matching, not LLM inference.
6. Domain-specific entities (SMILES, alloy designations, etc.) in corpus documents are automatically detected with zero user action.
7. No AI-generated prose appears in a researcher's deliverable without explicit researcher authorship.
8. The Stage is never blocked by a running pipeline — all long workflows run in the Jobs queue.
9. Every AI response presents exactly three follow-up options: Depth, Breadth, Opposition.
10. All passive discovery surfaces (graph insights, new connection alerts) are sequestered to the dashboard and can never overlay a document or interrupt the stage.
11. **A researcher can reject all Stage 4 candidates, modify constraints, and fork a new Epoch. Both the original and new Epoch are browsable. The new Epoch runs independently in the Jobs queue.**
12. **A researcher can approve multiple hits from the same Epoch and run parallel retrosynthesis routes as separate child Epochs, switching between them via the Epoch Navigator.**
13. **A researcher viewing a specific artifact on the Stage can open the supplementary chat, ask a question referencing "this" artifact, and receive an answer grounded in that artifact's data — without specifying the artifact in the prompt. If no discovery session is active, chat is unaffected.**
