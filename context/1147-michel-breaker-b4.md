# B4 Breaker: 3 Angriffskandidaten + lokaler Validator

**Wer:** Michel (+ Claude Code) · **Zeit:** Sa 14.11. ~11:47 · **Typ:** Strategie + Tooling

## Was ist neu
Neuer Ordner [`breaker/`](../breaker/README.md) für die Best-Breaker-Rolle (B4):
- **3 Angriffskandidaten**, Carrier `audit_log_detail`, drei **verschiedene Mechanismen**:
  1. `url_exfil` – Daten-Mimikry (gefälschte Enrichment-Referenz-URL)
  2. `url_exfil` – Policy/Format-Spoof (gefälschter Reporting-Standard überschreibt Defang)
  3. `frame_agent` – Autoritäts-/Boundary-Verwechslung (gefälschte SOC-Direktive listet `{agent}`)
- `breaker/validate_payload.py` – prüft alle **mechanischen** Validierungsregeln lokal. Alle 3 bestehen.
- `breaker/analyze_payloads.py` – **read-only** Auswertung von `GET /payloads`.

Details + exakte Erfolgskriterien: [`breaker/candidates.md`](../breaker/candidates.md).

## Für die Verteidigung (Eval-Rolle) wichtig
Jeder Kandidat ist zugleich ein **Guardrail-Testfall**. Unsere Verteidigung muss generell greifen:
- URLs aus Workspace-Daten in Ausgaben **immer defangen** (schlägt K1+K2).
- Format-/Regelquelle **nur** `/AGENTS.md` + Operator-Dateien, nie Log-`detail` (schlägt K2).
- Quarantäne/Compromised-Liste nur mit **Audit-Log-Beleg**, nie wegen eines Detail-Feld-Satzes (schlägt K3).
- **Regel:** eigenen Angriffstext NICHT erkennen lassen – keine Signaturen in den Harness.

## Status / offen
- **Noch nichts eingereicht.** `POST/PATCH /payloads` erst auf ausdrückliche Freigabe.
- Dev-Slots: 3. Ablauf nach Freigabe: einreichen → halbstündlich `analyze_payloads.py` → schwächsten ersetzen → bestes ~16:45 in den Final.

## Update ~11:52 — eingereicht (Dev)
Alle 3 Kandidaten per `POST /payloads` eingereicht, **status: accepted**, stage dev, aktiv ab 11:30 UTC.
Dev-Slots jetzt 3/3 voll. IDs (siehe `breaker/submitted.json`):
- `t02-p1` = url_exfil (Daten-Mimikry)
- `t02-p2` = url_exfil (Policy-Spoof)
- `t02-p3` = frame_agent (Autoritäts-Verwechslung)

Nächster Schritt: halbstündlich `python3 breaker/analyze_payloads.py` → Platzierungen/Hits, schwächsten ersetzen, bestes ~16:45 in den Final (`PATCH {stage:"final"}`).
