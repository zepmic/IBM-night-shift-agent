# Übergabe 3 an Fable: Stand 15:35, was offen ist, wie man prüft

**Wer:** Paul (+ Claude Code) · **Zeit:** Sa 14.11., 15:35 · **Typ:** Übergabe. Fable hat nur dieses Repo, keine lokalen
`runs/`-Traces. Alles Nötige steht hier oder lässt sich über die Task API neu holen (`.env` mit eigenen Team-Keys nötig).

## Zeitplan / Abgabe
- Demo-Fenster bis 16:30, Final 16:30–17:00 (eine finale Abgabe, danach gesperrt). Ohne finale Abgabe zählt die letzte Demo.
- Eine Demo (commit 938b1f8) wurde per API vorbereitet (`prep_zNDXfhOfG9tL`); ein Mensch muss sie im Dashboard bestätigen.
- Abgabe vorbereiten (der Agent darf alles außer der Bestätigung): `git archive -o submission.tar.gz HEAD`, dann
  `POST /api/v1/submissions` → `upload.url` per PUT mit `-T submission.tar.gz` → `POST /api/v1/submissions/<id>/ready`
  (challenge/01-task-api.md, „Prepare with your agent“). Danach Mensch: Dashboard → Submissions → „Prepared by your agent“.

## Messwerte (volle Dev-Runs, 48 Tasks, jeweils frischer Seed)
| Run | Code | Accuracy | Kosten | final |
|---|---|---|---|---|
| run_iOrNuR6b10uJ | 673bfd2 (Übergabe 2) | 0.772 | $0.45 | 0.512 |
| run_Go_5ItDDXKIl | 17de8e1 Bild-Tickets | 0.918 | $0.41 | 0.613 |
| run_32SoTk4qmWz4 | 81afee1 Zählregel | 0.863 | $0.40 | 0.579 |
| run_GXlstedXsIFN | 2866807 Zitate/Vision | 0.897 | $0.43 | 0.598 |
| run_Sb-7mLdXYUMt | 520e231 Standing Order, Trifecta, domain_contacts | 0.917 | $0.46 | 0.607 |
| run_SwvVSImU9uaS | 4291eae | ungültig: Plattform gab ab ~15:38 500er bei Submit/Manifest | – | – |

Seeds streuen stark (±0.03); ein einzelner Run ist kein Beweis. cost_score liegt bei ~0.33 und hat sich nicht bewegt.

