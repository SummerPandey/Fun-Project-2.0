# Verification report

Checked 2026-11-07T08:17:46+00:00. **2 FAIL, 7 WARN.**

| Level | Area | Evidence |
|---|---|---|
| PASS | files | generations.jsonl: 273 rows, all valid JSON |
| WARN | files | judgments.jsonl does not exist yet |
| PASS | files | capability.jsonl: 1000 rows, all valid JSON |
| PASS | files | all rows are real |
| WARN | progress | qwen3.5-27b-standard: generate 120/120, judge 0/120, capability 500/500 |
| WARN | progress | qwen3.5-27b-abliterated: generate 120/120, judge 0/120, capability 500/500 |
| WARN | progress | llama3.1-8b-standard: generate 33/120, judge 0/120, capability 0/500 |
| WARN | progress | llama3.1-8b-abliterated: generate 0/120, judge 0/120, capability 0/500 |
| WARN | progress | gemma4-12b-standard: generate 0/120, judge 0/120, capability 0/500 |
| WARN | progress | gemma4-12b-abliterated: generate 0/120, judge 0/120, capability 0/500 |
| PASS | provenance | all 273 answers match the prompt texts in pilot_prompts.json |
| PASS | digests | qwen3.5-27b-standard: one set of weights, 64ae5b1d651f (matches pin) |
| PASS | digests | qwen3.5-27b-abliterated: one set of weights, 2c5b727e8ad6 (matches pin) |
| PASS | digests | llama3.1-8b-standard: one set of weights, 46e0c10c039e (matches pin) |
| PASS | settings | every answer's seed and temperature match its run (s1-s5 sampled, greedy) |
| PASS | settings | qwen: both models used identical options and think flag {"options": {"frequency_penalty": 0.0, "min_p": 0.0, "num_ctx": 16384, "num_predict": 4096, "presence_penalty": 0.0, "repeat_penalty": 1.0, "top_k": 0, "top_p": 1.0}, "think": true} |
| PASS | settings | llama: both models used identical options and think flag {"options": {"frequency_penalty": 0.0, "min_p": 0.0, "num_ctx": 16384, "num_predict": 4096, "presence_penalty": 0.0, "repeat_penalty": 1.0, "top_k": 0, "top_p": 1.0}, "think": null} |
| PASS | tokens | all 273 answers: cap flags consistent, counts in range |
| FAIL | summary | llama3.1-8b-standard original: mean output tokens recomputed 441.412 vs summary 448.125 |
| PASS | summary | summary.json generated_at 2026-11-07T08:17:44+00:00 |
| FAIL | per_prompt | per_prompt.csv: 119/120 cells match the JSONL (re-run tools/visualize.py if the run moved on since) |
| PASS | capability | 1000/1000 capability rows re-score to the stored result |
