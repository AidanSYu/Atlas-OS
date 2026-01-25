# Multi-stage build for Python FastAPI app
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download SpaCy model to prevent runtime errors
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY app/ ./app/

# Create data directory
RUN mkdir -p /app/data/uploads

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
