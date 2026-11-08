#!/usr/bin/env python3
"""Follow-up tokenomics for Pilot 3 screening iteration 1 (development prompts, descriptive only).

Reads pilot3_screening/screen1/results/ (read-only) and writes
pilot3_design/screen1/analysis/tokenomics.{json,csv}.

For every prompt x standard model it compares three ways a user can end up with an answer:
  twin      ask the neutral wording directly (one turn)            -> the "no trigger" baseline
  original  ask the alarming wording and stop there (one turn)
  followup  ask the alarming wording; if the judge calls it a refusal, send
            "To be clear, I mean: <twin>" in the same conversation (the runner's `correct` stage)

Token measures per attempt:
  out       generated tokens (thinking + answer)
  billable  input + output tokens of every call (a follow-up re-sends the history, so its
            input includes turn 1)
Useful = the judge's `useful` flag (turn 2's flag for a corrected attempt).
TPUA = total tokens / useful answers.  'safety tax' = followup vs twin, in % of twin.

If corrections.jsonl is missing, the followup strategy is reported as pending (None).
Raw token counts are compared within a model only (each family has its own tokenizer).
Usage: python3 pilot3_design/screen1/tokenomics.py [results_dir] [out_dir]
"""
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "pilot3_screening/screen1/results"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).resolve().parent / "analysis"
PROMPTS = json.loads((Path(__file__).resolve().parent / "prompts.json").read_text())["prompts"]
REFUSAL = {"full_refusal", "partial_refusal"}


def jsonl(name):
    p = RES / name
    if not p.exists():
        return None
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


def key(r):
    return r.get("key") or f"{r['model']}|{r['prompt_id']}|{r['wording']}|{r['run']}"


gens = {key(r): r for r in jsonl("generations.jsonl")}
judg = {key(r): r for r in jsonl("judgments.jsonl")}
corr_rows = jsonl("corrections.jsonl")
cj_rows = jsonl("correction_judgments.jsonl") or []
corr = {r["parent_key"]: r for r in (corr_rows or [])}
cjudg = {r["key"]: r for r in cj_rows}
followup_available = corr_rows is not None

meta = {p["id"]: p for p in PROMPTS}
cells = defaultdict(lambda: defaultdict(list))  # (model, pid) -> strategy -> list of attempts
missing = []

for k, g in gens.items():
    j = judg.get(k)
    if j is None:
        missing.append(k)
        continue
    m, pid, w = g["model"], g["prompt_id"], g["wording"]
    t1 = {
        "out": g["output_tokens"],
        "billable": g["input_tokens"] + g["output_tokens"],
        "useful": bool(j.get("useful")),
        "refused": j.get("refusal_type") in REFUSAL,
        "thinking": g.get("thinking_tokens_est") or 0,
    }
    if w == "twin":
        cells[(m, pid)]["twin"].append(dict(t1, turns=1))
        continue
    cells[(m, pid)]["original"].append(dict(t1, turns=1))
    if not followup_available:
        continue
    att = dict(t1, turns=1, corrected=False, fixed=False)
    if t1["refused"]:
        c = corr.get(k)
        cj = cjudg.get(c["key"]) if c else None
        if c is None or cj is None:
            att["pending"] = True
        else:
            att.update(
                turns=2,
                corrected=True,
                out=t1["out"] + c["output_tokens"],
                billable=t1["billable"] + c["input_tokens"] + c["output_tokens"],
                useful=bool(cj.get("useful")),
                fixed=bool(cj.get("useful")),
                turn2_out=c["output_tokens"],
                turn2_refused=cj.get("refusal_type") in REFUSAL,
            )
    cells[(m, pid)]["followup"].append(att)


def summarise(atts):
    if not atts:
        return None
    n = len(atts)
    useful = sum(a["useful"] for a in atts)
    out = sum(a["out"] for a in atts)
    bill = sum(a["billable"] for a in atts)
    s = {
        "n": n,
        "refusal_rate_turn1": round(sum(a["refused"] for a in atts) / n, 4),
        "useful_rate": round(useful / n, 4),
        "mean_out": round(out / n, 1),
        "mean_billable": round(bill / n, 1),
        "mean_thinking": round(sum(a["thinking"] for a in atts) / n, 1),
        "tpua_out": round(out / useful, 1) if useful else None,
        "tpua_billable": round(bill / useful, 1) if useful else None,
        "mean_turns": round(sum(a["turns"] for a in atts) / n, 3),
    }
    if "corrected" in atts[0]:
        nc = sum(a["corrected"] for a in atts)
        s.update(
            n_corrected=nc,
            n_fixed=sum(a["fixed"] for a in atts),
            n_pending=sum(bool(a.get("pending")) for a in atts),
            correction_rate=round(sum(a["fixed"] for a in atts) / nc, 4) if nc else None,
            still_refused_after_followup=sum(bool(a.get("turn2_refused")) for a in atts),
        )
    return s


def pct(a, b):
    return round(100 * (a - b) / b, 1) if a is not None and b not in (None, 0) else None


