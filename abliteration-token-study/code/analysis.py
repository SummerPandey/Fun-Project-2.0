"""Merge attempts + deterministic scores + judge grades into one run table, then compute
paired modified-minus-original differences with a paired cluster bootstrap over base tasks.

  python3 code/analysis.py <phase> [--boot 10000]
Outputs in analysis/<phase>/: runs_scored.csv, paired_differences.csv, by_category.csv,
response_rates.csv, comparable_subset.csv, missingness.csv, fan_prompt.csv, charts/*.png
"""
import json, sys, pathlib, argparse, math
import numpy as np, pandas as pd
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from scoring import score as det_score

ORIG_C, MOD_C = "#2a78d6", "#eb6834"          # validated categorical slots 1-2 (dataviz reference palette)
INK, INK2, SURF, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df"
PAIR_LABEL = {"llama31": "Llama 3.1 8B", "gemma4": "Gemma 4 12B", "qwen35": "Qwen 3.5 27B"}


def load(phase):
    d = ROOT / "results" / phase
    P = {p["prompt_id"]: p for p in json.load(open(ROOT / "benchmark" / "benchmark_v1.json"))["prompts"]}
    att = [json.loads(l) for l in open(d / "attempts.jsonl") if l.strip()]
    all_att = pd.DataFrame(att)
    ok = [a for a in att if not a.get("transport_error")]
    # Re-derive token accounting from the immutable raw stream with the current (frozen) tokens.py,
    # so every phase uses identical accounting code regardless of runner version.
    from tokens import account
    fam = {"llama31": "llama", "gemma4": "gemma", "qwen35": "qwen"}
    for a in ok:
        ch = [json.loads(l) for l in open(ROOT / a["raw_response_path"]) if l.strip()]
        gen = a["api"] == "generate"
        th = "".join((c.get("message") or {}).get("thinking", "") for c in ch)
        ct = "".join((c.get("response", "") if gen else (c.get("message") or {}).get("content", "")) for c in ch)
        ent = [e for c in ch for e in (c.get("logprobs") or [])]
        acc = account(fam[a["pair_id"]], not gen, ent, ch[-1], th, ct)
        rt, at = acc["reasoning_tokens"], acc["answer_tokens"]
        a.update(reasoning_tokens=rt, answer_tokens=at, token_confidence=acc["confidence"],
                 token_count_method=acc["token_count_method"], reasoning_status=acc["reasoning_status"],
                 reasoning_share=(rt / (rt + at)) if (rt is not None and at is not None and rt + at > 0) else None)
    # final attempt per run: the (single) non-transport-error attempt
    J, M = {}, {}
    if (d / "judgments.jsonl").exists():
        for l in open(d / "judgments.jsonl"):
            if l.strip():
                j = json.loads(l); J[j["judge_item_id"]] = j
        for l in open(d / "judge_id_map.jsonl"):
            m = json.loads(l); M[(m["run_id"], m["attempt"])] = m["judge_item_id"]
    rows = []
    for a in ok:
        p = P[a["prompt_id"]]
        ds = det_score(p, a.get("answer_text") or "")
        j = J.get(M.get((a["run_id"], a["attempt"])), {})
        label = j.get("response_label")
        empty = not (a.get("answer_text") or "").strip()
        if a.get("error"):
            label = "error"
        elif a.get("truncated") and (empty or label in (None, "partial_answer", "error")):
            label = "truncated"
        elif empty:
            label = "error"
        has_det = ds["det_pass"] is not None and not ds.get("supplementary_only")
        if label == "truncated":
            corr = 0.0 if has_det or empty else (j["correctness"] / 2 if "correctness" in j else None)
        else:
            corr = float(ds["det_pass"]) if has_det else (j["correctness"] / 2 if "correctness" in j else None)
        comp = ds["det_fraction"] if has_det else (j["completeness"] / 2 if "completeness" in j else None)
        clarified = (label == "clarification") or bool(j.get("asked_useful_clarification"))
        rows.append({**{k: a.get(k) for k in [
            "run_id", "attempt", "pair_id", "worker_id", "condition", "model_tag", "model_digest", "task_id", "category",
            "variant_id", "repetition", "seed", "input_tokens", "reasoning_tokens", "answer_tokens", "total_generated_tokens",
            "reasoning_share", "reasoning_status", "token_count_method", "token_confidence", "truncated", "error",
            "latency_wall_s", "ttft_s", "load_time_s", "eval_s", "throughput_tok_s", "answer_words", "answer_chars",
            "raw_response_path"]},
            "clarification_warranted": p["clarification_warranted"],
            "det_pass": ds["det_pass"] if has_det else None, "det_fraction": ds["det_fraction"] if has_det else None,
            "format_ok": ds.get("format_ok"), "latency_valid": a.get("latency_valid"),
            "response_label": label, "judge_label": j.get("response_label"),
            "correctness_score": corr, "completeness_score": comp,
            "judge_correctness": j.get("correctness"), "judge_completeness": j.get("completeness"),
            "unsupported_assumptions": j.get("unsupported_assumptions"),
            "appropriate_uncertainty": j.get("appropriate_uncertainty"),
            "asked_useful_clarification": j.get("asked_useful_clarification"),
            "inappropriate_refusal": j.get("inappropriate_refusal"),
            "clarified": clarified, "refused": label == "refusal",
            "is_truncated": label == "truncated", "judge_missing": not j or "response_label" not in j})
    df = pd.DataFrame(rows)
    # token measurements usable only when exact or verified-estimated
    valid = df["token_confidence"].isin(["exact", "estimated"])
    for c in ["reasoning_tokens", "answer_tokens", "reasoning_share"]:
        df.loc[~valid, c] = np.nan
    df["reasoning_tokens"] = pd.to_numeric(df["reasoning_tokens"], errors="coerce")
    for c in ["clarified", "refused", "is_truncated"]:
        df[c] = df[c].astype(float)
    return df, all_att


