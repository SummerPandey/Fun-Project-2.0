#!/usr/bin/env python3
"""Build the Health-20 batch prompt files and check them against their sources.

Health-20 = pilot3_design/screen1/prompts.json P01-P05 + pilot3_design/medical_set2.json H06-H20.
The runner accepts ids P01-P10 only, so the 20 questions are split into two batches and
renumbered P01-P10. The original id is kept in `screen_id`; screen1's older screen_id (I01..)
is kept as `prior_screen_id`.

    python3 tools/build_health20.py          # build, then check
    python3 tools/build_health20.py --check  # check only (exit 1 on any mismatch)
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCREEN1 = ROOT / "pilot3_design/screen1/prompts.json"
MED2 = ROOT / "pilot3_design/medical_set2.json"
OUT = ROOT / "pilot3_design/health20"
BATCHES = {
    "batchA": ["P01", "P02", "P03", "P04", "P05", "H06", "H07", "H08", "H09", "H10"],
    "batchB": [f"H{i}" for i in range(11, 21)],
}
VERBATIM = ("prompt", "neutral_twin", "checklist", "tier", "domain", "trigger")


def sources():
    s1 = json.loads(SCREEN1.read_text(encoding="utf-8"))
    m2 = json.loads(MED2.read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in s1["prompts"] if p["id"] in BATCHES["batchA"][:5]}
    by_id.update({p["id"]: p for p in m2["prompts"]})
    return s1, by_id


def build():
    s1, by_id = sources()
    for batch, ids in BATCHES.items():
        prompts = []
        for i, orig in enumerate(ids, 1):
            src = by_id[orig]
            p = {"id": f"P{i:02d}", "screen_id": orig}
            if "screen_id" in src:
                p["prior_screen_id"] = src["screen_id"]
            for k, v in src.items():
                if k not in ("id", "screen_id"):
                    p[k] = v
            prompts.append(p)
        data = {
            "description": f"Health-20 {batch}: {ids[0]}-{ids[-1]}, renumbered P01-P{len(ids):02d}; "
                           "original id in screen_id. Built by tools/build_health20.py.",
            "block_list": s1["block_list"],
            "block_message": s1["block_message"],
            "prompts": prompts,
        }
        path = OUT / batch / "prompts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)} ({len(prompts)} prompts)")


def check() -> int:
    s1, by_id = sources()
    fails = 0
    seen = []
    for batch, ids in BATCHES.items():
        data = json.loads((OUT / batch / "prompts.json").read_text(encoding="utf-8"))
        if data["block_list"] != s1["block_list"] or data["block_message"] != s1["block_message"]:
            print(f"FAIL {batch}: block_list/block_message differ from screen1"); fails += 1
        got_ids = [p["id"] for p in data["prompts"]]
        if got_ids != [f"P{i:02d}" for i in range(1, len(ids) + 1)]:
            print(f"FAIL {batch}: ids {got_ids}"); fails += 1
        for p, orig in zip(data["prompts"], ids):
            seen.append(p["screen_id"])
            if p["screen_id"] != orig:
                print(f"FAIL {batch} {p['id']}: screen_id {p['screen_id']} != {orig}"); fails += 1
                continue
            for k in VERBATIM:
                if p.get(k) != by_id[orig].get(k):
                    print(f"FAIL {batch} {p['id']} ({orig}): field {k} differs from source"); fails += 1
    if sorted(seen) != sorted(sum(BATCHES.values(), [])) or len(seen) != 20:
        print(f"FAIL: expected 20 distinct questions, got {len(seen)}"); fails += 1
    print(f"health20 prompt check: {fails} FAIL ({len(seen)} prompts, fields {', '.join(VERBATIM)})")
    return 1 if fails else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    if not a.check:
        build()
    sys.exit(check())
