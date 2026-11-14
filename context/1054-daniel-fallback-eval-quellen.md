# Fallback-Submit, Offline-Eval, Quellen-Ledger (Branch `daniel/fallback-eval`)

> TEILWEISE VERALTET (Kostenschätzung, JSON-Records), siehe 1107-daniel-dev-run-auswertung.md

**Wer:** Daniel (+ Claude Code) · **Zeit:** Sa 10:54 · **Typ:** Status + Erkenntnis

Alles auf Branch `daniel/fallback-eval` (3 Commits, noch **nicht** auf main, noch **kein** Dev-Run, Kosten bisher $0).

## 1. Fallback-Submit (`agent.py`)
- `solve_task` gibt jetzt **immer genau einmal** ab: LLM-Fehler (auch 403 Budget-Limit), Exception, Step-Limit ohne Submit, Modell ruft kein Tool.
- Reihenfolge: letzter vom Modell versuchter, aber abgelehnter Submit (mit Quellen → ohne Quellen) → sonst `UNSUPPORTED` / `null` / keine Quellen.
- Warum `UNSUPPORTED`: laut Task API die einzige Verweigerung, die ohne Antwort punkten kann („the outcome alone counts“). `DENIED_SECURITY` braucht die Absender-Adresse, `NEEDS_CLARIFICATION` die Agent-IDs.
- Fallback ruft nie ein Workspace-Tool auf. Bei 409 (schon abgegeben / Deadline) kein zweiter Versuch.
- Ruft das Modell 4× kein Tool auf, gibt es vorher noch **einen** erzwungenen Submit-Call.
- Test: `uv run python tests/test_fallback.py` – u. a. `main.py` gegen den Mock ohne OpenRouter-Key: 2/2 Tasks abgegeben, 0 Tool-Calls.

## 2. Offline-Eval (`eval/`)
```bash
uv run python eval/collect.py     # runs/*/finish.json + Traces → runs/fallset.jsonl (git-ignored, enthält Dev-Antworten)
uv run python eval/score.py       # Tabelle pro Task: outcome, answer, sources hit/expected (+extra), score, Plattform-Score, Kosten
uv run python eval/score.py --answers a.jsonl   # andere Antworten für dieselben Fälle bewerten
```
- Formel: `answer · (0.7 + 0.3 · sources)`. Nachgebauter Baseline-Fall (Antwort ✓, 1/4): lokal 0.775, Plattform 0.77.
- Näherungen: Listen-Teilpunkte = F1; Action-Tasks und Constraints kommen aus dem Plattform-Grade; Zeilen ±2.
- Traces haben neu ein `end`-Event mit **Kosten pro Task** und ein `sources`-Event (Modell-Zitate / ergänzt / verworfen).
- **Bisher nur mit Fake-`finish.json` getestet** (`tests/test_eval.py`) – auf diesem Rechner liegt kein echter Run. Das echte Feld-Format von `finish.json` ist nur aus der Doku abgeleitet.

## 3. Quellen (`sources.py`)
- Befund: Quellen kamen nur aus dem Gedächtnis des Modells; alte Tool-Outputs werden auf 300 Zeichen gekürzt; `clean_sources` prüft nur Typen.
- Neu: Der Harness merkt sich jede gesehene Stelle (read/search/query_logs: Zeile bzw. CSV-/JSON-Record; download_file: Seite, Absatz, Sheet+Zeile). Beim Submit ergänzt er Stellen, an denen ein **ID-artiger Wert der Antwort** wörtlich steht – nur wenn er in der Datei ≤ 2× vorkommt, max. 4 Zusätze. JSON-Datei voll mit dem Wert → nur Pfad. Zitate auf nicht existierende Dateien (Manifest) werden verworfen.
- Kein LLM-Call. Abschaltbar: `--no-auto-sources`. Dazu ein Satz mehr im System-Prompt (alle tragenden Dateien zitieren).
- Test: `uv run python tests/test_sources.py` (Mock + nachgebauter Baseline-Fall). Alle Tests laufen auch im Docker-Image mit `--network none`.

## Offene Punkte
- **Wirkung auf echte Tasks unbewiesen.** Das Rückgabeformat von `read`/`search`/`query_logs` der echten Plattform kenne ich nicht; der Parser ist tolerant gebaut, aber ungeprüft. Wer einen echten `runs/<run_id>/`-Ordner hat: bitte ein Trace teilen oder `eval/collect.py` laufen lassen.
- Unklar, wie hart zusätzliche (falsche) Zitate bestraft werden → nach dem ersten Run `extra` in `eval/score.py` ansehen, ggf. `max_auto_sources` senken.
- `UNSUPPORTED` als Default punktet nur, wenn der Task wirklich UNSUPPORTED erwartet – sonst 0 wie ohne Submit.
- `tests/test_submit_retry.py` schlägt weiter fehl (Kit-Fehler, siehe 1000-michel-baseline).
- Vorgeschlagener Beweis-Run (wartet auf OK): Seed der Baseline, `--level 1 --limit 6`, ≈ $0.04.
