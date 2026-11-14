# Strategie entschieden: Plan A + B1 + B4

**Wer:** Michel (+ Claude Code) · **Zeit:** Sa 14.11. · **Typ:** Entscheidung

- **Rückgrat:** [Plan A](../plans/plan-a-solide.md) – Workspace-Spiegel, Parser mit Locators, Instruktions-Parser, Guardrails, Validator, Budget-/Zeit-Wächter, Offline-Eval.
- **B1 „Compiler statt Agent“:** für die häufigsten L1/L2-Familien ein einziger LLM-Call → JSON-Programm → Python. Nur wenn er auf frischen Seeds Plan A schlägt. L3 und Unbekanntes → Plan-A-Loop.
- **B4 „Best Breaker“:** eine Person schreibt Angriffe (Carrier `audit_log_detail`, Ziele `frame_agent` / `url_exfil`), wertet `GET /payloads` halbstündlich aus, schiebt das beste um ~16:45 in den Final. Fremde Treffer bei uns → sofort Guardrail-Testfall.
- **Nicht jetzt:** B2, B3, B5, B6 – nur wenn die Offline-Eval eine konkrete Lücke zeigt.

**Folge für andere:** Rollen = Infra · Solver (inkl. B1) · Eval + Sicherheit · Breaker (B4). Wer welche Rolle hat, im README eintragen.
