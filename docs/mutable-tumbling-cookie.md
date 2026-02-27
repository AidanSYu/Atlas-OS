# Phase 1: Discovery OS Foundation

## Context
Atlas is currently a text-reflecting RAG chatbot. This plan implements Phase 1 of the ConversionPlan.md — adding a ReAct tool-calling loop where the LLM reasons and routes, but all scientific computation is performed by deterministic, auditable plugins (RDKit on CPU). This delivers two real chemistry tools (`predict_properties`, `check_toxicity`), a bridge to existing RAG (`search_literature`), and a new "Discovery" tab in the frontend.

**Zero disruption to existing functionality.** All current intents (SIMPLE, DEEP_DISCOVERY, BROAD_RESEARCH, MULTI_STEP) and UI modes (Librarian, Cortex, MoE) continue to work unchanged.

---

## Implementation Order (17 steps, dependency-aware)

### Layer 0: Dependencies

**1. Add `rdkit-pypi` to requirements.txt**
- File: `src/backend/requirements.txt`
- Add: `rdkit-pypi>=2024.3.1` (CPU-only molecular toolkit, ~50MB)
- Run: `pip install rdkit-pypi` in backend venv

### Layer 1: Backend Foundations (no internal deps)

**2. Create `src/backend/app/services/plugins/base.py`** — BasePlugin ABC
- Abstract class with: `name` (property), `description` (property), `load()`, `execute()`, `input_schema()`, `output_schema()`
- Pattern: pure ABC, no imports from project

**3. Create `src/backend/app/services/agents/tool_schemas.py`** — JSON schemas
- `PHASE1_TOOLS = ["predict_properties", "check_toxicity", "search_literature", "final_answer"]`
- `TOOL_CALL_SCHEMA` — JSON Schema with `thought`/`action`/`action_input` fields, `action` enum-constrained to PHASE1_TOOLS
- `DISCOVERY_INTENT_KEYWORDS` — list of chemistry terms for fast-path intent detection

**4. Create `src/backend/app/services/agents/discovery_state.py`** — DiscoveryState TypedDict
- Follows exact pattern of `NavigatorState` in `swarm.py:163` — TypedDict with `total=False`
- Fields: `query`, `project_id`, `messages` (ReAct history), `current_iteration`, `available_tools`, `candidates`, `phase`, `reasoning_trace`, `status`, `final_answer`, `evidence`, `confidence_score`
- Plain dicts/lists only — no Pydantic inside (LangGraph requirement)

### Layer 2: Plugins (depends on Layer 1)

**5. Create `src/backend/app/services/plugins/properties.py`** — RDKit property predictor
- Implements BasePlugin. `name = "predict_properties"`
- `load()` returns `None` (pure code, no model)
- `execute(smiles=...)` runs RDKit: `MolWt`, `LogP`, `TPSA`, `HBD`, `HBA`, `NumRotatableBonds`, `RingCount`, `QED`, Lipinski check
- Uses `asyncio.get_running_loop().run_in_executor(None, ...)` — same pattern as `llm.py:740`
- RDKit imported inside `_compute()` so module loads even without rdkit installed

**6. Create `src/backend/app/services/plugins/toxicity.py`** — SMARTS toxicity checker
- Implements BasePlugin. `name = "check_toxicity"`
- `load()` pre-compiles SMARTS patterns + RDKit PAINS FilterCatalog
- `execute(smiles=...)` checks structural alerts + PAINS hits, returns `{clean: bool, alerts: [...], pains_hits: int}`
- Same `run_in_executor` pattern

**7. Create `src/backend/app/services/plugins/__init__.py`** — PluginManager
- `PluginManager` class: `register()`, `invoke()` (lazy-load + execute), `unload()`, `unload_all()`, `get_tool_descriptions(available_tools)`
- `get_plugin_manager()` singleton factory — registers Phase 1 plugins on first call
- Pattern: follows `LLMService.get_instance()` singleton pattern from `llm.py`
- `search_literature` is NOT a plugin — handled directly in discovery_graph.py via `RetrievalService.query_atlas()`

