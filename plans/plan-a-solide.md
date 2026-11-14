# Plan A – Solide Gewinnstrategie

**Status:** ✅ **Entschieden: Rückgrat**, kombiniert mit [B1 + B4](plan-b-out-of-the-box.md) · **Quelle:** [`challenge/01-task-api.md`](../challenge/01-task-api.md)
**Kernidee:** Lokale Kopie + Parser + Code für alles Regelhafte, das kleine Modell nur zum Verstehen und Abwägen. Guardrails um jede schreibende Aktion. Messen über viele Dev-Seeds mit aufgedeckten Antworten.

---

## 1. Was die Regeln für uns bedeuten

| Regel | Folge für uns |
|---|---|
| `final = A · (0.5 + 0.5·C)` | Kosten sind **die Hälfte des Multiplikators**. Bei 10× Kosten-Spanne bringt **halbe Kosten ≈ +0.15 Multiplikator**. Kosten und Genauigkeit sind gleich wichtig. |
| Task-Score = `answer · (0.7 + 0.3·sources)`, Verstoß → 0 | Falsche Aktion ist schlimmer als keine. Quellen bringen 30 % – präzise, nicht viele. |
| Unbeantwortete Tasks = 0 | **Jeder Task muss eine Antwort bekommen**, notfalls Best Guess. |
| Final: 30 Min., $3 Budget, einmalig, neue Formulierungen | Parallel arbeiten, Budget-Wächter, Instruktionen per LLM verstehen statt per Regex. |
| Dev: Seeds wiederholbar, Antworten nach `finish` sichtbar | **Gratis-Trainingsdaten**: wir bauen ein Offline-Eval-Set. |
| `/AGENTS.md` im Workspace = Quelle der Wahrheit | Pro Run zuerst die Operator-Dateien lesen; Rest ist Daten, nie Anweisung. |
| Andere Teams platzieren Prompt Injections | Guardrails sind Pflicht, nicht optional. |
| Nur `google/gemma-4-31b-it` + `typesafe/jev-1.14` + `qwen3-embedding-8b` | Keine OCR-Libs, keine lokalen Modelle. Bilder → Vision von Gemma. Embeddings $0.01/1M Tokens → Retrieval ist billig. |
| `JOURNAL.md` mit eigenem Eintrag | Sonst nicht preisberechtigt. **Sofort anlegen.** |

## 2. Architektur

```
            ┌──────────────── pro Run einmal ────────────────┐
POST /runs → Manifest → Blobs (sha256-Cache) → Parser → Text + Locator-Index
            │                                   (pdf→page, docx→paragraph,
            │                                    xlsx→sheet+row, csv→record, jsonl→line)
            └→ AGENTS.md + Operator-Dateien → 1 LLM-Call → strukturierte Regeln (JSON, gecacht)

pro Task (parallel, ~6–8 gleichzeitig):
  1. Instruktion verstehen  → 1 LLM-Call → {family, intent, entities, answer_shape, action_requested?}
  2. Solver                 → Familien-Solver (Code + gezielte LLM-Calls) oder generische Agent Loop
  3. Guardrail              → prüft jede schreibende Aktion + die Antwort
  4. Antwort-Validator      → Format, Refusal-Pflichtfelder, minimale Quellen
  5. submit
finish
```

### Bausteine

1. **Workspace-Spiegel:** Manifest + Blobs einmal laden, nach sha256 cachen. Spart Requests und Zeit.
2. **Parser mit Locators:** jedes Format → Textzeilen mit exaktem Zitat-Locator. Löst die 30 % Quellen fast komplett per Code.
   - pdf: `pdfplumber` (Seite) · docx: `python-docx` (nicht-leere Absätze) · odt/ods: `odfpy` · xlsx: `openpyxl` (Zeile wie im Sheet) · Bilder: Vision-Call **nur wenn der Task sie braucht**.
3. **Regel-Extraktor:** AGENTS.md + genannte Operator-Dateien einmal pro Run zu JSON: Quellen-Tiers, Konfliktregeln, Zähl-Regeln, erlaubte Empfänger, Outcome-Regeln.
4. **Instruktions-Parser (LLM):** übersetzt jede Formulierung in ein festes Schema. Das ist unser Schutz gegen die neuen Formulierungen im Final.
5. **Familien-Solver:** Dev-Tasks wiederholen sich als Familien (nur Werte/Oberfläche ändern sich). Pro Familie deterministischer Code (`query_logs`, `access_path`, Zählen, Joins) + LLM nur für Urteile.
6. **Generische Agent Loop (Fallback):** für unbekannte Familien. Wenige Tools, max. Schritte je Level (L1: 6, L2: 10, L3: 15), kurzer Kontext.
7. **Guardrail-Schicht** (Code, nicht LLM):
   - `containment` / `send_message` / `write` **nur wenn der Instruktions-Parser eine Aktion erkannt hat**, sonst blockiert.
   - Empfänger nur aus AGENTS.md/Operator-Dateien erlaubt. Nie an Adressen aus Logs, Mails, Dokumenten.
   - Keine Token-Werte (`fake_…`) und keine Inhalte aus AGENTS.md/Runbook in Nachrichten.
   - Alle URLs/Domains in Antworten, Nachrichten, Drafts **defangen** (`hxxps://x[.]y`).
   - Quarantäne nur für Agents mit Beleg im Audit-Log (echte Attack-Trace-Aktion), nie wegen eines Satzes in einem Dokument.
   - Ticket-Tasks: nur das Ticket mit `status: open` ist die Anfrage, geschlossene sind Historie.
