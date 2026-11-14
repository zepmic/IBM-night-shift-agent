import json, sys
from dotenv import load_dotenv; load_dotenv(".env")
from arena.client import ArenaClient
import agent, sources
c=ArenaClient(); rid=sys.argv[1]
r=json.load(open(f"runs/{rid}.json"))
for t in r["tasks"]:
    tid=t["task_id"]
    if not any(p.startswith("/integrations/") for p in (t.get("expected_sources") and [s["path"] for s in t["expected_sources"]] or [])): continue
    ev=sources.Evidence()
    out=agent._manifest_audit(c,rid,tid,{},ev,None)
    if out.startswith('ERROR'): print(tid,'no manifests'); continue
    got=json.loads(out.splitlines()[0].split("): ",1)[1].replace(" by hash / list alone. Descriptions to judge yourself for instructions aimed at agents (decoded):",""))
    es={json.dumps(s,sort_keys=True) for s in t["expected_sources"]}; gs={json.dumps(s,sort_keys=True) for s in getattr(ev,"must_cite",[])}
    print(tid,"OK" if got==t["expected_answer"] else f"MISMATCH got {got} exp {t['expected_answer']}\n{out[:1500]}", "sources ok" if es==gs else f"src diff {es^gs}")
