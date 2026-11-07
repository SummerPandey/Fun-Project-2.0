# Data schema

Every file the pipeline writes, every field, and how to read it. All files live in
`pilot/results/` (a real run) or `examples/mock_run/` (synthetic example). JSONL = one JSON
object per line, appended as the run goes; the **last** row for a key wins if a stage re-ran.

A **key** identifies one answer: `model|prompt_id|wording|run`, for example
`qwen3.5-27b-standard|P03|original|s2`.

## `generations.jsonl`: one row per answer (720 in a full run)

| Field | Type | Meaning |
|---|---|---|
| `timestamp` | ISO 8601 UTC | When the row was written. |
| `model` | str | Model name from `config.json` (e.g. `llama3.1-8b-abliterated`). |
| `family` | str | `qwen`, `llama` or `gemma`. Token counts compare only within a family. |
| `variant` | str | `standard` or `abliterated`. |
| `repo` | str | Ollama tag (or Hugging Face repo with the vLLM backend). |
| `revision` | str | Full weights digest (Ollama) or commit hash (vLLM); `mock` in mock runs. |
| `prompt_id` | str | `P01` … `P10`. |
| `wording` | str | `original` (risky-sounding) or `twin` (neutral rewording). |
| `run` | str | `s1` … `s5` (sampled, temperature 0.7) or `greedy` (temperature 0). |
| `seed` | int or null | 1-5 for sampled runs, null for greedy (sent to Ollama as 0). |
| `temperature` | float | 0.7 sampled, 0.0 greedy. |
| `prompt_text` | str | The exact text sent, checked against `pilot_prompts.json` by the verifier. |
| `output_text` | str | The **visible answer only** (no thinking). This is what the judge grades. |
| `input_tokens` | int | Prompt tokens incl. chat template (Ollama `prompt_eval_count`). |
| `output_tokens` | int | **All generated tokens, thinking included** (Ollama `eval_count`). The cost measure. |
| `finish_reason` | str | `stop` (finished) or `length` (hit `max_tokens`). |
| `hit_cap` | bool | `finish_reason == "length"`. |
| `latency_s` | float | Seconds for this request (Ollama `total_duration`). Not comparable within pairs (draft models, MTP layers). |
| `batch_size` | int | 1 with Ollama (sequential); the vLLM batch size otherwise. |
| `thinking_text` | str | *Ollama only.* The hidden reasoning, stored separately. Empty when thinking is off. |
| `thinking_tokens_est` | int | *Ollama only.* `eval_count × thinking chunks / all chunks`. An **estimate**. |
| `answer_tokens_est` | int | *Ollama only.* `output_tokens − thinking_tokens_est`. |
| `thinking_chunks`, `answer_chunks` | int | *Ollama only.* Streamed chunk counts behind the estimate. |
| `hit_cap_in_thinking` | bool | *Ollama only.* Cap reached before any visible answer. |
| `think` | bool or null | *Ollama only.* The `think` flag sent (null = not sent; model has no thinking mode). |
| `options` | object | *Ollama only.* Every sampling option sent: temperature, top_p, top_k, min_p, presence_penalty, frequency_penalty, repeat_penalty, seed, num_ctx, num_predict. |
| `backend`, `backend_version` | str | *Ollama only.* `ollama` and the server version. |
| `mock` | bool | true only for synthetic `--mock` rows. |

## `judgments.jsonl`: one row per judged answer

| Field | Type | Meaning |
|---|---|---|
| `key` | str | The answer's key (see top). |
| `model`, `prompt_id`, `wording`, `run` | str | Copied from the answer. |
| `refusal_type` | str | `full_refusal`, `partial_refusal` or `full_answer` (judge). |
| `required_met` | list[bool] | One per Required checklist item in `pilot_prompts.json`. |
| `materially_wrong` | bool | Judge: a step or claim would fail or cause harm. |
| `caution_present` | bool | Judge: a necessary caution is included. |
| `useful_judge` | bool | The judge's own `useful` value. |
| `useful` | bool | **Recomputed in code**: all required met, not materially wrong, not a full refusal. This one is analysed. |
| `judge_inconsistent` | bool | `useful_judge != useful`. |
| `judge_error` | bool | Judge reply unparseable even after one retry (other judge fields are null). |
| `judge_attempts` | int | 1, or 2 if the retry was needed. |
| `raw_output` | str | The judge's raw reply. |
| `keyword_refusal` | bool | Regex match on "I can't / I cannot / I'm sorry / …". Approximate; comparison only. |
| `judge_repo`, `judge_quantization`, `judge_revision` | str | Which judge weights produced this row. |
| `timestamp`, `mock` | | As above. |

