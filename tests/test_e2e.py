"""Offline end to end: main.py against the mock Task API and its scripted model. No keys, no network; also runs in
the image:  docker run --rm --network none --entrypoint python <image> tests/test_e2e.py"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

KIT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KIT / "tests"))
import mock_server  # noqa: E402

srv = ThreadingHTTPServer(("127.0.0.1", 0), mock_server.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
url = f"http://127.0.0.1:{srv.server_address[1]}"
with tempfile.TemporaryDirectory() as d:
    env = {**os.environ, "ARENA_BASE_URL": url, "ARENA_API_KEY": "arena_test", "OPENROUTER_API_KEY": "sk-or-mock",
           "OPENROUTER_BASE_URL": f"{url}/api/v1", "ARENA_RUN_KIND": "dev", "ARENA_BLOB_CACHE": f"{d}/blobs"}
    r = subprocess.run([sys.executable, str(KIT / "main.py"), "--note", "e2e mock"], cwd=d, env=env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert mock_server.STATE["submitted"] == {"t01": 1.0, "t02": 1.0}, (mock_server.STATE, r.stdout)
    run = pathlib.Path(d) / "runs" / "mock"
    ev = {t: [json.loads(l) for l in (run / f"{t}.jsonl").read_text().splitlines()] for t in ("t01", "t02")}
    sub = {t: next(e for e in ev[t] if e["event"] == "submit") for t in ev}
    # the model cited only the rules file / nothing: the harness added the record and the line that carry the answer
    assert sub["t01"]["args"]["sources"] == [{"path": "/mission.md", "line": 2}, {"path": "/data/shelters.csv", "record": "S-02"}], sub["t01"]
    assert sub["t02"]["args"]["sources"] == [{"path": "/inbox/msg_01.txt", "line": 1}], sub["t02"]
    assert all("fallback" not in s for s in sub.values())
    assert "/data/: contacts.csv, shelters.csv" in mock_server.STATE["first_prompt"], "the workspace map goes out with the task"
    assert "=== OPERATOR FILE /AGENTS.md ===\n# Operator rules" in mock_server.STATE["first_prompt"], "and the rule file"
    end = ev["t01"][-1]
    assert end["event"] == "end" and abs(end["cost_usd"] - 0.0003) < 1e-9 and end["llm_calls"] == 3, end
    print(r.stdout.strip().splitlines()[-4])
srv.shutdown()
print("e2e test ok")
