# DIC03-ContAInnum
Build AI Agents to empower healthcare teams by efficiently gathering, synthesizing, and applying distributed knowledge throughout the entire drug life cycle.

## Quick Start

### 1. Setup Ollama (Required)
```bash
# Install Ollama
brew install ollama  # macOS, or download from https://ollama.ai

# Pull the Mistral model
ollama pull mistral

# Start Ollama server (keep running)
ollama serve
```

### 2. Check Prerequisites
```bash
./check-startup.sh
```

### 3. Run Application
```bash
# Terminal 1: Ollama (already running from step 1)
# Terminal 2: Backend
./run-backend.sh

# Terminal 3: Frontend
cd frontend && npm run dev
```

Visit http://localhost:5173

## Documentation

- [OLLAMA_SETUP.md](OLLAMA_SETUP.md) - Ollama installation and configuration
- [TESTING.md](TESTING.md) - Testing guide and features overview
- [SYNTHESIS_AGENT_README.md](SYNTHESIS_AGENT_README.md) - Synthesis agent details
- [RETROSYNTHESIS_README.md](RETROSYNTHESIS_README.md) - Retrosynthesis engine details

## Example API Usage

```bash
curl -X POST http://localhost:8000/api/researcher/research \
  -H "Content-Type: application/json" \
  -d '{"disease": "Type 2 diabetes"}'
```

Notes: Conceptual prototype for hackathon use only; not lab instructions or medical advice.
