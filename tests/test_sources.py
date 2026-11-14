"""Offline: the evidence ledger (sources.py) and its use at submit time. python tests/test_sources.py"""
import json
import os
import pathlib
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "tests"))
import agent  # noqa: E402
import mock_server  # noqa: E402
import sources as S  # noqa: E402
from arena import llm  # noqa: E402
from arena.client import ArenaClient, Task  # noqa: E402

assert S.answer_values({"ids": ["agent-03", "TOK-1"], "n": 12, "who": "weber@org.example", "note": "two words", "x": "yes", "d": "3.5"}) == [
    "agent-03", "TOK-1", "weber@org.example"]
assert S._contains("x agent-03, y", "agent-03") and not S._contains("agent-031", "agent-03") and not S._contains("sub-agent-03", "agent-03")
assert S._contains("see evil.example.", "evil.example") and not S._contains("a@evil.example", "evil.example")

# read results in several shapes -> the same line numbers
for res in ("7: a agent-03\n8: b agent-03\n9: c", {"content": "a agent-03\nb agent-03\nc", "start_line": 7},
            ["a agent-03", "b agent-03", "c"], [{"line": 7, "text": "a agent-03"}, {"line": 8, "text": "b agent-03"}]):
    ev = S.Evidence()
    ev.add_tool("read", {"path": "/fleet/changes.md", "start_line": 7}, res)
    assert ev.candidates(["agent-03"], []) == [{"path": "/fleet/changes.md", "line": 7}], (res, ev.candidates(["agent-03"], []))

ev = S.Evidence()
# the baseline case: audit log full of the agent (ambiguous -> nothing), change record with it twice, registry export
ev.add_tool("query_logs", {"agent": "agent-03"}, {"events": [
    {"file": "/logs/audit/a.jsonl", "line": n, "agent": "agent-03", "action": "read"} for n in (10, 40, 90, 200)]})
ev.add_tool("read", {"path": "/fleet/changes.md"}, "\n".join(f"{i}: " + ("agent-03 scope widened" if i in (7, 12) else "noise") for i in range(1, 15)))
ev.add_tool("search", {"pattern": "agent-03"}, ["/fleet/registry_export.json:31:   \"id\": \"agent-03\",", "/notes/misc.txt:4: about agent-031"])
ev.add_tool("read", {"path": "/fleet/tokens.csv"}, "1: id,owner\n2: TOK-9,agent-03\n3: TOK-7,agent-11")
got = ev.candidates(["agent-03"], [{"path": "/logs/audit/a.jsonl", "line": 40}], max_add=9)
assert got == [{"path": "/fleet/changes.md", "line": 7}, {"path": "/fleet/changes.md", "line": 12},
               {"path": "/fleet/registry_export.json"}, {"path": "/fleet/tokens.csv", "record": "TOK-9"}], got
assert len(ev.candidates(["agent-03"], [], max_add=2)) == 2
# already cited within ±2 lines: not added again; numbers and words in the answer add nothing
assert {"path": "/fleet/changes.md", "line": 7} not in ev.candidates(["agent-03"], [{"path": "/fleet/changes.md", "line": 8}])
assert ev.candidates({"count": 4, "status": "compromised"}, []) == []
# a JSON file where the value is everywhere: the file, without a guessed record
ev2 = S.Evidence()
ev2.add_tool("read", {"path": "/fleet/reg.json"}, "\n".join(f'{i}: {{"from": "agent-03", "to": "x{i}"}}' for i in range(1, 6)))
assert ev2.candidates(["agent-03"], []) == [{"path": "/fleet/reg.json"}]

# the platform's real result shapes (dev run): read = {text: " 1| …"}, search = {hits: [{path, line, text}]},
# query_logs = {events: [{file, line, …}]}. Tables with an id column are cited by record, log archives by line.
ev3 = S.Evidence()
ev3.add_tool("read", {"path": "/fleet/fp.csv"}, {"path": "/fleet/fp.csv", "kind": "csv", "start_line": 1,
             "text": "1| token_id,first4\n2| TOK-A-1,aaaa\n3| TOK-B-2,bbbb"})
ev3.add_tool("search", {"pattern": "K-15"}, {"hits": [{"path": "/contacts.csv", "line": 16, "text": "K-15,Mateo,x@y.example"}]})
ev3.add_tool("query_logs", {}, {"events": [{"file": "/logs/archive/d.csv", "line": 77, "agent": "ops-01", "target": "TOK-B-2"}]})
ev3.add_tool("read", {"path": "/logs/archive/d.csv", "start_line": 1}, {"text": "1| time_local,agent\n2| 13.11.2026 01:00:01,ops-09"})
assert ev3.candidates(["TOK-B-2", "x@y.example", "ops-09"], [], max_add=9) == [
    {"path": "/fleet/fp.csv", "record": "TOK-B-2"}, {"path": "/logs/archive/d.csv", "line": 77},
    {"path": "/contacts.csv", "record": "K-15"}, {"path": "/logs/archive/d.csv", "line": 2}], ev3.candidates(["TOK-B-2", "x@y.example", "ops-09"], [], max_add=9)
# the model's own citations: csv line -> record, json -> the file, the rule book is no evidence
out, rep = S.finalize([{"path": "/fleet/fp.csv", "line": 2}, {"path": "/fleet/fp.csv", "line": 9}, {"path": "/logs/archive/d.csv", "line": 77},
                       {"path": "/fleet/reg.json", "line": 4}, {"path": "/fleet/reg.json", "record": "x"}, {"path": "/AGENTS.md", "line": 19}],
                      None, ev3, None)
assert out == [{"path": "/fleet/fp.csv", "record": "TOK-A-1"}, {"path": "/fleet/fp.csv", "line": 9}, {"path": "/logs/archive/d.csv", "line": 77},
               {"path": "/fleet/reg.json"}], out
