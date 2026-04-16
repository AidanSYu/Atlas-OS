"""Scaffolding templates for each supported .atlas runtime type."""

from __future__ import annotations

import json

# ---------------------------------------------------------------------------
# Manifest generation (keyed by runtime)
# ---------------------------------------------------------------------------

_RUNTIME_DEFAULTS = {
    "python": {
        "description": "TODO: describe what this plugin does.",
        "tags": [],
        "input_schema": {
            "type": "object",
            "properties": {
                "smiles": {
                    "type": "string",
                    "description": "SMILES string of the input molecule.",
                },
            },
            "required": ["smiles"],
        },
    },
    "gguf": {
        "description": "TODO: describe your GGUF model plugin.",
        "tags": ["llm", "gguf"],
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "Prompt to send to the model.",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum tokens to generate.",
                    "default": 256,
                },
            },
            "required": ["prompt"],
        },
    },
    "onnx": {
        "description": "TODO: describe your ONNX model plugin.",
        "tags": ["ml", "onnx"],
        "input_schema": {
            "type": "object",
            "properties": {
                "input_data": {
                    "type": "object",
                    "description": "Input tensors as named arrays.",
                },
            },
            "required": ["input_data"],
        },
    },
    "native": {
        "description": "TODO: describe your native code plugin.",
        "tags": ["native"],
        "input_schema": {
            "type": "object",
            "properties": {
                "args": {
                    "type": "object",
                    "description": "Arguments to pass to the native function.",
                },
            },
            "required": ["args"],
        },
    },
    "generic": {
        "description": "TODO: describe your plugin.",
        "tags": [],
        "input_schema": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "object",
                    "description": "Plugin input data.",
                },
            },
            "required": ["input"],
        },
    },
}


def get_manifest(name: str, runtime: str) -> str:
    defaults = _RUNTIME_DEFAULTS.get(runtime, _RUNTIME_DEFAULTS["generic"])
    manifest = {
        "schema_version": "1.0",
        "name": name,
        "version": "0.1.0",
        "description": defaults["description"],
        "entry_point": "wrapper.py",
        "priority": 50,
        "tags": defaults["tags"],
        "runtime": runtime,
        "input_schema": defaults["input_schema"],
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "object"},
                "summary": {"type": "string"},
            },
        },
    }
    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------------------
# Wrapper templates
# ---------------------------------------------------------------------------

WRAPPER_PYTHON = '''\
"""Atlas plugin wrapper for {name} (runtime: python)."""

from typing import Any, Dict, Optional


class {class_name}:

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {{}}
        smiles = args.get("smiles", "")

        # ----- YOUR LOGIC HERE -----
        result = {{"input": smiles, "status": "not_implemented"}}
        # ---------------------------

        return {{
            "result": result,
            "summary": f"{name} processed {{smiles}}",
        }}


PLUGIN = {class_name}()
'''

WRAPPER_GGUF = '''\
"""Atlas plugin wrapper for {name} (runtime: gguf).

Wraps a GGUF model file embedded in the .atlas asset bundle.
The orchestrator extracts assets to a cache directory and injects
``__atlas_assets__`` into this module's namespace before execution.

Build with:
    Place your .gguf file in the plugin directory, then:
    atlas-sdk build {name}/ --encrypt --key YOUR_KEY
"""

from pathlib import Path
from typing import Any, Dict, Optional


class {class_name}:

    def __init__(self):
        self._llm = None

    def _ensure_loaded(self):
        if self._llm is not None:
            return

        # __atlas_assets__ is injected by the .atlas loader at runtime.
        # It points to the directory where embedded assets were extracted.
        assets: Path = __atlas_assets__  # noqa: F821 — injected by loader

        # Find the GGUF file in the extracted assets
        gguf_files = list(assets.glob("*.gguf"))
        if not gguf_files:
            raise FileNotFoundError(
                f"No .gguf file found in assets directory: {{assets}}"
            )
        model_path = str(gguf_files[0])

        # Load via llama-cpp-python (must be installed in the host environment)
        from llama_cpp import Llama
        self._llm = Llama(
            model_path=model_path,
            n_ctx=4096,
            n_gpu_layers=-1,  # use all available GPU layers
            verbose=False,
        )

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {{}}
        prompt = args.get("prompt", "")
        max_tokens = args.get("max_tokens", 256)

        self._ensure_loaded()

        output = self._llm(prompt, max_tokens=max_tokens)
        text = output["choices"][0]["text"]

        return {{
            "result": {{"generated_text": text}},
            "summary": f"{name} generated {{len(text)}} chars",
        }}


PLUGIN = {class_name}()
'''

