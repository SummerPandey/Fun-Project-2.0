# Environment and model-pair audit

Audit date: 2026-11-08. Raw `ollama show --verbose` dumps are in `audit/show_*.json`. Probe outputs are in `audit/probe_*.json`.

## Hardware and runtime

| Item | Value |
|---|---|
| Host | `hopper`, Linux 7.0.0-31-generic (Ubuntu 24.04 base), 24 CPU threads, 62 GiB RAM |
| GPU | 1 × NVIDIA GeForce RTX 5090, 32,607 MiB; driver 610.43.02; CUDA UMD 13.3 |
| Runtime | Ollama 0.40.0 (`~/ollama/bin/ollama serve`, systemd user unit) on `127.0.0.1:11434` |
| Runtime env | `OLLAMA_MAX_LOADED_MODELS=3`, `OLLAMA_KEEP_ALIVE=30m`, `OLLAMA_CONTEXT_LENGTH=8192` (the experiment overrides it per request with `num_ctx`) |
| Other GPU users | Open WebUI on :7860 shares the same Ollama server. It could add contention if someone uses it during a run. Xorg and cinnamon use about 0.5 GB. |
| Client | Python 3.14.7 (miniconda), stdlib `urllib` only; analysis uses numpy 2.5.4, pandas 3.1.1, matplotlib 3.11.2 |

There is no other inference runtime (no vLLM, llama.cpp CLI, LM Studio or docker), and no HF tokenizer library. Nothing was downloaded, modified or restarted.

## Model inventory

| Worker | Pair | Condition | Ollama tag | Manifest digest | Weights blob (sha256 prefix) | Arch / blocks | Params (GGUF) | Quant | imatrix | Ctx (metadata) | Capabilities |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | llama31 | original | `llama3.1:8b-instruct-q4_K_M` | `46e0c10c039e` | `667b0c1932bc6ffc` | llama / 32 | 8,030,261,312 | Q4_K_M | none | 131,072 | completion, tools |
| B | llama31 | modified | `mannix/llama3.1-8b-abliterated:q4_k_m` | `5920dea9e0f0` | `656ce66dfc2920fb` | llama / 32 | 8,030,261,312 | Q4_K_M | yes (calibration_datav3) | 131,072 | completion |
| C | gemma4 | original | `gemma4:12b` | `6114515d63c1` | `bb722270d54346ad` + draft/proj `0cb0cd0a5c499d92` | gemma4 / 48 | 11,907,350,576 | Q4_K_M | yes (wikitext-2) | 262,144 | completion, vision, audio, tools, thinking |
| D | gemma4 | modified | `huihui_ai/gemma-4-abliterated:12b` | `526eca3f9757` | `b8d7a9b7fe829999` + proj `1dcc37d89299e1f0` | gemma4 / 48 | 11,907,350,576 | Q4_K_M | none | 131,072 | completion, vision, audio, tools, thinking |
| E | qwen35 | original | `qwen3.5:27b` | `64ae5b1d651f` | `c7e0e920a0948849` + proj `2abfbdeed2794d14` | qwen35 / 64 | 26,895,998,464 | Q4_K_M | none | 262,144 | completion, vision, tools, thinking |
| F | qwen35 | modified | `huihui_ai/qwen3.5-abliterated:27b` (llamacpp variant, loaded) | `2c5b727e8ad6` | `fb7973ac035cdcce` + proj `202a51c0d26b0784` | qwen35 / 65 (incl. 1 `nextn` MTP layer) | 27,320,697,856 | Q4_K_M | none | 262,144 | completion, vision, tools, thinking |

The tag `huihui_ai/qwen3.5-abliterated:27b` also lists a second `ggml` variant (`9f1f4b8914ba`) with no projector. Ollama 0.40 loads the `llamacpp` variant (`2c5b…`), which is the one used here.

The study uses only text input. Vision and audio projectors are loaded but never used.

## Tokenizers

| Pair | Tokenizer comparison |
|---|---|
| Llama | `tokens`, `merges` and `token_type` are byte-identical (128,256-token vocab, gpt2/llama-bpe). |
| Gemma | `tokens`, `merges`, `scores` and `token_type` are byte-identical (262,144-token vocab). |
| Qwen | `merges` are identical (247,587). In `tokens`, 250 of 248,320 entries differ, all at IDs ≥ 248,070 (audio, TTS and padding special tokens: the original names `<\|audio_start\|>` etc., the modified version uses `[PADn]`). `token_type` differs for 256 special-token IDs (FIM, audio and pad). The modified version also declares an extra EOS ID (248044 `<\|endoftext\|>`). Ordinary text tokens are identical, so native token counts are comparable within the pair. |

Token counts are comparable **within** each pair only. The three families use different vocabularies, so raw counts are not pooled across families.

## Chat templates and system prompts

