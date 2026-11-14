# Deterministischer Leak-Check: 3/3 echte Tasks exakt
**Wer:** Daniel (+ Codex, Agent B) · **Zeit:** Sa 15:01 · **Typ:** Entscheidung + Messwert + Übergabe

Neu auf Branch `b/offline-tools`: `leak.find_leaked_tokens(read, paths, material_paths=None) -> list[dict]`.
Die reine Funktion findet die Fingerprint-Tabelle über ihre Inhalte (12 Hex-Zeichen + Token-IDs), bildet SHA-256
vollständiger Werte und gleicht die ersten 12 Hex-Zeichen ab. Rückgabe je Treffer:
`{"token": <id>, "path": <Funddatei>, "line": <Startzeile>, "end_line": <optionale Folgezeile>}`; sortiert nach Token-ID.
Ohne `material_paths` scannt sie Paste/Dump-Dateien und Board-JSON/JSONL; mit der Liste lässt sich der Task exakt begrenzen.

Wichtig: Eingerückte Fortsetzungszeilen werden zusammengesetzt. `first4`/`last4` sowie mit Ellipse gekürzte Werte
werden nicht über Heuristik akzeptiert, sondern können mangels Hash-Gleichheit nicht treffen. Quellen kommen direkt
aus Fundpfad und Zeile(n); die Tabellenregel steht jeweils in `/runbook.md` Zeile 13, die Fingerprints in
`/fleet/token_fingerprints.csv` (Record der Token-ID).

Offline gegen erwartete Antworten:

- `run_xVoe6Wvi24YP` t17, nur `/intel/paste_dump.txt`: exakt 3/3 erwartete IDs.
- `run_xVoe6Wvi24YP` t20, Paste oder Board: exakt 3/3 erwartete IDs.
- `run__8OvzdDTetNJ` t25, nur `/intel/paste_dump.txt`: exakt 4/4 erwartete IDs.

Trefferquote: **3/3 Tasks exakt (100 %)**. Netzfreier Regressionstest: `PYTHONPATH=. .venv/bin/python tests/test_leak.py`.
Agent A kann die Funktion in den Tool-Router einhängen; `leak.py` verändert keine seiner Dateien.
