"""Jev = "System One"-Modell: billige, typisierte Entscheidungen mit Wahrscheinlichkeit.

Die echte API kennen wir erst am Samstag. Deshalb: EINE Funktion `decide()`,
die wir am Tag an die echte API anschließen. Bis dahin Fallback = kleines LLM
(oder Heuristik im Mock-Modus).

Typische Fragen, die man Jev stellt statt dem LLM:
  - "Ist die Antwort durch die Quellen gestützt?"   -> bool
  - "Welche Art Aufgabe ist das?"                     -> choice
  - "Retry oder weiter?"                              -> choice
  - "Wie relevant ist dieses Dokument?"               -> score 0..1
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from .llm import LLM


@dataclass
class Decision:
    value: object        # gewählte Option / bool / score
    prob: float          # Konfidenz 0..1 (Jev ist kalibriert -> als Schwellwert nutzbar!)


class Jev:
    def __init__(self, llm: LLM):
        self.llm = llm
        self.base_url = os.getenv("JEV_BASE_URL")
        self.mock = os.getenv("MOCK", "0") == "1"

    def decide(self, state: str, question: str, options: list[str]) -> Decision:
        self.llm.budget.jev_calls += 1
        if self.base_url and not self.mock:
            return self._call_real_jev(state, question, options)
        if self.mock:
            return self._mock(state, question, options)
        # Fallback: kleines LLM, auf eine Option gezwungen
        txt = self.llm.chat(
            "Wähle genau eine Option. Antworte nur mit der Option.",
            f"STATE:\n{state}\n\nFRAGE: {question}\nOPTIONEN: {', '.join(options)}",
            max_tokens=5, tag="jev-fallback")
        pick = next((o for o in options if o.lower() in txt.lower()), options[0])
        return Decision(pick, 0.6)

    def yes(self, state: str, question: str, threshold: float = 0.5) -> tuple[bool, float]:
        d = self.decide(state, question, ["yes", "no"])
        p_yes = d.prob if d.value == "yes" else 1 - d.prob
        return p_yes >= threshold, p_yes

    def _call_real_jev(self, state, question, options) -> Decision:
        # TODO am Hackathon: an echte Jev-API anpassen (Doku kommt bei der Eröffnung).
        import httpx
        r = httpx.post(f"{self.base_url}/decide", timeout=10,
                       headers={"Authorization": f"Bearer {os.getenv('JEV_API_KEY', '')}"},
                       json={"model": os.getenv("JEV_MODEL", "jev-1.14"), "state": state,
                             "questions": [{"text": question, "type": "choice", "options": options}]})
        r.raise_for_status()
        a = r.json()["answers"][0]
        return Decision(a["value"], float(a.get("probability", 0.5)))

    @staticmethod
    def _mock(state, question, options) -> Decision:
        if options == ["yes", "no"]:
            ok = '"UNKNOWN"' not in state and '"sources": []' not in state
            return Decision("yes" if ok else "no", 0.9)
        return Decision(options[0], 0.7)


