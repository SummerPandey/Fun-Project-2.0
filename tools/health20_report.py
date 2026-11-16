#!/usr/bin/env python3
"""Write pilot3_screening/health20/health.md and STATUS.json from the two batches' raw files.

Every number is computed here from generations/judgments/corrections JSONL (plus
verify_report.json for the FAIL/WARN counts). Nothing is typed by hand. As a self-check, the
per-model mean output tokens recomputed from the JSONL are compared with each batch's
summary.json; a mismatch is shown in the header (it means `analyze` is behind the data).

Conventions (same as pilot/run_pilot.py summarize):
  * sampled runs only (s1..s5; greedy excluded)
  * refusal = judge label full_refusal or partial_refusal
  * TPUA = sum(input + output tokens) / number of useful answers
  * raw tokens are never pooled across families; per-question token column = mean of the
    three abliterated/standard family ratios
"""
import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = "health20"
BATCHES = ("batchA", "batchB")
TOTAL = 1440
SCR = ROOT / "pilot3_screening" / STUDY
DESIGN = ROOT / "pilot3_design" / STUDY
LOG = ROOT / "logs" / f"{STUDY}.log"
PIDFILE = ROOT / "logs" / f"{STUDY}.pid"
REFUSE = ("full_refusal", "partial_refusal")


def jsonl(p: Path):
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # a line being written right now
    return out


def gkey(r):
    return f"{r['model']}|{r['prompt_id']}|{r['wording']}|{r['run']}"


RESULTS_ROOT = SCR   # --results-root overrides (mock tests write to /tmp; never into SCR)


def load():
    cfg = json.loads((ROOT / "pilot3_screening" / STUDY / BATCHES[0] / "config.json").read_text(encoding="utf-8"))
    fams = []
    for m in cfg["models"]:
        if m["family"] not in fams:
            fams.append(m["family"])
    fam_models = {f: {m["variant"]: m["name"] for m in cfg["models"] if m["family"] == f} for f in fams}
    questions, rows, judged = [], [], {}
    corr_j, corr = {}, {}
    n_gen = n_judged = 0
    summaries, verify = {}, {}
    for b in BATCHES:
        prompts = json.loads((DESIGN / b / "prompts.json").read_text(encoding="utf-8"))["prompts"]
        pid2q = {p["id"]: p["screen_id"] for p in prompts}
        for p in prompts:
            questions.append({"qid": p["screen_id"], "tier": p["tier"], "text": p["prompt"]})
        res = RESULTS_ROOT / b / "results"
        gens = jsonl(res / "generations.jsonl")
        n_gen += len(gens)
        for r in gens:
            rows.append(dict(r, qid=pid2q[r["prompt_id"]], batch=b))
        for j in jsonl(res / "judgments.jsonl"):
            if not j.get("judge_error"):
                judged[(b, j["key"])] = j
                n_judged += 1
        for c in jsonl(res / "corrections.jsonl"):
            corr[(b, c["parent_key"])] = c
        for j in jsonl(res / "correction_judgments.jsonl"):
            if not j.get("judge_error"):
                corr_j[(b, j["key"])] = j
        if (res / "summary.json").exists():
            summaries[b] = json.loads((res / "summary.json").read_text(encoding="utf-8"))
        if (res / "verify_report.json").exists():
            verify[b] = json.loads((res / "verify_report.json").read_text(encoding="utf-8"))
    return dict(fams=fams, fam_models=fam_models, questions=questions, rows=rows, judged=judged,
                corr=corr, corr_j=corr_j, n_gen=n_gen, n_judged=n_judged,
                summaries=summaries, verify=verify)


def stats(D, model, wording, qids=None):
    """Sampled-run stats for one model and wording, over the given questions (None = all)."""
    sel = [r for r in D["rows"] if r["model"] == model and r["wording"] == wording
           and r["run"] != "greedy" and (qids is None or r["qid"] in qids)]
    js = [(r, D["judged"].get((r["batch"], gkey(r)))) for r in sel]
    jd = [(r, j) for r, j in js if j is not None]
    n_ref = sum(j["refusal_type"] in REFUSE for _, j in jd)
    n_use = sum(bool(j["useful"]) for _, j in jd)
    tok = sum(r["input_tokens"] + r["output_tokens"] for r, _ in jd)
    fixed = corrected = 0
    for r, j in jd:
        if j["refusal_type"] in REFUSE:
            cj = D["corr_j"].get((r["batch"], gkey(r) + "|c1"))
            if cj is not None:
                corrected += 1
                fixed += bool(cj["useful"])
    return {
        "n": len(sel), "n_judged": len(jd),
        "mean_out": sum(r["output_tokens"] for r in sel) / len(sel) if sel else None,
        "ref": n_ref, "use": n_use,
        "tpua": tok / n_use if n_use else None,
        "fixed": fixed, "corrected": corrected,
    }


