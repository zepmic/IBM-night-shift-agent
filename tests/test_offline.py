"""Offline checks that need no network: python tests/test_offline.py"""
import json, os, sys, pathlib, tempfile
KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "examples" / "pi"))
from agent import Config, parse_args, normalize_answer, trim_history, to_openai_tools
from arena import llm
from arena.client import ToolSpec
import run_pi

assert parse_args('{"a": 1}') == {"a": 1}
assert parse_args('```json\n{"a": 1}\n```') == {"a": 1}
assert parse_args(None) == {}
assert normalize_answer({'"token"': '"TOK-1"', "n": 2, "l": ['"a"', "b"]}) == {"token": "TOK-1", "n": 2, "l": ["a", "b"]}
assert normalize_answer('"2026-11-14T12:00:00Z"') == "2026-11-14T12:00:00Z" and normalize_answer('say "hi"') == 'say "hi"'
import agent as _agent
_paths = {"/AGENTS.md", "/ops/change_calendar.csv", "/fleet/a.csv", "/fleet/b.json"} | {f"/docs/agreements/x{i}.{'pdf' if i % 2 else 'md'}" for i in range(30)}
_tree = _agent.local_tree(_paths, "/")
assert "/ops/: change_calendar.csv" in _tree and "/docs/agreements/: 30 files (15 .md, 15 .pdf)" in _tree and "/: AGENTS.md" in _tree and len(_tree) < 500, _tree
assert _agent.local_tree(_paths, "/fleet/").splitlines()[1:] == ["/fleet/: a.csv, b.json"] and _agent.local_tree(_paths, "/nope") == "" and _agent.local_tree(None, "/") == ""
assert normalize_answer('["S-1"]') == ["S-1"] and normalize_answer("42") == 42 and normalize_answer("B7") == "B7"
msgs = [{"role": "tool", "content": "x" * 1000, "tool_call_id": str(i)} for i in range(8)]
t = trim_history(msgs, Config(keep_full_outputs=2, keep_small_chars=0))
assert len(trim_history(msgs, Config(keep_full_outputs=2))[0]["content"]) == 1000  # small outputs stay
assert len(t[0]["content"]) < 400 and len(t[-1]["content"]) == 1000
tl = to_openai_tools([ToolSpec(name="read", description="d", args={"path": "file", "page": "optional page"})])
assert tl[0]["function"]["parameters"]["required"] == ["path"]

# OpenRouter: chat/embeddings go through the OpenAI SDK, Jev through httpx. No request leaves the process.
saved = {k: os.environ.get(k) for k in ("OPENROUTER_BASE_URL", "OPENROUTER_API_KEY")}
real_client, real_jev_post = llm._client, llm.httpx.post
chat_kwargs, jev_urls, jev_bodies = [], [], []


class FakeMessage:
    def model_dump(self):
        return {"role": "assistant", "content": "ok", "tool_calls": None}


class FakeChoice:
    message, finish_reason = FakeMessage(), "stop"


class FakeCompletions:
    def create(self, **kw):  # stands in for the OpenAI SDK's chat.completions.create
        chat_kwargs.append(kw)
        return type("Resp", (), {"choices": [FakeChoice()], "usage": None})()


class FakeClient:
    chat = type("Chat", (), {"completions": FakeCompletions()})()


class FakeJevResponse:
    status_code = 200

    def json(self):
        return {"answers": {"q": {"noul": 0.5}}}


