# Health-20 + Math-15 runs: instructions for the lead agent on the model machine

You are the lead agent for the **Health-20 run** of the token-cost study, on the machine that hosts
Ollama (`127.0.0.1:11434`, repo at `/home/sandb/Fun-Project-2.0`). Read `CLAUDE.md` first. Its
golden rules apply here without exception. This file only adds what is new.

## Goal

Run all **20 health questions**, each in two wordings (scary + plain twin), through all **6 models**
(3 standard/abliterated pairs: qwen3.5-27b, llama3.1-8b, gemma4-12b), score every answer with the
judge, and keep one compact, good-looking results page on GitHub, updated every 30 minutes.
**When health is finished, run Phase 2 (math, section 6) the same way.**

## 1. Set up (stop and tell me if any step fails)

1. `git pull`. Confirm `pilot3_design/medical_set2.json` (H06-H20) and `pilot3_design/math_set.json` (M01-M15) exist. If either is missing, stop.
2. `python3 tools/preflight.py` must print READY.
3. Build the 20 questions = `pilot3_design/screen1/prompts.json` P01-P05 + `medical_set2.json`
   H06-H20. The runner only accepts ids P01-P10, so split them into two batches:
   - `pilot3_design/health20/batchA/prompts.json`: P01-P05, H06-H10
   - `pilot3_design/health20/batchB/prompts.json`: H11-H20

   Renumber each batch P01-P10. Keep the original id in a `screen_id` field. Copy `block_list` and
   `block_message` from `screen1/prompts.json`. Copy the text of every prompt, twin and checklist
   **verbatim**, and write a check that compares each one to its source file.
4. Config: copy `pilot/config.json` (all 6 models, pinned digests, same sampling settings, same
   judge) to `pilot3_screening/health20/batchA/config.json` and `.../batchB/config.json`. Change
   **only** `prompts_file` (absolute path). Both batches must use identical settings.
5. Smoke test: `--limit 2` on one thinking and one non-thinking model, into `/tmp/h20smoke`.
   Report the time per answer and the estimated total **before** launching.

## 2. Run (background, resumable)

For each batch, out to `pilot3_screening/health20/<batch>/results`, in this order:
`generate` (each model in its own process) → `judge` → `correct` → `judge` → `analyze` → `sample`.
**Skip `capability`.** It was already measured in Pilot 2 with the same weights.
Scale: 10 questions × 2 wordings × 6 runs (5 sampled + 1 greedy) × 6 models = 720 answers per
batch, 1,440 in total.

Launch with `nohup`, write the PID to `logs/health20.pid` and log to `logs/health20.log`. On
transient errors (Ollama restart, timeout), relaunch the same command, since it resumes.

## 3. The results page: `pilot3_screening/health20/health.md`

Generate it with a script (`tools/health20_report.py`) that reads both batches'
`summary.json` and JSONL files. **Never type a number by hand.** It renders well on GitHub and fits
on about two screens:

1. **Header line:** status (RUNNING n/1,440 | FINISHED), last updated (UTC), verify FAIL/WARN.
2. **Headline (3-4 lines):** per family, abliterated/standard ratio of mean output tokens and of
   tokens per useful answer (TPUA), original wording, plus the refusal rate on each wording.
3. **One table, 20 rows, one per question, sorted by id:**
   `id | question (≤8 words) | tier | refusals std→abl (scary) | refusals std→abl (plain) |
   useful std→abl | mean out tokens std→abl | fixed by follow-up`
   Use the per-family values or the mean over the 3 families. Say which in the column header.
4. **Split by tier:** justified (6) vs over-refusal (14), same headline numbers.
5. **Caveats (3 bullets):** development prompts, descriptive only; raw tokens compared within a
   family only; the judge over-labels refusals (especially Llama), so refusal counts are maximums.

Keep the style compact: short headers, aligned tables, ✓/✗ only where they add meaning, no walls
of text. Also write `pilot3_screening/health20/STATUS.json`:
`{"updated_utc", "state": "running|finished|error", "answers_done", "answers_total": 1440,
"judged", "stage", "verify_fail", "verify_warn", "last_error"}`. This is what I check remotely.

## 4. Push to GitHub every 30 minutes

Use cron (or a `while sleep` loop under nohup) at **:00 and :30 of every hour (UTC)**:
`analyze` both batches → `tools/health20_report.py` → `tools/verify_results.py` → commit
`pilot3_screening/health20/`, `pilot3_design/health20/` and `logs/health20.log` with message
`health20: <n>/1440 answers, <stage>` → `git push`. Never force-push. Never commit anything else.
Also push once right after launch and once when the run finishes (message `health20: final`).
If a push fails, retry 3 times, then set `"last_error"` in STATUS.json and keep the run going.

## 5. Check-ins

Every 20 minutes while running, follow CLAUDE.md §5 (run-operator, verifier, archivist in
parallel; answer-auditor once per model after judging; claim-checker before any message with
numbers). When the run finishes, complete CLAUDE.md §6, then post a final summary with every
number checked twice.

## 6. Phase 2: Math-15 (start only after health is FINISHED and pushed as `health20: final`)

Same models, settings, judge, stages, push schedule and rules as health. Only these change:

- **Questions:** `pilot3_design/math_set.json` (M01-M15). Here `prompt` is the game-framed wording
  and `neutral_twin` is the same problem as plain math, so the wording contrast measures whether
  framing changes tokens or accuracy. No refusals are expected. Each question has an `answer_key`,
  and the first checklist R item is the final answer.
- **Batches:** `pilot3_design/math15/batchA/prompts.json` = M01-M10 and `.../batchB/prompts.json` = M11-M15
  (renumbered P01-P10 and P01-P05, with the original id in `screen_id`). The runner currently
  rejects anything other than exactly P01-P10. Make the **one** minimal change in
  `pilot/run_pilot.py` `load_prompts` to accept P01..Pn for 1 ≤ n ≤ 10 (and the same change in
  `tools/verify_results.py` if it hard-codes 10). Run the mock tests, then commit it alone as
  `runner: allow fewer than 10 prompts`. Change nothing else in the code.
- **Output:** `pilot3_screening/math15/<batch>/results`. Scale: 15 × 2 wordings × 6 runs × 6
  models = 1,080 answers.
- **Results page:** `pilot3_screening/math15/math.md`, made by `tools/math15_report.py`, in the
  same compact style as health.md. Header line. Headline per family: **accuracy (final answer
  matches the key)** std vs abl, mean output tokens std→abl, and **tokens per correct answer**.
  One 15-row table: `id | question (≤8 words) | accuracy std→abl (game) | accuracy std→abl
  (plain) | mean out tokens std→abl | refusals`. Caveats: development prompts; tokens compared
  within a family only; accuracy comes from the judge comparing against the key (M15 is very hard
  by hand, so expect low accuracy there).
- **Status:** `pilot3_screening/math15/STATUS.json`, same fields, `answers_total: 1080`.
- **Pushes:** same 30-minute slots, commit message `math15: <n>/1080 answers, <stage>`, final push `math15: final`.

## Never

Edit results by hand · change a config mid-run · mix mock and real data · update a pinned digest
yourself · open `handcheck_key.csv`. When unsure, stop and ask.
