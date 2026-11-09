# Pilot and measurement-validation report (2026-11-09)

The pilot data are **separate** from the main study and are not pooled. They come from 10 base tasks (2 per category), the original wording only, 1 repetition and 6 models: 60 runs. All 60 completed and none failed in transport. This sample is too small for inference; the numbers below are indicative only.

## Measurement validation (phase `validation`, 24 streams, plus pilot)

| Check | Result |
|---|---|
| Routing | All six manifest digests matched the audit before every session. Prompt-token counts are identical within each pair for every pilot prompt. Rendered prompts are byte-identical within each pair for all 150 prompts. |
| Normal completion | logprob tokens + 1 stop token = `eval_count` in 11/12 validation streams and 56/60 pilot runs. |
| Truncation, inside reasoning | 6/6 models at `num_predict=48`: `done_reason=length`, logprob tokens = `eval_count` = 48 (no stop token). |
| Truncation, inside the answer | Same seed, cap = first answer index + 4: Gemma-orig, Qwen-orig and Qwen-mod gave 4 answer tokens, an identical prefix and reconciled counts. The Llama tests are trivially answer-phase. Gemma-mod's base run never closed its reasoning, so the test doesn't apply. |
| Delimiters | Gemma (both): `<\|channel>` `thought` … `<channel\|>` in every closed run; 4 Gemma-mod runs were unclosed at the cap. Qwen (both): exactly one `</think>` per run. Llama: no special tokens in the output. Control tokens are counted separately. |
| Gemma draft disabled | With the shipped default, llama-server started with `--spec-type draft-mtp --spec-draft-n-max 3` and returned 1 logprob for 1,512 tokens at 265 tok/s. With `draft_num_predict: 0` it started with no `--spec-*` flags and returned 1,510 + 1 = 1,511 tokens at 128 tok/s. The toggle forces a reload (journal evidence in `results/validation/validation.json`). |
| Gaps found | (a) **Multi-byte merge**: Ollama emits one logprob entry for byte-level tokens forming an emoji (Qwen, Llama). Re-encoding with the GGUF BPE merges reproduced the gap exactly (13 = 13; pilot 1, 2 and 8). These runs are labelled `estimated`. (b) **Trailing text-less tokens** dropped by Llama stop handling (gap 2). The Llama answer count is taken as `eval_count − stop`, also `estimated`. No pilot run was left `unavailable`. |
| Determinism | Same-seed reruns diverge when the prompt-prefix cache differs (Llama-mod: 55/56 cached tokens). Seeds are recorded but don't make runs reproducible. |
| Hardware contention | **Found and fixed.** Ollama kept up to 3 models resident, and a newly loaded Llama ran partly on CPU (4.1/6.8 GB in VRAM, 11.5 tok/s, 1,068 s for one run). The runner now unloads the other models and verifies full residency (smoke test 6/6 fully on GPU). Pilot latencies for the affected runs are invalid. |

## Pilot observations (n = 10 tasks × 1 run per model; indicative only)

| Model | Truncated at 12,288 | Reasoning tokens, median / mean | Answer tokens, median | Correctness (mean) | Clarification rate |
|---|---|---|---|---|---|
| llama3.1 original | 0 | null (no separate stream) | 105 | 0.7 | 0.2 |
| llama3.1 modified | 1 (repetition loop in M03) | null | 90.5 | 0.8 | 0.2 |
| gemma4 original | 0 | 477 / 1,159 | 152 | 0.9 | 0.2 |
| gemma4 modified | **4** (reasoning loops: I07, K03, M03, M07) | 1,224 / 5,314 | 82.5 | 0.5 | 0.2 |
| qwen3.5 original | 0 | 2,456 / 2,665 | 62 | 1.0 | 0.2 |
| qwen3.5 modified | 0 (max 10,624) | 1,283 / 2,888 | 68.5 | 1.0 | 0.2 |

- No refusals on any pilot prompt. Both underspecified tasks (U01 fan, U05 "make this shorter") drew clarification-type responses from all six models.
- Gemma-mod's higher reasoning mean is driven by unclosed loops. Those runs are censored at the cap, so the true difference is not measured; it's at least this large.
- Budget: 12,288 is kept. No original model was truncated, and the longest non-looping run was Qwen-mod at 10,624. A higher cap mostly lengthens loop runs.

## Estimated main-study cost

From pilot per-run times at full GPU residency, 2,700 runs take about 19 h of generation, about 1.3 h of model switching and about 1 h of judging. The schedule interleaves (pair, task) units with both conditions adjacent, so an early stop still leaves a task-balanced paired subset.
