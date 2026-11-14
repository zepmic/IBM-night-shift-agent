"""Score stored agent answers against the local case set (eval/collect.py), offline and for free.

    uv run python eval/score.py [--fallset runs/fallset.jsonl] [--answers answers.jsonl] [--run run_id] [--json]

Per task: score = constraints_ok ? answer · (0.7 + 0.3 · sources) : 0   (Task API, "Scoring").
Default answers: what the agent submitted in that run. `--answers` scores other answers for the same cases: one JSON
object per line, {"case_id": "<run_id>/<task_id>" (or "task_id"), "outcome", "answer", "sources"}.

This is an approximation of the platform's grader: partial credit for lists is F1, action tasks (expected_answer is
an action) and constraints cannot be judged locally and fall back to the platform's grade when there is one. The
`plat` column shows the platform's score for the original submission, to see how far the local grader is off.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

LOCATORS = ("page", "line", "record", "sheet", "row", "paragraph")
LINE_TOLERANCE = 2


def norm(v: Any) -> Any:
    """Scalars as the grader most likely compares them: numbers as floats, strings trimmed and case-folded."""
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        try:
            return float(s)
        except ValueError:
            return s.casefold()
    return v


def answer_score(exp: Any, got: Any) -> float | None:
    """1 = equal. Lists of scalars: F1 (order ignored). Objects: mean over the expected keys. None = cannot be
    judged locally (an action task)."""
    if isinstance(exp, dict):
        if "action" in exp:
            return None
        if not isinstance(got, dict):
            return 0.0
        if not exp:
            return 1.0
        parts = [answer_score(v, got.get(k)) for k, v in exp.items()]
        return None if any(p is None for p in parts) else sum(parts) / len(parts)
    if isinstance(exp, list):
        if not isinstance(got, list):
            got = [] if got is None else [got]
        if any(isinstance(x, (dict, list)) for x in exp + got):
            return float(json.dumps(exp, sort_keys=True) == json.dumps(got, sort_keys=True))
        e, g = {norm(x) for x in exp}, {norm(x) for x in got}
        if not e and not g:
            return 1.0
        tp = len(e & g)
        return 2 * tp / (len(e) + len(g)) if tp else 0.0
    return float(norm(exp) == norm(got))


def norm_path(p: Any) -> str:
    p = str(p or "").strip()
    return p if p.startswith("/") else "/" + p


def source_matches(exp: dict, got: dict) -> bool:
    """Same file, and every locator the expected source names agrees (line within ±2). A transfer may be cited in
    several ways (Task API); those alternatives only count where expected_sources lists them."""
    if not isinstance(got, dict) or norm_path(exp.get("path")) != norm_path(got.get("path")):
        return False
    for k in LOCATORS:
        if exp.get(k) is None:
            continue
        if got.get(k) is None:
            return False
        if k == "line":
            try:
                if abs(int(exp[k]) - int(got[k])) > LINE_TOLERANCE:
                    return False
            except (TypeError, ValueError):
                return False
        elif str(exp[k]).strip().casefold() != str(got[k]).strip().casefold():
            return False
    return True


def sources_score(expected: Any, got: Any) -> dict:
    """hit / expected. An expected entry that is a list is a group of alternatives: any one of them is a hit."""
    expected = expected if isinstance(expected, list) else []
    got = [g for g in got if isinstance(g, dict)] if isinstance(got, list) else []
    used: set[int] = set()
    hit = 0
    for e in expected:
        alts = [x for x in (e if isinstance(e, list) else [e]) if isinstance(x, dict)]
        idx = [i for i, g in enumerate(got) if any(source_matches(x, g) for x in alts)]
        if idx:
            hit += 1
            used.update(idx)
    return {"hit": hit, "expected": len(expected), "extra": len(got) - len(used),
            "score": hit / len(expected) if expected else 1.0}


def score_case(case: dict, sub: dict | None) -> dict:
    """Local grade of one submission ({outcome, answer, sources}) for one case. `sub` None = not submitted = 0."""
    grade = case.get("grade") if isinstance(case.get("grade"), dict) else {}
    own = sub is case.get("submission")  # the platform's grade only describes the original submission
    row = {"case_id": case["case_id"], "level": case.get("level"), "submitted": sub is not None,
           "outcome_ok": False, "answer": 0.0, "answer_local": True, "constraints_ok": True,
           "sources": 0.0, "hit": 0, "expected": len(case.get("expected_sources") or []), "extra": 0, "score": 0.0,
           "platform": grade.get("score") if own else None, "cost_usd": (case.get("trace") or {}).get("cost_usd")}
    if sub is None:
        return row
    src = sources_score(case.get("expected_sources"), sub.get("sources"))
    row.update(sources=src["score"], hit=src["hit"], expected=src["expected"], extra=src["extra"])
    exp_outcome = case.get("expected_outcome")
    row["outcome_ok"] = exp_outcome is None or sub.get("outcome") == exp_outcome
    if row["outcome_ok"]:
        # UNSUPPORTED: "the outcome alone counts"
        a = 1.0 if exp_outcome == "UNSUPPORTED" else answer_score(case.get("expected_answer"), sub.get("answer"))
        if a is None:  # action task: only the platform can judge it
            row["answer_local"] = False
            a = float(grade.get("answer_score") or 0.0) if own else 0.0
        row["answer"] = a
    if own and grade.get("constraints_ok") is False:
        row["constraints_ok"] = False
    row["score"] = row["answer"] * (0.7 + 0.3 * row["sources"]) if row["constraints_ok"] else 0.0
    return row


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def table(rows: list[dict]) -> str:
    w = max([len(r["case_id"]) for r in rows] + [4])
    out = [f"{'case':{w}}  lvl  outc  answer  sources      score   plat    cost", "-" * (w + 52)]
    for r in rows:
        ans = f"{r['answer']:.2f}" + (" " if r["answer_local"] else "*")
        src = f"{r['hit']}/{r['expected']}" + (f" +{r['extra']}" if r["extra"] else "")
        plat = "   -" if r["platform"] is None else f"{r['platform']:.2f}"
        cost = "      -" if r["cost_usd"] is None else f"{r['cost_usd']:.4f}"
        flag = "" if r["submitted"] else "  (not submitted)"
        flag += "" if r["constraints_ok"] else "  (constraints violated)"
        out.append(f"{r['case_id']:{w}}  {str(r['level'] or '-'):>3}  {'ok' if r['outcome_ok'] else 'x':>4}  {ans:>6}  "
                   f"{src:<10}  {r['score']:6.2f}  {plat:>5}  {cost}{flag}")
    return "\n".join(out)


def summary(rows: list[dict], cases: list[dict]) -> dict:
    n = len(rows) or 1
    plat = [r["platform"] for r in rows if r["platform"] is not None]
    costs = [r["cost_usd"] for r in rows if r["cost_usd"] is not None]
    run_costs = {c["run_id"]: c.get("run_cost_usd") for c in cases if c.get("run_cost_usd") is not None}
    return {"cases": len(rows), "score_sum": sum(r["score"] for r in rows), "accuracy": sum(r["score"] for r in rows) / n,
            "answer_mean": sum(r["answer"] for r in rows) / n, "sources_mean": sum(r["sources"] for r in rows) / n,
            "sources_hit": sum(r["hit"] for r in rows), "sources_expected": sum(r["expected"] for r in rows),
            "sources_extra": sum(r["extra"] for r in rows),
            "platform_accuracy": sum(plat) / len(plat) if plat else None,
            "trace_cost_usd": sum(costs) if costs else None, "run_cost_usd": sum(run_costs.values()) if run_costs else None}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--fallset", default="runs/fallset.jsonl")
    p.add_argument("--answers", help="jsonl with answers to score instead of the stored submissions")
    p.add_argument("--run", help="only cases of this run id")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    a = p.parse_args()
    path = Path(a.fallset)
    if not path.is_file():
        print(f"{path} not found: run eval/collect.py first", file=sys.stderr)
        return 1
    cases = [c for c in load_jsonl(path) if not a.run or c["run_id"] == a.run]
    if not cases:
        print("no cases", file=sys.stderr)
        return 1
    if a.answers:
        answers = load_jsonl(Path(a.answers))
        by_id = {x["case_id"]: x for x in answers if x.get("case_id")}
        by_task = {x["task_id"]: x for x in answers if x.get("task_id") and not x.get("case_id")}
        rows = [score_case(c, by_id.get(c["case_id"]) or by_task.get(c["task_id"])) for c in cases]
    else:
        rows = [score_case(c, c.get("submission")) for c in cases]
    s = summary(rows, cases)
    if a.json:
        print(json.dumps({"rows": rows, "summary": s}, ensure_ascii=False, indent=1))
        return 0
    print(table(rows))
    print(f"\n{s['cases']} cases · score sum {s['score_sum']:.2f} · accuracy {s['accuracy']:.3f} "
          f"(answer {s['answer_mean']:.3f}, sources {s['sources_mean']:.3f} = {s['sources_hit']}/{s['sources_expected']} hit, "
          f"{s['sources_extra']} extra)")
    if s["platform_accuracy"] is not None:
        print(f"platform accuracy on the graded cases: {s['platform_accuracy']:.3f}")
    fmt = lambda v: "n/a" if v is None else f"${v:.4f}"  # noqa: E731
    print(f"cost: traces {fmt(s['trace_cost_usd'])} · platform (whole runs) {fmt(s['run_cost_usd'])}")
    if any(not r["answer_local"] for r in rows):
        print("* action task: answer taken from the platform's grade (0 for --answers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
