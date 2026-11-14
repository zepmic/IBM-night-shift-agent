# Docker lokal gegen Mock getestet – ohne Dev-Keys

**Wer:** Daniel (+ Claude Code) · **Zeit:** Sa 11:00 · **Typ:** Setup + Erkenntnis

## Ergebnis
- `docker build -t nightshift:local .` → ok, **~19 s**, Image **525 MB** (Limit 2 GB).
- `tests/test_offline.py` im Container mit `--network none` → **ok**.
- Agent im Container gegen `tests/mock_server.py` (eigenes internes Docker-Netz, kein Internet, keine echten Keys) → Run startet, Tasks werden geholt, **bricht erst beim LLM-Call ab** (`OPENROUTER_API_KEY is not set`). Die Kette Container → Task API funktioniert.
- Kosten: **$0**, kein Dev-Budget verbraucht.

## So nachmachen (kostenlos)

```bash
docker build -t nightshift:local .
docker run --rm --network none --entrypoint python nightshift:local tests/test_offline.py
docker network create --internal nstest
docker run -d --name nsmock --network nstest --entrypoint python nightshift:local tests/mock_server.py
docker run --rm --network container:nsmock -e ARENA_BASE_URL=http://localhost:3999 -e ARENA_API_KEY=arena_test nightshift:local --kind dev --note "mock"
docker rm -f nsmock && docker network rm nstest
```

Stolperfalle: Der Mock bindet nur `127.0.0.1` → Agent-Container muss mit `--network container:nsmock` dessen Netz teilen.

## Erkenntnis – wichtig fürs Final
Wenn der LLM-Call scheitert, gibt der Agent **gar nichts ab** (`ERROR`, Exit-Code trotzdem 0). Unbeantwortete Tasks = 0 Punkte. → Wir brauchen einen **Fallback-Submit** (Best Guess / `UNSUPPORTED`), wenn LLM oder Loop scheitern.

## Regel
Keine Runs mit den Dev-Keys ohne Rückfrage im Team. Erst lokal mit Mock + Docker testen.