### Layer 3: Config + Router (minimal deps)

**8. Modify `src/backend/app/core/config.py`** — Add 3 settings
- `MAX_TOOL_ITERATIONS: int = 8`
- `ENABLE_DISCOVERY_MODE: bool = True`
- `DISCOVERY_DEFAULT_PHASE: str = "hit_identification"`

**9. Modify `src/backend/app/services/agents/meta_router.py`** — Add DISCOVERY intent
- Add `DISCOVERY` to `valid_intents` list (line 43)
- Add DISCOVERY description to classification prompt (after MULTI_STEP, ~line 33)
- Add keyword fast-path before LLM classification (~line 39): check query against `DISCOVERY_INTENT_KEYWORDS` from tool_schemas.py
- Add `DISCOVERY` to `ensure_optimal_model()` alongside DEEP_DISCOVERY (line 79)

### Layer 4: Core ReAct Graph (depends on all above)

**10. Create `src/backend/app/services/agents/discovery_graph.py`** — The main orchestration file

**Key functions:**
- `_build_system_prompt(available_tools, phase)` — dynamic system prompt with tool descriptions
- `_build_discovery_graph(llm_service, retrieval_service)` — returns `StateGraph(DiscoveryState)` with:
  - `think` node: calls `llm_service.generate_constrained(prompt, dynamic_schema)` to get `{thought, action, action_input}` JSON
  - `execute` node: dispatches to `PluginManager.invoke()` for plugins, or `retrieval_service.query_atlas()` for `search_literature`
  - `should_continue()` conditional edge: if `action == "final_answer"` or `iteration >= MAX_TOOL_ITERATIONS` → END, else → execute
  - Edge: `execute → think` (loop back)
- `run_discovery_query(query, project_id, llm_service, retrieval_service)` — non-streaming execution, returns result dict
- `run_discovery_query_streaming(...)` — async generator yielding `(event_type, event_data)` tuples via `compiled.astream_events()`

**Pattern references:**
- Graph compilation: `swarm.py:2411` — `sg.compile(checkpointer=memory)`
- Streaming: `swarm.py:2419` — `compiled.astream_events(initial_state, config, version="v2")`
- Final state: `swarm.py:2491` — `compiled.aget(config)`
- Memory: `app.core.memory.get_memory_saver()` — shared MemorySaver singleton

**SSE event types emitted:**
| Event | Data | When |
|---|---|---|
| `routing` | `{brain: "discovery", intent: "DISCOVERY"}` | Start |
| `progress` | `{node: "think"/"execute", message: "..."}` | Each node start |
| `thinking` | `{content: "Thought: ..."}` | After think node |
| `tool_call` | `{tool: "predict_properties", input: {...}}` | After think node (non-final) |
| `tool_result` | `{tool: "predict_properties", output: {...}}` | After execute node |
| `complete` | `{hypothesis, evidence, candidates, reasoning_trace, ...}` | End |

### Layer 5: API Endpoints (depends on Layer 4)

**11. Modify `src/backend/app/api/routes.py`** — Add discovery endpoints
- Add `DiscoveryRequest(BaseModel)` and `DiscoveryResponse(BaseModel)` after MoE models (~line 862)
- Add `POST /api/discovery/run` — follows exact pattern of `/api/moe/run` (line 865)
- Add `POST /api/discovery/stream` — follows exact SSE pattern of `/api/moe/stream` (lines 893-951)
  - `event_generator()` calls `run_discovery_query_streaming()`
  - Uses `monitor_disconnect()`, `cancel_event`, `StreamingResponse`
- Access services via `chat_service.retrieval_service.llm_service` and `chat_service.retrieval_service` (same as MoE)

### Layer 6: Frontend (depends on API)

