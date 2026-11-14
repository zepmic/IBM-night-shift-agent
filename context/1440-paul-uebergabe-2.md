# Übergabe 2: Code-Werkzeuge für die Vorfalls-Familien, Stand und offene Punkte

**Wer:** Paul (+ Claude Code) · **Zeit:** Sa 14.11., ~14:40 · **Typ:** Status + Übergabe

## Messwerte (volle Runs, 48 Tasks, frische Seeds)
| Run | Code | Accuracy | Kosten | cost_score | final |
|---|---|---|---|---|---|
| run__8OvzdDTetNJ (Ausgang) | 431e3ec | 0.700 | $0.97 | 0.238 | 0.434 |
| run_xVoe6Wvi24YP | e6df0b9 | 0.709 | $0.41 | 0.337 | 0.474 |
| **run_iOrNuR6b10uJ** | **673bfd2 (main)** | **0.772** | **$0.45** | **0.327** | **0.512** |

Gezielte Replays auf Seed 1796485340: run_AxerKoP4Gin7 (18 Tasks, Ø 0.45 → 0.67, Kosten −73 %), run_lxrcans7xVRj (10 Tasks, Ø 0.81),
run_lV1jJDAluVK8 (14 Tasks, Ø 0.83; Board-Triage 3× 1.00). Dev-Budget: grob $7.6 von $15 verbraucht. Docker-Wächter: e6df0b9 grün,
673bfd2 in runs/docker_watch.log nachsehen.

## Was neu auf main ist
- `incident.py` (neu, kein Modell außer Vision/Jev über agent.py): Logs → UTC (Archiv ist Lokalzeit), Spalten am Inhalt erkannt.
  - `incident_facts`: Einstiegs-Artefakte (Text dekodiert; Bild-Anhang oder Bild-Kopie per Vision, Cache pro Blob-Hash; Red-Team
    ausgenommen), Attack Traces inkl. Kind-Traces über Board-Posts, kompromittierte Agents, Quarantäne-Stand, exponierte Tokens,
    Angreifer-Domains, Transfer-Register (csv/xlsx/ods) mit Urteil pro Transfer, Summen in allen Varianten, **Lesart der
    Runbook-Regel dieses Workspaces** (blockiert zählt? einmal oder aufsummiert?), Kanarien, sortierte Zeitleiste.
    Parameter `agent`: Aktivitätsübersicht eines Agents (Status-Report-Claims). Parameter `order`: Ereignis-Reihenfolge wird
    in Code sortiert, das Modell ordnet nur Buchstabe → Zeitleisten-Eintrag zu.
  - `review_access` rechnet den aktuellen Zustand selbst und liegt Access-Review-Aufgaben bei; `capabilities` mit `current`
    und `chain_from/chain_to`.
  - `board_triage` und `manifest_audit`: Kandidaten/Hashes in Code, Urteil pro Post bzw. Manifest per Jev; Fallback ans Modell.
  - Sperren: mehrdeutiger Agent-Bezug (→ NEEDS_CLARIFICATION), bereits quarantänisierte Agents, Form der Refusal-Antwort.
  - Zitate berechneter Antworten setzt der Harness (`evidence.must_cite`, Containment: erste Aktion je Agent).
- Prompt 3.6k → 3.2k Zeichen trotz 5 neuer Werkzeuge; `PINNED` in agent.py hält berechnete Blätter im Verlauf.

## Kostenlos prüfen (Skripte liegen lokal in runs/, git-ignoriert, nur auf Pauls Rechner)
`PYTHONPATH=. uv run python -W ignore runs/_inc_check.py <run_id> all` (Vorfalls-Familien gegen erwartete Antworten),
`runs/_ar_check.py <run_id>` (Access-Review), `runs/_mcp.py <run_id>`, `runs/_board.py <run_id>` (Jev pro Post),
`runs/_tr.py <run_id> tNN 400` (Trace lesbar), `runs/_stats.py <run_id>` (Kosten/Calls pro Task).
Erwartete Antworten: `ArenaClient().get_run(run_id)["tasks"]`. Muster, das am meisten gebracht hat: voller Run auf frischem Seed
(~$0.45) → die schwachen Tasks offline gegen die aufgedeckten Antworten nachrechnen → Szenario-Unterschied im Code beheben.

## Offen in run_iOrNuR6b10uJ (16 Tasks < 0.8, noch nicht analysiert außer den ersten beiden)
- 0.00: t04 („Agent mit dem größten Anteil exfiltrierter Records + Owner-E-Mail“: Faktenblatt hat keine Summe pro Agent →
  in `transfer_lines` ergänzen), t19, t21, t22, t40, t44 (ungesehen).
- partial: t12 (Indikator-Scans: Angreifer-Domain laut Runbook = Ziel eines Transfers in einem Attack Trace; das Modell nahm eine
  Domain dazu), t15, t16, t23, t37.
- nur Quellen: t09, t29, t38, t41, t45.
- Vorher bekannt: Leak-Check (t17/t20 in run_xVoe6Wvi24YP: ein Token zu viel, sha256_12-Abgleich in Code wäre exakt),
  Partner-Zusammenfassung (Zitate: jeder zählende Transfer per Record), Breach-Notification (Antwortform).
- Kosten: Verlauf (`keep_small_chars` 6000) ist unangetastet; 587 Calls im letzten Run, Ø 4.4k Tokens pro Call.
