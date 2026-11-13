# AIM Efficient Local Agents Hackathon – Spickzettel & Starter-Kit

**Sa, 14. Nov · 09:00–22:00 · IBM, Obere Donaustraße 95, 1020 Wien**

## 1. Worum geht's (in einem Satz)
Alle Teams bekommen **dasselbe kleine Sprachmodell + dasselbe Token-Budget**.
Gewinnen tut nicht das beste Modell, sondern der **beste "Harness"**, also der Code *rund um* das Modell.

## 2. Grundbegriffe

| Begriff | Was es heißt |
|---|---|
| **LLM / SLM** | (Small) Language Model. Bekommt Text rein, gibt Text raus. Klein = billig, aber dümmer. |
| **Token** | Wortstück (~¾ Wort). Man zahlt pro Token **rein** (Prompt) und **raus** (Antwort). |
| **Agent** | Programm, das ein LLM in einer Schleife nutzt: denken → Werkzeug benutzen → Ergebnis prüfen → weiter. |
| **Harness** | Das ganze Gerüst um das Modell: Prompts, Planung, Tools, Gedächtnis, Suche, Prüfung. **Das bauen wir.** |
| **Retrieval / RAG** | Relevante Textstellen suchen und dem Modell mitgeben, statt alles reinzukippen. Spart Tokens und verhindert Erfinden. |
| **Halluzination** | Das Modell erfindet etwas. Kleine Modelle tun das oft → darum prüfen. |
| **Jev 1.14** (TypeSafe AI) | Ein "System One"-Modell: schreibt keinen Text, sondern trifft **typisierte Entscheidungen** (ja/nein, Auswahl aus Optionen, Score) mit **kalibrierter Wahrscheinlichkeit**. Sehr schnell & billig. |
| **Kalibriert** | Sagt Jev "90 %", stimmt es ~90 % der Zeit. Man kann also Schwellwerte setzen. |
| **Benchmark** | Aufgabensammlung mit bekannten richtigen Antworten, um den Agenten zu messen. |

## 3. Wie bewertet wird
- **50 % Genauigkeit**: richtige Antwort **und richtige Quellen** angeben.
- **50 % Kosten**: so wenig Tokens/Calls wie möglich.
- 17:00 wird der Code eingefroren. Der Agent läuft dann **einmal, alleine**, auf einem **unbekannten** Szenario. Kein Nachbessern!
- Zur Laufzeit nur die zwei gestellten Modelle. Beim Bauen dürfen wir Claude & Co. verwenden.

## 4. Gewinnstrategie (Faustregeln)
1. **LLM nur, wo Text erzeugt werden muss.** Alles, was eine Entscheidung ist ("passt das?", "nochmal versuchen?", "welcher Aufgabentyp?") → **Jev**.
2. **Kurze Prompts.** Keine langen System-Prompts, keine Beispiele, die nichts bringen. Jeder Token zählt doppelt (rein + raus via `max_tokens`).
3. **Gut suchen statt viel lesen.** BM25-Suche kostet 0 Tokens. Nur die Top-3-Stellen ans Modell.
4. **Quellen immer mitliefern.** Sie zählen zur Genauigkeit.
5. **Lieber "weiß nicht" als falsch.** Wenn Jev sagt "nicht gestützt", lieber 1 Retry mit mehr Kontext, dann UNKNOWN.
6. **Caching**: gleiche Anfrage nie zweimal bezahlen (ist eingebaut).
7. **Robust bleiben**: der Final-Run läuft unbeaufsichtigt → Timeouts, Retries, kaputtes JSON abfangen. Ein Crash = 0 Punkte.
8. **Messen, messen, messen.** Nach jeder Änderung Benchmark laufen lassen, Genauigkeit *und* Kosten notieren.

## 5. Ablauf am Tag
| Zeit | Was wir tun |
|---|---|
| 09:15 | Challenge-Reveal: **Modellname, API-URL/Key, Jev-Doku, Benchmark-Format** mitschreiben → in `.env` eintragen |
| bis 10:00 | `harness/jev.py` (`_call_real_jev`) und `run.py` (`load_tasks`) an die echten APIs anpassen. Erster End-to-End-Lauf. |
| 10–12 | Baseline messen. Größte Fehlerquellen finden (falsche Suche? falsches Format? Halluzination?). |
| 12–16 | Iterieren: Prompts kürzen, Jev-Entscheidungen einbauen, Retrieval verbessern, Quellenformat exakt treffen. |
| 16–17 | **Nichts Riskantes mehr.** Stabilität testen, beste Version committen. |
| 17:00 | Freeze. |
| 18:00 | Präsentation: 2–3 Folien – Architekturbild, Zahlen (Genauigkeit/Kosten), 1 cleverer Trick. |

## 6. Das Starter-Kit

```
harness/llm.py        LLM-Client (OpenAI-kompatibel), Token-/Kostenzähler, Cache, Retries, robustes JSON
harness/jev.py        Jev-Wrapper: decide() / yes()  ← am Tag an echte API anschließen
harness/retrieval.py  BM25-Suche über Dokumente (0 Tokens)
harness/agent.py      Pipeline: suchen → antworten → mit Jev prüfen → ggf. 1x Retry
run.py                Benchmark-Runner: zeigt ✅/❌, Quellen-Treffer, Kosten
```

Ablauf eines Tasks:
```
Frage ──► BM25 (Top-3 Stellen) ──► SLM: {"answer", "sources"} ──► Jev: "gestützt?"
                ▲                                                     │ nein
                └──────────── mehr Kontext holen (k×2) ◄──────────────┘
```

### Starten
```bash
cd IBM-night-shift-agent
cp .env.example .env      # Werte am Samstag eintragen
MOCK=1 uv run run.py      # offline Test mit Fake-Modell
uv run run.py             # echt
```

### Vor Samstag zu Hause testen (optional)
Mit [Ollama](https://ollama.com) ein kleines Modell lokal laufen lassen:
```bash
brew install ollama && ollama serve &
ollama pull granite3.3:2b
```
Dann in `.env`: `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL=granite3.3:2b`, `MOCK=0`.

## 7. Checkliste fürs Mitnehmen
- [ ] Zusage per Mail bekommen? (Bewerbung lief über Airtable, Deadline war 7.11., Zusagen bis 9.11.)
- [ ] Laptop + Ladekabel, ggf. Mehrfachstecker
- [ ] Dieser Ordner auf dem Laptop, `uv run run.py` funktioniert mit `MOCK=1`
- [ ] Claude Code / IDE eingerichtet und eingeloggt
- [ ] IBM-WLAN-Link aus der Mail griffbereit (Hotspot als Backup)
- [ ] Team (max. 4) – wer macht was: 1× Retrieval, 1× Prompts/Jev, 1× Benchmark & Messen, 1× Präsentation
