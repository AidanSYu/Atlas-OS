# Atlas Framework — domain-agnostic research OS

Atlas Framework is a standalone Windows research operating system that keeps knowledge and tools on-device.
The architecture runs offline around a single llama-cpp-powered Orchestrator that reasons over our living knowledge substrate, deterministically calls tools, and synthesizes grounded answers.

## Platform guarantees

- **Offline-first knowledge substrate**: SQLite, embedded Qdrant, and Rustworkx form the always-on retrieval backbone. This stack is treated like hardware—Atlas cannot run without it because every query lands there first. The Orchestrator ranks and reasons over hybrid RAG hits (vector search + graph topology + lightweight text search) before invoking any optional tool.
- **Single Orchestrator kernel**: `llama-cpp-python` loads `nvidia_Orchestrator-8B-IQ2_M.gguf`, feeds in schema-aware prompts, and repeatedly loops through plugins until no additional tool call is requested. Tool outputs re-enter the context so the kernel self-reflects without any static agent graphs or medium-term planners.
- **Universal Plugin Protocol**: Plugins live in `src/backend/plugins/` and expose `manifest.json` plus `wrapper.py`. The Orchestrator ingests each manifest, injects the schema into the system prompt, and routes JSON calls to the wrapper. Every plugin is optional; if missing, the Orchestrator simply skips it.
- **Domain-agnostic core**: Core retrieval/KG capabilities (search, Qdrant, graph walks, ingestion) never appear as optional plugins. They are always-available kernel tools powered by the Hybrid RAG services.

## Getting started

1. Install the app via the standard MSI bundle.
2. Drop `nvidia_Orchestrator-8B-IQ2_M.gguf` into the models directory configured via environment variables (see `src/backend/app/core/config.py`).
3. Place `nomic-embed-text-v1.5` for embeddings and `gliner_small-v2.1` for entity extraction alongside the orchestrator model.
4. Launch Atlas; the orchestrator immediately loads the manifest catalog and the always-on core toolset.

## Developer workflow

### Directory highlights

- `src/backend/app/atlas_plugin_system/`: unified orchestrator code, `PluginRegistry`, and core tool catalog definitions.
- `src/backend/plugins/`: each plugin is a folder with `manifest.json` describing its schema and `wrapper.py` for execution.
- `src/backend/app/api/framework_routes.py`: the FastAPI surface for health checks, plugin catalogs, and orchestration requests.
- `src/backend/app/core/config.py`: resolves absolute paths for models, databases, and plugin directories.

### Local run commands

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

### Model installation

Set env vars (or edit `.env`) to point to your assets:

```env
MODELS_DIR=C:/path/to/models
DATABASE_PATH=C:/path/to/atlas.db
QDRANT_STORAGE_PATH=C:/path/to/qdrant_storage
ATLAS_PLUGIN_DIR=C:/path/to/ContAInuumAtlas/src/backend/plugins
```

Place `nvidia_Orchestrator-8B-IQ2_M.gguf` inside `MODELS_DIR`, and include the embedding + NER folders listed above. The orchestrator loads lazily on first framework run.

## Architecture summary

1. Frontend (Next.js/Tauri shell) → API `framework_routes`.
2. Orchestrator reads `PluginRegistry` plus built-in `CoreToolRegistry` (search, vector query, graph walk).
3. User prompt + manifest schemas → llama-cpp loop.
4. JSON tool calls are routed to plugin wrappers or core tool handlers; results are appended to the context.
5. Once no tool is requested, the orchestrator returns a final synthesis to the frontend.

## Plugin protocol

Atlas supports three plugin packaging formats. The orchestrator discovers all of them automatically when they are placed in the `plugins/` directory.

### Directory plugins (development)

The simplest format — a folder with two files:

- `manifest.json` — declares the tool name, description, input/output schemas, priority, and tags.
- `wrapper.py` — exposes a `PLUGIN` object (or `create_plugin()` / `invoke()` function) that the orchestrator calls at runtime.

Directory plugins are ideal during development because you can edit source files and the orchestrator picks up changes on the next refresh.

### `.atlas` packages (distribution & IP protection)

`.atlas` is the Atlas Framework's custom binary container format for distributing plugins. It compiles Python source into bytecode so the original code is not shipped, and optionally encrypts the bytecode with AES-256-GCM to protect proprietary IP.

#### File layout

```
Offset   Size        Section
──────   ────        ───────
0        8 bytes     Magic: ATLAS\x00\x01\x00
8        4 bytes     Flags (uint32-LE): bit 0 = encrypted, bit 1 = has embedded assets
12       4 bytes     Manifest size (uint32-LE)
16       4 bytes     Code size (uint32-LE)
20       4 bytes     Assets size (uint32-LE)
24       variable    Manifest (cleartext JSON — always readable without a key)
24+M     variable    Code (compiled Python bytecode, optionally AES-256-GCM encrypted)
24+M+C   variable    Assets (zip bundle of data files, optionally encrypted)
EOF-32   32 bytes    Signature (HMAC-SHA256 over all preceding bytes)
```

