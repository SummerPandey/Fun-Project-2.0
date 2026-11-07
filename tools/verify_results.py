#!/usr/bin/env python3
"""Independent cross-check of a results folder. Recomputes numbers from the raw JSONL and
compares them with what the pipeline wrote. Exit code 0 = no FAIL, 1 = at least one FAIL.

What it checks (each line of the report is PASS / WARN / FAIL with the evidence):
  files        every JSONL line parses; mock and real rows are never mixed
  progress     answers per model and stage against the expected counts
  provenance   every answer's prompt_text is exactly the text in pilot_prompts.json
  digests      one weights digest per model, matching the digest pinned in config.json
  settings     identical sampling options and think flag within each family (only seed and
               temperature may vary, and only as the run spec says)
  tokens       hit_cap <=> finish_reason "length"; counts within the cap; thinking <= output
  judge        every judgment belongs to an answer; "useful" follows its rule
  summary      summary.json mean output tokens and TPUA recomputed from the JSONL
  per_prompt   per_prompt.csv recomputed from the JSONL (if present)
  capability   every capability row re-scored from its own output text

Writes <results>/verify_report.md and verify_report.json.

Usage:  python3 tools/verify_results.py [--results pilot/results] [--config pilot/config.json]
                                        [--sample 5]   # also print 5 random raw rows to eyeball
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLED = ("s1", "s2", "s3", "s4", "s5")
TOL = 1e-6


def load_runner():
    spec = importlib.util.spec_from_file_location("run_pilot", ROOT / "pilot" / "run_pilot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Report:
    def __init__(self):
        self.items = []

    def add(self, level: str, area: str, msg: str):
        self.items.append({"level": level, "area": area, "message": msg})

    def ok(self, area, msg): self.add("PASS", area, msg)
    def warn(self, area, msg): self.add("WARN", area, msg)
    def fail(self, area, msg): self.add("FAIL", area, msg)

    @property
    def n_fail(self): return sum(i["level"] == "FAIL" for i in self.items)

    @property
    def n_warn(self): return sum(i["level"] == "WARN" for i in self.items)


def read_jsonl(path: Path, rep: Report, area="files") -> list[dict]:
    if not path.exists():
        rep.warn(area, f"{path.name} does not exist yet")
        return []
    rows, bad = [], []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            bad.append(n)
    if bad:
        rep.fail(area, f"{path.name}: lines {bad[:10]} are not valid JSON")
    else:
        rep.ok(area, f"{path.name}: {len(rows)} rows, all valid JSON")
    return rows


def gkey(r):
    return f"{r['model']}|{r['prompt_id']}|{r['wording']}|{r['run']}"


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def close(a, b) -> bool:
    if a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return a == b
    return abs(float(a) - float(b)) <= TOL * max(1.0, abs(float(a)))


def main() -> int:
    ap = argparse.ArgumentParser(description="Cross-check a results folder against its raw data.")
    ap.add_argument("--results", default=str(ROOT / "pilot" / "results"))
    ap.add_argument("--config", default=str(ROOT / "pilot" / "config.json"))
    ap.add_argument("--sample", type=int, default=0, help="print N random answers (raw fields) to eyeball")
    ap.add_argument("--quiet", action="store_true", help="print only the totals line")
    args = ap.parse_args()

    results = Path(args.results).resolve()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    prompts = {p["id"]: p for p in json.loads((ROOT / "pilot_prompts.json").read_text(encoding="utf-8"))["prompts"]}
    rp = load_runner()
    rep = Report()
    models = {m["name"]: m for m in cfg["models"]}
    gen_cfg = cfg["generation"]

    gens_raw = read_jsonl(results / "generations.jsonl", rep)
    judg_raw = read_jsonl(results / "judgments.jsonl", rep)
    cap_raw = read_jsonl(results / "capability.jsonl", rep)

    # ---- mock / real
    flags = {bool(r.get("mock")) for r in gens_raw + judg_raw + cap_raw}
    if len(flags) > 1:
        rep.fail("files", "mock and real rows are MIXED in this folder: no number from it can be used")
    elif flags:
        rep.ok("files", "all rows are " + ("MOCK (synthetic)" if True in flags else "real"))
    is_mock = True in flags

    # ---- duplicates: the pipeline keeps the last row per key; duplicates mean a stage re-ran
    dup = [k for k, n in Counter(gkey(r) for r in gens_raw).items() if n > 1]
    if dup:
        rep.warn("files", f"{len(dup)} answer keys appear more than once (last one is used), e.g. {dup[:3]}")
    gens = {gkey(r): r for r in gens_raw}
    judg = {r["key"]: r for r in judg_raw}
    cap = {(r["model"], r["item_id"]): r for r in cap_raw}

    unknown = sorted({r["model"] for r in gens.values()} - set(models))
    if unknown:
        rep.fail("files", f"answers from models not in config.json: {unknown}")

    # ---- progress
    specs = rp.run_specs(gen_cfg)
    per_model = len(prompts) * 2 * len(specs)
    n_items = None
    if (results / "capability_items.json").exists():
        n_items = len(json.loads((results / "capability_items.json").read_text(encoding="utf-8"))["items"])
    for name in models:
        g = sum(1 for r in gens.values() if r["model"] == name)
        j = sum(1 for r in judg.values() if r["model"] == name and not r.get("judge_error"))
        c = sum(1 for r in cap.values() if r["model"] == name)
        msg = f"{name}: generate {g}/{per_model}, judge {j}/{per_model}, capability {c}/{n_items or '?'}"
        (rep.ok if g == per_model and j == per_model and (n_items is None or c == n_items) else rep.warn)("progress", msg)

    # ---- provenance: the answer is to the exact prompt text on file
    bad_text = [k for k, r in gens.items()
                if r["prompt_id"] not in prompts
                or r["prompt_text"] != (prompts[r["prompt_id"]]["prompt"] if r["wording"] == "original"
                                        else prompts[r["prompt_id"]]["neutral_twin"])]
    if bad_text:
        rep.fail("provenance", f"{len(bad_text)} answers have a prompt_text that is not in pilot_prompts.json, e.g. {bad_text[:3]}")
    elif gens:
        rep.ok("provenance", f"all {len(gens)} answers match the prompt texts in pilot_prompts.json")

    # ---- digests
    if not is_mock:
        for name, m in models.items():
            revs = {r["revision"] for r in gens.values() if r["model"] == name}
            revs |= {r["revision"] for r in cap.values() if r["model"] == name}
            if not revs:
                continue
            if len(revs) > 1:
                rep.fail("digests", f"{name}: answers come from {len(revs)} different weights: {sorted(str(x)[:12] for x in revs)}")
            elif m.get("digest") and not str(next(iter(revs))).startswith(m["digest"]):
                rep.fail("digests", f"{name}: weights {str(next(iter(revs)))[:12]} do not match pinned {m['digest']}")
            else:
                rep.ok("digests", f"{name}: one set of weights, {str(next(iter(revs)))[:12]}"
                       + (" (matches pin)" if m.get("digest") else " (NOT pinned in config)"))

    # ---- settings: same options and think flag within a family; seed/temperature per run spec
    spec_by_run = {s["run"]: s for s in specs}
    bad_spec = [k for k, r in gens.items() if r["run"] in spec_by_run and
                (r["seed"] != spec_by_run[r["run"]]["seed"] or not close(r["temperature"], spec_by_run[r["run"]]["temperature"]))]
    if bad_spec:
        rep.fail("settings", f"{len(bad_spec)} answers have a seed/temperature that differs from the run spec, e.g. {bad_spec[:3]}")
    elif gens:
        rep.ok("settings", "every answer's seed and temperature match its run (s1-s5 sampled, greedy)")
    if not is_mock and any("options" in r for r in gens.values()):
        by_family = defaultdict(set)
        for r in gens.values():
            opts = {k: v for k, v in (r.get("options") or {}).items() if k not in ("seed", "temperature")}
            by_family[r["family"]].add(json.dumps({"options": opts, "think": r.get("think")}, sort_keys=True))
        for fam, variants in by_family.items():
            if len(variants) > 1:
                rep.fail("settings", f"{fam}: models in this family were run with different settings: {sorted(variants)}")
            else:
                rep.ok("settings", f"{fam}: both models used identical options and think flag {next(iter(variants))}")

    # ---- tokens
    cap_tok = gen_cfg["max_tokens"]
    issues = Counter()
    for r in gens.values():
        if bool(r["hit_cap"]) != (r["finish_reason"] == "length"):
            issues["hit_cap disagrees with finish_reason"] += 1
        if r["output_tokens"] < 0 or r["input_tokens"] <= 0:
            issues["non-positive token count"] += 1
        if r["output_tokens"] > cap_tok + 5:
            issues[f"output_tokens above the {cap_tok} cap"] += 1
        t = r.get("thinking_tokens_est")
        if t is not None and (t < 0 or t > r["output_tokens"]):
            issues["thinking estimate outside 0..output_tokens"] += 1
        if r["finish_reason"] == "stop" and not r["output_text"].strip():
            issues["empty answer with finish_reason stop"] += 1
    for k, n in issues.items():
        (rep.warn if "empty answer" in k else rep.fail)("tokens", f"{n} answers: {k}")
    if gens and not issues:
        rep.ok("tokens", f"all {len(gens)} answers: cap flags consistent, counts in range")
    thinking_cap = sum(bool(r.get("hit_cap_in_thinking")) for r in gens.values())
    if thinking_cap:
        rep.warn("tokens", f"{thinking_cap} answers ran out of tokens while still thinking (no visible answer); "
                           "consider a larger max_tokens before the main study")

    # ---- judge
    orphan = [k for k in judg if k not in gens]
    if orphan:
        rep.fail("judge", f"{len(orphan)} judgments have no matching answer, e.g. {orphan[:3]}")
    bad_rule, errors, inconsistent = [], 0, 0
    for k, j in judg.items():
        if j.get("judge_error"):
            errors += 1
            continue
        rule = bool(all(j["required_met"]) and not j["materially_wrong"] and j["refusal_type"] != "full_refusal")
        if rule != j["useful"]:
            bad_rule.append(k)
        inconsistent += bool(j.get("judge_inconsistent"))
    if bad_rule:
        rep.fail("judge", f"{len(bad_rule)} judgments break the useful rule, e.g. {bad_rule[:3]}")
    elif judg:
        rep.ok("judge", f"{len(judg)} judgments: 'useful' follows its rule in every one")
    if errors:
        (rep.warn if errors / max(len(judg), 1) < 0.05 else rep.fail)("judge", f"{errors} judge errors (unparseable after retry)")
    if inconsistent:
        rep.warn("judge", f"{inconsistent} times the judge's own 'useful' disagreed with the rule (rule value is used)")

    # ---- summary.json, recomputed independently (sampled runs, original and twin conditions)
    spath = results / "summary.json"
    if spath.exists() and gens:
        s = json.loads(spath.read_text(encoding="utf-8"))
        mism = 0
        checked = 0
        for name in models:
            for w in ("original", "twin"):
                rows = [r for r in gens.values() if r["model"] == name and r["wording"] == w and r["run"] in SAMPLED]
                if not rows:
                    continue
                mine = mean(r["output_tokens"] for r in rows)
                theirs = s["by_model"][name]["sampled"][w]["mean_output_tokens"]
                checked += 1
                if not close(mine, theirs):
                    mism += 1
                    rep.fail("summary", f"{name} {w}: mean output tokens recomputed {mine:.3f} vs summary {theirs}")
                js = [judg.get(gkey(r)) for r in rows]
                if all(j is not None and not j.get("judge_error") for j in js):
                    useful = sum(bool(j["useful"]) for j in js)
                    tok = sum(r["input_tokens"] + r["output_tokens"] for r in rows)
                    mine_t = tok / useful if useful else "undefined"
                    theirs_t = s["by_model"][name]["sampled"][w]["tpua"]["value"]
                    checked += 1
                    if not close(mine_t, theirs_t):
                        mism += 1
                        rep.fail("summary", f"{name} {w}: TPUA recomputed {mine_t} vs summary {theirs_t}")
        if checked and not mism:
            rep.ok("summary", f"{checked} summary numbers (mean output tokens, TPUA) recomputed from JSONL: all match")
        stale = s.get("generated_at", "")
        rep.ok("summary", f"summary.json generated_at {stale}") if stale else None
    elif gens:
        rep.warn("summary", "summary.json not written yet (run the analyze stage)")

    # ---- per_prompt.csv
    ppath = results / "per_prompt.csv"
    if ppath.exists() and gens:
        mism = 0
        with ppath.open(encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            g = [gens.get(f"{row['model']}|{row['prompt_id']}|{row['wording']}|{run}") for run in SAMPLED]
            g = [x for x in g if x]
            mine = mean(x["output_tokens"] for x in g)
            theirs = float(row["mean_output_tokens"]) if row["mean_output_tokens"] not in ("", "None") else None
            if not close(mine, theirs):
                mism += 1
        (rep.fail if mism else rep.ok)("per_prompt", f"per_prompt.csv: {len(rows) - mism}/{len(rows)} cells match the JSONL"
                                       + ("" if not mism else " (re-run tools/visualize.py if the run moved on since)"))

    # ---- correction turns (standard models get one follow-up after a refusal)
    corr_cfg = cfg.get("correction") or {}
    corr = {r["key"]: r for r in read_jsonl(results / "corrections.jsonl", rep, "correction")} \
        if (results / "corrections.jsonl").exists() else {}
    cjudg = {r["key"]: r for r in read_jsonl(results / "correction_judgments.jsonl", rep, "correction")} \
        if (results / "correction_judgments.jsonl").exists() else {}
    if corr_cfg.get("enabled") and judg:
        variants, trigger = set(corr_cfg["variants"]), set(corr_cfg["trigger"])
        targets = {f"{k}|c1" for k, j in judg.items() if k in gens and not j.get("judge_error")
                   and gens[k]["wording"] == "original" and models.get(gens[k]["model"], {}).get("variant") in variants
                   and j["refusal_type"] in trigger}
        bad = Counter()
        for k, c in corr.items():
            parent = gens.get(c.get("parent_key"))
            pj = judg.get(c.get("parent_key"))
            if parent is None or k != f"{c['parent_key']}|c1":
                bad["has no matching turn-1 answer"] += 1
                continue
            if models.get(c["model"], {}).get("variant") not in variants:
                bad[f"belongs to a model that should get one turn only ({c['model']})"] += 1
            if pj is None or pj.get("judge_error") or pj["refusal_type"] not in trigger:
                bad["follows a turn-1 answer that was not judged a refusal"] += 1
            want = corr_cfg["template"].format(twin=prompts[c["prompt_id"]]["neutral_twin"],
                                               original=prompts[c["prompt_id"]]["prompt"])
            if c["correction_text"] != want:
                bad["correction text differs from the configured template"] += 1
            if c["seed"] != parent["seed"] or not close(c["temperature"], parent["temperature"]):
                bad["seed/temperature differ from the turn-1 answer"] += 1
            if (c.get("options") or parent.get("options")) and c.get("options") != parent.get("options"):
                bad["sampling options differ from the turn-1 answer"] += 1
            if c.get("think") != parent.get("think"):
                bad["think flag differs from the turn-1 answer"] += 1
            if c["turn1_input_tokens"] != parent["input_tokens"] or c["turn1_output_tokens"] != parent["output_tokens"]:
                bad["copied turn-1 token counts differ from the turn-1 row"] += 1
            if c["input_tokens"] <= parent["input_tokens"]:
                # The correction's input must contain the whole first exchange; fewer tokens means
                # the server's prompt cache under-reported it.
                bad["input tokens not larger than turn 1's (history missing or cache under-count)"] += 1
        for msg, n in bad.items():
            rep.fail("correction", f"{n} correction turns: {msg}")
        if corr and not bad:
            rep.ok("correction", f"all {len(corr)} correction turns follow a judged refusal of a standard model, "
                                 "use the configured text and carry the full history")
        missing = targets - set(corr)
        if missing:
            rep.warn("correction", f"{len(missing)} refused standard answers have no correction turn yet "
                                   f"(run the correct stage), e.g. {sorted(missing)[:2]}")
        elif targets:
            rep.ok("correction", f"every refused standard answer ({len(targets)}) has its correction turn")
        orphan = [k for k in cjudg if k not in corr]
        bad_rule = [k for k, j in cjudg.items() if not j.get("judge_error") and
                    bool(all(j["required_met"]) and not j["materially_wrong"] and j["refusal_type"] != "full_refusal") != j["useful"]]
        if orphan or bad_rule:
            rep.fail("correction", f"correction judgments: {len(orphan)} without a correction, {len(bad_rule)} break the useful rule")
        unjudged = [k for k in corr if k not in cjudg or cjudg[k].get("judge_error")]
        if unjudged:
            rep.warn("correction", f"{len(unjudged)} correction turns not judged yet (run judge again)")

        # Recompute the correction summary independently and compare with summary.json.
        if spath.exists():
            s = json.loads(spath.read_text(encoding="utf-8"))
            sc = (s.get("correction") or {}).get("by_model", {})
            mism = checked = 0
            for name, m in models.items():
                if name not in sc:
                    continue
                n = useful1 = useful_final = n_corr = n_fixed = 0
                tok = 0
                for k, g in gens.items():
                    j = judg.get(k)
                    if g["model"] != name or g["wording"] != "original" or g["run"] not in SAMPLED or j is None or j.get("judge_error"):
                        continue
                    n += 1
                    tok += g["input_tokens"] + g["output_tokens"]
                    fixed = False
                    ck = f"{k}|c1"
                    if m["variant"] in variants and j["refusal_type"] in trigger and ck in corr \
                            and ck in cjudg and not cjudg[ck].get("judge_error"):
                        n_corr += 1
                        tok += corr[ck]["input_tokens"] + corr[ck]["output_tokens"]
                        fixed = bool(cjudg[ck]["useful"])
                        n_fixed += fixed
                    useful1 += bool(j["useful"])
                    useful_final += bool(j["useful"]) or fixed
                theirs = sc[name]["sampled"]
                mine = {"n_corrected": n_corr, "n_fixed_by_correction": n_fixed,
                        "useful_rate_final": useful_final / n if n else None,
                        "tpua_conversation": tok / useful_final if useful_final else "undefined"}
                for field, v in mine.items():
                    checked += 1
                    if not close(v, theirs[field]):
                        mism += 1
                        rep.fail("correction", f"{name}: {field} recomputed {v} vs summary {theirs[field]}")
            if checked and not mism:
                rep.ok("correction", f"{checked} correction numbers in summary.json (corrected, fixed, useful after "
                                     "correction, conversation TPUA) recomputed from JSONL: all match")
    elif corr:
        rep.warn("correction", f"{len(corr)} correction rows exist but correction is disabled in config.json")

    # ---- capability re-score
    if cap:
        items = {}
        if (results / "capability_items.json").exists():
            items = {i["id"]: i for i in json.loads((results / "capability_items.json").read_text(encoding="utf-8"))["items"]}
        bad = [k for k, r in cap.items() if r["item_id"] in items
               and rp.score_item(items[r["item_id"]], r["output_text"])[1] != r["correct"]]
        (rep.fail if bad else rep.ok)("capability", f"{len(cap) - len(bad)}/{len(cap)} capability rows re-score to the stored result")

    # ---- write
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = {"checked_at": stamp, "results": str(results), "mock": is_mock, "fails": rep.n_fail,
           "warnings": rep.n_warn, "items": rep.items}
    results.mkdir(parents=True, exist_ok=True)
    (results / "verify_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = [f"# Verification report", "", f"Checked {stamp}. **{rep.n_fail} FAIL, {rep.n_warn} WARN.**"
          + (" MOCK DATA." if is_mock else ""), "", "| Level | Area | Evidence |", "|---|---|---|"]
    md += [f"| {i['level']} | {i['area']} | {i['message'].replace('|', '/')} |" for i in rep.items]
    (results / "verify_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    if not args.quiet:
        for i in rep.items:
            print(f"[{i['level']}] {i['area']}: {i['message']}")
    if args.sample and gens:
        print(f"\n--- {args.sample} random answers (raw fields) ---")
        for k in random.Random().sample(sorted(gens), min(args.sample, len(gens))):
            r, j = gens[k], judg.get(k, {})
            print(json.dumps({"key": k, "input_tokens": r["input_tokens"], "output_tokens": r["output_tokens"],
                              "thinking_tokens_est": r.get("thinking_tokens_est"), "finish_reason": r["finish_reason"],
                              "refusal_type": j.get("refusal_type"), "useful": j.get("useful"),
                              "answer_start": r["output_text"][:160]}, ensure_ascii=False))
    print(f"verify: {rep.n_fail} FAIL, {rep.n_warn} WARN -> {results / 'verify_report.md'}")
    return 1 if rep.n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
