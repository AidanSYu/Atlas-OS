# Performance Optimization Guide

## Current Performance Status

**Your setup is running on CPU**, which is why models are slow.

### Current Expected Timing:
- **Pathway generation**: 30-60 seconds (Ollama llama3.1)
- **Deep analysis per pathway**: **3-5 minutes** (multiple ChemLLM calls on CPU)
  - Researcher analysis: ~45s
  - Retrosynthesis per candidate: ~45s  
  - Manufacturability per candidate: ~45s
  - Total for 2-3 candidates: ~3-5 minutes

## Why Is It Slow?

1. **No GPU**: PyTorch CPU-only version installed (`torch==2.9.1+cpu`)
2. **Large Model**: ChemLLM-7B (7 billion parameters) running in float32 on CPU
3. **Multiple Sequential Calls**: 5-7 LLM calls per analysis (can't parallelize)

## Speed Improvements (Already Applied)

✅ **Reduced LLM calls**: Removed 2 expensive calls (forward synthesis + availability)  
✅ **Optimized token counts**: 512 tokens instead of 1024 for ChemLLM  
✅ **Realistic ETA**: Now shows 3+ minutes instead of 25 seconds  

**Expected speedup: ~40% faster** (5 min → 3 min per analysis)

## Major Performance Boost Options

### Option 1: Install GPU-Enabled PyTorch ⚡ (10-50x faster)

If you have an NVIDIA GPU:

```bash
# Uninstall CPU version
pip uninstall torch torchvision torchaudio

# Install CUDA version (adjust for your CUDA version)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Result**: Deep analysis drops from **3-5 minutes → 10-30 seconds**

Check if you have GPU: `nvidia-smi` in terminal

### Option 2: Use Smaller/Quantized Models 🔧 (2-3x faster)

Replace ChemLLM-7B with a smaller or quantized version:

In `backend/agents/retrosynthesis.py`, change line 27:
```python
# Current (slow)
model_id = "AI4Chem/ChemLLM-7B-Chat-1.5-DPO"

# Faster options:
# model_id = "AI4Chem/ChemLLM-3B"  # If exists
# Or use quantization with bitsandbytes
```

### Option 3: Reduce Candidates 🎯 (2x faster)

In `backend/agents/researcher.py`, modify prompt to generate only 1-2 candidates instead of 2-3.

### Option 4: Parallel Processing (Future) 🚀

Currently sequential. Could parallelize candidate analysis using ThreadPoolExecutor.

## Recommended Action

**If you have an NVIDIA GPU**: Install CUDA-enabled PyTorch (Option 1)  
**If CPU-only**: Current optimizations are already applied. Consider Option 2 or 3 for more speed.

## Check Your Setup

```bash
# Check GPU
python -c "import torch; print('CUDA:', torch.cuda.is_available())"

# If False, you're on CPU (current situation)
# If True, PyTorch can use GPU!
```

## Monitor Performance

Use the **Debug Console** in the web UI to see:
- Which step is slow
- How long each API call takes
- Any errors or timeouts

Enable it with "Show Debug Logs" button at bottom of page.
