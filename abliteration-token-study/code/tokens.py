"""Native token accounting from Ollama streaming logprobs.

Each streamed chunk may carry `logprobs` entries; their concatenation is the generated token
sequence (one entry per sampled token). The terminal stop token is NOT included but IS counted
in eval_count. Reasoning/answer are split at delimiter tokens inside that sequence and then
validated against Ollama's own parsed `thinking` / `content` text.

Output confidence levels:
  exact      - logprob sequence reconciles with eval_count AND decoded segments match parsed text
  estimated  - sequence reconciles but a segment's decoded text does not match parsed text,
               or a delimiter is ambiguous; counts kept but flagged
  unavailable- sequence does not reconcile with eval_count (e.g. missing logprobs); split is null
"""
import re

SPECIAL_RE = re.compile(r"^(<\|[^|>]*\|?>|<[a-z_]*\|>|</?think>)$")


def _decode(entries):
    b = bytearray()
    for e in entries:
        bb = e.get("bytes")
        b.extend(bytes(bb) if bb is not None else e["token"].encode())
    return b.decode("utf-8", errors="replace")


def _norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def account(family, think_enabled, entries, final, thinking_text, content_text):
    toks = [e["token"] for e in entries]
    n = len(toks)
    eval_count = final.get("eval_count")
    done_reason = final.get("done_reason")
    stop_tok = 1 if done_reason == "stop" else 0
    reconciled = eval_count is not None and n + stop_tok == eval_count
    r = dict(n_logprob_tokens=n, eval_count=eval_count, done_reason=done_reason,
             stop_token_counted=stop_tok, reconciled=reconciled,
             reasoning_tokens=None, answer_tokens=None, control_tokens=None, control_token_list=None,
             reasoning_status=None, token_count_method=None, confidence=None, boundary_notes=[])
    specials = [(i, t) for i, t in enumerate(toks) if SPECIAL_RE.match(t)]

    if family == "llama":
        r["reasoning_status"] = "no_separate_reasoning_mode"
        # Llama has a single (answer) segment, so every generated non-control token is an answer token:
        # answer = eval_count - stop - control is native even if a few logprob entries are missing
        # (pilot A/K05: 2 trailing text-less tokens dropped by stop-sequence handling).
        gap = (eval_count - n - stop_tok) if eval_count is not None else None
        multib = [e for e in entries if len(e.get("bytes") or []) >= 3 and any(x > 127 for x in e["bytes"])]
        if not reconciled and not (gap and gap > 0):
            r.update(token_count_method="eval_count_only", confidence="unavailable")
            return r
        ctrl = [t for _, t in specials]
        if not reconciled:
            r["boundary_notes"].append(f"gap={gap}_merged_multibyte_entries={len(multib)}")
            idx = [i for i, e in enumerate(entries) if e in multib]
            add = _gap_by_segment("llama", entries, idx, gap, [entries])
            method = ("native_logprob_sequence+bpe_gap_reconstruction_verified" if add is not None
                      else "eval_count_minus_stop_and_control")
            r.update(answer_tokens=n - len(ctrl) + gap, control_tokens=len(ctrl) + stop_tok,
                     control_token_list=ctrl + (["<stop>"] if stop_tok else []),
                     token_count_method=method, confidence="estimated")
            return r
        r.update(answer_tokens=n - len(ctrl), control_tokens=len(ctrl) + stop_tok,
                 control_token_list=ctrl + (["<stop>"] if stop_tok else []),
                 token_count_method="native_logprob_sequence", confidence="exact")
        if _norm(_decode([e for e in entries if not SPECIAL_RE.match(e["token"])])) != _norm(content_text):
            r["confidence"] = "estimated"; r["boundary_notes"].append("answer_text_mismatch")
        return r

    if not think_enabled:
        r["reasoning_status"] = "disabled"

    gap = (eval_count - n - stop_tok) if eval_count is not None else None
    # Validated failure mode (validation V1/F/U01): Ollama emits ONE logprob entry for several
    # byte-level tokens that together form a multi-byte UTF-8 character (e.g. emoji in Qwen's BPE).
    # If the gap is positive and every multi-byte entry lies in one segment, the gap is attributed
    # to that segment and the split is labelled 'estimated'. Otherwise the split is unavailable.
    merge_candidates = [i for i, e in enumerate(entries) if len(e.get("bytes") or []) >= 3 and any(x > 127 for x in e["bytes"])]
    if not reconciled and not (gap and gap > 0 and merge_candidates):
        r.update(token_count_method="eval_count_only", confidence="unavailable",
                 reasoning_status=r["reasoning_status"] or "supported_but_unobserved")
        r["boundary_notes"].append(f"logprob_tokens({n})+stop({stop_tok})!=eval_count({eval_count})")
        return r
    if not reconciled:
        r["boundary_notes"].append(f"gap={gap}_merged_multibyte_entries={len(merge_candidates)}")

    if family == "gemma":
        opens = [i for i, t in enumerate(toks) if t == "<|channel>"]
        closes = [i for i, t in enumerate(toks) if t == "<channel|>"]
        if not opens:
            reasoning, answer, ctrl = [], entries, []
            if _norm(thinking_text):
                r["boundary_notes"].append("thinking_text_without_channel_tokens")
        elif opens[0] == 0 and len(opens) == 1 and n > 1 and toks[1] == "thought" and len(closes) <= 1:
            c = closes[0] if closes else n
            reasoning, answer = entries[2:c], entries[c + 1:] if closes else []
            ctrl = ["<|channel>", "thought"] + (["<channel|>"] if closes else [])
            if not closes:
                r["boundary_notes"].append("reasoning_unclosed")
        else:
            r.update(token_count_method="native_logprob_delimiter_split", confidence="estimated",
                     reasoning_status="supported_and_measured")
            r["boundary_notes"].append(f"unexpected_channel_layout opens={opens[:5]} closes={closes[:5]}")
            c = closes[0] if closes else n
            reasoning, answer, ctrl = entries[:c], entries[c + 1:], []
    elif family == "qwen":
        closes = [i for i, t in enumerate(toks) if t == "</think>"]
        if len(closes) == 1:
            c = closes[0]
            reasoning, answer, ctrl = entries[:c], entries[c + 1:], ["</think>"]
        elif not closes and done_reason == "length":
            reasoning, answer, ctrl = entries, [], []
            r["boundary_notes"].append("reasoning_unclosed")
        elif not closes:
            reasoning, answer, ctrl = [], entries, []
            r["boundary_notes"].append("no_think_close_token")
        else:
            c = closes[0]
            reasoning, answer, ctrl = entries[:c], entries[c + 1:], ["</think>"]
            r["boundary_notes"].append(f"multiple_think_close={len(closes)}")
    else:
        raise ValueError(family)

    # any remaining special tokens inside segments are counted as control tokens
    extra_r = [e["token"] for e in reasoning if SPECIAL_RE.match(e["token"])]
    extra_a = [e["token"] for e in answer if SPECIAL_RE.match(e["token"])]
    reasoning_t = [e for e in reasoning if not SPECIAL_RE.match(e["token"])]
    answer_t = [e for e in answer if not SPECIAL_RE.match(e["token"])]
    ctrl_all = ctrl + extra_r + extra_a + (["<stop>"] if stop_tok else [])
    r.update(reasoning_tokens=len(reasoning_t), answer_tokens=len(answer_t), control_tokens=len(ctrl_all),
             control_token_list=ctrl_all, token_count_method=r["token_count_method"] or "native_logprob_delimiter_split",
             reasoning_status=r["reasoning_status"] or "supported_and_measured")
    if r["confidence"] is None:
        r["confidence"] = "exact"
    th_ok = _norm(_decode(reasoning_t)) == _norm(thinking_text)
    an_ok = _norm(_decode(answer_t)) == _norm(content_text)
    r["reasoning_text_matches"] = th_ok
    r["answer_text_matches"] = an_ok
    if not (th_ok and an_ok) or any(x.startswith(("multiple", "no_think", "thinking_text")) for x in r["boundary_notes"]):
        r["confidence"] = "estimated"
    if extra_r or extra_a:
        r["boundary_notes"].append(f"special_tokens_inside_segments={extra_r + extra_a}")
    assert r["reasoning_tokens"] + r["answer_tokens"] + r["control_tokens"] == n + stop_tok
    if not reconciled:
        add = _gap_by_segment(family, entries, merge_candidates, gap, [reasoning_t, answer_t])
        if add is None:
            r.update(reasoning_tokens=None, answer_tokens=None, confidence="unavailable",
                     token_count_method="eval_count_only")
            r["boundary_notes"].append("gap_not_reconstructable")
            return r
        r["reasoning_tokens"] += add[0]; r["answer_tokens"] += add[1]
        r.update(confidence="estimated", token_count_method="native_logprob_delimiter_split+bpe_gap_reconstruction_verified")
    return r


def _gap_by_segment(family, entries, cand_idx, gap, segments):
    """Re-encode merged multi-byte entries with the model's own GGUF BPE merges.
    Returns per-segment extra counts only if their sum equals the native gap exactly."""
    try:
        from bpe_local import bpe_len, FILES
    except Exception:
        return None
    if family not in FILES:
        return None
    extra = {id(entries[i]): bpe_len(family, bytes(entries[i]["bytes"])) - 1 for i in cand_idx}
    if sum(extra.values()) != gap:
        return None
    return [sum(extra.get(id(e), 0) for e in seg) for seg in segments]
