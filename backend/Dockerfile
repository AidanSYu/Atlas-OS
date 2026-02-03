# DEPRECATED: This Dockerfile is for reference only.
# 
# Atlas 2.0 is now a Tauri desktop app with PyInstaller bundling.
# The backend runs as a Windows sidecar executable (atlas-backend-*.exe), 
# not in Docker containers.
#
# This Dockerfile is kept for historical reference.
# For development/testing only (not used in production):

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
RUN mkdir -p /app/data/uploads
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