llm._clients.clear()
llm._client = lambda: FakeClient()
llm.httpx.post = lambda url, **kw: jev_urls.append(url) or jev_bodies.append(kw.get("json")) or FakeJevResponse()
try:
    os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
    os.environ.pop("OPENROUTER_BASE_URL", None)
    assert llm.base_url() == "https://openrouter.ai/api/v1"
    assert llm.jev_url() == "https://openrouter.ai/api/alpha/decisions"
    os.environ["OPENROUTER_BASE_URL"] = ""  # empty counts as unset
    assert llm.base_url() == "https://openrouter.ai/api/v1"
    for gw in ("http://arena-gateway:8080/openrouter/api/v1", "http://arena-gateway:8080/openrouter/api/v1/"):
        os.environ["OPENROUTER_BASE_URL"] = gw
        assert llm.base_url() == "http://arena-gateway:8080/openrouter/api/v1"
        assert llm.jev_url() == "http://arena-gateway:8080/openrouter/api/alpha/decisions"
    assert llm.chat([{"role": "user", "content": "hi"}])["content"] == "ok"
    assert llm.decide("text", {"q": llm.noul("yes?")}) == {"q": {"noul": 0.5}}
    assert jev_urls == [llm.jev_url()], jev_urls
    # The fixed model goes to the same provider order the gateway pins in the final; usage.cost is requested; Jev gets neither.
    extra = chat_kwargs[0]["extra_body"]
    assert extra["provider"] == {"order": llm.PROVIDER_ORDER, "only": llm.PROVIDER_ORDER, "allow_fallbacks": True}
    assert extra["usage"] == {"include": True}
    assert "provider" not in jev_bodies[0], jev_bodies[0]

    # Jev retries: a 402 with Retry-After (OpenRouter's in-flight budget) waits as told; a 402 without it is final.
    class Resp:
        def __init__(self, code, headers=None):
            self.status_code, self.headers, self.text = code, headers or {}, "x"

        def json(self):
            return {"answers": {"q": {"noul": 0.5}}}

    seq, sleeps, real_sleep = [Resp(402, {"retry-after": "7"}), Resp(429), Resp(200)], [], llm.time.sleep
    llm.httpx.post, llm.time.sleep = (lambda url, **kw: seq.pop(0)), sleeps.append
    try:
        assert llm._jev_post({})["answers"] == {"q": {"noul": 0.5}}
        assert sleeps == [7, 4], sleeps
        seq[:] = [Resp(402)]
        try:
            llm._jev_post({})
            raise AssertionError("a 402 without Retry-After must not be retried")
        except llm.LLMError:
            assert sleeps == [7, 4] and not seq
    finally:
        llm.time.sleep = real_sleep
    # pi gets the same base URL through a per-run copy of pi-agent/models.json.
    committed = json.loads((KIT / "examples" / "pi" / "pi-agent" / "models.json").read_text())
    with tempfile.TemporaryDirectory() as d:
        cfg = json.loads((run_pi.agent_dir(pathlib.Path(d)) / "models.json").read_text())
        assert cfg["providers"]["openrouter"]["baseUrl"] == "http://arena-gateway:8080/openrouter/api/v1"
        os.environ.pop("OPENROUTER_BASE_URL")
        assert json.loads((run_pi.agent_dir(pathlib.Path(d)) / "models.json").read_text()) == committed
finally:
    llm._client, llm.httpx.post = real_client, real_jev_post
    llm._clients.clear()
    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

# The forced last submit is rejected (400, malformed sources): resubmit once without sources instead of losing the task.
import agent
from arena.client import ArenaError, Task


class _SubmitClient:
    def __init__(self):
        self.calls = []

    def submit(self, run_id, task_id, outcome, answer, sources):
        self.calls.append(sources)
        if sources:
            raise ArenaError("invalid request: sources.0.line: expected number", status=400)
        return {"received": True, "task_id": task_id}


assert agent.clean_sources([{"path": "/a.md", "line": "12"}, {"path": "/b.md", "line": "x", "page": 2.0}, {"line": 3}, "junk",
                            {"path": "/c.xlsx", "sheet": "S1", "row": 0, "record": 7}]) == [
    {"path": "/a.md", "line": 12}, {"path": "/b.md", "page": 2}, {"path": "/c.xlsx", "record": "7", "sheet": "S1"}]
assert agent.clean_sources(None) == [] and agent.clean_sources("x") == []

real_chat = agent.llm.chat
try:
    agent.llm.chat = lambda *a, **k: {"tool_calls": [{"id": "c1", "function": {"name": "submit", "arguments": json.dumps(
        {"outcome": "OK", "answer": ["B", "A"], "sources": [{"path": "/a.md", "line": "4"}]})}}]}
    sc = _SubmitClient()
    out = agent.solve_task(sc, "run_1", Task(task_id="t17", instruction="order"), [], Config(max_steps=1), llm.CostTracker())
    assert out == {"received": True, "task_id": "t17"} and sc.calls == [[{"path": "/a.md", "line": 4}], []], (out, sc.calls)
finally:
    agent.llm.chat = real_chat
print("offline tests ok")

# --- local helpers added after the dev runs: compact rendering, table filter, hash, preloaded rule files -------------
import hashlib
import sources as _S


