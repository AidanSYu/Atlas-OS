# Phase 5: Discovery OS — Bug Fixes + Plugin Architecture + Script Sandbox

## Executive Summary

**Current State**: Discovery OS has critical bugs preventing coordinator auto-start and lacks visibility into deterministic models/plugins.

**Phase 5 Goals**:
1. **Fix 3 Critical Bugs** preventing coordinator initialization
2. **Implement Plugin Visibility UI** — show all deterministic models, semantic models, allow configuration
3. **Establish LLM Orchestration Architecture** — DeepSeek (orchestrator) + MiniMax (tool caller), swappable to local
4. **Build Script Execution Sandbox** — transparent Python scripting with human oversight

**Architecture Philosophy**: Discovery OS is NOT a chatbot. It's a **transparent research workbench** where:
- Agent generates **executable Python scripts** (not text responses)
- Scripts use **deterministic tools** (RDKit, external APIs, chemistry simulators)
- All artifacts (scripts, logs, CSVs, images) saved to `discovery/{session_id}/generated/`
- Researcher **audits code** before execution, can edit/approve/reject
- Frontend shows real-time plugin status and generated files

---

## Part 0: CRITICAL BUG FIXES (Implement First)

### Context

Three bugs prevent Discovery Sessions from auto-starting:

1. **Global Run State Blocking** (`ChatShell.tsx` line 375)
2. **Ignored Coordinator Progress Events** (`ChatShell.tsx` buildOnProgress)
3. **Brittle React Mount Trigger** (`ChatShell.tsx` useEffect lines 256-266)

### Bug 1: Global Run State Blocking

**File**: [`src/frontend/components/chat/ChatShell.tsx`](src/frontend/components/chat/ChatShell.tsx:375)

**Problem**: Line 375 checks `if (runManager.isRunning) return;` which blocks coordinator auto-start if ANY previous run (Librarian, MoE, etc.) is still active in the global `useRunStore`.

**Fix**:
```tsx
// Line 256-266: Add cleanup on mount for coordinator mode
useEffect(() => {
  if (!isCoordinatorMode || !projectId || coordinatorTriggered.current) return;

  // BUGFIX: Clear any stale global run state before starting coordinator
  runManager.cancelCurrentRun();

  coordinatorTriggered.current = true;

  // Use immediate execution instead of setTimeout (see Bug 3 fix)
  handleSubmitWithContent('');
}, [isCoordinatorMode, projectId]); // eslint-disable-line react-hooks/exhaustive-deps
```

**Alternative Approach** (if above causes issues):
Add a `forceBootstrap?: boolean` parameter to `handleSubmitWithContent`:
```tsx
const handleSubmitWithContent = useCallback(async (
  userContent: string,
  selectedHypothesis?: boolean,
  forceBootstrap?: boolean
) => {
  // Allow bootstrap even if another run is active
  if ((!userContent.trim() && !isCoordinatorMode) || (!forceBootstrap && runManager.isRunning) || !projectId) return;
  // ... rest of function
}, [/* deps */]);

// In useEffect:
handleSubmitWithContent('', false, true);
```

### Bug 2: Ignored Coordinator Progress Events

**File**: [`src/frontend/components/chat/ChatShell.tsx`](src/frontend/components/chat/ChatShell.tsx:272)

**Problem**: `buildOnProgress()` lacks a case for `coordinator_thinking` events. Backend emits "Scanning your research corpus..." but UI stays stuck on "Starting coordinator...".

**Fix**:
```tsx
// Add to buildOnProgress() switch statement around line 289
case 'coordinator_thinking':
  setStreamProgress((prev) => ({
    ...(prev || { currentNode: 'coordinator', message: '', thinkingSteps: [], evidenceFound: 0 }),
    currentNode: 'coordinator',
    message: event.content || 'Processing...',
    thinkingSteps: prev ? [...prev.thinkingSteps, event.content] : [event.content],
  }));
  break;
```

### Bug 3: Brittle React Mount Trigger

**File**: [`src/frontend/components/chat/ChatShell.tsx`](src/frontend/components/chat/ChatShell.tsx:260)

**Problem**: Lines 260-265 use `setTimeout(..., 300)` with a cleanup function that calls `clearTimeout(timer)`. If `ChatShell` re-renders within 300ms (common in React Strict Mode or state changes), the timer is cancelled and coordinator never starts.

**Fix**: Replace brittle setTimeout with immediate, idempotent initialization:
```tsx
// Lines 256-266: Replace setTimeout pattern
useEffect(() => {
  if (!isCoordinatorMode || !projectId || coordinatorTriggered.current) return;

  // Clear stale runs first (Bug 1 fix)
  runManager.cancelCurrentRun();

  coordinatorTriggered.current = true;

  // Immediate execution — no setTimeout, no race condition
  const bootstrapCoordinator = async () => {
    try {
      await handleSubmitWithContent('');
    } catch (error) {
      console.error('Coordinator bootstrap failed:', error);
      coordinatorTriggered.current = false; // Allow retry
    }
  };

  bootstrapCoordinator();
}, [isCoordinatorMode, projectId]); // eslint-disable-line react-hooks/exhaustive-deps
```

