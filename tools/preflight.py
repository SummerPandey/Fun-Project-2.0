#!/usr/bin/env python3
"""Pre-run checklist. Run this FIRST on the machine that will run the pilot. Exit 0 = ready.

Checks: Python version and packages, Ollama server reachable, every model and the judge
pulled with the pinned digest, thinking capability as configured, pilot_prompts.json
next to pilot/, git remote and push access for the archivist, free disk space.

Usage:  python3 tools/preflight.py [--config pilot/config.json]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
results = []


def check(level_ok: bool, name: str, detail: str, warn_only: bool = False):
    level = "PASS" if level_ok else ("WARN" if warn_only else "FAIL")
    results.append(level)
    print(f"[{level}] {name}: {detail}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "pilot" / "config.json"))
    a = ap.parse_args()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))

    check(sys.version_info >= (3, 10), "python", sys.version.split()[0] + " (need 3.10+)")
    for mod, why, warn in (("matplotlib", "figures and dashboard", False),
                           ("datasets", "capability stage (GSM8K / MMLU download)", True)):
        ok = importlib.util.find_spec(mod) is not None
        check(ok, f"package {mod}", ("installed" if ok else f"missing: pip install {mod}") + f" - {why}", warn_only=warn)
    check((ROOT / "pilot_prompts.json").exists(), "prompts", str(ROOT / "pilot_prompts.json"))

    if cfg.get("backend") == "ollama":
        spec = importlib.util.spec_from_file_location("run_pilot", ROOT / "pilot" / "run_pilot.py")
        rp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rp)
        client = rp.OllamaClient(cfg["ollama"])
        try:
            v = client.version()
            check(True, "ollama server", f"{cfg['ollama']['host']} version {v}")
        except SystemExit as e:
            check(False, "ollama server", str(e))
            v = None
        if v:
            for m in cfg["models"] + [dict(cfg["judge"], name="judge", supports_thinking=None)]:
                try:
                    d = client.check_model(m["repo"], m.get("digest"), m.get("supports_thinking"))
                    pinned = bool(m.get("digest"))
                    check(pinned, f"model {m['name']}", f"{m['repo']} -> {d[:12]}"
                          + ("" if pinned else " (digest NOT pinned: copy it into config.json)"), warn_only=not pinned)
                except SystemExit as e:
                    check(False, f"model {m['name']}", str(e))

    git = shutil.which("git")
    if git and (ROOT / ".git").exists():
        remote = subprocess.run([git, "-C", str(ROOT), "remote", "get-url", "origin"], capture_output=True, text=True)
        check(remote.returncode == 0, "git remote", remote.stdout.strip() or remote.stderr.strip())
        dry = subprocess.run([git, "-C", str(ROOT), "push", "--dry-run", "origin", "HEAD"], capture_output=True, text=True)
        check(dry.returncode == 0, "git push access",
              "ok" if dry.returncode == 0 else (dry.stderr.strip().splitlines() or ["failed"])[-1]
              + " - run `gh auth login` (or set up a token) so the archivist can push", warn_only=True)
    else:
        check(False, "git", "not a git checkout: clone the repository instead of copying files", warn_only=True)

    free_gb = shutil.disk_usage(ROOT).free / 1e9
    check(free_gb > 2, "disk", f"{free_gb:.1f} GB free")

    fails = results.count("FAIL")
    print(f"\npreflight: {fails} FAIL, {results.count('WARN')} WARN -> " + ("READY" if not fails else "NOT READY"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
