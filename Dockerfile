# DataMate Offline Docker Submission Image
# Meets Zalo AI Challenge 2026 specs:
# - Offline inference (no internet access)
# - Input mounted at /data
# - Output written to /result/submission.jsonl
# - GPU acceleration supported (NVIDIA Blackwell / CUDA >= 12.8 compatible)

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY datamate /app/datamate
COPY scripts /app/scripts

# Create input/output directories
RUN mkdir -p /data /result

ENTRYPOINT ["python", "-m", "datamate.cli", "--data-dir", "/data", "--questions", "/data/questions.jsonl", "--output", "/result/submission.jsonl"]
