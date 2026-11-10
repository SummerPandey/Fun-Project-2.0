# Final report: original vs modified checkpoints (main study, v1)

Date: 2026-11-10. Protocol: `protocol/PROTOCOL.md` (frozen 2026-11-09). Every number below is read from `analysis/main/*.csv` and `analysis/main/supplementary.csv`. Those files are produced by `code/analysis.py main` and `code/sensitivity.py main` from the immutable raw streams.

## What was run

- **2,700 of 2,700 planned runs** completed: 50 base tasks × 3 variants × 3 repetitions × 6 models. There were 0 transport errors and 0 retries. All runs were fully resident on the GPU (`latency_valid` true for 2,700/2,700).
- The six models are the **installed original and modified ("abliterated") Ollama checkpoints** of Llama 3.1 8B, Gemma 4 12B and Qwen 3.5 27B (`audit/AUDIT.md`).
- Settings were identical within each pair: no system prompt, the original model's sampling defaults, `num_ctx` 16384, and a joint generation cap of 12,288 tokens. The Gemma draft model was disabled.
- The benchmark is entirely benign, in five categories: everyday, underspecified, math/logic, coding and instruction following. It does **not** measure behavior on harmful requests.
- Judge: mistral-small3.1:24b, blinded, at temperature 0. It graded 2,561 responses. 139 had no visible answer and were skipped by design; 135 of those are Gemma-modified runs truncated inside their reasoning. There were 0 judge failures. **Judge scores are provisional.** A blinded 60-item human-review sample is in `results/main/human_review_sample.csv`.

## 1. Are the pairs comparable?

| Pair | Classification | Caveats |
|---|---|---|
| Llama 3.1 8B | Closely matched | Quantization differs (imatrix vs none). The modified model's baked "always comply" system prompt was bypassed with raw prompting. |
| Gemma 4 12B | Partially matched | Different conversion and quantization, an undocumented base revision, and the original ships with a draft model (disabled here). |
| Qwen 3.5 27B | Partially matched | The original has an extra MTP layer (65 vs 64 blocks) and different special tokens. |

Rendered prompts and prompt-token counts were byte-identical within every pair. No difference below can be attributed cleanly to abliteration alone, because checkpoint, quantization and provenance differ as well.

## 2. Token results (modified − original; per-task means, paired cluster bootstrap over 50 tasks)

| Pair | Metric | Original | Modified | Difference [95% CI] | Tasks mod higher / lower |
|---|---|---|---|---|---|
| Gemma | Reasoning tokens | 813 | 4,662 | **+3,848 (+473%)** [+2,702, +5,050] | 50 / 0 |
| Gemma | Answer tokens | 326 | 280 | −45 (−14%) [−93, −2] | 17 / 30 |
| Gemma | Total generated | 1,143 | 4,945 | +3,803 (+333%) [+2,659, +4,968] | 50 / 0 |
| Gemma | Reasoning share | 0.71 | 0.80 | +0.09 [+0.06, +0.12] | n/a |
| Qwen | Reasoning tokens | 1,903 | 1,800 | −102 (−5%) [−286, +73] | 24 / 26 |
| Qwen | Answer tokens | 321 | 367 | **+46 (+14%)** [+28, +65] | 43 / 6 |
| Qwen | Total generated | 2,222 | 2,195 | −27 (−1%) [−230, +187] | 28 / 22 |
| Qwen | Reasoning share | 0.81 | 0.78 | −0.03 [−0.04, −0.02] | n/a |
| Llama | Answer tokens (no reasoning stream) | 213 | 224 | +12 (+5%) [−12, +33] | 28 / 21 |

- **Gemma.** The modified checkpoint generated far more reasoning on every one of the 50 tasks. Part of this is runaway reasoning: 30% of its runs (135/450) hit the 12,288 cap inside the reasoning, against 0% for the original. These counts are **censored at the cap**, so the true difference is at least this large. Excluding truncated runs (exploratory, because it selects on behavior), the difference is still +1,197 [+712, +1,755] on 43 tasks, higher on 41 of them.
- **Qwen.** There is no clear reasoning difference. The modified model wrote somewhat longer visible answers (higher on 43/50 tasks), and its reasoning share was slightly lower.
- **Llama.** No clear difference in answer length. Its reasoning count is null by design, which does not mean "no reasoning".
- **Exact-only sensitivity.** Gemma is unchanged, because all of its runs are exact. Qwen gives reasoning −103 [−294, +77] and answer +50 [+27, +74]. Llama answer gives +14 [−9, +35]. The conclusions don't change.
- **By category (Gemma reasoning, modified − original).**

  | Category | Reasoning difference |
  |---|---|
  | Math | +9,466 |
  | Coding | +5,426 |
  | Instruction | +3,637 |
  | Everyday | +551 |
  | Underspecified | +162 |

  It was higher on 10/10 tasks in every category. For Qwen, the category reasoning differences go both ways: coding −669 [−1,165, −208] and instruction +398 [+146, +756]. These category results are exploratory.

## 3. Quality

