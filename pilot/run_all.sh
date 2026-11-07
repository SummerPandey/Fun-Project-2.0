#!/usr/bin/env bash
# Pilot 2: run every stage with one model per process (vLLM and Ollama both free memory most
# reliably between processes). Resumable: re-running skips answers already on disk.
#
# Order:
#   1. generate + capability, each model in turn
#   2. judge          turn-1 answers
#   3. correct        standard models only: one follow-up turn after each judged refusal
#   4. judge          the correction turns
#   5. analyze, sample
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-results}"
MODELS=$(python3 -c "import json;print(' '.join(m['name'] for m in json.load(open('config.json'))['models']))")
for m in $MODELS; do
  python3 run_pilot.py generate   --models "$m" --out "$OUT"
  python3 run_pilot.py capability --models "$m" --out "$OUT"
done
python3 run_pilot.py judge   --out "$OUT"   # judge runs alone, after all six models
python3 run_pilot.py correct --out "$OUT"   # second turn for refused standard answers
python3 run_pilot.py judge   --out "$OUT"   # grades the correction turns
python3 run_pilot.py analyze --out "$OUT"
python3 run_pilot.py sample  --out "$OUT"
