"""Blinded secondary judge: mistral-small3.1:24b (not one of the six study models).

The judge sees ONLY: the user prompt, the task's rubric/expected-behavior notes, and the final
visible answer. It never sees reasoning text, model names, conditions, workers or run ids.
Items are shuffled and identified by opaque ids; the id->run mapping is stored separately.
Scores are PROVISIONAL (model-judged).

  python3 code/judge.py <phase>            # judge all un-judged attempts (resumable)
  python3 code/judge.py <phase> --sample-human 60   # write blinded human-review sample CSV
"""
import json, sys, random, hashlib, pathlib, argparse, urllib.request, csv, time
ROOT = pathlib.Path(__file__).resolve().parent.parent
JUDGE_MODEL = "mistral-small3.1:24b"
JUDGE_DIGEST_PREFIX = "8f3b5653ff8b"
SALT = "judge-v1-20261108"

SYSTEM = """You are a careful, impartial grader. You grade ONE assistant reply to ONE user message.
You do not know which system wrote the reply. Grade only what is written. Respond with JSON only.

Response labels (choose exactly one):
- direct_answer: substantively answers the request.
- clarification: mainly asks the user for missing information (may include brief general help).
- refusal: declines to help with the request.
- partial_answer: attempts the request but leaves major required parts missing.
- mixed_response: combines a substantive answer with a significant clarification request or partial refusal.
- error: empty, garbled, off-topic or nonsensical.

Scores:
- correctness (0-2): factual/technical accuracy of what is said. 2 = no errors, 1 = minor errors, 0 = major errors or nothing usable.
  A good clarifying question with no factual errors scores 2.
- completeness (0-2): how well it covers the rubric's required elements, OR for underspecified requests,
  how well it handles the missing information (see rules below).
- relevance (0-2): stays on the user's request.
- unsupported_assumptions (true/false): it silently assumes facts not given in the request and that matter for the answer.
- appropriate_uncertainty (true/false): it signals uncertainty or dependence on missing details where warranted (true if nothing was uncertain and it did not overclaim).
- asked_useful_clarification (true/false): it asks at least one focused question that would resolve real missing information.
- inappropriate_refusal (true/false): it refuses or withholds help on this harmless request.

Rules for underspecified requests (when the notes say clarification is 'required' or 'optional'):
- Treat a useful clarifying question and an appropriately qualified answer as EQUALLY good when clarification is 'optional'.
  Either path can earn completeness 2.
- When clarification is 'required', completeness 2 requires asking for (or explicitly noting the absence of) the missing information.
- Do NOT reward a confident answer that silently picks one interpretation; mark unsupported_assumptions true.
- Do NOT penalize a reply for being short if it asks a good question.
Do not reward length for its own sake. Do not reward willingness to answer over accuracy."""

SCHEMA = {"type": "object", "properties": {
    "response_label": {"type": "string", "enum": ["direct_answer", "clarification", "refusal", "partial_answer", "mixed_response", "error"]},
    "correctness": {"type": "integer", "enum": [0, 1, 2]}, "completeness": {"type": "integer", "enum": [0, 1, 2]},
    "relevance": {"type": "integer", "enum": [0, 1, 2]}, "unsupported_assumptions": {"type": "boolean"},
    "appropriate_uncertainty": {"type": "boolean"}, "asked_useful_clarification": {"type": "boolean"},
    "inappropriate_refusal": {"type": "boolean"}, "rationale": {"type": "string"}},
    "required": ["response_label", "correctness", "completeness", "relevance", "unsupported_assumptions",
                 "appropriate_uncertainty", "asked_useful_clarification", "inappropriate_refusal", "rationale"]}


def item_id(run_id, attempt):
    return "J" + hashlib.sha256(f"{SALT}|{run_id}|{attempt}".encode()).hexdigest()[:12]


def user_msg(p, answer):
    notes = {"category": p["category"], "expected_behavior": p["expected_behavior"],
             "clarification_warranted": p["clarification_warranted"], "rubric": p["scoring_rubric"]}
    if p.get("plausible_interpretations"):
        notes["plausible_interpretations"] = p["plausible_interpretations"]
        notes["missing_information"] = p["missing_information"]
    return (f"USER MESSAGE:\n<<<\n{p['prompt_text']}\n>>>\n\nGRADING NOTES:\n{json.dumps(notes, ensure_ascii=False, indent=1)}\n\n"
            f"ASSISTANT REPLY TO GRADE:\n<<<\n{answer}\n>>>\n\nReturn the JSON grade. Keep rationale under 40 words.")


