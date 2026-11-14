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
