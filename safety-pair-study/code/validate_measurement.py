"""Measurement-validation checks (phase 'validation'; data kept separate from pilot/main).

V1 normal completion: each model, 2 prompts -> logprob tokens + stop == eval_count; segment text matches.
V2 truncation inside reasoning (or answer for Llama): num_predict=48 -> done_reason=length, tokens == eval_count.
V3 truncation inside the answer: rerun V1's first prompt with the same seed and
   num_predict = (index of first answer token) + 4; checks determinism and answer-phase truncation.
V4 Gemma draft: gemma4:12b with shipped default vs draft_num_predict=0: logprob coverage,
   tokens per chunk, throughput, and server log lines mentioning the draft model.
Outputs results/validation/validation.json and raw streams in raw/validation/.
"""
import json, sys, pathlib, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
import config as C, runner as R
from tokens import account

OUT = ROOT / "results" / "validation"; OUT.mkdir(parents=True, exist_ok=True)
RAW = ROOT / "raw" / "validation"; RAW.mkdir(parents=True, exist_ok=True)
b, sha = R.bench(); P = {p["prompt_id"]: p for p in b["prompts"]}
PROMPTS = ["M04_v0_original", "U01_v0_original"]


def call(w, text, seed, npred, tag, opt_override=None):
    ep, body = R.build_request(w, text, seed, npred)
    if opt_override is not None:
        body["options"] = {**body["options"], **opt_override}
        body["options"] = {k: v for k, v in body["options"].items() if v is not None}
    chunks, wall, ttft = R.post_stream(ep, body)
    path = RAW / f"{tag}.jsonl"
    path.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks))
    fin = chunks[-1]
    th = "".join((c.get("message") or {}).get("thinking", "") for c in chunks)
    ct = "".join((c.get("response", "") if ep == "generate" else (c.get("message") or {}).get("content", "")) for c in chunks)
    ent = [e for c in chunks for e in (c.get("logprobs") or [])]
    acc = account(w["family"], bool(w["think"]), ent, fin, th, ct)
    nonempty = [c for c in chunks if not c.get("done")]
    return {"tag": tag, "model": w["model_tag"], "num_predict": npred, "seed": seed, "done_reason": fin.get("done_reason"),
            "eval_count": fin.get("eval_count"), "n_chunks": len(nonempty), "n_logprob_tokens": len(ent),
            "tokens_per_chunk": (fin.get("eval_count", 0) / max(1, len(nonempty))),
            "throughput": fin.get("eval_count", 0) / max(1e-9, fin.get("eval_duration", 0) / 1e9),
            "load_s": fin.get("load_duration", 0) / 1e9, "wall_s": wall, "accounting": acc,
            "first_tokens": [e["token"] for e in ent[:4]], "token_seq_sha": __import__("hashlib").sha256(
                json.dumps([e["token"] for e in ent]).encode()).hexdigest()[:16]}


def main():
    res = {"benchmark_sha256": sha, "started": R.now(), "V1": [], "V2": [], "V3": [], "V4": []}
    for w in C.WORKERS:
        R.warmup(w, OUT / "load_log.jsonl")
        for pid in PROMPTS:
            r = call(w, P[pid]["prompt_text"], 7, C.NUM_PREDICT, f"V1__{w['worker_id']}__{pid}")
            res["V1"].append(r); print("V1", w["worker_id"], pid, r["done_reason"], r["eval_count"], r["accounting"]["confidence"], flush=True)
        r = call(w, P[PROMPTS[1]]["prompt_text"], 7, 48, f"V2__{w['worker_id']}")
        res["V2"].append(r); print("V2", w["worker_id"], r["done_reason"], r["eval_count"], r["n_logprob_tokens"], flush=True)
        v1 = res["V1"][-2]; a = v1["accounting"]
        if a["confidence"] != "unavailable":
            first_answer_idx = (a["reasoning_tokens"] or 0) + (a["control_tokens"] - a["stop_token_counted"])
            npred = first_answer_idx + 4
            r = call(w, P[PROMPTS[0]]["prompt_text"], 7, npred, f"V3__{w['worker_id']}")
            r["same_prefix_as_V1"] = None
            full = [json.loads(l) for l in (RAW / f"V1__{w['worker_id']}__{PROMPTS[0]}.jsonl").read_text().splitlines()]
            ft = [e["token"] for c in full for e in (c.get("logprobs") or [])]
            tt = [e["token"] for c in [json.loads(l) for l in (RAW / f"V3__{w['worker_id']}.jsonl").read_text().splitlines()]
                  for e in (c.get("logprobs") or [])]
            r["same_prefix_as_V1"] = ft[:len(tt)] == tt
            res["V3"].append(r); print("V3", w["worker_id"], r["done_reason"], r["eval_count"], r["accounting"]["answer_tokens"],
                                       "prefix_match", r["same_prefix_as_V1"], flush=True)
    g = next(w for w in C.WORKERS if w["model_tag"] == "gemma4:12b")
    t0 = time.time()
    for setting, override in [("draft_default", {"draft_num_predict": None}), ("draft_off", {"draft_num_predict": 0}),
                              ("draft_default_2", {"draft_num_predict": None})]:
        r = call(g, P["E05_v0_original"]["prompt_text"], 11, 2048, f"V4__{setting}", override)
        r["setting"] = setting; res["V4"].append(r)
        print("V4", setting, "chunks", r["n_chunks"], "lp", r["n_logprob_tokens"], "eval", r["eval_count"],
              "tok/chunk %.2f" % r["tokens_per_chunk"], "tps %.0f" % r["throughput"], "load %.1f" % r["load_s"], flush=True)
    since = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0 - 5))
    log = subprocess.run(["journalctl", "--user", "-u", "ollama", "--since", since, "--no-pager"], capture_output=True, text=True).stdout
    res["V4_log_draft_lines"] = [l for l in log.splitlines() if "draft" in l.lower() or "assistant" in l.lower()][:40]
    res["finished"] = R.now()
    (OUT / "validation.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print("wrote", OUT / "validation.json")


if __name__ == "__main__":
    main()
