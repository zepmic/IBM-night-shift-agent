"""`arena` command for a coding agent working on one task (used by run_pi.py).

    arena tools                          list the Task API tools and their arguments
    arena tool <name> '<json args>'      call a tool, e.g.  arena tool weather '{"location": "S-04"}'
    arena submit '<json submission>'     submit {"outcome", "answer", "sources"} (once per task)

Reads ARENA_BASE_URL, ARENA_API_KEY, ARENA_RUN_ID and ARENA_TASK_ID from the environment.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # starter-kit root, for `arena.client`

from arena.client import ArenaClient, ArenaError  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    client = ArenaClient()
    run_id, task_id = os.environ["ARENA_RUN_ID"], os.environ["ARENA_TASK_ID"]
    cmd = argv[0]
    try:
        if cmd == "tools":
            for t in client.tools():
                print(f"{t.name}: {t.description}\n    args: {json.dumps(t.args)}")
            return 0
        if cmd == "tool" and len(argv) >= 2:
            args = json.loads(argv[2]) if len(argv) > 2 else {}
            print(json.dumps(client.call_tool(run_id, task_id, argv[1], args), indent=1, ensure_ascii=False))
            return 0
        if cmd == "submit" and len(argv) == 2:
            sub = json.loads(argv[1])
            res = client.submit(run_id, task_id, sub.get("outcome", "OK"), sub.get("answer"), sub.get("sources", []))
            if os.environ.get("ARENA_SUBMITTED_FLAG"):
                Path(os.environ["ARENA_SUBMITTED_FLAG"]).write_text("1")
            print(json.dumps(res, ensure_ascii=False))
            return 0
    except json.JSONDecodeError as e:
        print(f"ERROR: argument is not valid JSON ({e}). Quote it in single quotes.", file=sys.stderr)
        return 2
    except ArenaError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