**12. Modify `src/frontend/stores/chatStore.ts`** — Add discovery state
- Add to ChatState interface: `discoveryMessages`, `discoveryInput`, `discoverySessionId`
- Add actions: `addDiscoveryMessage`, `setDiscoveryInput`, `clearDiscoveryChat`
- Add `DISCOVERY_WELCOME` message constant
- Update `clearAllChats` (line 171), `setActiveProject` (line 181), and `partialize` (line 208)
- Bump storage `version` from `2` to `3`

**13. Modify `src/frontend/lib/api.ts`** — Add discovery API methods
- Add `DiscoveryResponse` type extending `SwarmResponse` with `candidates` and `iterations`
- Add `streamDiscovery(query, projectId, onEvent, sessionId?, signal?)` — same SSE pattern as `streamSwarm`
- Add `runDiscovery(query, projectId)` — non-streaming fallback

**14. Widen chatMode type in `src/frontend/app/project/workspace-page.tsx`** (line 70)
- `'librarian' | 'cortex' | 'moe'` → `'librarian' | 'cortex' | 'moe' | 'discovery'`

**15. Widen chatMode type in `src/frontend/components/ChatInterface.tsx`** (if it has its own type)

**16. Modify `src/frontend/components/DualAgentChat.tsx`** — Add Discovery mode
- Widen `DualAgentChatProps.chatMode` type (line 48-49)
- Import `Beaker` icon from lucide-react
- Destructure discovery store fields (after line 231)
- Update `currentMessages`/`currentInput`/`setCurrentInput`/`addMessage` ternaries (lines 256-259) to handle `'discovery'`
- Add Discovery tab button after MoE button (line 777): orange color scheme, Beaker icon
- Add `'discovery'` branch in `handleSubmit` — call `api.streamDiscovery()`, handle `tool_call` and `tool_result` events in thinkingSteps
- Add discovery suggestions in empty state (after line 831)
- Update `clearChat` function (line 690)
- Update scroll effect deps (line 239)
- Update input height effect (line 246)

**17. Modify `src/frontend/components/DualAgentChat.tsx`** — Render tool call/result events
- In the streaming progress display, show `tool_call` events as "Calling predict_properties({smiles: ...})"
- Show `tool_result` events with abbreviated output

---

## Verification

1. **Plugin unit test**: `python -c "from app.services.plugins.properties import PropertyPredictorPlugin; ..."` — verify aspirin MolWt == 180.16
2. **Toxicity test**: verify aspirin is `clean == True`
3. **PluginManager test**: `get_plugin_manager().invoke("predict_properties", smiles="...")`
4. **Meta-router test**: verify "properties of aspirin" → DISCOVERY intent via keyword fast-path
5. **API test**: `curl -X POST http://localhost:8000/api/discovery/run -d '{"project_id":"test","query":"What are the properties of aspirin?"}'`
6. **E2E frontend test**: Discovery tab → type query → see progress (Reasoning → Calling predict_properties → Tool result → Final answer) → verify existing tabs still work

---

## Files Summary

| Action | File | Lines Changed (est.) |
|---|---|---|
| Create | `src/backend/app/services/plugins/__init__.py` | ~70 |
| Create | `src/backend/app/services/plugins/base.py` | ~40 |
| Create | `src/backend/app/services/plugins/properties.py` | ~80 |
| Create | `src/backend/app/services/plugins/toxicity.py` | ~90 |
| Create | `src/backend/app/services/agents/discovery_state.py` | ~35 |
| Create | `src/backend/app/services/agents/discovery_graph.py` | ~300 |
| Create | `src/backend/app/services/agents/tool_schemas.py` | ~40 |
| Modify | `src/backend/requirements.txt` | +2 |
| Modify | `src/backend/app/core/config.py` | +5 |
| Modify | `src/backend/app/services/agents/meta_router.py` | +15 |
| Modify | `src/backend/app/api/routes.py` | +80 |
| Modify | `src/frontend/stores/chatStore.ts` | +35 |
| Modify | `src/frontend/lib/api.ts` | +60 |
| Modify | `src/frontend/app/project/workspace-page.tsx` | +1 |
| Modify | `src/frontend/components/DualAgentChat.tsx` | +120 |
