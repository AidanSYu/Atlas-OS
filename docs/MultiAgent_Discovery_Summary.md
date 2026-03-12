# Multi-Agent Discovery OS - Executive Summary

**Date:** 2026-03-02
**Status:** Design Phase - Awaiting Approval
**Full Plan:** See [MultiAgent_Discovery_Architecture.md](./MultiAgent_Discovery_Architecture.md)

---

## Current State

### ✅ What Works Today

**Backend:**
- Single-agent ReAct loop (discovery_graph.py) with RDKit tools
- Coordinator agent for goal extraction (HITL with LangGraph interrupt)
- Session management with folder structure
- SSE streaming infrastructure
- Executor agent scaffold (script generation/approval)

**Frontend:**
- DiscoveryStore with epoch-based branching
- DiscoveryWorkbench telemetry panel
- ChatStore with multi-mode support
- Coordinator chat interface

### ❌ What's Missing

1. **No orchestrator** - Current system is single-agent, not multi-agent
2. **No agent visibility** - Researcher can't see active agents
3. **No dynamic spawning** - Agents are hardcoded, not deployed based on task analysis
4. **No parallelization** - Everything runs sequentially
5. **Limited transparency** - No agent registry or activity tracking

---

## Proposed Solution

### Three-Tier Architecture

```
TIER 1: Orchestrator (Large Model - MiniMax 2.5)
   ↓ analyzes goals, decomposes tasks, spawns agents

TIER 2: Specialist Agents (7B-13B or deterministic)
   - ScriptWriterAgent: Generates Python scripts
   - LiteratureAgent: Searches corpus
   - PropertyPredictorAgent: Coordinates ML tools
   - ValidatorAgent: Checks constraints
   - SynthesisPlannerAgent: Plans routes
   ↓ each writes artifacts to session folder

TIER 3: Deterministic Tools (Existing)
   - RDKit plugins, external APIs, generated scripts
```

### Key Features

1. **Agent Registry**: Backend singleton tracking all active agents
2. **Agent Activity Panel**: Frontend component showing live agent status
3. **Event-Driven**: SSE events for orchestrator/agent state changes
4. **Artifact-Based**: Agents communicate via files, not messages
5. **Resource-Aware**: Orchestrator knows about 4GB VRAM limits

---

## How It Works

### User Journey

1. **Mission Control** → User sets target parameters
2. **Coordinator** → HITL goal extraction (already exists)
3. **Start Execution** → Triggers orchestrator
4. **Orchestrator** → Large model analyzes goals, creates task plan
5. **Agent Spawning** → Specialist agents deployed dynamically
6. **Parallel Execution** → Multiple agents work simultaneously (where safe)
7. **Progress Monitoring** → Frontend shows active agents in real-time
8. **Artifact Generation** → Scripts, CSVs, logs saved to session folder
9. **Synthesis** → Orchestrator aggregates results
10. **Researcher Review** → Browse artifacts, approve next steps

### Example Task Flow

**User Goal:** "Find EGFR kinase inhibitors with MW < 500, LogP 2-4"

**Orchestrator Decomposition:**
1. Task 1: Literature search for EGFR scaffolds → **LiteratureAgent**
2. Task 2: Generate candidate SMILES from scaffolds → **ScriptWriterAgent**
3. Task 3: Predict properties for candidates → **PropertyPredictorAgent**
4. Task 4: Filter by constraints → **ValidatorAgent**
5. Task 5: Synthesize findings → **AnalysisAgent**

**Execution:**
- Tasks 1-2 run in parallel (no dependencies)
- Task 3 waits for Task 2 (needs candidate list)
- Task 4 waits for Task 3 (needs properties)
- Task 5 runs after all complete

**Frontend View:**
```
┌─────────────────────────────────────┐
│ ACTIVE AGENTS                       │
├─────────────────────────────────────┤
│ ● literature_agent_001              │
│   Searching corpus for EGFR...      │
│   Progress: 45%                     │
│                                     │
│ ● script_writer_agent_002           │
│   Generating enumeration script...  │
│   Progress: 30%                     │
│                                     │
│ ○ property_predictor_agent_003      │
│   Waiting for candidates...         │
│                                     │
│ ✓ Completed (0)                     │
│ ✗ Failed (0)                        │
└─────────────────────────────────────┘
```

