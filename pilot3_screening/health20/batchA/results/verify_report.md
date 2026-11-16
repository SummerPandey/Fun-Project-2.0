# Verification report

Checked 2026-11-16T11:30:15+00:00. **2 FAIL, 2 WARN.**

| Level | Area | Evidence |
|---|---|---|
| PASS | files | generations.jsonl: 720 rows, all valid JSON |
| PASS | files | judgments.jsonl: 720 rows, all valid JSON |
| WARN | files | capability.jsonl does not exist yet |
| PASS | files | all rows are real |
| PASS | progress | qwen3.5-27b-standard: generate 120/120, judge 120/120, capability 0/? |
| PASS | progress | qwen3.5-27b-abliterated: generate 120/120, judge 120/120, capability 0/? |
| PASS | progress | llama3.1-8b-standard: generate 120/120, judge 120/120, capability 0/? |
| PASS | progress | llama3.1-8b-abliterated: generate 120/120, judge 120/120, capability 0/? |
| PASS | progress | gemma4-12b-standard: generate 120/120, judge 120/120, capability 0/? |
| PASS | progress | gemma4-12b-abliterated: generate 120/120, judge 120/120, capability 0/? |
| FAIL | provenance | 720 answers have a prompt_text that is not in pilot_prompts.json, e.g. ['qwen3.5-27b-standard/P01/original/s1', 'qwen3.5-27b-standard/P01/twin/s1', 'qwen3.5-27b-standard/P02/original/s1'] |
| PASS | digests | qwen3.5-27b-standard: one set of weights, 64ae5b1d651f (matches pin) |
| PASS | digests | qwen3.5-27b-abliterated: one set of weights, 2c5b727e8ad6 (matches pin) |
| PASS | digests | llama3.1-8b-standard: one set of weights, 46e0c10c039e (matches pin) |
| PASS | digests | llama3.1-8b-abliterated: one set of weights, 5920dea9e0f0 (matches pin) |
| PASS | digests | gemma4-12b-standard: one set of weights, 6114515d63c1 (matches pin) |
| PASS | digests | gemma4-12b-abliterated: one set of weights, 526eca3f9757 (matches pin) |
| PASS | settings | every answer's seed and temperature match its run (s1-s5 sampled, greedy) |
| PASS | settings | qwen: both models used identical options and think flag {"options": {"frequency_penalty": 0.0, "min_p": 0.0, "num_ctx": 16384, "num_predict": 4096, "presence_penalty": 0.0, "repeat_penalty": 1.0, "top_k": 0, "top_p": 1.0}, "think": true} |
| PASS | settings | llama: both models used identical options and think flag {"options": {"frequency_penalty": 0.0, "min_p": 0.0, "num_ctx": 16384, "num_predict": 4096, "presence_penalty": 0.0, "repeat_penalty": 1.0, "top_k": 0, "top_p": 1.0}, "think": null} |
| PASS | settings | gemma: both models used identical options and think flag {"options": {"frequency_penalty": 0.0, "min_p": 0.0, "num_ctx": 16384, "num_predict": 4096, "presence_penalty": 0.0, "repeat_penalty": 1.0, "top_k": 0, "top_p": 1.0}, "think": true} |
| PASS | tokens | all 720 answers: cap flags consistent, counts in range |
| WARN | tokens | 1 answers ran out of tokens while still thinking (no visible answer); consider a larger max_tokens before the main study |
| PASS | judge | 720 judgments: 'useful' follows its rule in every one |
| PASS | summary | 24 summary numbers (mean output tokens, TPUA) recomputed from JSONL: all match |
| PASS | summary | summary.json generated_at 2026-11-16T11:30:15+00:00 |
| PASS | correction | corrections.jsonl: 112 rows, all valid JSON |
| PASS | correction | correction_judgments.jsonl: 112 rows, all valid JSON |
| FAIL | correction | 112 correction turns: correction text differs from the configured template |
| PASS | correction | every refused standard answer (112) has its correction turn |
| PASS | correction | 24 correction numbers in summary.json (corrected, fixed, useful after correction, conversation TPUA) recomputed from JSONL: all match |
