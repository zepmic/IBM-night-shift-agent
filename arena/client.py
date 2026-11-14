"""Typed client for the Harness Arena Task API (v1).

Every call goes to ``{ARENA_BASE_URL}/api/v1`` with ``Authorization: Bearer <ARENA_API_KEY>``.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field

# Load ../.env and ./.env (existing environment variables win).
_here = Path(__file__).resolve().parent.parent
load_dotenv(_here.parent / ".env")
load_dotenv(_here / ".env")

Outcome = Literal["OK", "DENIED_SECURITY", "NEEDS_CLARIFICATION", "UNSUPPORTED"]
MAX_NOTE = 500  # characters in a run note (meta.note)


def git_meta(cwd: str | Path | None = None) -> dict:
    """``{commit, dirty}`` of the git checkout at ``cwd`` (default: this kit), or ``{}`` outside git or without git."""
    def git(*args: str) -> str | None:
        try:
            r = subprocess.run(["git", *args], cwd=cwd or _here, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout if r.returncode == 0 else None

    commit, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    if not commit or status is None:
        return {}
    return {"commit": commit.strip(), "dirty": bool(status.strip())}


class ArenaError(RuntimeError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class _Model(BaseModel):
    model_config = ConfigDict(extra="allow")  # tolerate new fields from the platform


class Task(_Model):
    task_id: str
    instruction: str
    level: int | None = None


class Run(_Model):
    run_id: str
    kind: str
    theme: str | None = None
    deadline_at: str | None = None
    tasks: list[Task] = Field(default_factory=list)


class Source(BaseModel):
    """A citation: path + the most specific locator for the file type.

    pdf -> page; csv/json -> record; xlsx/ods -> sheet + row; docx/odt -> paragraph;
    text/markdown -> line; png/jpg -> path only.
    """

    path: str
    page: int | None = None
    line: int | None = None
    record: str | None = None
    sheet: str | None = None
    row: int | None = None
    paragraph: int | None = None


class ToolSpec(_Model):
    name: str
    description: str = ""
    args: dict[str, str] = Field(default_factory=dict)


class BlobCache:
    """Content-addressed local cache: ``<root>/<sha256>``. A file's id is the sha256 of its bytes, so a cached blob
    never goes stale and can be shared by every task (and run) that uses the same file."""

    def __init__(self, root: str | Path | None = None):
        self.root = Path(root or os.environ.get("ARENA_BLOB_CACHE") or (_here / ".cache" / "blobs"))
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, sha256: str) -> Path:
        return self.root / sha256

    def get(self, sha256: str) -> bytes | None:
        p = self.path(sha256)
        try:
            data = p.read_bytes()
        except FileNotFoundError:
            return None
        if hashlib.sha256(data).hexdigest() != sha256:  # damaged on disk: drop it and download again
            p.unlink(missing_ok=True)
            return None
        return data

    def put(self, sha256: str, data: bytes) -> None:
        if hashlib.sha256(data).hexdigest() != sha256:
            raise ArenaError(f"blob {sha256[:12]}… does not match its sha256 (corrupt download?)")
        # Unique temp file per writer (several runs may share the cache), then an atomic rename.
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=f".{sha256[:16]}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp, self.path(sha256))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


# Tools that never change a task's files. Any other tool call may (write, containment, plans), so the cached manifest
# of that task is dropped and fetched again on the next download.
READ_ONLY_TOOLS = {"tree", "list", "ls", "read", "search", "grep", "query_logs", "access_path", "threat_intel",
                   "get_containment", "get_plan", "weather", "route"}


class ArenaClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: float = 60.0, retries: int = 3, cache: BlobCache | str | Path | None = None):
        self.base_url = (base_url or os.environ.get("ARENA_BASE_URL") or "http://localhost:3000").rstrip("/")
        self.api_key = api_key or os.environ.get("ARENA_API_KEY")
        if not self.api_key:
            raise ArenaError("ARENA_API_KEY is not set (copy .env.example to .env, or export it).")
        self.retries = retries
        self._http = httpx.Client(
            base_url=f"{self.base_url}/api/v1",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=timeout,
        )
        self.cache = cache if isinstance(cache, BlobCache) else BlobCache(cache)
        self._manifests: dict[tuple[str, str], dict[str, dict]] = {}
        self._lock = threading.Lock()
        self.stats = {"blob_downloads": 0, "blob_cache_hits": 0, "bytes_downloaded": 0}

    def _send(self, method: str, path: str, json: Any = None) -> httpx.Response:
        """Send with retries on network errors, 5xx and 429 (honouring Retry-After); raise ArenaError on other 4xx."""
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            delay = 0.5 * 2**attempt
            try:
                r = self._http.request(method, path, json=json)
            except httpx.TransportError as e:  # network problems: retry
                last = ArenaError(f"Cannot reach {self.base_url} ({type(e).__name__}: {e}). Is the platform URL right?")
            else:
                if r.status_code < 400:
                    return r
                try:
                    msg = r.json().get("error", r.text)
                except Exception:
                    msg = r.text[:300]
                if r.status_code == 429:  # per-team rate limit: back off as told
                    last = ArenaError(f"{method} {path} -> 429: {msg}", 429)
                    delay = max(delay, float(r.headers.get("retry-after", "1")))
                elif r.status_code >= 500:
                    last = ArenaError(f"{method} {path} -> {r.status_code}: {msg}", r.status_code)
                else:
                    hint = " (check ARENA_API_KEY)" if r.status_code == 401 else ""
                    raise ArenaError(f"{method} {path} -> {r.status_code}: {msg}{hint}", r.status_code)
            if attempt < self.retries:
                time.sleep(delay)
        assert last is not None
        raise last

    def _request(self, method: str, path: str, json: Any = None) -> Any:
        return self._send(method, path, json).json()

    # --- endpoints -------------------------------------------------------------------------
    def me(self) -> dict:
        return self._request("GET", "/me")

    def tools(self) -> list[ToolSpec]:
        data = self._request("GET", "/tools")
        items = data.get("tools", data) if isinstance(data, dict) else data
        return [ToolSpec.model_validate(t) for t in items]

    def start_run(self, kind: Literal["dev", "final"] = "dev", seed: int | None = None,
                  meta: dict | None = None) -> Run:
        """Dev runs: pass the `seed` of an earlier dev run to get the same tasks and answers again in a new surface.

        ``meta`` (e.g. ``{"note": "hypothesis"}``) is sent with the run, plus ``commit`` and ``dirty`` from git."""
        body: dict[str, Any] = {"kind": kind}
        if seed is not None:
            body["seed"] = seed
        meta = {**git_meta(), **(meta or {})}
        if meta:
            body["meta"] = meta
        return Run.model_validate(self._request("POST", "/runs", body))

    def get_run(self, run_id: str) -> dict:
        return self._request("GET", f"/runs/{run_id}")

    def list_runs(self) -> Any:
        return self._request("GET", "/runs")

    def call_tool(self, run_id: str, task_id: str, tool: str, args: dict | None = None) -> dict:
        """Returns ``{ok, result}`` or ``{ok: False, error}``. Tool-level errors are NOT exceptions."""
        res = self._request("POST", f"/runs/{run_id}/tasks/{task_id}/tools/{tool}", args or {})
        if tool not in READ_ONLY_TOOLS:
            with self._lock:
                self._manifests.pop((run_id, task_id), None)
        return res

    # --- content-addressed files: download every distinct file once per run -------------------------------------
    def task_manifest(self, run_id: str, task_id: str, refresh: bool = False) -> dict[str, dict]:
        """``{path: {sha256, size, kind, content_type, readable}}`` of a task's workspace in its current state."""
        key = (run_id, task_id)
        with self._lock:
            hit = self._manifests.get(key)
        if hit is not None and not refresh:
            return hit
        data = self._request("GET", f"/runs/{run_id}/tasks/{task_id}/manifest")
        m = {f["path"]: f for f in data.get("files", [])}
        with self._lock:
            self._manifests[key] = m
        return m

    def run_manifest(self, run_id: str) -> dict:
        """Distinct blobs of the run and, per task, ``path -> sha256`` (tasks in their initial state)."""
        return self._request("GET", f"/runs/{run_id}/manifest")

    def blob(self, run_id: str, sha256: str, task_id: str | None = None) -> bytes:
        """Bytes of a blob: from the local cache, else downloaded once and cached. ``task_id`` (a task whose manifest
        lists the blob) lets the platform find it without searching the whole run."""
        data = self.cache.get(sha256)
        if data is not None:
            with self._lock:
                self.stats["blob_cache_hits"] += 1
            return data
        url = f"/runs/{run_id}/blobs/{sha256}" + (f"?task={task_id}" if task_id else "")
        data = self._send("GET", url).content
        self.cache.put(sha256, data)
        with self._lock:
            self.stats["blob_downloads"] += 1
            self.stats["bytes_downloaded"] += len(data)
        return data

    def prefetch(self, run_id: str, workers: int = 8) -> dict:
        """Fetch the run manifest and every blob not cached yet (in parallel). Afterwards downloads need no network
        until a task changes its own files (drafts, containment state)."""
        m = self.run_manifest(run_id)
        types = {b["sha256"]: b for b in m.get("blobs", [])}
        with self._lock:
            for t in m.get("tasks", []):
                self._manifests[(run_id, t["task_id"])] = {
                    p: {"path": p, "sha256": h, **{k: types.get(h, {}).get(k) for k in ("size", "kind", "content_type")}}
                    for p, h in t["files"].items()}
        owner: dict[str, str] = {}
        for t in m.get("tasks", []):
            for h in t["files"].values():
                owner.setdefault(h, t["task_id"])
        missing = [h for h in types if self.cache.get(h) is None]
        before = self.stats["bytes_downloaded"]
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            list(ex.map(lambda h: self.blob(run_id, h, owner.get(h)), missing))
        return {"blobs": len(types), "downloaded": len(missing), "cached": len(types) - len(missing),
                "bytes": self.stats["bytes_downloaded"] - before}

    def download_file(self, run_id: str, task_id: str, path: str) -> tuple[bytes, str]:
        """Raw bytes of one workspace file (+ its content-type), through the manifest and the blob cache. Binary
        formats (pdf/docx/odt/xlsx/ods/png/jpg) are download-only — parse them locally (python-docx/openpyxl/odfpy/
        pypdf) or, for images, send them to vision."""
        p = path if path.startswith("/") else "/" + path
        try:
            entry = self.task_manifest(run_id, task_id).get(p) or self.task_manifest(run_id, task_id, refresh=True).get(p)
        except ArenaError as e:
            if e.status != 404:
                raise
            entry = None  # platform without manifests: plain download
        if entry and entry.get("sha256"):
            return self.blob(run_id, entry["sha256"], task_id), entry.get("content_type") or "application/octet-stream"
        r = self._send("GET", f"/runs/{run_id}/tasks/{task_id}/files{p}")
        return r.content, r.headers.get("content-type", "application/octet-stream")

    def download_workspace(self, run_id: str, task_id: str) -> bytes:
        """The whole task workspace as one zip of raw files (fetch once, work locally)."""
        return self._send("GET", f"/runs/{run_id}/tasks/{task_id}/workspace.zip").content

    def submit(self, run_id: str, task_id: str, outcome: Outcome, answer: Any,
               sources: list[Source | dict] | None = None) -> dict:
        srcs = [s.model_dump(exclude_none=True) if isinstance(s, Source) else s for s in (sources or [])]
        body = {"outcome": outcome, "answer": answer, "sources": srcs}
        return self._request("POST", f"/runs/{run_id}/tasks/{task_id}/submit", body)

    def finish(self, run_id: str) -> dict:
        return self._request("POST", f"/runs/{run_id}/finish")
