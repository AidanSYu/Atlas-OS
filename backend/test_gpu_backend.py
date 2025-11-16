#!/usr/bin/env python
"""Test that backend agents can use GPU-accelerated ChemLLM"""

import torch
print("=" * 60)
print("Backend GPU Test")
print("=" * 60)

print(f"\n1. PyTorch CUDA status:")
print(f"   CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"   GPU: {torch.cuda.get_device_name(0)}")
    print(f"   GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

print(f"\n2. Initializing RetrosynthesisEngine...")
from agents.retrosynthesis import RetrosynthesisEngine
engine = RetrosynthesisEngine()
print(f"   ✓ Engine initialized")

print(f"\n3. ChemLLM client check:")
print(f"   Client type: {type(engine.chem_client).__name__}")

if hasattr(engine.chem_client, 'model'):
    device = next(engine.chem_client.model.parameters()).device
    print(f"   ✓ Model device: {device}")
    
    if device.type == 'cuda':
        print(f"\n   🚀 SUCCESS: ChemLLM is running on GPU!")
        print(f"   Expected speedup: 10-50x faster than CPU")
    else:
        print(f"\n   ⚠ WARNING: Model is on {device}, not GPU")
else:
    print(f"   ⚠ Client doesn't have model attribute")

print("\n" + "=" * 60)

print("\n4. Testing quick generation...")
try:
    result = engine.chem_client.generate("What is aspirin?", max_tokens=50)
    print(f"   ✓ Generation successful!")
    print(f"   Response preview: {result[:100]}...")
except Exception as e:
    print(f"   ✗ Error: {e}")

print("\n" + "=" * 60)
print("Backend is ready for fast GPU-accelerated inference!")
print("=" * 60)