**Important**: Remove the `return () => { clearTimeout(timer); coordinatorTriggered.current = false; }` cleanup — it defeats the purpose of `coordinatorTriggered.current`.

---

## Part 1: LLM Orchestration Architecture

### Context

Currently, Discovery OS hardcodes `llama-cpp-python` for local LLMs. We need:
- **DeepSeek** as orchestrator (planning, high-level reasoning)
- **MiniMax** as tool caller (constrained generation, function calling)
- **Swappable config** — API-first now, local-first later when hardware available

### 1.1 Backend: LLM Service Abstraction

**File**: `src/backend/app/services/llm.py` (MODIFY)

**Current State**: Single `LLMService` class with hardcoded llama-cpp-python.

**Target State**: Abstract base class with pluggable providers.

#### Add Provider Enum
```python
from enum import Enum

class LLMProvider(str, Enum):
    LOCAL = "local"           # llama-cpp-python
    DEEPSEEK = "deepseek"     # DeepSeek API
    MINIMAX = "minimax"       # MiniMax API
    LITELLM = "litellm"       # Unified API gateway
```

#### Add Provider Registry
```python
class LLMService:
    """Unified LLM service supporting multiple providers."""

    def __init__(self):
        self._provider: LLMProvider = LLMProvider.LOCAL
        self._orchestrator_provider: LLMProvider = LLMProvider.DEEPSEEK
        self._tool_caller_provider: LLMProvider = LLMProvider.MINIMAX

        # Local models (lazy-loaded)
        self._local_llm = None
        self._local_embedding_model = None

        # API clients (lazy-loaded)
        self._deepseek_client = None
        self._minimax_client = None
        self._litellm_client = None

    def set_orchestrator(self, provider: LLMProvider):
        """Set the orchestrator LLM (for planning, reasoning)."""
        self._orchestrator_provider = provider

    def set_tool_caller(self, provider: LLMProvider):
        """Set the tool-calling LLM (for constrained generation)."""
        self._tool_caller_provider = provider

    async def generate_orchestrator(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512
    ) -> str:
        """Generate text using the orchestrator LLM."""
        provider = self._orchestrator_provider

        if provider == LLMProvider.DEEPSEEK:
            return await self._generate_deepseek(prompt, temperature, max_tokens)
        elif provider == LLMProvider.LOCAL:
            return await self._generate_local(prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported orchestrator provider: {provider}")

    async def generate_constrained(
        self,
        prompt: str,
        schema: dict,
        temperature: float = 0.3,
        max_tokens: int = 512
    ) -> dict:
        """Generate constrained JSON using the tool-calling LLM."""
        provider = self._tool_caller_provider

        if provider == LLMProvider.MINIMAX:
            return await self._generate_minimax_constrained(prompt, schema, temperature, max_tokens)
        elif provider == LLMProvider.LOCAL:
            # Use existing GBNF grammar approach
            return await self._generate_local_constrained(prompt, schema, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported tool caller provider: {provider}")

    # Private methods for each provider
    async def _generate_deepseek(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """DeepSeek API call."""
        if not self._deepseek_client:
            from litellm import acompletion
            self._deepseek_client = True  # Flag that we're using LiteLLM

        response = await acompletion(
            model="deepseek/deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.DEEPSEEK_API_KEY,
        )
        return response.choices[0].message.content

    async def _generate_minimax_constrained(
        self,
        prompt: str,
        schema: dict,
        temperature: float,
        max_tokens: int
    ) -> dict:
        """MiniMax API call with JSON schema."""
        if not self._minimax_client:
            from litellm import acompletion
            self._minimax_client = True

        response = await acompletion(
            model="minimax/abab6.5s-chat",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object", "schema": schema},
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=settings.MINIMAX_API_KEY,
        )
        import json
        return json.loads(response.choices[0].message.content)

    async def _generate_local(self, prompt: str, temperature: float, max_tokens: int) -> str:
        """Existing llama-cpp-python implementation."""
        # Keep existing code
        pass

    async def _generate_local_constrained(
        self,
        prompt: str,
        schema: dict,
        temperature: float,
        max_tokens: int
    ) -> dict:
        """Existing GBNF grammar implementation."""
        # Keep existing code
        pass
```

#### Add Config Settings

**File**: `src/backend/app/core/config.py` (MODIFY)

```python
class Settings(BaseSettings):
    # Existing settings...

    # LLM Provider Configuration
    LLM_ORCHESTRATOR: str = "deepseek"  # Options: "local", "deepseek", "litellm"
    LLM_TOOL_CALLER: str = "minimax"    # Options: "local", "minimax", "litellm"

    # API Keys (load from .env)
    DEEPSEEK_API_KEY: str | None = None
    MINIMAX_API_KEY: str | None = None
    LITELLM_API_BASE: str | None = None

    class Config:
        env_file = ".env"
```

**File**: `config/.env.example` (UPDATE)

```bash
# LLM Provider Configuration
LLM_ORCHESTRATOR=deepseek  # Options: local, deepseek, litellm
LLM_TOOL_CALLER=minimax    # Options: local, minimax, litellm

# API Keys (leave blank to use local models)
DEEPSEEK_API_KEY=sk-...
MINIMAX_API_KEY=...
LITELLM_API_BASE=http://localhost:4000  # Optional: self-hosted LiteLLM proxy
```

