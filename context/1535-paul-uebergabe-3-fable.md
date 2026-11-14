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
