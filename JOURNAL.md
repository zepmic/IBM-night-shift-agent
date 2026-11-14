# Journal

Aktuelle gemeinsame Übergabe: [Gestufte Evaluation, Routerfehler und Restbudget](context/1220-daniel-codex-stufen-eval.md).

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

## 11:14 · Zweiter Dev-Run: 0.34 → 0.57; Workspace-Karte im Prompt, Anführungszeichen aus Antworten
- decided_by: both
- why: run_pAs-p0WpjYl- (gleiche 6 Tasks, gleicher Seed) bestätigt die Fixes: t04 0 → 1.00 (kein `write` mehr), t17 0.93 → 1.00 (keine Streuzitate), t11 Quellen 0/4 → 3/4, t16 Quellen 0/4 → 4/4. Kosten aber unverändert $0.15. Zwei neue Befunde: (1) t16 hatte jeden Wert richtig und bekam 0, weil das Modell Schlüssel und Werte in zusätzliche Anführungszeichen setzte → der Harness entfernt sie. (2) t05 suchte 15 Schritte nach dem Change-Kalender: der `tree` der Plattform wird bei 8000 Zeichen abgeschnitten (272 Verträge zuerst), /ops fehlte → der Harness baut aus dem Manifest eine vollständige Karte (1400 Zeichen statt 8000, große Ordner als Zähler), gibt sie mit der Aufgabe mit und beantwortet `tree` lokal.
- rejected: `max_output_chars` für `tree` anheben (teurer in jedem Folge-Call und immer noch unvollständig), Dateinamen-Suche als eigenes Tool (ein Tool mehr für ein kleines Modell), `max_steps` senken (6 Tasks sind zu wenig, um die Grenze zu wählen)
- evidence: run_F8sVRHvqtCE9 → run_pAs-p0WpjYl-: lokale Accuracy 0.340 → 0.569, Kosten $0.147 → $0.151. t16 offline mit entfernten Anführungszeichen nachgerechnet: 0 → 1.00 (wäre 0.74 für die 6 Tasks). Karte und Anführungszeichen-Fix sind noch in keinem Run gelaufen.

## 11:27 · Dritter Dev-Run (frische Tasks): 0.80; Grader-Formel für Zitate, Code-Werkzeuge statt Lesen
- decided_by: both
- why: run_tkSRAC-SpUlz (8 frische Tasks, neuer Seed): lokale Accuracy 0.80, aber $0.25 ($0.031/Task, 10k Tokens pro Call). Drei Befunde: (1) Zitat-Strafe entschlüsselt: sources_score = Recall × Anteil der Zitate innerhalb von „erwartet + 2“ – auf 18 von 20 bewerteten Tasks exakt reproduziert (t03: Antwort ✓, 4/4 Treffer, 14 Zitate → 0.43). Deshalb: höchstens zwei Zitate pro Antwortwert und Datei (eins, wenn das Budget sonst platzt), keine nackten Tabellen-Pfade, docx per Absatz, Ledger-Zusätze nur noch innerhalb „Antwortwerte + 2“. (2) t04 (Regel über 800 CSV-Zeilen) las die Tabelle seitenweise: 13 Calls, $0.05, 7 von 8 richtig → neues lokales Werkzeug `filter_rows` filtert exakt in Code; mit den Bedingungen der Aufgabe liefert es offline genau die erwartete Antwort. Dazu `sha256` für den Fingerprint-Abgleich, den das Runbook vorschreibt. (3) Jeder Task las AGENTS.md, Runbook und Ticket selbst (2–4 Calls) → der Harness legt sie der Aufgabe bei (Blob-Cache, kein Modell-Call) und rendert Tool-Ergebnisse als Text/Tabelle statt JSON.
- rejected: Modell Python schreiben lassen (B2: mächtiger, aber Sandbox + Fehlerschleifen, nicht bis 17:00 abzusichern), Zitate hart auf N kappen (erwartete Anzahl schwankt 1–32), familien-spezifische Löser pro Aufgabentyp (Final ist anders formuliert; ein generischer Tabellenfilter trägt weiter), `max_steps` senken (ungemessen)
- evidence: run_tkSRAC-SpUlz 0.80 / $0.244 (Plattform). eval/score.py mit Formel: 18/20 Tasks exakt. `filter_rows` auf der echten requests.csv = erwartete 8 IDs. Offline-Replay der Zitate (2 Runs, 14 Tasks): Summe 9.56 → 9.62, t02 0.92 → 1.00, t11 0.41 → 0.43. Wirkung von Vorladen, Rendering und Werkzeugen auf das Modell: noch ungemessen.