### 1.2 Update Coordinator to Use Orchestrator

**File**: `src/backend/app/services/agents/coordinator.py` (MODIFY)

```python
# Line 206: Replace generate_constrained call
async def analyze_and_ask(state: CoordinatorState) -> dict:
    # ... existing code ...

    try:
        # Use orchestrator for planning (DeepSeek)
        orchestrator_prompt = f"{prompt}\n\nRespond with the required JSON schema."
        analysis = await llm_service.generate_constrained(
            prompt=orchestrator_prompt,
            schema=COORDINATOR_ANALYSIS_SCHEMA,
            temperature=0.3,
            max_tokens=512,
        )
    except Exception as exc:
        logger.error("Coordinator LLM analysis failed: %s", exc)
        # Fallback...
```

---

## Part 2: Plugin Visibility in Frontend

### 2.1 Backend: Plugin Status Endpoint

**File**: `src/backend/app/api/routes.py` (ADD)

```python
@app.get("/api/discovery/plugins")
async def get_plugins() -> dict:
    """List all registered plugins and their load status."""
    from app.services.plugins import get_plugin_manager

    pm = get_plugin_manager()
    registered = pm.get_registered_names()

    plugins_info = []
    for name in registered:
        plugin = pm.get_plugin(name)
        is_loaded = name in pm._loaded

        plugins_info.append({
            "name": name,
            "description": plugin.description if plugin else "Unknown",
            "loaded": is_loaded,
            "input_schema": plugin.input_schema() if plugin else {},
            "output_schema": plugin.output_schema() if plugin else {},
            "type": "deterministic",  # Future: add "semantic" for ML models
        })

    return {
        "plugins": plugins_info,
        "orchestrator": settings.LLM_ORCHESTRATOR,
        "tool_caller": settings.LLM_TOOL_CALLER,
    }

@app.post("/api/discovery/plugins/{plugin_name}/unload")
async def unload_plugin(plugin_name: str) -> dict:
    """Unload a plugin to free memory."""
    from app.services.plugins import get_plugin_manager

    pm = get_plugin_manager()
    pm.unload(plugin_name)
    return {"status": "unloaded", "plugin": plugin_name}
```

### 2.2 Frontend: Plugin Management Component

**File**: `src/frontend/components/PluginManager.tsx` (NEW FILE)

```tsx
'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Cpu, Database, Trash2, RefreshCw, Zap } from 'lucide-react';

interface Plugin {
  name: string;
  description: string;
  loaded: boolean;
  type: 'deterministic' | 'semantic';
  input_schema: any;
  output_schema: any;
}

interface PluginManagerProps {
  projectId?: string;
}

export function PluginManager({ projectId }: PluginManagerProps) {
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [orchestrator, setOrchestrator] = useState<string>('');
  const [toolCaller, setToolCaller] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [expandedPlugin, setExpandedPlugin] = useState<string | null>(null);

  const loadPlugins = async () => {
    setIsLoading(true);
    try {
      const data = await api.getPlugins();
      setPlugins(data.plugins);
      setOrchestrator(data.orchestrator);
      setToolCaller(data.tool_caller);
    } catch (err) {
      console.error('Failed to load plugins:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadPlugins();
  }, []);

  const handleUnload = async (pluginName: string) => {
    try {
      await api.unloadPlugin(pluginName);
      await loadPlugins();
    } catch (err) {
      console.error('Failed to unload plugin:', err);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-4 bg-surface rounded-lg border border-border">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Cpu className="h-5 w-5 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">Plugin Registry</h3>
        </div>
        <button
          onClick={loadPlugins}
          disabled={isLoading}
          className="flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-xs hover:bg-surface transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* LLM Configuration */}
      <div className="grid grid-cols-2 gap-3 p-3 bg-card/50 rounded border border-border/50">
        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Orchestrator</span>
          <div className="flex items-center gap-2">
            <Zap className="h-3.5 w-3.5 text-accent" />
            <span className="text-xs font-medium text-foreground">{orchestrator || 'local'}</span>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">Tool Caller</span>
          <div className="flex items-center gap-2">
            <Database className="h-3.5 w-3.5 text-blue-500" />
            <span className="text-xs font-medium text-foreground">{toolCaller || 'local'}</span>
          </div>
        </div>
      </div>

      {/* Plugin List */}
      <div className="flex flex-col gap-2">
        {plugins.map((plugin) => (
          <div
            key={plugin.name}
            className="flex flex-col gap-2 p-3 bg-card border border-border rounded-lg hover:border-primary/30 transition-colors"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className={`h-2 w-2 rounded-full ${
                    plugin.loaded ? 'bg-success' : 'bg-muted-foreground/30'
                  }`}
                />
                <span className="text-xs font-medium text-foreground">{plugin.name}</span>
                <span className="text-[10px] text-muted-foreground px-1.5 py-0.5 bg-surface rounded">
                  {plugin.type}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() =>
                    setExpandedPlugin(expandedPlugin === plugin.name ? null : plugin.name)
                  }
                  className="text-xs text-primary hover:underline"
                >
                  {expandedPlugin === plugin.name ? 'Hide' : 'Schema'}
                </button>
                {plugin.loaded && (
                  <button
                    onClick={() => handleUnload(plugin.name)}
                    className="rounded p-1.5 hover:bg-destructive/10 transition-colors"
                    title="Unload plugin"
                  >
                    <Trash2 className="h-3.5 w-3.5 text-destructive/80" />
                  </button>
                )}
              </div>
            </div>
            <p className="text-xs text-muted-foreground">{plugin.description}</p>

            {/* Expanded Schema View */}
            {expandedPlugin === plugin.name && (
              <div className="mt-2 space-y-2">
                <div className="text-[10px] text-muted-foreground">
                  <strong>Input Schema:</strong>
                  <pre className="mt-1 p-2 bg-surface rounded text-[9px] overflow-auto max-h-32">
                    {JSON.stringify(plugin.input_schema, null, 2)}
                  </pre>
                </div>
                <div className="text-[10px] text-muted-foreground">
                  <strong>Output Schema:</strong>
                  <pre className="mt-1 p-2 bg-surface rounded text-[9px] overflow-auto max-h-32">
                    {JSON.stringify(plugin.output_schema, null, 2)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 2.3 Frontend: Add to Discovery Workspace

**File**: `src/frontend/components/DiscoveryWorkspaceTab.tsx` (MODIFY)

```tsx
import { PluginManager } from './PluginManager';

