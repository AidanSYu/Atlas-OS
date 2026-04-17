# Prometheus Implementation Plan

**Last updated:** 2026-04-16
**Status:** Approved for implementation, Phase 0 ready to start
**Owner:** Aidan (human) + delegated agents per phase

---

## 0. How to use this document

This plan is written to be executed by agents across multiple sessions. Each phase is self-contained enough that a fresh agent can pick it up with only (a) this document, (b) the CLAUDE.md at repo root, and (c) the listed files to read first.

**Execution convention per phase:**
1. Read the phase's "Files to read first" list to load context
2. Verify dependencies are done (see "Depends on")
3. Make the listed changes; create the listed new files
4. Run "Verification" to confirm the phase is actually complete — not just "code compiles"
5. Update the phase status table at the bottom of this doc

**Agent recommendations:**
- Plan-sensitive changes (contracts, doctrine): Opus, human review before merge
- Straight implementation from spec (new plugin wrappers, UI components): Sonnet acceptable
- Research/exploration tasks: Explore agent subtype
- Training runs (Phase 9): external cluster, not Claude Code

---

## 1. Vision recap

Prometheus is the plugin suite for manufacturing-focused product built on Atlas — an offline-first, air-gapped research and manufacturing OS powered by a local NVIDIA Orchestrator-8B (IQ2_M GGUF) natively integrated with a Rustworkx knowledge graph + SQLite + Qdrant substrate.

The product is positioned for Luxshare-style factory floor deployment: runs on a standard workstation, no cloud dependencies, understands the causal chain of manufacturing processes, and generates ISO-compliant audit trails from deterministic graph walks. 

**What Atlas actually is:** a programmable hypothesis-filter pipeline. The orchestrator does not "do research"; it routes candidates (from DL models, user queries, sensor anomalies) through plugin chains that aggressively winnow hypotheses before any human or lab resource is committed. Think of it as a domain agnostic framework.

---

## 2. Design principles (north stars)

- **Native-first** — the local NV Orchestrator-8B is the only guaranteed path. API models (Claude, DeepSeek, OpenAI) are an optional layer *above* ToolOrchestra, user-invoked, not silent fallback
- **Hypothesis-until-verified** — every machine-generated output is a candidate. States: `unverified` → `in_silico_verified` (passed a filter chain) → `human_verified` → `lab_verified` (future physical robot loop)
- **Filter-first orchestration** — the orchestrator's job is to route candidates through appropriate filters, *dynamically at runtime*. No hard-coded DAGs (that's LangGraph's failure mode). Filter chains are authored by the orchestrator itself based on hypothesis type
- **Novelty-before-work** — query KG + literature *before* spending compute. Surfaces prior art so we don't reinvent what a postdoc did in 2014
- **Graduated trust** — session → project → global memory tiers. Promotion requires filter-chain pass + novelty check + user confirm. Evidence-based, not frequency-based
- **Traceable both directions** — research provenance ("how was this discovered?") and manufacturing provenance ("why did this batch fail?") use the same Rustworkx edges
- **Self-improving** — every user edit, approval, rejection, and promotion decision becomes training signal for eventual custom orchestrator fine-tuning

---

## 3. Prometheus component status (as of 2026-04-16)

| # | Vision component | Plugin path | Status | Phase |
|---|---|---|---|---|
| C1 | Small Manufacturing World Model (Chronos/TTM/MOMENT timeseries) | [src/backend/plugins/prometheus/manufacturing_world_model/](src/backend/plugins/prometheus/manufacturing_world_model/) | Working | Verify in 2a |
| C2 | Causal Discovery Engine (PCMCI+ + PySR) | [src/backend/plugins/prometheus/causal_discovery/](src/backend/plugins/prometheus/causal_discovery/) | Working | Verify in 2a |
| C3 | Physics-Accelerated Simulators (PINN surrogates) | [src/backend/plugins/prometheus/physics_simulator/](src/backend/plugins/prometheus/physics_simulator/) | Stub — manifest only | Build in 2b |
| C4 | Autonomous Sandbox Lab (BoTorch BO) | [src/backend/plugins/prometheus/sandbox_lab/](src/backend/plugins/prometheus/sandbox_lab/) | Working | Verify in 2a |
| C5 | Offline Vision Inspector (Qwen2-VL) | [src/backend/plugins/prometheus/vision_inspector/](src/backend/plugins/prometheus/vision_inspector/) | Stub | Build in 2c |
| C6 | Autonomous Traceability & Compliance (subgraph + synthesis) | [src/backend/plugins/prometheus/traceability_compliance/](src/backend/plugins/prometheus/traceability_compliance/) | Stub | Build in 2d |

---

## 4. Repo map (for agent orientation)

**Backend — always start here:**
- [src/backend/app/main.py](src/backend/app/main.py) — FastAPI app entry, router registration
- [src/backend/app/core/config.py](src/backend/app/core/config.py) — `Settings` class, env-var backed
- [src/backend/app/atlas_plugin_system/orchestrator.py](src/backend/app/atlas_plugin_system/orchestrator.py) — `AtlasOrchestratorService`, main loop at line 190
- [src/backend/app/atlas_plugin_system/catalog.py](src/backend/app/atlas_plugin_system/catalog.py) — `ToolCatalog` merging core + plugins
- [src/backend/app/atlas_plugin_system/core_tools.py](src/backend/app/atlas_plugin_system/core_tools.py) — `CoreToolRegistry` and always-on tool classes
- [src/backend/app/atlas_plugin_system/registry.py](src/backend/app/atlas_plugin_system/registry.py) — `PluginRegistry`, `PluginManifest`
- [src/backend/app/atlas_plugin_system/atlas_runtime.py](src/backend/app/atlas_plugin_system/atlas_runtime.py) — runtime preflight + plugin proof invocation
- [src/backend/app/api/framework_routes.py](src/backend/app/api/framework_routes.py) — `/api/framework/*` endpoints
- [src/backend/app/services/retrieval.py](src/backend/app/services/retrieval.py) — hybrid RAG (Qdrant + Rustworkx)
- [src/backend/app/services/graph.py](src/backend/app/services/graph.py) — `GraphService` over Rustworkx
- [src/backend/plugins/prometheus/](src/backend/plugins/prometheus/) — the six manufacturing plugins