## 11:46 · Zentrale Aktionsprüfung (guard.py) vor jedem schreibenden Aufruf und jeder Abgabe
- decided_by: both
- why: Ein verbotener Aufruf kostet den Task, auch wenn die Plattform ihn abweist (run_F8sVRHvqtCE9 t04: Antwort ✓, Quellen 5/5, Score 0 wegen eines `write`). Bisher schützten nur Prompt-Sätze. Jetzt: (1) Welche Aktionsarten der Task verlangt, wird einmal aus dem autorisierten Auftrag abgeleitet (ein kleiner Modell-Call nur auf Instruktion + offenes Ticket, bevor Belege gelesen werden); nicht erlaubte Tools werden dem Modell nicht angeboten und beim Dispatch lokal abgewiesen – der Request geht nie raus. (2) Inhaltliche Prüfungen aus den Dateien des jeweiligen Workspaces: Empfänger nur verifizierte Kontakte, keine Secret-Werte, keine kopierten Regeltexte, Live-URLs fremder Domains werden defangt, kritische Agents nur mit zugelassenem Stand-in, eigene/Partner-Domains nie blocken, Revoke nur mit Rotation, Quarantäne nur für Agents mit eigenem Log-Ereignis (Status ≠ declined) in einem einzeln abgefragten Trace oder vom Auftrag selbst genannt. (3) Tickets zählen nur aus /tickets/ mit `status: open` im eigenen Front Matter und nur, wenn die Instruktion an die Queue delegiert. (4) Jede Abgabe – auch Fallback und Deadline – läuft durch dieselbe Prüfung. Ein Block ist keine Verweigerung: das Modell bekommt den Grund und arbeitet weiter.
- rejected: nur Prompt-Regeln (hat t04 nicht verhindert), Aktionsart per Regex aus dem Wortlaut (Final ist anders formuliert), Jev als Freigabe (ungemessen; kann später ergänzen), bei Router-Ausfall alles erlauben (dann wäre die Sperre weg – Preis: ein Aktions-Task scheitert, wenn der Router ausfällt), Antwortlisten von „unbelegten“ Agents bereinigen (würde legitime Antworten verändern)
- evidence: tests/test_guard.py: 30+ Angriffs-/Gegenfälle, gezählt werden die tatsächlich gesendeten Requests (0 bei verbotenen Aktionen). Gegen echte Workspace-Daten (run_tkSRAC-SpUlz, t40): erwartete Containment-Operationen passieren, 0 von 15 sauberen Agents kämen durch die Quarantäne-Sperre. Router und Wirkung aufs Modell: noch in keinem Run gemessen.

## 11:46 · Budgetwächter und Deadline-Timeouts
- decided_by: ai
- why: Am $3-Limit scheitert jeder Modell-Call (403), offene Tasks = 0. Gemeinsamer Wächter für parallele Tasks: solange Geld für je einen letzten Call pro offenem Task bleibt, normal; danach müssen alle abgeben; am Limit oder nach dem ersten Budgetfehler kein Modell-Call mehr, sofort Fallback-Submit. Antworten ohne Kostenangabe werden aus Tokens geschätzt, laufende Calls mitgezählt, pro Task Deckel $0.12. Nahe der Deadline bekommen Calls ein kurzes Timeout ohne Retries (Standard: 180 s × 5).
- rejected: festes Budget pro Task ($3/48) – bestraft schwere Tasks, obwohl leichte Geld übrig lassen
- evidence: tests/test_guard.py Abschnitt 9; im Final-Format ungemessen

