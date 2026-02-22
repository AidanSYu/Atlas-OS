# Atlas - AI-Native Knowledge Desktop Application

> **The AI does not know things. It queries a living knowledge substrate... and reasons over it automatically.**

Atlas is a **standalone Windows desktop application** that builds a continuous knowledge layer beneath an AI model. This is not a chatbot—it's a scalable, explainable, open-source **Agentic Research Assistant** optimized for retrieval, relationships, and multi-turn reasoning over your personal documents.

Fully self-contained desktop app powered by a **Multi-Agent LangGraph Architecture**. All components are bundled: Qdrant vector database, Rustworkx knowledge graph, and Python backend run as secure local processes.

---

## ✨ Key Features

- **Local-First Architecture** - All data stays on your computer. Zero cloud dependencies.
- **Agentic RAG (Swarm)** - Dynamic query routing via a `Meta-Router` to specialized agents (Librarian for direct lookup, Navigator for deep discovery, Cortex for broad research).
- **Multi-Turn Reflection Loops (`Navigator 2.0`)** - Agents plan, explore graphs, retrieve iteratively, and self-critique using chain-of-thought methodologies up to 3 times before finalizing.
- **Mixture of Experts (`Cortex MoE`)** - Complex tasks are broken down by a Supervisor and delegated to Hypothesis, Retrieval, and Writer experts.
- **Document Grounding & Auditing** - All answers logically cite source documents and page numbers. A dedicated Grounding Auditor verifies that outputs trace back to actual text.
- **Knowledge Graph (Rustworkx)** - Entities and relationships are mathematically queryable. Atlas walks subgraphs assessing node centrality and clustered concepts for non-obvious insights.
- **Constrained Generation** - Uses GBNF grammars attached to `llama-cpp-python` to ensure native JSON reliability out of small local models (4GB-8GB VRAM constraint).
- **Fast NER** - GLiNER-based entity extraction (~50x faster than LLM-based extraction).

---

## 🚀 Installation & Usage

### For Users: Install the Application

