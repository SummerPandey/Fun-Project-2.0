# Snapshot status: main study IN PROGRESS

This folder is a **snapshot** of `~/safety-pair-study/` on the experiment machine, taken on 2026-11-09 at about 10:30 CST while the main study was still running.

| Phase | State in this snapshot |
|---|---|
| Audit, protocol, benchmark, code | Complete and frozen (`protocol/freeze_hashes.txt`). |
| Measurement validation | Complete (`results/validation/`). |
| Pilot (60 runs) | Complete, judged and analyzed (`results/pilot/PILOT_REPORT.md`, `analysis/pilot/`). Kept separate from the main study. |
| Main study | **2,075 of 2,700 planned runs** recorded in `results/main/attempts.jsonl`. **Not finished.** |
| Judge on main study | **Not run yet.** |
| Final analysis and report | **Not produced yet.** `analysis/main_interim/` holds an interim, token-and-deterministic-only look; read its README first. |

There are no final results in this snapshot. A later commit will add the finished runs, the judgments, `analysis/main/` and `report/REPORT.md`.

## Raw responses

Every attempt's raw streamed response is stored compressed in `raw_archives/`. Each archive is under 25 MB, which keeps the repo within GitHub's file limits.

| Archive | Contents |
|---|---|
| `raw_validation.tar.xz` | Measurement-validation streams |
| `raw_pilot.tar.xz` | Pilot streams |
| `raw_smoke_fix.tar.xz` | Six-run check of the model-unloading fix |
| `raw_main_worker{A..F}.tar.xz` | Main-study streams, one archive per worker/model |

Unpack them in place before running the analysis, since `raw_response_path` in the records points to `raw/<phase>/…`:

```bash
cd safety-pair-study
for f in raw_archives/*.tar.xz; do tar -xJf "$f"; done
python3 code/analysis.py pilot
```

To check archive integrity, the archives together contain one file per attempt record (2,075 for `main` in this snapshot).
