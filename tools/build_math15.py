#!/usr/bin/env python3
"""Build the Math-15 batch prompt files and check them against pilot3_design/math_set.json.

batchA = M01-M10 (renumbered P01-P10), batchB = M11-M15 (renumbered P01-P05). The original id
is kept in `screen_id`. block_list/block_message are copied from screen1 (the runner needs them;
no math wording matches them, which the check confirms).

    python3 tools/build_math15.py          # build, then check
    python3 tools/build_math15.py --check  # check only (exit 1 on any mismatch)
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "pilot3_design/math_set.json"
SCREEN1 = ROOT / "pilot3_design/screen1/prompts.json"
OUT = ROOT / "pilot3_design/math15"
BATCHES = {"batchA": [f"M{i:02d}" for i in range(1, 11)], "batchB": [f"M{i:02d}" for i in range(11, 16)]}
VERBATIM = ("prompt", "neutral_twin", "checklist", "answer_key", "assumptions", "tier", "domain")


def sources():
    s1 = json.loads(SCREEN1.read_text(encoding="utf-8"))
    src = json.loads(SRC.read_text(encoding="utf-8"))
    return s1, src, {p["id"]: p for p in src["prompts"]}


def build():
    s1, src, by_id = sources()
    for batch, ids in BATCHES.items():
        prompts = []
        for i, orig in enumerate(ids, 1):
            p = {"id": f"P{i:02d}", "screen_id": orig}
            p.update({k: v for k, v in by_id[orig].items() if k != "id"})
            prompts.append(p)
        data = {
            "description": f"Math-15 {batch}: {ids[0]}-{ids[-1]}, renumbered P01-P{len(ids):02d}; original id in "
                           "screen_id. prompt = game-framed wording, neutral_twin = plain math. "
                           "Built by tools/build_math15.py.",
            "rubric": src["rubric"],
            "block_list": s1["block_list"],
            "block_message": s1["block_message"],
            "prompts": prompts,
        }
        path = OUT / batch / "prompts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(prompts)} prompts)")


def check() -> int:
    s1, src, by_id = sources()
    fails, seen = 0, []
    block_re = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in s1["block_list"]) + r")\w*", re.I)
    for batch, ids in BATCHES.items():
        data = json.loads((OUT / batch / "prompts.json").read_text(encoding="utf-8"))
        if data["block_list"] != s1["block_list"] or data["block_message"] != s1["block_message"]:
            print(f"FAIL {batch}: block_list/block_message differ from screen1"); fails += 1
        got = [p["id"] for p in data["prompts"]]
        if got != [f"P{i:02d}" for i in range(1, len(ids) + 1)]:
            print(f"FAIL {batch}: ids {got}"); fails += 1
        for p, orig in zip(data["prompts"], ids):
            seen.append(p["screen_id"])
            if p["screen_id"] != orig:
                print(f"FAIL {batch} {p['id']}: screen_id {p['screen_id']} != {orig}"); fails += 1
                continue
            for k in VERBATIM:
                if p.get(k) != by_id[orig].get(k):
                    print(f"FAIL {batch} {p['id']} ({orig}): field {k} differs from source"); fails += 1
            for w in ("prompt", "neutral_twin"):
                hit = block_re.search(p[w])
                if hit:
                    print(f"WARN {batch} {p['id']} ({orig}): {w} matches block-list term '{hit.group(0)}'")
    if sorted(seen) != sorted(sum(BATCHES.values(), [])):
        print(f"FAIL: expected M01-M15 once each, got {seen}"); fails += 1
    print(f"math15 prompt check: {fails} FAIL ({len(seen)} prompts, fields {', '.join(VERBATIM)})")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not a.check:
        build()
    sys.exit(check())
