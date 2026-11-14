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
assert [(p, k) for p, k, _ in _pre] == [("/AGENTS.md", "rule"), ("/runbook.md", "rule"), ("/fleet/changes.md", "named"),
                                        ("/tickets/IR-2.md", "ticket")], _pre   # closed ticket: history, not sent
assert _pre[1][2] == "1| # Runbook\n2| rule 1" and _agent._preload(_fc, "r", "t", None) == [] and _agent._preload(_fc, "r", "t", {"/x.md"}) == []

_r = _agent.render({"total": 2, "events": [{"file": "/l.jsonl", "line": 3, "agent": "a", "detail": 'say "hi"\nnow'}, {"file": "/l.jsonl", "line": 9, "agent": "b"}]})
assert _r == 'total=2\nevents (file | line | agent | detail):\n/l.jsonl | 3 | a | say "hi" now\n/l.jsonl | 9 | b | ', _r
assert _agent.render({"path": "/a.md", "start_line": 1, "end_line": 2, "total_lines": 2, "text": '1| a "q"\n2| b'}) == '/a.md lines 1-2 of 2\n1| a "q"\n2| b'
assert _agent.render("tree") == "tree" and _agent.render({"found": False}) == '{"found": false}'
print("helper tests ok")

# --- spreadsheets in filter_rows (title rows above the header, numbers stored as text), long documents in parts ----
import io as _io
from openpyxl import Workbook as _Workbook

_wb = _Workbook()
_ws = _wb.active
_ws.title = "transfers"
for _row in (["Outbound transfer register"], [], ["tx_id", "agent_id", "target_host", "record_count", "status"],
             ["TX-1", "ops-01", "evil.example", "12", "ok"], ["TX-2", "ops-02", "partner.example", 0, "ok"],
             ["TX-3", "ops-01", "evil.example", 7, "blocked"]):
    _ws.append(_row)
_buf = _io.BytesIO()
_wb.save(_buf)
_Files.FILES["/security/x.xlsx"] = None


class _Bin(_Files):
    def download_file(self, run_id, task_id, path):
        return (_buf.getvalue(), "application/xlsx") if path.endswith(".xlsx") else super().download_file(run_id, task_id, path)


_ev2 = _S.Evidence()
_out = _agent._filter_rows(_Bin(), "r", "t", {"path": "/security/x.xlsx", "where": [
    {"column": "target_host", "op": "eq", "value": "evil.example"}, {"column": "record_count", "op": "gt", "value": 5}]}, _ev2, 8000)
assert "sheet 'transfers': 2 of 3 rows match" in _out and "[4, 6]" in _out and '["TX-1", "TX-3"]' in _out, _out
assert _ev2.candidates(["TX-3"], []) == [{"path": "/security/x.xlsx", "sheet": "transfers", "row": 6}]


class _Doc:
    def submit(self, *a):
        return {"received": True}


_long = "\n".join(f"{i}. paragraph {i} " + "x" * 80 for i in range(1, 200))
_real_dl, _seen = _agent._download_file, []
_agent._download_file = lambda *a, **k: _long
_steps = iter([("download_file", {"path": "/d.docx"}), ("download_file", {"path": "/d.docx", "part": 3}),
               ("download_file", {"path": "/d.docx", "part": 9}), ("submit", {"outcome": "OK", "answer": 1, "sources": []})])
_real_chat = _agent.llm.chat


def _chat(messages, **kw):
    _seen[:] = [m["content"] for m in messages if m.get("role") == "tool"]
    n, a = next(_steps)
    return {"content": "", "tool_calls": [{"id": "c", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}}]}


_agent.llm.chat = _chat
try:
    _agent.solve_task(_Doc(), "r", Task(task_id="t1", instruction="x"), [], Config(route=False), llm.CostTracker())
finally:
    _agent.llm.chat, _agent._download_file = _real_chat, _real_dl
