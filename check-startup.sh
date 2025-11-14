#!/usr/bin/env bash
# Startup check script - verifies Ollama is running before starting the application

set -e

echo "=== Drug Dev Agents Startup Check ==="
echo ""

# Check if Ollama is running
echo "Checking if Ollama is running..."
if ! curl -s http://127.0.0.1:11434/api/tags > /dev/null 2>&1; then
    echo "❌ ERROR: Ollama is not running!"
    echo ""
    echo "Please start Ollama first:"
    echo "  1. In a new terminal, run: ollama serve"
    echo "  2. Keep it running in the background"
    echo ""
    echo "If you haven't installed Ollama yet:"
    echo "  brew install ollama"
    echo "  ollama pull mistral"
    echo ""
    echo "See OLLAMA_SETUP.md for detailed instructions."
    exit 1
fi

echo "✓ Ollama is running"

# Check if mistral model is available
echo "Checking for Mistral model..."
if ! curl -s http://127.0.0.1:11434/api/tags | grep -q "mistral"; then
    echo "⚠️  WARNING: Mistral model not found"
    echo "   Run: ollama pull mistral"
    echo ""
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo "✓ Mistral model installed"
fi

# Check virtual environment
if [ ! -d ".venv" ]; then
    echo "❌ ERROR: Virtual environment not found at .venv/"
    echo "   Please set up the backend first"
    exit 1
fi
echo "✓ Virtual environment exists"

# Check frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "❌ ERROR: Frontend dependencies not installed"
    echo "   Run: cd frontend && npm install"
    exit 1
fi
echo "✓ Frontend dependencies installed"

echo ""
echo "=== All checks passed! ==="
echo ""
echo "Start the application:"
echo "  Terminal 1: (Ollama already running)"
echo "  Terminal 2: ./run-backend.sh"
echo "  Terminal 3: cd frontend && npm run dev"
echo ""
echo "Then visit: http://localhost:5173"
