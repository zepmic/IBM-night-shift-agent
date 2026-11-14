"""Offline test of the content-addressed blob cache against the mock server: python tests/test_cache.py"""
import pathlib
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mock_server  # noqa: E402
from arena.client import ArenaClient, ArenaError, BlobCache  # noqa: E402

srv = ThreadingHTTPServer(("127.0.0.1", 0), mock_server.H)
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{srv.server_address[1]}"

with tempfile.TemporaryDirectory() as d:
    c = ArenaClient(base_url=base, api_key="arena_test", cache=d)
    st = c.prefetch("mock")
    n = len(mock_server.FILES)
    assert st == {"blobs": n, "downloaded": n, "cached": 0, "bytes": st["bytes"]} and st["bytes"] > 0, st
    assert mock_server.STATE["blob_gets"] == n
    assert all(q.startswith("task=") for q in mock_server.STATE["blob_queries"]), "prefetch passes a task hint"
    data, ctype = c.download_file("mock", "t01", "/data/shelters.csv")
    assert data.decode() == mock_server.FILES["/data/shelters.csv"] and ctype.startswith("text/")
    c.download_file("mock", "t02", "data/shelters.csv")  # other task, same blob, path without leading slash
    assert mock_server.STATE["blob_gets"] == n, "cached blobs must not be downloaded again"
    # A fresh client sharing the cache directory downloads nothing.
    c2 = ArenaClient(base_url=base, api_key="arena_test", cache=d)
    assert c2.prefetch("mock")["downloaded"] == 0 and mock_server.STATE["blob_gets"] == n
    # A state-changing tool call drops the task's cached manifest.
    c2.call_tool("mock", "t01", "write", {"path": "/drafts/x.md", "content": "x"})
    assert ("mock", "t01") not in c2._manifests and ("mock", "t02") in c2._manifests
    # A blob damaged on disk is dropped and downloaded again.
    h = next(iter(c.cache.root.glob("[0-9a-f]" * 64)))
    h.write_bytes(b"damaged")
    assert c.cache.get(h.name) is None and not h.exists()
    # Writers never share a temp file and leave none behind.
    blob = mock_server.FILES["/data/shelters.csv"].encode()
    sha_ = __import__("hashlib").sha256(blob).hexdigest()
    ts = [threading.Thread(target=BlobCache(d).put, args=(sha_, blob)) for _ in range(16)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert BlobCache(d).get(sha_) == blob and not list(pathlib.Path(d).glob("*.tmp"))
    # Corrupt data never enters the cache.
    try:
        BlobCache(d).put("0" * 64, b"not matching")
        raise SystemExit("corrupt blob accepted")
    except ArenaError:
        pass
srv.shutdown()
print("cache tests ok")
