"""Frozen inference configuration. Within each pair, every option is identical.
Sampling values follow the ORIGINAL model's shipped defaults and are applied to both pair members."""
OLLAMA = "http://127.0.0.1:11434"
NUM_CTX = 16384
NUM_PREDICT = 12288          # joint cap on reasoning + answer tokens (Ollama counts all generated tokens)
SYSTEM_PROMPT = ""           # empty for all models; overrides nothing because no system turn is sent
REQUEST_TIMEOUT_S = 1200
MAX_ATTEMPTS = 3             # transport/HTTP failures only; each attempt is logged separately

PAIR_OPTIONS = {
    "llama31": {"temperature": 0.6, "top_p": 0.9, "top_k": 40, "min_p": 0.0,
                "repeat_penalty": 1.0, "presence_penalty": 0.0, "frequency_penalty": 0.0},
    "gemma4":  {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0.0,
                "repeat_penalty": 1.0, "presence_penalty": 0.0, "frequency_penalty": 0.0,
                "draft_num_predict": 0},   # disables gemma4:12b speculative draft; no-op for the huihui build
    "qwen35":  {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0,
                "repeat_penalty": 1.0, "presence_penalty": 1.5, "frequency_penalty": 0.0},
}

WORKERS = [
    {"worker_id": "A", "pair_id": "llama31", "condition": "original", "model_tag": "llama3.1:8b-instruct-q4_K_M",
     "api": "generate_raw", "think": None, "family": "llama"},
    {"worker_id": "B", "pair_id": "llama31", "condition": "modified", "model_tag": "mannix/llama3.1-8b-abliterated:q4_k_m",
     "api": "generate_raw", "think": None, "family": "llama"},
    {"worker_id": "C", "pair_id": "gemma4", "condition": "original", "model_tag": "gemma4:12b",
     "api": "chat", "think": True, "family": "gemma"},
    {"worker_id": "D", "pair_id": "gemma4", "condition": "modified", "model_tag": "huihui_ai/gemma-4-abliterated:12b",
     "api": "chat", "think": True, "family": "gemma"},
    {"worker_id": "E", "pair_id": "qwen35", "condition": "original", "model_tag": "qwen3.5:27b",
     "api": "chat", "think": True, "family": "qwen"},
    {"worker_id": "F", "pair_id": "qwen35", "condition": "modified", "model_tag": "huihui_ai/qwen3.5-abliterated:27b",
     "api": "chat", "think": True, "family": "qwen"},
]

# Expected manifest digests from the audit; the runner refuses to run if a tag resolves elsewhere.
EXPECTED_DIGESTS = {
    "llama3.1:8b-instruct-q4_K_M": "46e0c10c039e",
    "mannix/llama3.1-8b-abliterated:q4_k_m": "5920dea9e0f0",
    "gemma4:12b": "6114515d63c1",
    "huihui_ai/gemma-4-abliterated:12b": "526eca3f9757",
    "qwen3.5:27b": "64ae5b1d651f",
    "huihui_ai/qwen3.5-abliterated:27b": "2c5b727e8ad6",
}

def llama_raw_prompt(user_text: str) -> str:
    """Official Llama 3.1 rendering (identical to Ollama's llama3.1 template with no system turn).
    BOS is added by the runtime."""
    return ("<|start_header_id|>user<|end_header_id|>\n\n" + user_text +
            "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n")