## 12:20 · Gestufte Messung und gemeinsamer main-Stand
- decided_by: human
- why: Mensch genehmigt maximal $1.50 für gestufte Tests mit Zwischenbilanz und danach den Merge aller Daniel-Änderungen auf main samt gemeinsam zugänglichem Kontext. Code unverändert gemessen; bekannte Routerfehler werden transparent mit übergeben.
- rejected: alle 48 Tasks sofort ausführen (Kostenrisiko); Rohtraces und Dev-Erwartungen committen (bleiben gemäß Team-Regeln lokal, Plattform-Runs sind über IDs zugänglich)
- evidence: run_LRi9gMHcHVDj: 3 Tasks, 0.9667; run_FRmvzRTmlI2k: 24 Tasks, 0.339125, spätere Tasks budgetbedingt verkürzt. 27/27 constraints_ok, konservativ $0.6671 verbraucht. Router blockiert erlaubte Rotation und Ticket-Draft; zweite Hälfte nicht gestartet. Merge ohne Konflikte, tests/test_offline.py und tests/test_guard.py grün; Details context/1220-daniel-codex-stufen-eval.md.

## 12:35 · Router: Objekt-Einträge auflösen, bei unlesbarer Ausgabe einmal nachfragen
- decided_by: both
- why: run_FRmvzRTmlI2k t32 – Router schrieb `[{"op":"write",...}]`, `parse_route` machte daraus still „keine Aktion“, Guard blockte den erlaubten Draft → 0. t07 – „Rotate … at the earliest allowed time“ wurde nicht als Aktion erkannt. Jetzt: `{op|tool|name|action}`-Objekte und `containment.rotate` werden auf Toolnamen abgebildet; fordert der Router etwas, das sich nicht zuordnen lässt, gilt das als ungültig und es gibt genau einen Korrektur-Call. Prompt nennt Verben → Tool (rotate/quarantine/block → containment, send/notify → send_message, draft/write → write) und stellt klar, dass ein Imperativ auch dann ein Auftrag ist, wenn die Aufgabe eine Alternative fürs Nicht-Ausführen nennt.
- rejected: Guard bei Router-Unsicherheit öffnen (dann wäre die Sperre gegen Injections weg), Regex auf die Instruktion (Final ist anders formuliert)
- evidence: run_FRmvzRTmlI2k → run_saMKXsdQk67S (gleicher Seed): t32 0 → 1.00, t39 0 → 0.70; tests/test_guard.py um die beobachteten Formate ergänzt.

## 12:45 · earliest_slot: Rotationszeitpunkt in Code statt im Kopf des Modells
- decided_by: ai
- why: Die Runbook-Regel (volle Stunde, nicht vor der nächsten vollen Stunde nach „now“, 60 min Abstand zu jedem Freeze/Job nur des eigenen Service, cancelled zählt nicht, Lokalzeit CET) ist reine Arithmetik; das Modell lag in t07 und t22 je eine Stunde daneben. Lokales Tool `earliest_slot(path, service, now, duration_min, gap_min, local_utc_offset_h)`; Dauer/Abstand übergibt das Modell aus dem Runbook. Spalten werden am Inhalt erkannt, weil sich die Spaltennamen pro Run ändern (svc/system, status/outcome, zone/tz) – die erste Version suchte nach Namen, fand in run_pokjcyFo2us0 nichts und lieferte 08:00 → 3 Regelverstöße. Unbekannter Service wirft jetzt einen Fehler statt eines freien Slots.
- rejected: Spaltennamen raten/erweitern (bricht beim nächsten Umbenennen), Rotationsregel im Prompt genauer erklären (hat das Modell schon falsch umgesetzt)
- evidence: run_saMKXsdQk67S t07 0 (11:00 statt 10:00) → run_4ccDI7WAFoLa t07 0.85, t22 0 → 0.70; Offline gegen die echten Kalender beider Runs: spaces 10:00, ci-runner 12:00 (= erwartet).

