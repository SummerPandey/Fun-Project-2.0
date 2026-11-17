# Verification report

Checked 2026-11-17T18:30:50+00:00. **0 FAIL, 9 WARN.**

| Level | Area | Evidence |
|---|---|---|
| PASS | files | generations.jsonl: 356 rows, all valid JSON |
| WARN | files | judgments.jsonl does not exist yet |
| WARN | files | capability.jsonl does not exist yet |
| PASS | files | all rows are real |
| WARN | progress | qwen3.5-27b-standard: generate 60/60, judge 0/60, capability 0/? |
| WARN | progress | qwen3.5-27b-abliterated: generate 60/60, judge 0/60, capability 0/? |
| WARN | progress | llama3.1-8b-standard: generate 60/60, judge 0/60, capability 0/? |
| WARN | progress | llama3.1-8b-abliterated: generate 60/60, judge 0/60, capability 0/? |
| WARN | progress | gemma4-12b-standard: generate 60/60, judge 0/60, capability 0/? |
| WARN | progress | gemma4-12b-abliterated: generate 56/60, judge 0/60, capability 0/? |
| PASS | provenance | all 356 answers match the prompt texts in pilot_prompts.json |
| PASS | digests | qwen3.5-27b-standard: one set of weights, 64ae5b1d651f (matches pin) |
| PASS | digests | qwen3.5-27b-abliterated: one set of weights, 2c5b727e8ad6 (matches pin) |
| PASS | digests | llama3.1-8b-standard: one set of weights, 46e0c10c039e (matches pin) |
| PASS | digests | llama3.1-8b-abliterated: one set of weights, 5920dea9e0f0 (matches pin) |
| PASS | digests | gemma4-12b-standard: one set of weights, 6114515d63c1 (matches pin) |
| PASS | digests | gemma4-12b-abliterated: one set of weights, 526eca3f9757 (matches pin) |
| PASS | settings | every answer's seed and temperature match its run (s1-s5 sampled, greedy) |
| PASS | settings | qwen: both models used identical options and think flag {"options": {"frequency_penalty": 0.0, "min_p": 0.0, "num_ctx": 20480, "num_predict": 16384, "presence_penalty": 0.0, "repeat_penalty": 1.0, "top_k": 0, "top_p": 1.0}, "think": true} |
| PASS | settings | llama: both models used identical options and think flag {"options": {"frequency_penalty": 0.0, "min_p": 0.0, "num_ctx": 20480, "num_predict": 16384, "presence_penalty": 0.0, "repeat_penalty": 1.0, "top_k": 0, "top_p": 1.0}, "think": null} |
| PASS | settings | gemma: both models used identical options and think flag {"options": {"frequency_penalty": 0.0, "min_p": 0.0, "num_ctx": 20480, "num_predict": 16384, "presence_penalty": 0.0, "repeat_penalty": 1.0, "top_k": 0, "top_p": 1.0}, "think": true} |
| PASS | tokens | all 356 answers: cap flags consistent, counts in range |
| WARN | tokens | 112 answers ran out of tokens while still thinking (no visible answer); consider a larger max_tokens before the main study |
| PASS | summary | 12 summary numbers (mean output tokens, TPUA) recomputed from JSONL: all match |
| PASS | summary | summary.json generated_at 2026-11-17T18:30:50+00:00 |
