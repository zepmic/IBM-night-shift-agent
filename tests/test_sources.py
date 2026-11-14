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
               {"path": "/fleet/registry_export.json", "record": "agent-03"}, {"path": "/fleet/tokens.csv", "record": "TOK-9"}], got
assert len(ev.candidates(["agent-03"], [], max_add=2)) == 2
# already cited within ±2 lines: not added again; numbers and words in the answer add nothing
assert {"path": "/fleet/changes.md", "line": 7} not in ev.candidates(["agent-03"], [{"path": "/fleet/changes.md", "line": 8}])
assert ev.candidates({"count": 4, "status": "compromised"}, []) == []
# a JSON file where the value is everywhere: the file, without a guessed record
ev2 = S.Evidence()
ev2.add_tool("read", {"path": "/fleet/reg.json"}, "\n".join(f'{i}: {{"from": "agent-03", "to": "x{i}"}}' for i in range(1, 6)))
assert ev2.candidates(["agent-03"], []) == [{"path": "/fleet/reg.json"}]

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
assert out == [{"path": "/r/a.pdf", "page": 2}, {"path": "/r/h.docx", "paragraph": 2}] and rep["dropped"] == [{"path": "/nope.md", "line": 1}], (out, rep)
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