def ratio(a, s):
    return a / s if (a is not None and s not in (None, 0)) else None


def f2(x):
    return "–" if x is None else f"{x:.2f}"


def pct(k, n):
    return "–" if not n else f"{100 * k / n:.0f}%"


def frac(k, n):
    return "–" if not n else f"{k}/{n}"


def mean_ratio(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def headline_rows(D, qids=None):
    out = []
    for f in D["fams"]:
        s_name, a_name = D["fam_models"][f]["standard"], D["fam_models"][f]["abliterated"]
        so, ao = stats(D, s_name, "original", qids), stats(D, a_name, "original", qids)
        st, at = stats(D, s_name, "twin", qids), stats(D, a_name, "twin", qids)
        out.append(f"| {f} | {f2(ratio(ao['mean_out'], so['mean_out']))} | {f2(ratio(ao['tpua'], so['tpua']))} | "
                   f"{pct(so['ref'], so['n_judged'])} → {pct(ao['ref'], ao['n_judged'])} | "
                   f"{pct(st['ref'], st['n_judged'])} → {pct(at['ref'], at['n_judged'])} | "
                   f"{pct(so['use'], so['n_judged'])} → {pct(ao['use'], ao['n_judged'])} |")
    return out


HEAD = ("| family | out tokens abl/std | TPUA abl/std | refusals std→abl (scary) | "
        "refusals std→abl (plain) | useful std→abl (scary) |\n|---|--:|--:|--:|--:|--:|")


def summary_check(D):
    """Recomputed per-model mean output tokens vs summary.json, per batch. Returns problems."""
    bad = []
    for b, s in D["summaries"].items():
        for model, bm in s.get("by_model", {}).items():
            for w in ("original", "twin"):
                want = bm.get("sampled", {}).get(w, {}).get("mean_output_tokens")
                sel = [r["output_tokens"] for r in D["rows"] if r["batch"] == b and r["model"] == model
                       and r["wording"] == w and r["run"] != "greedy"]
                got = sum(sel) / len(sel) if sel else None
                if want is not None and got is not None and abs(want - got) > 0.01:
                    bad.append(f"{b}/{model}/{w}")
    return bad


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
            alive = False
    if f"FINISHED {STUDY}" in log:
        return "finished", "finished"
    return ("running" if alive else "error"), stage


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--last-error", default=None, help="set last_error in STATUS.json ('' clears it)")
    ap.add_argument("--results-root", default=None, help="test only: read batches from here, write report there")
    a = ap.parse_args()
    global RESULTS_ROOT, SCR
    if a.results_root:
        RESULTS_ROOT = SCR = Path(a.results_root)
    D = load()
    state, stage = run_state()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    vf = sum(v.get("fails", 0) for v in D["verify"].values())
    vw = sum(v.get("warnings", 0) for v in D["verify"].values())
    vtxt = " · ".join(f"{b} {v.get('fails', 0)} FAIL / {v.get('warnings', 0)} WARN" for b, v in D["verify"].items()) or "not run yet"
    stale = summary_check(D)

    status_p = SCR / "STATUS.json"
    prev = json.loads(status_p.read_text()) if status_p.exists() else {}
    last_error = prev.get("last_error") if a.last_error is None else (a.last_error or None)
    if state == "error" and not last_error:
        last_error = f"runner not running and not finished (last stage: {stage}); see logs/{STUDY}.log"
    status = {"updated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "state": state,
              "answers_done": D["n_gen"], "answers_total": TOTAL, "judged": D["n_judged"], "stage": stage,
              "verify_fail": vf, "verify_warn": vw, "last_error": last_error}
    status_p.write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")

    st_txt = f"FINISHED {D['n_gen']:,}/{TOTAL:,}" if state == "finished" else \
        f"{state.upper()} {D['n_gen']:,}/{TOTAL:,} answers · judged {D['n_judged']:,} · stage: {stage}"
    L = [f"# Health-20: standard vs abliterated", "",
         f"**{st_txt}** · updated {now} · verify: {vtxt}"]
    if stale:
        L.append(f"⚠ summary.json behind the data for {len(stale)} model/wording cells (re-run analyze)")
    L += ["", "Sampled runs (n=5 per question and wording). Ratios are abliterated/standard within a family. "
          "Refusal = judge label full or partial. TPUA = tokens per useful answer (input+output).", "",
          "## Headline (all 20 questions)", "", HEAD, *headline_rows(D), ""]

    # per-question table
    L += ["## Per question (pooled over the 3 families; tokens = mean of the 3 family ratios)", "",
          "| id | question | tier | refusals std→abl (scary) | refusals std→abl (plain) | useful std→abl (scary) "
          "| out tokens abl/std (scary) | fixed by follow-up |",
          "|---|---|---|--:|--:|--:|--:|--:|"]
    for q in sorted(D["questions"], key=lambda q: int(q["qid"][1:])):
        agg = {k: 0 for k in ("so_ref", "so_n", "ao_ref", "ao_n", "st_ref", "st_n", "at_ref", "at_n",
                              "so_use", "ao_use", "fixed", "corr")}
        ratios = []
        for f in D["fams"]:
            s_name, a_name = D["fam_models"][f]["standard"], D["fam_models"][f]["abliterated"]
            so, ao = stats(D, s_name, "original", {q["qid"]}), stats(D, a_name, "original", {q["qid"]})
            st, at = stats(D, s_name, "twin", {q["qid"]}), stats(D, a_name, "twin", {q["qid"]})
            for pre, x in (("so", so), ("ao", ao), ("st", st), ("at", at)):
                agg[pre + "_ref"] += x["ref"]; agg[pre + "_n"] += x["n_judged"]
            agg["so_use"] += so["use"]; agg["ao_use"] += ao["use"]
            agg["fixed"] += so["fixed"]; agg["corr"] += so["corrected"]
            ratios.append(ratio(ao["mean_out"], so["mean_out"]))
        words = q["text"].split()
        short = " ".join(words[:8]) + (" …" if len(words) > 8 else "")
        tier = "justified" if q["tier"] == "justified" else "over-refusal"
        r = lambda pre: frac(agg[pre + "_ref"], agg[pre + "_n"])
        L.append(f"| {q['qid']} | {short} | {tier} | {r('so')} → {r('ao')} | {r('st')} → {r('at')} | "
                 f"{frac(agg['so_use'], agg['so_n'])} → {frac(agg['ao_use'], agg['ao_n'])} | "
                 f"{f2(mean_ratio(ratios))} | {frac(agg['fixed'], agg['corr'])} |")
    L += ["", "Fixed by follow-up = standard answers to the scary wording that were refused, got the "
          "follow-up \"To be clear, I mean: <plain wording>\", and were useful after it (fixed/followed up).", ""]

    # tiers
    L += ["## By tier", ""]
    for tier_name, pred in (("justified", lambda t: t == "justified"), ("over-refusal", lambda t: t != "justified")):
        qids = {q["qid"] for q in D["questions"] if pred(q["tier"])}
        L += [f"**{tier_name}** ({len(qids)} questions)", "", HEAD, *headline_rows(D, qids), ""]

    L += ["## Caveats", "",
          "- Development prompts; descriptive pilot numbers, not main results.",
          "- Raw token counts are compared within a family only (each family has its own tokenizer); "
          "across families only abl/std ratios.",
          "- The judge over-labels refusals (especially for Llama), so refusal counts are upper bounds.", "",
          f"<sub>Generated by tools/health20_report.py from pilot3_screening/health20/batch*/results. "
          f"Questions P01-P05 come from screen1, H06-H20 from medical_set2; batchA = P01-P05 + H06-H10, "
          f"batchB = H11-H20 (renumbered P01-P10 for the runner; original id in screen_id).</sub>", ""]
    (SCR / "health.md").write_text("\n".join(L), encoding="utf-8")
    print(f"health.md + STATUS.json: {state}, {D['n_gen']}/{TOTAL} answers, judged {D['n_judged']}, "
          f"verify {vf} FAIL {vw} WARN, stage {stage}")


if __name__ == "__main__":
    main()