## Was seit Übergabe 2 auf main ist (Details: JOURNAL.md ab 15:15)
- **Bild-Tickets**: `_preload` transkribiert /tickets/*.jpg wörtlich (erste Zeile `status: open|closed`); offene Tickets
  gehen an Router + Aufgabe. Größter Einzelhebel (+0.1 Accuracy): vorher wurden angeforderte Aktionen blockiert.
- **Bilder, die die Regeldateien nennen** (Standing Order) kommen transkribiert mit der Aufgabe (Rotationspuffer, Zählregel).
- **Zählregel**: `incident.runbook_reading` folgt der Datei, auf die das Runbook verweist; Records pro Agent („größter Anteil“).
- **Eingebettete Bilder** in Artefakten (MCP-Icon als data:image) gehen an die Vision (Patient Zero).
- **view_image** vom Modell: erst wörtliche Transkription, dann Antwort (sonst fallen „effective from …“ weg).
- **agreement_terms** (Vertragsfrist „in force right now“) und **leak_check** (SHA-256 gegen Fingerprints) in Code,
  Ergebnis liegt der Aufgabe bei, Zitate setzt der Harness.
- **domain_contacts**: Domains gegen alle Logs (E-Mail-/URL-Ziele), dazu Prompt-Satz gegen eingeschleuste „richtige Antworten“.
- **Berechnete Trifecta-Liste**: Zusätze des Modells werden verworfen (injected_action), Zitate aus der Rechnung.
- **Zitate**: fehlender `sheet` bei .ods/.xlsx-Zeilen wird ergänzt; Kanarien-IDs, MCP-Manifeste, Patient Zero aus der Rechnung.
- Kosten: `keep_small_chars` 4000, `keep_full_outputs` 2; wiederholte lokale Aufrufe mit evtl. gekürzter Ausgabe bekommen sie neu.

## Nachtrag 15:45
- Neu auf main seit dem ersten Stand dieser Notiz: Leak-Check liest auch Board-Posts und „ID=Wert“ (offline 12/12 exakt inkl.
  Quellen über 5 Seeds); Reihenfolge-Labels mit Ereignistext werden in Code dem passenden Zeitleisten-Eintrag zugeordnet
  (Unit-Test t40). Beides ist **noch nicht in einem echten Run bestätigt**: als Erstes einen vollen Dev-Run auf main fahren.
- Die Plattform lieferte ab ~15:38 HTTP 500 (Submit, Manifest, /submissions). Wenn ein Run viele „fallback submit failed … 500“
  zeigt, ist er nicht aussagekräftig.
- Demo-Abgaben: um 15:10 waren 0/3 genutzt; eine vorbereitete Abgabe (938b1f8, `prep_zNDXfhOfG9tL`, gültig bis 15:50) wartete
  auf Bestätigung im Dashboard. Vor dem Final den aktuellen main neu vorbereiten (neuer prep ersetzt den alten).

## Offen, nach Nutzen
1. **Ereignis-Reihenfolge** (Zuordnung jetzt in Code, s. Nachtrag; Rest:) (je Run 1–3 Tasks bei 0.3–0.45): `incident.order_events` ordnet nur Ereignisse, die in der
   Zeitleiste stehen. Es fehlen u. a. SIEM-Alarm (`/security/siem_alerts.xlsx`), Board-Post des Angreifers, Quarantäne-Zeitpunkte
   aus dem Gateway-Log, Delegations-Widerruf. Diese als Zeitleisten-Einträge ergänzen (Zitat: Blatt+Zeile bzw. Log-Zeile).
2. **Kosten** (cost_score 0.33): Grundlast ~6k Tokens pro Call (Systemprompt 3.3k Zeichen + vorgeladene Regeldateien + Baum).
   Teuerste Tasks sind such-lastig (`search` 10×). Ideen: Vorladen nur relevanter Regeldateien, Baum kürzen, max_steps 14 → 12
   messen, berechnete Antworten (review_access, agreement_terms, leak_check) direkt abgeben ohne weiteren Modell-Call.
3. Partner-Zusammenfassung (Draft): erwartete Quellen sind Zeilen aus `/notes/*internal_notes.md`, das Modell zitiert Transfers.
4. run_GXlstedXsIFN t13 (Trifecta nur Registry: Antwort `[]`) und t21 (`[2,5]` erwartet, `["2","3","4","5"]` abgegeben) nicht analysiert.

## So prüft man ohne Kosten
- `PYTHONPATH=. uv run python eval/offline/fresh.py` → leerer Dev-Run ($0), 48 Aufgaben + erwartete Antworten in runs/<id>.json.
- Werkzeuge direkt gegen diese Workspaces laufen lassen (Beispiel: `agent._workspace(client, run_id, task_id, cfg, tracker)` →
  `incident.fact_sheet(read, paths, {}, vision)`, `incident.agreement_terms(...)`, `incident.leak_check(...)`), Ergebnis mit
  `expected_answer`/`expected_sources` vergleichen. Prüfskripte: eval/offline/*.py (Aufrufe im Kopf von fresh.py).
- Tests vor jedem Merge: `for t in test_offline test_guard test_e2e test_fallback test_sources test_real_data; do uv run python -W ignore tests/$t.py; done`
  plus `PYTHONPATH=. uv run python tests/test_leak.py`.
- Echte Runs: `uv run main.py --kind dev --note "<Hypothese>"` (~$0.45, ~6 min), immer nur einer gleichzeitig.
  Traces danach lokal unter runs/<run_id>/, lesbar mit `PYTHONPATH=. uv run python eval/offline/tr.py <run_id> tNN 400`.

## Nachtrag 15:45
- **Demo vorbereitet:** `prep_A7lEq9tpTG0L` = commit 4de7e02 (46 Journal-Einträge), wartet auf Bestätigung im Dashboard.
- **Danach auf main (4673cf3):** Rückschritt behoben: gekürzte lokale Ergebnisse wurden bei jeder Wiederholung neu geliefert
  (run_Sb-7mLdXYUMt t25: 6× dieselbe 102-Zeilen-Ausgabe, $0.053). Für das Final also main ab 4673cf3 abgeben, nicht 4de7e02.
- **Bestätigungs-Run** auf 4de7e02 lief beim Schreiben (runs/full_run11.log lokal bei Paul; Ergebnis im Dashboard).
- **Nächster Hebel, teuerster Task:** Access-Log-Policy („Which requests in /logs/access/requests.csv break the access-log
  policy“): Score 0.1–0.6, bis $0.05. Die Regel 3 (gültiges Ticket in change_tickets.csv: approved, gleicher actor+resource,
  ts in [valid_from, valid_until), vor revoked_at) braucht `filter_rows` mit `{"op": "no_match", ...}`; das Modell nutzt es
  nicht. Lösung: POLICY.md-Bedingungen in Code auf eine filter_rows-Spezifikation abbilden und das Ergebnis vorab beilegen
  (wie review_access), mit Test gegen einen leeren Dev-Run.

## Nachtrag 15:55: Stand für Fable (ab 16:00)
**main = 2a6d810** (alle Tests grün). Seit 4de7e02 neu: Wiederholungs-Schleife behoben (Kostenfehler), Werkzeug-Beschreibungen
nur bei passendem Thema (`SPECIAL_TOOLS` in agent.py), Request-Log-Policy als Filter in Code (`_policy_spec`, offline 4/4).

| Run | Code | Accuracy | Kosten | final |
|---|---|---|---|---|
| run_m3AU4AsnXI6B | 4de7e02 (Demo-Build) | 0.899 | $0.62 | 0.577 |
| **run_07oOLC4jn7Vg** | **2a6d810** | **0.938** | **$0.32** | **0.643** (bester Run, C 0.37) |

**Kosten zählen die Hälfte:** `final = A · (0.5 + 0.5 · C)`, C logarithmisch zwischen Floor und Cap des Feldes. Halbe Kosten
≈ +0.15–0.2 auf C ≈ +0.08 final. Unser C liegt bei 0.28–0.34: hier ist am meisten zu holen.

### Kostenhebel, konkret (nach geschätztem Nutzen)
1. **Berechnete Antworten direkt abgeben, ohne weitere Modell-Schritte.** review_access, agreement_terms, leak_check, Policy-
   Filter, manifest_audit, board_triage, capabilities liefern fertige Antworten; das Modell braucht danach noch 2–4 Calls à
   ~6k Tokens. Wenn die Aufgabe nur das Ergebnis verlangt (sorted JSON array / JSON-Objekt der berechneten Form) und keine
   Aktion: direkt `submit` aus dem Harness (Zitate sind schon berechnet: `evidence.must_cite` / `list_cites`).
2. **Owner-/E-Mail-/Token-Nachschlagen ins Faktenblatt.** Viele Vorfalls-Tasks machen danach 4–7 `filter_rows` auf
   agents.csv / tokens.csv / contacts.csv (Owner, verifizierte E-Mail, Service). Im Faktenblatt pro genanntem Agent/Token
   gleich Owner + verifizierte E-Mail + Service mit Record-Zitat ausgeben.
3. **Grundlast pro Call senken**: pro Call gehen Systemprompt (3.4k Zeichen) + vorgeladene Regeldateien (AGENTS.md ~4k,
   runbook ~4k, changes.md, Standing Order) + Baum + Werkzeug-Schemas mit. Ideen: Baum nur bei Bedarf, Regeldateien nur die
   Abschnitte zur Aufgabe, Plattform-Werkzeuge ebenfalls nach Thema filtern (wie SPECIAL_TOOLS).
4. Verlauf: `old_output_chars` 300, `keep_full_outputs` 2, `keep_small_chars` 4000. Messen, ob 1/2000 schadet.
5. `max_steps` 14 und `task_cost_cap` 0.12: Tasks über ~10 Schritte sind meist verloren; messen mit 10 / 0.05.
Jede Änderung mit einem vollen Dev-Run bestätigen (Kosten stehen in `platform finish`), nie zwei Runs gleichzeitig.

### Genauigkeit, verbleibend
- Reihenfolge-Fragen (Zuordnung jetzt in Code, im Run noch unbestätigt), Partner-Zusammenfassung (Zitate aus internal_notes),
  einzelne Inbox-Tasks (run_m3AU4AsnXI6B t10: 0).

### Final-Abgabe (16:30–17:00)
Commit auf main, `git archive -o submission.tar.gz HEAD`, `POST /api/v1/submissions` → PUT des Archivs auf `upload.url`
(Header aus `upload.headers`) → `POST /api/v1/submissions/<id>/ready`. Dann bestätigt ein Mensch im Dashboard
„Prepared by your agent“ als **final submission**. Vorher Docker-Build lokal prüfen (README / AGENTS.md „Container contract“).

## Arbeitsweise für die letzte Stunde: Tempo vor Vorsicht
- Keine Wartezeiten: Während ein voller Dev-Run läuft (~6 min, im Hintergrund), am nächsten Hebel arbeiten.
- Parallel arbeiten, wo es geht: Subagents oder parallele Shells für Offline-Prüfungen, Trace-Analyse, Tests. Leere
  Dev-Runs (eval/offline/fresh.py) kosten $0 und dürfen jederzeit parallel laufen; nur volle Dev-Runs nie gleichzeitig.
- Dev-Budget ist da (~$15 gesamt, bisher grob $11 verbraucht): pro Hebel ein voller Run zur Bestätigung ist ok.
- Kleine, getestete Schritte schnell mergen und pushen, statt einen großen Umbau am Ende.
- Harte Grenze: spätestens 16:40 den besten bestätigten Stand als finale Abgabe vorbereiten und das Team zum Bestätigen holen.

## Tempo (nur ~40 Minuten)
Kein Plan, sofort loslegen: den größten Kostenhebel bauen, testen, mergen, Run im Hintergrund, sofort den nächsten Hebel.
Nur eine harte Grenze: um 16:40 den besten bestätigten Stand (mindestens 2a6d810) als finale Abgabe vorbereiten.
