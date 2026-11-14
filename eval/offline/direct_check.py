"""Direct submit of computed answers vs. the expected answers of an (empty) dev run: no model call, $0.

    PYTHONPATH=. uv run python -W ignore eval/offline/direct_check.py <run_id>
"""
import json, sys
from dotenv import load_dotenv; load_dotenv(".env")
from arena.client import ArenaClient, Task
from arena import llm
import agent

c = ArenaClient(); rid = sys.argv[1]
r = json.load(open(f"runs/{rid}.json"))
specs = c.tools()
got = {}
c.submit = lambda run, tid, outcome, answer, sources: got.update({tid: (outcome, answer, sources)}) or {"ok": True}
class Stop(Exception): pass
def no_model(*a, **k): raise Stop()
llm.chat = no_model
class T:
    total = 0.0
    def add(self, *a): return 0
key = lambda s: json.dumps(s, sort_keys=True)
n = 0
for t in r["tasks"]:
    if len(sys.argv) > 2 and t["task_id"] not in sys.argv[2:]: continue
    task = Task(task_id=t["task_id"], instruction=t["instruction"], level=t.get("level"))
    try:
        agent._solve(c, rid, task, specs, agent.Config(route=False), T(), lambda e: None, {})
    except Stop:
        continue
    except Exception as e:
        print(t["task_id"], "CRASH", type(e).__name__, e); continue
    if t["task_id"] in got:
        n += 1
        o, a, s = got[t["task_id"]]
        es = {key(x) for x in t["expected_sources"]}; gs = {key(x) for x in s}
        print(t["task_id"], "answer", "OK" if a == t["expected_answer"] and o == t["expected_outcome"] else f"MISMATCH got {str(a)[:200]} exp {str(t['expected_answer'])[:200]}",
              "| sources hit", len(es & gs), "of", len(es), "extra", len(gs - es), "|", t["instruction"][:70])
print("direct:", n)
