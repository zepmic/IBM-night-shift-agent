"""Deterministic full-value leak matching against SHA-256 fingerprint tables."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Callable, Iterable

VALUE_RX = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{7,}")


def _fingerprints(read: Callable[[str], bytes], paths: Iterable[str]) -> dict[str, str]:
    """sha256_12 -> token id, with both columns identified from their values."""
    for path in sorted(paths):
        if not path.lower().endswith(".csv"):
            continue
        rows = list(csv.reader(io.StringIO(read(path).decode("utf-8-sig", "replace"))))
        if len(rows) < 2:
            continue
        body = rows[1:]
        width = max(map(len, body), default=0)
        sha_col = next((i for i in range(width) if body and all(
            i < len(row) and re.fullmatch(r"[0-9a-fA-F]{12}", row[i].strip()) for row in body)), None)
        id_col = next((i for i in range(width) if i != sha_col and body and all(
            i < len(row) and re.fullmatch(r"[A-Z][A-Z0-9-]*-\d+", row[i].strip()) for row in body)), None)
        if sha_col is not None and id_col is not None:
            return {row[sha_col].strip().lower(): row[id_col].strip() for row in body}
    return {}


def _values(text: str) -> list[tuple[str, int, int]]:
    """Candidate full values and their 1-based line range, including indented continuations."""
    lines = text.splitlines()
    out = [(m.group(), n, n) for n, line in enumerate(lines, 1) for m in VALUE_RX.finditer(line)]
    for n in range(len(lines) - 1):
        left = re.search(r":\s*([A-Za-z0-9_.-]{4,})\s*$", lines[n])
        right = re.fullmatch(r"\s+([A-Za-z0-9_.-]{4,})\s*", lines[n + 1])
        if left and right:
            out.append((left.group(1) + right.group(1), n + 1, n + 2))
    return out


def find_leaked_tokens(read: Callable[[str], bytes], paths: set[str],
                       material_paths: Iterable[str] | None = None) -> list[dict]:
    """Return matched token ids with source path and line(s), sorted by token id.

    When ``material_paths`` is omitted, paste/dump files and board JSON/JSONL files are scanned.
    Only candidates whose complete value hashes to a table fingerprint can match; display-only
    first/last fragments and ellipsis-truncated values therefore never count.
    """
    fingerprints = _fingerprints(read, paths)
    selected = list(material_paths) if material_paths is not None else [
        p for p in sorted(paths) if re.search(r"paste|dump", p, re.I)
        or ("board" in p.lower() and p.lower().endswith((".json", ".jsonl", ".ndjson")))
    ]
    hits: dict[str, dict] = {}
    for path in selected:
        if path not in paths:
            continue
        text = read(path).decode("utf-8-sig", "replace")
        candidates = _values(text)
        if path.lower().endswith((".json", ".jsonl", ".ndjson")):
            candidates = []
            for n, line in enumerate(text.splitlines(), 1):
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    value = line
                strings = value.values() if isinstance(value, dict) else [value]
                candidates += [(m.group(), n, n) for s in strings if isinstance(s, str) for m in VALUE_RX.finditer(s)]
        for value, line, end_line in candidates:
            token = fingerprints.get(hashlib.sha256(value.encode()).hexdigest()[:12])
            if token and token not in hits:
                hits[token] = {"token": token, "path": path, "line": line, **({"end_line": end_line} if end_line != line else {})}
    return [hits[token] for token in sorted(hits)]