METRICS = [("reasoning_tokens", "Reasoning tokens"), ("answer_tokens", "Answer tokens"),
           ("total_generated_tokens", "Total generated tokens"), ("reasoning_share", "Reasoning share"),
           ("correctness_score", "Correctness (0-1)"), ("completeness_score", "Completeness (0-1)"),
           ("clarified", "Clarification rate"), ("refused", "Refusal rate"), ("is_truncated", "Truncation rate"),
           ("latency_wall_s", "Wall latency (s)"), ("throughput_tok_s", "Throughput (tok/s)")]


def task_means(sub, metric):
    g = sub.groupby(["task_id", "condition"])[metric].mean().unstack("condition")
    return g.dropna(subset=[c for c in ["original", "modified"] if c in g.columns])


def paired(sub, metric, B, rng):
    g = task_means(sub, metric)
    if g.empty or "original" not in g or "modified" not in g:
        return None
    o, m = g["original"].to_numpy(), g["modified"].to_numpy()
    diff = m - o
    n = len(diff)
    idx = rng.integers(0, n, size=(B, n))
    bd = diff[idx].mean(axis=1)
    bo = o[idx].mean(axis=1); bm = m[idx].mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        bpct = np.where(bo != 0, (bm - bo) / bo * 100, np.nan)
    om = o.mean()
    pct = (m.mean() - om) / om * 100 if om != 0 else None
    return {"n_tasks": n, "n_runs_orig": int(sub.loc[sub.condition == "original", metric].notna().sum()),
            "n_runs_mod": int(sub.loc[sub.condition == "modified", metric].notna().sum()),
            "mean_orig": om, "mean_mod": m.mean(), "median_run_orig": sub.loc[sub.condition == "original", metric].median(),
            "median_run_mod": sub.loc[sub.condition == "modified", metric].median(),
            "mean_diff": diff.mean(), "ci95_lo": np.percentile(bd, 2.5), "ci95_hi": np.percentile(bd, 97.5),
            "median_task_diff": np.median(diff), "tasks_mod_higher": int((diff > 0).sum()), "tasks_mod_lower": int((diff < 0).sum()),
            "pct_change": pct, "pct_ci95_lo": None if pct is None else np.nanpercentile(bpct, 2.5),
            "pct_ci95_hi": None if pct is None else np.nanpercentile(bpct, 97.5)}


