# VaakSetu Backend — Python 3.11 (Lightweight)
FROM python:3.11-slim

# System dependencies for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (no torch/whisper — uses SpeechRecognition instead)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip "setuptools<70" wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Create database directory
RUN mkdir -p db audio_cache

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
