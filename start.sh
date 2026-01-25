#!/bin/bash

# Atlas Quick Start Script
# This script sets up and starts all Atlas services

set -e

echo "🚀 Atlas Quick Start"
echo "===================="

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Python
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.10+."
    exit 1
fi
PYTHON_CMD=$(command -v python3 || command -v python)
echo "✅ Python found: $PYTHON_CMD"

# Check Node
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Please install Node.js 18+."
    exit 1
fi
echo "✅ Node.js found: $(node --version)"

# Check Ollama
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Please install Ollama from https://ollama.ai"
    exit 1
fi
echo "✅ Ollama found"

echo ""
echo "🗄️  Checking local services (PostgreSQL :5432, Qdrant :6333)..."
PG_UP=$(nc -z localhost 5432 && echo "1" || echo "0")
QD_UP=$(nc -z localhost 6333 && echo "1" || echo "0")
if [ "$PG_UP" != "1" ]; then
    echo "⚠️  PostgreSQL not reachable on localhost:5432. Please start your local Postgres service."
fi
if [ "$QD_UP" != "1" ]; then
    echo "⚠️  Qdrant not reachable on localhost:6333. Set VECTOR_BACKEND=local in backend/.env to use the local JSON fallback."
fi
echo "✅ Service checks complete (backend will fail if stores stay offline)."

echo ""
echo "🤖 Checking Ollama models..."
if ! ollama list | grep -q "llama3"; then
    echo "📥 Pulling llama3 model..."
    ollama pull llama3
fi
if ! ollama list | grep -q "nomic-embed-text"; then
    echo "📥 Pulling nomic-embed-text model..."
    ollama pull nomic-embed-text
fi
echo "✅ Ollama models ready"

echo ""
echo "🐍 Setting up backend..."
cd backend

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    $PYTHON_CMD -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate || . .venv/Scripts/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cp .env.example .env
fi

echo "✅ Backend setup complete"

echo ""
echo "⚛️  Setting up frontend..."
cd ../frontend

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install --silent
fi

if [ ! -f ".env.local" ]; then
    echo "Creating .env.local file..."
    echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
fi

echo "✅ Frontend setup complete"

cd ..

echo ""
echo "============================================"
echo "✨ Setup complete!"
echo "============================================"
echo ""
echo "📍 Service URLs:"
echo "   Frontend:  http://localhost:3000"
echo "   Backend:   http://localhost:8000"
echo "   Postgres:  localhost:5432 (configure in backend/.env)"
echo "   Qdrant:    http://localhost:6333 (or VECTOR_BACKEND=local)"
echo ""
echo "To start the services manually:"
echo "   1. Backend:  cd backend && python -m app.main"
echo "   2. Frontend: cd frontend && npm run dev"
echo ""

# Ask user if they want to start services now
read -p "Start services now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting backend..."
    cd backend
    source .venv/bin/activate || . .venv/Scripts/activate
    python -m app.main &
    BACKEND_PID=$!
    
    echo "Starting frontend..."
    cd ../frontend
    npm run dev &
    FRONTEND_PID=$!
    
    echo ""
    echo "✅ Services started!"
    echo "   Backend PID: $BACKEND_PID"
    echo "   Frontend PID: $FRONTEND_PID"
    echo ""
    echo "Press Ctrl+C to stop all services"
    
    # Wait for Ctrl+C
    trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
    wait
else
    echo "Services not started. Start them manually when ready."
fi
