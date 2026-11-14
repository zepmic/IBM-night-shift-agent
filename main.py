"""CLI: start a run, solve its tasks in parallel with agent.py, finish the run, print a summary.

    uv run main.py --kind dev --note "hypothesis" [--tasks t01,t03] [--model ...] [--parallel 4]
    uv run main.py --kind dev --level 1 --limit 6       # a cheap start: 6 straightforward tasks
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from agent import Budget, Config, solve_task
from arena import llm
from arena.client import MAX_NOTE, ArenaClient, ArenaError


def select_tasks(tasks: list, ids: str | None = None, levels: str | None = None, match: str | None = None,
                 limit: int | None = None) -> list:
    """--tasks, --level, --match and --limit, applied in that order."""
    if ids:
        want = set(ids.split(","))
        tasks = [t for t in tasks if t.task_id in want]
    if levels:
        want_levels = {int(x) for x in levels.split(",")}
        tasks = [t for t in tasks if t.level in want_levels]
    if match:
        rx = re.compile(match, re.IGNORECASE)
        tasks = [t for t in tasks if rx.search(t.instruction)]
    return tasks[:limit] if limit is not None else tasks


def main() -> int:
    sys.stdout.reconfigure(line_buffering=True)  # progress lines show up even when output goes to a file
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    env_kind = os.environ.get("ARENA_RUN_KIND")  # set in the organisers' container
    p.add_argument("--kind", choices=["dev", "final"], default=env_kind or "dev",
                   help="default: $ARENA_RUN_KIND, else dev. The final runs in the organisers' container")
    p.add_argument("--note", help=f"hypothesis for this run, stored with it (max {MAX_NOTE} characters)")
    p.add_argument("--seed", type=int, help="dev only: replay the tasks of an earlier dev run (same answers, new surface)")
    p.add_argument("--tasks", help="comma-separated task ids to solve (default: all; dev ids are reshuffled every run)")
    p.add_argument("--level", help="only these levels, e.g. 1 or 1,2 (1 = straightforward, 3 = hard)")
    p.add_argument("--match", help="only tasks whose instruction matches this regex (case-insensitive), e.g. 'rotat|contain'")
    p.add_argument("--limit", type=int, help="solve at most N of the selected tasks")
    p.add_argument("--model", default=llm.MAIN_MODEL, help="chat model (default %(default)s; use a :free model to test)")
    p.add_argument("--parallel", type=int, default=6)  # full run at 6 took ~13 min; the final stops at 30
    p.add_argument("--max-steps", type=int, default=Config.max_steps)
    p.add_argument("--max-tokens", type=int, default=4096)
    p.add_argument("--temperature", type=float, default=0.2)
    p.add_argument("--reasoning-effort", choices=["none", "low", "medium", "high"], default=None)
    p.add_argument("--jev-inbox-check", action="store_true", help="example: Jev flags injection-like content in read results")
    p.add_argument("--no-auto-sources", action="store_true", help="submit only the model's own citations (A/B against sources.py)")
    p.add_argument("--budget", type=float, default=float(os.environ["ARENA_BUDGET_USD"]) if os.environ.get("ARENA_BUDGET_USD") else None,
                   help="stop spending at this many USD (default: 2.70 for a final run, no limit for dev)")
    p.add_argument("--prefetch", action="store_true", help="download every distinct file of the run once at start (blob cache)")
    p.add_argument("--yes", action="store_true", help="do not ask for confirmation on --kind final")
    a = p.parse_args()
    if a.kind not in ("dev", "final"):
        p.error(f"ARENA_RUN_KIND must be dev or final, not {a.kind!r}")
    if a.note and len(a.note) > MAX_NOTE:
        p.error(f"--note is {len(a.note)} characters; the limit is {MAX_NOTE}")
    if a.level and not re.fullmatch(r"[123](,[123])*", a.level):
        p.error(f"--level takes levels 1-3, comma-separated, not {a.level!r}")
    if a.match:
        try:
            re.compile(a.match)
        except re.error as e:
            p.error(f"--match is not a valid regex: {e}")

    client = ArenaClient()
    if a.kind == "final" and not a.yes and not env_kind:
        print("Final runs are started by the organisers' runner from your latest upload; team keys can't start them.")
        if input("Type 'final' to continue: ").strip() != "final":
            return 1
    try:
        tool_specs = client.tools()
        run = client.start_run(a.kind, seed=a.seed if a.kind == "dev" else None,
                               meta={"note": a.note} if a.note else None)
    except ArenaError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    tasks = select_tasks(run.tasks, ids=a.tasks, levels=a.level, match=a.match, limit=a.limit)
    if run.kind == "final" and len(tasks) < len(run.tasks):
        print(f"warning: a final run with {len(tasks)} of {len(run.tasks)} tasks selected; the others score 0", file=sys.stderr)
    # After a container restart the final continues the same run: skip what is already submitted (it can't change,
    # and re-solving it only costs money).
    try:
        done = {t["task_id"] for t in client.get_run(run.run_id).get("tasks", []) if t.get("submitted")}
    except ArenaError:
        done = set()
    if done:
        print(f"resuming: {len(done)} task(s) already submitted, skipped")
        tasks = [t for t in tasks if t.task_id not in done]
    seed = (run.model_extra or {}).get("seed")
    print(f"run {run.run_id} ({run.kind}, theme={run.theme}{f', seed={seed}' if seed is not None else ''}), {len(tasks)} tasks, model={a.model}"
          + (f", note: {a.note}" if a.note else ""))

    if a.prefetch:
        t0 = time.time()
        try:
            st = client.prefetch(run.run_id)
            print(f"prefetch: {st['blobs']} distinct files, {st['downloaded']} downloaded ({st['bytes'] / 1e6:.1f} MB), "
                  f"{st['cached']} already cached, {time.time() - t0:.1f}s")
        except ArenaError as e:
            print(f"prefetch skipped: {e}")

    # Leave 3 minutes before the platform's deadline (final: 30 min after the run started; dev runs have none).
    try:
        deadline = datetime.fromisoformat(run.deadline_at.replace("Z", "+00:00")).timestamp() - 180
    except (AttributeError, ValueError):
        deadline = time.time() + 27 * 60 if run.kind == "final" else None
    cfg = Config(model=a.model, max_steps=a.max_steps, max_tokens=a.max_tokens, temperature=a.temperature,
                 reasoning_effort=a.reasoning_effort, jev_inbox_check=a.jev_inbox_check,
                 auto_sources=not a.no_auto_sources, deadline=deadline,
                 budget=Budget(a.budget if a.budget is not None else 2.70 if run.kind == "final" else None, len(tasks)))
    tracker = llm.CostTracker()
    out_dir = Path("runs") / run.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    lock = threading.Lock()

    def work(task):
        t0 = time.time()
        with open(out_dir / f"{task.task_id}.jsonl", "w") as f:
            def trace(e):
                with lock:
                    f.write(json.dumps({"t": round(time.time() - t0, 2), **e}, ensure_ascii=False, default=str) + "\n")
                    f.flush()
            try:
                res = solve_task(client, run.run_id, task, tool_specs, cfg, tracker, trace)
            except Exception as e:  # never let one task kill the run
                res = {"error": f"{type(e).__name__}: {e}"}
                trace({"event": "crash", "error": res["error"]})
        print(f"  {task.task_id} done in {time.time() - t0:.0f}s: {_fmt(res)}")
        return task.task_id, res

    with ThreadPoolExecutor(max_workers=max(1, a.parallel)) as ex:
        results = dict(ex.map(work, tasks))

    try:
        fin = client.finish(run.run_id)
    except ArenaError as e:
        fin = {"error": str(e)}

    print("\n" + "-" * 78)
    for tid, res in sorted(results.items()):
        print(f"{tid:5} {_fmt(res)}")
    scores = [r["score"] for r in results.values() if isinstance(r.get("score"), (int, float))]
    if scores:
        print(f"\nlocal accuracy (dev feedback): {sum(scores) / len(tasks):.3f} over {len(tasks)} tasks")
    print(f"local cost tally: ${tracker.total:.4f} in {tracker.calls} calls "
          f"({tracker.prompt_tokens} in / {tracker.completion_tokens} out tokens) {dict(tracker.by_model)}")
    print(f"files: {client.stats['blob_downloads']} blob downloads ({client.stats['bytes_downloaded'] / 1e6:.1f} MB), "
          f"{client.stats['blob_cache_hits']} cache hits")
    # The full finish response (per-task expected answers once a dev run ends) is long: save it, print the summary.
    (out_dir / "finish.json").write_text(json.dumps(fin, ensure_ascii=False, indent=1))
    keys = ("status", "tasks_submitted", "tasks_total", "accuracy", "cost_usd", "cost_score", "final_score", "error")
    print("platform finish: " + json.dumps({k: fin[k] for k in keys if k in fin}, ensure_ascii=False) + f" (full response: {out_dir}/finish.json)")
    print(f"traces: {out_dir}/")
    return 0


def _fmt(res: dict) -> str:
    if "error" in res:
        return f"ERROR {res['error'][:200]}"
    fb = res.get("feedback", res)
    return fb if isinstance(fb, str) else " | ".join(map(str, fb)) if isinstance(fb, list) else json.dumps(fb, ensure_ascii=False)


if __name__ == "__main__":
    sys.exit(main())