assert {"path": "/AGENTS.md", "line": 19} in rep["dropped"]
# the grader tolerates expected + 2 citations: one per answer value and file, no bare table paths, docx by paragraph,
# and additions only for values without support (or the value's own table row)
ev4 = S.Evidence()
ev4.add_tool("query_logs", {}, {"events": [{"file": "/logs/a.jsonl", "line": n, "agent": a} for n, a in
                                           ((10, "ops-01"), (11, "ops-01"), (30, "ops-02"), (31, "ops-02"), (50, "ops-01"))]})
ev4.add_tool("read", {"path": "/fleet/agents.csv"}, {"text": "1| agent_id,name\n2| ops-01,A\n3| ops-02,B"})
ev4.add_tool("read", {"path": "/notes/n.md"}, {"text": "1| ops-02 looked odd"})
out, rep = S.finalize([{"path": "/logs/a.jsonl", "line": n} for n in (10, 11, 30, 31, 50)] + [{"path": "/fleet/agents.csv"}, {"path": "/n.docx", "line": 4}],
                      ["ops-01", "ops-02"], ev4, None)
assert out == [{"path": "/logs/a.jsonl", "line": 10}, {"path": "/logs/a.jsonl", "line": 30}, {"path": "/n.docx", "paragraph": 4},
               {"path": "/fleet/agents.csv", "record": "ops-01"}], out  # 2 values + 2: the budget is full
# within the budget two citations per value stay (two transfers to one domain are two pieces of evidence)
out, _ = S.finalize([{"path": "/logs/a.jsonl", "line": n} for n in (10, 11, 50, 30)], ["ops-01", "ops-02"], ev4, None, max_add=0)
assert [x["line"] for x in out] == [10, 11, 30], out

# download_file extractions
ev = S.Evidence()
ev.add_extraction("/r/a.pdf", "[pdf extraction]\n--- page 1 ---\nintro\n--- page 2 ---\nblocked evil-cdn.test today\n--- page 3 ---\nend")
ev.add_extraction("/r/h.docx", "[docx]\n1. Hello\n2. Handover names TOK-4 as leaked\n[header] x")
ev.add_extraction("/s/x.xlsx", "[xlsx]\n=== sheet 'transfers' (9 rows) ===\nr1: id | to\nr5 [hidden]: TR-5 | evil-cdn.test\n=== sheet \"o'k\" (1 rows) ===\nr1: TOK-4")
assert ev.candidates(["evil-cdn.test", "TOK-4"], [], max_add=9) == [
    {"path": "/r/a.pdf", "page": 2}, {"path": "/s/x.xlsx", "sheet": "transfers", "row": 5},
    {"path": "/r/h.docx", "paragraph": 2}, {"path": "/s/x.xlsx", "sheet": "o'k", "row": 1}]

# finalize: unknown files dropped, paths normalised, duplicates removed
out, rep = S.finalize([{"path": "r/a.pdf", "page": 2}, {"path": "/nope.md", "line": 1}, {"path": "/r/a.pdf", "page": 2}],
                      ["TOK-4"], ev, {"/r/a.pdf", "/r/h.docx"})
assert out == [{"path": "/r/a.pdf", "page": 2}, {"path": "/r/h.docx", "paragraph": 2}] and {"path": "/nope.md", "line": 1} in rep["dropped"], (out, rep)
# odd tool results never raise
for junk in (None, 5, {"content": None}, [[1, 2], {"path": 3, "line": "x"}], "x" * 10):
    ev.add_tool("read", {"path": "/a.md"}, junk)
    ev.add_tool("search", {}, junk)

# end to end on the mock Task API with a scripted model: reads the rules and the CSV, cites only the rules file and
# a file that does not exist -> the CSV record that carries the answer is added, the phantom file is dropped.
srv = ThreadingHTTPServer(("127.0.0.1", 0), mock_server.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
script = [("read", {"path": "/mission.md"}), ("read", {"path": "/data/shelters.csv"}),
          ("submit", {"outcome": "OK", "answer": '["S-02"]', "sources": [{"path": "/mission.md", "line": 2}, {"path": "/data/ghost.csv", "record": "S-02"}]})]
step = {"n": 0}


def chat(messages, **kw):
    name, args = script[step["n"]]
    step["n"] += 1
    return {"content": "", "tool_calls": [{"id": f"c{step['n']}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


real = agent.llm.chat
agent.llm.chat = chat
try:
    with tempfile.TemporaryDirectory() as d:
        client = ArenaClient(base_url=f"http://127.0.0.1:{srv.server_address[1]}", api_key="arena_test", cache=d)
        run = client.start_run("dev")
        events = []
        res = agent.solve_task(client, run.run_id, run.tasks[0], client.tools(), agent.Config(), llm.CostTracker(), events.append)
        sub = [e for e in events if e["event"] == "submit"][0]
        assert sub["args"]["sources"] == [{"path": "/mission.md", "line": 2}, {"path": "/data/shelters.csv", "record": "S-02"}], sub
        assert res["score"] == 1.0, res
        rep = [e for e in events if e["event"] == "sources"][0]
        assert rep["dropped"] == [{"path": "/data/ghost.csv", "record": "S-02"}] and len(rep["added"]) == 1
        # switched off: the model's citations go out as they are
        step["n"] = 0
        run = client.start_run("dev")
        events = []
        agent.solve_task(client, run.run_id, run.tasks[0], client.tools(), agent.Config(auto_sources=False), llm.CostTracker(), events.append)
        assert len([e for e in events if e["event"] == "submit"][0]["args"]["sources"]) == 2
finally:
    agent.llm.chat = real
    srv.shutdown()
print("sources tests ok")