assert _seen[0].startswith("[part 1 of 3; call download_file with part=2 for more]\n1. paragraph 1 ") and len(_seen[0]) < 8100
assert _seen[1].startswith("[part 3 of 3, the last]") and _seen[1].rstrip().endswith("x") and _seen[2].startswith("ERROR: this file has only 3 parts")
print("format tests ok")

# Scanned tickets: the status line decides; pictures embedded in text artifacts are found for vision
import base64 as _b64
import incident as _inc
assert _agent._image_ticket_open("[vision transcription of /tickets/a.jpg — x]\nstatus: open\nTicket IR-1 OPEN")
assert not _agent._image_ticket_open("[vision transcription of /tickets/a.jpg — x]\nstatus: closed\nTicket IR-1 CLOSED")
assert not _agent._image_ticket_open("Ticket IR-2\nStatus: CLOSED\nRequest: something open")
_png = b"\x89PNG" + b"x" * 300
_doc = '{"icon": "data:image/png;base64,' + _b64.b64encode(_png).decode() + '"}'
assert _inc.embedded_images(_doc) == [("image/png", _png)]
assert _inc.read_embedded(lambda p: _doc.encode(), "/a.json#img0") == ("image/png", _png)
assert _inc.read_embedded(lambda p: b"", "/a.json") is None
print("image tickets + embedded images ok")

# Counting rule: a runbook line that only names the question defers to the file it references
assert _inc._rule_flags("What the gateway stopped never left: leave blocked attempts out. Count each record id a single time across all transfers.") == (True, True)
assert _inc._rule_flags("Both successful and blocked transfers count; a record sent twice counts twice.") == (False, False)
print("rule flags ok")
assert _inc._rule_flags("Repeated records. Do not merge overlapping ranges or re-sends. Sum them. Blocked transfers. What the gateway stopped never left: leave blocked attempts out.") == (True, False)
print("rule flags 2 ok")

# Contract clause in force: signed, replaces the clause, effective by now; the latest wins
_files = {
    "/AGENTS.md": b'Current time ("now"): 2026-11-14T07:30:00Z (UTC).',
    "/docs/enterprise_accounts.csv": b"agreement_id,organisation,document\nAGR-1,Acme Labs,/docs/agreements/acme.md\n",
    "/docs/agreements/acme.md": b"# DPA\n\nAgreement reference AGR-1. Signed 2025-01-01 for Acme Labs by Ann Lee.\n\n12.1 In the event of a personal-data breach affecting Acme Labs, MuggingFace will notify Acme Labs within 72 hours of detection.\n",
    "/docs/agreements/acme_amendment_1.md": b'Clause 12.1 is replaced by:\n"12.1 In the event of a personal-data breach affecting Acme Labs, MuggingFace will notify Acme Labs\nwithin 24 hours of detection."\nEffective from 2026-01-01T00:00:00Z.\nSigned 2026-01-01 for Acme Labs by Ann Lee.\nSigned 2026-01-01 for MuggingFace by Bo Ng.\n',
    "/docs/agreements/acme_amendment_2.md": b'Clause 12.1 is replaced by:\n"12.1 In the event of a personal-data breach affecting Acme Labs, MuggingFace will notify Acme Labs within 120 hours of detection."\nEffective from 2026-12-01T00:00:00Z.\nSigned 2026-11-01 for Acme Labs by Ann Lee.\n',
    "/docs/agreements/acme_amendment_3.md": b'Prepared for review; not signed.\n"12.1 ... MuggingFace will notify Acme Labs of a personal-data breach within 12 hours of detection."\nSigned for Acme Labs: ________\n',
}
_a, _s, _e = _inc.agreement_terms(lambda p: _files[p], set(_files), "Which notification deadline is in force for Acme Labs right now?")
assert _a == {"agreement": "AGR-1", "notify_hours": 24, "signatory": "Ann Lee"}, _a
assert _s == [{"path": "/docs/enterprise_accounts.csv", "record": "AGR-1"}, {"path": "/docs/agreements/acme.md", "line": 3},
              {"path": "/docs/agreements/acme_amendment_1.md"}], _s
