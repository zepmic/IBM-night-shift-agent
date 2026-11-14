"""Offline: a submit rejected with 400 (e.g. a source without `path`) goes back to the model, which can fix it.
python tests/test_submit_retry.py"""
import json
import pathlib
import sys

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
import agent  # noqa: E402
from arena import llm  # noqa: E402
from arena.client import ArenaError, Task  # noqa: E402

submits = [
    {"outcome": "OK", "answer": ["a"], "sources": [{"path": "/a.csv", "record": "a"}, {"record": "b"}]},
    {"outcome": "OK", "answer": ["a"], "sources": [{"path": "/a.csv", "record": "a"}]},
]
seen: list[list] = []


def fake_chat(messages, **kw):
    i = len(seen)
    return {"content": "", "tool_calls": [{"id": f"c{i}", "type": "function",
            "function": {"name": "submit", "arguments": json.dumps(submits[min(i, 1)])}}]}


class FakeClient:
    def submit(self, run_id, task_id, outcome, answer, sources):
        seen.append(sources)
        if any("path" not in s for s in sources):
            raise ArenaError("POST /submit -> 400: invalid request: sources.1.path: Invalid input", status=400)
        return {"received": True, "task_id": task_id, "score": 1}


llm.chat = fake_chat
res = agent.solve_task(FakeClient(), "run_x", Task(task_id="t01", instruction="x"), [], agent.Config(max_steps=5),
                       llm.CostTracker())
assert res.get("received") is True, res
assert len(seen) == 2, seen
print("ok: a 400 on submit goes back to the model, the second submit lands")
