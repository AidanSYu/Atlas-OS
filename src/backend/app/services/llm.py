"""
LLM Service - Bundled LLM and embedding service using llama-cpp-python.

Replaces Ollama for standalone desktop app deployment.
Uses:
- llama-cpp-python for text generation (Llama 3 GGUF)
- sentence-transformers for embeddings (nomic-embed-text-v1.5)
"""
from pathlib import Path
from typing import List, Optional
import logging
import os
import sys
import asyncio
import threading
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ensure CUDA runtime DLLs (installed via pip nvidia-* packages) are findable
# on Windows before llama_cpp tries to load its shared libraries.
# ---------------------------------------------------------------------------
_cuda_dll_dirs_added = False


def _add_cuda_dll_directories():
    """Register NVIDIA pip-package DLL directories with Windows DLL loader.
    Looks in Python site-packages (where pip installs nvidia-* wheels) and
    in the project/backend folder in case libs were extracted there.
    """
    global _cuda_dll_dirs_added
    if _cuda_dll_dirs_added or sys.platform != "win32":
        return
    _cuda_dll_dirs_added = True

    # Pip nvidia-* wheels put DLLs in bin/ (cudart64_12.dll, cublas64_12.dll, etc.)
    nvidia_lib_subdirs = [
        "nvidia/cublas/bin",
        "nvidia/cuda_runtime/bin",
        "nvidia/cublas/lib",
        "nvidia/cuda_runtime/lib",
        "nvidia/cuda_runtime/lib/x64",
        "nvidia/cufft/lib",
        "nvidia/cusparse/lib",
    ]

    dirs_to_check = []

    try:
        import site
        # User site-packages (pip --user installs)
        user_site = site.getusersitepackages()
        if user_site:
            dirs_to_check.append(Path(user_site))
        # System site-packages
        for sp in site.getsitepackages():
            dirs_to_check.append(Path(sp))
    except Exception:
        pass

    # Project folder: backend/app/services/llm.py -> backend = parents[2], project root = parents[3]
    try:
        _backend = Path(__file__).resolve().parents[2]
        _project_root = _backend.parent
        dirs_to_check.extend([_project_root, _backend])
    except Exception:
        pass

    for base in dirs_to_check:
        for subdir in nvidia_lib_subdirs:
            candidate = base / subdir
            if candidate.is_dir():
                try:
                    os.add_dll_directory(str(candidate))
                    logger.info("Added CUDA DLL directory: %s", candidate)
                except Exception as e:
                    logger.debug("Could not add DLL dir %s: %s", candidate, e)

    # CRITICAL: Add llama_cpp/lib directory itself to DLL search path
    try:
        import importlib.util
        spec = importlib.util.find_spec("llama_cpp")
        if spec and spec.origin:
            lc_lib = Path(spec.origin).resolve().parent / "lib"
            if lc_lib.is_dir():
                try:
                    os.add_dll_directory(str(lc_lib))
                    logger.info("Added llama_cpp lib directory: %s", lc_lib)
                except Exception as e:
                    logger.warning("Could not add llama_cpp lib dir: %s", e)
                
                # Also prepend to PATH as a fallback
                existing_path = os.environ.get("PATH", "")
                if str(lc_lib) not in existing_path:
                    os.environ["PATH"] = str(lc_lib) + os.pathsep + existing_path
                    logger.info("Added llama_cpp lib to PATH")
    except Exception as e:
        logger.debug("Could not locate llama_cpp lib directory: %s", e)

    # Prepend nvidia bin dirs to PATH so the loader finds cudart/cublas when loading ggml-cuda.dll
    path_additions = []
    for base in dirs_to_check:
        for subdir in ("nvidia/cuda_runtime/bin", "nvidia/cublas/bin"):
            candidate = base / subdir
            if candidate.is_dir():
                path_additions.append(str(candidate))
    if path_additions:
        existing = os.environ.get("PATH", "")
        new_path = os.pathsep.join(path_additions) + os.pathsep + existing
        os.environ["PATH"] = new_path
        logger.info("Prepended %d CUDA bin dir(s) to PATH", len(path_additions))

    # Copy CUDA runtime DLLs next to llama_cpp lib so ggml-cuda.dll can load them
    try:
        import shutil
        import importlib.util
        spec = importlib.util.find_spec("llama_cpp")
        lc_lib = Path(spec.origin).resolve().parent / "lib" if spec and spec.origin else None
        if lc_lib and (lc_lib / "llama.dll").exists():
            for subdir, dll_name in [
                ("nvidia/cuda_runtime/bin", "cudart64_12.dll"),
                ("nvidia/cublas/bin", "cublas64_12.dll"),
                ("nvidia/cublas/bin", "cublasLt64_12.dll"),
            ]:
                for base in dirs_to_check:
                    src = base / subdir / dll_name
                    if src.is_file():
                        dest = lc_lib / dll_name
                        if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                            try:
                                shutil.copy2(src, dest)
                                logger.info("Copied CUDA DLL to llama_cpp lib: %s", dll_name)
                            except Exception as e:
                                logger.debug("Could not copy %s: %s", src, e)
                        break
    except Exception as e:
        logger.debug("Could not copy CUDA DLLs: %s", e)


