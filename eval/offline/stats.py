import json, sys, glob, os
rid = sys.argv[1]
fin = json.load(open(f"runs/{rid}/finish.json")) if os.path.exists(f"runs/{rid}/finish.json") else {}
print({k: (v if not isinstance(v,(list,dict)) else type(v).__name__) for k,v in fin.items()})
tot=0
for f in sorted(glob.glob(f"runs/{rid}/t*.jsonl")):
    ev=[json.loads(l) for l in open(f)]
    st=next((e for e in ev if e["event"]=="start"),{})
    en=next((e for e in ev if e["event"]=="end"),{})
    sub=[e for e in ev if e["event"]=="submit"]
    resp=sub[-1]["response"] if sub else {}
    tools=[e.get("name") or e["event"] for e in ev if e["event"] in("tool","view_image","download_file")]
    from collections import Counter
    c=Counter(tools)
    tot+=en.get("cost_usd",0)
    score = resp.get("score") if isinstance(resp,dict) else None
    print(os.path.basename(f)[:3], f"s={score}", f"${en.get('cost_usd',0):.3f}", f"calls={en.get('llm_calls')}", f"pt={en.get('prompt_tokens')}", f"ct={en.get('completion_tokens')}", dict(c), "|", st.get("instruction","")[:110].replace("\n"," "))
print("total", tot)
