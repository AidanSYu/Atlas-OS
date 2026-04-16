Check the full status of the Atlas Framework:
1. Verify the orchestrator model file exists at the configured MODELS_DIR path
2. Check if Qdrant storage is accessible
3. Check if SQLite database exists
4. List all registered plugins under `src/backend/plugins/`
5. Check if the backend server is running (try curl localhost:8000/api/health)
6. Check if the frontend dev server is running (try curl localhost:5173)
7. Report a summary of what's healthy and what needs attention