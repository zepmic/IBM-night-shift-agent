import json, sys
rid, tid = sys.argv[1], sys.argv[2]; n=int(sys.argv[3]) if len(sys.argv)>3 else 500
for l in open(f"runs/{rid}/{tid}.jsonl"):
    e=json.loads(l); ev=e["event"]
    if ev=="assistant":
        for c in e.get("tool_calls") or []: print("  CALL", c["function"]["name"], c["function"]["arguments"][:n])
        if e.get("content"): print("  SAY", e["content"][:n])
    elif ev in("tool","download_file","view_image"): print("  OUT", e.get("name",ev), str(e.get("output"))[:n].replace("\n"," ⏎ "))
    elif ev in("guard","blocked","repeat","submit_error","crash","llm_error"): print("  !!",ev, str({k:v for k,v in e.items() if k not in("event","t")})[:n])
    elif ev=="submit": print("  SUBMIT", json.dumps(e["args"],ensure_ascii=False)[:n], "->", e["response"].get("feedback") if isinstance(e["response"],dict) else e["response"])
    elif ev=="end": print("  END", e["cost_usd"], e["llm_calls"], e["actions_sent"], e["actions_blocked"])
