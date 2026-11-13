"""Retrieval ohne Embeddings: BM25 (schnell, gratis, keine Tokens).

Kostet 0 Tokens -> der billigste Weg, dem Modell nur die relevanten Stellen zu geben.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

_tok = lambda s: re.findall(r"\w+", s.lower())  # noqa: E731


class Index:
    def __init__(self, chunks: list[tuple[str, str]]):  # (source_id, text)
        self.chunks = chunks
        self.docs = [_tok(t) for _, t in chunks]
        self.avg = sum(map(len, self.docs)) / max(len(self.docs), 1)
        df = Counter(w for d in self.docs for w in set(d))
        n = len(self.docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    @classmethod
    def from_dir(cls, path: str | Path, chunk_chars: int = 600) -> "Index":
        chunks = []
        for f in sorted(Path(path).rglob("*")):
            if f.is_file() and f.suffix in {".md", ".txt", ".json", ".csv", ".html"}:
                text = f.read_text(errors="ignore")
                for i in range(0, len(text), chunk_chars):
                    chunks.append((f.name, text[i:i + chunk_chars]))
        return cls(chunks)

    def search(self, query: str, k: int = 3, k1: float = 1.5, b: float = 0.75):
        q = _tok(query)
        scored = []
        for (src, text), d in zip(self.chunks, self.docs):
            tf = Counter(d)
            s = sum(self.idf.get(w, 0) * tf[w] * (k1 + 1) /
                    (tf[w] + k1 * (1 - b + b * len(d) / self.avg)) for w in q if w in tf)
            if s > 0:
                scored.append((s, src, text))
        scored.sort(reverse=True)
        return scored[:k]
