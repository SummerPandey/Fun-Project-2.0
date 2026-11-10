# Frozen protocol: original vs modified checkpoints (v1)

Status: **FROZEN 2026-11-09, after the pilot.** See the freeze record at the bottom.

## Scope and framing

- This compares **the installed original and modified ("abliterated") Ollama checkpoints** for three families: Llama 3.1 8B, Gemma 4 12B and Qwen 3.5 27B. See `audit/AUDIT.md`.
- "Censored" and "uncensored" are informal labels. The data uses `original` and `modified`.
- Quantization, conversion and provenance differences (and, for Qwen, an extra MTP layer) prevent clean attribution of any difference to abliteration alone. Results describe these checkpoints under these prompts and settings only.
- The benchmark is entirely benign. It does **not** measure behavior on harmful requests. An earlier draft category of benign prompts containing alarming-sounding words was dropped and is not part of v1.
- Reasoning **text** is a generated token stream. It is not a faithful or complete record of the network's computation, which runs for every token, answer tokens included. Llama 3.1 has no separate reasoning stream. Its reasoning count is null, which does not mean "no reasoning".

## Hypotheses (two-sided; no direction assumed)

- H1 (primary): within the Gemma and Qwen pairs, mean reasoning-token count differs between modified and original.
- H2: visible-answer tokens and total generated tokens differ within each pair.
- H3: correctness and completeness differ within each pair.
- H4: clarification, refusal and truncation rates differ within each pair.

## Outcomes

- **Primary:** modified − original reasoning tokens (Gemma and Qwen pairs only), using runs whose token measurement is `exact` or `estimated` (verified BPE gap reconstruction).
- **Secondary:** answer tokens; total generated tokens (native `eval_count`, including the stop token); reasoning share = reasoning / (reasoning + answer), excluding control tokens; correctness; completeness; clarification rate; refusal rate; unsupported-assumption rate; truncation and error rates; wall latency and throughput.

## Benchmark

`benchmark/benchmark_v1.json` contains 50 base tasks in 5 categories × 3 centrally authored variants (`v0_original`, `v1_natural`, `v2_conversational`) = 150 prompts.

