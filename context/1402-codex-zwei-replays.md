# Zwei gezielte Replays: Access Review und Agentenliste
**Wer:** Daniel (+ Codex) · **Zeit:** Sa 14:02 · **Typ:** Messwert + offene Fehler

Es wurden wie vereinbart genau zwei Dev-Tasks ausgeführt, beide auf sauberem Commit `3518bc9` und mit `google/gemma-4-31b-it`. Keine weiteren Tasks wurden gestartet.

## Access Review – run_0iZJI8P2jdv0 / t08

- Score **0.705**, Answer 0.8, Constraints ✓, Sources 5/6, 8 Tool-Calls.
- Bekannter Ausgangsfall run_tkSRAC-SpUlz/t08: 0.417 und 15 Tool-Calls.
- Wichtig: Das neue `review_access`-Tool lieferte einen Fehler, weil der Roster die Owner-Spalte diesmal `responsible` statt `owner_person` nannte. Das Modell fiel auf die vorhandenen Einzelwerkzeuge zurück und löste manuell.
- Konkreter Restfehler: AR-3785 wurde approved statt denied; außerdem fehlte die Registry-Quelle.
- Kleinster nächster Fix: `responsible` als Owner-Spaltenalias akzeptieren und denselben Einzel-Task erneut ausführen. Die Score-Steigerung beweist noch nicht die Wirksamkeit von `review_access`.

## Agentenliste – run_1E_xnLolRal0 / t25

- Score **0.855**, Answer 0.909, Constraints ✓, Sources 4/5, 3 Tool-Calls.
- Erwartet waren 10 Agents; die Antwort enthielt zusätzlich `tooling-17`.
- Die Aufgabe fragte nach aktuellen lethal-trifecta-Rechten, nicht nach kompromittierten Agents. Der Router setzte deshalb `agent_evidence=false`; der neue Submit-Filter wurde nicht ausgeführt. `capabilities` gab `tooling-17` bereits aus, weil der aktuelle Zustand nicht vollständig aus den Changes übernommen wurde.
- Dieser Replay bestätigt den eigentlichen `detail`-Injection-Filter nicht. Er zeigt stattdessen, dass die Current-Permissions-Agentenliste weiterhin einen falschen Extra-Agent zulässt. Die frühere Aussage „frame_agent ist erledigt“ ist für diesen Pfad zu stark.

## Kosten

Lokale Modellkosten laut Traces: t08 `$0.0233`, t25 `$0.0103`. Plattform-Finish meldete für die beiden Einzelruns `$0.0731` beziehungsweise `$0.0085`; diese Werte sind wegen der Plattform-Abrechnung getrennt zu betrachten.
