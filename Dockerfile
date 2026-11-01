# DataMate Offline Docker Submission Image
# Meets Zalo AI Challenge 2026 specs:
# - Offline inference (no internet access)
# - Input mounted at /data (read-only)
# - Output written to /result/submission.jsonl
# - Logs written to /result/logs/execution.jsonl
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

# Copy source code and entrypoint
COPY datamate /app/datamate
COPY scripts /app/scripts
COPY predict.sh /app/predict.sh
RUN chmod +x /app/predict.sh

# Create input/output and cache directories
RUN mkdir -p /data /result /tmp/datamate_cache

ENTRYPOINT ["/app/predict.sh"]
