#!/usr/bin/env bash
set -euo pipefail

GE_PROJECT_DIR="${GE_PROJECT_DIR:-/workspace/great_expectations}"
DATA_DIR="${DATA_DIR:-/data}"
OUTPUT_DIR="${OUTPUT_DIR:-/output}"
CHECKPOINT_NAME="${CHECKPOINT_NAME:-validation_checkpoint}"

echo "[GE Docker] Project: $GE_PROJECT_DIR"
echo "[GE Docker] Data dir: $DATA_DIR"
echo "[GE Docker] Output:  $OUTPUT_DIR"
echo "[GE Docker] Checkpoint: $CHECKPOINT_NAME"

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$RANDOM"
AUDIT_LOG="${OUTPUT_DIR}/logs/validation_audit_log.jsonl"
mkdir -p "$(dirname "$AUDIT_LOG")"
echo "{"stage":"validate","event":"start","run_id":"$RUN_ID","ts":"$(date -u +%FT%TZ)"}" >> "$AUDIT_LOG"

# Run our simple Python-based validator that also emits a CSV summary.
python /workspace/run_validation.py --data "$DATA_DIR" --out "$OUTPUT_DIR"

echo "{"stage":"validate","event":"end","run_id":"$RUN_ID","ts":"$(date -u +%FT%TZ)"}" >> "$AUDIT_LOG"