| Category | Tasks | Scoring |
|---|---|---|
| everyday | E01–E10 | judge; E07 also numeric |
| underspecified | U01–U10 (U01 = Summer's exact prompt) | judge; U06 has a supplementary keyword check |
| math_logic | M01–M10 | deterministic final-answer check |
| coding | K01–K10 | deterministic sandboxed hidden tests |
| instruction | I01–I10 | deterministic constraint checks, plus judge for content |

Underspecified tasks record their plausible interpretations and missing information. `clarification_warranted` is `required` or `optional`. For `optional` tasks, a useful clarifying question and an appropriately qualified answer are scored as equally good.

## Inference settings (identical within each pair)

- Runtime: Ollama 0.40.0, one RTX 5090, one model loaded and generating at a time. Six logical workers (A–F) in one harness (`code/runner.py`), each calling its own model tag. Manifest digests are checked before every session.
- Fresh single-turn conversation per run. **No system prompt** for any model.
- Llama pair: `/api/generate` with `raw: true` and the official Llama 3.1 rendering. This bypasses the modified model's baked "always comply" system prompt and its system-duplicating template.
- Gemma and Qwen pairs: `/api/chat` with native renderers and `think: true`. Rendered prompts were verified byte-identical within each pair for all 150 prompts (`results/pilot/rendered_prompts.jsonl`).
- Sampling (the original model's shipped defaults, applied to both members):
  - Llama: T = 0.6, top_p = 0.9, top_k = 40
  - Gemma: T = 1.0, top_p = 0.95, top_k = 64, `draft_num_predict = 0`
  - Qwen: T = 1.0, top_p = 0.95, top_k = 20, presence_penalty = 1.5
  - All: min_p = 0, repeat_penalty = 1.0
- `num_ctx` = 16384. `num_predict` = **12288** (confirmed by the pilot). The cap applies **jointly** to reasoning and answer tokens, and prompt + cap stays below num_ctx, so llama-server's `--context-shift` never triggers.
- Seeds: `seed = sha256(task|variant|rep)`, identical across models. Matching seeds does not make different models' samples equivalent. Prompt-prefix caching also makes same-seed reruns non-reproducible (observed in validation).

## Token measurement

Streaming logprobs give the native generated-token sequence. Reasoning and answer are split at the native delimiters (Gemma `<|channel>thought … <channel|>`; Qwen `… </think>`), and each decoded segment is checked against Ollama's parsed `thinking`/`content` text.

| Confidence | Meaning |
|---|---|
| `exact` | The sequence reconciles with `eval_count` and the decoded text matches. |
| `estimated` | Ollama merged multi-byte characters into single entries, and the model's own GGUF BPE merges reconstruct the gap **exactly**; or a text or boundary mismatch was flagged. |
| `unavailable` | Otherwise. The split is null and only `eval_count` is kept. |

Control tokens (delimiters and the stop token) are counted separately and excluded from reasoning share.

## Schedule

- Blocks of (pair, base task): all 9 runs (3 variants × 3 repetitions) for one condition, then 9 for the other. Run order within a block is random. Half the tasks in each pair run original-first and half modified-first. Block units are shuffled across pairs (seed 20261108).
- A warm-up request follows every model switch. Its load time is logged separately (`load_log.jsonl`), and `load_duration` is recorded per run.
- Checkpointing: one immutable raw file per attempt, plus an fsync'd `attempts.jsonl`. Resume skips completed runs. Transport errors are retried as new attempts (max 3) and kept.

## Exclusions

- Transport-failed attempts are excluded from analysis but kept in the logs.
- Truncated runs (`done_reason = length`) are **kept**. They are labelled `truncated`, score correctness 0 on deterministic tasks, and keep their native token counts. The cap therefore censors reasoning counts, which is reported explicitly.
- Token-split analyses use only `exact` and `estimated` runs. A sensitivity check uses `exact` only.
- Pilot data are never pooled with main-study data.

## Scoring

- **Deterministic** (`code/scoring.py`): math final-answer line (numeric tolerance, or yes/no); coding hidden tests in a sandboxed `python3 -I -S` subprocess (1 GB memory, 5 s CPU, 10 s wall); instruction constraints. Correctness is pass/fail. Completeness is the fraction of components passed.
- **Judge** (`code/judge.py`): mistral-small3.1:24b at temperature 0 with a JSON schema. It sees only the prompt, the rubric and the visible answer: no reasoning text and no identity. Items are shuffled under opaque IDs. It supplies the response label and the subjective scores for the everyday and underspecified tasks and the content of instruction tasks. **Judge scores are provisional.** A stratified blinded sample is exported for human review (`human_review_sample.csv`).
- Label precedence: runtime error → `error`; truncated with an empty or partial answer → `truncated`; otherwise the judge label.

## Statistical analysis

- Per pair: per-task condition means (equal weight per base task, averaging variants and repetitions), then the modified − original difference. 95% CI from a **paired cluster bootstrap over base tasks** (10,000 resamples), so variants and repetitions stay together.
- The report gives absolute and percent differences (percent undefined if the original mean is 0), medians, the number of tasks where modified is higher or lower, and n and missingness.
- Results are reported by pair, then by category. Category-level and secondary comparisons are **exploratory**, with no multiple-comparison correction.
- Comparable-response subset (both conditions gave the same label in the same task/variant/repetition cell): **exploratory**, because it selects on behavior.
- No pooling of raw token counts across families.

## Changes made after the pilot (applied before the freeze; the pilot data stay separate)

1. **Model residency.** With `OLLAMA_MAX_LOADED_MODELS=3`, Ollama kept other models resident and a newly loaded Llama ran partly on CPU: 4.1 of 6.8 GB in VRAM, 11.5 tok/s instead of about 227 (pilot run B/M03 took 1,068 s). The runner now unloads every other model before each switch, verifies `size_vram == size`, and stores `fully_on_gpu_before/after` and `latency_valid` per run. Latency analyses use only `latency_valid` runs. Pilot latencies for the affected runs are not valid.
2. **Llama token count.** Llama has a single segment, so `answer = eval_count − stop − control` is native even when Ollama drops a few text-less trailing logprob entries (pilot A/K05). It is labelled `estimated` (`eval_count_minus_stop_and_control`).
3. **Multi-byte gap reconstruction.** Merged emoji logprob entries are re-encoded with the model's own GGUF BPE merges. The split is kept only if the extra tokens equal the native gap exactly (validation F/U01: 13 = 13). Otherwise the split is null.
4. **Scoring.** The math final answer is extracted leniently (`Final answer:` line, then "the final answer is", then the last `\boxed{}`). `format_ok` is recorded separately, so formatting doesn't count as correctness. The I07 lipogram keyword topic check was removed, because nearly every ocean word contains "e"; topicality is left to the judge.
5. **Accounting.** The analysis re-derives token accounting from the immutable raw streams with the frozen `code/tokens.py`.

## Freeze record

- Benchmark: `benchmark/benchmark_v1.json`, sha256 `4663fa5fd20bf4c919dcba6ea23e26df6a62f31ec87e6ccba3bbe8043ba18fb1`. The prompt texts are identical to the pilot's benchmark (`00eb9b21…`); only I07's check metadata changed.
- Main design: 50 tasks × 3 variants × 3 repetitions × 6 models = **2,700 planned runs**.
- Settings: `code/config.py` as committed at freeze time (sha256 is recorded in `protocol/freeze_hashes.txt`).
- If time is limited, the main schedule's order (shuffled (pair, task) units, both conditions adjacent) means any completed prefix is a task-balanced paired subset. Incomplete units are dropped from the paired analysis and reported.
