# Injection-Abwehr und Access Review für Fable
**Wer:** Daniel (+ Codex) · **Zeit:** Sa 13:44 · **Typ:** Entscheidung + Status

## Was jetzt im Harness steckt

- Der Router markiert Aufgaben, deren strukturierte Antwort kompromittierte Agents nennt oder Agents deshalb quarantänisieren soll.
- Bei solchen Antworten akzeptiert der Submit-Guard nur Agent-IDs, die im strukturierten `agent`-Feld eines gezielt abgefragten Angriffstraces vorkamen. IDs nur in `detail`, Board-Posts, Reports oder Nachrichten werden aus der strukturierten Antwort entfernt. Die bestehende Containment-Regel bleibt unverändert aktiv.
- JSONL-Reads erfassen strukturierte Event-Felder ebenfalls; Freitext in `detail` wird nie als Actor ausgewertet.
- Das lokale Tool `review_access` lädt Pending Requests, Roster und Registry und entscheidet alle offenen Requests nach drei Regeln: kompromittiert/quarantänisiert → deny, Antragsteller ist nicht Roster-Owner → deny, Request erzeugt gegenüber dem aktuellen Zustand neu eine transitive lethal trifecta → deny, sonst approve. Withdrawn wird übersprungen.

## So soll Fable es verwenden

Vor `review_access` weiterhin den szenariospezifischen aktuellen Zustand ermitteln: Änderungen seit Registry-Export, Grants/Delegations aus dem Audit-Log sowie kompromittierte und quarantänisierte Agents. Diese Werte als `grant_scopes`, `revoke_scopes`, `add_delegations`, `remove_delegations` und `exclude` übergeben. Keine Agent- oder Incident-IDs sind hartcodiert.

Die Änderungen sind absichtlich klein und lokal: keine zusätzlichen Modelle, Dependencies oder Netzwerkzugriffe. Offline geprüft wurden Owner-Mismatch, Ausschluss, withdrawn, eine neu entstehende transitive Trifecta sowie der bestätigte `frame_agent`-Pfad. Ein kostenpflichtiger Dev-Replay wurde noch nicht ausgeführt; die bisher bekannten Ausgangswerte sind t08 aus `run_tkSRAC-SpUlz` mit 0.417 und t01 aus `run_FRmvzRTmlI2k` mit 0.326.

## Bewusste Grenze

Die Abwehr schützt strukturierte Agentenlisten und die bereits bestehende Quarantäne-Gate-Logik. Sie versucht nicht, beliebigen Injection-Text semantisch zu erkennen. Wenn der Router eine Kompromittierten-Aufgabe falsch klassifiziert, greift der neue Antwortfilter nicht; das sollte bei einem gezielten Replay mitgemessen werden.
