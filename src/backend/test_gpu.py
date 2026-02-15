#!/usr/bin/env python
"""Quick test to verify GPU is working with llama-cpp-python."""

import sys
import logging

# Setup logging to see CUDA initialization
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(levelname)s - %(message)s'
)

print("=" * 70)
print("GPU INITIALIZATION TEST")
print("=" * 70)

# Test 1: Check NVIDIA GPU
print("\n[1] Checking NVIDIA GPU...")
try:
    import subprocess
    result = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'], 
                          capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        print(f"GPU Found: {result.stdout.strip()}")
    else:
        print("nvidia-smi failed")
except Exception as e:
    print(f"Could not check GPU: {e}")

# Test 2: Import llama-cpp-python
print("\n[2] Importing llama-cpp-python...")
try:
    from llama_cpp import Llama
    print("SUCCESS: llama-cpp-python imported")
except ImportError as e:
    print(f"FAILED: {e}")
    sys.exit(1)

# Test 3: Load LLMService
print("\n[3] Initializing LLMService...")
try:
    from app.services.llm import LLMService
    llm_service = LLMService()
    print("SUCCESS: LLMService created")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

# Test 4: Load model
print("\n[4] Loading language model (this may take a moment)...")
try:
    llm_service._load_llm()
    if llm_service._llm == "FALLBACK":
        print("WARNING: Using fallback mode - model not found")
    else:
        print(f"SUCCESS: Model loaded")
        print(f"  - Model: {llm_service._active_model_name}")
        print(f"  - Device: {llm_service._device}")
        print(f"  - GPU Layers: {llm_service._gpu_layers}")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
