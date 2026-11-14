# Baseline: Starter Kit unverändert, 1 Task

**Wer:** Michel (+ Claude Code) · **Zeit:** Sa 14.11. ~10:00 · **Typ:** Messwert + Setup

## Ergebnis
- Run `run_7FdiWah57oDE`, seed `1006996093`, Commit `c2ab907`, Modell `google/gemma-4-31b-it`
- **t01: Score 0.77** – Outcome ✓, Answer ✓, Constraints ✓, **Sources 1/4**, 7 Tool-Calls, 14 s
- Kosten: **~$0.005–0.007 pro Task** (34k Input-, 332 Output-Tokens, 8 LLM-Calls)
- Hochgerechnet: voller Run (48 Tasks) ≈ **$0.25–0.35** mit dem Baseline-Agent

## Erkenntnisse
- **Quellen sind der schnellste Hebel:** Antwort war richtig, aber nur 1 von 4 Quellen → 0.77 statt 1.0. Erwartet waren zusätzlich `/fleet/registry_export.json` (nur Pfad) und `/fleet/changes.md` Zeile 7 und 8. → Antwort hing an Registry + Änderungsprotokoll, nicht nur am Audit-Log.
- **Input-Tokens dominieren** (34k rein, 0.3k raus) → Kontext kürzen spart am meisten.
- Die platform-`accuracy` (0.016) zählt alle 48 Tasks, also 47 × 0. Für Teilmengen-Runs die lokale Accuracy ansehen.

## Setup-Wissen
- `uv` auf Michels Mac per `brew install uv` (0.13.8); ggf. `export PATH=/opt/homebrew/bin:$PATH`.
- Kit-Tests: `uv run python tests/test_cache.py` usw. `tests/test_submit_retry.py` **schlägt im Original-Kit fehl** (der Agent filtert Quellen ohne `path` schon vor dem Submit, der Test erwartet einen 400-Retry) – kein Problem unsererseits.
- Traces liegen in `runs/<run_id>/` (nicht im Repo). `finish.json` enthält nach Run-Ende `expected_answer` / `expected_sources` → Datenquelle für die Offline-Eval.
