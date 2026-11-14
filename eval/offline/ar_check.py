import json, sys, re, os
from dotenv import load_dotenv; load_dotenv(".env")
from arena.client import ArenaClient
import incident, agent, sources
sys.path.insert(0, __import__("os").path.dirname(__file__)); import vis as _vis
c=ArenaClient(); rid=sys.argv[1]
if not os.path.exists(f"runs/{rid}.json"): json.dump(c.get_run(rid),open(f"runs/{rid}.json","w"))
r=json.load(open(f"runs/{rid}.json"))
class T: 
    def add(self,*a): return 0
for t in r["tasks"]:
    tid=t["task_id"]; exp=t["expected_answer"]
    if not (isinstance(exp,dict) and "approve" in exp): continue
    orig=agent._workspace
    agent._workspace=lambda cl,ru,ta,cfg,tr: (set(c.task_manifest(ru,ta)), (lambda p: c.download_file(ru,ta,p)[0]), _vis.make(lambda p: c.download_file(ru,ta,p)[0]))
    out=agent._review_access(c,rid,tid,{},sources.Evidence(),agent.Config(),T())
    got=json.loads(out.splitlines()[0][8:])
    print(tid,"OK" if got==exp else f"MISMATCH\n got {got}\n exp {exp}\n"+out[:1500])