---

## Benefits

### For Researchers
- **See what's happening**: Live agent status and progress
- **Maintain control**: Approve scripts before execution
- **Trust results**: Full artifact audit trail

### For System
- **Scalable**: Add agents without changing core logic
- **Robust**: Agent failures isolated, don't crash session
- **Efficient**: Resource-aware scheduling for 4GB VRAM

### For Development
- **Modular**: Orchestrator and agents are independent
- **Testable**: Each agent can be tested in isolation
- **Extensible**: New agent types plug into existing registry

---

## Technical Highlights

### 1. Agent Registry Pattern
```python
class AgentRegistry:
    def register_agent(self, metadata: AgentMetadata) -> None
    def update_status(self, agent_id: str, status: AgentStatus) -> None
    def get_session_agents(self, session_id: str) -> List[AgentMetadata]
```

### 2. Orchestrator State Machine
```
plan_tasks → spawn_agents → monitor_agents → synthesize_results
     ↑                            ↓
     └────────── loop ────────────┘
```

### 3. Specialist Agent Template
```python
async def run_specialist_agent(agent_id, task, state, llm):
    1. Create workspace: discovery/{session}/agents/{agent_id}/
    2. Update registry: RUNNING
    3. Execute task (generate script, search corpus, etc.)
    4. Save artifacts (scripts, CSVs, logs)
    5. Update registry: COMPLETED
    6. Return artifact list
```

### 4. Frontend Updates
- New `AgentActivityPanel` component (real-time updates via polling)
- Extended `discoveryStore` with `activeAgents` and `orchestratorStatus`
- New API: `GET /api/discovery/{session_id}/agents`
- SSE events: `orchestrator_planning`, `agent_spawned`, `agent_completed`

---

## SOTA Patterns Applied

1. **Hierarchical Spawning** (AutoGen/CrewAI): Orchestrator spawns specialists
2. **Event-Driven** (LangGraph): SSE for real-time updates
3. **Resource-Aware** (Magentic-One): Respects VRAM constraints
4. **Artifact-Based** (Devin/Cursor): Files, not messages
5. **HITL Checkpoints** (Copilot Workspace): Approval for critical steps

---

## Open Questions

1. **Model for Orchestrator**: MiniMax 2.5 API or local 13B?
2. **Approval Granularity**: All scripts or only "risky" ones?
3. **Parallel Limit**: Max concurrent agents given 4GB VRAM?
4. **Persistence**: Agent state across app restarts?
5. **Error Recovery**: Auto-retry or ask user?

---

## Implementation Phases

### Phase 1: Foundation (Week 1)
- AgentRegistry singleton
- `/api/discovery/{session_id}/agents` endpoint
- AgentActivityPanel frontend component

### Phase 2: Orchestrator (Week 2)
- orchestrator.py with LangGraph
- Task planning + agent spawning
- SSE streaming

### Phase 3: Specialist Agents (Week 3-4)
- ScriptWriterAgent
- LiteratureAgent
- PropertyPredictorAgent
- ValidatorAgent

### Phase 4: Integration (Week 5)
- End-to-end testing
- Error handling
- UI polish

---

## Next Actions

1. **Review this plan** - Confirm architecture matches vision
2. **Answer open questions** - Model choice, approval granularity, etc.
3. **Prototype** - Build minimal orchestrator + 1 agent to validate
4. **Iterate** - Refine based on real-world testing
5. **Scale** - Add remaining agents once pattern proven

---

## Files to Reference

- **Full Architecture**: [MultiAgent_Discovery_Architecture.md](./MultiAgent_Discovery_Architecture.md)
- **Existing Code**:
  - Backend: `src/backend/app/services/agents/` (coordinator, discovery_graph, executor, supervisor)
  - Frontend: `src/frontend/stores/discoveryStore.ts`, `src/frontend/components/DiscoveryWorkbench.tsx`
  - API: `src/backend/app/api/routes.py` (discovery endpoints)
- **Plans**: `docs/DiscoveryOS_GoldenPath_Plan.md`, `docs/Phase5_ScriptSandbox_Implementation.md`