// Add to the render (e.g., in a collapsible sidebar or modal):
<div className="border-t border-border p-4">
  <PluginManager projectId={projectId} />
</div>
```

### 2.4 Frontend: API Client

**File**: `src/frontend/lib/api.ts` (ADD)

```typescript
export interface PluginInfo {
  name: string;
  description: string;
  loaded: boolean;
  type: 'deterministic' | 'semantic';
  input_schema: any;
  output_schema: any;
}

export interface PluginsResponse {
  plugins: PluginInfo[];
  orchestrator: string;
  tool_caller: string;
}

// Add to api object:
async getPlugins(): Promise<PluginsResponse> {
  const res = await fetch(`${getApiBase()}/api/discovery/plugins`);
  if (!res.ok) throw new Error('Failed to fetch plugins');
  return res.json();
},

async unloadPlugin(pluginName: string): Promise<void> {
  const res = await fetch(`${getApiBase()}/api/discovery/plugins/${pluginName}/unload`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error(`Failed to unload plugin: ${pluginName}`);
}
```

---

## Part 3: Script Execution Sandbox

### 3.1 Backend: Executor Agent

**File**: `src/backend/app/services/agents/executor.py` (NEW FILE — Keep original Phase 5 plan)

```python
"""Executor Agent — Script Generation & Sandboxed Execution.

Phase 5: Transform Discovery OS from chatbot to transparent scripting sandbox.
"""
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, TypedDict

from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command

from app.services.llm import LLMService
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================
# State
# ============================================================

class ExecutorState(TypedDict, total=False):
    session_id: str
    project_id: str
    extracted_goals: List[str]  # from coordinator

    # Script generation
    current_task: str
    generated_script: str
    script_filename: str
    script_description: str
    required_packages: List[str]
    script_status: str  # "draft" | "approved" | "rejected" | "executed"

    # Execution
    execution_output: str
    execution_error: Optional[str]
    artifacts_generated: List[str]

    # Loop control
    iteration: int
    max_iterations: int
    status: str  # "planning" | "scripting" | "awaiting_approval" | "executing" | "complete"


# ============================================================
# Schemas
# ============================================================

SCRIPT_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "script_code": {"type": "string", "description": "Complete Python script"},
        "filename": {"type": "string", "description": "e.g., generate_candidates.py"},
        "description": {"type": "string", "description": "Plain English summary"},
        "required_packages": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["script_code", "filename", "description", "required_packages"]
}


# ============================================================
# Graph Nodes
# ============================================================

async def plan_task(state: ExecutorState) -> dict:
    """Node 1: Plan next task based on goals and existing artifacts."""
    goals = state.get("extracted_goals", [])
    session_id = state.get("session_id", "")
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 10)

    generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
    generated_folder.mkdir(parents=True, exist_ok=True)

    # List existing artifacts
    existing_files = [f.name for f in generated_folder.iterdir() if f.is_file()]

    # Check if all goals are satisfied (simple heuristic: iteration limit or explicit completion)
    if iteration >= max_iterations:
        return {
            "status": "complete",
            "iteration": iteration + 1,
        }

    # TODO: Use orchestrator LLM to determine next task
    # For now, use a simple template
    if iteration == 0:
        current_task = f"Generate 100 candidate molecules matching goals: {', '.join(goals[:3])}"
    else:
        current_task = f"Analyze results and refine candidates based on iteration {iteration} feedback"

    return {
        "current_task": current_task,
        "status": "scripting",
        "iteration": iteration,
    }


