# Kosten-Runs 16:07–16:45 und Stand der finalen Abgabe

**Wer:** Fable (Claude Code) · **Zeit:** Sa 14.11., 16:45 · **Typ:** Messwerte / Status / Übergabe

**Vorbereitete Abgabe:** `prep_dN8-a9-wadtF` = main `3e3af0e`. Ein Mensch bestätigt im Dashboard („Prepared by your agent“ → final submission).

| Run | Code | Seed | Accuracy | Kosten | C | final |
|---|---|---|---|---|---|---|
| run_07oOLC4jn7Vg | 2a6d810 (Baseline) | 675237767 | 0.938 | $0.328 | 0.368 | 0.642 |
| run_QfHOqhRM75Om | c75847b Direkt-Abgabe | 675237767 | 0.964 | $0.307 | 0.377 | 0.663 |
| run_7YkAuXC_t0cU | 8bd08a9 + Vertrags-Tickets, Plattform-Werkzeuge nach Thema | 675237767 | 0.948 | $0.258 | 0.401 | 0.664 |
| run_GCpXQhcr35u4 | 8ddb4d2 + Faktenblatt vorab | 675237767 | 0.966 | $0.270 | 0.395 | 0.674 |
| run_31AOC3VsQHDx | a106722 + kleine Tabellen, Board direkt, Regeln ohne Zeilennummern | 675237767 | 0.963 | $0.274 | 0.392 | 0.670 |
| run_jh_DV7e7d4K6 | e004800 (= a106722), zweiter Schlüssel | 112309987 (frisch) | 0.832 | $0.459 | 0.323 | 0.550 |
| run_PmKXXmW6n-9X | d3094cf + Faktenblatt-Auslöser korrigiert | 112309987 | 0.877 | $0.362 | 0.355 | 0.594 |

- Kosten-Rauschen zwischen zwei Runs desselben Codes und Seeds: etwa ±$0.015. Sicher belegt: Direkt-Abgabe (alle betroffenen
  Tasks 1.00 bei ~$0.0001–0.0007), Faktenblatt vorab (18 Tasks: 42 statt 58 Calls), kleine Tabellen (Aktions-Tasks 30 statt 45 Calls).
- Seed 112309987 ist deutlich schwerer und teurer; es gibt dort keinen Baseline-Run von 2a6d810. Der Kosten-Wert von
  run_jh_DV7e7d4K6 ist nicht belastbar (zweiter Schlüssel, evtl. parallel anderweitig genutzt).
- Auf dem frischen Seed gefunden und in `3e3af0e` behoben (JOURNAL 16:44): Faktenblatt bei jedem Ticket, unvollständig übersetzte
  Policy direkt abgegeben, Provider-Timeout → sofort UNSUPPORTED, Agent-ID-Filter leerte berechnete Trifecta-Liste.
  Die letzten drei Korrekturen haben nur Offline-/Unit-Prüfung, ein Kontroll-Run lief beim Schreiben.
- Offen: Rotation im Freeze (`rotation_in_freeze`, 0), Inbox-Outcome falsch (t35), Vertragsfrist mit Bild-Amendments schwankt
  (Vision), Partner-Zusammenfassung 0.45.