print("agreement terms ok")

# Event order: labels that carry their text are matched to the entry they describe (run_GXlstedXsIFN t40)
_tl = """TIMELINE, sorted earliest first (UTC). For an order-of-events question:
1. 2026-11-13T19:29:59Z approved transfer TX-70036 sent to verified partner audit.lindqvist-partners.example (/security/egress_export.csv record TX-70036; /logs/archive/2026-11-13.csv line 2893)
2. 2026-11-13T19:54:00Z change log: grant_scope analytics-16 read:metrics (dashboard refresh) took effect (/fleet/changes.md line 7)
3. 2026-11-13T20:46:37Z attack ENTRY artifact uploaded by external:hivemind-5-50: models/hivemind-5-50/benchmark-mirror-2026/README.md (/logs/archive/2026-11-13.csv line 3122)
4. 2026-11-14T00:14:54Z red-team canary artifact uploaded by redteam-01: models/redteam-01/prompt-hygiene-check/README.md (/logs/audit/2026-11-14.jsonl line 156)
5. 2026-11-14T03:10:16Z entry artifact models/hivemind-5-50/benchmark-mirror-2026/README.md first processed (read_artifact) by moderation-18 (/logs/audit/2026-11-14.jsonl line 1928; cite the copy /artifacts/q.md by path too)
7. 2026-11-14T03:17:27Z FIRST secret read within the attack: TOK-SUP-25 by devops-07 (/logs/audit/2026-11-14.jsonl line 1994)
11. 2026-11-14T04:37:27Z SIEM alert: AL-9190 | 2026-11-14T04:37:27Z | devops-07 | secret read outside maintenance window | medium | open (/security/siem_alerts.xlsx sheet 'alerts' row 73)
12. 2026-11-14T05:38:43Z moderation-18 quarantine_agent by human:Mira Petrović (/logs/audit/2026-11-14.jsonl line 3274)"""
_labs = ["A: moderation-18 was quarantined", "B: the red-team canary artifact was uploaded",
         "C: the approved transfer to the external auditor was sent", "D: the entry artifact was uploaded to our platform",
         "E: the SIEM raised its alert about the secret read"]
_got = _inc.order_events(_tl, [{"label": l, "entry": [1, 2, 3, 4, 5][i]} for i, l in enumerate(_labs)])[0]
assert [g[0] for g in _got] == ["C", "D", "B", "E", "A"], _got
_got = _inc.order_events(_tl, [{"label": l[0], "entry": n} for l, n in zip(_labs, [12, 4, 1, 3, 11])])[0]  # bare letters: as given
assert _got == ["C", "D", "B", "E", "A"], _got
print("order matching ok")

# Request-log policy wording -> filter spec
_spec = _agent._policy_spec('A request in /logs/access/requests.csv is a policy violation if all of these hold: 1. action is exactly "read" and scope_class is "private"; 2. the actor is external (the actor field starts "external:"); 3. it has no valid change ticket in /logs/access/change_tickets.csv: the ticket must be listed with status "approved", match the request\'s actor and resource, and cover the request timestamp (valid_from inclusive, valid_until exclusive); if revoked_at is set, the timestamp must also be strictly before revoked_at; 4. the result is not "denied".', "/logs/access/requests.csv")
_w = _spec["where"]
assert {"column": "action", "op": "eq", "value": "read"} in _w and {"column": "scope_class", "op": "eq", "value": "private"} in _w
assert {"column": "actor", "op": "startswith", "value": "external:"} in _w and {"column": "result", "op": "ne", "value": "denied"} in _w
_nm = next(x for x in _w if x.get("op") == "no_match")["value"]
assert _nm["on"] == {"actor": "actor", "resource": "resource"} and "within" in _nm and "before" in _nm, _nm
assert not any(x.get("column") == "result" and x.get("op") == "eq" for x in _w)
print("policy spec ok")
