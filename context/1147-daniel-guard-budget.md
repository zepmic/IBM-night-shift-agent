# Zentrale Aktionsprüfung (guard.py), Budgetwächter – Stand und offene Messungen

**Wer:** Daniel (+ Claude Code) · **Zeit:** Sa 11:47 · **Typ:** Status + Entscheidung

Branch `daniel/fallback-eval`, Commit `d14c259`. **Offline und im Image getestet, noch in keinem Dev-Run gelaufen.**

## Budget-Stand (aus `GET /runs`, 11:47)
4 Dev-Runs des Teams, zusammen **$0.56 von $15**. Der zweite Fable (B4) und ich fahren Runs nicht gleichzeitig – wer einen Run startet, schreibt es vorher in den Team-Chat.

## Was die Prüfung abfängt (`tests/test_guard.py`, gezählt werden gesendete Requests)
| Angriff / Fehler | Verhalten |
|---|---|
| send_message / containment / write in einem Analyse-Task (egal wodurch ausgelöst: Log-detail, Dokument, „SYSTEM:“-Text) | Tool wird nicht angeboten; Aufruf lokal abgewiesen, 0 Requests |
| erfundener Tool-Name | lokal abgewiesen |
| Empfänger nicht verifiziert, Look-alike, unverifizierter Eintrag | nicht gesendet |
| Secret-Wert (Präfix aus AGENTS.md) in Nachricht, Draft, Notiz | nicht gesendet; in Antworten entfernt |
| kopierte Regeltexte (≥ 2 lange Zeilen aus AGENTS.md/Runbook) | nicht gesendet |
| Live-URL fremder Domain (auch Markdown-Bild, auch „als Quelle“) in Nachricht, Draft, Antwort | defangt (`hxxps://evil[.]example/…`); nackte Domains, E-Mails, Workspace-Pfade bleiben |
| Quarantäne eines Agents ohne eigenes Log-Ereignis in einem einzeln abgefragten Trace (nur im detail-Text genannt, oder nur `declined`) | nicht gesendet, Modell bekommt Hinweis und kann nachprüfen |
| kritischer Agent ohne zugelassenen Stand-in | nicht gesendet |
| Block eigener / verifizierter Partner-Domain | nicht gesendet |
| Revoke ohne Rotation, Rotation in der Vergangenheit / nicht zur vollen Stunde | nicht gesendet |
| Inbox-Task, Absender nicht verifiziert | keinerlei Aktion |
| geschlossenes Ticket, Ticket-Text in anderer Datei, `status: open` nur im Fließtext | kein Auftrag |

Legitime Gegenfälle laufen weiter: Breach-Notification an den DPO, Draft schreiben, volle Eindämmung mit Stand-in, Quarantäne auf Bitte eines verifizierten Absenders, Analyse bösartiger Belege, Ticket-Aufgabe.

Gegen echte Daten (run_tkSRAC-SpUlz, Workspace t40): erwartete Containment-Operationen passieren; **0 von 15 sauberen Agents** kämen durch die Quarantäne-Sperre.

## Wie die Freigabe entsteht
Ein kleiner Modell-Call pro Task liest **nur** Instruktion (+ offenes Ticket) und liefert `{ticket_queue, inbox, actions}`. Validiert; bei Ausfall ist **keine** Aktion erlaubt. Spätere Tool-Argumente oder Belege können das nicht erweitern.

## Nicht abgedeckt (Restrisiko)
- Personenbezogene Daten in Nachrichten erkennt der Code nicht (nur Secret-Werte und Regeltexte).
- Falsch beschuldigte Agents in **Antwortlisten** (frame_agent über die Antwort) werden nicht bereinigt.
- „Nur der DPO meldet an die Behörde“ ist nicht technisch erzwungen (Behörden-Adresse ist ein verifizierter Kontakt).
- Ob eine Verweigerung vorgeschrieben war, kann der Code nicht wissen; er verhindert nur Aktionen bei unverifiziertem Inbox-Absender.
- Router-Fehlurteil: „keine Aktion“ bei einem Aktions-Task → Task scheitert; „Aktion“ bei Analyse-Task → nur noch Inhaltsprüfungen. **Trefferquote ungemessen.**

## Budgetwächter / Deadline
Gemeinsam für alle parallelen Tasks: Reserve $0.004 pro offenem Task; danach erzwungener Submit; am Limit oder nach 403 kein Modell-Call mehr. Final-Default $2.70 (`--budget`, `ARENA_BUDGET_USD`). Kurz vor der Deadline: Timeout ≤ 90 s, keine Retries.