| Pair | Correctness, original → modified | Difference [95% CI] |
|---|---|---|
| Gemma | 0.98 → 0.66 | **−0.31** [−0.43, −0.21]; lower on 24 tasks, higher on 0 |
| Llama | 0.87 → 0.84 | −0.03 [−0.10, +0.03] |
| Qwen | 0.99 → 0.99 | −0.003 [−0.011, +0.004] |

- Gemma's quality loss is concentrated where reasoning ran away:

  | Category | Original → modified correctness |
  |---|---|
  | Math | 1.00 → 0.20 |
  | Coding | 1.00 → 0.57 |
  | Instruction | 0.89 → 0.59 |
  | Everyday | 1.00 → 0.97 |
  | Underspecified | 1.00 → 1.00 |

  Truncated runs score 0 on deterministic tasks. Among non-truncated runs, Gemma's correctness difference is −0.05 [−0.12, −0.00] (exploratory). So most of the loss comes from not finishing.
- **Judge-scored answered responses** (everyday and underspecified, provisional): correctness is about 1.95–2.00 out of 2 for all six models, with no clear differences. Gemma-modified completeness on underspecified tasks is lower: 1.97 → 1.66 [−0.57, −0.07]. Qwen-modified had slightly more unsupported assumptions: 0.01 → 0.05 [+0.01, +0.09].

## 4. Clarification, refusal and verbosity

- **Refusals: 0 for all six models** on all 2,700 runs. This is expected on a benign benchmark. It says nothing about harmful requests.

| Underspecified tasks | Clarification rate, original → modified |
|---|---|
| Llama | 0.74 → 0.73 |
| Gemma | 0.81 → 0.66 |
| Qwen | 0.84 → 0.83 |

- Overall, Gemma-modified clarified a little less: −0.04 [−0.09, −0.01] across all tasks. Llama and Qwen show no clear difference.
- **Verbosity.** Visible answers were longer for Qwen-modified (+14%). Gemma-modified answers were shorter overall (−14%), mostly because many math runs never reached an answer (math answer tokens 325 → 47). On underspecified tasks Gemma-modified answers were longer (+121 [+61, +186]).
- **Latency (all runs valid).** Gemma 9.3 → 39.8 s, driven by reasoning length; throughput was unchanged (127 tok/s). Llama 0.96 → 1.01 s. Qwen 32.3 → 31.5 s.

## 5. The fan prompt (U01: "Hello, my name is Summer, and I want to learn how to fix a fan.")

All 54 runs asked a useful clarifying question (clarified = 1.0 for every model). None were truncated or refused.

| Pair | Condition | Reasoning (mean) | Answer (mean) | Total (mean) | Labels (9 runs) |
|---|---|---|---|---|---|
| Llama | original | null | 111.7 | 112.7 | 9 clarification |
| Llama | modified | null | 107.7 | 108.7 | 9 clarification |
| Gemma | original | 500.3 | 738.3 | 1,242.7 | 9 mixed |
| Gemma | modified | 580.2 | 823.0 | 1,407.2 | 6 mixed, 2 partial, 1 direct |
| Qwen | original | 724.2 | 531.6 | 1,257.8 | 3 clarification, 6 mixed |
| Qwen | modified | 687.8 | 612.3 | 1,302.1 | 4 clarification, 5 mixed |

Here "mixed" means the response asked which kind of fan it was and also gave general steps. Per-run rows are in `analysis/main/fan_prompt.csv`.

## 6. What this does and doesn't show

- It does **not** show that "uncensored models think more". One of the two measurable pairs (Gemma) generated much more reasoning, often failing to stop. The other (Qwen) did not differ in reasoning. Llama has no reasoning stream to measure.
- The Gemma effect is consistent (50/50 tasks) and large, but it is a property of these two installed checkpoints. The checkpoints differ in conversion, quantization and base revision, not only in abliteration.
- Not measured:
  - behavior on harmful or borderline requests (out of scope by design);
  - the network's internal computation (reasoning text is only a generated token stream);
  - reasoning beyond the 12,288 cap (censored);
  - other settings, prompts, system prompts or quantizations;
  - human-validated quality (the judge is provisional; the human sample is not yet filled in).
- Seeds are recorded, but prompt-prefix caching makes exact reruns non-reproducible.

## Files

| Path | Contents |
|---|---|
| `analysis/main/paired_differences.csv` | Primary and secondary paired results |
| `analysis/main/by_category.csv` | Category results (exploratory) |
| `analysis/main/supplementary.csv` | Exact-only sensitivity, non-truncated subset, judge quality |
| `analysis/main/comparable_subset_EXPLORATORY.csv` | Comparable-response subset |
| `analysis/main/response_rates.csv`, `response_labels.csv`, `missingness.csv`, `fan_prompt.csv` | Rates, labels, missingness and the fan prompt |
| `analysis/main/runs_scored.csv` | One row per run |
| `analysis/main/charts/*.png` | Charts |
| `results/main/` | Attempts, judgments, judge ID map, human-review sample (the key is kept separately) |
