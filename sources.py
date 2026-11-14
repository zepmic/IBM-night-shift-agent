"""Evidence ledger: which file lines / records / pages the agent has actually seen in tool results, and which of
them literally carry the values of the final answer.

Why: the model cites from memory, and old tool outputs are trimmed from its context, so it tends to cite only the
last file it looked at (baseline: answer right, sources 1/4). The harness has seen every tool result with its
locators; at submit time it adds the few places that unambiguously support the answer. Deterministic, no model call.

Precision over recall: a place is added only when an id-like value of the answer (agent id, token id, address,
domain…) occurs there, and only when that value occurs in at most MAX_PER_FILE places of that file. A value that is
all over a file (an agent in an audit log) is left to the model's own citation.

Everything in here is data handling: text from the workspace is matched, never interpreted.
"""
from __future__ import annotations

import json
import re
from typing import Any

MAX_PER_FILE = 2      # an answer value found in more places of one file than this is ambiguous there: add nothing
LINE_TOLERANCE = 2    # the grader accepts a text line within ±2
LOCATOR_KEYS = ("line", "record", "page", "paragraph", "sheet", "row")

_NUMBERED = re.compile(r"^\s*(\d+)\s*[:|\t]\s?(.*)$")
_HIT = re.compile(r"^(/[^\s:]+):(\d+)(?::\s?(.*))?$", re.S)
_DATE_LIKE = re.compile(r"\d{1,4}[.\-/:]\d")


def norm_path(p: Any) -> str:
    p = str(p or "").strip()
    return p if p.startswith("/") or not p else "/" + p


def answer_values(answer: Any) -> list[str]:
    """Id-like strings in the answer: at least 3 characters and a digit or one of - _ @ . in them. Plain words and
    bare numbers match too much text to prove anything."""
    out: list[str] = []

    def walk(v: Any) -> None:
        if isinstance(v, str):
            s = v.strip()
            if 3 <= len(s) <= 80 and " " not in s and re.search(r"[\d\-_@.]", s) and not re.fullmatch(r"[\d.,\-]+", s) \
                    and s not in out:
                out.append(s)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)

    walk(answer)
    return out


def _contains(text: str, value: str) -> bool:
    return re.search(r"(?<![\w\-.@])" + re.escape(value) + r"(?![\w\-@]|\.\w)", text, re.I) is not None


