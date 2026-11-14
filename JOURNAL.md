# Journal

One entry per design decision, newest last: whenever someone on the team makes or overrides a design call, and when
the coding agent makes one. Mark `decided_by` honestly; the content isn't scored. The journal feeds your 18:00 story
page, and your upload needs at least one entry of your own to be eligible for prizes.

Format example (ignored: it sits in a code block). Write your entries below it, outside the block:

```markdown
## 11:42 · Jev pre-filter for long documents
- decided_by: human        # human | ai | both
- why: t07 L3 at 0.31; reading every document with the main model costs $0.04/task
- rejected: regex filter (misses base64), main model only (cost)
- evidence: run_abc → run_def, t07 0.31 → 0.78, cost −40 %
```

## 09:30 · Strategie: Plan A + B1 + B4
- decided_by: human
- why: Kosten sind die Hälfte des Multiplikators (`A · (0.5 + 0.5·C)`), falsche Aktionen setzen Tasks auf 0, Dev-Runs zeigen die Lösungen → Code statt LLM wo möglich, Guardrails in Code, Offline-Eval. B1 (ein LLM-Call übersetzt die Instruktion in ein JSON-Programm) drückt die Kosten, B4 (Break it) ist ein zweiter Gewinnweg.
- rejected: reine Agent Loop (teuer, unberechenbar), B2 LLM-schreibt-Python / B3 Embeddings / B5 Voting / B6 Jev vorerst (nur bei konkreter Lücke)
- evidence: noch keine Runs; Details in plans/plan-a-solide.md und plans/plan-b-out-of-the-box.md

## 09:45 · Repo-Struktur: Starter Kit + Team-Kontext
- decided_by: both
- why: alle Coding-Agents im Team brauchen denselben Kontext sofort; Kit-Dateien bleiben unverändert im Root, damit Updates der Veranstalter leicht übernommen werden können
- rejected: eigenes Projekt neben dem Kit (doppelte Pflege), Team-Infos im Kit-README (Konflikte bei Kit-Updates)
- evidence: challenge/ (Veranstalter-Infos wörtlich), context/ (Team-Wissen), plans/, TEAM.md; AGENTS.md = Kit-Regeln + Team-Abschnitt

## 10:50 · Fallback-Submit: jeder Task wird genau einmal abgegeben
- decided_by: both
- why: Mock-Test (context/1100) zeigte: scheitert der LLM-Call, gibt der Agent nichts ab → Task sicher 0. Im Final ($3-Limit → 403, 30 Min) wären das alle Rest-Tasks. Jetzt: letzter vom Modell versuchter Submit (erst mit, dann ohne Quellen), sonst `UNSUPPORTED`/null – laut Task API die einzige Verweigerung, die ohne Antwort punkten kann. Nie ein schreibendes Tool im Fallback.
- rejected: `OK` mit leerer Antwort (immer 0), `DENIED_SECURITY`/`NEEDS_CLARIFICATION` (brauchen Absender bzw. Agent-IDs, sonst 0), weiterer LLM-Call im Fehlerfall (bei 403 sinnlos, kostet Zeit)
- evidence: tests/test_fallback.py (Mock, kein Key): 2/2 Mock-Tasks abgegeben, 0 Tool-Calls; noch kein Dev-Run

## 10:51 · Offline-Eval aus Dev-Runs (eval/collect.py, eval/score.py)
- decided_by: both
- why: $15 Dev-Budget; jeder beendete Dev-Run verrät expected_answer/expected_sources in finish.json. Daraus ein lokales Fallset bauen und Antworten kostenlos mit der Score-Formel nachrechnen (answer und sources getrennt), statt für jede Quellen-Idee einen neuen Run zu bezahlen. Kosten pro Task stehen jetzt im Trace (`end`-Event).
- rejected: Fallset ins Repo committen (enthält Dev-Antworten → Overfitting-/Regelrisiko; bleibt in runs/, git-ignored), exakte Nachbildung des Plattform-Graders (unbekannt: Listen-Teilpunkte = F1 angenähert, Action-Tasks und Constraints kommen aus dem Plattform-Grade)
- evidence: tests/test_eval.py mit Fake-finish.json: Baseline-Fall (Antwort ✓, Quellen 1/4) → lokal 0.775, Plattform 0.77