# Call DLL setup at module import time to ensure directories are registered
# before any code tries to import llama_cpp
if sys.platform == "win32":
    try:
        _add_cuda_dll_directories()
    except Exception as e:
        logger.debug("Early DLL directory setup failed (non-fatal): %s", e)


# Lazy imports to avoid loading heavy models at import time
_llm_instance = None
_embedder_instance = None

# Default GPU layers for partial offload
# RTX 3050 (4GB VRAM): Use 35 layers for Llama 3 8B-Instruct (Q4_K_M quantization)
# This allows ~3.2GB GPU usage, leaving headroom for inference
DEFAULT_GPU_LAYERS = 35


def _resolve_gpu_layers() -> int:
    """Resolve GPU layer count from env with a safe default."""
    raw = os.environ.get("ATLAS_GPU_LAYERS", "").strip()
    if not raw:
        return DEFAULT_GPU_LAYERS
    if raw.lower() == "auto":
        return -1
    try:
        return int(raw)
    except ValueError:
        return DEFAULT_GPU_LAYERS


class LLMService:
    """Bundled LLM service using llama-cpp-python and sentence-transformers.
    
    This service provides:
    - Text generation using Llama 3 (quantized GGUF) with proper chat template
    - Text embeddings using nomic-embed-text-v1.5
    - Runtime model switching
    
    Models are loaded from the MODELS_DIR specified in settings.
    """
    
    _instance: Optional['LLMService'] = None
    
    def __init__(self, models_dir: Optional[Path] = None):
        """Initialize LLM service.
        
        Args:
            models_dir: Path to directory containing models.
                       Defaults to settings.MODELS_DIR.
        """
        self.models_dir = Path(models_dir or settings.MODELS_DIR)
        self._llm = None
        self._embedder = None
        self._embedding_dim = 768  # nomic-embed-text dimension
        self._active_model_name: Optional[str] = None
        self._model_type: str = "llama"
        self._gpu_layers: int = _resolve_gpu_layers()
        self._device: str = "unloaded"
        self._llm_last_error: Optional[str] = None
        # Lock to prevent concurrent model loading/switching
        self._model_lock = asyncio.Lock()
        # Lock to prevent concurrent embedding generation (Nomic v1.5 race condition fix)
        self._embed_lock = threading.Lock()
        self._is_initializing = False
        
        logger.info(f"LLMService initializing with models_dir: {self.models_dir}")
    
    # ----------------------------------------------------------------
    # Llama 3 Chat Template
    # ----------------------------------------------------------------

    @staticmethod
    def _format_llama3_prompt(system_msg: str, user_msg: str) -> str:
        """Format a prompt using the Llama 3 Instruct chat template.
        
        Args:
            system_msg: The system instruction (role/persona).
            user_msg: The user's message / query with context.
            
        Returns:
            Formatted prompt string with Llama 3 special tokens.
        """
        return (
            "<|start_header_id|>system<|end_header_id|>\n\n"
            f"{system_msg}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
            f"{user_msg}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
        )

    @staticmethod
    def _format_qwen_prompt(system_msg: str, user_msg: str) -> str:
        """Format a prompt using the Qwen ChatML template."""
        return (
            f"<|im_start|>system\n{system_msg}<|im_end|>\n"
            f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

    @staticmethod
    def _format_phi3_prompt(system_msg: str, user_msg: str) -> str:
        """Format a prompt using the Phi-3 chat template.
        
        Phi-3 template:
        <|system|>
        failed to find system prompt!
        <|end|>
        <|user|>
        {msg}<|end|>
        <|assistant|>
        """
        # Phi-3 typically doesn't use a system prompt in the standard template,
        # but the instruct version supports it via <|system|>.
        return (
            f"<|system|>\n{system_msg}<|end|>\n"
            f"<|user|>\n{user_msg}<|end|>\n"
            "<|assistant|>\n"
        )

    # ----------------------------------------------------------------
    # Model Loading
    # ----------------------------------------------------------------

    def _load_llm(self, model_name: Optional[str] = None):
        """Load the LLM model (lazy loading).
        
        Args:
            model_name: Optional specific GGUF filename to load.
                       If None, auto-detects from models_dir.
        """
        if self._llm is not None and self._llm != "FALLBACK":
            return
        
        # Ensure CUDA DLL directories are registered before importing llama_cpp
        _add_cuda_dll_directories()
        
        try:
            from llama_cpp import Llama
        except ImportError as e:
            error_msg = str(e)
            self._llm_last_error = error_msg
            if "llama.dll" in error_msg or "shared library" in error_msg.lower():
                logger.error("Failed to load llama.dll - missing dependencies: %s", error_msg)
                logger.error("Check that CUDA DLLs are in .venv/Lib/site-packages/llama_cpp/lib/")
            
            import sys
            if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
                logger.warning(
                    "LLM runtime not available in this installation (bundled app). "
                    "Use development mode from source for full LLM support, or reinstall with a build that includes the LLM backend. Error: %s",
                    e,
                )
            else:
                logger.warning(
                    "llama-cpp-python not installed. Text generation will use fallback. "
                    "Install with: pip install llama-cpp-python (in your backend venv or environment)."
                )
            self._llm = "FALLBACK"  # Mark as fallback mode
            self._device = "cpu"
            return
        
        model_path = None
        
        # If a specific model was requested, look for it directly
        if model_name:
            candidate = self.models_dir / model_name
            if candidate.exists():
                model_path = candidate
            else:
                logger.warning(f"Requested model '{model_name}' not found in {self.models_dir}")

        # Auto-detect if no specific model or requested model not found
        if model_path is None:
            model_patterns = [
                "Phi-3.5-mini-instruct*.gguf",  # Priority 1: SOTA Small Model
                "Qwen2.5-3B-Instruct*.gguf",    # Priority 2: Fast Small Model
                "llama-3-8b-instruct*.gguf",    # Priority 3: Legacy Standard
                "Meta-Llama-3-8B-Instruct*.gguf",
                "*.gguf"
            ]
            for pattern in model_patterns:
                matches = list(self.models_dir.glob(pattern))
                if matches:
                    model_path = matches[0]
                    break
        
        if not model_path or not model_path.exists():
            logger.warning(
                f"LLM model not found in {self.models_dir}. Using fallback mode. "
                f"Download a .gguf model for full functionality."
            )
            self._llm = "FALLBACK"
            self._active_model_name = None
            self._device = "cpu"
            return
        
        logger.info(f"Loading LLM from {model_path}")
        logger.info(f"GPU layers config: {self._gpu_layers}")
        self._llm = Llama(
            model_path=str(model_path),
            n_ctx=4096,
            n_gpu_layers=self._gpu_layers,  # Partial offload for 4GB VRAM
            verbose=True,  # Enable verbose to see CUDA initialization
            n_threads=4
        )
        self._active_model_name = model_path.name
        
        # Detect model type for chat templates
        name_lower = model_path.name.lower()
        if "phi" in name_lower:
             self._model_type = "phi3"
        elif "qwen" in name_lower:
             self._model_type = "qwen"
        else:
             self._model_type = "llama"
        
        # Verify actual GPU availability using torch (since we rely on system CUDA)
        # This prevents the UI from showing "GPU" just because we REQUESTED layers
        try:
            import torch
            has_cuda = torch.cuda.is_available()
        except ImportError:
            has_cuda = False

        if self._gpu_layers > 0 and has_cuda:
            self._device = "gpu"
        else:
            self._device = "cpu"
            if self._gpu_layers > 0:
                logger.warning("GPU layers requested but CUDA not available/detected. Reporting CPU.")

        logger.info(f"LLM loaded successfully: {self._active_model_name}")
        logger.info(f"Model type: {self._model_type}, Device: {self._device}")
        logger.info(f"GPU layers: {self._gpu_layers}, actual device: {self._device}")
    
    def _load_embedder(self):
        """Load the embedding model (lazy loading)."""
        if self._embedder is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        # Look for embedding model directory
        embed_patterns = [
            "nomic-embed-text-v1.5",
            "nomic-embed-text*",
        ]
        
        embed_path = None
        for pattern in embed_patterns:
            matches = list(self.models_dir.glob(pattern))
            if matches:
                embed_path = matches[0]
                break
        
        # nomic-embed uses custom code (nomic-bert-2048) - trust_remote_code required
        # Must pass as direct arg; model_kwargs is not forwarded to AutoConfig.from_pretrained
        st_kwargs = {"trust_remote_code": True}
        if embed_path and embed_path.exists():
            logger.info(f"Loading embedding model from {embed_path}")
            self._embedder = SentenceTransformer(str(embed_path), **st_kwargs)
        else:
            # Fall back to downloading from HuggingFace (first run)
            logger.warning(
                f"Embedding model not found in {self.models_dir}. "
                "Downloading from HuggingFace..."
            )
            self._embedder = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", **st_kwargs)
        
        logger.info("Embedding model loaded successfully")
    
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None
    ) -> str:
        """Generate text completion.
        
        Args:
            prompt: The prompt to complete (should already be formatted
                   with the appropriate chat template).
            temperature: Sampling temperature (lower = more deterministic)
            max_tokens: Maximum tokens to generate
            stop: List of stop sequences. Defaults to Llama 3 stop tokens.
            
        Returns:
            Generated text string
        """
        # Lazy load model
        if self._llm is None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_llm)
        
        # Handle fallback mode (no llama-cpp-python or no model)
        if self._llm == "FALLBACK":
            logger.warning("LLM generation in fallback mode - returning placeholder response")
            import sys
            if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
                msg = (
                    "LLM is not available in this installation. Run Atlas from source (development mode) for full LLM support."
                )
            else:
                msg = (
                    "LLM model is not available. Install llama-cpp-python (pip install llama-cpp-python) and add a GGUF model to the models folder."
                )
            return (
                f"I cannot generate a detailed response because the LLM is not available. {msg} "
                "The retrieval system did find relevant documents."
            )
        
        # Default stop tokens based on loaded model
        if stop is None:
            if self._model_type == "qwen":
                stop = ["<|im_end|>", "<|endoftext|>"]
            elif self._model_type == "phi3":
                stop = ["<|end|>", "<|endoftext|>"]
            else:
                stop = ["<|eot_id|>", "<|end_of_text|>"]
        
        # Run generation in executor to not block event loop
        loop = asyncio.get_running_loop()
        
        def _generate():
            output = self._llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
                echo=False
            )
            return output["choices"][0]["text"].strip()
        
        return await loop.run_in_executor(None, _generate)
    
    async def generate_chat(
        self,
        system_message: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        stop: Optional[List[str]] = None
    ) -> str:
        """Generate a response using the active model's chat template.
        
        Convenience method that formats the prompt with the proper
        Llama 3 Instruct chat template before calling generate().
        
        Args:
            system_message: System instruction (role, persona, rules).
            user_message: User query / content.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            stop: Optional custom stop sequences.
            
        Returns:
            Generated text string
        """
        if self._llm is None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_llm)

        if self._model_type == "qwen":
            prompt = self._format_qwen_prompt(system_message, user_message)
        elif self._model_type == "phi3":
            prompt = self._format_phi3_prompt(system_message, user_message)
        else:
            prompt = self._format_llama3_prompt(system_message, user_message)
            
        return await self.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )
    
    async def embed(self, text: str) -> List[float]:
        """Generate embedding vector for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        # Lazy load model
        if self._embedder is None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_embedder)
        
        # Run embedding in executor to not block event loop
        loop = asyncio.get_running_loop()
        
        def _embed():
            with self._embed_lock:
                return self._embedder.encode(text).tolist()
        
        return await loop.run_in_executor(None, _embed)
    
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        # Lazy load model
        if self._embedder is None:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._load_embedder)
        
        # Run batch embedding in executor
        loop = asyncio.get_running_loop()
        
        def _embed_batch():
            with self._embed_lock:
                return self._embedder.encode(texts).tolist()
        
        return await loop.run_in_executor(None, _embed_batch)
    
    @property
    def embedding_dimension(self) -> int:
        """Return the embedding dimension."""
        return self._embedding_dim
    
    @property
    def active_model_name(self) -> Optional[str]:
        """Return the name of the currently loaded GGUF model, or None."""
        return self._active_model_name

    def get_status(self) -> dict:
        """Return LLM status for UI display."""
        return {
            "active_model": self._active_model_name,
            "model_type": self._model_type,
            "device": self._device,
            "gpu_layers": self._gpu_layers,
            "fallback": self._llm == "FALLBACK",
        }
    
    def list_available_models(self) -> List[str]:
        """List all .gguf files in the models directory."""
        if not self.models_dir.exists():
            return []
        return sorted(p.name for p in self.models_dir.glob("*.gguf"))
    
    async def load_model(self, model_name: str) -> str:
        """Unload the current LLM and load a different GGUF model.
        
        This method is LOCKED to prevent concurrent model switching during active queries.
        Subsequent load_model() calls will wait for the first to complete.
        
        Args:
            model_name: Filename of the .gguf model in MODELS_DIR.
            
        Returns:
            Name of the newly loaded model.
            
        Raises:
            FileNotFoundError: If the model file does not exist.
            RuntimeError: If llama-cpp-python is not available.
            TimeoutError: If another query/operation holds the lock too long.
        """
        # Acquire lock with timeout to prevent permanent blocking
        try:
            await asyncio.wait_for(self._model_lock.acquire(), timeout=120)
            try:
                logger.info(f"Model switch lock acquired, switching to: {model_name}")
                return await self._do_load_model(model_name)
            finally:
                self._model_lock.release()
        except asyncio.TimeoutError:
            raise RuntimeError(
                "Model switch timed out - a query or operation is holding the model lock. "
                "Please wait for the current operation to complete before switching models."
            )
    
    async def _do_load_model(self, model_name: str) -> str:
        """Internal model loading with lock already held."""
        model_path = self.models_dir / model_name
        if not model_path.exists():
            raise FileNotFoundError(f"Model '{model_name}' not found in {self.models_dir}")
        
        # If already loaded, skip
        if self._active_model_name == model_name and self._llm is not None and self._llm != "FALLBACK":
            logger.info(f"Model '{model_name}' is already loaded")
            return model_name
        
        # Unload current model to free memory
        if self._llm is not None and self._llm != "FALLBACK":
            logger.info(f"Unloading current model: {self._active_model_name}")
            del self._llm
            self._llm = None
            self._active_model_name = None
            # Encourage garbage collection to free VRAM
            import gc
            gc.collect()
            logger.info("Previous model unloaded and memory freed")
        
        # Load the new model
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._load_llm, model_name)
        
        if self._llm == "FALLBACK":
            detail = self._llm_last_error or "llama-cpp-python failed to initialize"
            raise RuntimeError(
                "Failed to load model. "
                "Ensure llama-cpp-python is installed and its llama.dll dependencies are available. "
                f"Last error: {detail}"
            )
        
        return self._active_model_name
    
    async def initialize_default_model(self) -> str:
        """Load the default GPU-accelerated model at startup.
        
        Returns:
            Name of the loaded model, or empty string if no model available.
        """
        if self._is_initializing:
            logger.info("Model initialization already in progress")
            return self._active_model_name or ""
        
        self._is_initializing = True
        try:
            available = self.list_available_models()
            if not available:
                logger.warning("No GGUF models found in models directory")
                self._device = "cpu"
                self._active_model_name = None
                return ""
            
            # Load the first available model
            model_to_load = available[0]
            logger.info(f"Loading default model at startup: {model_to_load}")
            
            async with self._model_lock:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._load_llm, model_to_load)
            
            if self._llm == "FALLBACK":
                logger.error(f"Failed to load default model: {self._llm_last_error}")
                self._device = "cpu"
                return ""
            
            logger.info(f"Default model loaded successfully: {self._active_model_name} on {self._device}")
            return self._active_model_name or ""
        finally:
            self._is_initializing = False
    
    @classmethod
    def get_instance(cls) -> 'LLMService':
        """Get or create singleton instance.
        
        Note: Does not initialize the model. Call initialize_default_model() separately
        during application startup.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Convenience function for getting the service
def get_llm_service() -> LLMService:
    """Get the singleton LLM service instance."""
    return LLMService.get_instance()
