#!/usr/bin/env python3
"""Look up the raw numbers behind any claim, straight from the JSONL. The cross-checkers use
this: a number may be reported only if this tool (or verify_results.py) prints it.

Examples
  python3 tools/lookup.py --prompt P03                         # every model, both wordings
  python3 tools/lookup.py --prompt P03 --family llama          # one pair
  python3 tools/lookup.py --model qwen3.5-27b-standard --prompt P01 --wording original --runs
  python3 tools/lookup.py --key "llama3.1-8b-standard|P05|twin|s2" --text   # one answer in full
  python3 tools/lookup.py --key "llama3.1-8b-standard|P05|original|s2|c1" --text   # its correction turn
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLED = ("s1", "s2", "s3", "s4", "s5")


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default=str(ROOT / "pilot" / "results"))
    ap.add_argument("--config", default=str(ROOT / "pilot" / "config.json"))
    ap.add_argument("--prompt", help="P01..P10")
    ap.add_argument("--family", help="qwen | llama | gemma")
    ap.add_argument("--model", help="model name from config.json")
    ap.add_argument("--wording", choices=("original", "twin"))
    ap.add_argument("--runs", action="store_true", help="list every run, not only the sampled means")
    ap.add_argument("--key", help="one answer: model|prompt|wording|run")
    ap.add_argument("--text", action="store_true", help="with --key: print the full answer and thinking")
    a = ap.parse_args()

    res = Path(a.results)
    gens = {f"{r['model']}|{r['prompt_id']}|{r['wording']}|{r['run']}": r for r in read(res / "generations.jsonl")}
    judg = {r["key"]: r for r in read(res / "judgments.jsonl")}
    corr = {r["key"]: r for r in read(res / "corrections.jsonl")}
    cjudg = {r["key"]: r for r in read(res / "correction_judgments.jsonl")}
    if not gens:
        print(f"no generations in {res}")
        return 1
    mock = any(r.get("mock") for r in gens.values())
    if mock:
        print("NOTE: MOCK DATA in this folder - synthetic, not results")

    if a.key:
        r = gens.get(a.key) or corr.get(a.key)
        j = judg.get(a.key) or cjudg.get(a.key)
        if r is None:
            print(f"no answer with key {a.key}")
            return 1
        show = {k: v for k, v in r.items() if k not in ("output_text", "thinking_text", "options")}
        print(json.dumps(show, indent=2, ensure_ascii=False))
        if j:
            print("judge:", json.dumps({k: j.get(k) for k in ("refusal_type", "required_met", "materially_wrong",
                                                               "caution_present", "useful", "judge_error")}))
        if a.key in gens and f"{a.key}|c1" in corr:
            print(f"this answer has a correction turn: --key \"{a.key}|c1\"")
        if a.text:
            if r.get("correction_text"):
                print("\n--- user correction (turn 2) ---\n" + r["correction_text"])
            if r.get("thinking_text"):
                print("\n--- thinking ---\n" + r["thinking_text"])
            print("\n--- answer ---\n" + r["output_text"])
        return 0

    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    names = [m["name"] for m in cfg["models"]
             if (not a.family or m["family"] == a.family) and (not a.model or m["name"] == a.model)]
    prompts = [a.prompt] if a.prompt else [f"P{i:02d}" for i in range(1, 11)]
    wordings = [a.wording] if a.wording else ["original", "twin"]
    print(f"{'model':32} {'prompt':6} {'wording':8} {'n':>2} {'mean_out':>9} {'mean_think':>10} "
          f"{'refusals':>8} {'useful':>6} {'cap_hits':>8} {'corrected':>9} {'fixed':>5} {'useful_final':>12}")
    for name in names:
        for p in prompts:
            for w in wordings:
                rows = [(run, gens.get(f"{name}|{p}|{w}|{run}")) for run in SAMPLED]
                rows = [(run, r) for run, r in rows if r]
                if not rows:
                    print(f"{name:32} {p:6} {w:8}  0  (not run yet)")
                    continue
                js = [judg.get(f"{name}|{p}|{w}|{run}") for run, _ in rows]
                judged = [j for j in js if j and not j.get("judge_error")]
                mo = sum(r["output_tokens"] for _, r in rows) / len(rows)
                mt = sum((r.get("thinking_tokens_est") or 0) for _, r in rows) / len(rows)
                ref = sum(j["refusal_type"] == "full_refusal" for j in judged)
                use = sum(bool(j["useful"]) for j in judged)
                caps = sum(bool(r["hit_cap"]) for _, r in rows)
                cs = [(corr.get(f"{name}|{p}|{w}|{run}|c1"), cjudg.get(f"{name}|{p}|{w}|{run}|c1")) for run, _ in rows]
                cs_j = [(c, cj) for c, cj in cs if c and cj and not cj.get("judge_error")]
                fixed = sum(bool(cj["useful"]) for _, cj in cs_j)
                final = sum(bool(j and not j.get("judge_error") and j["useful"]) or bool(cj and not cj.get("judge_error") and cj["useful"])
                            for j, (_, cj) in zip(js, cs))
                extra = (f" {len(cs_j):>9} {fixed:>5} {f'{final}/{len(judged)}':>12}" if w == "original" else "")
                print(f"{name:32} {p:6} {w:8} {len(rows):>2} {mo:>9.1f} {mt:>10.1f} "
                      f"{f'{ref}/{len(judged)}':>8} {f'{use}/{len(judged)}':>6} {caps:>8}{extra}")
                if a.runs:
                    for (run, r), j in zip(rows, js):
                        print(f"    {run:7} out={r['output_tokens']:>5} think={r.get('thinking_tokens_est') or 0:>5} "
                              f"in={r['input_tokens']:>4} finish={r['finish_reason']:6} "
                              f"refusal={(j or {}).get('refusal_type')} useful={(j or {}).get('useful')}")
                        c, cj = corr.get(f"{name}|{p}|{w}|{run}|c1"), cjudg.get(f"{name}|{p}|{w}|{run}|c1")
                        if c:
                            print(f"      correction: in={c['input_tokens']:>5} out={c['output_tokens']:>5} "
                                  f"refusal={(cj or {}).get('refusal_type')} useful={(cj or {}).get('useful')}")
                    g = gens.get(f"{name}|{p}|{w}|greedy")
                    if g:
                        print(f"    greedy  out={g['output_tokens']:>5} (greedy is reported separately)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
