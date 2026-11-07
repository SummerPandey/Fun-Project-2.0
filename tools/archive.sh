#!/usr/bin/env bash
# Archive the run to GitHub: refresh figures and the verification report, then commit and push
# pilot/results/ and logs/. Never force-pushes; never touches code or config.
#
#   tools/archive.sh                 # once
#   tools/archive.sh "note"          # once, with a note in the commit message
#   tools/archive.sh --loop 900      # every 900 s until stopped (Ctrl-C or kill)
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

once() {
  local note="${1:-}"
  python3 tools/visualize.py >/dev/null 2>&1 || echo "archive: visualize skipped (no data yet or matplotlib missing)"
  python3 tools/verify_results.py --quiet >/dev/null 2>&1
  local verify; verify=$(python3 - <<'EOF'
import json, pathlib
p = pathlib.Path("pilot/results/verify_report.json")
if p.exists():
    d = json.loads(p.read_text()); print(f"verify {d['fails']} FAIL {d['warnings']} WARN")
else:
    print("verify n/a")
EOF
)
  local done; done=$(grep -c . pilot/results/generations.jsonl 2>/dev/null || echo 0)
  git add pilot/results logs
  if git diff --cached --quiet; then
    echo "archive: nothing new to commit ($(date -u +%H:%M) UTC)"
    return 0
  fi
  git commit -q -m "archive: ${done} answers, ${verify}${note:+ - $note}" \
    -m "Automatic snapshot by tools/archive.sh at $(date -u +%Y-%m-%dT%H:%M:%SZ)." || return 1
  if ! git push -q origin HEAD 2>/dev/null; then
    # Someone else pushed (e.g. a doc fix). Rebase our results commit on top and retry once.
    git pull -q --rebase origin "$(git rev-parse --abbrev-ref HEAD)" && git push -q origin HEAD \
      || { echo "archive: PUSH FAILED - commit kept locally; check 'gh auth status'"; return 1; }
  fi
  echo "archive: pushed $(git rev-parse --short HEAD) (${done} answers, ${verify})"
}

if [[ "${1:-}" == "--loop" ]]; then
  every="${2:-900}"
  echo "archive: looping every ${every}s"
  while true; do once "auto"; sleep "$every"; done
else
  once "${1:-}"
fi
