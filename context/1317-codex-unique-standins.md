# Stand-ins pro Quarantäne eindeutig

**Wer:** Codex · **Zeit:** Sa 14.11., 13:17 · **Typ:** Sicherheitsfix

Im Replay von t21 wurde `standby-01` gleichzeitig mehreren kritischen Agents als Vertretung zugewiesen. `guard.py`
blockiert jetzt den gesamten atomaren Containment-Aufruf, sobald ein Stand-in innerhalb des Aufrufs oder über mehrere
bereits ausgeführte Containment-Aufrufe desselben Tasks erneut verwendet wird.

Der Test bildet zwei kompromittierte kritische Agents mit demselben zulässigen Stand-in nach. Die doppelte Zuweisung
erreicht die Task API nicht; die bestehende legitime Einzelzuweisung bleibt erlaubt. Die separate `frame_agent`-Lücke
(harmlose Gegenmaßnahmen zählen bisher als Aktivität in einem untersuchten Trace) ist damit ausdrücklich nicht gelöst.
