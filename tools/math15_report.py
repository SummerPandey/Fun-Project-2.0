#!/usr/bin/env python3
"""Write pilot3_screening/math15/math.md and STATUS.json from the two batches' raw files.

Every number is computed here from generations/judgments JSONL (plus verify_report.json for the
FAIL/WARN counts). Nothing is typed by hand.

Conventions:
  * sampled runs only (s1..s5; greedy excluded)
  * correct = the judge marked the first checklist R item (the final answer vs answer_key) as met
  * refusal = judge label full_refusal or partial_refusal
  * TPCA = sum(input + output tokens) / number of correct answers
  * raw tokens are never pooled across families; per-question token column = mean of the
    three abliterated/standard family ratios
  * wording: 'game' = the prompt as written (game-framed), 'plain' = neutral_twin (plain math)
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from health20_report import jsonl, gkey, ratio, f2, pct, frac, mean_ratio  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STUDY = "math15"
BATCHES = ("batchA", "batchB")
TOTAL = 1080
SCR = ROOT / "pilot3_screening" / STUDY
RESULTS_ROOT = SCR
DESIGN = ROOT / "pilot3_design" / STUDY
LOG = ROOT / "logs" / f"{STUDY}.log"
PIDFILE = ROOT / "logs" / f"{STUDY}.pid"
REFUSE = ("full_refusal", "partial_refusal")


def load():
    cfg = json.loads((ROOT / "pilot3_screening" / STUDY / BATCHES[0] / "config.json").read_text(encoding="utf-8"))
    fams = []
    for m in cfg["models"]:
        if m["family"] not in fams:
            fams.append(m["family"])
    fam_models = {f: {m["variant"]: m["name"] for m in cfg["models"] if m["family"] == f} for f in fams}
    questions, rows, judged, verify = [], [], {}, {}
    n_gen = n_judged = 0
    for b in BATCHES:
        prompts = json.loads((DESIGN / b / "prompts.json").read_text(encoding="utf-8"))["prompts"]
        pid2q = {p["id"]: p["screen_id"] for p in prompts}
        questions += [{"qid": p["screen_id"], "text": p["neutral_twin"]} for p in prompts]
        res = RESULTS_ROOT / b / "results"
        gens = jsonl(res / "generations.jsonl")
        n_gen += len(gens)
        rows += [dict(r, qid=pid2q[r["prompt_id"]], batch=b) for r in gens]
        for j in jsonl(res / "judgments.jsonl"):
            if not j.get("judge_error"):
                judged[(b, j["key"])] = j
                n_judged += 1
        if (res / "verify_report.json").exists():
            verify[b] = json.loads((res / "verify_report.json").read_text(encoding="utf-8"))
    return dict(fams=fams, fam_models=fam_models, questions=questions, rows=rows, judged=judged,
                n_gen=n_gen, n_judged=n_judged, verify=verify)


def stats(D, model, wording, qids=None):
    sel = [r for r in D["rows"] if r["model"] == model and r["wording"] == wording
           and r["run"] != "greedy" and (qids is None or r["qid"] in qids)]
    jd = [(r, D["judged"][(r["batch"], gkey(r))]) for r in sel if (r["batch"], gkey(r)) in D["judged"]]
    correct = sum(bool(j.get("required_met") and j["required_met"][0]) for _, j in jd)
    # an empty visible answer that stopped at the token cap is "no answer", not a refusal
    # (the judge labels these full_refusal; the answer audits confirmed none contain a decline)
    empty = lambda r: r.get("finish_reason") == "length" and not (r.get("output_text") or "").strip()
    tok = sum(r["input_tokens"] + r["output_tokens"] for r, _ in jd)
    return {"n": len(sel), "n_judged": len(jd),
            "mean_out": sum(r["output_tokens"] for r in sel) / len(sel) if sel else None,
            "correct": correct, "ref": sum(j["refusal_type"] in REFUSE and not empty(r) for r, j in jd),
            "noans": sum(empty(r) for r in sel),
            "tpca": tok / correct if correct else None}


def run_state():
    log = LOG.read_text(encoding="utf-8", errors="replace") if LOG.exists() else ""
    stages = re.findall(r"^=== \S+ (\S+) stage (.+)$", log, re.M)
    stage = f"{stages[-1][0]} {stages[-1][1]}" if stages else "not started"
    alive = False
    if PIDFILE.exists():
        try:
            os.kill(int(PIDFILE.read_text().strip()), 0)
            alive = True
        except (ValueError, ProcessLookupError, PermissionError):
            pass
    if f"FINISHED {STUDY}" in log:
        return "finished", "finished"
    return ("running" if alive else "error"), stage


HEAD = ("| family | accuracy std→abl (game) | accuracy std→abl (plain) | out tokens abl/std (game) "
        "| TPCA abl/std (game) | TPCA abl/std (plain) | no answer (ran out of tokens) std→abl |\n"
        "|---|--:|--:|--:|--:|--:|--:|")


def main():
    global RESULTS_ROOT, SCR
    ap = argparse.ArgumentParser()
    ap.add_argument("--last-error", default=None, help="set last_error in STATUS.json ('' clears it)")
    ap.add_argument("--results-root", default=None, help="test only: read batches from here, write report there")
    a = ap.parse_args()
    if a.results_root:
        RESULTS_ROOT = SCR = Path(a.results_root)
    D = load()
    state, stage = run_state()
    vf = sum(v.get("fails", 0) for v in D["verify"].values())
    vw = sum(v.get("warnings", 0) for v in D["verify"].values())
    vtxt = " · ".join(f"{b} {v.get('fails', 0)} FAIL / {v.get('warnings', 0)} WARN"
                      for b, v in D["verify"].items()) or "not run yet"

    status_p = SCR / "STATUS.json"
    prev = json.loads(status_p.read_text()) if status_p.exists() else {}
    last_error = prev.get("last_error") if a.last_error is None else (a.last_error or None)
    if state == "error" and not last_error:
        last_error = f"runner not running and not finished (last stage: {stage}); see logs/{STUDY}.log"
    status_p.parent.mkdir(parents=True, exist_ok=True)
    status_p.write_text(json.dumps({
        "updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "state": state,
        "answers_done": D["n_gen"], "answers_total": TOTAL, "judged": D["n_judged"], "stage": stage,
        "verify_fail": vf, "verify_warn": vw, "last_error": last_error}, indent=2) + "\n", encoding="utf-8")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    st = f"FINISHED {D['n_gen']:,}/{TOTAL:,}" if state == "finished" else \
        f"{state.upper()} {D['n_gen']:,}/{TOTAL:,} answers · judged {D['n_judged']:,} · stage: {stage}"
    L = ["# Math-15: standard vs abliterated", "", f"**{st}** · updated {now} · verify: {vtxt}", "",
         "Sampled runs (n=5 per question and wording). Game = the game-framed wording, plain = the same problem "
         "as plain math. Correct = the judge says the final answer matches the key. Ratios are abliterated/standard "
         "within a family. TPCA = tokens per correct answer (input+output).", "",
         "## Headline (all 15 questions)", "", HEAD]
    for f in D["fams"]:
        s, ab = D["fam_models"][f]["standard"], D["fam_models"][f]["abliterated"]
        sg, ag, sp, apl = (stats(D, s, "original"), stats(D, ab, "original"),
                           stats(D, s, "twin"), stats(D, ab, "twin"))
        L.append(f"| {f} | {pct(sg['correct'], sg['n_judged'])} → {pct(ag['correct'], ag['n_judged'])} | "
                 f"{pct(sp['correct'], sp['n_judged'])} → {pct(apl['correct'], apl['n_judged'])} | "
                 f"{f2(ratio(ag['mean_out'], sg['mean_out']))} | {f2(ratio(ag['tpca'], sg['tpca']))} | "
                 f"{f2(ratio(apl['tpca'], sp['tpca']))} | "
                 f"{frac(sg['noans'] + sp['noans'], sg['n'] + sp['n'])} → {frac(ag['noans'] + apl['noans'], ag['n'] + apl['n'])} |")
    L += ["", "## Per question (pooled over the 3 families; tokens = mean of the 3 family ratios)", "",
          "| id | question | accuracy std→abl (game) | accuracy std→abl (plain) | out tokens abl/std (game) "
          "| refusals std→abl (both wordings) | no answer std→abl (both wordings) |", "|---|---|--:|--:|--:|--:|--:|"]
    for q in sorted(D["questions"], key=lambda q: int(q["qid"][1:])):
        agg = {k: 0 for k in ("sgc", "sgn", "agc", "agn", "spc", "spn", "apc", "apn", "sr", "sn", "ar", "an",
                              "se", "sa", "ae", "aa")}
        ratios = []
        for f in D["fams"]:
            s, ab = D["fam_models"][f]["standard"], D["fam_models"][f]["abliterated"]
            sg, ag = stats(D, s, "original", {q["qid"]}), stats(D, ab, "original", {q["qid"]})
            sp, apl = stats(D, s, "twin", {q["qid"]}), stats(D, ab, "twin", {q["qid"]})
            for pre, x in (("sg", sg), ("ag", ag), ("sp", sp), ("ap", apl)):
                agg[pre + "c"] += x["correct"]; agg[pre + "n"] += x["n_judged"]
            agg["sr"] += sg["ref"] + sp["ref"]; agg["sn"] += sg["n_judged"] + sp["n_judged"]
            agg["ar"] += ag["ref"] + apl["ref"]; agg["an"] += ag["n_judged"] + apl["n_judged"]
            agg["se"] += sg["noans"] + sp["noans"]; agg["sa"] += sg["n"] + sp["n"]
            agg["ae"] += ag["noans"] + apl["noans"]; agg["aa"] += ag["n"] + apl["n"]
            ratios.append(ratio(ag["mean_out"], sg["mean_out"]))
        words = q["text"].split()
        short = " ".join(words[:8]) + (" …" if len(words) > 8 else "")
        L.append(f"| {q['qid']} | {short} | {frac(agg['sgc'], agg['sgn'])} → {frac(agg['agc'], agg['agn'])} | "
                 f"{frac(agg['spc'], agg['spn'])} → {frac(agg['apc'], agg['apn'])} | {f2(mean_ratio(ratios))} | "
                 f"{frac(agg['sr'], agg['sn'])} → {frac(agg['ar'], agg['an'])} | "
                 f"{frac(agg['se'], agg['sa'])} → {frac(agg['ae'], agg['aa'])} |")
    L += ["", "## Caveats", "",
          "- Development prompts; descriptive pilot numbers, not main results.",
          "- Raw token counts are compared within a family only (each family has its own tokenizer); "
          "across families only abl/std ratios.",
          "- Accuracy comes from the judge comparing each answer with the key (first checklist item); M15 is "
          "very hard by hand, so expect low accuracy there.",
          "- max_tokens is 16,384 for math (4,096 for health). Thinking models (Qwen, Gemma) often still ran out "
          "while thinking and showed no answer; these count as not correct and appear under 'no answer'. "
          "Gemma abliterated mostly looped (repeating the same lines) until the cap.",
          "- The judge labels an empty, token-capped answer as full_refusal; answer audits found no decline in any "
          "of them, so this page counts them as 'no answer', not as refusals. The runner's follow-up turn still "
          "fired on them for standard models (it uses the judge label).",
          "- A few answers have no usable judgment after the retry (judge_error); they are left out of accuracy and "
          "refusal counts (n is the judged count).", "",
          "<sub>Generated by tools/math15_report.py from pilot3_screening/math15/batch*/results. batchA = M01-M10, "
          "batchB = M11-M15 (renumbered P01.. for the runner; original id in screen_id).</sub>", ""]
    (SCR / "math.md").write_text("\n".join(L), encoding="utf-8")
    print(f"math.md + STATUS.json: {state}, {D['n_gen']}/{TOTAL} answers, judged {D['n_judged']}, "
          f"verify {vf} FAIL {vw} WARN, stage {stage}")


if __name__ == "__main__":
    main()
