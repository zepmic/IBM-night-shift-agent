import json, sys, re, os
from dotenv import load_dotenv; load_dotenv(".env")
from arena.client import ArenaClient
import incident
sys.path.insert(0, __import__("os").path.dirname(__file__)); import vis as _vis
c=ArenaClient(); rid=sys.argv[1]
if not os.path.exists(f"runs/{rid}.json"): json.dump(c.get_run(rid),open(f"runs/{rid}.json","w"))
r=json.load(open(f"runs/{rid}.json"))
want=set(sys.argv[2].split(",")) if len(sys.argv)>2 and sys.argv[2]!="all" else None
ok=bad=0
for t in r["tasks"]:
    tid=t["task_id"]
    if want and tid not in want: continue
    paths=set(c.task_manifest(rid,tid))
    read=lambda p: c.download_file(rid,tid,p)[0]
    ins=t["instruction"]
    for p in paths:
        if p.startswith("/tickets/"):
            x=read(p).decode("utf-8","replace")
            if "status: open" in x: ins+=" "+x
    exp=t["expected_answer"]; res=None
    fam=None
    if re.search(r"compromised in incident|executed attacker-directed|list of compromised agents", ins): fam="comp"
    elif re.search(r"entry point|where INC.*started|patient zero of incident", ins): fam="entry"
    elif "Contain INC" in ins and isinstance(exp,dict): fam="contain"
    elif re.search(r"How many (distinct )?customer records", ins) and isinstance(exp,dict): fam="count"
    elif "canary records" in ins: fam="canary"
    elif "first exfiltrating transfer" in ins and isinstance(exp,str): fam="first"
    elif "first to actually receive" in ins: fam="firstdom"
    if not fam: continue
    try:
        if fam in("comp","entry","contain"):
            a=incident.analyse(read,paths,None,_vis.make(read))
        if fam=="comp": res=sorted(a["compromised"])
        elif fam=="entry":
            e=a["entry"][0] if a["entry"] else None; fr=a["first_reads"].get(e["location"]) if e else None
            res={"artifact":e and e["copy"],"agent":fr and fr["agent"],"at":fr and incident.iso(fr["ts"])}
        elif fam=="contain":
            res={"quarantine":sorted(set(a["compromised"])-a["quarantined"]),"rotate":sorted(a["tokens"]),"block":sorted(a["attacker_domains"])}
            exp={"quarantine":exp["quarantine"],"rotate":sorted(x["token"] for x in exp["rotate"]),"block":exp["block"]}
            if "every compromised" not in ins: res["quarantine"]=exp["quarantine"]
            if "every exposed" not in ins.lower(): res["rotate"]=exp["rotate"]
            if "every attacker domain" not in ins: res["block"]=exp["block"]
        else:
            tr=incident.transfers(read,paths); cnt=[x for x in tr["rows"] if x["counts"]]; okk=[x for x in cnt if x["status"]=="ok"]
            if fam=="count":
                ids=[i for x in cnt for i in x["ids"]]
                res={"records":len(set(ids)) if "distinct" in ins else len(ids),"domains":sorted({x["dest"] for x in cnt})}
            elif fam=="canary": res=sorted(tr["canaries"]&{i for x in cnt for i in x["ids"]})
            elif fam=="first": res=incident.iso(okk[0]["ts"]) if okk else None
            elif fam=="firstdom": res=okk[0]["dest"] if okk else None
    except Exception as e:
        import traceback; traceback.print_exc(); res=f"ERR {e}"
    good = res==exp
    ok+=good; bad+=not good
    print(tid, fam, "OK" if good else "MISMATCH", "" if good else f"\n   got {res}\n   exp {exp}\n   {ins[:200]}")
print(ok,bad)
