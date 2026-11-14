# Dritter Dev-Run (frische Tasks): 0.80 – Grader-Formel für Zitate gefunden

**Wer:** Daniel (+ Claude Code) · **Zeit:** Sa 11:27 · **Typ:** Messwert + Erkenntnis

## Messwert
`run_tkSRAC-SpUlz`, neuer Seed, `--limit 8`, Commit auf `daniel/fallback-eval`: **lokale Accuracy 0.80, Kosten $0.244** (119 Calls, 1.23 M Input-Tokens, $0.031/Task). Plattform-`cost_score` für diesen Run: 1.0.

| Task | Score | Befund |
|---|---|---|
| t02, t05, t07 | 1.00 | |
| t03 | 0.83 | Antwort ✓, Quellen 4/4, aber 14 Zitate → sources_score 0.43 |
| t04 | 0.78 | Regel über 800 CSV-Zeilen von Hand gelesen: 7/8 richtig, $0.05 |
| t01 | 0.69 | Draft-Task, Inhalt teilweise |
| t06 | 0.68 | MCP-Audit, 4/5 Server |
| t08 | 0.42 | Access-Review, Hälfte der Entscheidungen falsch |

## Erkenntnis 1: so rechnet der Grader Zitate (wichtig für alle)
```
n      = Anzahl Zitate (mehrere Treffer auf dieselbe erwartete Quelle zählen einmal)
over   = max(0, n − (expected + 2))
sources_score = (hit / expected) × (1 − over / n)
```
Auf 18 von 20 bewerteten Tasks aus drei Runs exakt (die 2 Abweichungen sind Alternativ-Zitate für Transfers, nicht die Formel). **Folge: bis „erwartet + 2“ ist jedes Zitat gratis, danach kostet jedes weitere seinen Anteil.** `eval/score.py` rechnet jetzt so.

## Erkenntnis 2: Tabellen-Regeln gehören in Code
Aufgaben wie „alle Zeilen, für die A und B und C gilt“ (requests.csv: 55 erwartete Quellen im ersten Run) liest das Modell seitenweise und verzählt sich. Neues lokales Tool `filter_rows(path, where=[{column, op, value}])` – offline mit den Bedingungen von t04 gegen die echte Datei geprüft: exakt die 8 erwarteten IDs, 1 Call statt 13.

## Geändert (Tests lokal + im Image grün; **Wirkung aufs Modell noch in keinem Run gemessen**)
- Zitate im Budget „Antwortwerte + 2“: max. 2 pro Wert und Datei, keine nackten csv/jsonl/xlsx-Pfade, docx-`line` → `paragraph`, CSV → `record` außer Zeilen mit Zeitstempel in Spalte 1.
- Lokale Tools `filter_rows` und `sha256` (Runbook: Token-Abgleich per `sha256_12`).
- /AGENTS.md, die darin genannten .md-Dateien und das Ticket mit `status: open` liegen der Aufgabe bei (geschlossene Tickets nicht). Nicht-Ticket-Tasks haben kein /tickets/.
- Tool-Ergebnisse als Text/Tabelle statt JSON (−12 % Zeichen auf kleinen Outputs, mehr bei Log-Abfragen).

## Offen
- Kosten: 10k Tokens pro Call. Voller Run ≈ 48 × $0.03 ≈ $1.50. Hebel: weniger Calls (Vorladen, filter_rows), `max_steps`.
- Regel-Aufgaben mit Schlussfolgern (Access-Review t08/t11, MCP-Audit t06) bleiben bei ~0.4–0.7.
- Dev-Budget durch Daniels drei Runs: ~$0.55.
