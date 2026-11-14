"""Code tools against real files from dev runs (tests/fixtures, no network, no model): the computed results must equal
the platform's revealed answers. Fixtures are test data only; nothing here is read by the solver."""
import csv
import io
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent  # noqa: E402
import sources as srcs  # noqa: E402

FX = Path(__file__).parent / "fixtures"
EXP = json.loads((FX / "s675_expected.json").read_text())
FILES = {"/fleet/registry_export.json": "s675_registry_export.json", "/ops/change_calendar.csv": "s675_change_calendar.csv",
         "/security/egress_export.ods": "s675_egress_export.ods", "/fleet/agents.csv": "s675_agents.csv",
         "/logs/access/requests.csv": "s675_requests.csv", "/logs/access/change_tickets.csv": "s675_change_tickets.csv"}


class Client:
    def download_file(self, run_id, task_id, path):
        return (FX / FILES[path]).read_bytes(), ""


def ids(out: str) -> list[str]:
    return json.loads(re.search(r"ids of all matching rows.*?: (\[.*\])", out).group(1))


# lethal trifecta from the registry export only (t37)
hits, _ = agent.capabilities(json.loads((FX / "s675_registry_export.json").read_text()), {})
assert hits == sorted(EXP["t37"]), hits

# policy check with a ticket join (t03): 39 violations
match = {"path": "/logs/access/change_tickets.csv", "on": {"actor": "actor", "resource": "resource", "ticket": "ticket"},
         "where": [{"column": "status", "op": "eq", "value": "approved"}],
         "within": {"column": "ts", "from": "valid_from", "until": "valid_until"}, "before": {"column": "ts", "other": "revoked_at"}}
out = agent._filter_rows(Client(), "r", "t", {"path": "/logs/access/requests.csv", "where": [
    {"column": "action", "op": "eq", "value": "read"}, {"column": "scope_class", "op": "eq", "value": "private"},
    {"column": "actor", "op": "startswith", "value": "external:"}, {"column": "result", "op": "ne", "value": "denied"},
    {"op": "no_match", "value": match}]}, srcs.Evidence(), 8000)
assert sorted(ids(out)) == sorted(EXP["t03"]), out[-300:]

# exfiltrated records per team from the .ods register joined with the roster (t01)
out = agent._filter_rows(Client(), "r", "t", {"path": "/security/egress_export.ods", "where": [
    {"column": "records", "op": "ne", "value": "-"}, {"column": "result", "op": "eq", "value": "ok"}, {"column": "chg", "op": "empty"}],
    "count_distinct": "records", "group_by": "agent", "group_lookup": {"path": "/fleet/agents.csv", "key": "id", "value": "group"}},
    srcs.Evidence(), 8000)
per = json.loads(out.split("per group: ")[1])
top = max(per, key=per.get)
assert {"team": top, "records": per[top]} == EXP["t01"], per

# rotation slot with consumer services and a 30-minute buffer (seed 675 runbook), and the 60-minute variant (seed 388)
cal = list(csv.DictReader(io.StringIO((FX / "s675_change_calendar.csv").read_text())))
assert agent.earliest_slot(cal, "ci-runner,billing,support-desk", "2026-11-14T07:30:00Z", gap_min=30)[0] == "2026-11-14T19:00:00Z"
cal = list(csv.DictReader(io.StringIO((FX / "s388_change_calendar.csv").read_text())))
assert agent.earliest_slot(cal, "spaces", "2026-11-14T07:30:00Z")[0] == "2026-11-14T10:00:00Z"
assert agent.earliest_slot(cal, "ci-runner", "2026-11-14T07:30:00Z")[0] == "2026-11-14T12:00:00Z"
print("real-data tool checks ok")
