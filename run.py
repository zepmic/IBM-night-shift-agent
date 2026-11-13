"""Benchmark-Runner: lokale Aufgaben laufen lassen, Genauigkeit + Kosten messen.

  MOCK=1 uv run run.py                 # offline testen
  uv run run.py --docs data/docs --tasks data/tasks.jsonl

Am Hackathon: `load_tasks` / `submit` an die Live-Benchmark-API anpassen.
"""
from __future__ import annotations

import argparse
import json
import time

from dotenv import load_dotenv

load_dotenv()

from harness.agent import Agent  # noqa: E402
from harness.llm import LLM  # noqa: E402
from harness.retrieval import Index  # noqa: E402


def load_tasks(path: str) -> list[dict]:
    return [json.loads(line) for line in open(path) if line.strip()]


def is_correct(pred: str, gold: str) -> bool:
    return gold.lower() in str(pred).lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="data/docs")
    ap.add_argument("--tasks", default="data/tasks.jsonl")
    args = ap.parse_args()

    llm = LLM()
    agent = Agent(Index.from_dir(args.docs), llm)
    n_ok = n_src = 0
    tasks = load_tasks(args.tasks)
    for t in tasks:
        t0 = time.time()
        r = agent.run(t["question"])
        ok = is_correct(r.get("answer", ""), t.get("gold", ""))
        src_ok = set(r.get("sources", [])) == set(t.get("gold_sources", []))
        n_ok += ok
        n_src += src_ok
        print(f"{'✅' if ok else '❌'}{'📎' if src_ok else '  '} {t['id']}: {r.get('answer')!r:60.60} "
              f"src={r.get('sources')} conf={r.get('confidence')} {time.time() - t0:.1f}s")
    n = len(tasks)
    print(f"\nAntworten {n_ok}/{n} · Quellen {n_src}/{n} · {llm.budget.summary()}")


if __name__ == "__main__":
    main()