async def generate_script(state: ExecutorState, llm_service: LLMService) -> dict:
    """Node 2: Generate Python script using tool-calling LLM."""
    current_task = state.get("current_task", "")
    goals = state.get("extracted_goals", [])
    session_id = state.get("session_id", "")

    generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
    existing_files = [f.name for f in generated_folder.iterdir() if f.is_file()]

    prompt = f"""You are a scientific computing agent generating Python scripts for chemistry research.

=== RESEARCH GOALS ===
{chr(10).join(f"- {g}" for g in goals)}

=== CURRENT ARTIFACTS ===
{chr(10).join(f"- {f}" for f in existing_files) if existing_files else "None yet."}

=== CURRENT TASK ===
{current_task}

Generate a complete, executable Python script that:
1. Uses deterministic tools (RDKit, NumPy, Pandas — NO LLM calls)
2. Saves all outputs to the current directory (logs.txt, results.csv, plots.png)
3. Includes error handling and progress logging
4. Is fully self-contained (no external file dependencies)

Available packages: rdkit, pandas, numpy, matplotlib, requests

Return JSON with: script_code, filename, description, required_packages
"""

    try:
        result = await llm_service.generate_constrained(
            prompt=prompt,
            schema=SCRIPT_GENERATION_SCHEMA,
            temperature=0.3,
            max_tokens=2048,
        )
    except Exception as exc:
        logger.error("Script generation failed: %s", exc)
        return {
            "execution_error": f"Script generation failed: {exc}",
            "status": "error",
        }

    # Save script to disk
    script_path = generated_folder / result["filename"]
    with open(script_path, "w") as f:
        f.write(result["script_code"])

    return {
        "generated_script": result["script_code"],
        "script_filename": result["filename"],
        "script_description": result["description"],
        "required_packages": result["required_packages"],
        "script_status": "draft",
        "status": "awaiting_approval",
    }


async def await_approval(state: ExecutorState) -> dict:
    """Node 3: HITL interrupt for human approval."""
    approval_payload = {
        "filename": state.get("script_filename", ""),
        "code": state.get("generated_script", ""),
        "description": state.get("script_description", ""),
        "required_packages": state.get("required_packages", []),
    }

    # Pause graph and surface approval payload
    user_decision = interrupt(approval_payload)

    # Resume when user approves/rejects/edits
    if isinstance(user_decision, str) and user_decision.startswith("edit:"):
        edited_code = user_decision[5:]
        # Overwrite script file
        session_id = state.get("session_id", "")
        generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
        script_path = generated_folder / state["script_filename"]
        with open(script_path, "w") as f:
            f.write(edited_code)
        return {"script_status": "approved", "generated_script": edited_code}
    elif user_decision == "approve":
        return {"script_status": "approved"}
    else:  # reject
        return {"script_status": "rejected", "status": "planning"}  # Loop back to plan


async def execute_script(state: ExecutorState) -> dict:
    """Node 4: Execute Python script in sandboxed subprocess."""
    session_id = state["session_id"]
    script_filename = state["script_filename"]

    generated_folder = Path(settings.DATA_DIR) / "discovery" / session_id / "generated"
    script_path = generated_folder / script_filename

    if not script_path.exists():
        return {"execution_error": f"Script not found: {script_filename}", "status": "error"}

    try:
        # Execute with timeout
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(generated_folder),
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutes
            env={**os.environ, "PYTHONPATH": str(Path(__file__).parent.parent.parent)},
        )

        # Save logs
        log_file = generated_folder / "execution_log.txt"
        with open(log_file, "a") as f:
            f.write(f"\n=== {script_filename} ===\n")
            f.write(f"STDOUT:\n{result.stdout}\n")
            if result.stderr:
                f.write(f"STDERR:\n{result.stderr}\n")

        if result.returncode != 0:
            return {
                "execution_error": result.stderr,
                "execution_output": result.stdout,
                "status": "error",
            }

        # List new artifacts
        artifacts = [f.name for f in generated_folder.iterdir() if f.is_file()]

        return {
            "execution_output": result.stdout,
            "execution_error": None,
            "artifacts_generated": artifacts,
            "iteration": state.get("iteration", 0) + 1,
            "status": "planning",  # loop back to plan next task
        }

    except subprocess.TimeoutExpired:
        return {"execution_error": "Script execution timeout", "status": "error"}
    except Exception as exc:
        logger.exception("Script execution failed")
        return {"execution_error": str(exc), "status": "error"}


# ============================================================
# Graph Builder
# ============================================================

def _build_executor_graph(llm_service: LLMService, auto_approve: bool) -> StateGraph:
    """Build the Executor StateGraph."""

    async def _plan_task_wrapper(state: ExecutorState) -> dict:
        return await plan_task(state)

    async def _generate_script_wrapper(state: ExecutorState) -> dict:
        return await generate_script(state, llm_service)

    async def _await_approval_wrapper(state: ExecutorState) -> dict:
        return await await_approval(state)

    async def _execute_script_wrapper(state: ExecutorState) -> dict:
        return await execute_script(state)

    def should_await_approval(state: ExecutorState) -> str:
        if auto_approve or state.get("script_status") == "approved":
            return "execute"
        return "await"

    def should_continue(state: ExecutorState) -> str:
        status = state.get("status", "")
        if status in ("complete", "error"):
            return "end"
        return "continue"

    sg = StateGraph(ExecutorState)
    sg.add_node("plan_task", _plan_task_wrapper)
    sg.add_node("generate_script", _generate_script_wrapper)
    sg.add_node("await_approval", _await_approval_wrapper)
    sg.add_node("execute_script", _execute_script_wrapper)

    sg.set_entry_point("plan_task")
    sg.add_edge("plan_task", "generate_script")
    sg.add_conditional_edges("generate_script", should_await_approval, {
        "execute": "execute_script",
        "await": "await_approval",
    })
    sg.add_edge("await_approval", "execute_script")
    sg.add_conditional_edges("execute_script", should_continue, {
        "continue": "plan_task",
        "end": END,
    })

    return sg


