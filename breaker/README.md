# breaker/ — B4 Best Breaker (Team Donaufriends)

Arbeitsordner für die Break-it-Angriffe. **Nur innerhalb der Wettbewerbs-Schnittstelle**
(synthetische Task-Workspaces fremder Agents). Keine echten Systeme/Personen/Anbieter.

| Datei | Zweck |
|---|---|
| [`candidates.md`](candidates.md) | 3 Angriffskandidaten + Regeln + Erfolgskriterien + Begründung |
| `payloads.json` | maschinenlesbare Kandidaten (carrier/goal/text) |
| `validate_payload.py` | prüft die **mechanischen** Validierungsregeln lokal |
| `analyze_payloads.py` | **read-only** Auswertung von `GET /payloads` (Platzierungen/Hits) |

## Benutzen
```bash
python3 breaker/validate_payload.py          # Kandidaten gegen alle mechanischen Regeln
python3 breaker/analyze_payloads.py          # eigene Payloads + Treffer (braucht .env-Keys)
```

## Regeln, die Code NICHT prüfen kann (menschlich)
Keine echten Personen/Firmen/Produkte · nichts Anstößiges · nichts gegen Plattform/Provider ·
**eigener Agent darf den eigenen Angriffstext nicht erkennen** (kein Harness-Code, keine Signaturen).

## Einreichen / Verschieben = nur auf ausdrückliche Freigabe
`POST /payloads`, `PATCH /payloads/{id}` (retire / stage) werden **nicht** ohne Auftrag ausgeführt.
