"""LLM-Client (OpenAI-kompatibel) mit Kosten-Tracking, Cache und Mock-Modus.

Fast jeder Hackathon-Endpunkt (vLLM, Ollama, watsonx-Proxy, LiteLLM) spricht das
OpenAI-Chat-Format. Falls nicht: nur `_raw_call` anpassen.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass, field


@dataclass
class Budget:
    price_in_per_m: float = float(os.getenv("PRICE_IN_PER_M", "0.1"))
    price_out_per_m: float = float(os.getenv("PRICE_OUT_PER_M", "0.4"))
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 0
    jev_calls: int = 0
    log: list = field(default_factory=list)

    def add(self, tin: int, tout: int, tag: str):
        self.tokens_in += tin
        self.tokens_out += tout
        self.calls += 1
        self.log.append((tag, tin, tout))

    @property
    def cost(self) -> float:
        return self.tokens_in / 1e6 * self.price_in_per_m + self.tokens_out / 1e6 * self.price_out_per_m

    def summary(self) -> str:
        return (f"LLM-Calls={self.calls} Jev-Calls={self.jev_calls} "
                f"in={self.tokens_in} out={self.tokens_out} ~${self.cost:.5f}")


class LLM:
    def __init__(self, budget: Budget | None = None):
        self.budget = budget or Budget()
        self.mock = os.getenv("MOCK", "0") == "1"
        self.model = os.getenv("LLM_MODEL", "mock")
        self._cache: dict[str, str] = {}
        if not self.mock:
            from openai import OpenAI
            self.client = OpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key=os.getenv("LLM_API_KEY", "x"))

    def chat(self, system: str, user: str, *, max_tokens: int = 256, tag: str = "chat",
             temperature: float = 0.0, stop: list[str] | None = None) -> str:
        key = hashlib.sha1(json.dumps([system, user, max_tokens, stop]).encode()).hexdigest()
        if key in self._cache:  # gleiche Frage nie zweimal bezahlen
            return self._cache[key]
        out = self._raw_call(system, user, max_tokens, temperature, stop, tag)
        self._cache[key] = out
        return out

    def _raw_call(self, system, user, max_tokens, temperature, stop, tag) -> str:
        if self.mock:
            out = _mock_answer(user)
            self.budget.add(len(system + user) // 4, len(out) // 4, tag)
            return out
        for attempt in range(3):
            try:
                r = self.client.chat.completions.create(
                    model=self.model, max_tokens=max_tokens, temperature=temperature, stop=stop,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
                u = r.usage
                self.budget.add(u.prompt_tokens if u else 0, u.completion_tokens if u else 0, tag)
                return r.choices[0].message.content or ""
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    raise
                time.sleep(1.5 * (attempt + 1))
                print(f"[llm] retry after {e!r}")
        return ""

    def json(self, system: str, user: str, **kw) -> dict:
        """Kleine Modelle liefern oft kaputtes JSON -> robust extrahieren."""
        txt = self.chat(system + "\nAntworte NUR mit gültigem JSON.", user, **kw)
        m = re.search(r"\{.*\}", txt, re.S)
        try:
            return json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            return {}


def _mock_answer(user: str) -> str:
    """Primitives Fake-Modell: nimmt den ersten Kontextsatz, der Wörter der Frage enthält."""
    q = user.split("FRAGE:")[-1].lower()
    words = {w for w in re.findall(r"\w{4,}", q)}
    ctx = user.split("FRAGE:")[0]
    for block in re.findall(r"\[(.+?)\]\n(.+?)(?=\n\[|\Z)", ctx, re.S):
        src, text = block
        for sent in re.split(r"(?<=[.!?])\s", text):
            if len(words & set(re.findall(r"\w{4,}", sent.lower()))) >= 2:
                return json.dumps({"answer": sent.strip(), "sources": [src]})
    return json.dumps({"answer": "UNKNOWN", "sources": []})
