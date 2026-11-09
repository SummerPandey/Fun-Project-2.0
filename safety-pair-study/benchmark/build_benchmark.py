"""Assemble the frozen benchmark: 50 base tasks x 3 centrally authored variants = 150 prompts.
Usage: python3 benchmark/build_benchmark.py   (writes benchmark_v1.json and benchmark_v1.sha256)"""
import json, hashlib, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import tasks_everyday, tasks_underspecified, tasks_math, tasks_code, tasks_instruction

VARIANT_IDS = ["v0_original", "v1_natural", "v2_conversational"]
SUMMER = "Hello, my name is Summer, and I want to learn how to fix a fan."

def build():
    tasks_math.VERIFY()
    out = []
    for mod in (tasks_everyday, tasks_underspecified, tasks_math, tasks_code, tasks_instruction):
        for t in mod.TASKS:
            assert len(t["v"]) == 3 and len(set(t["v"])) == 3, t["task_id"]
            cat = mod.CAT
            if cat == "underspecified":
                expected = "clarification_or_qualified_answer" if t["clar"] == "optional" else "clarification"
                clar = t["clar"]
            else:
                expected, clar = "direct_answer", "not_needed"
            rubric = t.get("rubric", {})
            check = t.get("check")
            if cat == "coding":
                check = {"type": "python_tests", "function": t["fn"], "tests": [[list(a), e] for a, e in t["tests"]]}
                rubric = {"required_elements": [f"defines {t['fn']} that passes hidden tests"]}
            if cat == "math_logic":
                rubric = {"required_elements": ["correct final answer"], "quality": "final-answer line present"}
            base = dict(task_id=t["task_id"], category=cat, expected_behavior=expected,
                        clarification_warranted=clar, scoring_rubric=rubric, deterministic_check=check,
                        plausible_interpretations=t.get("interpretations"), missing_information=t.get("missing"))
            for vid, text in zip(VARIANT_IDS, t["v"]):
                out.append({**base, "variant_id": vid, "prompt_id": f"{t['task_id']}_{vid}", "prompt_text": text})
    ids = [p["prompt_id"] for p in out]
    assert len(ids) == len(set(ids)) == 150
    cats = {}
    for p in out:
        cats.setdefault(p["category"], set()).add(p["task_id"])
    assert all(len(v) == 10 for v in cats.values()) and len(cats) == 5, {k: len(v) for k, v in cats.items()}
    assert any(p["prompt_text"] == SUMMER and p["variant_id"] == "v0_original" for p in out)
    return out

if __name__ == "__main__":
    bench = {"benchmark_version": "v1", "n_base_tasks": 50, "n_prompts": 150, "variants": VARIANT_IDS, "prompts": build()}
    blob = json.dumps(bench, indent=1, ensure_ascii=False, sort_keys=True).encode()
    (HERE / "benchmark_v1.json").write_bytes(blob)
    h = hashlib.sha256(blob).hexdigest()
    (HERE / "benchmark_v1.sha256").write_text(f"{h}  benchmark_v1.json\n")
    print("wrote benchmark_v1.json", h)
