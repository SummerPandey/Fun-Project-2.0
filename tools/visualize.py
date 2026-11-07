#!/usr/bin/env python3
"""Build every figure, the per-prompt comparison table and a self-contained dashboard.

Reads only the run's own files (never invents a number):
  <results>/generations.jsonl, judgments.jsonl, capability.jsonl, summary.json (optional)
Writes:
  <results>/figures/*.png         static charts (shown in the README / GitHub)
  <results>/per_prompt.csv        prompt x wording x model rows, sampled runs s1-s5
  <results>/per_prompt.md         the same as Markdown, paired standard vs abliterated
  <results>/dashboard.html        one file, open in any browser; hover tooltips; table views

Safe to run at any time during a run: missing files or models are shown as gaps, not zeros.

Usage:  python3 tools/visualize.py [--results pilot/results] [--config pilot/config.json]
Needs:  matplotlib (pip install matplotlib)
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLED = ("s1", "s2", "s3", "s4", "s5")
WORDINGS = ("original", "twin")
PROMPTS = [f"P{i:02d}" for i in range(1, 11)]

# Validated with the dataviz skill's validator (light and dark): slot 1 blue, slot 2 orange.
COL = {"standard": "#2a78d6", "abliterated": "#eb6834"}
COL_DARK = {"standard": "#3987e5", "abliterated": "#d95926"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
NEUTRAL = "#8a8984"
SEQ_BLUE = ["#fcfcfb", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            print(f"warning: {path.name} line {n} is not valid JSON (partial write?); skipped", file=sys.stderr)
    return rows


def last_by(rows: list[dict], key) -> dict:
    out = {}
    for r in rows:
        out[key(r)] = r
    return out


def gkey(r: dict) -> str:
    return f"{r['model']}|{r['prompt_id']}|{r['wording']}|{r['run']}"


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def load(results: Path, cfg: dict) -> dict:
    gens = last_by(read_jsonl(results / "generations.jsonl"), gkey)
    judg = last_by(read_jsonl(results / "judgments.jsonl"), lambda r: r["key"])
    cap = last_by(read_jsonl(results / "capability.jsonl"), lambda r: (r["model"], r["item_id"]))
    summary = None
    if (results / "summary.json").exists():
        summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    mock_flags = {bool(r.get("mock")) for r in list(gens.values()) + list(judg.values())}
    n_items = None
    if (results / "capability_items.json").exists():
        n_items = len(json.loads((results / "capability_items.json").read_text(encoding="utf-8"))["items"])
    d = {"gens": gens, "judg": judg, "cap": cap, "summary": summary, "models": cfg["models"],
         "mock": True in mock_flags, "mixed": len(mock_flags) > 1, "n_cap_items": n_items, "cfg": cfg,
         "corr": None}
    if (cfg.get("correction") or {}).get("enabled"):
        # Same code the analyze stage uses, so the figures and summary.md can never disagree.
        rp = load_runner()
        fams = []
        for m in cfg["models"]:
            if m["family"] not in fams:
                fams.append(m["family"])
        n_s = cfg["generation"]["n_sampled"]
        run_sets = {"sampled": [f"s{i}" for i in range(1, n_s + 1)], "greedy": ["greedy"]}
        d["corr"] = rp.correction_summary(cfg, cfg["models"], fams, PROMPTS, run_sets, gens, judg, results, d["mock"])
    return d


def load_runner():
    import importlib.util

    spec = importlib.util.spec_from_file_location("run_pilot", ROOT / "pilot" / "run_pilot.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Per-prompt table (the core comparison: P01-P10, standard vs abliterated)
# ---------------------------------------------------------------------------

def cell_stats(d: dict, model: str, pid: str, wording: str) -> dict:
    rows = [d["gens"].get(f"{model}|{pid}|{wording}|{run}") for run in SAMPLED]
    rows = [r for r in rows if r is not None]
    js = [d["judg"].get(gkey(r)) for r in rows]
    judged = [j for j in js if j is not None and not j.get("judge_error")]
    return {
        "n": len(rows),
        "n_judged": len(judged),
        "mean_output_tokens": mean(r["output_tokens"] for r in rows),
        "mean_thinking_tokens_est": mean(r.get("thinking_tokens_est") or 0 for r in rows) if rows else None,
        "mean_input_tokens": mean(r["input_tokens"] for r in rows),
        "full_refusal_rate": mean(float(j["refusal_type"] == "full_refusal") for j in judged),
        "useful_rate": mean(float(bool(j["useful"])) for j in judged),
        "cap_hit_rate": mean(float(bool(r["hit_cap"])) for r in rows),
    }


def per_prompt_rows(d: dict) -> list[dict]:
    out = []
    for m in d["models"]:
        for pid in PROMPTS:
            for w in WORDINGS:
                row = {"family": m["family"], "variant": m["variant"], "model": m["name"],
                       "prompt_id": pid, "wording": w, **cell_stats(d, m["name"], pid, w)}
                c = (d["corr"] or {}).get("per_prompt", {}).get(m["name"], {}).get(pid) if w == "original" else None
                row.update({
                    "turns_allowed": c["turns_allowed"] if c else None,
                    "n_refused_turn1": c["n_refused_turn1"] if c else None,
                    "n_corrected": c["n_corrected"] if c else None,
                    "n_fixed_by_correction": c["n_fixed_by_correction"] if c else None,
                    "correction_rate": c["correction_rate"] if c else None,
                    "useful_rate_final": c["useful_rate_final"] if c else None,
                    "mean_tokens_turn1": c["mean_tokens_turn1"] if c else None,
                    "mean_tokens_conversation": c["mean_tokens_conversation"] if c else None,
                })
                out.append(row)
    return out


def fmt(x, digits=1) -> str:
    if x is None:
        return "–"
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def pct(x) -> str:
    return "–" if x is None else f"{x * 100:.0f}%"


def families(d: dict) -> list[str]:
    seen = []
    for m in d["models"]:
        if m["family"] not in seen:
            seen.append(m["family"])
    return seen


def pair(d: dict, fam: str):
    std = next((m for m in d["models"] if m["family"] == fam and m["variant"] == "standard"), None)
    ab = next((m for m in d["models"] if m["family"] == fam and m["variant"] == "abliterated"), None)
    return std, ab


def write_tables(d: dict, rows: list[dict], results: Path) -> str:
    with (results / "per_prompt.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    idx = {(r["model"], r["prompt_id"], r["wording"]): r for r in rows}
    prompts = {p["id"]: p for p in json.loads((ROOT / "pilot_prompts.json").read_text(encoding="utf-8"))["prompts"]}
    lines = ["# Per-prompt comparison: standard vs abliterated", ""]
    if d["mock"]:
        lines += ["> **MOCK DATA. Synthetic numbers from `--mock`. Not results.**", ""]
    lines += ["Sampled runs s1-s5 only (n = 5 per cell). Tokens are raw counts from each family's own "
              "tokenizer: compare within a row's family only. Refusal and useful rates are judge-based.", ""]
    for fam in families(d):
        std, ab = pair(d, fam)
        if not std or not ab:
            continue
        lines += [f"## {fam}: `{std['repo']}` vs `{ab['repo']}`", "",
                  "| Prompt | Wording | Out tokens std | Out tokens abl | Ratio abl/std | Thinking std | Thinking abl "
                  "| Refusal std | Refusal abl | Useful std | Useful abl | n std/abl |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for pid in PROMPTS:
            for w in WORDINGS:
                s, a = idx[(std["name"], pid, w)], idx[(ab["name"], pid, w)]
                ratio = (a["mean_output_tokens"] / s["mean_output_tokens"]
                         if a["mean_output_tokens"] is not None and s["mean_output_tokens"] else None)
                lines.append(
                    f"| {pid} | {w} | {fmt(s['mean_output_tokens'])} | {fmt(a['mean_output_tokens'])} | "
                    f"{fmt(ratio, 2)} | {fmt(s['mean_thinking_tokens_est'])} | {fmt(a['mean_thinking_tokens_est'])} | "
                    f"{pct(s['full_refusal_rate'])} | {pct(a['full_refusal_rate'])} | {pct(s['useful_rate'])} | "
                    f"{pct(a['useful_rate'])} | {s['n']}/{a['n']} |")
        lines.append("")
    if d["corr"]:
        lines += ["# Correction: abliterated answers in 1 turn, standard gets up to 2", "",
                  f"Original wording, sampled runs. A refused standard answer gets the follow-up "
                  f"\"{d['cfg']['correction']['template']}\". Tokens are input + output; the conversation "
                  "column adds the correction turn (whose input includes the first exchange).", ""]
        for fam in families(d):
            std, ab = pair(d, fam)
            if not std or not ab:
                continue
            lines += [f"## {fam}", "",
                      "| Prompt | Std refused t1 | Corrected | Fixed | Correction % | Std useful t1 | Std useful final "
                      "| Abl useful (1 turn) | Std tokens t1 | Std tokens conversation | Abl tokens |",
                      "|---|---|---|---|---|---|---|---|---|---|---|"]
            for pid in PROMPTS:
                s, a = idx[(std["name"], pid, "original")], idx[(ab["name"], pid, "original")]
                lines.append(
                    f"| {pid} | {fmt(s['n_refused_turn1'])} | {fmt(s['n_corrected'])} | {fmt(s['n_fixed_by_correction'])} | "
                    f"{pct(s['correction_rate'])} | {pct(s['useful_rate'])} | {pct(s['useful_rate_final'])} | "
                    f"{pct(a['useful_rate'])} | {fmt(s['mean_tokens_turn1'])} | {fmt(s['mean_tokens_conversation'])} | "
                    f"{fmt(a['mean_tokens_turn1'])} |")
            g = d["corr"]["gap"].get(fam, {}).get("sampled")
            if g:
                lines += ["", f"Gap: abliterated useful {pct(g['abliterated_useful_rate_one_turn'])} in one turn; standard "
                          f"{pct(g['standard_useful_rate_turn1'])} on turn 1 and {pct(g['standard_useful_rate_after_correction'])} "
                          f"after correction (share of gap closed {fmt(g['share_of_gap_closed_by_correction'], 2)}; correction "
                          f"{pct(g['standard_correction_rate'])}). Tokens per useful answer, standard whole conversation / "
                          f"abliterated: {fmt(g['tpua_ratio_standard_conversation_over_abliterated'], 2)}.", ""]
    lines += ["## Prompt texts", "", "| ID | Original | Neutral twin |", "|---|---|---|"]
    for pid in PROMPTS:
        p = prompts[pid]
        lines.append(f"| {pid} | {p['prompt']} | {p['neutral_twin']} |")
    md = "\n".join(lines) + "\n"
    (results / "per_prompt.md").write_text(md, encoding="utf-8")
    return md


# ---------------------------------------------------------------------------
# Static figures (matplotlib)
# ---------------------------------------------------------------------------

def setup_mpl():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
    })
    return plt


def stamp(fig, d: dict, title: str):
    fig.suptitle(title, x=0.01, ha="left", fontsize=13, fontweight="bold", color=INK)
    note = "MOCK DATA - not results" if d["mock"] else "Pilot 2 - development prompts, descriptive only"
    fig.text(0.99, 0.995, note, ha="right", va="top", fontsize=9,
             color="#b3261e" if d["mock"] else INK2, fontweight="bold" if d["mock"] else "normal")


def finish(plt, fig, out: Path) -> None:
    h = fig.get_size_inches()[1]
    fig.tight_layout(rect=(0, 0, 1, 1 - 0.62 / h))
    fig.savefig(out, dpi=130)
    plt.close(fig)


def legend_above(ax, **kw) -> None:
    """Legend in the band above the plot area, right-aligned, so it never covers a mark."""
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=kw.pop("ncol", 2), fontsize=8,
              borderaxespad=0.2, **kw)


def fig_per_prompt_tokens(plt, d, idx, out: Path):
    fams = families(d)
    fig, axes = plt.subplots(len(fams), 2, figsize=(13, 3.2 * len(fams)), squeeze=False)
    x = range(len(PROMPTS))
    wbar = 0.38
    for r, fam in enumerate(fams):
        std, ab = pair(d, fam)
        for c, w in enumerate(WORDINGS):
            ax = axes[r][c]
            for k, m in enumerate((std, ab)):
                if m is None:
                    continue
                vals = [idx[(m["name"], p, w)]["mean_output_tokens"] for p in PROMPTS]
                xs = [i + (k - 0.5) * wbar for i in x]
                ax.bar([xi for xi, v in zip(xs, vals) if v is not None], [v for v in vals if v is not None],
                       width=wbar - 0.04, color=COL[m["variant"]], label=f"{m['variant']} ({m['repo']})",
                       edgecolor=SURFACE, linewidth=1)
            ax.set_xticks(list(x), PROMPTS)
            ax.set_title(f"{fam} - {w} wording", loc="left")
            ax.set_ylabel("mean output tokens")
            if c == 1:
                legend_above(ax, ncol=1)
    stamp(fig, d, "Output tokens per prompt: standard vs abliterated (sampled runs, n=5 per bar)")
    finish(plt, fig, out)


def fig_refusal_heatmap(plt, d, idx, out: Path):
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("seqblue", SEQ_BLUE)
    cmap.set_bad("#b9b8b3")  # not judged yet: solid grey, never confused with a 0% (near-white) cell
    models = d["models"]
    cols = [(p, w) for p in PROMPTS for w in WORDINGS]
    grid = [[idx[(m["name"], p, w)]["full_refusal_rate"] for p, w in cols] for m in models]
    fig, ax = plt.subplots(figsize=(14, 0.55 * len(models) + 2))
    data = [[(v if v is not None else float("nan")) for v in row] for row in grid]
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.grid(False)
    ax.set_yticks(range(len(models)), [m["name"] for m in models])
    ax.set_xticks(range(len(cols)), [f"{p}\n{'orig' if w == 'original' else 'twin'}" for p, w in cols], fontsize=8)
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            label = "–" if v is None else f"{v * 100:.0f}"
            ax.text(j, i, label, ha="center", va="center", fontsize=7.5,
                    color="#fcfcfb" if (v or 0) > 0.55 else INK)
    for j in range(2, len(cols), 2):
        ax.axvline(j - 0.5, color=SURFACE, linewidth=3)
    cb = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.01)
    cb.set_label("full refusal rate (judge)")
    stamp(fig, d, "Full refusal rate (%) by prompt and wording; grey cells (–) are not judged yet")
    finish(plt, fig, out)


def fig_family_ratios(plt, d, out: Path):
    s = d["summary"]
    if not s:
        return False
    metrics = [("mean_output_tokens", "mean output tokens"), ("tpua", "TPUA (tokens per useful answer)")]
    fams = families(d)
    conds = ("original", "twin", "block")
    fig, axes = plt.subplots(1, 2, figsize=(13, 0.5 * len(fams) * len(conds) + 1.8), squeeze=False)
    for ax, (mt, label) in zip(axes[0], metrics):
        names, vals = [], []
        for fam in fams:
            for c in conds:
                v = s["within_family_ratios"]["sampled"][c][mt]["by_family"].get(fam)
                names.append(f"{fam} · {c}")
                vals.append(v)
        ys = list(range(len(names)))[::-1]
        ax.barh([y for y, v in zip(ys, vals) if v is not None], [v for v in vals if v is not None],
                color=NEUTRAL, height=0.6, edgecolor=SURFACE)
        for y, v in zip(ys, vals):
            ax.text((v or 0) + 0.03, y, fmt(v, 2) if v is not None else "n/a", va="center", fontsize=8, color=INK2)
        ax.axvline(1.0, color=INK, linewidth=1.2, linestyle="--")
        ax.set_yticks(ys, names, fontsize=8)
        ax.set_title(f"abliterated / standard: {label}", loc="left")
        ax.set_xlabel("ratio (1.0 = no difference; >1 = abliterated uses more)")
    stamp(fig, d, "Within-family ratios, sampled runs")
    finish(plt, fig, out)
    return True


def fig_thinking_split(plt, d, out: Path):
    models = d["models"]
    ans, think = [], []
    for m in models:
        rows = [r for r in d["gens"].values() if r["model"] == m["name"] and r["run"] in SAMPLED]
        t = mean(r.get("thinking_tokens_est") or 0 for r in rows) if rows else None
        o = mean(r["output_tokens"] for r in rows) if rows else None
        think.append(t)
        ans.append(None if o is None else o - (t or 0))
    fig, ax = plt.subplots(figsize=(11, 0.6 * len(models) + 1.6))
    ys = list(range(len(models)))[::-1]
    for y, m, a, t in zip(ys, models, ans, think):
        if a is None:
            ax.text(0, y, "  no answers yet", va="center", fontsize=8, color=INK2)
            continue
        c = COL[m["variant"]]
        ax.barh(y, a, color=c, height=0.6, edgecolor=SURFACE, linewidth=2)
        ax.barh(y, t or 0, left=a, color=c, alpha=0.45, hatch="///", height=0.6, edgecolor=SURFACE, linewidth=2)
        ax.text(a + (t or 0) + 5, y, f"{a:.0f} answer + {t or 0:.0f} thinking", va="center", fontsize=8, color=INK2)
    ax.set_yticks(ys, [m["name"] for m in models])
    ax.set_xlabel("mean output tokens per answer (sampled runs)")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=COL["standard"], label="standard: answer"),
                       Patch(color=COL["abliterated"], label="abliterated: answer"),
                       Patch(facecolor="#bbbbbb", hatch="///", edgecolor=SURFACE, label="thinking (est., hatched)")],
              loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=3, fontsize=8)
    stamp(fig, d, "Where output tokens go: visible answer vs hidden thinking (estimate)")
    finish(plt, fig, out)


def fig_capability(plt, d, out: Path):
    fams = families(d)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), squeeze=False)
    for ax, ds in zip(axes[0], ("gsm8k", "mmlu")):
        for k, variant in enumerate(("standard", "abliterated")):
            xs, vs = [], []
            for i, fam in enumerate(fams):
                m = next((m for m in d["models"] if m["family"] == fam and m["variant"] == variant), None)
                rows = [r for r in d["cap"].values() if m and r["model"] == m["name"] and r["dataset"] == ds]
                if rows:
                    xs.append(i + (k - 0.5) * 0.38)
                    vs.append(mean(float(r["correct"]) for r in rows))
            ax.bar(xs, vs, width=0.34, color=COL[variant], label=variant, edgecolor=SURFACE)
            for x, v in zip(xs, vs):
                ax.text(x, v + 0.01, f"{v * 100:.0f}%", ha="center", fontsize=8, color=INK2)
        ax.set_xticks(range(len(fams)), fams)
        ax.set_ylim(0, 1.1)
        ax.set_ylabel("accuracy (greedy)")
        ax.set_title(ds.upper(), loc="left")
        legend_above(ax)
    stamp(fig, d, "Capability check: did abliteration cost accuracy?")
    finish(plt, fig, out)


def fig_token_distribution(plt, d, out: Path):
    fams = families(d)
    fig, axes = plt.subplots(1, len(fams), figsize=(4.2 * len(fams), 3.8), squeeze=False)
    for ax, fam in zip(axes[0], fams):
        std, ab = pair(d, fam)
        data, labels, colors = [], [], []
        for m in (std, ab):
            for w in WORDINGS:
                vals = [r["output_tokens"] for r in d["gens"].values()
                        if m and r["model"] == m["name"] and r["wording"] == w and r["run"] in SAMPLED]
                data.append(vals or [float("nan")])
                labels.append(f"{'std' if m['variant'] == 'standard' else 'abl'}\n{w[:4]}")
                colors.append(COL[m["variant"]])
        bp = ax.boxplot(data, patch_artist=True, widths=0.55, medianprops={"color": INK, "linewidth": 1.5},
                        flierprops={"markersize": 3, "markerfacecolor": NEUTRAL, "markeredgecolor": NEUTRAL})
        for patch, c in zip(bp["boxes"], colors):
            patch.set_facecolor(c)
            patch.set_alpha(0.75)
            patch.set_edgecolor(c)
        ax.set_xticks(range(1, len(labels) + 1), labels, fontsize=8)
        ax.set_title(fam, loc="left")
        ax.set_ylabel("output tokens per answer")
    stamp(fig, d, "Spread of output tokens (sampled runs; std = standard, abl = abliterated)")
    finish(plt, fig, out)


def fig_correction_per_prompt(plt, d, idx, out: Path):
    """Original wording. Standard: turn-1 tokens + correction tokens (hatched) stacked; abliterated: one turn."""
    fams = families(d)
    fig, axes = plt.subplots(len(fams), 1, figsize=(13, 3.3 * len(fams)), squeeze=False)
    wbar = 0.38
    for ax, fam in zip(axes[:, 0], fams):
        std, ab = pair(d, fam)
        if not std or not ab:
            continue
        top = 0
        for i, pid in enumerate(PROMPTS):
            s, a = idx[(std["name"], pid, "original")], idx[(ab["name"], pid, "original")]
            x_s, x_a = i - wbar / 2, i + wbar / 2
            t1, conv = s["mean_tokens_turn1"], s["mean_tokens_conversation"]
            if t1 is not None:
                ax.bar(x_s, t1, width=wbar - 0.04, color=COL["standard"], edgecolor=SURFACE, linewidth=1,
                       label="standard: turn 1" if i == 0 else None)
                extra = (conv or t1) - t1
                ax.bar(x_s, extra, bottom=t1, width=wbar - 0.04, color=COL["standard"], alpha=0.45, hatch="///",
                       edgecolor=SURFACE, linewidth=1, label="standard: correction turn" if i == 0 else None)
                label = f"{s['n_fixed_by_correction']}/{s['n_corrected']}" if s["n_corrected"] else "–"
                ax.text(x_s, (conv or t1) * 1.02, label, ha="center", va="bottom", fontsize=7.5, color=INK2)
                top = max(top, conv or t1)
            if a["mean_tokens_turn1"] is not None:
                ax.bar(x_a, a["mean_tokens_turn1"], width=wbar - 0.04, color=COL["abliterated"], edgecolor=SURFACE,
                       linewidth=1, label="abliterated: one turn" if i == 0 else None)
                top = max(top, a["mean_tokens_turn1"])
        ax.set_ylim(0, top * 1.15 if top else 1)
        ax.set_xticks(range(len(PROMPTS)), PROMPTS)
        ax.set_ylabel("mean tokens per attempt\n(input + output)")
        ax.set_title(f"{fam} - original wording", loc="left")
        legend_above(ax, ncol=3)
    stamp(fig, d, "Cost with correction, per prompt (labels: corrections that worked / corrections sent)")
    finish(plt, fig, out)


def fig_correction_gap(plt, d, out: Path):
    """Per family: useful rate of abliterated (1 turn) vs standard on turn 1 and after correction."""
    gap = d["corr"]["gap"]
    fams = [f for f in families(d) if f in gap]
    if not fams:
        return False
    fig, axes = plt.subplots(1, 2, figsize=(13, 3.9), squeeze=False)
    ax = axes[0][0]
    w = 0.26
    series = (("standard_useful_rate_turn1", "standard, turn 1", COL["standard"], None, 1.0),
              ("standard_useful_rate_after_correction", "standard, after correction", COL["standard"], "///", 0.45),
              ("abliterated_useful_rate_one_turn", "abliterated, one turn", COL["abliterated"], None, 1.0))
    for k, (field, label, color, hatch, alpha) in enumerate(series):
        xs = [i + (k - 1) * w for i in range(len(fams))]
        vals = [gap[f]["sampled"][field] for f in fams]
        ax.bar([x for x, v in zip(xs, vals) if v is not None], [v for v in vals if v is not None], width=w - 0.03,
               color=color, hatch=hatch, alpha=alpha, edgecolor=SURFACE, linewidth=1, label=label)
        for x, v in zip(xs, vals):
            if v is not None:
                ax.text(x, v + 0.015, f"{v * 100:.0f}%", ha="center", fontsize=8, color=INK2)
    ax.set_xticks(range(len(fams)), [f"{f}\ncorrection {pct(gap[f]['sampled']['standard_correction_rate'])}" for f in fams])
    ax.set_ylim(0, 1.38)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_ylabel("useful answers (share of attempts)")
    ax.set_title("Does the correction close the usefulness gap?", loc="left")
    ax.legend(loc="upper left", ncol=3, fontsize=8)  # inside, above the 100% line, clear of the title

    ax = axes[0][1]
    names, vals = [], []
    for f in fams:
        g = gap[f]["sampled"]
        names += [f"{f} · turn 1 only", f"{f} · with correction"]
        vals += [g["tpua_ratio_standard_turn1_over_abliterated"], g["tpua_ratio_standard_conversation_over_abliterated"]]
    ys = list(range(len(names)))[::-1]
    ax.barh([y for y, v in zip(ys, vals) if v is not None], [v for v in vals if v is not None],
            color=[COL["standard"] if "turn 1" in n else "#8fb6e8" for n, v in zip(names, vals) if v is not None],
            height=0.6, edgecolor=SURFACE)
    for y, v in zip(ys, vals):
        ax.text((v or 0) + 0.03, y, fmt(v, 2) if v is not None else "n/a", va="center", fontsize=8, color=INK2)
    ax.axvline(1.0, color=INK, linewidth=1.2, linestyle="--")
    ax.set_yticks(ys, names, fontsize=8)
    ax.set_xlabel("standard / abliterated (1.0 = same cost; >1 = standard costs more)")
    ax.set_title("Tokens per useful answer: standard vs abliterated", loc="left")
    stamp(fig, d, "Correction: abliterated gets 1 turn, standard gets up to 2 (sampled runs, original wording)")
    finish(plt, fig, out)
    return True


def progress(d: dict) -> list[dict]:
    cfg = d["cfg"]["generation"]
    per_model = 10 * 2 * (cfg["n_sampled"] + 1)
    rows = []
    for m in d["models"]:
        g = sum(1 for r in d["gens"].values() if r["model"] == m["name"])
        j = sum(1 for k, r in d["judg"].items() if r["model"] == m["name"] and not r.get("judge_error"))
        c = sum(1 for r in d["cap"].values() if r["model"] == m["name"])
        rows.append({"model": m["name"], "generate": g, "generate_expected": per_model, "judge": j,
                     "judge_expected": per_model, "capability": c, "capability_expected": d["n_cap_items"] or 500})
    return rows


def fig_progress(plt, d, prog, out: Path):
    fig, ax = plt.subplots(figsize=(11, 0.55 * len(prog) * 1.2 + 1.6))
    stages = (("generate", "#2a78d6"), ("capability", "#1baf7a"), ("judge", "#6250d6"))
    y0 = 0
    yt, yl = [], []
    for p in prog[::-1]:
        for k, (st, c) in enumerate(stages):
            y = y0 + k * 0.28
            frac = p[st] / p[f"{st}_expected"] if p[f"{st}_expected"] else 0
            ax.barh(y, 1, color=GRID, height=0.24)
            ax.barh(y, frac, color=c, height=0.24, label=st if y0 == 0 else None)
            ax.text(1.01, y, f"{st} {p[st]}/{p[f'{st}_expected']}", va="center", fontsize=7.5, color=INK2)
        yt.append(y0 + 0.28)
        yl.append(p["model"])
        y0 += 1.1
    ax.set_yticks(yt, yl)
    ax.set_xlim(0, 1.25)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    ax.legend(loc="lower right", fontsize=8, ncol=3, bbox_to_anchor=(1.0, 1.0))
    ax.grid(axis="y", visible=False)
    stamp(fig, d, f"Run progress (updated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)")
    finish(plt, fig, out)


# ---------------------------------------------------------------------------
# Dashboard (one self-contained HTML file)
# ---------------------------------------------------------------------------

def dashboard(d: dict, rows: list[dict], figs: list[tuple[str, str]], prog: list[dict], results: Path):
    def img(name: str) -> str:
        data = base64.b64encode((results / "figures" / name).read_bytes()).decode("ascii")
        return f'<img alt="{html.escape(name)}" src="data:image/png;base64,{data}">'

    prompts = {p["id"]: p for p in json.loads((ROOT / "pilot_prompts.json").read_text(encoding="utf-8"))["prompts"]}
    payload = {
        "rows": rows,
        "models": [{k: m[k] for k in ("name", "family", "variant", "repo")} for m in d["models"]],
        "prompts": {k: {"original": v["prompt"], "twin": v["neutral_twin"]} for k, v in prompts.items()},
        "mock": d["mock"],
    }
    prog_rows = "".join(
        f"<tr><td>{html.escape(p['model'])}</td><td>{p['generate']}/{p['generate_expected']}</td>"
        f"<td>{p['capability']}/{p['capability_expected']}</td><td>{p['judge']}/{p['judge_expected']}</td></tr>"
        for p in prog)
    banner = ('<div class="banner">MOCK DATA: synthetic numbers from <code>--mock</code>. Not results.</div>'
              if d["mock"] else "")
    if d["mixed"]:
        banner += '<div class="banner">WARNING: mock and real rows are mixed in this folder. Do not use these numbers.</div>'
    fig_html = "".join(f"<section><h2>{html.escape(t)}</h2>{img(n)}</section>" for n, t in figs)
    page = DASHBOARD_TEMPLATE.replace("__BANNER__", banner).replace("__PROGRESS__", prog_rows) \
        .replace("__FIGURES__", fig_html).replace("__PAYLOAD__", json.dumps(payload).replace("</", "<\\/")) \
        .replace("__UPDATED__", f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    (results / "dashboard.html").write_text(page, encoding="utf-8")


DASHBOARD_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Token Cost Dashboard</title>
<style>
:root{--surface:#fcfcfb;--surface2:#f3f2ee;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;--std:#2a78d6;--abl:#eb6834;--warn:#b3261e}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--surface:#1a1a19;--surface2:#242422;--ink:#f0efec;--ink2:#c3c2b7;--grid:#3a3936;--std:#3987e5;--abl:#d95926;--warn:#ff8a80}}
:root[data-theme="dark"]{--surface:#1a1a19;--surface2:#242422;--ink:#f0efec;--ink2:#c3c2b7;--grid:#3a3936;--std:#3987e5;--abl:#d95926;--warn:#ff8a80}
*{box-sizing:border-box}body{margin:0;background:var(--surface);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{margin:0 0 4px;font-size:26px}h2{font-size:18px;margin:32px 0 10px}
.sub{color:var(--ink2);margin:0 0 16px}.banner{background:var(--warn);color:#fff;padding:10px 14px;border-radius:8px;font-weight:700;margin:10px 0}
section img{max-width:100%;height:auto;border:1px solid var(--grid);border-radius:8px;background:#fcfcfb}
.controls{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:8px 0 12px}
select,button{font:inherit;padding:6px 10px;border-radius:6px;border:1px solid var(--grid);background:var(--surface2);color:var(--ink)}
.legend{display:flex;gap:16px;color:var(--ink2);font-size:13px}.sw{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
#chart{width:100%;overflow-x:auto}svg text{fill:var(--ink2);font-size:11px}
#tip{position:fixed;pointer-events:none;background:var(--surface2);color:var(--ink);border:1px solid var(--grid);border-radius:8px;padding:8px 10px;font-size:13px;display:none;max-width:340px;box-shadow:0 4px 16px rgba(0,0,0,.15)}
.tablewrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{border-bottom:1px solid var(--grid);padding:6px 8px;text-align:right;white-space:nowrap}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}th{color:var(--ink2);font-weight:600}
code{background:var(--surface2);padding:1px 5px;border-radius:4px}
</style></head><body><main>
<h1>Token cost of safety alignment: Pilot 2</h1>
<p class="sub">Updated __UPDATED__. Development prompts only; descriptive, never main results. Every number below is read from the run's JSONL files.</p>
__BANNER__
<h2>Progress</h2>
<div class="tablewrap"><table><tr><th>Model</th><th>Generate</th><th>Capability</th><th>Judge</th></tr>__PROGRESS__</table></div>

<h2>Prompt by prompt: standard vs abliterated</h2>
<div class="controls">
  <label>Family <select id="fam"></select></label>
  <label>Wording <select id="wording"><option value="original">original</option><option value="twin">neutral twin</option></select></label>
  <label>Measure <select id="metric">
    <option value="mean_output_tokens">mean output tokens</option>
    <option value="mean_thinking_tokens_est">mean thinking tokens (est.)</option>
    <option value="full_refusal_rate">full refusal rate</option>
    <option value="useful_rate">useful rate</option>
    <option value="cap_hit_rate">cap hit rate</option>
    <option value="mean_tokens_conversation">tokens with correction (in+out, original only)</option>
    <option value="useful_rate_final">useful after correction (original only)</option>
    <option value="correction_rate">correction success rate (standard, original only)</option></select></label>
  <span class="legend"><span><span class="sw" style="background:var(--std)"></span><span id="lstd">standard</span></span><span><span class="sw" style="background:var(--abl)"></span><span id="labl">abliterated</span></span></span>
</div>
<div id="chart"></div>
<h2>Table view</h2>
<div class="tablewrap" id="table"></div>
__FIGURES__
</main><div id="tip"></div>
<script>
const D = __PAYLOAD__;
const $ = s => document.querySelector(s);
const fams = [...new Set(D.models.map(m => m.family))];
fams.forEach(f => { const o = document.createElement('option'); o.value = o.textContent = f; $('#fam').appendChild(o); });
const P = Array.from({length:10}, (_, i) => 'P' + String(i + 1).padStart(2, '0'));
const isRate = m => m.endsWith('_rate');
const show = (v, m) => v == null ? 'not run yet' : isRate(m) ? Math.round(v * 100) + '%' : v.toFixed(1);
function cell(model, pid, w) { return D.rows.find(r => r.model === model && r.prompt_id === pid && r.wording === w); }
function render() {
  const fam = $('#fam').value, w = $('#wording').value, m = $('#metric').value;
  const std = D.models.find(x => x.family === fam && x.variant === 'standard');
  const abl = D.models.find(x => x.family === fam && x.variant === 'abliterated');
  $('#lstd').textContent = 'standard: ' + (std ? std.repo : 'missing');
  $('#labl').textContent = 'abliterated: ' + (abl ? abl.repo : 'missing');
  const vals = P.map(p => [std ? cell(std.name, p, w) : null, abl ? cell(abl.name, p, w) : null]);
  const all = vals.flat().map(c => c && c[m]).filter(v => v != null);
  const max = isRate(m) ? 1 : Math.max(1, ...all) * 1.1;
  const W = 1100, H = 320, L = 52, B = 34, T = 12, gw = (W - L - 10) / P.length, bw = gw * 0.36;
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${m} per prompt, ${fam}, ${w} wording">`;
  for (let i = 0; i <= 4; i++) { const y = T + (H - B - T) * (1 - i / 4), v = max * i / 4;
    s += `<line x1="${L}" x2="${W - 10}" y1="${y}" y2="${y}" stroke="var(--grid)"/><text x="${L - 6}" y="${y + 4}" text-anchor="end">${isRate(m) ? Math.round(v * 100) + '%' : Math.round(v)}</text>`; }
  P.forEach((p, i) => {
    [0, 1].forEach(k => {
      const c = vals[i][k], v = c && c[m];
      const x = L + i * gw + gw / 2 + (k - 1) * bw + (k ? 2 : -2) + (k ? 0 : 0);
      if (v == null) { s += `<text x="${x + bw / 2}" y="${H - B - 4}" text-anchor="middle">–</text>`; return; }
      const h = (H - B - T) * v / max, y = H - B - h;
      const corr = (c.n_corrected != null && !k) ? `<br>corrections: ${c.n_fixed_by_correction} worked of ${c.n_corrected} sent (${c.n_refused_turn1} refused on turn 1)` : '';
      const tip = `${p} · ${w}<br><b>${k ? 'abliterated' : 'standard'}</b>: ${show(v, m)}<br>n = ${c.n} answers, ${c.n_judged} judged${corr}<br><i>${(D.prompts[p] || {})[w] || ''}</i>`;
      s += `<rect x="${x}" y="${y}" width="${bw}" height="${Math.max(h, 0.5)}" rx="4" fill="var(${k ? '--abl' : '--std'})" data-tip="${tip.replace(/"/g, '&quot;')}"/>`;
      s += `<rect x="${x - 3}" y="${T}" width="${bw + 6}" height="${H - B - T}" fill="transparent" data-tip="${tip.replace(/"/g, '&quot;')}"/>`;
    });
    s += `<text x="${L + i * gw + gw / 2}" y="${H - B + 18}" text-anchor="middle">${p}</text>`;
  });
  $('#chart').innerHTML = s + '</svg>';
  let t = '<table><tr><th>Prompt</th><th>Wording</th><th>Std tokens</th><th>Abl tokens</th><th>Std thinking</th><th>Abl thinking</th><th>Std refusal</th><th>Abl refusal</th><th>Std useful</th><th>Std useful after corr.</th><th>Abl useful</th><th>Corrections worked</th><th>n</th></tr>';
  P.forEach((p, i) => { const [a, b] = vals[i]; const g = (c, k) => c ? show(c[k], k) : '–';
    t += `<tr><td>${p}</td><td>${w}</td><td>${g(a,'mean_output_tokens')}</td><td>${g(b,'mean_output_tokens')}</td><td>${g(a,'mean_thinking_tokens_est')}</td><td>${g(b,'mean_thinking_tokens_est')}</td><td>${g(a,'full_refusal_rate')}</td><td>${g(b,'full_refusal_rate')}</td><td>${g(a,'useful_rate')}</td><td>${a && a.useful_rate_final != null ? show(a.useful_rate_final, 'useful_rate_final') : '–'}</td><td>${g(b,'useful_rate')}</td><td>${a && a.n_corrected ? a.n_fixed_by_correction + '/' + a.n_corrected : '–'}</td><td>${a ? a.n : 0}/${b ? b.n : 0}</td></tr>`; });
  $('#table').innerHTML = t + '</table>';
}
document.addEventListener('mousemove', e => { const el = e.target && e.target.closest ? e.target.closest('[data-tip]') : null, tip = $('#tip');
  if (!el) { tip.style.display = 'none'; return; }
  tip.innerHTML = el.dataset.tip; tip.style.display = 'block';
  tip.style.left = Math.min(e.clientX + 14, innerWidth - 360) + 'px'; tip.style.top = (e.clientY + 14) + 'px'; });
['#fam', '#wording', '#metric'].forEach(s => $(s).addEventListener('change', render));
render();
</script></body></html>
"""


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", default=str(ROOT / "pilot" / "results"))
    ap.add_argument("--config", default=str(ROOT / "pilot" / "config.json"))
    args = ap.parse_args()
    results = Path(args.results).resolve()
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    d = load(results, cfg)
    if not d["gens"]:
        print(f"no generations in {results} yet; nothing to draw", file=sys.stderr)
        return 1
    (results / "figures").mkdir(parents=True, exist_ok=True)
    plt = setup_mpl()
    rows = per_prompt_rows(d)
    idx = {(r["model"], r["prompt_id"], r["wording"]): r for r in rows}
    write_tables(d, rows, results)
    prog = progress(d)
    F = results / "figures"
    figs = [("progress.png", "Run progress")]
    fig_progress(plt, d, prog, F / "progress.png")
    fig_per_prompt_tokens(plt, d, idx, F / "per_prompt_tokens.png")
    figs.append(("per_prompt_tokens.png", "Output tokens per prompt"))
    fig_refusal_heatmap(plt, d, idx, F / "refusal_heatmap.png")
    figs.append(("refusal_heatmap.png", "Refusal heatmap"))
    fig_thinking_split(plt, d, F / "thinking_split.png")
    figs.append(("thinking_split.png", "Answer vs thinking tokens"))
    fig_token_distribution(plt, d, F / "token_distribution.png")
    figs.append(("token_distribution.png", "Token spread"))
    if fig_family_ratios(plt, d, F / "family_ratios.png"):
        figs.append(("family_ratios.png", "Within-family ratios"))
    if d["corr"] and fig_correction_gap(plt, d, F / "correction_gap.png"):
        figs.insert(3, ("correction_gap.png", "Correction: gap and cost"))
        fig_correction_per_prompt(plt, d, idx, F / "correction_per_prompt.png")
        figs.insert(4, ("correction_per_prompt.png", "Correction cost per prompt"))
    if d["cap"]:
        fig_capability(plt, d, F / "capability.png")
        figs.append(("capability.png", "Capability check"))
    dashboard(d, rows, figs, prog, results)
    print(f"wrote {len(figs)} figures to {F}, per_prompt.csv/.md and dashboard.html in {results}"
          + (" (MOCK DATA)" if d["mock"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