**Frontend:**
- [src/frontend/app/page.tsx](src/frontend/app/page.tsx) — root page
- [src/frontend/components/FrameworkPluginsTab.tsx](src/frontend/components/FrameworkPluginsTab.tsx) — current plugin UI
- [src/frontend/lib/api.ts](src/frontend/lib/api.ts) — API client (~1500 lines, methods around line 1332 for framework)

**Docs:**
- [CLAUDE.md](CLAUDE.md) — orchestrator/plugin doctrine
- [AGENTS.md](AGENTS.md) — agent guidance
- [docs/PROMETHEUS_IMPLEMENTATION_PLAN.md](docs/PROMETHEUS_IMPLEMENTATION_PLAN.md) — this file

---

## 5. Phase-by-phase plan

---

### Phase 0 — Harden the local path

**Goal:** ToolOrchestra (local NV Orchestrator-8B) is the guaranteed default. API models become an explicit opt-in escalation layer above ToolOrchestra, never a silent fallback.

**Doctrine:** Native-first. Offline-first promise is only real if the system fails loudly when the local model is missing.

**Depends on:** nothing

**Files to read first:**
- [src/backend/app/atlas_plugin_system/orchestrator.py](src/backend/app/atlas_plugin_system/orchestrator.py) — especially lines 99-185 (model loading + API fallback) and 322-357 (generation)
- [src/backend/app/core/config.py](src/backend/app/core/config.py)

**Changes:**

1. In [config.py](src/backend/app/core/config.py), add:
   ```python
   ATLAS_ALLOW_API_FALLBACK: bool = False   # default OFF
   ATLAS_STARTUP_SMOKE_TEST: bool = True     # run end-to-end check on boot
   ```

2. In [orchestrator.py](src/backend/app/atlas_plugin_system/orchestrator.py) `_load_model_sync` (line 147):
   - Keep the GGUF loading block unchanged
   - Guard the API fallback path (line 173-185) behind `settings.ATLAS_ALLOW_API_FALLBACK`
   - If GGUF fails AND fallback disabled → raise `FileNotFoundError` with a detailed setup message (model path, env var to check, where to download)

3. Refactor `_use_api` / `_api_model` into a separate `ApiEscalationLayer` class in a new file [src/backend/app/atlas_plugin_system/api_escalation.py](src/backend/app/atlas_plugin_system/api_escalation.py):
   - Not called during normal orchestrator `run()` — only via explicit `/api/framework/escalate` endpoint (Phase 4 UI hook)
   - This is the "layer above ToolOrchestra" the user specified — keeps code paths alive for dev iteration and future user-invoked escalation, but removes the silent-fallback liability

4. Add startup smoke test in [src/backend/app/main.py](src/backend/app/main.py) lifespan:
   ```python
   if settings.ATLAS_STARTUP_SMOKE_TEST:
       orchestrator = get_atlas_orchestrator()
       await orchestrator.ensure_model_loaded()
       result = await orchestrator.catalog.invoke("search_literature", {"query": "test"}, {})
       logger.info("Startup smoke test: %s", result.get("status"))
   ```

**Verification:**
- Rename/move the GGUF file, start server → server fails to start with clear error naming the expected file path
- Restore the file, start with `ATLAS_ALLOW_API_FALLBACK=false` → loads local model, smoke test logs a status line
- `curl POST /api/framework/run` with prompt "what tools do you have" → answer comes from local model, not API

**Pitfalls:**
- The `_litellm_available` check at orchestrator.py:32 still gets imported at module load — that's fine, just don't USE it unless fallback is enabled
- Startup smoke test must not block if Qdrant has zero docs — `search_literature` handles the empty case (core_tools.py:86-100), just log the empty result as passing

**Estimated effort:** 2-4 hours

---

### Phase 1 — Plugin sandbox tab

**Goal:** Replace the "Run Proof" button with a schema-driven interactive sandbox where users can invoke any plugin directly with arbitrary parameters. Replace the `self_test` manifest field with an `examples` array that pre-populates the form.

**Doctrine:** Self-tests and real-task verification overlap — sandbox is strictly better UX. One code path.

**Depends on:** Phase 0

**Files to read first:**
- [src/backend/app/atlas_plugin_system/registry.py](src/backend/app/atlas_plugin_system/registry.py) — `PluginManifest` (lines 30-59)
- [src/backend/app/atlas_plugin_system/atlas_runtime.py](src/backend/app/atlas_plugin_system/atlas_runtime.py) — `run_plugin_proof` function
- [src/backend/app/api/framework_routes.py](src/backend/app/api/framework_routes.py) — existing `/plugins/{name}/invoke` and `/plugins/{name}/proof` routes
- [src/frontend/components/FrameworkPluginsTab.tsx](src/frontend/components/FrameworkPluginsTab.tsx) — current UI
- [src/frontend/lib/api.ts](src/frontend/lib/api.ts) — `proveFrameworkPlugin` around line 1370

**Changes:**

1. Extend `PluginManifest` in [registry.py](src/backend/app/atlas_plugin_system/registry.py):
   ```python
   examples: List[Dict[str, Any]] = Field(default_factory=list)
   # deprecated but kept for backward compat, remove in Phase 6
   self_test: str = Field(default="", deprecated=True)
   ```
   Each example: `{"name": "...", "description": "...", "arguments": {...}}`