class Evidence:
    """Places seen in tool results: (path, locator) -> text."""

    def __init__(self) -> None:
        self.items: dict[tuple, dict] = {}   # key -> {"source": {...}, "text": str}
        self.paths: set[str] = set()         # files opened or named with a line by a tool
        self.csv_ids: dict[str, bool] = {}   # csv path -> its first column is a record id (header seen)

    # --- recording ----------------------------------------------------------------------------------------------
    def _add(self, path: str, text: str, **loc: Any) -> None:
        path = norm_path(path)
        loc = {k: v for k, v in loc.items() if v is not None}
        key = (path, *sorted((k, str(v)) for k, v in loc.items()))
        self.paths.add(path)
        self.items.setdefault(key, {"source": {"path": path, **loc}, "text": text})

    def add_tool(self, name: str, args: dict, result: Any, max_chars: int = 8000) -> None:
        """A Task API tool result (the `result` of an ok call). Formats differ per tool, so: `read` is parsed as the
        lines of args.path; anything else is searched for {path|file, line} objects and "path:line: text" strings."""
        try:
            if name == "read" and isinstance(args.get("path"), str):
                self._add_read(args["path"], result, _int(args.get("start_line")) or 1, max_chars)
            else:
                self._walk(result)
        except Exception:  # noqa: BLE001 - the ledger is a bonus; an odd result format must not break the task
            pass

    def _add_read(self, path: str, result: Any, start: int, max_chars: int) -> None:
        lines = _numbered_lines(result, start)
        path = norm_path(path)
        low = path.lower()
        used = 0
        for n, text in lines:
            used += len(text) + 1
            if used > max_chars:  # the model only saw the output up to the cap
                break
            if not text.strip():
                continue
            if n == 1 and low.endswith(".csv"):  # header row: is the first column a record id?
                self.csv_ids[path] = re.fullmatch(r"(\w*_)?id", text.split(",", 1)[0].strip().strip('"').lower()) is not None
                continue
            self._add_line(path, n, text, text)

    def _walk(self, v: Any) -> None:
        if isinstance(v, dict):
            p = v.get("path") if isinstance(v.get("path"), str) else v.get("file") if isinstance(v.get("file"), str) else None
            n = _int(v.get("line"))
            if p and p.startswith("/") and n:
                self._add_line(p, n, json.dumps(v, ensure_ascii=False), v.get("text") if isinstance(v.get("text"), str) else None)
            for x in v.values():
                if isinstance(x, (dict, list)):
                    self._walk(x)
        elif isinstance(v, list):
            for x in v:
                self._walk(x)
        elif isinstance(v, str):
            m = _HIT.match(v)
            if m:
                self._add_line(m.group(1), int(m.group(2)), m.group(3) or "", m.group(3))

    def _add_line(self, path: str, n: int, text: str, raw: str | None) -> None:
        """One line of a text file, with the locator the Task API wants for its type: csv tables -> `record` (the id
        in the first column), .json -> the file alone, everything else (markdown, text, jsonl, log archives) -> `line`.
        `raw` is the line itself when the tool gave it (a log event from query_logs has none)."""
        path = norm_path(path)
        low = path.lower()
        if low.endswith(".json"):
            return self._add(path, text, _line=n)
        if low.endswith(".csv") and raw is not None:
            first = raw.split(",", 1)[0].strip().strip('"')
            # header unseen: a first column that looks like a date/time is a log row, cited by line
            if first and self.csv_ids.get(path, not _DATE_LIKE.match(first)):
                return self._add(path, text, record=first, _line=n)
        self._add(path, text, line=n)

    def record_at(self, path: str, line: int) -> str | None:
        """The record id of a csv line the agent has seen."""
        for it in self.items.values():
            s = it["source"]
            if s["path"] == path and s.get("_line") == line and s.get("record"):
                return s["record"]
        return None

    def add_extraction(self, path: str, text: str) -> None:
        """Output of the harness's own download_file parser (formats defined in agent.py)."""
        path = norm_path(path)
        self.paths.add(path)
        low = path.lower()
        if low.endswith(".pdf"):
            for m in re.finditer(r"^--- page (\d+) ---\n(.*?)(?=^--- page \d+ ---$|\Z)", text, re.S | re.M):
                self._add(path, m.group(2), page=int(m.group(1)))
        elif low.endswith((".docx", ".odt")):
            for line in text.splitlines():
                m = re.match(r"^(\d+)\. (.*)$", line)
                if m:
                    self._add(path, m.group(2), paragraph=int(m.group(1)))
        elif low.endswith((".xlsx", ".ods")):
            sheet = None
            for line in text.splitlines():
                m = re.match(r"^=== sheet '(.*?)'", line) or re.match(r'^=== sheet "(.*?)"', line)
                if m:
                    sheet = m.group(1)
                    continue
                m = re.match(r"^r(\d+)(?: \[hidden\])?: (.*)$", line)
                if m and sheet is not None:
                    self._add(path, m.group(2), sheet=sheet, row=int(m.group(1)))

    def add_image(self, path: str, text: str) -> None:
        self._add(path, text)

    # --- at submit time -----------------------------------------------------------------------------------------
    def candidates(self, answer: Any, cited: list[dict], max_add: int = 4) -> list[dict]:
        """Sources to add to the model's own: places where an answer value occurs, unambiguous per file, not cited
        yet. At most `max_add`."""
        added: list[dict] = []
        for value in answer_values(answer):
            by_path: dict[str, list[dict]] = {}
            for it in self.items.values():
                if _contains(it["text"], value):
                    by_path.setdefault(it["source"]["path"], []).append(it["source"])
            for path, srcs in by_path.items():
                exact = [s for s in srcs if str(s.get("record", "")).casefold() == value.casefold()]
                srcs = _merge_near(exact or srcs)
                if len(srcs) > MAX_PER_FILE:
                    continue
                for s in srcs:
                    s = {k: v for k, v in s.items() if not k.startswith("_")}
                    if not any(_same(s, c) for c in cited + added):
                        added.append(s)
                        if len(added) >= max_add:
                            return added
        return added


