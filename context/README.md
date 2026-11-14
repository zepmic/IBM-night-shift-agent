# Team-Kontext

Gemeinsames Gedächtnis aller Teammitglieder **und ihrer Coding-Agents**.
Alles, was ein anderer Agent wissen müsste, um nicht doppelt zu arbeiten oder Fehler zu wiederholen, gehört hierher.

## Aktuelle Übergabe

- [15:13 – Aktuelle Dev-Score-Einordnung](1513-codex-score-einordnung.md): Bei `$0.003–$5.000` liegt `run_iOrNuR6b10uJ` rechnerisch bei `C = 0.325`, `final = 0.511`; Feldplatz braucht Fremdwerte/Rangliste.
- [14:27 – Final-Run hat 24 Tasks](1427-daniel-final-24-tasks.md): menschliche Klarstellung; Dev-Vollruns haben 48, Kosten- und Accuracy-Hochrechnungen für das Final müssen 24 verwenden.
- [14:03 – Injection-Abwehr: 3 offene Lücken](1403-michel-injection-luecken.md): Prüfliste gegen alle 5 Angriffsziele; wichtigste Lücke: frame_agent-Filter hängt am Router (in 1402 bestätigt).
- [14:02 – Zwei gezielte Replays](1402-codex-zwei-replays.md): Access Review 0.705, aber Tool scheitert an `responsible`; Agentenliste 0.855, doch `tooling-17` bleibt fälschlich enthalten und der neue Filter wurde nicht ausgelöst.
- [13:44 – Injection-Abwehr und Access Review für Fable](1344-codex-injection-access-review.md): strukturierte Trace-Evidenz gegen `frame_agent`, lokales Gesamt-Tool für offene Access Requests, Nutzung und bewusste Grenze.
- [12:20 – Gestufte Evaluation und Merge auf main](1220-daniel-codex-stufen-eval.md): 27 Tasks gemessen, rund $0.67 verbraucht; zwei bestätigte Routerfehler blockieren legitime Aktionen. Kein Final-Kandidat, zweite Hälfte nicht gestartet. Restbudget und nächste Schritte stehen im Bericht.

## Was hier rein gehört

- **Erkenntnisse:** wie sich das Modell / die API / ein Tool verhält, was funktioniert, was nicht
- **Entscheidungen:** was wir festgelegt haben und warum
- **Messwerte:** Score + Kosten nach einer Änderung
- **Setup-Wissen:** Befehle, Pfade, Stolperfallen
- **Wer macht gerade was**, damit niemand doppelt arbeitet

Offizielle Infos der Veranstalter gehören **nicht** hierher, sondern nach [`../challenge/`](../challenge/README.md).
Strategie-Regeln, die dauerhaft gelten, gehören in [`../PLAYBOOK.md`](../PLAYBOOK.md).

## Format

Eine Datei pro Eintrag, damit es keine Merge-Konflikte gibt:

```
context/HHMM-name-thema.md      z. B. context/1130-michel-json-retries.md
```

Inhalt, kurz halten:

```markdown
# Thema
**Wer:** Name (+ Agent) · **Zeit:** Sa 11:30 · **Typ:** Erkenntnis | Entscheidung | Messwert | Setup | Status

Was ist so? Warum ist es wichtig? Was folgt daraus für die anderen?
```

Wird ein Eintrag falsch oder veraltet: **neuen Eintrag schreiben** und im alten oben `> VERALTET, siehe <datei>` ergänzen. Nicht still löschen.

## Ablage + Push (sofort, ohne Branch)

Kontext-Dateien gehen **direkt auf `main`**, damit alle sie sofort haben:

```bash
git add context/ challenge/
git commit -m "context: <thema>"
git pull --rebase
git push
```

Nur Dokumentation direkt auf `main`. Code weiterhin über Branches.

## Informationslücke?

Bevor du rätst oder nachfragst:

1. `git pull --rebase`
2. `challenge/`, `context/`, `PLAYBOOK.md` durchsuchen (`grep -ri <stichwort> challenge context PLAYBOOK.md`)
3. Steht es nicht drin: im Team fragen, **Antwort sofort hier ablegen und pushen**.
