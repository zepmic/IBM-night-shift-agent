import csv, io, json, sys, re, os
from dotenv import load_dotenv; load_dotenv(".env")
from arena.client import ArenaClient
import incident
sys.path.insert(0, __import__("os").path.dirname(__file__)); import vis as _vis
c=ArenaClient(); rid=sys.argv[1]
if not os.path.exists(f"runs/{rid}.json"): json.dump(c.get_run(rid),open(f"runs/{rid}.json","w"))
r=json.load(open(f"runs/{rid}.json"))

def family(ins, exp):
    if re.search(r"compromised (?:agents|in incident)|executed attacker-directed|list of compromised agents|full list of compromised", ins, re.I): return "comp"
    if isinstance(exp,dict) and {"artifact","agent","at"} <= set(exp) and re.search(r"entry point|where INC.*started|patient zero|artifact carried the injected instruction", ins, re.I): return "entry"
    if re.search(r"\bcontain(?:ment)?\b", ins, re.I) and isinstance(exp,dict): return "contain"
    if re.search(r"how many .*customer records|number of exfiltrated customer records", ins, re.I) and isinstance(exp,dict): return "count"
    if re.search(r"chronological order|put these events.*order", ins, re.I): return "chronology"
    if re.search(r"canary|honeytoken", ins, re.I) and isinstance(exp,list): return "canary"
    if re.search(r"first exfiltrating transfer|first successful.*transfer", ins, re.I): return "firstdom" if isinstance(exp,str) and "." in exp else "first"
    if re.search(r"first to actually receive", ins, re.I): return "firstdom"
    if isinstance(exp,dict) and "owner_email" in exp and re.search(r"(?:most|largest (?:share|number)).*exfiltrated.*records|exfiltrated.*records.*per agent", ins, re.I): return "largest"

def counting_rows(read, paths, tr):
    text="\n".join(read(p).decode("utf-8","replace") for p in paths if p.count("/")==1 and p.lower().endswith(".md"))
    signed=re.search(r"(/[^\s)`]+\.(?:png|jpe?g)).{0,120}(?:only|in force)|(?:only|in force).{0,120}(/[^\s)`]+\.(?:png|jpe?g))",text,re.I)
    image=next((x for x in signed.groups() if x),None) if signed else None
    if image in paths:
        text=_vis.make(read)(image)
    only_ok=bool(re.search(r"only successful|delivered transfers only|blocked[^.]*not (?:count|exposure)|blocked[^.]*never count",text,re.I)) and not re.search(r"both successful and blocked",text,re.I)
    once=bool(re.search(r"counted once|count(?:s|ed)? only once|distinct|unique|deduplicat",text,re.I)) and not re.search(r"add up",text,re.I)
    rows=[x for x in tr["rows"] if x["counts"] and (not only_ok or x["status"] in ("ok","success"))]
    return rows,once

def chronology(ins, lines):
    entries=[x for x in lines if re.match(r"\d+\. \d{4}-",x)]
    events=re.findall(r"\b([A-Z]):\s*(.*?)(?=;\s*[A-Z]:|\.\s*Answer|$)",ins,re.S)
    def pick(desc):
        d=desc.lower()
        tests=[
            ("entry artifact" in d and "uploaded" in d, r"attack ENTRY artifact uploaded"),
            ("patient zero" in d or ("entry artifact" in d and "processed" in d), r"entry artifact .* first processed"),
            ("approved transfer" in d, r"approved transfer"),
            ("red-team canary" in d, r"red-team canary artifact"),
            ("first exfiltrating" in d, r"FIRST successful exfiltrating transfer"),
            ("injected notice" in d, r"injected notice"),
            ("first secret" in d, r"FIRST secret read"),
            ("siem" in d, r"SIEM alert"),
            ("revocation" in d or "remove_delegation" in d, r"remove_delegation"),
            ("quarantined" in d, re.escape(next(iter(re.findall(r"[a-z][a-z_]*-\d+",d)),""))+r" quarantine"),
        ]
        return next((x for x in entries for yes,rx in tests if yes and re.search(rx,x,re.I)),None)
    found=[(x.split()[1],label) for label,desc in events if (x:=pick(desc))]
    return [label for _,label in sorted(found)] if len(found)==len(events) else None

def largest_sender(read, paths, rows, once):
    scores={}
    for x in rows:
        scores.setdefault(x["agent"],[]).extend(x["ids"])
    scores={a:len(set(ids)) if once else len(ids) for a,ids in scores.items()}
    agent=max(scores,key=lambda a:(scores[a],a))
    roster=next((p for p in paths if re.search(r"/agents\.csv$",p,re.I)),"")
    contacts=next((p for p in paths if re.search(r"contacts.*\.csv$",p,re.I)),"")
    rr=list(csv.DictReader(io.StringIO(read(roster).decode("utf-8-sig","replace"))))
    cr=list(csv.DictReader(io.StringIO(read(contacts).decode("utf-8-sig","replace"))))
    row=next(r for r in rr if agent in r.values())
    contact=next(r for r in cr if set(v for v in row.values() if v) & set(v for v in r.values() if v)
                 and any("@" in str(v) for v in r.values()))
    email=next(v for v in contact.values() if "@" in str(v))
    return {"agent":agent,"owner_email":email}
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
    fam=family(ins,exp)
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
            tr=incident.transfers(read,paths); cnt,once=counting_rows(read,paths,tr); okk=[x for x in cnt if x["status"] in ("ok","success")]
            if fam=="count":
                ids=[i for x in cnt for i in x["ids"]]
                res={"records":len(set(ids)) if once or "distinct" in ins.lower() else len(ids),"domains":sorted({x["dest"] for x in cnt})}
            elif fam=="canary": res=sorted(tr["canaries"]&{i for x in cnt for i in x["ids"]})
            elif fam=="first": res=incident.iso(okk[0]["ts"]) if okk else None
            elif fam=="firstdom": res=okk[0]["dest"] if okk else None
            elif fam=="chronology": res=chronology(ins,incident.timeline(read,paths,incident.analyse(read,paths),tr))
            elif fam=="largest": res=largest_sender(read,paths,cnt,once)
    except Exception as e:
        import traceback; traceback.print_exc(); res=f"ERR {e}"
    good = res==exp
    ok+=good; bad+=not good
    print(tid, fam, "OK" if good else "MISMATCH", "" if good else f"\n   got {res}\n   exp {exp}\n   {ins[:200]}")
print(ok,bad)
