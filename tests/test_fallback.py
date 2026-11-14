"""Offline: a task that fails (model error, crash, step limit, silent model) is still submitted exactly once.
python tests/test_fallback.py   — needs no keys and no network (mock Task API in a thread, main.py as a subprocess)."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "tests"))
import agent  # noqa: E402
import mock_server  # noqa: E402
from arena import llm  # noqa: E402
from arena.client import ArenaError, Task  # noqa: E402


class Client:
    """Records submits; `reject` = number of leading submits answered with a 400."""

    def __init__(self, reject=0, status=400):
        self.submits, self.tools, self.reject, self.status = [], [], reject, status

    def submit(self, run_id, task_id, outcome, answer, sources):
        self.submits.append((outcome, answer, sources))
        if len(self.submits) <= self.reject:
            raise ArenaError("rejected", status=self.status)
        return {"received": True, "task_id": task_id}

    def call_tool(self, run_id, task_id, name, args):
        self.tools.append(name)
        return {"ok": True, "result": "x"}


def run(chat, client, steps=3, deadline=None):
    real = agent.llm.chat
    agent.llm.chat = chat
    try:
        return agent.solve_task(client, "r", Task(task_id="t01", instruction="x"), [], agent.Config(max_steps=steps, deadline=deadline),
                                llm.CostTracker())
    finally:
        agent.llm.chat = real


def call(name, args):
    return {"content": "", "tool_calls": [{"id": "c", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def raises(exc):
    def chat(*a, **k):
        raise exc
    return chat


DEFAULT = [("UNSUPPORTED", None, [])]

# 1. model error / unexpected exception on the first call: safe default, exactly one submit, no tool call
for exc in (llm.LLMError("403 Key limit exceeded"), KeyError("boom")):
    c = Client()
    out = run(raises(exc), c)
    assert c.submits == DEFAULT and not c.tools and out["received"] and "fallback" in out, (out, c.submits)

# 2. model never calls a tool: one forced try, then the default
c = Client()
out = run(lambda *a, **k: {"content": "thinking"}, c, steps=25)
assert c.submits == DEFAULT, c.submits

# 3. step limit, and the forced last call is not a submit: default
c = Client()
out = run(lambda *a, **k: call("read", {"path": "/a"}), c, steps=2)
assert c.submits == DEFAULT and c.tools == ["read", "read"], (c.submits, c.tools)

# 4. the model's submit was rejected (400) and then the model dies: best interim state = that answer without sources
state = {"n": 0}


def chat4(*a, **k):
    state["n"] += 1
    if state["n"] > 1:
        raise llm.LLMError("down")
    return call("submit", {"outcome": "OK", "answer": ["a"], "sources": [{"path": "/a.md", "line": 3}]})


c = Client(reject=2)
out = run(chat4, c, steps=5)
assert c.submits == [("OK", ["a"], [{"path": "/a.md", "line": 3}])] * 2 + [("OK", ["a"], [])], c.submits
assert out["received"]

# 5. already submitted / deadline (409): no second attempt
c = Client(reject=9, status=409)
out = run(lambda *a, **k: call("submit", {"outcome": "OK", "answer": 1, "sources": []}), c)
assert len(c.submits) == 1 and "error" in out, (c.submits, out)

# 6. a normal submit is untouched
c = Client()
out = run(lambda *a, **k: call("submit", {"outcome": "OK", "answer": 1, "sources": []}), c)
assert c.submits == [("OK", 1, [])] and "fallback" not in out

# 6b. run deadline: just past it the model gets one forced submit; a minute later only the fallback, no model call
import time  # noqa: E402

c, seen = Client(), []
out = run(lambda *a, **k: seen.append(k.get("tool_choice")) or call("submit", {"outcome": "OK", "answer": 1, "sources": []}), c,
          steps=25, deadline=time.time() - 1)
assert c.submits == [("OK", 1, [])] and seen == [{"type": "function", "function": {"name": "submit"}}], (c.submits, seen)
c = Client()
out = run(raises(AssertionError("no model call after the deadline")), c, deadline=time.time() - 100)
assert c.submits == DEFAULT and "deadline" in out["fallback"], (c.submits, out)

# 7. end to end: main.py against the mock Task API without an OpenRouter key -> both mock tasks are submitted
srv = ThreadingHTTPServer(("127.0.0.1", 0), mock_server.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
env = {**os.environ, "ARENA_BASE_URL": f"http://127.0.0.1:{srv.server_address[1]}", "ARENA_API_KEY": "arena_test",
       "OPENROUTER_API_KEY": "", "OPENROUTER_BASE_URL": "http://127.0.0.1:9/api/v1", "ARENA_RUN_KIND": "dev"}
with tempfile.TemporaryDirectory() as d:
    r = subprocess.run([sys.executable, str(KIT / "main.py"), "--note", "fallback test"], cwd=d, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert set(mock_server.STATE["submitted"]) == {"t01", "t02"}, (mock_server.STATE, r.stdout)
    assert mock_server.STATE["tool_calls"] == 0, "the fallback must not call workspace tools"
    for t in ("t01", "t02"):
        ev = [json.loads(l) for l in (pathlib.Path(d) / "runs" / "mock" / f"{t}.jsonl").read_text().splitlines()]
        sub = [e for e in ev if e["event"] == "submit"]
        assert len(sub) == 1 and sub[0]["args"]["outcome"] == "UNSUPPORTED" and sub[0]["fallback"], sub
srv.shutdown()
print("fallback tests ok")
