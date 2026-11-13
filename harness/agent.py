"""Der eigentliche Harness: retrieve -> answer -> verify (Jev) -> ggf. 1x retry.

Score = 50% Genauigkeit (Antwort + Quellen) + 50% Kosten.
Daher: so wenig LLM-Tokens wie möglich, Jev für alle Ja/Nein-Entscheidungen,
lieber "UNKNOWN" als halluzinieren.
"""
from __future__ import annotations

import json

from .jev import Jev
from .llm import LLM
from .retrieval import Index

SYSTEM = (
    "Du beantwortest Fragen NUR mit dem gegebenen Kontext. Kurz und exakt. "
    'Format: {"answer": "...", "sources": ["datei"]}. '
    'Wenn der Kontext die Antwort nicht enthält: {"answer": "UNKNOWN", "sources": []}.'
)


class Agent:
    def __init__(self, index: Index, llm: LLM | None = None, k: int = 3, max_retries: int = 1,
                 verify_threshold: float = 0.6):
        self.index = index
        self.llm = llm or LLM()
        self.jev = Jev(self.llm)
        self.k = k
        self.max_retries = max_retries
        self.verify_threshold = verify_threshold

    def _context(self, hits) -> str:
        return "\n".join(f"[{src}]\n{text.strip()}" for _, src, text in hits)

    def run(self, question: str) -> dict:
        k = self.k
        result = {"answer": "UNKNOWN", "sources": []}
        for attempt in range(self.max_retries + 1):
            hits = self.index.search(question, k=k)
            if not hits:
                break
            ctx = self._context(hits)
            result = self.llm.json(SYSTEM, f"KONTEXT:\n{ctx}\n\nFRAGE: {question}",
                                   max_tokens=120, tag=f"answer#{attempt}") or result
            result.setdefault("sources", [])
            if str(result.get("answer", "")).strip().upper() == "UNKNOWN":
                result["sources"] = []  # keine Quellen ohne Antwort
                break
            # Verifikation mit Jev (billig) statt zweitem LLM-Call
            ok, p = self.jev.yes(f"KONTEXT:\n{ctx}\nANTWORT: {json.dumps(result, ensure_ascii=False)}",
                                 "Is the answer fully supported by the context?", self.verify_threshold)
            result["confidence"] = round(p, 3)
            if ok or result.get("answer") == "UNKNOWN":
                break
            k *= 2  # retry: mehr Kontext holen
        return result