| Pair | Finding | Handling in the experiment |
|---|---|---|
| Llama | **Material confound found.** The modified Modelfile ships a baked-in SYSTEM prompt ("…You ALWAYS comply with the user's request… a kitten is killed…", GuruBot-style). Its template also differs from the official Llama 3.1 template, and with an explicit system message it renders the system turn twice: prompt_eval 33 vs 22 tokens for an identical input. | Both models are called through `/api/generate` with `raw: true` and the same prompt string, rendered in the official Llama 3.1 format (identical to what Ollama's official template produces, with no system turn). Verified: prompt_eval_count = 28 for both on Summer's prompt, equal to the official chat rendering. The baked prompt is therefore **not** used. Ollama's official template omits the "Cutting Knowledge Date / Today Date" system preamble from Meta's HF template, and so does this rendering. |
| Gemma | Both use Ollama's built-in gemma4 renderer (`{{ .Prompt }}` template, renderer chosen by architecture). No baked system prompt. | `/api/chat`, no system message. Verified identical prompt_eval_count (34 vs 34). |
| Qwen | Both use the built-in qwen35 renderer. No baked system prompt. The original's Modelfile sets `presence_penalty 1.5`; the modified one does not. | `/api/chat`, no system message. All sampling parameters are set explicitly per request, so Modelfile defaults never apply. Verified identical prompt_eval_count (28 vs 28). |

The experiment-level system prompt is **empty for all six models**. This avoids adding any new instruction, and it removes the Llama baked prompt.

## Reasoning streams and token accounting (verified empirically)

- Gemma 4 and Qwen 3.5 (both conditions): `think: true` puts reasoning in `message.thinking`; `think: false` disables it (verified in the 2026-11-06 report).
- Llama 3.1 8B has **no separate reasoning mode** (`thinking` capability absent). Its reasoning count is `null` with status `no_separate_reasoning_mode`. This does not mean the model performs no computation.
- `eval_count` (Ollama's generated-token counter) **includes reasoning tokens and the terminal stop token**. Verified with streaming logprobs: `eval_count = len(logprob tokens) + 1` when `done_reason = stop`.
- Streaming `logprobs: true` returns every generated token as a string with raw bytes. This is the **native generated-token sequence**, so no re-tokenization is needed.
- Chunk-level attribution is unreliable: Ollama's thinking parser buffers tokens, leaving 40–55 tokens on chunks with no visible text. Reasoning and answer are therefore split **at the delimiter tokens inside the native sequence**:
  - Gemma 4: `<|channel>` `thought` … `<channel|>` → reasoning = tokens between the header and `<channel|>`; answer = tokens after it.
  - Qwen 3.5: the prompt ends with `<think>\n` (renderer); reasoning = tokens before `</think>`; answer = tokens after it.
- `gemma4:12b` (original) ships a speculative-decoding draft model (`draft_num_predict 3`). With drafting on, streaming chunks carry several tokens and logprobs are **missing** (1 entry for 159 tokens). Setting `draft_num_predict: 0` per request restores one token per chunk and complete logprobs (272 + 1 = 273 = eval_count). The experiment sets `draft_num_predict: 0` for **both** Gemma models. With exact verification, speculative decoding does not in principle change the sampling distribution, but it does change throughput. Disabling it makes latency comparable within the pair and makes token accounting native. Consequence: original-Gemma throughput here is lower than its shipped default.
- Logprobs on the non-streaming endpoint are broken for llamacpp-runner models (only 1 entry), so all runs use streaming.

## Provenance of the modified models

| Model | Source claim (Ollama page, fetched 2026-11-08) | GGUF metadata | Method |
|---|---|---|---|
| `mannix/llama3.1-8b-abliterated` | "uncensored version of Llama 3.1 8B Instruct … created with abliteration with an uncensored prompt"; links `mlabonne/Meta-Llama-3.1-8B-Instruct-abliterated`; prompt "based on GuruBot" | `general.base_model.0` = Meta-Llama-3.1-8B-Instruct (HF URL); imatrix-quantized | Refusal-direction removal (abliteration), per the source. Plus a baked prompt in the Ollama packaging, which is removed here. |
| `huihui_ai/gemma-4-abliterated:12b` | "uncensored version of google/gemma-4 created with abliteration"; refers to `remove-refusals-with-transformers`; links the HF collection `huihui-ai/gemma-4-abliterated`; no single repo or revision | `basename` Huihui-gemma-4, `finetune` it-abliterated; **no base_model field**; no imatrix | Abliteration (claimed). Base revision and whether any fine-tuning followed are not documented. |
| `huihui_ai/qwen3.5-abliterated:27b` | "uncensored version of Qwen/qwen3.5 created with abliteration"; links the HF collection `huihui-ai/qwen35-abliterated` | No base_model, license or sampling metadata; includes a `nextn` MTP layer the original Ollama build lacks | Abliteration (claimed). Base revision undocumented. |

The underlying abliteration weights could not be verified (no published diff or checkpoint hash to compare against).

## Pair classification

| Pair | Class | Rationale and confounds |
|---|---|---|
| **Llama 3.1 8B** (A vs B) | **Closely matched**, with one quantization caveat | Same declared base checkpoint (GGUF metadata), identical tokenizer and architecture, same Q4_K_M type, and abliteration documented with a source repo. Inference was made identical (raw prompt, same options). Remaining confound: **different quantization recipes** (modified used an importance matrix, original did not), so some differences may reflect quantization noise rather than abliteration. |
| **Gemma 4 12B** (C vs D) | **Partially matched** | Same architecture, param count and tokenizer. Confounds: different conversion and quantization pipelines (the original is Ollama's imatrix build, the modified has no imatrix); the base revision of the modified model is undocumented; different context metadata (262k vs 131k, irrelevant at 16k); the original's draft model (neutralized with `draft_num_predict: 0`). Differences can't be attributed cleanly to abliteration alone. |
| **Qwen 3.5 27B** (E vs F) | **Partially matched** | Same architecture family and text tokenizer. Confounds: the modified GGUF has an extra MTP layer and 0.42B more parameters; different converters (the original is Ollama's `qwen35-validation-20261004` build); special-token tables differ; the base revision is undocumented. MTP layers are not used for ordinary decoding in this runtime as far as can be determined, but this was not verified. |

No pair reaches "closely matched" without caveats. Cross-family comparisons are descriptive only.
