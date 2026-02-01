#!/bin/bash
# Fix GLiNER installation on Windows with long path issues

echo "🔧 Installing GLiNER and transformers with Windows long-path workaround..."

# Uninstall broken packages
pip uninstall -y gliner transformers tokenizers 2>/dev/null

# Install with explicit versions and special handling
python -m pip install \
    torch==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu121 \
    --no-warn-script-location

# Install transformers before gliner (specific compatible version)
python -m pip install \
    "transformers==4.38.2" \
    --no-warn-script-location \
    --no-deps

# Now install gliner
python -m pip install \
    "gliner==0.1.6" \
    --no-warn-script-location

echo "✅ Installation complete. Testing imports..."

python -c "
try:
    import torch
    print(f'✅ torch {torch.__version__}')
except Exception as e:
    print(f'❌ torch: {e}')

try:
    import transformers
    print(f'✅ transformers {transformers.__version__}')
except Exception as e:
    print(f'❌ transformers: {e}')

try:
    from gliner import GLiNER
    print(f'✅ gliner imported successfully')
except Exception as e:
    print(f'❌ gliner: {e}')
"