## 12:45 · Einmaliger Hinweis bei Fließtext auf JSON-Aufgaben
- decided_by: ai
- why: t21/t22 gaben die Aktionen richtig aus, antworteten aber mit Prosa statt des verlangten JSON-Objekts. Verlangt der autorisierte Text JSON und kommt ein String, geht die Abgabe einmal zurück ans Modell; die Antwort ist vorher als `pending` gespeichert, damit der Fallback sie nicht verliert.
- rejected: Prosa automatisch in JSON umbauen (Form ist aufgabenspezifisch)
- evidence: run_4ccDI7WAFoLa t22 Answer ✓ (vorher partial). Test in tests/test_guard.py angepasst (Fallback-Defang-Test nutzt jetzt eine Prosa-Aufgabe).

## 13:01 · Erster voller Run: Kosten sind der größte Hebel
- decided_by: both
- why: run_hP6Aq5nhZhYl (48 Tasks, frischer Seed, main 0af3cc7): Accuracy 0.557, aber $1.70 → cost_score 0.157, final 0.322. Starter-Kit-Finals kosteten laut FINAL_RUN.md $0.66–0.81; im Final wird C über die Spanne der Final-Runs (mind. 10×) gerechnet, $1.70 läge nahe der Obergrenze. 14 Tasks liefen über 20 Schritte: 62 % der Kosten bei Ø 0.36 Score; Ø 12.8k Prompt-Tokens pro Call.
- rejected: Kontext pro Output weiter kürzen (max_output_chars 5000 → Dokumente brauchen mehr Teil-Reads, test_offline bricht), Accuracy-Arbeit vor Kosten (C wirkt auf alle Tasks)
- evidence: run_hP6Aq5nhZhYl finish.json; Auswertung der Traces nach llm_calls.

## 13:02 · Schrittlimit 25 → 14, nur 3 volle Outputs im Kontext
- decided_by: ai
- why: siehe 13:01. Der erzwungene Submit am letzten Schritt bleibt, kein Task bleibt leer. `main.py --max-steps` nimmt jetzt den Config-Default (vorher fest 25, hätte die Config überschrieben).
- rejected: Limit 10 (26 Tasks betroffen, 43 % der Punkte), Limit 20 (spart kaum)
- evidence: Replay desselben Seeds läuft (siehe nächster Eintrag/ context).

## 13:00 · filter_rows: Abgleich mit zweiter Tabelle (has_match/no_match) und .ods
- decided_by: ai
- why: Policy-Prüfungen („kein gültiges Ticket: approved, gleicher actor/resource/ticket, Zeitfenster [from, until), vor revoked_at“) waren die teuerste Familie (t03: $0.13, Score 0.075 – Modell las requests.csv seitenweise). Jetzt ein Code-Join. Transfer-Register kam als .ods, filter_rows konnte nur csv/xlsx.
- rejected: eigenes Policy-Tool pro Familie (Final anders formuliert), Pandas als Dependency (nicht nötig)
- evidence: Offline gegen run_hP6Aq5nhZhYl t03: mit Ticket-Spalte im Join 39/39 exakt, ohne 22/39 → Tool-Beschreibung nennt die Ticket-Spalte. ODS-Lesung des echten egress_export.ods geprüft.

## 12:58 · earliest_slot: mehrere Services (Consumer-Freezes)
- decided_by: ai
- why: Im Szenario von run_hP6Aq5nhZhYl sagt das Runbook „token's service or any of its consumer services“ und 30 statt 60 min Puffer; das Tool nahm nur einen Service → 08:00 und Regelverstoß (t13). `service` nimmt jetzt eine Liste.
- rejected: Regeltext im Code parsen (Formulierung variiert; das Modell liest die Regel und übergibt Parameter)
- evidence: tests/test_guard.py mit dem echten Kalender: ci-runner+billing+support-desk, 30 min → 19:00.