# ============================================================
# Streaming Execution
# ============================================================

async def run_executor_streaming(
    session_id: str,
    extracted_goals: List[str],
    auto_approve: bool,
    llm_service: LLMService,
    cancel_event: Optional[asyncio.Event] = None,
) -> AsyncGenerator[Tuple[str, dict], None]:
    """Stream executor events.

    Event types:
        executor_thinking: {"content": "Planning next task..."}
        executor_script_generated: {"filename": ..., "code": ..., "description": ..., "requiredPackages": [...]}
        executor_awaiting_approval: {"script_id": ..., "filename": ..., "preview": ...}
        executor_executing: {"filename": ..., "progress": ...}
        executor_artifact: {"filename": ..., "type": "log|csv|image"}
        executor_complete: {"artifacts": [...], "summary": ...}
        error: {"message": ...}
    """
    from app.core.memory import get_memory_saver

    memory = await get_memory_saver()
    sg = _build_executor_graph(llm_service, auto_approve)
    compiled = sg.compile(checkpointer=memory)

    thread_id = f"executor-{session_id}"
    config = {"configurable": {"thread_id": thread_id}}

    # Check if this is a resume (approval decision) or initial start
    snapshot = await compiled.aget_state(config)
    is_resume = bool(snapshot.next)

    if is_resume:
        yield ("executor_thinking", {"content": "Resuming execution..."})
        # Resume is handled by Command(resume=...) from approval endpoint
        return
    else:
        yield ("executor_thinking", {"content": "Initializing executor..."})
        input_value = {
            "session_id": session_id,
            "extracted_goals": extracted_goals,
            "status": "planning",
            "iteration": 0,
            "max_iterations": 10,
        }

    try:
        async for event in compiled.astream(input_value, config=config, stream_mode="updates"):
            if cancel_event and cancel_event.is_set():
                return

            for node_name, update in event.items():
                if not isinstance(update, dict):
                    continue

                if node_name == "plan_task":
                    yield ("executor_thinking", {"content": f"Planning: {update.get('current_task', '')}"})

                elif node_name == "generate_script":
                    if update.get("script_filename"):
                        yield ("executor_script_generated", {
                            "filename": update["script_filename"],
                            "code": update["generated_script"],
                            "description": update["script_description"],
                            "requiredPackages": update.get("required_packages", []),
                        })

                elif node_name == "execute_script":
                    artifacts = update.get("artifacts_generated", [])
                    for artifact in artifacts:
                        file_ext = Path(artifact).suffix.lower()
                        artifact_type = (
                            "csv" if file_ext == ".csv" else
                            "image" if file_ext in [".png", ".jpg", ".jpeg"] else
                            "log"
                        )
                        yield ("executor_artifact", {"filename": artifact, "type": artifact_type})

    except Exception as exc:
        logger.exception("Executor streaming failed")
        yield ("error", {"message": str(exc)})
        return

    # Check final state
    try:
        final_snapshot = await compiled.aget_state(config)
        final_state = final_snapshot.values or {}

        if final_state.get("status") == "complete":
            artifacts = final_state.get("artifacts_generated", [])
            yield ("executor_complete", {
                "artifacts": artifacts,
                "summary": f"Completed {final_state.get('iteration', 0)} iterations.",
            })
        elif not final_snapshot.next:
            # Graph ended without completing (e.g., error)
            yield ("error", {"message": "Executor ended unexpectedly"})
        else:
            # Graph is paused at await_approval — extract interrupt
            for task in (final_snapshot.tasks or []):
                if hasattr(task, "interrupts") and task.interrupts:
                    approval_data = task.interrupts[0].value
                    if isinstance(approval_data, dict):
                        yield ("executor_awaiting_approval", approval_data)
                    return

    except Exception as exc:
        logger.warning("Failed to read executor snapshot: %s", exc)
        yield ("error", {"message": f"State read error: {exc}"})
```

### 3.2 Backend: Executor Endpoints

**File**: `src/backend/app/api/routes.py` (ADD)

```python
@app.post("/api/discovery/{session_id}/executor/start")
async def start_executor(
    session_id: str,
    request: Request,
    auto_approve: bool = Query(default=False),
):
    """Start script execution sandbox after coordinator completes."""
    from app.services.discovery_session import DiscoverySessionService
    from app.services.agents.executor import run_executor_streaming
    from app.services.llm import get_llm_service

    # Load extracted goals from database
    db_session = DiscoverySessionService.get_session(session_id)
    goals = db_session.target_params.get("coordinator_extracted_goals", [])

    llm_service = get_llm_service()

    async def event_generator():
        cancel_event = asyncio.Event()
        monitor_task = asyncio.create_task(monitor_disconnect(request, cancel_event))

        try:
            async for event_type, event_data in run_executor_streaming(
                session_id=session_id,
                extracted_goals=goals,
                auto_approve=auto_approve,
                llm_service=llm_service,
                cancel_event=cancel_event,
            ):
                if cancel_event.is_set():
                    yield f"event: cancelled\ndata: {{}}\n\n"
                    break
                yield f"event: {event_type}\ndata: {json.dumps(event_data)}\n\n"
        finally:
            monitor_task.cancel()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/api/discovery/{session_id}/executor/approve")
