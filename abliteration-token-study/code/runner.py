"""Experiment runner: six logical workers (A-F), one per model, executed sequentially on one GPU.

  python3 code/runner.py schedule <phase> [--tasks T1,T2,..] [--variants v0_original,..] [--reps N]
  python3 code/runner.py run <phase> [--limit N] [--num-predict N]
  python3 code/runner.py render <phase>          # save rendered prompts per model/prompt

Every attempt writes an immutable raw file raw/<phase>/<run_id>__a<k>.jsonl and appends one
record to results/<phase>/attempts.jsonl. Resume skips run_ids that already have a non-error
attempt. Transport errors are retried as new attempts (max config.MAX_ATTEMPTS).
"""
import json, os, sys, time, random, hashlib, argparse, pathlib, urllib.request, subprocess, datetime
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
import config as C
from tokens import account

BENCH = ROOT / "benchmark" / "benchmark_v1.json"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def bench():
    blob = BENCH.read_bytes()
    return json.loads(blob), hashlib.sha256(blob).hexdigest()


def post_stream(ep, body, timeout=C.REQUEST_TIMEOUT_S):
    req = urllib.request.Request(f"{C.OLLAMA}/api/{ep}", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.perf_counter(); first = None; chunks = []
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for line in r:
            if not line.strip():
                continue
            if first is None:
                first = time.perf_counter() - t0
            chunks.append(json.loads(line))
    return chunks, time.perf_counter() - t0, first


def get_json(ep):
    with urllib.request.urlopen(f"{C.OLLAMA}/api/{ep}", timeout=30) as r:
        return json.loads(r.read())


def digests():
    out = {}
    for m in get_json("tags")["models"]:
        out.setdefault(m["name"], []).append(m["digest"])
    return out


def seed_for(task_id, variant_id, rep):
    return int(hashlib.sha256(f"{task_id}|{variant_id}|{rep}".encode()).hexdigest()[:8], 16) % 2_000_000_000


def build_request(w, prompt_text, seed, num_predict):
    opts = {**C.PAIR_OPTIONS[w["pair_id"]], "num_ctx": C.NUM_CTX, "num_predict": num_predict, "seed": seed}
    if w["api"] == "generate_raw":
        body = {"model": w["model_tag"], "prompt": C.llama_raw_prompt(prompt_text), "raw": True,
                "stream": True, "logprobs": True, "options": opts, "keep_alive": "30m"}
        return "generate", body
    body = {"model": w["model_tag"], "messages": [{"role": "user", "content": prompt_text}], "stream": True,
            "logprobs": True, "options": opts, "keep_alive": "30m"}
    if w["think"] is not None:
        body["think"] = w["think"]
    return "chat", body


def gpu_snapshot():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        u, m = [x.strip() for x in out.split(",")]
        return {"gpu_util_pct": int(u), "gpu_mem_mib": int(m)}
    except Exception as e:
        return {"error": str(e)}


# ---------------------------------------------------------------- schedule
def make_schedule(phase, task_ids=None, variants=None, reps=3, rng_seed=20261108):
    b, sha = bench()
    prompts = [p for p in b["prompts"] if (not task_ids or p["task_id"] in task_ids) and (not variants or p["variant_id"] in variants)]
    by_task = {}
    for p in prompts:
        by_task.setdefault(p["task_id"], []).append(p)
    rng = random.Random(rng_seed)
    pairs = sorted({w["pair_id"] for w in C.WORKERS})
    blocks = []
    for pair in pairs:
        ws = [w for w in C.WORKERS if w["pair_id"] == pair]
        tids = sorted(by_task); rng.shuffle(tids)
        for i, tid in enumerate(tids):
            order = ws if i % 2 == 0 else ws[::-1]   # balanced: half the tasks original-first
            for w in order:
                items = [(p, r) for p in by_task[tid] for r in range(1, reps + 1)]
                rng.shuffle(items)
                blocks.append({"pair_id": pair, "task_id": tid, "worker_id": w["worker_id"],
                               "runs": [{"run_id": f"{phase}__{w['worker_id']}__{p['prompt_id']}__r{r}",
                                         "prompt_id": p["prompt_id"], "repetition": r,
                                         "seed": seed_for(p["task_id"], p["variant_id"], r)} for p, r in items]})
    # interleave pairs: shuffle (pair, task) units, keeping each unit's two worker blocks adjacent
    units = {}
    for bl in blocks:
        units.setdefault((bl["pair_id"], bl["task_id"]), []).append(bl)
    keys = list(units); rng.shuffle(keys)
    ordered = [bl for k in keys for bl in units[k]]
    d = ROOT / "results" / phase; d.mkdir(parents=True, exist_ok=True)
    sched = {"phase": phase, "benchmark_sha256": sha, "created": now(), "rng_seed": rng_seed, "reps": reps,
             "n_runs": sum(len(b["runs"]) for b in ordered), "blocks": ordered}
    path = d / "schedule.json"
    if path.exists():
        old = json.loads(path.read_text())
        if [r["run_id"] for bl in old["blocks"] for r in bl["runs"]] != [r["run_id"] for bl in ordered for r in bl["runs"]]:
            sys.exit(f"refusing to overwrite a different existing schedule at {path}")
        print("schedule unchanged"); return
    path.write_text(json.dumps(sched, indent=1))
    print(f"wrote {path}: {sched['n_runs']} runs in {len(ordered)} blocks")


# ---------------------------------------------------------------- run
def load_done(att_path):
    done, attempts = set(), {}
    if att_path.exists():
        for line in att_path.read_text().splitlines():
            if not line.strip():
                continue
            a = json.loads(line)
            attempts[a["run_id"]] = max(attempts.get(a["run_id"], 0), a["attempt"])
            if not a.get("transport_error"):
                done.add(a["run_id"])
    return done, attempts


def append(path, rec):
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush(); os.fsync(f.fileno())


def unload_others(keep_tag):
    """Pilot finding: with OLLAMA_MAX_LOADED_MODELS=3 a newly loaded model could be partly offloaded
    to CPU (4.1/6.8 GB in VRAM, 11 tok/s instead of 227). Unload everything else before switching."""
    for m in get_json("ps")["models"]:
        if m["name"] != keep_tag and m["model"] != keep_tag:
            req = urllib.request.Request(f"{C.OLLAMA}/api/generate", json.dumps({"model": m["name"], "keep_alive": 0}).encode(),
                                         {"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=120).read()
    for _ in range(60):
        if all(m["name"] == keep_tag or m["model"] == keep_tag for m in get_json("ps")["models"]):
            return
        time.sleep(1)


def residency(tag):
    ps = [m for m in get_json("ps")["models"] if m["name"] == tag or m["model"] == tag]
    if not ps:
        return None
    return ps[0].get("size_vram", 0) >= ps[0].get("size", 1)


def warmup(w, log_path):
    """Unload other models, load this one, verify full GPU residency, record load time separately."""
    unload_others(w["model_tag"])
    ep, body = build_request(w, "Hi", 0, 1)
    t0 = time.perf_counter()
    chunks, wall, _ = post_stream(ep, body)
    fin = chunks[-1]
    ps = [m for m in get_json("ps")["models"] if m["name"] == w["model_tag"] or m["model"] == w["model_tag"]]
    rec = {"ts": now(), "worker_id": w["worker_id"], "model_tag": w["model_tag"], "wall_s": wall,
           "load_duration_s": fin.get("load_duration", 0) / 1e9, "ps": ps,
           "fully_on_gpu": bool(ps) and ps[0].get("size_vram", 0) >= ps[0].get("size", 1),
           "loaded_models": [m["name"] for m in get_json("ps")["models"]], **gpu_snapshot()}
    append(log_path, rec)
    return rec


def run(phase, limit=None, num_predict=None):
    num_predict = num_predict or C.NUM_PREDICT
    b, sha = bench()
    P = {p["prompt_id"]: p for p in b["prompts"]}
    d = ROOT / "results" / phase
    sched = json.loads((d / "schedule.json").read_text())
    if sched["benchmark_sha256"] != sha:
        sys.exit("benchmark checksum differs from schedule; refusing to run")
    W = {w["worker_id"]: w for w in C.WORKERS}
    dig = digests()
    for w in C.WORKERS:
        got = dig.get(w["model_tag"], [])
        if not any(g.startswith(C.EXPECTED_DIGESTS[w["model_tag"]]) for g in got):
            sys.exit(f"digest mismatch for {w['model_tag']}: {got}")
    rawd = ROOT / "raw" / phase; rawd.mkdir(parents=True, exist_ok=True)
    att_path = d / "attempts.jsonl"; load_log = d / "load_log.jsonl"
    done, attempts = load_done(att_path)
    n_new = 0; current = None
    for bl in sched["blocks"]:
        w = W[bl["worker_id"]]
        todo = [r for r in bl["runs"] if r["run_id"] not in done and attempts.get(r["run_id"], 0) < C.MAX_ATTEMPTS]
        if not todo:
            continue
        if current != w["model_tag"] or residency(w["model_tag"]) is not True:
            warm = None
            for _try in range(3):
                try:
                    warm = warmup(w, load_log)
                except Exception as e:
                    append(load_log, {"ts": now(), "worker_id": w["worker_id"], "warmup_error": repr(e)})
                    continue
                if warm["fully_on_gpu"]:
                    break
                time.sleep(10)
            current = w["model_tag"]
        for r in todo:
            if limit is not None and n_new >= limit:
                print("limit reached"); return
            p = P[r["prompt_id"]]
            k = attempts.get(r["run_id"], 0) + 1
            ep, body = build_request(w, p["prompt_text"], r["seed"], num_predict)
            raw_path = rawd / f"{r['run_id'].replace('/', '_')}__a{k}.jsonl"
            rec = {"run_id": r["run_id"], "attempt": k, "phase": phase, "ts_start": now(),
                   "pair_id": w["pair_id"], "worker_id": w["worker_id"], "condition": w["condition"],
                   "model_tag": w["model_tag"], "model_digest": next(g for g in dig[w["model_tag"]] if g.startswith(C.EXPECTED_DIGESTS[w["model_tag"]])),
                   "task_id": p["task_id"], "category": p["category"], "variant_id": p["variant_id"],
                   "prompt_id": p["prompt_id"], "repetition": r["repetition"], "seed": r["seed"],
                   "prompt_text": p["prompt_text"], "system_prompt": C.SYSTEM_PROMPT, "api": ep,
                   "inference_settings": {k2: v for k2, v in body.items() if k2 not in ("messages", "prompt")},
                   "benchmark_sha256": sha, "raw_response_path": str(raw_path.relative_to(ROOT)),
                   "gpu_before": gpu_snapshot(), "model_switch_warmup": warm if r is todo[0] else None}
            rec["fully_on_gpu_before"] = residency(w["model_tag"])
            try:
                chunks, wall, ttft = post_stream(ep, body)
            except Exception as e:
                rec.update(transport_error=repr(e), error=True, ts_end=now())
                append(att_path, rec); attempts[r["run_id"]] = k
                print("ERR", r["run_id"], repr(e)); time.sleep(5); continue
            with open(raw_path, "x") as f:
                for c in chunks:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")
            os.chmod(raw_path, 0o444)
            fin = chunks[-1]
            key = "response" if ep == "generate" else None
            thinking = "".join((c.get("message") or {}).get("thinking", "") or c.get("thinking", "") for c in chunks)
            content = "".join((c.get(key, "") if key else (c.get("message") or {}).get("content", "")) for c in chunks)
            entries = [e for c in chunks for e in (c.get("logprobs") or [])]
            acc = account(w["family"], bool(w["think"]), entries, fin, thinking, content)
            rt, at = acc["reasoning_tokens"], acc["answer_tokens"]
            ev_s = fin.get("eval_duration", 0) / 1e9
            rec.update(
                ts_end=now(), transport_error=None, error=bool(fin.get("error")), runtime_error=fin.get("error"),
                done_reason=fin.get("done_reason"), truncated=fin.get("done_reason") == "length",
                input_tokens=fin.get("prompt_eval_count"), input_tokens_cached=fin.get("prompt_eval_cached_count"),
                total_generated_tokens=fin.get("eval_count"),
                reasoning_tokens=rt, answer_tokens=at,
                reasoning_share=(rt / (rt + at)) if (rt is not None and at is not None and rt + at > 0) else None,
                reasoning_status=acc["reasoning_status"], token_count_method=acc["token_count_method"],
                token_confidence=acc["confidence"],
                special_token_accounting={"control_tokens": acc["control_tokens"], "control_token_list": acc["control_token_list"],
                                          "excluded_from_reasoning_share": True, "stop_token_in_eval_count": acc["stop_token_counted"]},
                token_reconciliation={k2: acc.get(k2) for k2 in ("n_logprob_tokens", "eval_count", "reconciled", "boundary_notes",
                                                                 "reasoning_text_matches", "answer_text_matches")},
                answer_text=content, reasoning_text_chars=len(thinking), answer_chars=len(content),
                answer_words=len(content.split()),
                latency_wall_s=wall, ttft_s=ttft, load_time_s=fin.get("load_duration", 0) / 1e9,
                prompt_eval_s=fin.get("prompt_eval_duration", 0) / 1e9, eval_s=ev_s,
                total_duration_s=fin.get("total_duration", 0) / 1e9,
                throughput_tok_s=(fin.get("eval_count", 0) / ev_s) if ev_s else None,
                gpu_after=gpu_snapshot(), fully_on_gpu_after=residency(w["model_tag"]),
            )
            rec["latency_valid"] = bool(rec["fully_on_gpu_before"]) and bool(rec["fully_on_gpu_after"])
            append(att_path, rec); done.add(r["run_id"]); n_new += 1
            print(f"{r['run_id']} gen={rec['total_generated_tokens']} r={rt} a={at} {acc['confidence']} "
                  f"{rec['done_reason']} {wall:.1f}s", flush=True)
    print("phase complete:", phase, "new attempts:", n_new)


def render(phase):
    b, _ = bench()
    d = ROOT / "results" / phase; d.mkdir(parents=True, exist_ok=True)
    out = d / "rendered_prompts.jsonl"
    with open(out, "w") as f:
        for w in C.WORKERS:
            for p in b["prompts"]:
                if w["api"] == "generate_raw":
                    rendered, how = "<|begin_of_text|>" + C.llama_raw_prompt(p["prompt_text"]), "client_raw_string (BOS added by runtime)"
                else:
                    body = {"model": w["model_tag"], "messages": [{"role": "user", "content": p["prompt_text"]}],
                            "stream": False, "_debug_render_only": True}
                    if w["think"] is not None:
                        body["think"] = w["think"]
                    req = urllib.request.Request(f"{C.OLLAMA}/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
                    rendered = json.loads(urllib.request.urlopen(req, timeout=120).read())["_debug_info"]["rendered_template"]
                    how = "ollama _debug_render_only"
                f.write(json.dumps({"worker_id": w["worker_id"], "model_tag": w["model_tag"], "prompt_id": p["prompt_id"],
                                    "rendered_prompt": rendered, "method": how}, ensure_ascii=False) + "\n")
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd"); ap.add_argument("phase")
    ap.add_argument("--tasks"); ap.add_argument("--variants"); ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--limit", type=int); ap.add_argument("--num-predict", type=int)
    a = ap.parse_args()
    if a.cmd == "schedule":
        make_schedule(a.phase, a.tasks.split(",") if a.tasks else None, a.variants.split(",") if a.variants else None, a.reps)
    elif a.cmd == "run":
        run(a.phase, a.limit, a.num_predict)
    elif a.cmd == "render":
        render(a.phase)