def _int(v: Any) -> int | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v)
    return None


def _numbered_lines(result: Any, start: int) -> list[tuple[int, str]]:
    """(line number, text) of a `read` result, whatever its shape: a string (with or without "12: " prefixes), a
    list of lines, or an object holding one of those."""
    if isinstance(result, dict):
        start = _int(result.get("start_line")) or start
        for k in ("content", "text", "lines", "data", "result"):
            if k in result:
                return _numbered_lines(result[k], start)
        return []
    if isinstance(result, list):
        out = []
        for i, x in enumerate(result):
            if isinstance(x, dict):
                t = x.get("text") if isinstance(x.get("text"), str) else x.get("content") if isinstance(x.get("content"), str) else json.dumps(x, ensure_ascii=False)
                out.append((_int(x.get("line")) or _int(x.get("n")) or start + i, t))
            else:
                out.append((start + i, str(x)))
        return out
    if not isinstance(result, str):
        return []
    raw = result.split("\n")
    parsed = [_NUMBERED.match(l) for l in raw]
    nonempty = [m for l, m in zip(raw, parsed) if l.strip()]
    nums = [int(m.group(1)) for m in nonempty if m]
    if nonempty and len(nums) >= 0.8 * len(nonempty) and nums == sorted(nums) and len(set(nums)) == len(nums):
        return [(int(m.group(1)), m.group(2)) for m in parsed if m]
    return [(start + i, l) for i, l in enumerate(raw)]


def _merge_near(srcs: list[dict]) -> list[dict]:
    """Drop duplicates and text lines within the grader's tolerance of an earlier one (one citation covers them)."""
    out: list[dict] = []
    for s in sorted(srcs, key=lambda s: (s.get("line") or s.get("_line") or 0)):
        if not any(_same(s, o) for o in out):
            out.append(s)
    return out


def _same(a: dict, b: dict) -> bool:
    """Would citation b already cover a? Same file and same locator (lines within tolerance). A citation of the
    file without any locator does not cover a located one."""
    if norm_path(a.get("path")) != norm_path(b.get("path")):
        return False
    ka = {k: a[k] for k in LOCATOR_KEYS if a.get(k) is not None}
    kb = {k: b[k] for k in LOCATOR_KEYS if b.get(k) is not None}
    if not ka:
        return True  # nothing more specific to add than the path, which is cited
    if set(ka) != set(kb):
        return False
    for k in ka:
        if k == "line":
            if abs(int(ka[k]) - int(kb[k])) > LINE_TOLERANCE:
                return False
        elif str(ka[k]).casefold() != str(kb[k]).casefold():
            return False
    return True


def finalize(model_sources: list[dict], answer: Any, evidence: Evidence, existing: set[str] | None,
             max_add: int = 4) -> tuple[list[dict], dict]:
    """The sources to submit: the model's own (paths normalised, files that do not exist in the workspace dropped)
    plus the ledger's candidates. Returns (sources, report for the trace)."""
    kept, dropped = [], []
    for s in model_sources:
        s = {**s, "path": norm_path(s["path"])}
        low = s["path"].lower()
        if low.endswith(".json"):  # cited as a whole file
            s = {"path": s["path"]}
        elif low.endswith(".csv") and "record" not in s and "line" in s:
            rec = evidence.record_at(s["path"], s["line"])  # the model cites tables by line; the grader wants the id
            if rec:
                s = {"path": s["path"], "record": rec}
        # /AGENTS.md is the rule book of every workspace, not evidence; citing it only counts as a stray citation
        if (existing is not None and s["path"] not in existing) or s["path"] == "/AGENTS.md":
            dropped.append(s)
        elif s not in kept:
            kept.append(s)
    added = [s for s in evidence.candidates(answer, kept, max_add)
             if existing is None or s["path"] in existing]
    return kept + added, {"model": model_sources, "added": added, "dropped": dropped}