async def approve_script(
    session_id: str,
    decision: str,  # "approve" | "reject" | "edit"
    edited_code: Optional[str] = None,
):
    """Resume executor with approval decision."""
    from app.core.memory import get_memory_saver
    from app.services.agents.executor import _build_executor_graph
    from app.services.llm import get_llm_service

    memory = await get_memory_saver()
    llm_service = get_llm_service()
    sg = _build_executor_graph(llm_service, auto_approve=False)
    compiled = sg.compile(checkpointer=memory)

    thread_id = f"executor-{session_id}"
    config = {"configurable": {"thread_id": thread_id}}

    user_response = decision if not edited_code else f"edit:{edited_code}"

    # Resume graph via Command(resume=...)
    await compiled.ainvoke(Command(resume=user_response), config=config)
    return {"status": "resumed"}
```

### 3.3 Frontend: Script Approval Modal (Keep from Original)

**File**: `src/frontend/components/ScriptApprovalModal.tsx` — already exists, no changes needed.

### 3.4 Frontend: Stream Adapter

**File**: `src/frontend/lib/stream-adapter.ts` (ADD executor event types)

```typescript
export type NormalizedEvent =
  // ... existing types ...
  | { type: 'executor_thinking'; content: string }
  | { type: 'executor_script_generated'; filename: string; code: string; description: string; requiredPackages: string[] }
  | { type: 'executor_awaiting_approval'; script_id: string; filename: string; preview: string }
  | { type: 'executor_executing'; filename: string; progress: string }
  | { type: 'executor_artifact'; filename: string; type: 'log' | 'csv' | 'image' }
  | { type: 'executor_complete'; artifacts: string[]; summary: string };
