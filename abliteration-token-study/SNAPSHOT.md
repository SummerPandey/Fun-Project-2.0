# Snapshot status: main study COMPLETE

This folder (`abliteration-token-study/`, originally `safety-pair-study/`) is a copy of `~/safety-pair-study/` on the experiment machine, taken on 2026-11-10 at about 10:50 CST after the study finished.

| Phase | State |
|---|---|
| Audit, protocol, benchmark, code | Complete and frozen (`protocol/freeze_hashes.txt`). `code/sensitivity.py` was added after the freeze to produce the pre-specified exact-only sensitivity check and supplementary tables. |
| Measurement validation | Complete (`results/validation/`). |
| Pilot (60 runs) | Complete (`results/pilot/PILOT_REPORT.md`, `analysis/pilot/`). Kept separate. |
| Main study | **2,700 of 2,700 runs**, 0 transport errors (`results/main/attempts.jsonl`). |
| Judge on main study | Complete: 2,561 graded, 139 with no visible answer skipped by design, 0 failures. Provisional. |
| Human-review sample | 60 blinded items in `results/main/human_review_sample.csv`, not yet filled in. The judge's grades for them are in `human_review_judge_key.jsonl`; don't open it before reviewing. |
| Final analysis and report | `analysis/main/`, `report/REPORT.md`. `analysis/main_interim/` is superseded. |

## Raw responses

Every attempt's raw streamed response is stored compressed in `raw_archives/`. Each archive is under 25 MB.

| Archive | Contents |
|---|---|
| `raw_validation.tar.xz` | Measurement-validation streams |
| `raw_pilot.tar.xz` | Pilot streams |
| `raw_smoke_fix.tar.xz` | Six-run check of the model-unloading fix |
| `raw_main_worker{A,B,C,E,F}.tar.xz` | Main-study streams, one archive per worker/model |
| `raw_main_workerD_part{1,2}.tar.xz` | Worker D (Gemma modified), split by task category (E/U/M, then K/I) |

Unpack them in place before running the analysis, since `raw_response_path` points to `raw/<phase>/…`:

```bash
cd abliteration-token-study
for f in raw_archives/*.tar.xz; do tar -xJf "$f"; done
python3 code/analysis.py main && python3 code/sensitivity.py main
```

The main archives together contain 2,700 files, one per attempt record.
