"""Build a local case set from finished dev runs: runs/<run_id>/finish.json (expected answers, revealed once a dev
run has ended) + the per-task traces (what our agent submitted, cost, files touched).

    uv run python eval/collect.py [--runs runs] [--out runs/fallset.jsonl]

The case set holds dev answers, so it stays in runs/ (git-ignored). It is for scoring and debugging the harness
offline (eval/score.py); never feed it to the agent.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

EXPECTED = ("expected_outcome", "expected_answer", "expected_sources")


def read_trace(path: Path) -> dict:
    """What one task trace (<task>.jsonl) tells: the submission, cost, tool calls, files touched."""
    out: dict = {"submission": None, "response": None, "fallback": None, "tool_calls": 0, "llm_calls": 0,
                 "cost_usd": None, "paths": [], "error": None}
    if not path.is_file():
        return out
    paths: list[str] = []
    for line in path.read_text().splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        ev = e.get("event")
        if ev == "assistant":
            out["llm_calls"] += 1
        elif ev in ("tool", "view_image", "download_file"):
            out["tool_calls"] += 1
            p = (e.get("args") or {}).get("path")
            if isinstance(p, str) and p not in paths:
                paths.append(p)
        elif ev == "submit":
            a = e.get("args") or {}
            out["submission"] = {"outcome": a.get("outcome"), "answer": a.get("answer"), "sources": a.get("sources") or []}
            out["response"], out["fallback"] = e.get("response"), e.get("fallback")
        elif ev == "end":
            out["cost_usd"] = e.get("cost_usd")
        elif ev in ("llm_error", "crash"):
            out["error"] = e.get("error")
    out["paths"] = paths
    return out


def collect(runs_dir: Path) -> list[dict]:
    cases = []
    for fin_path in sorted(runs_dir.glob("*/finish.json")):
        try:
            fin = json.loads(fin_path.read_text())
        except json.JSONDecodeError:
            print(f"skip {fin_path}: not JSON", file=sys.stderr)
            continue
        run_id = fin.get("run_id") or fin_path.parent.name
        tasks = fin.get("tasks") if isinstance(fin, dict) else None
        for t in tasks or []:
            if not isinstance(t, dict) or not any(k in t for k in EXPECTED):
                continue  # no reveal (final run, or the run had not ended)
            tr = read_trace(fin_path.parent / f"{t.get('task_id')}.jsonl")
            grade = t.get("grade") if isinstance(t.get("grade"), dict) else tr["response"] if isinstance(tr["response"], dict) else None
            cases.append({
                "case_id": f"{run_id}/{t.get('task_id')}", "run_id": run_id, "task_id": t.get("task_id"),
                "seed": fin.get("seed"), "variation": fin.get("variation"), "level": t.get("level"),
                "instruction": t.get("instruction"),
                **{k: t.get(k) for k in EXPECTED},
                "submission": t.get("submission") or tr["submission"],  # the platform's record wins over our trace
                "grade": grade, "run_cost_usd": fin.get("cost_usd"),
                "trace": {k: tr[k] for k in ("tool_calls", "llm_calls", "cost_usd", "paths", "fallback", "error")},
            })
    return cases


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--runs", default="runs", help="directory with <run_id>/finish.json and traces")
    p.add_argument("--out", default=None, help="default: <runs>/fallset.jsonl")
    a = p.parse_args()
    runs = Path(a.runs)
    cases = collect(runs)
    out = Path(a.out) if a.out else runs / "fallset.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in cases))
    n_runs = len({c["run_id"] for c in cases})
    print(f"{len(cases)} cases from {n_runs} run(s) -> {out}")
    if not cases:
        print("no finish.json with expected answers found (dev runs reveal them once the run has ended)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
