# Donaufriends (team-02) – IBM Night Shift Agent

Efficient Local Agents Hackathon · IBM Vienna · Sa 14.11.2026
Challenge: **The MuggingFace Incident** – Small model. Smart harness.

Unser Agent löst die Incident-Tasks der Task API – **korrekt und billig**.
Modell: **`google/gemma-4-31b-it`** (+ `typesafe/jev-1.14`, `qwen/qwen3-embedding-8b`). Dev-Budget **$15**.

- Kit-Doku (Befehle, Flags): [README.md](README.md)
- Regeln für Agents: [AGENTS.md](AGENTS.md)
- Strategie: [plans/](plans/) (Plan A + B1 + B4) und [PLAYBOOK.md](PLAYBOOK.md)
- Entscheidungen: [JOURNAL.md](JOURNAL.md)

## Setup

```bash
git clone https://github.com/zepmic/IBM-night-shift-agent.git
cd IBM-night-shift-agent
cp .env.example .env   # ARENA_API_KEY + OPENROUTER_API_KEY vom Dashboard / Team eintragen
uv sync
uv run main.py --kind dev --tasks t01 --note "baseline"
```

Pakete hinzufügen: `uv add <paket>` (aktualisiert `pyproject.toml` + `uv.lock` – beide committen).
uv installieren (Mac): `brew install uv`

**Budget schonen:** `--tasks t01,t03`, `--level 1 --limit 6`, `--match '<regex>'`, `--seed <seed> --tasks …`. Voller Run (48 Tasks) nur zur Bestätigung.

## Team & Rollen

| Rolle | Wer | Verantwortung |
|---|---|---|
| Infra | _TBD_ | Client, Workspace-Spiegel, Parser mit Locators, Dockerfile, Budget-/Zeit-Wächter, Submit |
| Solver | _TBD_ | Instruktions-Parser, Compiler (B1), Agent-Loop-Fallback |
| Eval + Sicherheit | _TBD_ | Datensammler, Offline-Eval, Guardrails, Antwort-Validator |
| Breaker | _TBD_ | Break-it-Angriffe (B4), fremde Treffer → Guardrail-Tests |

## Git-Regeln

- `main` ist **immer lauffähig**.
- Code auf eigenem Branch: `name/feature` (z. B. `michel/json-retry`). Merge nach erfolgreichem Eval-Lauf.
- **Vor jedem Run committen**, immer mit `--note "<Hypothese>"`.
- **Keine Keys committen.** Keys nur in `.env`.
- **Kontext sofort teilen:** Veranstalter-Infos → `challenge/`, Erkenntnisse/Messwerte → `context/`, Entscheidungen → `JOURNAL.md`. Doku direkt auf `main` und sofort pushen. Details: [context/README.md](context/README.md).
- Vor jeder Aufgabe: `git pull --rebase`.

## Zeitplan (Sa)

| Zeit | Was |
|---|---|
| ~10:00 | Baseline: `uv run main.py --kind dev --tasks t01 --note "baseline"`, **Score + Kosten notieren** |
| 10:30 | Erster Break-it-Angriff (B4) |
| 11:30 | Datensammler + Offline-Eval stehen |
| 12:00 | Pizza |
| 14:00 | **Demo-Submission 1** |
| 16:30–16:45 | **Final-Submission hochladen** |
| 17:00 | Alles gesperrt |

## Baseline / Ergebnisse

| Version | Run-ID | Tasks | Score | Kosten | Notiz |
|---|---|---|---|---|---|
| Starter Kit (c2ab907) | run_7FdiWah57oDE | t01 | 0.77 (Sources 1/4) | $0.0045–0.007 | Antwort richtig, Quellen unvollständig. Details: [context/1000-michel-baseline.md](context/1000-michel-baseline.md) |
| Router-Fix + earliest_slot (0af3cc7) | run_hP6Aq5nhZhYl | alle 48 | A 0.557 · final 0.322 | $1.70 | erster voller Run, Kosten zu hoch ([context/1315](context/1315-paul-tools-kosten.md)) |
| + max_steps 14 (a0ae1fb) | run_VLE9AicO_TF3 | alle 48 (Replay) | A 0.578 · final 0.348 | $1.24 | gleicher Seed, −27 % Kosten |
| + alle Code-Tools (431e3ec) | run__8OvzdDTetNJ | alle 48, frischer Seed | **A 0.700 · final 0.434** | **$0.97** | 0 Regelverstöße, 11/48 am Schrittlimit ([context/1335](context/1335-paul-uebergabe.md)) |
