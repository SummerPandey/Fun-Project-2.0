# Superseded: judgments made under judge pin b9aaf0c2586a

Moved here (not deleted) on 2026-11-07, with the user's OK, before re-judging Pilot 2 in place.

- `judgments.jsonl`: the 720 first-pass judgments. Each row records judge_revision b9aaf0c2586a.
- `corrections.jsonl`: the 8 correction turns produced from those judgments (never judged).

Why: Ollama 0.40 ran an automatic "local compat GGUF migration" on the judge
mistral-small3.1:24b at 03:38:28-03:38:39 local, during the first judge pass. It wrote new
split blobs (sha256-974b8e6ce74d text, sha256-81c41cd4eb21 vision projector) and replaced the
manifest with two variants: b02dc4066b18 (original blob sha256-1fa8532d986d) and
8f3b5653ff8b (new split blobs, selected). The judge reloaded from the new blob at 03:38:42,
and all 720 judgments are timestamped after that, so they most likely came from the new
weights despite carrying the old pin. Verdict: DIFFERENT/UNKNOWN. Full diagnosis: comms H5.

The judge was re-pinned to 8f3b5653ff8b and every answer re-judged; new correction turns
were generated from the new judgments. These files are kept for the old-vs-new comparison.
