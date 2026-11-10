"""Supplementary analyses on analysis/<phase>/runs_scored.csv (written after the main analysis):
(1) exact-only token sensitivity (pre-specified in PROTOCOL.md); (2) non-truncated runs (exploratory,
selects on behavior); (3) judge quality on judge-scored categories."""
import sys, csv, numpy as np, pandas as pd, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from analysis import paired
phase = sys.argv[1] if len(sys.argv) > 1 else "main"
d = pathlib.Path(__file__).resolve().parents[1] / "analysis" / phase
df = pd.read_csv(d / "runs_scored.csv")
for c in ["unsupported_assumptions", "judge_correctness", "judge_completeness"]:
    df[c] = pd.to_numeric(df[c].map({True: 1, False: 0, "True": 1, "False": 0}).fillna(df[c]), errors="coerce").astype(float)
rows = []
def add(name, sub, metrics):
    for pid, s in sub.groupby("pair_id"):
        for m in metrics:
            if s[m].notna().sum() == 0: continue
            r = paired(s, m, 10000, np.random.default_rng(20261108))
            if r: rows.append({"pair_id": pid, "analysis": name, "metric": m, **r})
tok = ["reasoning_tokens", "answer_tokens", "reasoning_share"]
add("exact_only_SENSITIVITY", df[df.token_confidence == "exact"], tok)
add("non_truncated_EXPLORATORY", df[df.is_truncated == 0], tok + ["correctness_score"])
jq = df[df.category.isin(["everyday", "underspecified"]) & df.judge_correctness.notna()]
add("judge_scored_answered_PROVISIONAL", jq, ["judge_correctness", "judge_completeness", "unsupported_assumptions"])
for c in ["everyday", "underspecified"]:
    add(f"judge_{c}_PROVISIONAL", jq[jq.category == c], ["judge_correctness", "judge_completeness"])
pd.DataFrame(rows).to_csv(d / "supplementary.csv", index=False)
print("wrote", d / "supplementary.csv", len(rows))
