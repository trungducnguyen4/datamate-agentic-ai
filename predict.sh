#!/usr/bin/env bash
set -e

# ==============================================================================
# DataMate - Zalo AI Challenge 2026 Official Prediction Runner
# ==============================================================================
# Environment requirements:
# - Input data (read-only): /data (contains questions.jsonl and business packages)
# - Result directory: /result (contains submission.jsonl and logs/)
# - Hardware: Offline inference, strictly local computations
# ==============================================================================

echo "[DataMate] Starting official inference pipeline..."

DATA_DIR="${DATA_DIR:-/data}"
RESULT_DIR="${RESULT_DIR:-/result}"
LOGS_DIR="${RESULT_DIR}/logs"

mkdir -p "${RESULT_DIR}"
mkdir -p "${LOGS_DIR}"
mkdir -p "/tmp/datamate_cache"
export DATAMATE_CACHE_DIR="/tmp/datamate_cache"

# Discover questions file
if [ -f "${DATA_DIR}/questions.jsonl" ]; then
    QUESTIONS_FILE="${DATA_DIR}/questions.jsonl"
elif [ -f "./data/public_test/questions.jsonl" ]; then
    QUESTIONS_FILE="./data/public_test/questions.jsonl"
    DATA_DIR="./data/public_test/data"
else
    QUESTIONS_FILE=$(find "${DATA_DIR}" -name "questions.jsonl" 2>/dev/null | head -n 1)
fi

# Locate data packages folder
if [ -d "${DATA_DIR}/data" ]; then
    PACKAGES_DIR="${DATA_DIR}/data"
else
    PACKAGES_DIR="${DATA_DIR}"
fi

echo "[DataMate] Packages directory: ${PACKAGES_DIR}"
echo "[DataMate] Questions file:     ${QUESTIONS_FILE}"
echo "[DataMate] Target submission:   ${RESULT_DIR}/submission.jsonl"
echo "[DataMate] Execution log:      ${LOGS_DIR}/execution.jsonl"

python -m datamate.cli \
    --data-dir "${PACKAGES_DIR}" \
    --questions "${QUESTIONS_FILE}" \
    --output "${RESULT_DIR}/submission.jsonl" \
    --log "${LOGS_DIR}/execution.jsonl"

echo "[DataMate] Inference pipeline completed successfully."
