# AGENTS.md — Atlas Framework reference

This document now describes the Atlas Framework architecture so every agent starts from the same offline, domain-agnostic baseline.

## Atlas Framework overview

- **Offline-first system**: Atlas runs entirely on Windows without cloud dependencies. All models, data, and processing stay local.
- **Single llama-cpp Orchestrator**: `nvidia_Orchestrator-8B-IQ2_M.gguf` (via `llama-cpp-python`) holds the reasoning loop. It ingests user prompts, the manifest catalog, and your knowledge substrate hits before deciding on a tool call.
- **Always-on knowledge substrate**: SQLite, Qdrant, and Rustworkx form the foundational retrieval layer. They are treated like hardware (SSD analog) and are never packaged as optional plugins. The Orchestrator queries them first via core tool handlers.
- **Universal Plugin Protocol**: Optional tools live under `src/backend/plugins/`, each exposing `manifest.json` + `wrapper.py`. The Orchestrator merges the plugin catalog with core tools so it can output JSON tool calls reliably.
- **Hybrid RAG infrastructure**: Vector search, graph traversal, and lighter BM25-style text search collaborate inside the retrieval services. These services are exposed through the core tool catalog and stay active for every request.

## Key directories

- `src/backend/app/atlas_plugin_system/`: orchestrator loop, plugin registry, and core tool definitions.
- `src/backend/plugins/`: optional tools that follow the manifest + wrapper contract. Dropping a folder here will make a new tool available without touching the core orchestrator.
- `src/backend/app/api/framework_routes.py`: FastAPI surface for plugin catalogs, orchestration runs, and health checks.
- `src/backend/app/core/config.py`: controllers for absolute paths (models, databases, plugin directories) and environment settings.
- `src/backend/app/services/retrieval.py` & `graph.py`: implement the always-on vector + graph capabilities that remain active even if no plugin is invoked.

## Working in the repository

1. Start by reading `framework_routes` and `atlas_plugin_system` to understand how the Orchestrator gathers schema+context.
2. Always formulate new functionality as either:
   - a core tool (if it represents foundational KG/retrieval behavior), or
   - a plugin (if it is optional, domain-specific, and implements `manifest.json` + `wrapper.py`).
3. Keep the knowledge substrate decoupled from the plugin system—never move a graph query or vector search helper into `src/backend/plugins/`.
4. When adding documentation, emphasize the new Atlas Framework story: local orchestrator, always-on substrate, plugin protocol, offline guarantees, and `nvidia_Orchestrator-8B-IQ2_M.gguf`.

## Testing & verification

- Backend: `cd src/backend && python run_server.py` and exercise `/api/framework/run`.
- Frontend: `cd src/frontend && npm run dev`; verify the UI mentions the new framework story.
- When debugging, check the orchestrator logs (FastAPI startup logs) and confirm plugins loaded via `/api/framework/plugins`.

## Status

- **Version**: Atlas Framework (post-LangGraph purge).
- **Focus**: single orchestrator + universal plugin protocol + always-on knowledge substrate.

