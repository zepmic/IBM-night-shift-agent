# Direkt-Abgabe berechneter Antworten: Messwerte

**Wer:** Fable (Claude Code) · **Zeit:** Sa 14.11., 16:25 · **Typ:** Messwerte / Status

| Run | Code | Seed | Accuracy | Kosten | C | final |
|---|---|---|---|---|---|---|
| run_07oOLC4jn7Vg | 2a6d810 (Baseline) | 675237767 | 0.938 | $0.328 | 0.368 | 0.642 |
| run_vgw01u5R4u-J | 5ce2584 | frisch (1320915688) | 0.856 | $0.326 | 0.369 | 0.586 |
| run_QfHOqhRM75Om | c75847b | 675237767 (wie Baseline) | 0.964 | $0.307 | 0.377 | 0.663 |

- **main = 12a28d5** enthält c75847b: Access-Review, Request-Log-Policy, Leak-Check und Vertragsfrist werden ohne Modell-Call
  abgegeben, wenn keine Aktion erlaubt ist und genau eine Rechnung gegriffen hat. In beiden Runs alle direkt abgegebenen
  Tasks 1.00 (5 bzw. 8 Tasks) bei $0.0001–0.0007 statt $0.005–0.016. max_steps 12, task_cost_cap 0.05 (kein Task kam an die Grenze).
- Der frische Seed (0.856) verlor bei Listen kompromittierter Agents (Antwort teilweise), nicht bei den geänderten Pfaden.
- **Wo die Kosten liegen:** 164 Hauptschleifen-Calls à ~10k Tokens (≈ $0.002), im Schnitt 3,4 Calls pro Task. Grundlast:
  Werkzeug-Schemas ~12k Zeichen, Regeldateien ~10k, Systemprompt 3,4k, Baum 1,7k. C ≈ a − 0,135·ln(Kosten): halbe Kosten ≈ +0,09 C.
- Nicht gemergt: Branch `fable/factsheet-owner` (Owner/E-Mail/Token-Service im Faktenblatt, offline korrekt, kein Mess-Run).
- Prüfskript: `PYTHONPATH=. uv run python -W ignore eval/offline/direct_check.py <run_id> [tNN …]`.
