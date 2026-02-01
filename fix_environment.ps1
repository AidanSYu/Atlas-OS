# Install GLiNER and transformers with Windows long-path workaround
# This script handles the Windows long-path filename limitation in transformers 4.45+

Write-Host "🔧 Installing GLiNER and transformers..." -ForegroundColor Cyan

# Step 1: Uninstall broken packages
Write-Host "🗑️ Removing old packages..." -ForegroundColor Yellow
python -m pip uninstall gliner transformers tokenizers -y 2>$null

# Step 2: Install torch
Write-Host "📦 Installing torch 2.5.1..." -ForegroundColor Yellow
python -m pip install torch==2.5.1 `
    --index-url https://download.pytorch.org/whl/cu121 `
    --no-warn-script-location | Select-String -Pattern "Successfully|ERROR" -ErrorAction SilentlyContinue

# Step 3: Install transformers (compatible version, before gliner)
Write-Host "📦 Installing transformers 4.38.2..." -ForegroundColor Yellow
python -m pip install "transformers==4.38.2" `
    --no-warn-script-location `
    --no-deps | Select-String -Pattern "Successfully|ERROR" -ErrorAction SilentlyContinue

# Step 4: Install gliner
Write-Host "📦 Installing gliner 0.1.6..." -ForegroundColor Yellow  
python -m pip install "gliner==0.1.6" `
    --no-warn-script-location | Select-String -Pattern "Successfully|ERROR" -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "✅ Installation complete. Testing imports..." -ForegroundColor Green
Write-Host ""

# Test imports
python -c @"
import sys
success = True

try:
    import torch
    print(f'✅ torch {torch.__version__}')
except Exception as e:
    print(f'❌ torch: {e}')
    success = False

try:
    import transformers
    print(f'✅ transformers {transformers.__version__}')
except Exception as e:
    print(f'❌ transformers: {e}')
    success = False

try:
    from gliner import GLiNER
    print(f'✅ gliner imported successfully')
    model = GLiNER.from_pretrained('urchade/gliner_small-v2.1')
    print(f'✅ GLiNER model loaded')
except Exception as e:
    print(f'❌ gliner: {e}')
    success = False

if success:
    print('')
    print('🎉 All dependencies installed successfully!')
    sys.exit(0)
else:
    print('')
    print('⚠️ Some dependencies failed. See errors above.')
    sys.exit(1)
"@

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Ready to ingest documents with full entity extraction!" -ForegroundColor Green
    Write-Host "Restart the backend: python -m uvicorn app.main:app --reload" -ForegroundColor Cyan
}

