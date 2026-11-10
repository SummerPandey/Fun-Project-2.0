"""Minimal byte-level BPE using the exact vocab+merges embedded in each model's GGUF metadata
(audit/show_*.json). Used ONLY to re-encode individual merged multi-byte logprob entries, so that
the per-segment token gap can be reconstructed and checked against the native eval_count."""
import json, functools, pathlib
AUDIT = pathlib.Path(__file__).resolve().parent.parent / "audit"
FILES = {"qwen": "show_qwen3.5_27b.json", "llama": "show_llama3.1_8b-instruct-q4_K_M.json"}


def _bytes_to_unicode():
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]; n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b); cs.append(256 + n); n += 1
    return dict(zip(bs, map(chr, cs)))


B2U = _bytes_to_unicode()


@functools.lru_cache(maxsize=None)
def _ranks(family):
    mi = json.loads((AUDIT / FILES[family]).read_text())["model_info"]
    return {tuple(m.split(" ", 1)): i for i, m in enumerate(mi["tokenizer.ggml.merges"])}


def bpe_len(family, raw_bytes):
    ranks = _ranks(family)
    word = [B2U[b] for b in raw_bytes]
    while len(word) > 1:
        pairs = [(ranks.get((word[i], word[i + 1]), 1 << 30), i) for i in range(len(word) - 1)]
        r, i = min(pairs)
        if r == 1 << 30:
            break
        word = word[:i] + [word[i] + word[i + 1]] + word[i + 2:]
    return len(word)
