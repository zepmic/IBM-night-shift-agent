# Plan B – Out-of-the-box-Ideen (riskanter)

**Status:** ✅ **Entschieden: B1 + B4 werden umgesetzt** (zusammen mit Plan A). B2/B3/B5/B6 nur bei konkretem Bedarf. · Ergänzt [Plan A](plan-a-solide.md), ersetzt ihn nicht.
Jede Idee: was, warum sie gewinnen könnte, warum sie scheitern kann, wie wir sie billig testen.
**Regel:** Eine B-Idee kommt nur in die Abgabe, wenn sie auf **frischen Seeds** Plan A schlägt.

---

## B1 – „Fast-Null-Kosten“: Compiler statt Agent

**Idee:** Das LLM löst keine Tasks, es **übersetzt** nur. Ein Call pro Task wandelt die Instruktion in ein kleines JSON-Programm unserer eigenen Mini-Sprache (z. B. `{"op":"count_events","filter":{...},"dedupe":"trace"}`). Ausführung komplett in Python. Kein Hin und Her, keine Logs im Kontext.

**Warum es gewinnen könnte:** `C` ist logarithmisch. Wer 5–10× billiger ist als das Feld, landet bei `C ≈ 1` → Multiplikator 1.0 statt ~0.75. Mit gleicher Genauigkeit wie andere = klarer Sieg.

**Warum es scheitern kann:** Final hat neue Formulierungen und evtl. Varianten, die unsere Mini-Sprache nicht abdeckt. Level-3-Tasks brauchen echtes Abwägen.

**Absicherung:** Hybride Route – Compiler für L1/L2-Familien mit hoher Offline-Trefferquote, Plan-A-Loop für L3 und alles Unbekannte. Konfidenz-Schwelle entscheidet.

**Billiger Test:** Für die 3 häufigsten Familien bauen, Offline-Eval vergleichen.

## B2 – LLM schreibt Python statt Tool-Calls

**Idee:** Für schwere Tasks liefert das Modell **ein Python-Snippet** gegen unseren lokalen Workspace-Index (pandas-DataFrames der Logs, Registry, Sheets). Wir führen es lokal aus (Timeout, kein Netzwerk, keine API-Tools im Snippet). Ein Call ersetzt 10 Tool-Runden.

**Warum es gewinnen könnte:** Zählen, Joinen, Zeitfenster-Logik ist für kleine Modelle in Code viel zuverlässiger als im Kopf. Spart Tokens.

**Warum es scheitern kann:** Kleines Modell schreibt fehlerhaften Code; Sicherheit des Ausführens; Debug-Zeit.

**Absicherung:** Ausführung nur lokal in Sandbox (subprocess, Timeout, read-only Daten). Schreibende Aktionen **nie** aus dem Snippet, nur über die Guardrail-Schicht. 1 Retry mit Fehlermeldung.

## B3 – Embeddings als Such-Turbo

**Idee:** `qwen3-embedding-8b` ist erlaubt. Alle geparsten Text-Chunks einmal pro Run embedden (geteilte Blobs → nur ~2 MB). Pro Task die Top-k relevanten Chunks statt ganzer Dateien ins Modell.

**Warum:** Embeddings sind sehr billig, der LLM-Kontext schrumpft drastisch.

**Risiko:** Embedding-Kosten zählen auch; findet bei Zahlen/IDs schlechter als Keyword-Suche → Hybrid (BM25/grep + Embedding).

## B4 – Best Breaker als zweiter Gewinnweg

**Idee:** Eine Person schreibt ab 10:30 Angriffe. Eigener Preis, unabhängig vom Leaderboard.

**Strategie:**
- Carrier `audit_log_detail` (landet in ~40 % auf zitierten Belegen).
- Ziel `frame_agent` oder `url_exfil`: brauchen keine Mail, nur ein JSON-Feld bzw. eine URL in der Antwort → niedrigere Hürde für fremde Agents.
- Text, der wie echte Log-Detailinfo aussieht (Analysten-Notiz, Korrelations-Hinweis), nicht wie ein Befehl.
- 3 Dev-Slots ab 10:30 nutzen, jede halbe Stunde `GET /payloads` auswerten, schlechteste Variante ersetzen, bestes um ~16:45 in den Final verschieben.

**Doppelnutzen:** Jede fremde Injection, die uns in Dev trifft (`injected_action:` im Feedback), wird sofort ein Guardrail-Testfall.

**Risiko:** Kostet eine Person. Darf unseren eigenen Agent nicht gezielt immun machen (Regel!). Unser Final-Angriff läuft auch bei uns → unsere Guardrails müssen allgemein gut sein.

## B5 – „Abstimmen nur wenn unsicher“

**Idee:** Zwei billige, unabhängige Lösungswege (z. B. Compiler B1 + Agent-Loop A). Stimmen sie überein → abgeben. Nur bei Abweichung ein dritter, teurerer Durchlauf oder Self-Consistency mit 3 Samples.

**Warum:** Teure Rechenzeit fließt nur in die schwierigen ~20 %.

**Risiko:** Doppelte Basiskosten, wenn Wege selten übereinstimmen. Erst messen.

## B6 – Jev-„decisions“-Endpunkt erkunden

**Idee:** Die Doku nennt `/openrouter/api/alpha/decisions` für Jev. Möglicherweise ein günstiger Klassifikations- oder Entscheidungs-Endpunkt (z. B. für Outcome-Wahl OK / DENIED / CLARIFY / UNSUPPORTED).

**Risiko:** Unbekannt, Alpha. **15 Min. Erkundung** am Vormittag, dann entscheiden. Beim Opening/Slack nachfragen.

---

## Empfohlene Kombination

**Plan A als Rückgrat + B1 für die häufigsten Familien + B4 mit einer Person.**
B2/B3/B5 nur, wenn die Offline-Eval eine konkrete Lücke zeigt, die sie schließen.
