# Testing the Application

## Prerequisites

**REQUIRED:**
- Ollama installed and running (see [OLLAMA_SETUP.md](OLLAMA_SETUP.md))
- Python virtual environment at `.venv/` with dependencies installed
- Node.js dependencies installed in `frontend/`

## Before You Start

**Start Ollama first:**
```bash
ollama serve
```
Keep this running in a terminal. The application will not work without it.

## Starting the Application

### Step 0: Start Ollama (Required)
```bash
# In Terminal 1
ollama serve
```
**Leave this running!** You should see "Ollama is running" message.

### 1. Start the Backend (Terminal 2)
```bash
./run-backend.sh
```
The backend API will run at http://localhost:8000

### 2. Start the Frontend (Terminal 3)
```bash
cd frontend
npm run dev
```
The frontend will run at http://localhost:5173

## Testing Features

### Available Endpoints in the UI:

1. **Synthesis Predictor** - Predict synthesis routes for a target molecule
2. **Manufacturability Agent** - Assess manufacturability of a candidate compound
3. **Researcher Agent** 
   - Generate research plans
   - Research disease information (uses Perplexity API)
4. **Compound Analysis** - Analyze a single compound for synthesis routes and manufacturability
5. **Integrated Research & Manufacturing** - Research disease and analyze treatment compounds in one workflow

### New Features Added:
- **Compound Analysis section**: Analyze individual compounds with SMILES support
- **Integrated Research & Manufacturing section**: One-click workflow that researches a disease and analyzes potential treatments
- Loading states for long-running operations
- Better structured output display for compound analyses
- **Increased timeouts**: Up to 5 minutes for complex LLM operations
- **Clear error messages**: Helpful guidance when Ollama is not running

## API Endpoints

All endpoints are available at http://localhost:8000/api/

- POST `/api/synthesis/predict` - Predict synthesis routes
- POST `/api/manufacturability/assess` - Assess manufacturability
- POST `/api/researcher/plan` - Generate research plan
- POST `/api/researcher/research` - Research disease (requires Perplexity API key)
- POST `/api/synthesis/analyze` - Analyze compound
- POST `/api/integrated/research-and-manufacture` - Integrated workflow (requires Perplexity API key)

## API Documentation

Visit http://localhost:8000/docs for interactive API documentation (Swagger UI)
