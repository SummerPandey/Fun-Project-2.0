# Verification report

Checked 2026-11-07T05:17:13+00:00. **0 FAIL, 1 WARN.** MOCK DATA.

| Level | Area | Evidence |
|---|---|---|
| PASS | files | generations.jsonl: 720 rows, all valid JSON |
| PASS | files | judgments.jsonl: 720 rows, all valid JSON |
| PASS | files | capability.jsonl: 120 rows, all valid JSON |
| PASS | files | all rows are MOCK (synthetic) |
| PASS | progress | qwen3.5-27b-standard: generate 120/120, judge 120/120, capability 20/20 |
| PASS | progress | qwen3.5-27b-abliterated: generate 120/120, judge 120/120, capability 20/20 |
| PASS | progress | llama3.1-8b-standard: generate 120/120, judge 120/120, capability 20/20 |
| PASS | progress | llama3.1-8b-abliterated: generate 120/120, judge 120/120, capability 20/20 |
| PASS | progress | gemma4-12b-standard: generate 120/120, judge 120/120, capability 20/20 |
| PASS | progress | gemma4-12b-abliterated: generate 120/120, judge 120/120, capability 20/20 |
| PASS | provenance | all 720 answers match the prompt texts in pilot_prompts.json |
| PASS | settings | every answer's seed and temperature match its run (s1-s5 sampled, greedy) |
| PASS | tokens | all 720 answers: cap flags consistent, counts in range |
| PASS | judge | 720 judgments: 'useful' follows its rule in every one |
| WARN | judge | 12 times the judge's own 'useful' disagreed with the rule (rule value is used) |
| PASS | summary | 24 summary numbers (mean output tokens, TPUA) recomputed from JSONL: all match |
| PASS | summary | summary.json generated_at 2026-11-07T05:17:09+00:00 |
| PASS | per_prompt | per_prompt.csv: 120/120 cells match the JSONL |
| PASS | capability | 120/120 capability rows re-score to the stored result |