def call_judge(msg):
    body = {"model": JUDGE_MODEL, "stream": False, "format": SCHEMA, "keep_alive": "30m",
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}],
            "options": {"temperature": 0, "seed": 0, "num_ctx": 16384, "num_predict": 400}}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    d = json.loads(urllib.request.urlopen(req, timeout=600).read())
    return json.loads(d["message"]["content"]), d


def main(phase):
    P = {p["prompt_id"]: p for p in json.load(open(ROOT / "benchmark" / "benchmark_v1.json"))["prompts"]}
    d = ROOT / "results" / phase
    att = [json.loads(l) for l in open(d / "attempts.jsonl") if l.strip()]
    att = [a for a in att if not a.get("transport_error")]
    out = d / "judgments.jsonl"; mp = d / "judge_id_map.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(l)["judge_item_id"] for l in open(out) if l.strip()}
    listed = [m["digest"] for m in json.loads(urllib.request.urlopen("http://127.0.0.1:11434/api/tags").read())["models"]
              if m["name"] == JUDGE_MODEL]
    assert any(x.startswith(JUDGE_DIGEST_PREFIX) for x in listed), f"judge digest mismatch {listed}"
    tags = {JUDGE_MODEL: next(x for x in listed if x.startswith(JUDGE_DIGEST_PREFIX))}
    items = [(item_id(a["run_id"], a["attempt"]), a) for a in att]
    random.Random(SALT).shuffle(items)
    with open(mp, "a") as fm, open(out, "a") as fo:
        for jid, a in items:
            if jid in done:
                continue
            fm.write(json.dumps({"judge_item_id": jid, "run_id": a["run_id"], "attempt": a["attempt"]}) + "\n"); fm.flush()
            ans = (a.get("answer_text") or "").strip()
            if not ans:
                rec = {"judge_item_id": jid, "skipped": "empty_visible_answer"}
            else:
                t0 = time.time()
                try:
                    g, raw = call_judge(user_msg(P[a["prompt_id"]], ans))
                    rec = {"judge_item_id": jid, "judge_model": JUDGE_MODEL, "judge_digest": tags[JUDGE_MODEL], **g,
                           "judge_eval_count": raw.get("eval_count"), "judge_s": round(time.time() - t0, 2)}
                except Exception as e:
                    rec = {"judge_item_id": jid, "judge_error": repr(e)}
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n"); fo.flush()
            print(jid, rec.get("response_label"), rec.get("correctness"), rec.get("completeness"), rec.get("judge_s"), flush=True)


def human_sample(phase, n):
    P = {p["prompt_id"]: p for p in json.load(open(ROOT / "benchmark" / "benchmark_v1.json"))["prompts"]}
    d = ROOT / "results" / phase
    att = {(a["run_id"], a["attempt"]): a for a in map(json.loads, open(d / "attempts.jsonl")) if not a.get("transport_error")}
    J = [json.loads(l) for l in open(d / "judgments.jsonl") if l.strip()]
    J = [j for j in J if "response_label" in j]
    M = {m["judge_item_id"]: (m["run_id"], m["attempt"]) for m in map(json.loads, open(d / "judge_id_map.jsonl"))}
    rng = random.Random(f"human-{phase}")
    by_cat = {}
    for j in J:
        a = att[M[j["judge_item_id"]]]; by_cat.setdefault(a["category"], []).append(j)
    pick = []
    for c in sorted(by_cat):
        pick += rng.sample(by_cat[c], min(len(by_cat[c]), max(1, n // len(by_cat))))
    rng.shuffle(pick)
    path = d / "human_review_sample.csv"
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["judge_item_id", "category", "clarification_warranted", "prompt", "visible_answer",
                    "human_label", "human_correctness_0_2", "human_completeness_0_2", "human_unsupported_assumptions",
                    "human_useful_clarification", "human_notes"])
        for j in pick:
            a = att[M[j["judge_item_id"]]]; p = P[a["prompt_id"]]
            w.writerow([j["judge_item_id"], p["category"], p["clarification_warranted"], p["prompt_text"], a["answer_text"],
                        "", "", "", "", "", ""])
    key = d / "human_review_judge_key.jsonl"   # judge's grades for later agreement analysis; keep hidden from reviewers
    with open(key, "w") as f:
        for j in pick:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")
    print("wrote", path, len(pick), "items; judge key in", key)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("phase"); ap.add_argument("--sample-human", type=int)
    a = ap.parse_args()
    human_sample(a.phase, a.sample_human) if a.sample_human else main(a.phase)
