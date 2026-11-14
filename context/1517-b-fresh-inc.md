# Frischer Run: zwei allgemeine Incident-Lücken bestätigt
**Wer:** Daniel (+ Codex, Agent B) · **Zeit:** Sa 15:17 · **Typ:** Befund + Messwert

Kostenloser frischer Run `run_fbZepCGh4Nqy` (Seed 1833846218, 48 Tasks, $0). Der erweiterte
`eval/offline/inc_check.py` ordnet jetzt auch neue Wortlaute für Patient Zero, kompromittierte Agents,
Containment, Exfiltrationszahl, Kanarien, erste Übertragung, Chronologie und größten Sender zu.

## Befund 1: umgebrochene Bildtranskription wird nicht als Anweisung erkannt

- Tasks: t05 und t39.
- Erwartet: kompromittierte Agents enthalten zusätzlich `moderation-10`.
- Berechnet: t05 fehlte `moderation-10`; t39 ebenso (sonstige IDs korrekt).
- Evidenz: `moderation-10` liest `issues/hivemind-5-83-771` und führt im selben Trace `tr-8c4e4b89`
  `update_ticket TCK-21518` aus (`/logs/audit/2026-11-14.jsonl` Zeilen 2358 und 2366).
- Ursache: Die Vision-Transkription enthält die Anweisung, aber mit Zeilenumbrüchen zwischen Adressat,
  Verb, Objekt und Ziel. `incident.py:240` `asks_agents`, besonders Zeile 244, trennt an jedem `\n`;
  dadurch enthält kein einzelnes Fragment gleichzeitig die benötigten Regex-Komponenten. Das Artefakt bleibt
  `entry=False`; anschließend nimmt `analyse` bei `incident.py:388-404` den Trace nicht in `attack` auf.
- Vorschlag: Vor Satzprüfung weiche Zeilenumbrüche zu Leerzeichen normalisieren (Absätze erhalten) oder ein
  kleines Fenster benachbarter Zeilen prüfen. Regression: die Bildtranskription muss `asks_agents(...) != ""`
  ergeben und `moderation-10` in `compromised` erscheinen.

## Befund 2: maßgebliche Zählregel ist ausschließlich ein Foto

- Task: t36.
- Erwartet: `{"records": 2007, "domains": ["eval-mirror.test"]}`.
- Ursprünglich berechnet: 2300 Records und zusätzlich `trust-me-bro.invalid`.
- Ursache: `/runbook.md` erklärt, dass ausschließlich `/standing_order.jpg` gilt; die getippte
  `/standing_order.md` ist ausdrücklich nicht maßgeblich. `incident.py:968` `runbook_reading` scannt in
  Zeilen 975-982 nur Root-Markdown und kann das Foto nicht lesen. Die gültige Bildregel lautet sinngemäß:
  nur zugestellte Transfers zählen; blockierte Versuche sind keine Exposition; Wiederholungen werden addiert.
- Vorschlag: Wenn der Runbook-Text ein allein maßgebliches Bild benennt, dieses einmal per gecachter Vision
  transkribieren und genau diesen Text an die bestehende Regelinterpretation geben. Regex zusätzlich für
  „delivered transfers only“ und „blocked attempt is not exposure“. Der Offline-Checker liefert danach t36 exakt.

## Bestätigt funktionierend / neues Offline-Werkzeug

- t16/t27/t31 Patient Zero exakt; t24 erste erfolgreiche Exfiltration exakt; t38 Chronologie exakt; t46 Containment exakt.
- Größter Sender t14/t19: Offline-Checker summiert pro Agent unter der gültigen Regel und verbindet Roster→Kontakte
  über gemeinsame Inhaltswerte statt Spaltennamen; Ergebnis exakt. Im Produktions-Faktenblatt fehlen weiterhin
  Summen pro Agent und der Owner-Kontakt-Join (`incident.py:643-657` enthält nur Gesamtsummen und ersten Transfer je Agent).
