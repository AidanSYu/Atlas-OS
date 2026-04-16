# CLAUDE.md — Atlas Framework guidance

This file guides Claude Code when working within the Atlas repo. The system now orbits a single local Orchestrator and an always-on knowledge substrate.

## Atlas Framework essentials

- **Single Orchestrator**: All reasoning happens inside `llama-cpp-python` running `nvidia_Orchestrator-8B-IQ2_M.gguf`. The loop ingests the user prompt, manifest catalog, and hybrid RAG hits, emits JSON tool calls, and appends observations until final synthesis.
- **Always-on substrate**: SQLite + Qdrant + Rustworkx persistently power retrieval. These components are treated like system hardware (non-optional). They remain active for every request and are surfaced through `CoreToolRegistry` handlers, not the plugin directory.
- **Universal Plugin Protocol**: Optional capabilities live under `src/backend/plugins/`, each with `manifest.json` plus `wrapper.py`. The Orchestrator merges plugin schemas with core tools so it can call any tool uniformly. Adding a plugin should not require touching the Orchestrator loop.
- **Offline-first**: No external agents, no cloud dependencies; everything runs locally. Plugin shells must avoid remote calls unless explicitly allowed by the user.

## Workflow reminders

1. Read `src/backend/app/atlas_plugin_system/` to understand how the orchestrator loads schemas and routes JSON calls.
2. When you add features, decide if they belong in:
   - `CoreToolRegistry` (if foundational retrieval/graph behavior), or
   - `src/backend/plugins/` (if optional and implements the manifest/wrapper contract).
3. Keep documentation consistent: describe the orchestrator + plugin story, mention the always-on substrate, and highlight `nvidia_Orchestrator-8B-IQ2_M.gguf`.
4. Avoid references to LangGraph, agents, or swarms; they have been purged and are no longer part of the architecture.

## Run commands

```powershell
cd src/backend
python run_server.py
```

```powershell
cd src/frontend
npm run dev
```

```powershell
npm run tauri:dev
```

## Model setup

Ensure `.env` or `config/.env` points to:

```env
MODELS_DIR=C:/path/to/models
QDRANT_STORAGE_PATH=C:/path/to/qdrant_storage
ATLAS_PLUGIN_DIR=C:/path/to/ContAInuumAtlas/src/backend/plugins
DATABASE_PATH=C:/path/to/atlas.db
```

Place `nvidia_Orchestrator-8B-IQ2_M.gguf` in `MODELS_DIR` along with `nomic-embed-text-v1.5` and `gliner_small-v2.1`. The orchestrator will pick it up automatically.

## Testing and delegation

- After you implement a change, validate via `python run_server.py` and ping `/api/framework/run`.
- For UI work, run `npm run dev` inside `src/frontend` and confirm the interface mentions the Atlas Framework story.
- Delegate repetitive tasks using Aider commands when appropriate.