## 10:54 · Quellen: Evidence-Ledger aus Tool-Ergebnissen (sources.py)
- decided_by: both
- why: Baseline t01: Antwort ✓, aber Quellen 1/4 → 0.77 statt 1.0. Ursache: Quellen kamen nur aus dem Gedächtnis des Modells, alte Tool-Outputs werden auf 300 Zeichen gekürzt, `clean_sources` prüft nur Typen. Jetzt führt der Harness jede gelesene Zeile/Record/Seite/Absatz/Zeile-im-Sheet mit und ergänzt beim Submit deterministisch die Stellen, an denen ein ID-artiger Wert der Antwort wörtlich steht – nur wenn er in der Datei höchstens 2× vorkommt (sonst mehrdeutig → nichts), max. 4 Zusätze. Zitate auf Dateien, die es laut Manifest nicht gibt, fliegen raus. Kein LLM-Call, $0.
- rejected: alle gelesenen Dateien zitieren (Streuzitate werden bestraft), zweiter LLM-Call „welche Quellen?“ (Kosten), Pfade/Dateinamen aus dem Dev-Szenario fest verdrahten (Overfitting, Final hat andere Oberfläche)
- evidence: tests/test_sources.py (Mock + nachgebauter Baseline-Fall); echter Beleg steht aus → ein Dev-Run mit/ohne `--no-auto-sources` auf gleichem Seed

## 11:00 · Deadline-Schutz und kostenloser End-to-End-Test im Container
- decided_by: ai
- why: Im Final wird der Container nach 30 Min gestoppt, niemand kann eingreifen; 25 Schritte × langsame Modell-Calls (p95 9 s, laut FINAL_RUN.md bis 67 s) × 48 Tasks können das reißen. 3 Min vor der Plattform-Deadline bekommt jeder laufende Task einen erzwungenen Submit, 60 s später nur noch den Fallback. Dazu spielt der Mock-Server jetzt ein Modell-Skript (POST /chat/completions), damit die ganze Kette main.py → Task API → Modell → Submit im Image ohne Keys und ohne Netz testbar ist.
- rejected: fester Zeitbudget-Zähler pro Task (bestraft schwere Tasks, obwohl Zeit nicht gewertet wird), echte Modell-Calls für Container-Tests (Dev-Budget)
- evidence: tests/test_fallback.py (6b), tests/test_e2e.py lokal und im Image mit `--network none`: 2/2 Mock-Tasks 1.0, ergänzte Quellen im Trace

## 11:07 · Nach dem ersten Dev-Run: Wiederholungs-Sperre, Zitate nach Dateityp, kein `write` als Notizblock
- decided_by: both
- why: run_F8sVRHvqtCE9 (6 Level-1-Tasks, Seed der Baseline): 0.34 lokal, $0.147 statt geschätzter $0.04. Traces zeigen: (1) 3 von 6 Tasks am Step-Limit, weil alte Tool-Outputs auf 300 Zeichen gekürzt wurden und das Modell AGENTS.md/Runbook/dieselben CSVs 3–5× neu las → Outputs ≤ 6000 Zeichen bleiben jetzt im Kontext, identische Read-only-Calls beantwortet der Harness lokal. (2) Der Grader will CSV-Tabellen per `record` (107 von 114 erwarteten CSV-Quellen), JSON nur per Pfad (18/18), Log-Archive per Zeile; das Modell zitiert Zeilen → Harness rechnet Zeile→Record um (Kopfzeile entscheidet: erste Spalte `id`/`*_id`), JSON → nur Pfad, /AGENTS.md-Zitate raus (Streuzitate kosteten t17 0.075). (3) t04: Antwort ✓, Quellen 5/5, aber Score 0, weil das Modell ein Python-Skript per `write` „ausführen“ wollte → Prompt sagt jetzt klar: keine Code-Ausführung, ein einziger schreibender Call ohne Auftrag kostet den Task.
- rejected: alten Verlauf nie kürzen (Log-Abfragen mit 8000 Zeichen würden jeden Folge-Call verteuern), schreibende Tools hart sperren (Action-Tasks brauchen sie; ob ein Task sie erlaubt, lässt sich nicht per Regex aus unbekannten Final-Formulierungen lesen), Datei-/Spaltennamen des Dev-Szenarios verdrahten
- evidence: run_F8sVRHvqtCE9: t07 1.00, t17 0.92, t04 0.00 (Constraint), t05/t11/t16 am Step-Limit. Ledger-Zusätze: 4 Treffer (t04), 2 Fehlgriffe. Offline-Replay derselben Zitate mit neuer Logik: Streuzitate 14 → 7 bei gleichen Treffern. Wirkung von (1) und (3) noch nicht gemessen – braucht einen zweiten Run.