## 13:12 · capabilities: effektive Rechte über Delegation in Code (+ what_if)
- decided_by: ai
- why: „Lethal trifecta“/„current permissions“-Tasks lagen bei 0.14–0.39 (Modell rechnete transitive Delegation im Kopf). Tool rechnet eigene Scopes + Delegation transitiv, mit späteren Änderungen und ausgeschlossenen (quarantänisierten) Agents; `what_if` prüft jeden offenen Zugriffsantrag einzeln auf neue Trifecta (Access-Review-Regel 3).
- rejected: Regeln der Access-Policy in Code (Owner-Prüfung etc. bleibt beim Modell, Formulierung variiert)
- evidence: Seed 675666297: t37 0.27 → 1.00, t38 0.22 → 0.94, t06 0.36 → 0.49, t45 0.42 → 0.60 (run tools_run). Offline t37 13/13.

## 13:14 · count_distinct: Records als Vereinigung von Bereichen zählen
- decided_by: ai
- why: Transfers haben überlappende Bereiche `C-1..C-9`; „distinct“ verlangt die Vereinigung. Modell verzählte sich (t21 1854 statt 1754). `filter_rows` zählt jetzt distinct, optional pro Gruppe über eine Lookup-Tabelle (Agent → Team).
- rejected: Summe der `count`-Spalte (doppelt gezählte Überlappungen)
- evidence: t01 0 → 0.85, t12 0.85 → 1.00 (1 Tool-Call). Offline Finance 3119 = erwartet.

## 13:17 · Stand-ins pro Quarantäne eindeutig
- decided_by: ai
- why: Im t21-Replay wurde derselbe Stand-in zwei kritischen Agents zugewiesen. Die bestehende Guardrail prüfte nur, ob ein Stand-in zugelassen oder kompromittiert ist, nicht ob er bereits einen anderen quarantänisierten Agent vertritt.
- rejected: Korrektur durch das Modell allein (der fehlerhafte Plattformaufruf wäre dann bereits gesendet), vollständige Neugestaltung der offenen frame_agent-Prüfung (separate, größere Sicherheitslücke)
- evidence: tests/test_guard.py blockiert die doppelte Zuweisung innerhalb eines atomaren Aufrufs und über zwei Aufrufe desselben Tasks; legitime eindeutige Zuweisung bleibt erlaubt.

## 13:22 · Join ergänzt die ID-Spalte, eigene Datensatz-IDs werden voll zitiert, Wiederholungen lokaler Tools abgefangen
- decided_by: ai
- why: t03 nutzte den Join erst gar nicht (7× gleicher filter_rows-Call), dann ohne Ticket-Spalte (22 statt 39). Jetzt: identische lokale Calls bekommen einen Hinweis statt Neuberechnung; hat die Tabelle eine Spalte wie die ID-Spalte der Join-Tabelle, wird sie mit abgeglichen. Antwortwerte, die selbst Datensatz-IDs sind, werden über den 4er-Deckel hinaus zitiert (Grader-Budget „erwartet + 2“ bleibt).
- rejected: Modell per Prompt zwingen, die Spalte zu nennen (hat es trotz Beispiel nicht getan)
- evidence: t03 0.06 → 0.41 (vor ID-Spalten-Fix); offline jetzt 39/39 auch mit der Spezifikation des Modells. tests/test_real_data.py prüft die Tools gegen echte Dev-Dateien (auch im Docker-Wächter).

## 13:40 · Bestätigung auf frischem Seed: 0.700 / $0.97
- decided_by: both
- why: Abnahme aller Änderungen (Router, earliest_slot, Join, count_distinct, capabilities, max_steps 14, Zitat-Fix) auf einem ungesehenen Seed, wie im Final.
- rejected: weitere Replays auf bekannten Seeds (überschätzen den Effekt)
- evidence: run_hP6Aq5nhZhYl 0.557 / $1.70 / final 0.322 → run__8OvzdDTetNJ 0.700 / $0.97 / final 0.434; Tasks am Schrittlimit 23 → 11; 0 Regelverstöße.
