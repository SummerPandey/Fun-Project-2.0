"""Deterministic scoring. Code runs in a sandboxed subprocess (isolated interpreter, temp dir,
CPU/memory/file limits, 10 s wall timeout). Returns dict with det_pass (bool|None), det_fraction, details."""
import re, json, subprocess, tempfile, os, sys, pathlib, unicodedata

NUM = r"-?\d[\d,]*(?:\.\d+)?"


def _clean(s):
    return (s or "").replace("**", "").replace("`", "").strip()


def final_answer(text):
    """Returns (answer, format_ok). Requested format 'Final answer: X' first; fallbacks
    ('the final answer is X', last \\boxed{X}) count for correctness but not format compliance."""
    t = _clean(text)
    m = None
    for m in re.finditer(r"(?im)final answer\s*[:：]\s*(.+)$", t):
        pass
    if m:
        return m.group(1).strip(), True
    m = None
    for m in re.finditer(r"final answer\s*(?:is)?\s*[:：]?\s*(.+)", t, flags=re.I):
        pass
    if m:
        ans = m.group(1).strip()
        b = re.search(r"\\boxed\{([^{}]*)\}", ans)
        return (b.group(1) if b else ans), False
    bs = re.findall(r"\\boxed\{([^{}]*)\}", t)
    return (bs[-1], False) if bs else (None, False)


def _nums(s):
    out = []
    for x in re.findall(NUM, s or ""):
        try:
            out.append(float(x.replace(",", "")))
        except ValueError:
            pass
    return out


def _words(s):
    return re.findall(r"[A-Za-z0-9']+(?:[-'][A-Za-z0-9]+)*|\d[\d,.]*", s or "")


def _sentences(s):
    s = re.sub(r"\s+", " ", (s or "").strip())
    if not s:
        return []
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\"'(])", s)
    return [p for p in parts if p.strip()]


def _nonempty_lines(s):
    return [l for l in (s or "").strip().splitlines() if l.strip()]


def _has_any(text, alts):
    t = text.lower()
    return any(a.lower() in t for a in alts)


def run_python_tests(answer, fn, tests, timeout=10):
    blocks = re.findall(r"```(?:python|py|Python)?[ \t]*\n(.*?)```", answer or "", flags=re.S)
    cands = [b for b in blocks if re.search(rf"def\s+{re.escape(fn)}\s*\(", b)]
    if not cands:
        if re.search(rf"^def\s+{re.escape(fn)}\s*\(", answer or "", flags=re.M) and not blocks:
            cands = [answer]
        else:
            return {"det_pass": False, "det_fraction": 0.0, "details": {"reason": "no_code_block_defining_function", "n_blocks": len(blocks)}}
    code = cands[-1]
    harness = (
        "import json,sys,resource\n"
        "resource.setrlimit(resource.RLIMIT_AS,(1<<30,1<<30))\n"
        "resource.setrlimit(resource.RLIMIT_CPU,(5,5))\n"
        "resource.setrlimit(resource.RLIMIT_FSIZE,(1<<20,1<<20))\n"
        "ns={}\n"
        "try:\n    exec(compile(open('sol.py').read(),'sol.py','exec'),ns)\n"
        "except BaseException as e:\n    print(json.dumps({'load_error':repr(e)[:300]}));sys.exit(0)\n"
        f"tests=json.loads(open('tests.json').read());res=[]\n"
        "for args,exp in tests:\n"
        "    try:\n"
        f"        got=ns['{fn}'](*args)\n"
        "        if isinstance(exp,float) or isinstance(got,float):\n"
        "            ok=got is not None and exp is not None and abs(float(got)-float(exp))<1e-9\n"
        "        else:\n"
        "            ok=(got==exp) or (isinstance(got,tuple) and list(map(list,got))==exp)\n"
        "        res.append([bool(ok),repr(got)[:80]])\n"
        "    except BaseException as e:\n"
        "        res.append([False,'EXC '+repr(e)[:120]])\n"
        "print(json.dumps({'results':res}))\n")
    with tempfile.TemporaryDirectory(prefix="sbx_") as d:
        pathlib.Path(d, "sol.py").write_text(code)
        pathlib.Path(d, "tests.json").write_text(json.dumps(tests))
        pathlib.Path(d, "h.py").write_text(harness)
        try:
            p = subprocess.run([sys.executable, "-I", "-S", "h.py"], cwd=d, capture_output=True, text=True, timeout=timeout,
                               env={"PATH": "/usr/bin:/bin", "HOME": d})
            out = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {"crash": p.stderr[-300:]}
        except subprocess.TimeoutExpired:
            out = {"timeout": True}
        except Exception as e:
            out = {"harness_error": repr(e)}
    if "results" not in out:
        return {"det_pass": False, "det_fraction": 0.0, "details": out}
    ok = [r[0] for r in out["results"]]
    return {"det_pass": all(ok), "det_fraction": sum(ok) / len(ok), "details": {"results": out["results"]}}


