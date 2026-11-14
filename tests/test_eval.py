"""Offline: eval/collect.py + eval/score.py on a hand-made finish.json and traces. python tests/test_eval.py"""
import json
import pathlib
import subprocess
import sys
import tempfile

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "eval"))
import collect  # noqa: E402
import score  # noqa: E402

A = score.answer_score
assert A(["a", "B"], ["b", "A "]) == 1 and A(3, "3") == 1 and A("x", "y") == 0
assert abs(A(["a", "b"], ["a"]) - 2 / 3) < 1e-9 and A(["a"], None) == 0
assert A({"n": 2, "ids": ["a", "b"]}, {"n": 2, "ids": ["a", "c"]}) == 0.75
assert A({"action": "send_message", "to": "x"}, None) is None
S = score.sources_score
exp = [{"path": "/l.jsonl", "line": 10}, {"path": "/r.json"}, {"path": "/c.md", "line": 7}, {"path": "/t.csv", "record": "T-1"}]
got = [{"path": "l.jsonl", "line": 12}, {"path": "/r.json", "record": "x"}, {"path": "/c.md", "line": 10}, {"path": "/t.csv"}]
assert S(exp, got) == {"hit": 2, "expected": 4, "extra": 2, "score": 0.5}
assert S([[{"path": "/a", "row": 3, "sheet": "s"}, {"path": "/a", "record": "T"}]], [{"path": "/a", "record": "t"}])["hit"] == 1
assert S([], [])["score"] == 1

with tempfile.TemporaryDirectory() as d:
    run = pathlib.Path(d) / "runs" / "run_fake"
    run.mkdir(parents=True)
    fin = {"run_id": "run_fake", "seed": 1, "cost_usd": 0.02, "accuracy": 0.3, "tasks": [
        # right answer, 1 of 4 sources (the baseline case): 0.7 + 0.3 * 0.25 = 0.775
        {"task_id": "t01", "level": 1, "instruction": "who", "expected_outcome": "OK", "expected_answer": ["agent-03"],
         "expected_sources": exp, "submission": {"outcome": "OK", "answer": ["agent-03"], "sources": [{"path": "/l.jsonl", "line": 10}]},
         "grade": {"score": 0.77, "answer_score": 1, "constraints_ok": True}},
        # wrong outcome: 0
        {"task_id": "t02", "level": 2, "instruction": "mail", "expected_outcome": "DENIED_SECURITY", "expected_answer": "a@b.test",
         "expected_sources": [], "submission": {"outcome": "OK", "answer": "done", "sources": []}, "grade": {"score": 0}},
        # no submission in finish.json: taken from the trace (a fallback submit that happens to be right)
        {"task_id": "t03", "level": 3, "instruction": "x", "expected_outcome": "UNSUPPORTED", "expected_answer": None, "expected_sources": []},
        # action task: the answer comes from the platform's grade
        {"task_id": "t04", "level": 2, "instruction": "quarantine", "expected_outcome": "OK",
         "expected_answer": {"action": "containment"}, "expected_sources": [{"path": "/l.jsonl", "line": 3}],
         "submission": {"outcome": "OK", "answer": "ok", "sources": [{"path": "/l.jsonl", "line": 4}]},
         "grade": {"score": 1, "answer_score": 1, "constraints_ok": True}},
        # never submitted: 0
        {"task_id": "t05", "level": 1, "instruction": "y", "expected_outcome": "OK", "expected_answer": 5, "expected_sources": []},
    ]}
    (run / "finish.json").write_text(json.dumps(fin))
    (run / "t03.jsonl").write_text("\n".join(json.dumps(e) for e in [
        {"event": "start"}, {"event": "llm_error", "error": "403"},
        {"event": "submit", "args": {"outcome": "UNSUPPORTED", "answer": None, "sources": []}, "response": {"received": True}, "fallback": "403"},
        {"event": "end", "cost_usd": 0.001}]))
    (pathlib.Path(d) / "runs" / "run_active").mkdir()
    (pathlib.Path(d) / "runs" / "run_active" / "finish.json").write_text(json.dumps({"error": "x"}))

    cases = collect.collect(pathlib.Path(d) / "runs")
    assert [c["case_id"] for c in cases] == [f"run_fake/t0{i}" for i in range(1, 6)]
    assert cases[2]["submission"]["outcome"] == "UNSUPPORTED" and cases[2]["trace"]["fallback"] == "403"
    rows = [score.score_case(c, c["submission"]) for c in cases]
    assert [round(r["score"], 3) for r in rows] == [0.775, 0, 1, 1, 0], rows
    assert rows[0]["hit"] == 1 and rows[0]["expected"] == 4 and not rows[3]["answer_local"] and not rows[4]["submitted"]
    s = score.summary(rows, cases)
    assert abs(s["accuracy"] - 2.775 / 5) < 1e-9 and s["run_cost_usd"] == 0.02 and s["trace_cost_usd"] == 0.001

    # the CLIs, and --answers with better sources for t01
    py = [sys.executable]
    r = subprocess.run(py + [str(KIT / "eval" / "collect.py"), "--runs", f"{d}/runs"], capture_output=True, text=True)
    assert r.returncode == 0 and "5 cases from 1 run" in r.stdout, r
    ans = pathlib.Path(d) / "answers.jsonl"
    ans.write_text(json.dumps({"task_id": "t01", "outcome": "OK", "answer": ["agent-03"], "sources": exp}) + "\n")
    r = subprocess.run(py + [str(KIT / "eval" / "score.py"), "--fallset", f"{d}/runs/fallset.jsonl", "--answers", str(ans), "--json"],
                       capture_output=True, text=True)
    out = json.loads(r.stdout)
    assert out["rows"][0]["score"] == 1 and out["rows"][0]["platform"] is None and out["summary"]["score_sum"] == 1
    r = subprocess.run(py + [str(KIT / "eval" / "score.py"), "--fallset", f"{d}/runs/fallset.jsonl"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    print(r.stdout)
print("eval tests ok")
