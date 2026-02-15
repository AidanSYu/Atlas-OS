import sys
import os
import torch

print(f"Python: {sys.version}")
print(f"PyTorch: {torch.__version__}")

if torch.cuda.is_available():
    print(f"CUDA Available: YES")
    print(f"Device Count: {torch.cuda.device_count()}")
    print(f"Current Device: {torch.cuda.current_device()}")
    print(f"Device Name: {torch.cuda.get_device_name(0)}")
else:
    print(f"CUDA Available: NO")

try:
    import llama_cpp
    print(f"llama-cpp-python installed: {llama_cpp.__version__}")
except ImportError:
    print("llama-cpp-python not installed")
