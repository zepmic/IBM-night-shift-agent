"""Start an empty dev run and finish it at once: $0, and the platform reveals all 48 tasks of a fresh scenario with
their expected answers (challenge/01-task-api.md, "Dev answer reveal"). Saves runs/<run_id>.json and prints the id.

    PYTHONPATH=. uv run python eval/offline/fresh.py
    PYTHONPATH=. uv run python -W ignore eval/offline/inc_check.py <run_id> all     # incident families vs. expected
    PYTHONPATH=. uv run python -W ignore eval/offline/ar_check.py <run_id>          # access review
    PYTHONPATH=. uv run python -W ignore eval/offline/mcp.py <run_id>               # manifest audit (uses Jev)
    PYTHONPATH=. uv run python -W ignore eval/offline/board.py <run_id>             # board triage (uses Jev)
"""
import json
import os

from dotenv import load_dotenv

load_dotenv(".env")
from arena.client import ArenaClient  # noqa: E402

c = ArenaClient()
run = c.start_run("dev", meta={"note": "empty run: no model calls, fresh scenario + revealed answers for offline checks"})
rid = run.run_id if hasattr(run, "run_id") else run["run_id"]
c.finish(rid)
r = c.get_run(rid)
os.makedirs("runs", exist_ok=True)
json.dump(r, open(f"runs/{rid}.json", "w"), ensure_ascii=False)
print(rid, "seed", r.get("seed"), "cost", r.get("cost_usd"), "tasks", len(r["tasks"]))