2. Update all six Prometheus plugin manifests to add at least one entry in `examples` (the existing `self_test` canonical input becomes example #1)

3. Add a new React component at [src/frontend/components/PluginSandbox.tsx](src/frontend/components/PluginSandbox.tsx):
   - Takes a plugin manifest
   - Generates a form from `input_schema` using a JSON-Schema-to-form library (react-jsonschema-form is fine, or hand-roll for typography control)
   - Dropdown to pick one of the `examples` to pre-populate the form
   - "Invoke" button → calls existing `POST /api/framework/plugins/{name}/invoke`
   - Result panel with timing, status, JSON tree view, and an "artifacts" viewer for any returned file paths

4. Integrate into [FrameworkPluginsTab.tsx](src/frontend/components/FrameworkPluginsTab.tsx): replace the per-plugin "Run Proof" button with an expand/collapse sandbox panel

**Verification:**
- Open the Plugins tab in the UI
- Click any of the working plugins (manufacturing_world_model, causal_discovery, sandbox_lab)
- Pick an example → form populates → click Invoke → see real output with timing
- Modify inputs, re-invoke, see different output
- Try an invalid input → error surfaces cleanly, doesn't crash the UI

**Pitfalls:**
- `input_schema` on some plugins may be minimal or missing — form should gracefully show a raw JSON text editor as fallback
- Don't regress the existing `/proof` endpoint — keep it alive, just replace UI callsite

**Estimated effort:** 1-2 days

---

### Phase 2a — Verify C1, C2, C4 (working plugins) + output contract standardization

**Goal:** All three implemented manufacturing plugins pass canonical invocations via the sandbox and return outputs in the standardized contract.

**Doctrine:** Hypothesis-until-verified. Every plugin output must carry `hypothesis_state` and reproducibility metadata.

**Depends on:** Phase 1

**Files to read first:**
- [src/backend/plugins/prometheus/manufacturing_world_model/wrapper.py](src/backend/plugins/prometheus/manufacturing_world_model/wrapper.py)
- [src/backend/plugins/prometheus/causal_discovery/wrapper.py](src/backend/plugins/prometheus/causal_discovery/wrapper.py)
- [src/backend/plugins/prometheus/sandbox_lab/wrapper.py](src/backend/plugins/prometheus/sandbox_lab/wrapper.py)

**Changes:**

1. Define the standardized output contract in a new module [src/backend/app/atlas_plugin_system/output_contract.py](src/backend/app/atlas_plugin_system/output_contract.py):
   ```python
   class PluginOutput(BaseModel):
       status: Literal["ok", "error", "partial"]
       summary: str
       value: Dict[str, Any]               # domain-specific payload
       confidence: Optional[float] = None   # 0-1 where meaningful
       uncertainty: Optional[Dict[str, Any]] = None  # e.g. {"std": 0.1, "source": "posterior_variance"}
       hypothesis_state: Literal["unverified", "in_silico_verified", "human_verified", "lab_verified"] = "unverified"
       reproducibility: Dict[str, Any]      # {"plugin_version": "1.0.0", "input_hash": "...", "seed": 42, "duration_ms": 1234}
       artifacts: List[str] = Field(default_factory=list)  # file paths relative to session artifacts dir
   ```

2. Wrap each of C1, C2, C4's existing output into this contract. Key mappings:
   - **manufacturing_world_model**: `confidence` = forecast coverage rate; `uncertainty` = `{"prediction_interval": [...], "source": "quantile_forecasts"}`
   - **causal_discovery**: `confidence` = PCMCI p-value-derived score; each discovered equation from PySR becomes its own hypothesis candidate with its own confidence
   - **sandbox_lab**: `confidence` = best-candidate posterior mean; `uncertainty` = `{"std": posterior_std, "source": "gp_posterior_variance"}`

3. Add Luxshare-shaped canonical examples to each plugin's `examples`:
   - **manufacturing_world_model**: 60-point synthetic reflow oven thermal profile with a planted anomaly
   - **causal_discovery**: 200-point multivariate synthetic dataset where temp → solder_viscosity → defect_rate is the ground-truth chain
   - **sandbox_lab**: 3-parameter reflow optimization (peak temp, dwell time, ramp rate) with the solder-bridge loss function from the existing solder-reflow benchmark

**Verification:**
- Sandbox invocation of each plugin returns an output matching `PluginOutput` schema (use Pydantic validation in a test)
- `hypothesis_state` is always `"unverified"` in direct-invocation mode (never auto-promoted)
- `reproducibility.input_hash` is deterministic — invoking twice with same args produces same hash
- Two runs with the same seed produce bit-identical `value` payloads

**Pitfalls:**
- Some plugins (causal_discovery's PySR stage) use wall-clock seeding internally — need to plumb an explicit seed through
- Don't break existing invocation paths while adding the wrapper — migrate one plugin, test, then the others

**Estimated effort:** 2-3 days

---

### Phase 2b — Build C3 physics_simulator

**Goal:** Ship a physics simulator that Luxshare can *watch get better*. Demo-first: the point is to show a surrogate PINN training live on a simple physical system so factory engineers can see their own future workflow.

**Doctrine:** We don't have Luxshare data. We build our own. The demo *is* the learning curve — "watch the simulator get more accurate with each training epoch."

**Depends on:** Phase 2a (output contract)

**Files to read first:**
- [src/backend/plugins/prometheus/physics_simulator/manifest.json](src/backend/plugins/prometheus/physics_simulator/manifest.json) — current stub
- [src/backend/app/atlas_plugin_system/registry.py](src/backend/app/atlas_plugin_system/registry.py) — wrapper contract
- [src/backend/plugins/prometheus/sandbox_lab/wrapper.py](src/backend/plugins/prometheus/sandbox_lab/wrapper.py) — reference self-contained wrapper

**Choice of physical system:**
Use **1D heat equation along a PCB during reflow** — simple enough to have a closed-form analytical solution, physically meaningful for manufacturing, visually compelling.
- Ground truth: analytical solution to ∂T/∂t = α∂²T/∂x² with time-varying boundary condition (the reflow oven's thermal profile)
- Surrogate: small PINN trained via PyTorch (no NVIDIA Modulus dependency for MVP — the library is heavy; revisit in Phase 8 for the real demo)
- Training loop: surrogate starts naive → synthetic ground-truth data generated from the analytical solution → gradient descent → error drops

**Plugin interface:**
```python
# modes supported
"train_surrogate": {"epochs": int, "training_points": int} → {"epoch_losses": [...], "final_error": float, "model_id": "..."}
"predict": {"model_id": str, "x": [...], "t": [...]} → {"temperature": [...], "ground_truth": [...], "residual": [...]}
"list_models": {} → {"models": [{"id": "...", "trained_epochs": N, "final_error": ...}]}
```

**Changes:**

1. Create [src/backend/plugins/prometheus/physics_simulator/wrapper.py](src/backend/plugins/prometheus/physics_simulator/wrapper.py) — single-file, self-contained (no `app.*` imports)
2. Create [src/backend/plugins/prometheus/physics_simulator/heat_equation.py](src/backend/plugins/prometheus/physics_simulator/heat_equation.py) — analytical ground truth + PINN module
3. Update [manifest.json](src/backend/plugins/prometheus/physics_simulator/manifest.json) with real `input_schema`, `output_schema`, and three `examples` (one per mode)
4. Persist trained surrogates to `{ATLAS_DATA_DIR}/physics_models/{model_id}.pt` so the "watch it get better" demo can continue across sessions

**Verification:**
- Sandbox: invoke `train_surrogate` with `{"epochs": 100}` → see loss curve in returned artifacts, final error visibly lower than start
- Invoke `predict` with the trained model → temperature prediction within 2% of ground truth at typical reflow conditions
- Can be called as a filter in a chain: given a proposed reflow parameter set, returns `hypothesis_state: "in_silico_verified"` iff residual is within tolerance

**Pitfalls:**
- Keep PyTorch CPU-only for MVP — the PINN is tiny, don't compete with the 8B orchestrator for GPU
- The learning-curve artifact (a PNG plot) needs to be written to the session `artifacts/` directory — see Phase 3 for that mechanism; for now, write to a temp file and return the path

**Estimated effort:** 3-5 days

---

### Phase 2c — Build C5 vision_inspector

**Goal:** Wrap a local small VLM so the orchestrator can call it for AOI image verification. Model choice: **Qwen2-VL-2B-Instruct** (or latest Qwen2.5-VL / Qwen3-VL in the 2B class — verify SOTA at implementation time).

**Doctrine:** Offline-first, small enough to fit alongside the 8B orchestrator on a single factory workstation GPU.

**Depends on:** Phase 2a

**Files to read first:**
- [src/backend/plugins/prometheus/vision_inspector/manifest.json](src/backend/plugins/prometheus/vision_inspector/manifest.json)
- Hugging Face model card for the chosen Qwen-VL variant (pick quantized GGUF if llama.cpp support is mature, else transformers 4-bit)

**Plugin interface:**
```python
"inspect": {
    "image_path": str,          # path to the AOI image (local filesystem)
    "aoi_flag": str,            # what the AOI system flagged it for, e.g. "possible_solder_bridge"
    "context": Optional[str]    # optional additional context (board ID, component region, etc.)
} → {
    "confirmed": bool,          # True = real defect, False = false positive
    "reasoning": str,           # VLM's natural-language explanation
    "confidence": float,        # 0-1, elicited from model
    "suggested_next_action": Optional[str]
}
```

**Changes:**

1. Create [src/backend/plugins/prometheus/vision_inspector/wrapper.py](src/backend/plugins/prometheus/vision_inspector/wrapper.py)
2. Bundle 10 sample AOI images (half true defects, half false positives — synthetic or sourced from public PCB datasets) in `samples/` subdirectory
3. Model loading: lazy-load on first invocation, cache in-memory singleton — similar pattern to `AtlasOrchestratorService._load_model_sync`
4. If GPU unavailable or insufficient VRAM, fall back to CPU inference with a clear log warning (vs the orchestrator which hard-fails — vision is optional)

**Verification:**
- Sandbox: invoke `inspect` with one of the bundled samples → get a sensible pass/fail + reasoning
- Running alongside the orchestrator doesn't OOM (peak VRAM under ~12GB on a 16GB workstation target)

**Pitfalls:**
- Qwen2-VL tokenizer has specific image-placeholder handling — check the model's chat template before assuming transformers' default works
- **Verify model choice at implementation time** — by then Qwen3-VL or similar might be SOTA in the 2B class. The principle matters more than the exact model: small local VLM, offline, strong on visual reasoning

**Estimated effort:** 3-5 days

---

### Phase 2d — Build C6 traceability_compliance

**Goal:** Given a query like "prove calibration status of machinery processing Board #8842," deterministically extract the relevant Rustworkx subgraph and have the orchestrator synthesize an ISO-shaped compliance report from it.

**Doctrine:** Traceable both directions — research audit AND manufacturing audit use the same mechanism. Deterministic (no LLM hallucination in the graph walk itself; synthesis over verified nodes).

**Depends on:** Phase 2a

**Files to read first:**
- [src/backend/app/services/graph.py](src/backend/app/services/graph.py) — `GraphService` over Rustworkx
- [src/backend/plugins/prometheus/traceability_compliance/manifest.json](src/backend/plugins/prometheus/traceability_compliance/manifest.json)
- [src/backend/app/atlas_plugin_system/core_tools.py](src/backend/app/atlas_plugin_system/core_tools.py) — for reference on wrapping a substrate service

**Architectural split:**
- **Graph walk** is deterministic → goes into `CoreToolRegistry` as a new core tool `kg_subgraph_walk` (not a plugin — it's foundational retrieval)
- **Report synthesis** is LLM-authored → stays as the plugin `traceability_compliance` which composes `kg_subgraph_walk` + orchestrator synthesis

**Plugin interface:**
```python
"extract_genealogy": {
    "entity_id": str,           # e.g. "PCBA-8842"
    "relation_types": List[str],  # e.g. ["processed_by", "calibrated_with", "inspected_by"]
    "max_depth": int = 5,
    "format": Literal["iso_9001", "iatf_16949", "plain"]
} → {
    "subgraph": {"nodes": [...], "edges": [...]},
    "report_markdown": str,     # synthesized by the orchestrator from the subgraph
    "provenance": [{"claim": "...", "evidence_node_ids": [...]}, ...]
}
```

**Changes:**

1. Add `kg_subgraph_walk` core tool to [core_tools.py](src/backend/app/atlas_plugin_system/core_tools.py): BFS/DFS from entity_id, filtered by `relation_types`, bounded by `max_depth`
2. Create [src/backend/plugins/prometheus/traceability_compliance/wrapper.py](src/backend/plugins/prometheus/traceability_compliance/wrapper.py):
   - Calls `kg_subgraph_walk` via context
   - Passes subgraph to a sub-orchestrator invocation with a template: "Given these verified factory graph nodes and edges, synthesize an `{format}` compliance report. Cite every claim with node IDs."
   - Returns the markdown + structured provenance list
3. Seed the KG with a small demo factory dataset (20-50 nodes covering: machines, calibration events, operators, boards, defects) — put in [src/backend/data/demo_factory_graph.json](src/backend/data/demo_factory_graph.json)

**Verification:**
- Query "extract_genealogy for PCBA-8842" returns a subgraph + report
- Every claim in the report cites at least one node ID from the subgraph (use a linter step)
- Subgraph extraction is deterministic (same entity_id + relation_types → bit-identical subgraph JSON)
- Report passes a structural check for the specified format (headers present, required sections populated)

**Pitfalls:**
- The LLM-authored report CAN hallucinate if the orchestrator pulls in info outside the subgraph. Enforce by: prompting strictly ("ONLY use the provided nodes and edges"), post-hoc linting (every cited node_id must exist in the subgraph), and UI highlighting unverified claims
- Don't skip the demo seed data — the plugin is untestable without it

**Estimated effort:** 3-4 days

---

### Phase 3 — Session memory + pause/resume orchestrator

**Goal:** Every task spawns a session folder of editable MDs. The orchestrator can pause for user input (clarifying questions, plan approval) and resume. Session memory IS the pause/resume state, not a separate database.

**Doctrine:** Session folders are human-editable, LLM-re-readable, training-data-ready — one mechanism, three wins.

**Depends on:** Phases 0, 1, 2a (minimum — other plugins can land later)

**Files to read first:**
- [src/backend/app/atlas_plugin_system/orchestrator.py](src/backend/app/atlas_plugin_system/orchestrator.py) — `run()` loop at line 190
- [src/backend/app/atlas_plugin_system/core_tools.py](src/backend/app/atlas_plugin_system/core_tools.py) — how to add new core tools
- [src/backend/app/api/framework_routes.py](src/backend/app/api/framework_routes.py) — existing `/run` endpoint
- [src/backend/app/core/config.py](src/backend/app/core/config.py)

**New config:**
```python
ATLAS_SESSIONS_DIR: Path = Path("data/sessions")   # relative to repo root; sessions live under {SESSIONS_DIR}/{project_id}/{session_id}/
```

**Session folder structure:**
```
data/sessions/{project_id}/{session_id}/
  SESSION.md          # index + status (running|awaiting_user|completed|failed)
  context.md          # init_session output: goal, constraints, known entities, open questions
  plan.md             # propose_plan output (and edits)
  hypotheses.md       # register_hypothesis entries with states
  findings.md         # write_session_note kind="finding"
  learnings.md        # write_session_note kind="learning"
  decisions.md        # write_session_note kind="decision"
  messages.jsonl      # full orchestrator message log (for resume)
  artifacts/          # plugin binary outputs, plots, reports
```

**New core tools to add** (in [core_tools.py](src/backend/app/atlas_plugin_system/core_tools.py)):

- `init_session(goal: str, ambiguities: List[str] = [])` — writes `context.md`, triggers `ask_user` if ambiguities non-empty
- `ask_user(question: str, options: List[str] = [])` — orchestrator-initiated pause; returns a sentinel that the orchestrator loop recognizes as "pause and surface to UI"
- `propose_plan(steps: List[Dict], rationale: str)` — writes `plan.md`, pauses for user review
- `register_hypothesis(statement: str, falsifiers: List[str], evidence: List[str] = [])` — appends to `hypotheses.md` with state `unverified`, returns hypothesis_id
- `update_hypothesis_state(hypothesis_id: str, new_state: str, evidence: List[str])` — transitions states, requires evidence citation
- `write_session_note(kind: Literal["finding", "learning", "decision"], content: str, heading: Optional[str])` — appends to the right MD
- `read_session_notes(kind: Optional[str])` — reads back what's been written (for orchestrator self-reference)
- `novelty_check(hypothesis_id: str)` — runs `search_literature` + `kg_subgraph_walk` + prior session scan, returns similarity report (note: not binary)

**Orchestrator loop changes (orchestrator.py):**

- `run()` at line 190 gets a new param `resume_token: Optional[str]`. If provided, load `messages.jsonl` from the session folder and continue from there instead of starting fresh
- When the orchestrator emits an `ask_user` or unapproved `propose_plan` tool call, break the loop and return `{status: "awaiting_user", type: "question"|"plan", payload: ..., resume_token: session_id}` instead of continuing
- After each iteration, write `messages.jsonl` atomically (write to `.tmp` then rename)
- New method `resume(session_id, user_response)`: loads messages, appends the user response as a tool result, continues the loop

**New API routes (framework_routes.py):**

- `POST /api/framework/run/resume` — body: `{session_id, user_response}` → continues the paused orchestrator
- `GET /api/framework/sessions/{session_id}` — returns session metadata + list of MDs
- `GET /api/framework/sessions/{session_id}/files/{filename}` — streams an MD file
- `PUT /api/framework/sessions/{session_id}/files/{filename}` — allows user to edit an MD mid-flow (orchestrator will read the updated version on next tool call)

**SQLite schema:** add a `sessions` table indexing `session_id → project_id, created_at, status, folder_path, user_prompt`. Don't store the session contents in SQLite — just the index.

**Verification:**
- Start a task that needs clarification → orchestrator calls `ask_user` → API returns `awaiting_user` + session_id → session folder exists with `SESSION.md` showing status
- Call `/run/resume` with an answer → orchestrator continues, eventually produces a plan
- Edit `plan.md` directly on disk between pause and resume → orchestrator sees the edited version
- Kill the server mid-session → restart → `/run/resume` still works (pure filesystem state)

**Pitfalls:**
- Concurrent writes to `messages.jsonl` — use a per-session file lock (or just SQLite-backed queue for the writes)
- Don't put binary outputs (images, large arrays) in the MDs — always to `artifacts/` with a link in the MD
- The orchestrator must be prompted to actually USE these new tools (`ask_user` when unclear, `propose_plan` before multi-step). Update the system message at orchestrator.py:292 to explain the workflow

**Estimated effort:** 1-2 weeks

---

### Phase 3.5 — Reproducibility layer

**Goal:** Every tool call logs `{plugin_version, input_hash, seed, duration, resource_usage}`. Any completed session can be deterministically replayed.

**Doctrine:** Traceability. "How did we arrive at this?" must always be answerable, bit-for-bit.

**Depends on:** Phase 3

**Files to read first:**
- [src/backend/app/atlas_plugin_system/orchestrator.py](src/backend/app/atlas_plugin_system/orchestrator.py) — tool invocation at line 246-265
- [src/backend/app/atlas_plugin_system/output_contract.py](src/backend/app/atlas_plugin_system/output_contract.py) — already has `reproducibility` field (Phase 2a)

**Changes:**

1. In orchestrator's tool invocation (orchestrator.py:246), wrap each tool call:
   ```python
   import hashlib, time
   input_hash = hashlib.sha256(json.dumps(tool_args, sort_keys=True).encode()).hexdigest()[:16]
   t0 = time.perf_counter()
   result = await self.catalog.invoke(...)
   duration_ms = int((time.perf_counter() - t0) * 1000)
   # augment result with reproducibility if not already set
   ```

2. Add `POST /api/framework/sessions/{session_id}/replay` — re-runs every tool call in `messages.jsonl` with identical inputs + seeds, compares outputs, reports any divergence

3. New session MD `replay.md` that gets populated when a replay is run — diffs against the original session

**Verification:**
- Run a session with sandbox_lab (which uses a seed)
- Replay the session → all outputs bit-identical
- Run a session with a stochastic plugin that doesn't take a seed → replay reports divergence with specific tool calls

**Pitfalls:**
- Some plugins have wall-clock or cwd-sensitive behavior (file paths in output). Either fix the plugin or mark its outputs `deterministic: false` in the contract
- The orchestrator itself is stochastic (temperature > 0). Replay only guarantees tool-call determinism given the same tool-call inputs — not that the orchestrator chooses the same tools. That's a separate property

**Estimated effort:** 3-5 days

---

### Phase 4 — Tasks tab frontend

**Goal:** A Claude Code-style task interface. User prompts, sees clarifying questions, reviews + edits plans, watches execution, browses session memory live.

**Doctrine:** The UX IS the product. No power without usable surface.

**Depends on:** Phase 3

**Files to read first:**
- [src/frontend/app/page.tsx](src/frontend/app/page.tsx) — current landing, to see where to add the Tasks route
- [src/frontend/components/FrameworkPluginsTab.tsx](src/frontend/components/FrameworkPluginsTab.tsx) — reference for how tabs integrate
- [src/frontend/lib/api.ts](src/frontend/lib/api.ts) — API client patterns

**New components:**

- [src/frontend/components/TasksTab.tsx](src/frontend/components/TasksTab.tsx) — main container
- [src/frontend/components/TaskPromptBar.tsx](src/frontend/components/TaskPromptBar.tsx) — user input, attach files, pick project
- [src/frontend/components/TaskTimeline.tsx](src/frontend/components/TaskTimeline.tsx) — chronological view: user prompt → clarifications → plan → tool calls → hypothesis state transitions → final answer
- [src/frontend/components/PlanEditor.tsx](src/frontend/components/PlanEditor.tsx) — editable plan steps with approve/reject/edit actions
- [src/frontend/components/QuestionInterrupt.tsx](src/frontend/components/QuestionInterrupt.tsx) — user-facing UI for `ask_user` pauses
- [src/frontend/components/SessionMemorySidebar.tsx](src/frontend/components/SessionMemorySidebar.tsx) — tabbed editor: Context / Plan / Hypotheses / Findings / Learnings / Decisions — each is a live MD editor
- [src/frontend/components/HypothesisPill.tsx](src/frontend/components/HypothesisPill.tsx) — visual state indicator (unverified=grey, in_silico=blue, human=green, lab=gold)
- [src/frontend/components/FilterChainView.tsx](src/frontend/components/FilterChainView.tsx) — when the orchestrator runs a dynamic filter chain, visualize it as nodes connecting in real-time (NOT a pre-defined DAG — the view is built from the actual tool calls as they happen)
- [src/frontend/components/ContradictionBanner.tsx](src/frontend/components/ContradictionBanner.tsx) — surfaces when a new finding contradicts existing memory

**API client additions** (lib/api.ts):
```typescript
api.runTask(prompt, projectId)                    // POST /api/framework/run (possibly returns awaiting_user)
api.resumeTask(sessionId, userResponse)            // POST /api/framework/run/resume
api.getSession(sessionId)                          // GET
api.getSessionFile(sessionId, filename)            // GET
api.updateSessionFile(sessionId, filename, content) // PUT
api.streamSessionUpdates(sessionId)                // SSE or WebSocket for live updates
```

**Backend addition:** SSE endpoint for live session updates so the frontend doesn't poll:
- `GET /api/framework/sessions/{session_id}/stream` — emits events on every tool call, hypothesis registration, state transition

**Verification:**
- User types "Help me diagnose a yield drop on line 3" → Tasks tab shows the prompt landing, orchestrator pausing with clarifying questions
- User answers → plan appears in editable form → user edits one step → approves → execution proceeds with live tool-call updates
- During execution, user opens `hypotheses.md` in the sidebar, edits a falsifier, saves → orchestrator reads the update on next iteration
- At completion, user sees final answer + can browse all session MDs + see hypothesis states

**Pitfalls:**
- Plan editing shouldn't be TOO free-form — if user rewrites a step into something the orchestrator can't parse, show a linter warning before accepting
- Live streaming + file editing creates race conditions — server is the arbiter; if user edits `plan.md` while orchestrator is mid-write, orchestrator's write wins and user gets a "file changed during your edit — review?" dialog
- Filter chain visualization must NOT be a pre-built DAG component — it's dynamic, built from the live tool call stream. Re-emphasize to implementing agent: NO LANGGRAPH-STYLE DAGS

**Estimated effort:** 2-3 weeks

---

### Phase 4.5 — Memory tier + promotion review

**Goal:** Three memory tiers (session → project → global KG subtree). AI proposes promotions in batches, user confirms. Provenance edges preserve the audit trail.

**Doctrine:** Graduated trust. Evidence-based promotion, not frequency-based.

**Depends on:** Phase 4 (UI) + Phase 3 (sessions)

**Files to read first:**
- [src/backend/app/services/graph.py](src/backend/app/services/graph.py) — Rustworkx interface
- Phase 3 session folder structure

**Storage:**
- **Session memory** → `data/sessions/{project}/{session}/*.md` (Phase 3)
- **Project memory** → `data/projects/{project_id}/memory/*.md` (new)
- **Global KG** → Rustworkx nodes with a `tier: "global_memory"` attribute, edges back to source sessions

**New core tools:**
- `propose_promotions(from_tier: str, to_tier: str)` — AI scans memory, returns candidates with reasoning
- `commit_promotion(memory_id: str, to_tier: str, user_approved: bool, user_edits: Optional[str])` — moves the memory, creates provenance edges

**Promotion gate logic:**
- **Session → Project:** hypothesis must be `in_silico_verified` (passed a filter chain) AND pass novelty check
- **Project → Global:** must have been stable in project memory for ≥N sessions AND be cross-cutting (applied in ≥2 distinct task types)

**New UI:** `MemoryReviewPanel.tsx` — diff-style batch review:
```
PROPOSED PROMOTIONS — session → project (5)
  ✓ Reflow temp 245°C correlates with solder-bridge defect on Board#R7 [evidence: sessions 0408, 0411, 0413]
  ✗ [candidate dropped — contradicted by session 0412]
KEEP SESSION-ONLY (12)
PROPOSED DEMOTIONS — project → archived (2)
```

**Verification:**
- Run 3+ tasks with overlapping findings → invoke `propose_promotions` → UI shows batch
- Approve one, edit wording of another, reject a third → verify each action landed correctly in the target tier
- Check Rustworkx graph: promoted node has edges back to each source session

**Pitfalls:**
- Don't auto-delete from session memory on promotion — session folders are the training data, keep them forever
- De-duplication: if the same finding surfaces 10 times across sessions, promotion should consolidate into one project memory with 10 provenance edges, not 10 duplicates

**Estimated effort:** 1-2 weeks

---

### Phase 5 — Hypothesis filter chain doctrine

**Goal:** Make the filter-chain pattern first-class. Orchestrator authors chains dynamically (NO hard-coded DAGs) based on hypothesis type. Every plugin output is tagged with hypothesis state that only transitions on chain success.

**Doctrine:** Filter-first orchestration, versatility over rigidity (the LangGraph rejection).

**Depends on:** Phase 3 (hypothesis tools) + Phase 2a-d (all plugins working)

**Files to read first:**
- [src/backend/app/atlas_plugin_system/orchestrator.py](src/backend/app/atlas_plugin_system/orchestrator.py) — system message at line 292
- Phase 3's hypothesis-related core tools

**Key principle:** chains are NOT declared upfront. The orchestrator invokes plugins sequentially, and at each step decides whether the hypothesis has been sufficiently verified to update its state or whether another filter is needed. This is what makes Atlas more flexible than LangGraph.

**Changes:**

1. Update the orchestrator system message (orchestrator.py `_build_system_message`) to include the doctrine:
   - "Every output is an unverified hypothesis. Use `register_hypothesis` immediately when making a claim. Only use `update_hypothesis_state` to mark `in_silico_verified` after calling at least one verification plugin AND a novelty check."
   - "Filter chains are yours to compose. Choose the plugins that serve the hypothesis; do not follow a pre-written sequence."

2. Add one meta-tool `run_filter_chain(hypothesis_id, suggested_plugins: List[str])` — convenience wrapper that invokes each plugin in sequence, passes output to next, auto-registers intermediate hypothesis state transitions. This is a *helper*, not the only way to run chains

3. Document 2-3 canonical chain patterns in a new doc [docs/FILTER_CHAIN_PATTERNS.md](docs/FILTER_CHAIN_PATTERNS.md) as *examples* the orchestrator can learn from, not as rigid templates:
   - Manufacturing parameter candidate: `novelty_check → physics_simulator → sandbox_lab → causal_discovery`
   - Anomaly diagnosis: `manufacturing_world_model → causal_discovery → traceability_compliance`
   - AOI escalation: `vision_inspector → (if confirmed) traceability_compliance`

**Verification:**
- Run a task that generates a novel hypothesis → orchestrator calls register_hypothesis → calls novelty_check first → calls domain plugins → state transitions to `in_silico_verified` → only then is it a promotion candidate
- Run a task that tries to promote a hypothesis *without* running the chain → promotion is blocked with clear error

**Pitfalls:**
- Hardest part: getting the orchestrator to actually USE the hypothesis lifecycle reliably. Stock Nemotron-Orchestrator-8B wasn't trained on this pattern. Expect some prompt iteration. This is WHY Phase 9 (custom training) matters eventually — but for the MVP, good prompting + clear tool contracts should suffice
- Don't make `run_filter_chain` mandatory — the orchestrator should be able to do ad-hoc chains too

**Estimated effort:** 1 week

---

### Phase 6 — Evaluation harness

**Goal:** ~10 gold manufacturing scenarios with expected outcomes. Regression tracking between orchestrator versions. Doubles as Luxshare demo script + future DPO eval set.

**Doctrine:** You can't improve what you can't measure.

**Depends on:** All prior phases

**Files to read first:** all prior phase outputs

**Scenarios to build** (starter set, expand over time):

1. **Yield drop diagnosis** — synthetic line data with planted causal chain; expected: orchestrator finds root cause via causal_discovery
2. **Reflow parameter optimization** — given a defect constraint, find parameter set; expected: sandbox_lab converges, physics_simulator validates
3. **AOI false-positive triage** — mixed batch of images; expected: vision_inspector correctly classifies ≥90%
4. **Calibration genealogy** — query specific board; expected: traceability_compliance produces correctly structured report
5. **Novel hypothesis generation** — open-ended "what could improve this line?"; expected: proposes hypotheses, runs filter chain, produces ≥1 `in_silico_verified`
6. **Already-known rediscovery** — hypothesis that IS in the KG; expected: novelty_check flags it, doesn't re-run full chain
7. **Hypothesis falsification** — plant a hypothesis that MUST fail; expected: orchestrator correctly refuses to promote
8. **Multi-session project continuity** — run 3 tasks in one project; expected: later tasks reference prior findings without being told to
9. **Contradiction handling** — new finding contradicts project memory; expected: contradiction banner surfaces, user resolves
10. **Plan editing roundtrip** — user edits plan mid-flow; expected: orchestrator incorporates edit cleanly

**Storage:** [tests/scenarios/](tests/scenarios/) with one YAML per scenario: `prompt`, `expected_tool_calls` (partial match), `expected_hypothesis_states`, `expected_final_answer_contains`

**Runner:** `tests/run_scenarios.py` — executes each scenario, diffs against expectations, outputs a dashboard

**Verification:** the harness itself runs and reports pass/fail per scenario

**Pitfalls:**
- Scenarios will be noisy at first (LLM stochasticity). Define pass criteria as "tool call set overlap ≥ 80%" + "hypothesis states achieved" rather than exact trace match
- Don't over-fit prompting to make scenarios pass — they exist to catch regressions

**Estimated effort:** 1-2 weeks

---

### Phase 7 — Trajectory export

**Goal:** Convert completed session folders into SFT/DPO training format.

**Doctrine:** Every interaction is training data.

**Depends on:** Phase 3 (sessions), Phase 4.5 (promotion decisions = DPO pairs)

Trivial phase — session folders already contain the data. Just write [scripts/export_trajectories.py](scripts/export_trajectories.py) that reads `data/sessions/**` and emits:

- `sft.jsonl`: `{prompt, tools_block, assistant_tool_chain, final_answer}` per successful session
- `dpo_edits.jsonl`: `{prompt, chosen: user_approved_plan, rejected: original_plan}` where users edited plans
- `dpo_promotions.jsonl`: `{claim, chosen: user_approved_wording, rejected: original_ai_wording}`
- `dpo_rejections.jsonl`: `{hypothesis, chosen: "rejected_by_user", rejected: "promoted"}`

**Verification:** export N sessions → counts match; spot-check 3 records manually.

**Estimated effort:** 2-3 days

---

### Phase 8 — Prometheus demo scenarios

**Goal:** End-to-end Luxshare-facing demo flows. Each demo is a gold-standard session folder.

**Depends on:** All prior phases

Script 3-4 canonical demos:

1. **"Yield drop on Line 3"** — engineer describes symptoms → Atlas clarifies, plans, runs manufacturing_world_model → causal_discovery → finds root cause → proposes parameter change → sandbox_lab + physics_simulator verify → produces traceability report
2. **"Physics simulator getting better"** — the visible-improvement demo: show a naive PINN, train it on user's workstation, watch error drop, use it for a real parameter check
3. **"Compliance audit"** — auditor asks a question → traceability_compliance produces ISO-shaped report with full provenance
4. **"Offline AOI triage"** — batch of flagged images → vision_inspector processes all locally → traceability cross-refs with BOM

Script each demo so it runs reliably on a stock workstation. Capture video.

**Estimated effort:** 1-2 weeks

---

### Phase 9 — Custom orchestrator training

**Goal:** Fine-tune Nemotron-Orchestrator-8B on our accumulated session trajectories so the hypothesis-lifecycle + filter-chain patterns become native to the model, not prompted.

**Depends on:** Phase 7 (training data) + Phase 6 (eval harness)

This is an external project, not in-repo work:

1. **SFT stage:** train on `sft.jsonl` (successful session trajectories) for 1-3 epochs
2. **DPO stage:** preference pairs from `dpo_edits.jsonl` + `dpo_promotions.jsonl` + `dpo_rejections.jsonl`
3. **Base:** continue from Nemotron-Orchestrator-8B, don't train from scratch
4. **Infrastructure:** rented A100 (Lambda Labs, Modal, or similar)
5. **Quantize:** export to IQ2_M GGUF for in-repo inference
6. **Eval:** run Phase 6 harness against both stock and trained models; require strict improvement on ≥7 of 10 scenarios before swapping

**Not starting this phase** until we have ≥500 real sessions, per the principle that synthetic-only training produces brittle models.

**Estimated effort:** 2-4 weeks (depends on dataset size and compute)

---

## 6. Phase status tracker

| Phase | Status | Started | Completed | Notes |
|---|---|---|---|---|
| 0 | Not started | | | |
| 1 | Not started | | | |
| 2a | Not started | | | |
| 2b | Not started | | | Physics sim: 1D heat eqn PINN, PyTorch |
| 2c | Not started | | | Qwen2-VL-2B (verify SOTA at start) |
| 2d | Not started | | | Needs demo KG seed |
| 3 | Not started | | | |
| 3.5 | Not started | | | |
| 4 | Not started | | | NO DAG component — dynamic chain viz |
| 4.5 | Not started | | | |
| 5 | Not started | | | |
| 6 | Not started | | | |
| 7 | Not started | | | |
| 8 | Not started | | | |
| 9 | Blocked | | | Needs ≥500 sessions |

---

## 7. Open questions / decisions log

| Date | Question | Decision | Rationale |
|---|---|---|---|
| 2026-04-16 | Keep API fallback silently or gate? | Gate off by default, keep code path for explicit escalation layer above ToolOrchestra | User wants native-first with optional escalation |
| 2026-04-16 | C3 physics sim: bundle Luxshare surrogate or build own? | Build own; demo is the learning curve itself | No Luxshare data available; visible improvement is a selling point |
| 2026-04-16 | C5 VLM: Qwen2-VL-2B or alternatives? | Qwen2-VL-2B-Instruct (verify SOTA in 2B class at implementation time) | Matches Prometheus vision |
| 2026-04-16 | Filter chain library: pre-defined or user-defined? | Fully user/orchestrator-defined at runtime — NO DAGs | Versatility is a key selling point vs LangGraph |
| 2026-04-16 | Session storage location | Project-local: `data/sessions/{project_id}/{session_id}/` | Matches graduated-trust model |
| 2026-04-16 | Promotion cadence | User-triggered only for MVP | Stay in control until signal quality is understood |

---

## 8. Agent hand-off notes

- **Before starting any phase:** read this doc's phase section + CLAUDE.md at repo root + the phase's "Files to read first" list
- **Never introduce LangGraph, agent swarms, or pre-defined DAGs.** The previous architecture was purged for a reason. The orchestrator is the only planner; plugins are the only capabilities; filter chains are dynamic
- **Never bypass the offline-first promise.** If a phase seems to need cloud services (API, web fetch), raise it in the open questions log first
- **Never auto-promote hypotheses.** Every tier transition requires either a filter-chain pass + novelty check (session → project) or explicit user confirm
- **Preserve provenance.** Every claim, every promotion, every state transition has edges back to source sessions. Audit trail is non-negotiable
- **Update this doc** after completing a phase: mark status, note any deviations from the plan, log any new open questions
