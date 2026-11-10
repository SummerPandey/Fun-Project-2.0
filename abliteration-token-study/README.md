# Do Abliterated Models Think Longer? Reasoning Tokens and Answer Quality in Three Original-vs-Abliterated Model Pairs

*Abliteration token study: a paired comparison of three original vs abliterated local models (Llama 3.1 8B, Gemma 4 12B, Qwen 3.5 27B) on 50 benign tasks, 2,700 runs.*

> **Status: complete.** All 2,700 main runs are done and judged. Read [`report/REPORT.md`](report/REPORT.md). To unpack the raw streams, see [`SNAPSHOT.md`](SNAPSHOT.md).

This is a separate study from the token-cost pilots in the rest of this repository, and the repo-level `CLAUDE.md` playbook doesn't apply to it.

A controlled comparison of three installed Ollama model pairs: reasoning tokens, answer tokens, quality and clarification behavior.

## Layout

| Path | Contents |
|---|---|
| `audit/AUDIT.md` | Environment and model-pair audit, provenance, pair classification. `show_*.json` = raw metadata. |
| `protocol/PROTOCOL.md` | Frozen protocol: hypotheses, outcomes, settings, exclusions, analysis plan. |
| `benchmark/` | Task sources (`tasks_*.py`), builder, frozen `benchmark_v1.json` and `.sha256`. |
| `code/config.py` | Workers A–F, per-pair options, expected digests, Llama raw rendering. |
| `code/runner.py` | Schedule, run (checkpoint/resume) and render-prompt commands. |
| `code/tokens.py`, `code/bpe_local.py` | Native token accounting and verified multi-byte gap reconstruction. |
| `code/validate_measurement.py` | Measurement-validation checks (phase `validation`). |
| `code/scoring.py` | Deterministic scoring and sandboxed code tests. |
| `code/judge.py` | Blinded secondary judge (mistral-small3.1:24b) and human-review sample. |
| `code/analysis.py` | Merge, paired cluster bootstrap, tables, charts. |
| `code/sensitivity.py` | Exact-only sensitivity, non-truncated subset and judge-quality tables (`analysis/<phase>/supplementary.csv`). |
| `raw/<phase>/` | Immutable raw streamed responses, one file per attempt (read-only). In the GitHub copy these are compressed in `raw_archives/`; see `SNAPSHOT.md` to unpack. |
| `results/<phase>/` | `schedule.json`, `attempts.jsonl` (one record per attempt), `load_log.jsonl`, judgments. |
| `analysis/<phase>/` | Scored run table, paired differences, rates, missingness, fan table, charts. |
| `report/REPORT.md` | Final report. |

Phases are kept separate: `validation` (measurement checks), `pilot` (60 runs) and `main` (2,700 runs).

## Reproduce

Requirements: Ollama 0.40.0 on `127.0.0.1:11434` with the six tags and digests in `code/config.py`, plus `mistral-small3.1:24b` for judging; Python ≥ 3.12 with numpy, pandas and matplotlib.

```bash
cd ~/safety-pair-study   # path on the experiment machine; abliteration-token-study/ in this repo
python3 benchmark/build_benchmark.py        # must print sha256 00eb9b21…; compare benchmark/benchmark_v1.sha256
python3 code/validate_measurement.py        # optional: measurement checks
python3 code/runner.py schedule main        # 50 tasks x 3 variants x 3 reps x 6 models
python3 code/runner.py render main          # rendered prompts per model
python3 code/runner.py run main             # long; resumable
python3 code/judge.py main                  # blinded judging; resumable
python3 code/judge.py main --sample-human 60
python3 code/analysis.py main
```

## Resume

`runner.py run <phase>` and `judge.py <phase>` are both idempotent. Rerun the same command after an interruption:

- Runs with a completed (non-transport-error) attempt are skipped.
- Transport failures are retried as new attempts `a2`, `a3`. Earlier attempts and their records are kept.
- Raw files are opened exclusively (`x` mode) and set read-only, so a completed measurement is never overwritten.
- The runner refuses to start if the benchmark checksum differs from the schedule's, or if any model tag resolves to an unexpected digest.

To run in the background and survive logout:

```bash
nohup python3 code/runner.py run main >> results/main/run_stdout.log 2>&1 &
```

Keep other Ollama clients (Open WebUI) idle during timed runs. `gpu_before`/`gpu_after` snapshots are stored per run to flag contention.
