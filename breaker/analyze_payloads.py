#!/usr/bin/env python3
"""
Read-only-Auswertung von GET /payloads (Team Donaufriends, B4).

Holt die eigenen Angriffe + Platzierungen + Treffer und fasst sie zusammen.
Aendert NICHTS (kein POST/PATCH). Braucht ARENA_BASE_URL + ARENA_API_KEY aus .env.

Nutzung:
    python3 breaker/analyze_payloads.py
"""
import json
import os
import sys
import urllib.request

def load_env():
    env = dict(os.environ)
    try:
        for line in open(".env", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass
    return env

def main() -> int:
    env = load_env()
    base = env.get("ARENA_BASE_URL", "").rstrip("/")
    key = env.get("ARENA_API_KEY", "")
    if not base or not key:
        print("ARENA_BASE_URL / ARENA_API_KEY fehlen (.env).", file=sys.stderr)
        return 2
    url = base + "/api/v1/payloads"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.load(r)
    except Exception as e:
        print(f"Request fehlgeschlagen: {e}", file=sys.stderr)
        return 1

    payloads = data.get("payloads", [])
    limits = data.get("limits", {})
    print(f"Slots: dev {limits.get('dev_used')}/{limits.get('dev_slots')}  "
          f"final {limits.get('final_used')}/{limits.get('final_slots')}  "
          f"final_open={limits.get('final_open')}  deadline={limits.get('deadline')}")
    if not payloads:
        print("\nNoch keine eigenen Payloads eingereicht.")
        return 0

    for p in payloads:
        plc = p.get("placements", []) or []
        # exposed != gelesen: ein Treffer (hit) zaehlt, Platzierung allein nicht.
        hits = [x for x in plc if x.get("hit")]
        on_cited = [x for x in plc if x.get("slot") == "cited"]
        dev = p.get("dev", {}) or {}
        print(f"\n[{p.get('id')}] {p.get('goal')} / {p.get('carrier')}  "
              f"status={p.get('status')} stage={p.get('stage')} in_pool={p.get('in_pool')}")
        if p.get("review_note"):
            print(f"   review_note: {p['review_note']}")
        print(f"   platziert={len(plc)}  davon cited-slot={len(on_cited)}  hits={len(hits)}  "
              f"(dev.placed={dev.get('placed')} dev.hits={dev.get('hits')})")
        # Treffer nach via (welcher Tool-Call des Opfers) und Level
        by_via, by_level, by_slot = {}, {}, {}
        for x in plc:
            by_level[x.get("level")] = by_level.get(x.get("level"), 0) + 1
            by_slot[x.get("slot")] = by_slot.get(x.get("slot"), 0) + 1
        for x in hits:
            v = x.get("via", "?")
            by_via[v] = by_via.get(v, 0) + 1
        if by_slot:
            print("   Platzierungen nach slot:", dict(sorted(by_slot.items())))
        if by_level:
            print("   Platzierungen nach level:", dict(sorted(by_level.items(), key=lambda t: str(t[0]))))
        if by_via:
            print("   Treffer nach via:", dict(sorted(by_via.items())))
    # Ranking: Hit-Rate je platzierter Gelegenheit
    print("\n--- Ranking (Trefferquote je Platzierung) ---")
    rank = []
    for p in payloads:
        plc = p.get("placements", []) or []
        hits = sum(1 for x in plc if x.get("hit"))
        rate = hits / len(plc) if plc else 0.0
        rank.append((rate, hits, len(plc), p.get("id")))
    for rate, hits, placed, pid in sorted(rank, reverse=True):
        print(f"   {pid}: {hits}/{placed} = {rate:.0%}")
    print("\nHinweis: 'exposed' = Opfer hat den Task abgegeben (nicht unbedingt gelesen). "
          "Best Breaker zaehlt hits/exposed ueber FREMDE Teams. Platzierung != Lesen != Treffer.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
