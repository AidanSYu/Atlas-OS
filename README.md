# DIC03-ContAInnum
Build AI Agents to empower healthcare teams by efficiently gathering, synthesizing, and applying distributed knowledge throughout the entire drug life cycle.


## Run locally
- Backend: ./run-backend.sh
- Frontend: cd frontend && npm run dev

- Run fastapi backend: ./run-backend.sh
- Initialize Ollama: ollama serve
- Test by running: ollama run mistral "test"

- Example run in terminal: 
curl -X POST http://localhost:8000/api/researcher/research \
  -H "Content-Type: application/json" \
  -d '{"disease": "Type 2 diabetes"}'
Notes: Conceptual prototype for hackathon use only; not lab instructions or medical advice.