def analyze(phase, B):
    out = ROOT / "analysis" / phase; (out / "charts").mkdir(parents=True, exist_ok=True)
    df, all_att = load(phase)
    df.to_csv(out / "runs_scored.csv", index=False)
    rng = np.random.default_rng(20261108)
    res, cat_res, comp_res = [], [], []
    for pair in sorted(df.pair_id.unique()):
        sp = df[df.pair_id == pair]
        for mkey, mname in METRICS:
            if mkey in ("reasoning_tokens", "reasoning_share") and pair == "llama31":
                continue
            r = paired(sp, mkey, B, rng)
            if r:
                res.append({"pair_id": pair, "metric": mkey, "analysis": "all_valid_runs", **r})
            for cat in sorted(sp.category.unique()):
                r = paired(sp[sp.category == cat], mkey, B, rng)
                if r:
                    cat_res.append({"pair_id": pair, "category": cat, "metric": mkey, **r})
        # exploratory comparable-response subset: same (task, variant, repetition) cell, same label in both conditions
        cell = sp.pivot_table(index=["task_id", "variant_id", "repetition"], columns="condition",
                              values="response_label", aggfunc="first")
        if {"original", "modified"} <= set(cell.columns):
            same = cell[cell["original"] == cell["modified"]]
            for lab in sorted(same["original"].dropna().unique()):
                keys = set(same[same["original"] == lab].index)
                ss = sp[[k in keys for k in zip(sp.task_id, sp.variant_id, sp.repetition)]]
                for mkey in ["reasoning_tokens", "answer_tokens", "total_generated_tokens", "correctness_score"]:
                    if mkey == "reasoning_tokens" and pair == "llama31":
                        continue
                    r = paired(ss, mkey, B, rng)
                    if r:
                        comp_res.append({"pair_id": pair, "subset": f"both_{lab}", "metric": mkey, **r})
    pd.DataFrame(res).to_csv(out / "paired_differences.csv", index=False)
    pd.DataFrame(cat_res).to_csv(out / "by_category.csv", index=False)
    pd.DataFrame(comp_res).to_csv(out / "comparable_subset_EXPLORATORY.csv", index=False)
    # response rates and missingness
    rates = df.groupby(["pair_id", "condition", "category"]).agg(
        n=("run_id", "count"), clarification_rate=("clarified", "mean"), refusal_rate=("refused", "mean"),
        truncation_rate=("is_truncated", "mean"), correctness=("correctness_score", "mean"),
        unsupported_assumption_rate=("unsupported_assumptions", lambda s: pd.to_numeric(s, errors="coerce").mean())).reset_index()
    rates.to_csv(out / "response_rates.csv", index=False)
    labels = df.groupby(["pair_id", "condition", "response_label"]).size().unstack(fill_value=0)
    labels.to_csv(out / "response_labels.csv")
    miss = df.groupby(["pair_id", "condition"]).agg(
        runs=("run_id", "count"), token_exact=("token_confidence", lambda s: (s == "exact").sum()),
        token_estimated=("token_confidence", lambda s: (s == "estimated").sum()),
        token_unavailable=("token_confidence", lambda s: (s == "unavailable").sum()),
        truncated=("truncated", "sum"), judge_missing=("judge_missing", "sum")).reset_index()
    te = all_att[all_att.get("transport_error").notna()] if "transport_error" in all_att else all_att.iloc[0:0]
    miss["transport_error_attempts"] = miss.apply(lambda r: int(((te.pair_id == r.pair_id) & (te.condition == r.condition)).sum()) if len(te) else 0, axis=1)
    miss.to_csv(out / "missingness.csv", index=False)
    fan = df[df.task_id == "U01"][["model_tag", "condition", "variant_id", "repetition", "response_label", "reasoning_tokens",
                                   "answer_tokens", "total_generated_tokens", "token_count_method", "token_confidence",
                                   "asked_useful_clarification", "unsupported_assumptions", "completeness_score"]]
    fan.sort_values(["model_tag", "variant_id", "repetition"]).to_csv(out / "fan_prompt.csv", index=False)
    charts(df, out / "charts")
    print("analysis written to", out)
    return df


def _style(ax):
    ax.set_facecolor(SURF)
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)
    for s in ["left", "bottom"]:
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)
    ax.grid(axis="y", color=GRID, linewidth=0.6); ax.set_axisbelow(True)