#### Design decisions

| Concern | How `.atlas` handles it |
|---|---|
| **Orchestrator discovery** | The manifest is always cleartext. The orchestrator reads tool name, description, and schemas without needing a decryption key. |
| **IP protection** | Source code is compiled to Python bytecode (`marshal`), then optionally encrypted with AES-256-GCM. Without the key, the code section is indistinguishable from random bytes. |
| **Key derivation** | Encryption keys are derived from a user-supplied passphrase via PBKDF2-HMAC-SHA256 with 600,000 iterations, making brute-force expensive. |
| **Tamper detection** | An HMAC-SHA256 signature covers the entire file. The orchestrator rejects packages where the signature does not match. |
| **Embedded assets** | Model weights, lookup tables, or data files can be bundled as a zip archive inside the `.atlas` container. |
| **Zero config loading** | Drop a `.atlas` file into `plugins/` and the orchestrator loads it on the next refresh — no configuration changes required. |

#### Encryption details

When `--encrypt` is used, the code section is structured as:

```
SALT (16 bytes) | NONCE (12 bytes) | AES-256-GCM ciphertext + tag
```

At runtime, the orchestrator reads the `ATLAS_PLUGIN_KEY` environment variable to derive the decryption key. If a `.atlas` package is encrypted and no key is set, the orchestrator logs a warning and skips the plugin.

### Zip plugins

Zip archives containing `manifest.json` + `wrapper.py` are also supported. These behave like directory plugins but are easier to email or upload. For IP protection, use `.atlas` instead.

---

## Atlas SDK

The Atlas SDK (`atlas-sdk`) is a standalone CLI tool that lets researchers build, inspect, and verify `.atlas` plugin packages. It ships as its own Python package with minimal dependencies (`cryptography`, `pydantic`) — no Atlas backend installation required.

### Installation

```bash
# From PyPI (when published)
pip install atlas-sdk

# From the repo directly
pip install git+https://github.com/yourorg/ContAInuumAtlas.git#subdirectory=sdk

# Local development
cd sdk
pip install -e .
```

### Commands

#### `atlas-sdk init <name>` — Scaffold a new plugin

```bash
atlas-sdk init score_del_hits
```

Creates a directory with a starter `manifest.json` and `wrapper.py`:

```
score_del_hits/
├── manifest.json   ← edit description, schemas, tags
└── wrapper.py      ← implement your logic here
```

The `--runtime` flag generates a wrapper template tailored to your payload type:

```bash
atlas-sdk init my_plugin                        # Pure Python (default)
atlas-sdk init my_llm -r gguf                   # GGUF model wrapper
atlas-sdk init my_model -r onnx                 # ONNX model wrapper
atlas-sdk init my_scorer -r native              # Rust/C/C++ shared library
atlas-sdk init my_tool -r generic               # Arbitrary binary/subprocess
```

The generated `wrapper.py` contains a skeleton class with the `invoke(arguments, context)` signature the orchestrator expects. Fill in your logic and you're ready to build.

#### `atlas-sdk build [directory]` — Compile to `.atlas`

```bash
# Open-source plugin (bytecode only, no encryption)
atlas-sdk build score_del_hits

# Proprietary plugin (AES-256-GCM encrypted)
atlas-sdk build score_del_hits --encrypt --key "my-secret-key"

# Or use an environment variable for the key
export ATLAS_PLUGIN_KEY="my-secret-key"
atlas-sdk build score_del_hits --encrypt

# Custom output path
atlas-sdk build score_del_hits -o dist/score_del_hits.atlas
```

The build step:
1. Validates `manifest.json` against the Atlas plugin schema.
2. Compiles `wrapper.py` to Python bytecode (no raw source in the output).
3. Collects any extra files in the directory as an embedded asset bundle.
4. Optionally encrypts the code and asset sections with AES-256-GCM.
5. Signs the entire package with HMAC-SHA256.
6. Writes the `.atlas` binary.

#### `atlas-sdk inspect <file>` — View package metadata

```bash
atlas-sdk inspect score_del_hits.atlas
```

```
Atlas Plugin Package: score_del_hits.atlas
  File size:   1,290 bytes
  Encrypted:   yes
  Has assets:  no

  Name:        score_del_hits
  Version:     0.1.0
  Description: Score DEL hits using a custom ML model
  Priority:    50
  Tags:        chemistry, del, ml
```

Inspection never requires a decryption key — the manifest is always cleartext.

#### `atlas-sdk verify <file>` — Check signature integrity

```bash
atlas-sdk verify score_del_hits.atlas
```

```
PASS: score_del_hits.atlas — signature is valid
```

Returns exit code 0 on success, 1 if the file has been tampered with.

