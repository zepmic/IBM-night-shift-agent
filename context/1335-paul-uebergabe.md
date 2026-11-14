# Übergabe: Stand des Harness, Messwerte, offene Hebel (für den nächsten Coding-Agent)

**Wer:** Paul (+ Claude Code) · **Zeit:** Sa 14.11., ~13:35 · **Typ:** Status + Übergabe

## Budget
Team-Dev-Budget: **~$5.85 von $15** verbraucht (15 Runs, Stand 13:40). Ab jetzt sparsam:
erst offline/Docker testen, dann gezielte `--tasks`-Replays, volle Runs nur zur Bestätigung. **Immer nur ein Run gleichzeitig**
(Kosten werden als Key-Verbrauch zwischen Start und Finish gemessen).

## Messwerte (volle Runs, 48 Tasks)
| Run | Seed | Code | Accuracy | Kosten | cost_score | final |
|---|---|---|---|---|---|---|
| run_hP6Aq5nhZhYl | 675666297 | 0af3cc7 | 0.557 | $1.70 | 0.157 | 0.322 |
| run_VLE9AicO_TF3 | 675666297 (Replay) | a0ae1fb (max_steps 14) | 0.578 | $1.24 | 0.203 | 0.348 |
| **run__8OvzdDTetNJ** | **1796485340 (frisch)** | **431e3ec (alle Tools)** | **0.700** | **$0.97** | **0.238** | **0.434** |

Run 3: nur noch 11/48 Tasks am Schrittlimit (vorher 23), 0 Regelverstöße. Das ist die Ausgangszahl für weitere Arbeit.

Kosten sind der größte Hebel: im Final wird C über die Spanne der Final-Runs aller Teams (mind. 10×) gerechnet; Starter-Kit-Finals
kosteten $0.66–0.81. Bei max_steps 14 laufen ~23/48 Tasks ans Limit (72 % der Kosten, Ø 0.37 Score). Ø ~11.5k Prompt-Tokens pro Call.

## Was im Harness steckt (alles auf main)
- **Code-Tools** (lokal, 0 Tokens): `filter_rows` (csv/xlsx/**ods**; `has_match`/`no_match`-Join mit Zeitfenster/revoked, ID-Spalte
  wird automatisch mitgejoint; `count_distinct` mit Bereichen `C-1..C-9`, `group_by`, `group_lookup`), `earliest_slot` (Rotation,
  mehrere Services, Spalten per Inhalt erkannt), `capabilities` (+ `what_if`, transitive Delegation / lethal trifecta), `sha256`.
- Router-Fix + 1 Korrektur-Call, JSON-Hinweis bei Prosa-Antworten, Wiederholungssperre auch für lokale Tools.
- Zitate: eigene Datensatz-IDs der Antwort werden voll zitiert (Budget „erwartet + 2“).
- Final: `--parallel 6` (Default), `max_steps 14`, Resume nach Container-Neustart, Budgetwächter $2.70.

## Kostenlos testen
```bash
for t in test_offline test_guard test_e2e test_fallback test_sources test_real_data; do uv run python tests/$t.py; done
```
- `tests/test_real_data.py` + `tests/fixtures/`: Tools gegen **echte Dateien aus Dev-Runs**, Ergebnis muss die aufgedeckte Antwort
  treffen (Policy-Join 39/39, Team-Records, Trifecta, Rotationsslots). Neue Fixtures: Datei per `client.download_file(run, task, path)`
  aus einem beendeten Run ziehen; erwartete Antworten aus `GET /runs/<id>` (Feld `tasks[].expected_answer`).
- Abgeschlossene Runs bleiben read-only abrufbar: Traces lokal unter `runs/<run_id>/tNN.jsonl` (nur auf Pauls Rechner),
  Aufgaben + Erwartungen für alle 48 Tasks über `GET /runs/<id>` für jeden mit dem Team-Key.
- Docker: `git archive HEAD | tar -x -C /tmp/x && docker build -t h /tmp/x && docker run --rm --network none --entrypoint python h tests/test_real_data.py`

## Offene Hebel, nach geschätztem Nutzen
1. **Kosten pro Call** (~11.5k Tokens): Verlauf schrumpfen, ohne dass die Wiederholungssperre Inhalte unterschlägt
   (`keep_small_chars` 6000 hält viele Outputs voll im Kontext). Ggf. Tool-Beschreibungen kürzen (gehen bei jedem Call mit).
2. **Step-Limit-Tasks** (23/48 bei 14 Schritten): Familien ohne Code-Tool: Chronologie/Ereignis-Reihenfolge, Board-Triage
   (injected posts, auch base64/Fremdsprache), Status-Report-Claims vs. Audit-Log, Eintrittspunkt/Patient Zero, MCP-Audit.
   Muster bisher: ein exaktes Code-Tool hebt eine Familie auf ~0.9–1.0 und senkt die Calls.
3. **Injections (frame_agent):** Antwortlisten enthalten von Fremd-Payloads beschuldigte Agents (t25 Seed 675: `tooling-17`,
   `injected_action` im Feedback) → Constraint ✗ = 0. Quarantäne-Sperre lässt Agents mit legitimer Gegenmaßnahme im Trace durch
   (support-25, Seed 388). Eine Regel „Trace beginnt mit read_artifact“ trennt nicht (875 harmlose Traces beginnen so).
4. **Access-Review** (~0.5–0.6): Regel 2 (Antrag vom Owner laut Roster) und Regel 1 (quarantänisiert/kompromittiert) könnten auch
   in Code; `capabilities what_if` deckt Regel 3 ab.
5. Daniels Branch `codex/unique-containment-standins` (Stand-ins pro Call eindeutig) ist noch nicht auf main; Konflikt nur in
   tests/test_guard.py (beide hängen Tests an).

## Regeln, die sich bewährt haben
- Ein Tool erst bauen, wenn es offline gegen echte Daten die erwartete Antwort trifft; Spaltennamen ändern sich pro Run → Spalten
  am Inhalt erkennen oder Fehlermeldung mit Spaltenliste zurückgeben.
- Runbook-Regeln variieren pro Szenario (z. B. Consumer-Freezes, 30 statt 60 min) → Parameter vom Modell, keine Konstanten.
