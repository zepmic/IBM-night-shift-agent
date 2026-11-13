# Docker-Setup getestet

**Wer:** Michel (+ Claude Code) · **Zeit:** Fr 13.11. 13:00 · **Typ:** Setup

- Docker 29.5.3 läuft auf Michels Laptop, der Repo-Ordner ist als Bind Mount in Container eingebunden und sichtbar.
- Test: `docker run --rm -v "$PWD":/app alpine:3.20 ls -la /app`
- Michels lokaler Pfad enthält ein Leerzeichen (`Meine Ablage`) → Pfade in Docker-Befehlen immer quoten (`"$PWD"`).
- Der Ordner liegt evtl. in einem Google-Drive-Sync. Falls es langsam wird oder Sync-Konflikte gibt: `.venv` außerhalb anlegen bzw. von `uv` verwalten lassen.

**Folge für andere:** Mindestens Michel kann lokal und offline (`--network none`) testen, ohne Test-Submissions zu verbrauchen.