def score(prompt, answer):
    chk = prompt.get("deterministic_check")
    if not chk:
        return {"det_pass": None, "det_fraction": None, "details": None}
    t = chk["type"]; a = answer or ""; ca = _clean(a)
    if t == "numeric":
        fa, fmt = final_answer(a)
        vals = _nums(fa) if fa else []
        ok = bool(vals) and abs(vals[0] - chk["answer"]) <= chk["tol"]
        return {"det_pass": ok, "det_fraction": float(ok), "format_ok": fmt, "details": {"final_answer": fa, "format_ok": fmt}}
    if t == "yesno":
        fa, fmt = final_answer(a)
        m = re.match(r"\W*(yes|no)\b", (fa or "").lower())
        ok = bool(m) and m.group(1) == chk["answer"]
        return {"det_pass": ok, "det_fraction": float(ok), "format_ok": fmt, "details": {"final_answer": fa, "format_ok": fmt}}
    if t == "numeric_any":
        vals = _nums(a)
        ok = any(abs(v - chk["target"]) <= chk["tolerance"] for v in vals)
        return {"det_pass": ok, "det_fraction": float(ok), "details": {"numbers_found": vals[:10]}}
    if t == "keywords_all_ci":
        base = all(k in ca.lower() for k in chk["keywords"]); bonus = _has_any(ca, chk.get("bonus_any", []))
        return {"det_pass": base, "det_fraction": (base + bonus) / 2, "details": {"primary": base, "second_sense": bonus},
                "supplementary_only": True}
    if t == "python_tests":
        return run_python_tests(a, chk["function"], chk["tests"])
    comps = {}
    lines = _nonempty_lines(ca)
    if t == "numbered_list_exact":
        comps["all_lines_numbered"] = bool(lines) and all(re.match(r"^\s*\d+[.)]\s+\S", l) for l in lines)
        comps["count_exact"] = len(lines) == chk["n"]
    elif t == "line_count_exact":
        comps["line_count_exact"] = len(lines) == chk["n"]
    elif t == "summary":
        comps["max_words"] = len(_words(ca)) <= chk["max_words"]
        comps["one_sentence"] = len(_sentences(ca)) <= chk["max_sentences"]
        for i, alts in enumerate(chk["required_facts"]):
            comps[f"fact_{i}"] = _has_any(ca, alts)
    elif t == "word_limit_keywords":
        comps["word_limit"] = len(_words(ca)) <= chk["max_words"]
        for i, alts in enumerate(chk["keywords_any_groups"]):
            comps[f"kw_{alts[0]}"] = _has_any(ca, alts)
    elif t == "json_exact":
        strict = lenient = False
        try:
            strict = json.loads(a.strip()) == chk["expected"]
        except Exception:
            pass
        m = re.search(r"\{.*\}", a, flags=re.S)
        try:
            lenient = m is not None and json.loads(m.group(0)) == chk["expected"]
        except Exception:
            pass
        comps["only_json_strict"] = strict; comps["json_content_correct"] = lenient
    elif t == "bullets_exact":
        bl = [l for l in lines if re.match(r"^\s*([-*•●▪–])\s+\S", l)]
        comps["bullets_exact"] = len(bl) == chk["n"]
        for i, alts in enumerate(chk["required_facts"]):
            comps[f"fact_{i}"] = _has_any(ca, alts)
    elif t == "lipogram":
        comps["no_letter"] = bool(ca) and chk["letter"] not in ca.lower()
        comps["one_sentence"] = len(_sentences(ca)) == 1
    elif t == "sentence_count_exact":
        comps["sentence_count_exact"] = len(_sentences(ca)) == chk["n"]
        comps["keywords"] = all(k in ca.lower() for k in chk["keywords_all"])
    elif t == "rhyme_list":
        items = [x.strip() for x in ca.strip().rstrip(".").split(",")]
        comps["exactly_n_items"] = len(items) == chk["n"] and len(lines) == 1
        comps["lowercase_words"] = all(re.fullmatch(r"[a-z]+", x) for x in items)
        comps["rhymes_distinct"] = (len(set(items)) == len(items) and
                                    all(x.endswith(tuple(chk["suffixes"])) and x not in chk["exclude"] for x in items))
    else:
        raise ValueError(t)
    vals = list(comps.values())
    return {"det_pass": all(vals), "det_fraction": sum(vals) / len(vals), "details": comps}