## `capability.jsonl`: one row per model × capability item (greedy)

`model`, `family`, `variant`, `repo`, `revision`, `item_id` (`gsm8k:<i>` or `mmlu:<i>`),
`dataset`, `gold`, `prediction` (last number for GSM8K, first standalone A-D for MMLU, or null),
`correct`, `output_text`, `input_tokens`, `output_tokens`, `finish_reason`, `hit_cap`, the
Ollama-only fields above, `timestamp`, `mock`. Cap is 1,024 tokens and thinking is off
(`capability.think: false`).

`capability_items.json` freezes the 500 drawn items (seed 2026) so every model sees the same ones.

## `summary.json`: written by the `analyze` stage

| Path | Meaning |
|---|---|
| `mock`, `generated_at`, `notes` | Provenance and the method notes. |
| `judge` | Counts: judged, errors, inconsistent, missing; which judge weights were used. |
| `by_model.<model>.<sampled|greedy>.<original|twin|block>` | Per-condition stats (below). |
| `within_family_ratios.<run set>.<condition>.<metric>` | abliterated / standard per family, and their mean. Metrics: `mean_output_tokens`, `mean_thinking_tokens_est`, `tpua`. |
| `capability` | Accuracy per model and abliterated − standard in percentage points. |
| `block` | Per prompt: which wording the blocking regex blocks and which answer the block path uses. |

Per-condition stats: `n_attempts`, `n_answered`, `mean_input_tokens`, `mean_output_tokens`,
`mean_thinking_tokens_est`, `cap_hit_rate`, `cap_hit_in_thinking_rate`, `keyword_refusal_rate`,
`full_refusal_rate`, `partial_refusal_rate`, `useful_rate`, `n_judged`, `n_unjudged_answers`,
`refusal_source` (`judge` or `keyword`), and `tpua` = {`numerator_tokens`, `denominator_useful`,
`value`}. **TPUA** (tokens per useful answer) = Σ(input + output tokens) over judged attempts ÷
number of useful attempts; `"undefined"` if none were useful.

Conditions: `original` and `twin` are the model's answers to that wording. `block` simulates a
keyword filter: if the original wording contains a blocked word, the user sees a block message
(0 tokens) and re-asks with the twin; that path's cost is the twin answer's.

## `summary.md`

The same numbers as human-readable tables.

## `per_prompt.csv` / `per_prompt.md`: written by `tools/visualize.py`

One row per model × prompt × wording, sampled runs only (n = 5): `family`, `variant`, `model`,
`prompt_id`, `wording`, `n`, `n_judged`, `mean_output_tokens`, `mean_thinking_tokens_est`,
`mean_input_tokens`, `full_refusal_rate`, `useful_rate`, `cap_hit_rate`. The `.md` version
pairs standard and abliterated side by side per family. **This is the main "P01-P10, model vs
model" view.**

## `handcheck.csv` / `handcheck_key.csv`: written by the `sample` stage

60 answers, stratified by model, wording, refusal label and cap hit. `handcheck.csv` has no model
names or token counts (they can reveal the model) and blank `useful_author`,
`refusal_type_author` and `notes` columns **for the human author to fill in**. `handcheck_key.csv`
maps `anon_id` to the model and automatic labels. Do not open the key before scoring.

## `verify_report.md` / `verify_report.json`: written by `tools/verify_results.py`

A list of `{level: PASS|WARN|FAIL, area, message}` with `fails` and `warnings` totals.

## `figures/*.png` and `dashboard.html`: written by `tools/visualize.py`

| Figure | Shows |
|---|---|
| `progress.png` | Answers done per model and stage. |
| `per_prompt_tokens.png` | Mean output tokens per prompt, standard (blue) vs abliterated (orange), per family and wording. |
| `refusal_heatmap.png` | Full refusal rate for every model × prompt × wording. |
| `thinking_split.png` | Mean visible-answer tokens vs estimated thinking tokens per model. |
| `token_distribution.png` | Spread of output tokens per model and wording. |
| `family_ratios.png` | abliterated / standard ratios (mean output tokens, TPUA) per family and condition. |
| `capability.png` | GSM8K and MMLU accuracy, standard vs abliterated. |

`dashboard.html` is a single self-contained file (figures embedded). It has an interactive
per-prompt chart with family, wording and measure selectors, hover tooltips with the prompt
text, and a table view of the same numbers.
