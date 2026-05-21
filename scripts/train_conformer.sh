#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
PYTHON="$ROOT/.venv/bin/python"
export PYTHONPATH="$ROOT/src"

echo "=============================================="
echo "Stage 1: Conformer Regression Training"
echo "=============================================="
"$PYTHON" -m leak_detection.cli.train \
  --config "$ROOT/configs/stage1_conformer.yaml" \
  --output-dir "$ROOT/outputs/stage1/internoise_stage1_conformer"

echo ""
echo "=============================================="
echo "Stage 2: Conformer Classification Training"
echo "=============================================="
"$PYTHON" -m leak_detection.cli.train \
  --config "$ROOT/configs/stage2_conformer.yaml" \
  --output-dir "$ROOT/outputs/stage2/internoise_stage2_conformer"

echo ""
echo "Both Conformer training runs completed."
