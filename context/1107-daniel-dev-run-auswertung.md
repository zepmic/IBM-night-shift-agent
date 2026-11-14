# Erster Dev-Run auf `daniel/fallback-eval`: Auswertung und Fixes

**Wer:** Daniel (+ Claude Code) · **Zeit:** Sa 11:07 · **Typ:** Messwert + Erkenntnis

## Messwert
- Run `run_F8sVRHvqtCE9`, Seed `1006996093`, `--level 1 --limit 6`, Commit `29314d1`.
- **Lokale Accuracy 0.34, Kosten $0.147** (105 LLM-Calls, 728k Input-Tokens). Geschätzt waren $0.04 – **die $0.006/Task aus der Baseline gelten nur für kurze Tasks**; ein Task am Step-Limit kostet ~$0.035.

| Task | Score | Befund |
|---|---|---|
| t07 | 1.00 | Quellen 3/3 |
| t17 | 0.92 | Quellen 1/1, aber 3 Streuzitate (2× /AGENTS.md, 1× contacts) → sources_score 0.75 |
| t04 | 0.00 | Antwort ✓, Quellen 5/5, **Constraint verletzt**: Modell wollte per `write` ein Python-Skript ablegen/ausführen |
| t11 | 0.12 | Step-Limit (24 Tool-Calls), Antwort falsch |
| t05 | 0.00 | Step-Limit, Action-Task (Rotation planen) nicht ausgeführt |
| t16 | 0.00 | Step-Limit, Antwort als Fließtext statt JSON |

## Erkenntnisse (wichtig für alle)
1. **Der Kit-Agent liest sich in eine Schleife.** `trim_history` kürzt alte Tool-Outputs auf 300 Zeichen („re-read if needed“) → das Modell liest /AGENTS.md, /runbook.md und dieselben CSVs 3–5× neu, bis das Step-Limit kommt. Das war der Hauptgrund für Kosten **und** falsche Antworten.
2. **So will der Grader Quellen** (aus 255 erwarteten Quellen der 48 Tasks in `finish.json`):
   - `.csv`-Tabellen → `record` (107×). Ausnahme: Log-Archiv `/logs/archive/*.csv` → `line` (7×).
   - `.jsonl`, die meisten `.md` → `line`. `.json` → **nur Pfad** (18×, nie mit Record). `.xlsx` → `sheet`+`row`. `.txt`, `.jpg`, Inbox-`.md` → nur Pfad.
   - /AGENTS.md und /runbook.md kommen **nie** als erwartete Quelle vor.
3. **Streuzitate kosten wirklich:** 1 Fehlzitat war gratis (t07), 3 kosteten 25 % des Quellen-Scores (t17), Deckel bei ~30 % (t04).
4. **`finish.json` verrät alle 48 Tasks** (auch nicht bearbeitete) mit `expected_answer`/`expected_sources`/`request` (Ticket-Text). Felder `level`/`instruction` fehlen dort.
5. Echte Tool-Formate: `read` → `{path, kind, total_lines, start_line, end_line, text: " 1| …"}`; `search` → `{hits: [{path, line, text}]}`; `query_logs` → `{total, events: [{file, line, ts, agent, …}]}`. Schreibende Tools antworten bei Verstoß mit `this task does not authorise that state-changing action` – dann ist der Task schon verloren.
6. Modell kann kein SHA-256 rechnen (t04 verlangt Abgleich per `sha256_12`); es hat über first4/last4 richtig geraten. Ein lokales Rechen-Tool wäre der saubere Weg (Plan B2) – offen.

## Was geändert wurde (Commit auf dem Branch, alle Tests grün, auch im Image mit `--network none`)
- Outputs ≤ 6000 Zeichen bleiben im Kontext; identische Read-only-Calls beantwortet der Harness lokal („already made this exact call“).
- Zitate: CSV-Zeile → Record (Kopfzeile entscheidet), JSON → nur Pfad, /AGENTS.md raus. Offline-Replay der Zitate dieses Runs: Streuzitate 14 → 7 bei gleichen Treffern.
- Prompt: keine Code-Ausführung, `write` ist kein Notizblock, ein schreibender Call ohne Auftrag kostet den Task.
- `UNSUPPORTED` → Antwort immer `null`. Deadline-Schutz (3 Min vor Run-Ende erzwungener Submit). Traces speichern Tool-Outputs jetzt ungekürzt.
- Neu: `tests/test_e2e.py` – Mock-Server spielt ein Modell-Skript, ganze Kette ohne Keys testbar.

## Offen
- **Wirkung von Wiederholungs-Sperre und Prompt ist ungemessen** (geht nur mit echtem Modell). Vorschlag: dieselben 6 Tasks, gleicher Seed, erwartet ~$0.05–0.10.
- `eval/score.py` rechnet Streuzitate noch nicht ein und kennt bei `--answers` keine Constraints.
- Ticket-Tasks (t05, t16): das Modell findet die nötigen Dateien nicht zielstrebig – Kandidat für Plan B1.