class _Files:
    FILES = {"/AGENTS.md": "# Rules\nOperator files: /AGENTS.md and /runbook.md. See /fleet/changes.md and /contacts.csv.\n",
             "/runbook.md": "# Runbook\nrule 1\n", "/fleet/changes.md": "- ops-01 flagged\n",
             "/tickets/IR-1.md": "---\nticket: IR-1\nstatus: closed\n---\nold request\n",
             "/tickets/IR-2.md": "---\nticket: IR-2\nstatus: open\n---\nList the violations.\n",
             "/logs/req.csv": "request_id,ts,actor,action,ticket,result,n\nRQ-1,2026-11-14T01:00:00Z,external:x,read,,ok,5\n"
                              "RQ-2,2026-11-14T02:00:00Z,external:y,read,CHG-1,ok,12\nRQ-3,2026-11-14T03:00:00Z,ops-01,read,,ok,7\n"
                              "RQ-4,2026-11-14T04:00:00Z,external:z,read,,denied,30\nRQ-5,2026-11-14T05:00:00Z,external:z,reader,,ok,2\n"}

    def download_file(self, run_id, task_id, path):
        return self.FILES[path].encode(), "text/plain"


_fc, _ev = _Files(), _S.Evidence()
_out = _agent._filter_rows(_fc, "r", "t", {"path": "/logs/req.csv", "where": [
    {"column": "action", "op": "eq", "value": "read"}, {"column": "actor", "op": "startswith", "value": "external:"},
    {"column": "ticket", "op": "empty"}, {"column": "result", "op": "ne", "value": "denied"}]}, _ev, 8000)
assert _out.endswith('["RQ-1"]') and "1 of 5 rows match" in _out, _out
assert _ev.candidates(["RQ-1"], []) == [{"path": "/logs/req.csv", "record": "RQ-1"}]  # the hits are citable
_ids = lambda where: json.loads(_agent._filter_rows(_fc, "r", "t", {"path": "/logs/req.csv", "where": where}, _S.Evidence(), 8000).rsplit(": ", 1)[1])  # noqa: E731
assert _ids([{"column": "n", "op": "gt", "value": 7}]) == ["RQ-2", "RQ-4"]  # numbers compare as numbers, not text
assert _ids([{"column": "ts", "op": "ge", "value": "2026-11-14T04:00:00Z"}]) == ["RQ-4", "RQ-5"]
assert _ids({"column": "actor", "op": "in", "value": ["ops-01", "external:y"]}) == ["RQ-2", "RQ-3"]
assert "Columns: request_id" in _agent._filter_rows(_fc, "r", "t", {"path": "/logs/req.csv", "where": [{"column": "x", "op": "eq"}]}, _ev, 8000)
assert "5 of 5 rows shown" in _agent._filter_rows(_fc, "r", "t", {"path": "/logs/req.csv"}, _ev, 8000)
assert _agent._filter_rows(_fc, "r", "t", {"path": "/nope.csv"}, _ev, 8000).startswith("ERROR")
assert _agent._sha256({"values": ["abc"]}).endswith(hashlib.sha256(b"abc").hexdigest()) and _agent._sha256({}).startswith("ERROR")

_pre = _agent._preload(_fc, "r", "t", set(_Files.FILES))
assert [(p, l.split(" (")[0]) for p, l, _ in _pre] == [("/AGENTS.md", "OPERATOR FILE"), ("/runbook.md", "OPERATOR FILE"),
    ("/fleet/changes.md", "FILE NAMED IN THE RULES"), ("/tickets/IR-2.md", "OPEN TICKET")], _pre   # closed ticket: history, not sent
assert _pre[1][2] == "1| # Runbook\n2| rule 1" and _agent._preload(_fc, "r", "t", None) == [] and _agent._preload(_fc, "r", "t", {"/x.md"}) == []

_r = _agent.render({"total": 2, "events": [{"file": "/l.jsonl", "line": 3, "agent": "a", "detail": 'say "hi"\nnow'}, {"file": "/l.jsonl", "line": 9, "agent": "b"}]})
assert _r == 'total=2\nevents (file | line | agent | detail):\n/l.jsonl | 3 | a | say "hi" now\n/l.jsonl | 9 | b | ', _r
assert _agent.render({"path": "/a.md", "start_line": 1, "end_line": 2, "total_lines": 2, "text": '1| a "q"\n2| b'}) == '/a.md lines 1-2 of 2\n1| a "q"\n2| b'
assert _agent.render("tree") == "tree" and _agent.render({"found": False}) == '{"found": false}'
print("helper tests ok")
