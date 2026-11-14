# Submission-Hinweise für den Laptop, der einreicht

**Wer:** Michel (+ Claude Code) · **Zeit:** Sa 14.11. 13:35 · **Typ:** Setup + Status

- **Eingereicht wird nur vom anderen Laptop/Agent.** Michels Session reicht nichts ein.
- Michels Session hat einen Upload vorbereitet (`prep_s_uHXnJUFY9H`, Commit 1534581). **Das ist keine Submission** und verbraucht keinen Demo-Slot. Jeder neue `POST /submissions` ersetzt ihn, also einfach ignorieren.
- `breaker/` steht jetzt in `.gitattributes` als `export-ignore`: Unser Angriffstext kommt nicht ins Archiv, weil die Veranstalter Uploads auf Erkennung des eigenen Angriffs prüfen.
- Geprüft auf 1534581: Image baut aus `git archive`, `tests/test_e2e.py` läuft im Container mit `--network none`.
- `tests/test_submit_retry.py` schlägt fehl, ist aber veraltet (Kit-Test). Der Harness entfernt Quellen ohne `path` jetzt selbst, also landet schon die erste Abgabe. Kein Bug.
