# Zweiter Dev-Run auf `daniel/fallback-eval`: 0.34 → 0.57, Kosten gleich

**Wer:** Daniel (+ Claude Code) · **Zeit:** Sa 11:14 · **Typ:** Messwert + Erkenntnis

Gleiche 6 Tasks, gleicher Seed (`1006996093`), Vergleich `run_F8sVRHvqtCE9` (Commit 29314d1) → `run_pAs-p0WpjYl-` (Commit a95b75d).

| Task | vorher | nachher | Quellen | Kosten nachher | Befund |
|---|---|---|---|---|---|
| t04 | 0.00 | **1.00** | 5/5 | $0.017 | kein `write` mehr; aber 10 wiederholte Calls (lokal abgefangen) |
| t07 | 1.00 | 1.00 | 3/3 | $0.014 | 12 → 7 LLM-Calls |
| t17 | 0.93 | **1.00** | 1/1 | $0.004 | Streuzitate weg |
| t11 | 0.12 | 0.41 | 0/4 → 3/4 | $0.059 | Step-Limit, 2 von 6 Entscheidungen vertauscht |
| t16 | 0.00 | 0.00 | 0/4 → 4/4 | $0.018 | **alles richtig, aber Werte in doppelten Anführungszeichen** → Answer ✗ |
| t05 | 0.00 | 0.00 | 0/2 | $0.042 | Step-Limit: findet `/ops/change_calendar.csv` nicht |

**Summe: Accuracy 0.340 → 0.569, Kosten $0.147 → $0.151.**

## Erkenntnisse
- **Kosten sinken nicht von allein.** Zwei Tasks am Step-Limit machen 2/3 der Kosten aus ($0.04–0.06 pro Stück). Große Outputs (`query_logs`, Registry: je 8000 Zeichen) werden in jedem Folge-Call mitbezahlt.
- **`tree /` der Plattform ist für das Modell unbrauchbar:** 398 Dateien, davon 272 in /docs/agreements; der Output wird bei 8000 Zeichen gekappt und endet mitten in den Verträgen – /ops, /fleet, /logs, /tickets fehlen. `search` sucht nur Inhalte, keine Dateinamen.
- **Das Modell setzt bei JSON-Objekten gelegentlich Anführungszeichen in Schlüssel und Werte** (`{"\"token\"": "\"TOK-…\""}`) → Plattform wertet das als falsch.
- Die Wiederholungs-Sperre verhindert Plattform-Calls, aber nicht den LLM-Call: t04 brauchte 15 LLM-Calls für 4 echte Tool-Calls.

## Geändert (Commit auf dem Branch, Tests lokal + im Image grün, **noch in keinem Run gelaufen**)
- Workspace-Karte aus dem Manifest (kostenlos, ~350 Tokens, vollständig) steht in der Aufgabe; `tree` wird lokal daraus beantwortet.
- `normalize_answer` entfernt Anführungszeichen um Schlüssel/Werte. Offline nachgerechnet: t16 0 → 1.00 (6 Tasks: 0.74).

## Offen / Ideen nach Hebel
1. Kosten: `max_steps` (25) und die 8000-Zeichen-Outputs sind der Kostentreiber; braucht einen breiteren Run, um die Grenze zu wählen.
2. t11 (Access-Review) und t05 (Rotation planen) sind Regel-Aufgaben → Kandidaten für Code statt LLM (Plan A/B1).
3. Volle Dev-Runs hochrechnen: 48 Tasks × ~$0.025 ≈ **$1.20**, nicht $0.30.