rows = []
for (m, pid), strat in sorted(cells.items(), key=lambda x: (x[0][1], x[0][0])):
    p = meta[pid]
    tw, og, fu = (summarise(strat.get(s)) for s in ("twin", "original", "followup"))
    row = {
        "model": m,
        "family": m.split("-")[0],
        "prompt_id": pid,
        "screen_id": p.get("screen_id"),
        "domain": p.get("domain"),
        "tier": p.get("tier"),
        "prompt": p["prompt"],
        "twin_text": p["neutral_twin"],
        "twin": tw,
        "original": og,
        "followup": fu,
        "diff": {
            "refusal_pts_original_minus_twin": round(100 * (og["refusal_rate_turn1"] - tw["refusal_rate_turn1"]), 1),
            "out_pct_original_vs_twin": pct(og["mean_out"], tw["mean_out"]),
            "out_pct_followup_vs_twin": pct(fu["mean_out"], tw["mean_out"]) if fu else None,
            "billable_pct_followup_vs_twin": pct(fu["mean_billable"], tw["mean_billable"]) if fu else None,
            "tpua_out_pct_followup_vs_twin": pct(fu["tpua_out"], tw["tpua_out"]) if fu else None,
            "tpua_billable_pct_followup_vs_twin": pct(fu["tpua_billable"], tw["tpua_billable"]) if fu else None,
        },
    }
    rows.append(row)

result = {
    "label": "Pilot 3 screening iteration 1 - development prompts, descriptive only",
    "source": str(RES.relative_to(ROOT)) if RES.is_relative_to(ROOT) else str(RES),
    "followup_available": followup_available,
    "n_corrections": len(corr_rows or []),
    "n_correction_judgments": len(cj_rows),
    "unjudged_turn1": len(missing),
    "notes": [
        "Runs per cell: 5 sampled + 1 greedy = 6.",
        "Twin = no-trigger baseline; the abliterated models were not run in screening.",
        "Token counts compare within a model only (tokenizers differ by family).",
        "Refusal and useful labels are the judge's; the auditor found the judge over-calls refusals (H8).",
    ],
    "rows": rows,
}
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "tokenomics.json").write_text(json.dumps(result, indent=1) + "\n")

flat_cols = ["model", "screen_id", "domain", "tier"]
with (OUT / "tokenomics.csv").open("w", newline="") as f:
    w = csv.writer(f)
    stats = ["n", "refusal_rate_turn1", "useful_rate", "mean_out", "mean_billable", "tpua_out", "tpua_billable", "mean_turns"]
    extra = ["n_corrected", "n_fixed", "n_pending", "correction_rate"]
    header = flat_cols + [f"{s}_{k}" for s in ("twin", "original", "followup") for k in stats] + [f"followup_{k}" for k in extra] + list(rows[0]["diff"])
    w.writerow(header)
    for r in rows:
        line = [r[c] for c in flat_cols]
        for s in ("twin", "original", "followup"):
            line += [(r[s] or {}).get(k) for k in stats]
        line += [(r["followup"] or {}).get(k) for k in extra]
        line += list(r["diff"].values())
        w.writerow(line)

# Flat file for the dashboard: medical prompts only, one row per prompt x model.
LABELS = {"I01": "Tylenol lethal dose", "I02": "Dislocated shoulder", "I03": "Stitch a deep cut",
          "I04": "Drain an abscess", "I05": "Fewest safe calories"}
flat = []
for r in rows:
    if r["domain"] != "medical":
        continue
    tw, og, fu = r["twin"], r["original"], r["followup"]
    fam = r["family"].replace("3.5", "").replace("3.1", "").replace("4", "")
    flat.append({
        "cell": f"{r['screen_id']}|{fam}",
        "screen_id": r["screen_id"],
        "prompt_label": LABELS.get(r["screen_id"], r["screen_id"]),
        "model": fam,
        "tier": r["tier"],
        "n": og["n"],
        "refused_orig": og["refusal_rate_turn1"],
        "refused_twin": tw["refusal_rate_turn1"],
        "refusal_gap_pts": r["diff"]["refusal_pts_original_minus_twin"],
        "useful_orig": og["useful_rate"],
        "useful_twin": tw["useful_rate"],
        "out_orig": og["mean_out"],
        "out_twin": tw["mean_out"],
        "out_change_pct": r["diff"]["out_pct_original_vs_twin"],
        "thinking_orig": og["mean_thinking"],
        "thinking_twin": tw["mean_thinking"],
        "tpua_orig": og["tpua_out"],
        "tpua_twin": tw["tpua_out"],
        "followup_status": "done" if fu and not fu.get("n_pending") else ("partial" if fu else "pending"),
        "fu_corrected": fu.get("n_corrected") if fu else None,
        "fu_fixed": fu.get("n_fixed") if fu else None,
        "fu_useful": fu.get("useful_rate") if fu else None,
        "fu_out": fu.get("mean_out") if fu else None,
        "fu_out_change_pct": r["diff"]["out_pct_followup_vs_twin"],
        "fu_billable_change_pct": r["diff"]["billable_pct_followup_vs_twin"],
        "fu_tpua": fu.get("tpua_out") if fu else None,
        "fu_tpua_change_pct": r["diff"]["tpua_out_pct_followup_vs_twin"],
    })
with (OUT / "medical_flat.csv").open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(flat[0]))
    w.writeheader()
    w.writerows(flat)
(OUT / "medical_flat.json").write_text(json.dumps(flat, indent=1) + "\n")

print(f"followup data: {'yes' if followup_available else 'NOT YET (run correct + judge on hopper)'}; "
      f"{len(rows)} cells; wrote {OUT/'tokenomics.json'} and tokenomics.csv")
