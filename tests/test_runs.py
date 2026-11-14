"""Offline test of run metadata (commit, dirty, --note) and ARENA_RUN_KIND against the mock server:
python tests/test_runs.py"""
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT))
sys.path.insert(0, str(KIT / "tests"))
import mock_server  # noqa: E402
import arena.client as client_mod  # noqa: E402
from arena.client import MAX_NOTE, ArenaClient, git_meta  # noqa: E402

srv = ThreadingHTTPServer(("127.0.0.1", 0), mock_server.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"
bodies = mock_server.STATE.setdefault("run_bodies", [])


def git(cwd, *args):
    cfg = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false",
           "-c", "core.hooksPath=/dev/null"]
    subprocess.run(["git", *cfg, *args], cwd=cwd, check=True, capture_output=True)


with tempfile.TemporaryDirectory() as tmp:
    tmp = pathlib.Path(tmp)
    repo = tmp / "repo"
    repo.mkdir()

    # git_meta: nothing outside a repo or before the first commit, else HEAD and whether the tree is dirty.
    assert git_meta(repo) == {}
    git(repo, "init", "-q")
    assert git_meta(repo) == {}
    (repo / "a.txt").write_text("a")
    git(repo, "add", "a.txt")
    git(repo, "commit", "-q", "-m", "a")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    assert git_meta(repo) == {"commit": head, "dirty": False}
    (repo / "b.txt").write_text("b")
    assert git_meta(repo) == {"commit": head, "dirty": True}
    path = os.environ["PATH"]
    os.environ["PATH"] = str(tmp / "no-git-here")
    try:
        assert git_meta(repo) == {}, "missing git is silently omitted"
    finally:
        os.environ["PATH"] = path

    # start_run sends meta = git info + the caller's meta, and no meta key when there is nothing to send.
    c = ArenaClient(base_url=base, api_key="arena_test", cache=tmp / "cache")
    c.start_run("dev", meta={"note": "jev pre-filter"})
    assert bodies[-1] == {"kind": "dev", "meta": {**git_meta(), "note": "jev pre-filter"}}, bodies[-1]
    real_git_meta = client_mod.git_meta
    client_mod.git_meta = lambda cwd=None: {}
    try:
        c.start_run("dev", seed=7)
        assert bodies[-1] == {"kind": "dev", "seed": 7}, bodies[-1]
        c.start_run("dev", meta={"note": "n"})
        assert bodies[-1] == {"kind": "dev", "meta": {"note": "n"}}, bodies[-1]
    finally:
        client_mod.git_meta = real_git_meta

    # main.py: --kind defaults to ARENA_RUN_KIND, no confirmation prompt then (stdin is closed), note in the header.
    def main(*args, run_kind=None):
        env = {k: v for k, v in os.environ.items() if k != "ARENA_RUN_KIND"}
        env.update(ARENA_BASE_URL=base, ARENA_API_KEY="arena_test", ARENA_BLOB_CACHE=str(tmp / "cache"))
        if run_kind is not None:
            env["ARENA_RUN_KIND"] = run_kind
        return subprocess.run([sys.executable, str(KIT / "main.py"), "--tasks", "none", *args], cwd=tmp, env=env,
                              stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)

    r = main("--note", "container test", run_kind="final")
    assert r.returncode == 0, r.stderr
    assert bodies[-1]["kind"] == "final" and bodies[-1]["meta"]["note"] == "container test", bodies[-1]
    header = next(l for l in r.stdout.splitlines() if l.startswith("run "))
    assert header.startswith("run mock (final") and header.endswith(", note: container test"), header
    r = main()
    assert r.returncode == 0, r.stderr
    assert bodies[-1]["kind"] == "dev" and "note" not in bodies[-1].get("meta", {}), bodies[-1]
    r = main("--kind", "dev", run_kind="final")
    assert r.returncode == 0 and bodies[-1]["kind"] == "dev", "an explicit --kind wins"
    n = len(bodies)
    assert main(run_kind="nightly").returncode == 2
    assert main("--note", "x" * (MAX_NOTE + 1)).returncode == 2
    assert len(bodies) == n, "invalid arguments start no run"

    # Task selection: --tasks, --level, --match, --limit (applied in that order); bad values start no run.
    from arena.client import Task  # noqa: E402
    from main import select_tasks  # noqa: E402
    ts = [Task(task_id=f"t0{i}", level=lvl, instruction=ins) for i, (lvl, ins) in
          enumerate([(1, "Rotate TOK-1"), (2, "Containment plan"), (1, "Summarise"), (3, "rotation window")], 1)]
    ids = lambda xs: [t.task_id for t in xs]  # noqa: E731
    assert ids(select_tasks(ts)) == ["t01", "t02", "t03", "t04"]
    assert ids(select_tasks(ts, levels="1")) == ["t01", "t03"]
    assert ids(select_tasks(ts, match="rotat|contain")) == ["t01", "t02", "t04"]
    assert ids(select_tasks(ts, ids="t02,t04", levels="3")) == ["t04"]
    assert ids(select_tasks(ts, levels="1,3", limit=2)) == ["t01", "t03"]
    n = len(bodies)
    assert main("--level", "4").returncode == 2 and main("--match", "(").returncode == 2
    assert len(bodies) == n

srv.shutdown()
print("run meta tests ok")