def charts(df, cd):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 9, "text.color": INK, "axes.labelcolor": INK2, "figure.facecolor": SURF})
    # 1. paired reasoning-token differences per task (only valid measurements; Llama excluded)
    pairs = [p for p in ["gemma4", "qwen35"] if p in df.pair_id.unique()]
    if pairs:
        fig, axes = plt.subplots(1, len(pairs), figsize=(5.2 * len(pairs), 4.2), squeeze=False)
        for ax, p in zip(axes[0], pairs):
            g = task_means(df[df.pair_id == p], "reasoning_tokens")
            d = (g["modified"] - g["original"]).sort_values()
            ax.hlines(range(len(d)), 0, d.values, color=INK2, linewidth=1)
            ax.plot(d.values, range(len(d)), "o", color=MOD_C, markersize=5, markeredgecolor=SURF, markeredgewidth=1.5)
            ax.axvline(0, color=INK2, linewidth=0.8)
            ax.set_yticks(range(len(d))); ax.set_yticklabels(d.index, fontsize=6)
            ax.set_xlabel("Modified − original reasoning tokens (task mean)")
            ax.set_title(f"{PAIR_LABEL[p]}: paired reasoning-token difference", fontsize=9, loc="left"); _style(ax)
        fig.tight_layout(); fig.savefig(cd / "paired_reasoning_diff.png", dpi=150); plt.close(fig)
    # 2. answer-token distributions
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, p in zip(axes, ["llama31", "gemma4", "qwen35"]):
        s = df[df.pair_id == p]
        data = [s[s.condition == c]["answer_tokens"].dropna() for c in ["original", "modified"]]
        if all(len(x) for x in data):
            bp = ax.boxplot(data, tick_labels=["original", "modified"], widths=0.5, patch_artist=True, showfliers=True,
                            flierprops=dict(markersize=3, markeredgecolor=INK2), medianprops=dict(color=INK))
            for patch, c in zip(bp["boxes"], [ORIG_C, MOD_C]):
                patch.set_facecolor(c); patch.set_alpha(0.85); patch.set_edgecolor(SURF)
        ax.set_yscale("log"); ax.set_title(PAIR_LABEL[p], fontsize=9, loc="left"); ax.set_ylabel("Answer tokens (log)"); _style(ax)
    fig.suptitle("Visible-answer token distributions (native tokenizer; not comparable across families)", fontsize=9, x=0.01, ha="left")
    fig.tight_layout(); fig.savefig(cd / "answer_token_distributions.png", dpi=150); plt.close(fig)
    # 3. correctness vs total generated tokens
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.8))
    for ax, p in zip(axes, ["llama31", "gemma4", "qwen35"]):
        for c, col in [("original", ORIG_C), ("modified", MOD_C)]:
            s = df[(df.pair_id == p) & (df.condition == c)].dropna(subset=["correctness_score"])
            jit = np.random.default_rng(1).uniform(-0.04, 0.04, len(s))
            ax.scatter(s.total_generated_tokens, s.correctness_score + jit, s=10, color=col, alpha=0.6, label=c,
                       edgecolors=SURF, linewidths=0.5)
        ax.set_xscale("log"); ax.set_xlabel("Total generated tokens (log)"); ax.set_ylabel("Correctness")
        ax.set_title(PAIR_LABEL[p], fontsize=9, loc="left"); _style(ax); ax.legend(frameon=False, fontsize=7)
    fig.tight_layout(); fig.savefig(cd / "correctness_vs_tokens.png", dpi=150); plt.close(fig)
    # 4. clarification and refusal rates by category
    r = df.groupby(["pair_id", "condition", "category"])[["clarified", "refused"]].mean().reset_index()
    cats = sorted(df.category.unique())
    fig, axes = plt.subplots(2, 3, figsize=(12, 6), sharey=True)
    for row, metric in enumerate(["clarified", "refused"]):
        for ax, p in zip(axes[row], ["llama31", "gemma4", "qwen35"]):
            x = np.arange(len(cats)); wdt = 0.38
            for k, (c, col) in enumerate([("original", ORIG_C), ("modified", MOD_C)]):
                v = [r[(r.pair_id == p) & (r.condition == c) & (r.category == ct)][metric].mean() for ct in cats]
                ax.bar(x + (k - 0.5) * (wdt + 0.02), np.nan_to_num(v), wdt, color=col, label=c)
            ax.set_xticks(x); ax.set_xticklabels(cats, rotation=30, fontsize=7); ax.set_ylim(0, 1)
            ax.set_title(f"{PAIR_LABEL[p]}: {'clarification' if metric == 'clarified' else 'refusal'} rate", fontsize=9, loc="left")
            _style(ax)
            if row == 0 and p == "llama31":
                ax.legend(frameon=False, fontsize=7)
    fig.tight_layout(); fig.savefig(cd / "clarification_refusal_by_category.png", dpi=150); plt.close(fig)
    # 5. reasoning share (valid measurements only)
    if pairs:
        fig, ax = plt.subplots(figsize=(6, 3.8))
        pos = 0; ticks = []
        for p in pairs:
            for c, col in [("original", ORIG_C), ("modified", MOD_C)]:
                v = df[(df.pair_id == p) & (df.condition == c)]["reasoning_share"].dropna()
                if len(v):
                    bp = ax.boxplot([v], positions=[pos], widths=0.6, patch_artist=True, medianprops=dict(color=INK),
                                    flierprops=dict(markersize=3, markeredgecolor=INK2))
                    bp["boxes"][0].set_facecolor(col); bp["boxes"][0].set_edgecolor(SURF)
                ticks.append((pos, f"{PAIR_LABEL[p]}\n{c}")); pos += 1
            pos += 0.6
        ax.set_xticks([t[0] for t in ticks]); ax.set_xticklabels([t[1] for t in ticks], fontsize=7)
        ax.set_ylabel("Reasoning / (reasoning + answer)"); ax.set_ylim(0, 1)
        ax.set_title("Reasoning share (Llama has no separate reasoning stream; not plotted)", fontsize=9, loc="left"); _style(ax)
        fig.tight_layout(); fig.savefig(cd / "reasoning_share.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("phase"); ap.add_argument("--boot", type=int, default=10000)
    a = ap.parse_args(); analyze(a.phase, a.boot)