```

### 3.5 Frontend: API Client

**File**: `src/frontend/lib/api.ts` (ADD)

```typescript
async approveScript(
  sessionId: string,
  decision: 'approve' | 'reject' | 'edit',
  editedCode?: string | null
): Promise<void> {
  const res = await fetch(`${getApiBase()}/api/discovery/${sessionId}/executor/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, edited_code: editedCode }),
  });
  if (!res.ok) throw new Error('Failed to approve script');
}
```

---

## Part 4: Implementation Checklist

### Part 0: Bug Fixes (CRITICAL — Do First)
- [ ] Fix Bug 1: Global Run State Blocking in [`ChatShell.tsx:256-266`](src/frontend/components/chat/ChatShell.tsx:256)
- [ ] Fix Bug 2: Add `coordinator_thinking` case to [`buildOnProgress()`](src/frontend/components/chat/ChatShell.tsx:272)
- [ ] Fix Bug 3: Replace brittle setTimeout with immediate execution in [`ChatShell.tsx:260`](src/frontend/components/chat/ChatShell.tsx:260)
- [ ] Test coordinator auto-start in clean browser session
- [ ] Test coordinator auto-start after running Librarian query first

### Part 1: LLM Orchestration
- [ ] Add `LLMProvider` enum to [`llm.py`](src/backend/app/services/llm.py)
- [ ] Implement `set_orchestrator()` and `set_tool_caller()` methods
- [ ] Implement `_generate_deepseek()` using LiteLLM
- [ ] Implement `_generate_minimax_constrained()` using LiteLLM
- [ ] Add config settings to [`config.py`](src/backend/app/core/config.py)
- [ ] Update [`config/.env.example`](config/.env.example)
- [ ] Test DeepSeek API integration
- [ ] Test MiniMax API integration with JSON schema

### Part 2: Plugin Visibility
- [ ] Add `/api/discovery/plugins` endpoint to [`routes.py`](src/backend/app/api/routes.py)
- [ ] Add `/api/discovery/plugins/{name}/unload` endpoint
- [ ] Create [`PluginManager.tsx`](src/frontend/components/PluginManager.tsx) component
- [ ] Add `getPlugins()` and `unloadPlugin()` to [`api.ts`](src/frontend/lib/api.ts)
- [ ] Integrate `PluginManager` into [`DiscoveryWorkspaceTab.tsx`](src/frontend/components/DiscoveryWorkspaceTab.tsx)
- [ ] Test plugin load/unload cycle
- [ ] Verify schema display in UI

### Part 3: Script Sandbox
- [ ] Create [`executor.py`](src/backend/app/services/agents/executor.py) with full LangGraph
- [ ] Add `/api/discovery/{session_id}/executor/start` endpoint
- [ ] Add `/api/discovery/{session_id}/executor/approve` endpoint
- [ ] Extend [`stream-adapter.ts`](src/frontend/lib/stream-adapter.ts) with executor events
- [ ] Add `approveScript()` to [`api.ts`](src/frontend/lib/api.ts)
- [ ] Update [`DiscoveryWorkspaceTab.tsx`](src/frontend/components/DiscoveryWorkspaceTab.tsx) with "Start Execution" button
- [ ] Test script generation with MiniMax
- [ ] Test script approval modal
- [ ] Test subprocess execution
- [ ] Verify artifact file polling

---

## Part 5: Testing Strategy

### Manual Testing
1. **Bug Fix Verification**:
   - Start Librarian chat → immediately create new Discovery Session → verify coordinator starts
   - Create Discovery Session → verify progress updates from "Starting..." to "Scanning corpus..."
   - Create Discovery Session → verify no mount/unmount race conditions

2. **LLM Integration**:
   - Set `LLM_ORCHESTRATOR=deepseek` in `.env`
   - Verify coordinator uses DeepSeek for Q&A
   - Set `LLM_TOOL_CALLER=minimax` in `.env`
   - Verify executor script generation uses MiniMax

3. **Plugin Visibility**:
   - Open Plugin Manager → verify all plugins listed
   - Check loaded status (green dot)
   - Unload a plugin → verify status changes
   - Expand schema → verify JSON schema display

4. **Script Execution**:
   - Complete coordinator → click "Start Execution"
   - Verify script approval modal renders
   - Edit script code → approve → verify execution
   - Check `discovery/{session_id}/generated/` folder for artifacts
   - Verify frontend polls and displays new files

### Automated Tests
- `tests/test_executor_graph.py` — state transitions
- `tests/test_plugin_manager.py` — load/unload cycle
- Integration test: POST `/executor/start` → verify SSE events

---

## Part 6: Success Criteria

- ✅ **Bug 1 Fixed**: Coordinator starts even if previous run is active
- ✅ **Bug 2 Fixed**: UI shows "Scanning corpus..." progress
- ✅ **Bug 3 Fixed**: No mount/unmount race condition
- ✅ **LLM Orchestration**: DeepSeek orchestrates, MiniMax generates scripts
- ✅ **Plugin Visibility**: All plugins visible in UI with load status
- ✅ **Script Sandbox**: Executor generates Python scripts, not text
- ✅ **Human Oversight**: Script approval modal works
- ✅ **Transparent Execution**: All artifacts saved to `generated/` folder
- ✅ **Real-Time Polling**: Frontend displays new files as they're created
- ✅ **No LLM Hallucination**: All computation is deterministic and auditable

---

## Part 7: Migration Path for Other Agents

If you're implementing this plan as another agent (e.g., Aider, Antigravity):

1. **Start with Part 0** (Bug Fixes) — this unblocks all Discovery functionality
2. **Then Part 2** (Plugin Visibility) — this gives immediate user value
3. **Then Part 1** (LLM Orchestration) — this sets up the architecture
4. **Finally Part 3** (Script Sandbox) — this is the most complex piece

Each part is independently testable. Don't move to the next part until the previous part works end-to-end.

---

## Appendix A: File Reference

### Backend Files to Modify
- [`src/backend/app/services/llm.py`](src/backend/app/services/llm.py) — LLM abstraction
- [`src/backend/app/core/config.py`](src/backend/app/core/config.py) — Settings
- [`src/backend/app/api/routes.py`](src/backend/app/api/routes.py) — Endpoints
- [`src/backend/app/services/agents/coordinator.py`](src/backend/app/services/agents/coordinator.py) — Use orchestrator

### Backend Files to Create
- `src/backend/app/services/agents/executor.py` — Script sandbox

### Frontend Files to Modify
- [`src/frontend/components/chat/ChatShell.tsx`](src/frontend/components/chat/ChatShell.tsx) — Bug fixes
- [`src/frontend/lib/stream-adapter.ts`](src/frontend/lib/stream-adapter.ts) — Event types
- [`src/frontend/lib/api.ts`](src/frontend/lib/api.ts) — API methods
- [`src/frontend/components/DiscoveryWorkspaceTab.tsx`](src/frontend/components/DiscoveryWorkspaceTab.tsx) — Executor UI

### Frontend Files to Create
- `src/frontend/components/PluginManager.tsx` — Plugin visibility

### Config Files
- [`config/.env.example`](config/.env.example) — API keys

---

## Appendix B: DeepSeek vs MiniMax Configuration

| Component | Model | Purpose | Fallback |
|-----------|-------|---------|----------|
| **Coordinator** | DeepSeek | High-level planning, Q&A generation | Local Llama 3 |
| **Executor (Script Gen)** | MiniMax | Constrained JSON, tool calling | Local Llama 3 + GBNF |
| **Discovery Agent** | MiniMax | Tool calling (RDKit, etc.) | Local Llama 3 + GBNF |
| **Librarian** | Local Llama 3 | Simple RAG queries | N/A |

**Why this split?**
- **DeepSeek**: Best for open-ended reasoning and dialogue
- **MiniMax**: Best for structured output and function calling
- **Local**: Zero-cost fallback when APIs unavailable

**Future**: When local hardware is sufficient, replace both with locally-hosted DeepSeek + swarm of fine-tuned tool-calling models.