WRAPPER_ONNX = '''\
"""Atlas plugin wrapper for {name} (runtime: onnx).

Wraps an ONNX model embedded in the .atlas asset bundle.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


class {class_name}:

    def __init__(self):
        self._session = None

    def _ensure_loaded(self):
        if self._session is not None:
            return

        assets: Path = __atlas_assets__  # noqa: F821 — injected by loader

        onnx_files = list(assets.glob("*.onnx"))
        if not onnx_files:
            raise FileNotFoundError(
                f"No .onnx file found in assets directory: {{assets}}"
            )

        import onnxruntime as ort
        self._session = ort.InferenceSession(str(onnx_files[0]))

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {{}}
        input_data = args.get("input_data", {{}})

        self._ensure_loaded()

        # Convert input arrays to numpy
        feeds = {{
            name: np.array(values, dtype=np.float32)
            for name, values in input_data.items()
        }}

        outputs = self._session.run(None, feeds)
        result = {{
            name.name: out.tolist()
            for name, out in zip(self._session.get_outputs(), outputs)
        }}

        return {{
            "result": result,
            "summary": f"{name} inference complete, {{len(result)}} output(s)",
        }}


PLUGIN = {class_name}()
'''

WRAPPER_NATIVE = '''\
"""Atlas plugin wrapper for {name} (runtime: native).

Wraps a native shared library (.dll / .so / .dylib) embedded in the
.atlas asset bundle.  Uses ctypes to call exported functions.

Build with:
    1. Compile your Rust/C/C++ code to a shared library.
    2. Place the .dll / .so / .dylib in the plugin directory.
    3. atlas-sdk build {name}/ --encrypt --key YOUR_KEY
"""

import ctypes
import platform
from pathlib import Path
from typing import Any, Dict, Optional


class {class_name}:

    def __init__(self):
        self._lib = None

    def _ensure_loaded(self):
        if self._lib is not None:
            return

        assets: Path = __atlas_assets__  # noqa: F821 — injected by loader

        # Detect platform and find the matching shared library
        system = platform.system().lower()
        if system == "windows":
            pattern = "*.dll"
        elif system == "darwin":
            pattern = "*.dylib"
        else:
            pattern = "*.so"

        libs = list(assets.glob(pattern))
        if not libs:
            raise FileNotFoundError(
                f"No shared library ({{pattern}}) found in assets: {{assets}}"
            )

        self._lib = ctypes.CDLL(str(libs[0]))

        # ----- CONFIGURE FUNCTION SIGNATURES HERE -----
        # Example for a function: double score(const char* smiles)
        #
        # self._lib.score.argtypes = [ctypes.c_char_p]
        # self._lib.score.restype = ctypes.c_double
        # ----------------------------------------------

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {{}}

        self._ensure_loaded()

        # ----- CALL YOUR NATIVE FUNCTION HERE -----
        # Example:
        # smiles = args.get("smiles", "").encode("utf-8")
        # score = self._lib.score(smiles)
        # result = {{"score": score}}
        result = {{"status": "not_implemented"}}
        # ------------------------------------------

        return {{
            "result": result,
            "summary": f"{name} native call complete",
        }}


PLUGIN = {class_name}()
'''

WRAPPER_GENERIC = '''\
"""Atlas plugin wrapper for {name} (runtime: generic).

A generic wrapper for arbitrary payloads embedded in the .atlas asset
bundle.  The assets directory is available as ``__atlas_assets__``.

This template works for any payload type — Java JARs, WASM modules,
data files, shell scripts, etc.  Use subprocess, ctypes, or any
Python binding to bridge to your payload.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


class {class_name}:

    async def invoke(
        self,
        arguments: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        args = arguments or {{}}
        assets: Path = __atlas_assets__  # noqa: F821 — injected by loader

        # ----- YOUR LOGIC HERE -----
        # Example: call a bundled executable
        # exe = assets / "my_tool.exe"
        # proc = subprocess.run([str(exe), args.get("input", "")],
        #                       capture_output=True, text=True, timeout=60)
        # result = {{"stdout": proc.stdout}}
        result = {{"assets_dir": str(assets), "status": "not_implemented"}}
        # ---------------------------

        return {{
            "result": result,
            "summary": f"{name} completed",
        }}


PLUGIN = {class_name}()
'''


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

WRAPPER_TEMPLATES = {
    "python": WRAPPER_PYTHON,
    "gguf": WRAPPER_GGUF,
    "onnx": WRAPPER_ONNX,
    "native": WRAPPER_NATIVE,
    "generic": WRAPPER_GENERIC,
}

SUPPORTED_RUNTIMES = list(WRAPPER_TEMPLATES.keys())


def get_wrapper(name: str, runtime: str) -> str:
    class_name = "".join(word.capitalize() for word in name.split("_")) + "Plugin"
    template = WRAPPER_TEMPLATES.get(runtime, WRAPPER_TEMPLATES["generic"])
    return template.format(name=name, class_name=class_name)
