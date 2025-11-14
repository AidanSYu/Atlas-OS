# Ollama Setup Guide

## Required Setup

Ollama is **required** to run this application. The agents use Ollama to generate synthesis plans, research summaries, and manufacturability assessments.

## Installation

### macOS / Linux

1. **Download and Install Ollama:**
   ```bash
   # macOS (using Homebrew)
   brew install ollama
   
   # Or download from: https://ollama.ai
   ```

2. **Pull the Mistral model:**
   ```bash
   ollama pull mistral
   ```
   This downloads the ~4GB Mistral model (may take a few minutes)

3. **Start the Ollama server:**
   ```bash
   ollama serve
   ```
   Keep this running in a terminal. The server runs on `http://127.0.0.1:11434`

### Windows

1. Download Ollama from https://ollama.ai
2. Install the application
3. Open Command Prompt or PowerShell:
   ```bash
   ollama pull mistral
   ollama serve
   ```

## Verification

Test that Ollama is running:

```bash
curl http://127.0.0.1:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Hello",
  "stream": false
}'
```

You should get a JSON response with generated text.

## Usage with the Application

You **must** have Ollama running before starting the application:

1. **Start Ollama** (in Terminal 1):
   ```bash
   ollama serve
   ```
   Keep this running - you should see "Ollama is running"

2. **Start the backend** (in Terminal 2):
   ```bash
   ./run-backend.sh
   ```

3. **Start the frontend** (in Terminal 3):
   ```bash
   cd frontend
   npm run dev
   ```

The agents will now use AI-generated responses for all research and synthesis analysis.

## Troubleshooting

### "Connection refused" or timeout errors

- Make sure `ollama serve` is running
- Check that nothing else is using port 11434
- Verify the model is downloaded: `ollama list`

### Slow responses

- First request may be slow as the model loads into memory
- Subsequent requests should be faster (~10-30 seconds)
- Mistral requires ~8GB RAM; consider closing other applications

### Alternative: Use a different model

If Mistral is too slow or large, try a smaller model:

```bash
ollama pull llama2:7b
```

Then update the agents to use "llama2:7b" instead of "mistral" (in the agent files).

## Performance Notes

- Responses take 10-60 seconds depending on prompt complexity
- First request after starting Ollama is slowest (model loading into memory)
- Requires ~8GB RAM for Mistral model
- Timeout is set to 5 minutes per request

## Alternative LLM Providers

If you prefer not to run Ollama locally, you could modify the agents to use:

- OpenAI API (GPT-4)
- Anthropic API (Claude)
- Google Vertex AI
- Groq (fast inference)

These require API keys and typically have per-token costs.