1. **Download** the latest installer from [Releases](https://github.com/[your-repo]/releases)
   - `Atlas_x64_en-US.msi` (Windows Installer) - Recommended

2. **Run** the installer and follow the setup wizard.
3. **Launch** Atlas from your Start Menu or Desktop shortcut.
4. **Add Documents**:
   - Click "Upload Documents" or drag-and-drop PDF files.
   - Atlas automatically extracts text, entities, and builds a hybrid Qdrant + Rustworkx knowledge graph.
5. **Setting up AI models (if the installer did not include them)**  
   - Open Atlas; in the left sidebar under **Models** you will see the folder path where models should go.
   - Place the following in that folder:
     - **LLM:** one or more `.gguf` files (e.g., Llama 3 8B, Qwen 2.5, Phi-3).
     - **Embeddings:** a folder named `nomic-embed-text-v1.5`.
     - **NER:** a folder named `gliner_small-v2.1`.
   - The default model fallback uses `llama-cpp-python` to run these entirely on your local GPU/CPU.

6. **Ask Questions**:
   - The Meta-Router will detect if your question is simple or deep, invoking the Librarian or the full Swarm.

---

## 🛠️ Development & Building

### Prerequisites (For Developers)

- **Windows 10/11** (x64)
- **Node.js 18+** - https://nodejs.org/
- **Python 3.12**
- **Rust** (optional) - Required only to modify Tauri/desktop components

### Quick Start: Development Mode

For faster development with hot-reloading, run the backend and frontend in separate terminals.

**Terminal 1 (Backend):**  
From repo root:
```powershell
.\scripts\dev\run_backend.ps1
```
*(Runs FastAPI on http://127.0.0.1:8000 with embedded Qdrant/SQLite/Rustworkx)*

**Terminal 2 (Frontend):**
```powershell
cd src/frontend
npm run dev
```
*(Runs Next.js on http://localhost:3000)*

**Terminal 3 (Tauri App Shell):**
```powershell
npm run tauri:dev
```

### Build Production Installer

```powershell
# Build backend PyInstaller executable + frontend bundle + Tauri app
npm run tauri:build
```
This generates the standalone MSI installer, bundling the Python environment and Tauri desktop executable.

---

## 🏗️ Architecture

### Desktop Application Structure

```
Atlas (Windows Application)
├── Frontend Layer (Next.js 14, React, Tailwind, TypeScript)
├── Tauri Shell (Rust core, Window/process management)
└── Backend Layer (Python/FastAPI)
    ├── Qdrant v1.7.0 (Executables)
    ├── Rustworkx Knowledge Graph engine
    ├── LangGraph Swarm (Agents)
    └── llama-cpp-python / PyTorch (Local Inference)
```

### Multi-Agent Knowledge Pipeline

```
User Query (Frontend)
    ↓
Meta-Router Agent (Intent Classification)
    ├─> Simple Query → [Librarian Agent] (Fast Vector Search)
    │
    ├─> Deep Discovery → [Navigator 2.0]
    │      ↳ Planner → Rustworkx Graph Walk → Multi-Turn Retrieval → Reasoner → Critic Loop
    │
    └─> Broad Research → [Cortex MoE Supervisor]
           ↳ Maps sub-tasks to → [Hypothesis Expert, Retrieval Expert, Writer Expert]
           ↳ Sent to → [Grounding Auditor] (Rejects unsupported claims)
    ↓
Synthesized Answer + Confidence Score + Citations
```

---

## ⚡ Performance Optimizations

### Local Constraints (RTX 3050 - 4GB VRAM target)
Atlas is explicitly engineered to wring maximum intelligence out of hardware-constrained systems:
- **Sequential Execution:** LangGraph handles tasks sequentially so VRAM isn't overwhelmed.
- **GBNF Grammar:** Forces small un-aligned models to spit out perfect JSON for predictable agent states.
- **Rustworkx Centrality:** High-performance graph walks offload heavy connection-finding from the LLM down to native C/Rust graph mathematics.
- **GLiNER Entity Extraction:** ~50x faster document ingestion compared to LLM-prompted extraction.

---

## 🔧 Configuration

All configuration is automatic for the desktop app. For development, set in `src/backend/.env`:

```env
# Database (SQLite - automatic, no setup needed)
DATABASE_URL=sqlite:///app.db

# Vector Store (Embedded Qdrant - automatic)
QDRANT_STORAGE_PATH=./qdrant_data

# Features
ENABLE_OUTPUT_VALIDATION=true
ENABLE_RERANKING=true
MOE_MAX_EXPERT_ROUNDS=3
```

---

## 📊 Model Information

### Included Models

**LLMs (Local via GGUF)**
- Optimized for Qwen 2.5 (3B-7B), Llama 3 (8B), Phi-3, Mistral, and DeepSeek variants.
- Automatically swapped by Meta-Router based on task complexity (uses smaller models for fast tasks, larger for deep agentic planning).

**Nomic Embed Text** - Embeddings
- ~350MB, runs locally via sentence-transformers.

**GLiNER Small** - Named Entity Recognition
- Fast, lightweight (~50MB), highly accurate token span predictor.

**Changelog:**
- **v1.0**: Agentic architecture. LangGraph swarm (`Navigator 2.0`, `Cortex MoE`). `Rustworkx` for high-performance localized subgraph extraction. Local-first GBNF grammar constraints. SQLite-only backend.

---

## 🤝 Contributing
We welcome contributions! See `CONTRIBUTING.md` for guidelines.

### Key Areas for Future Contribution
1. Adding persistent `ATLAS_MEMORY.md` to track user preferences across projects.
2. Expanding the Meta-Router intent classifiers.
3. Adding whitelisted Tool Calling Nodes (e.g. Google Scholar integration) for safe external API use.

---

## 📄 License
This project is licensed under the MIT License - see the `LICENSE` file for details.

---

**Last Updated:** February 2026  
**Version:** 1.0.0  
**Status:** Production Ready (Agentic Architecture Active) ✅
