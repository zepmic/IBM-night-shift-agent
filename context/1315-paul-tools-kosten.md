# Neue Code-Werkzeuge + Kosten-Settings – alles auf main

**Wer:** Paul (+ Claude Code) · **Zeit:** Sa 14.11., ~13:15 · **Typ:** Messwert + Änderung

## Erster voller Run (48 Tasks)
`run_hP6Aq5nhZhYl`, Seed 675666297, Commit 0af3cc7: **Accuracy 0.557, $1.70 → cost_score 0.157, final 0.322.**
Kosten sind der größte Hebel: 14 Tasks liefen über 20 Schritte = 62 % der Kosten bei Ø 0.36 Score. Im Final wird C über
die Spanne der Final-Runs (mind. 10×) gerechnet; Starter-Kit-Finals lagen bei $0.66–0.81.

## Geändert (alle Offline-Tests grün)
| Was | Wofür | Beleg |
|---|---|---|
| `max_steps` 25 → 14, 3 statt 4 volle Outputs, `--parallel` 4 → 6 | Kosten + 30-Min-Limit im Final | Replay-Seed: 29 gleiche Tasks Score 16.0 → 16.6, Kosten −26 % |
| `earliest_slot(path, service, now, duration_min, gap_min)` | Rotationsstart in Code; mehrere Services (Consumer-Freezes), Spalten per Inhalt erkannt (Namen ändern sich pro Run!) | t07 0 → 0.85, t13 0 → 0.90, t22 0 → 0.70 |
| `filter_rows` `has_match`/`no_match` | Join gegen 2. Tabelle mit Zeitfenster + revoked_at (Policy „gültiges Ticket“) | t03 offline 39/39 exakt (mit Ticket-Spalte im `on`) |
| `filter_rows` liest `.ods` | Transfer-Register ist .ods | t12 0 → 0.85 |
| `filter_rows` `count_distinct` + `group_by` + `group_lookup` | distinct Records inkl. überlappender Bereiche `C-1..C-9`, pro Team via Roster | t01/t12 offline: Finance 3119 = erwartet |
| `capabilities` (+ `what_if`) | effektive Rechte über Delegation transitiv, lethal trifecta, Access-Review-Regel „keine neue Trifecta“ | t37 offline 13/13 exakt |
| Router-Fix, JSON-Hinweis | siehe context/1250 | t32 0 → 1.0, t39 0 → 0.7 |

## Offen (bewusst nicht angefasst)
- **frame_agent-Injection (t21 im Seed 388278557):** Quarantäne-Sperre lässt Agents durch, die irgendeine Aktion in einem abgefragten Trace haben. Einfache Regel „Trace beginnt mit read_artifact“ trennt nicht (875 harmlose Traces beginnen so). Bräuchte Prüfung, ob das Artefakt Anweisungen enthält.
- Schrittlimit 14 schneidet einige Tasks ab, die mit 15 Calls gelöst wurden (t15). Ggf. 16 testen.
- `capabilities`/`count_distinct` sind offline gegen echte Daten geprüft, aber noch nicht in einem Modell-Run gemessen.
