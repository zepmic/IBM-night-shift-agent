# IBM Night Shift Agent

Efficient Local Agents Hackathon · IBM Vienna · Sa 14.11.2026
Challenge: **The MuggingFace Incident** – Small model. Smart harness.

Unser Agent untersucht einen Angriff auf einen Model Hub und dämmt ihn ein – **korrekt und billig**.
Bewertung: Genauigkeit + Kosten (LLM-Calls). Läuft im Docker-Container **ohne Internet** auf einem **unbekannten Szenario**.

Strategie & Regeln: siehe [PLAYBOOK.md](PLAYBOOK.md).
Harness-Gerüst, Grundbegriffe & Spickzettel: siehe [docs/STARTER-KIT.md](docs/STARTER-KIT.md).

```bash
MOCK=1 uv run run.py   # offline Test des Harness
```

## Setup

```bash
git clone https://github.com/zepmic/IBM-night-shift-agent.git
cd IBM-night-shift-agent
cp .env.example .env   # Keys eintragen, die wir am Tag bekommen
```

Voraussetzungen: Git, Python ≥ 3.11, uv, Docker Desktop (`docker run hello-world` muss laufen).

## Team & Rollen

| Rolle | Wer | Verantwortung |
|---|---|---|
| Harness / Pipeline | _TBD_ | Agent Loop, Tool-Aufrufe, JSON-Validierung, Retries |
| Daten / Regeln | _TBD_ | Szenario-Logs lesen, deterministische Filter & Detektoren |
| Eval + Docker | _TBD_ | Mess-Skript (Score + Tokens), Dockerfile, Offline-Test, Abgabe |

## Git-Regeln

- `main` ist **immer lauffähig**.
- Jeder arbeitet auf eigenem Branch: `name/feature` (z. B. `michel/json-retry`).
- Merge in `main` nur nach einem erfolgreichen Eval-Lauf. Kleine, häufige Merges.
- **Keine Keys committen.** Keys nur in `.env`.

## Zeitplan (Sa)

| Zeit | Was |
|---|---|
| 07:00 | Claude Code / Codex kurz anpingen (Usage-Fenster resettet ~12:00) |
| 09:15 | Opening & Challenge Reveal – Notizen in PLAYBOOK.md |
| ~10:00 | Starter Kit ins Repo, Baseline laufen lassen, **Score + Kosten notieren** |
| 10:45 | Ein Szenario manuell durchgehen: Was würden wir als Mensch tun? |
| 11:30 | Eval-Skript steht. Ab jetzt: eine Änderung → messen → behalten/verwerfen |
| 12:00 | Pizza |
| 15:30 | **Docker-Build lokal + offline testen** (`docker run --network none …`) |
| 16:30 | Feature Freeze. Nur noch Bugfixes. |
| 17:00 | **Abgabe – sharp!** |

## Baseline / Ergebnisse

| Version | Score | Kosten / Tokens | Notiz |
|---|---|---|---|
| Starter Kit | | | |