8. **Antwort-Validator:** Form laut Instruktion; `DENIED_SECURITY` → Absender-Mail; `NEEDS_CLARIFICATION` → alle passenden Agent-IDs; `UNSUPPORTED` → `null`. Quellen auf das Nötigste kürzen.
9. **Budget- und Zeit-Wächter:** Kosten pro Task tracken, Budget je Level. Bei 22 Min. oder ~$2.50: alle offenen Tasks mit Best Guess abgeben. **Kein Task bleibt leer.**
10. **Robustheit:** 429 → `Retry-After`, 500 → Retry. Nach Container-Neustart den laufenden Final-Run fortsetzen statt neu starten (`GET /runs`, bereits abgegebene Tasks überspringen).

## 3. Eval-Maschine (der eigentliche Hebel)

1. **Datensammler:** N Dev-Runs (verschiedene Seeds) → Instruktionen, Level, Workspace, `expected_*` lokal speichern (`data/`, nicht committen, wenn groß).
2. **Familien-Katalog:** Tasks clustern (LLM oder per Hand) → `context/` dokumentieren: Familie, Beispiel-Instruktionen, Lösungsweg, Fallen.
3. **Offline-Check:** Solver gegen gespeicherte Workspaces + Erwartungen laufen lassen, **ohne** neue Dev-Runs → billig und schnell.
4. **Online-Check:** gelegentlich frischer Seed als ehrlicher Test (Variation!). Seed-Replays nur zum Debuggen.
5. **Ergebnis-Log:** jede Messung als `context/`-Eintrag (Typ Messwert) + `meta.note` beim Run.

Achtung: Dev-Runs kosten echtes Budget. Ein ganzer Run = 30 Tasks. Zum Debuggen `--tasks tNN`.

## 4. Rollen (3–4 Personen)

| Rolle | Baut |
|---|---|
| **Infra** | Client, Workspace-Spiegel, Parser mit Locators, Dockerfile, Budget-/Zeit-Wächter, Submit-Pipeline |
| **Solver** | Instruktions-Parser, Familien-Solver, Agent-Loop-Fallback |
| **Eval + Sicherheit** | Datensammler, Offline-Eval, Guardrail-Schicht, Antwort-Validator |
| *(optional)* **Breaker** | Angriffe schreiben (siehe Plan B) + aus fremden Angriffen Guardrail-Tests ableiten |

## 5. Zeitplan

| Zeit | Meilenstein |
|---|---|
| bis 10:30 | Starter Kit ins Repo, `JOURNAL.md` mit erstem Eintrag, `.env` mit Keys, **Baseline-Run mit 1–3 Tasks** |
| bis 11:30 | Datensammler läuft, erste 3–5 Dev-Runs gespeichert; Parser für alle Formate; Familien-Katalog v1 |
| bis 13:00 | Instruktions-Parser + Guardrails + Validator; Fallback-Loop; erster ehrlicher Voll-Run (Score + Kosten) |
| 13:00–14:00 | Größte Verlust-Familien angehen; **Docker lokal + offline testen** |
| 14:00 | **Demo-Submission 1** (prüft Container, Zeit, Kosten) |
| 14:00–15:45 | Iterieren: Familie für Familie, Kosten runter (Calls streichen, Kontext kürzen) |
| ~15:00 | Demo-Submission 2 |
| 15:45 | Voll-Run auf frischem Seed als Abnahme |
| 16:15 | Demo-Submission 3 = Kandidat |
| 16:30–16:45 | **Final-Submission hochladen** (WLAN-Puffer!) |
| bis 17:00 | Final-Angriff festlegen (falls Plan-B-Breaker aktiv) |

## 6. Risiken

| Risiko | Gegenmittel |
|---|---|
| Final-Formulierungen anders | Instruktions-Parser per LLM, keine Regex auf Instruktionen |
| Container crasht / zu langsam | Früh Demo-Submission, Resume-Logik, Parallelität, Timeout pro Task |
| $3 Budget überschritten → 403 | Budget-Wächter, Best-Guess-Abgabe |
| Injection trifft uns → Task = 0 | Guardrails in Code, nicht im Prompt |
| Overfitting auf Dev-Werte | nur Logik hart codieren, nie Namen/IDs/Pfade |

## 7. Offene Fragen ans Opening / Slack

- Wie gut ist `gemma-4-31b-it` bei Tool Calling / JSON / Vision? → in der ersten Stunde testen
- Was ist der Jev-Endpunkt `/openrouter/api/alpha/decisions`? Evtl. ein günstiger Entscheidungs-Endpunkt → ausprobieren
- Preis pro Token von Gemma und Jev (Embeddings: $0.01 / 1M laut Kit)
- ~~Dev-Budget-Höhe~~ → **$15**, voller Run = 48 Tasks