### End-to-end example: custom DEL scoring plugin

```bash
# 1. Scaffold
atlas-sdk init score_del_hits
cd score_del_hits

# 2. Edit manifest.json — set the name, description, input schema
# 3. Edit wrapper.py — load your model in invoke(), score the SMILES input

# 4. Build with IP protection
atlas-sdk build . --encrypt --key "lab-secret-2026"

# 5. Distribute: send score_del_hits.atlas to collaborators
#    They drop it into their Atlas plugins/ directory

# 6. On their machine, set the decryption key
#    export ATLAS_PLUGIN_KEY="lab-secret-2026"

# 7. Start Atlas — the orchestrator discovers and loads the plugin automatically
```

### Batch compilation

To compile all existing directory plugins at once:

```bash
cd src/backend
python scripts/compile_all_plugins.py

# With encryption
python scripts/compile_all_plugins.py --encrypt --key "your-key"

# Custom output directory
python scripts/compile_all_plugins.py --output-dir dist/plugins
```

### Supported runtimes

The `.atlas` format wraps any computational payload, not just Python. The wrapper is always a thin Python shim — the heavy payload (model weights, compiled binaries, data files) goes in the embedded asset bundle. At load time, the orchestrator extracts assets to a cache directory and injects the path as `__atlas_assets__` into the wrapper's namespace.

#### `python` — Pure Python plugins

The default. The wrapper contains all logic directly. No asset bundle needed.

```bash
atlas-sdk init predict_properties
# Edit wrapper.py with your RDKit/scipy/etc. logic
atlas-sdk build predict_properties
```

#### `gguf` — LLM model plugins

Wrap a GGUF model (quantized LLM) as an Atlas tool. The model file is embedded in the asset bundle and loaded via `llama-cpp-python` at runtime.

```bash
atlas-sdk init domain_expert -r gguf
# Place your .gguf file in the domain_expert/ directory
cp my-fine-tuned-model-Q4_K_M.gguf domain_expert/
atlas-sdk build domain_expert --encrypt --key "secret"
```

The generated wrapper automatically finds the `.gguf` file in `__atlas_assets__` and loads it. The orchestrator can then call this plugin as a tool — for example, a domain-specific LLM fine-tuned on patent literature or chemical safety data.

#### `onnx` — Deep learning model plugins

Wrap an ONNX model (PyTorch, TensorFlow, scikit-learn exports) as an Atlas tool. Uses `onnxruntime` for inference.

```bash
atlas-sdk init bioactivity_predictor -r onnx
# Export your model to ONNX and place it in the directory
cp model.onnx bioactivity_predictor/
atlas-sdk build bioactivity_predictor --encrypt --key "secret"
```

Works for any model exportable to ONNX: GNNs trained on molecular graphs, transformers fine-tuned on DEL data, random forests for ADMET prediction, etc.

#### `native` — Rust, C, C++ shared libraries

Wrap a compiled shared library (`.dll`, `.so`, `.dylib`) using `ctypes`. Ideal for high-performance scoring functions, custom docking engines, or proprietary algorithms written in systems languages.

```bash
atlas-sdk init fast_docking -r native
# Compile your Rust/C code to a shared library
cargo build --release
cp target/release/fast_docking.dll fast_docking/   # or .so on Linux
atlas-sdk build fast_docking --encrypt --key "secret"
```

Edit the generated `wrapper.py` to configure `ctypes` function signatures matching your library's exported functions.

#### `generic` — Anything else

For payloads that don't fit the other categories: Java JARs, WebAssembly modules, standalone executables, R scripts, Julia code, data lookup tables, etc. The wrapper uses `subprocess` or any Python binding to call into the bundled payload.

```bash
atlas-sdk init custom_tool -r generic
# Place any files in the directory
cp my_tool.exe custom_tool/
cp lookup_table.csv custom_tool/
atlas-sdk build custom_tool
```

### How asset embedding works

When `atlas-sdk build` runs, any file in the plugin directory that isn't `manifest.json` or `wrapper.py` is automatically collected into a zip archive and embedded in the `.atlas` asset section. At runtime:

1. The orchestrator reads the `.atlas` file and extracts the asset bundle to a persistent cache directory (`ATLAS_ASSET_CACHE` env var, or system temp).
2. The cache is keyed by a content hash — identical assets are never extracted twice.
3. The extraction path is injected into the wrapper module as `__atlas_assets__` (a `Path` object).
4. The wrapper uses this path to locate model files, shared libraries, data, etc.

If the `.atlas` package is encrypted, assets are encrypted alongside the code. The decryption key (`ATLAS_PLUGIN_KEY`) is required at runtime.

---

## Monitoring & telemetry

- The orchestrator exposes `/api/framework/plugins` and `/api/framework/run` (see `framework_routes`) for health and tool invocation.
- Because the system runs locally, inspect logs in the backend terminal or via Tauri's dev console.
