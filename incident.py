"""Incident facts in code: the gateway logs of the task's workspace, normalised to UTC, and what the runbook's
definitions (attack trace, patient zero, compromised agent, exposed token, attacker domain, exfiltrated records)
yield on them. No model call. Nothing here knows a file's content in advance: columns are recognised by their
values (their names change between runs), and the rule parameters that vary between scenarios come from the caller.

The result is a fact sheet with a citation for every fact. The model still reads the runbook and decides which
facts the task asks for.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
AGENT_RX = re.compile(r"^[a-z][a-z_]*-\d{1,3}$")
TS_FORMATS = ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
              "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M")


def parse_ts(s: Any, local_offset_h: float = 1.0, assume_local: bool = False) -> datetime | None:
    """A timestamp as aware UTC datetime. 'Z' or an explicit offset decides; a bare time is UTC unless the source
    is known to be local (`assume_local`: the file or column says so, or the format is the local dd.mm.yyyy)."""
    s = str(s or "").strip()
    if not s or not s[0].isdigit():
        return None
    m = re.fullmatch(r"(.*?)(Z|[+-]\d{2}:?\d{2})?", s)
    body, tz = m.group(1).strip(), m.group(2)
    body = re.sub(r"\.\d+$", "", body)
    for fmt in TS_FORMATS:
        try:
            d = datetime.strptime(body, fmt)
        except ValueError:
            continue
        if tz == "Z":
            off = 0.0
        elif tz:
            sign = -1 if tz[0] == "-" else 1
            off = sign * (int(tz[1:3]) + int(tz[-2:]) / 60)
        else:
            off = local_offset_h if (assume_local or fmt.startswith("%d")) else 0.0
        return (d - timedelta(hours=off)).replace(tzinfo=timezone.utc)
    return None


def iso(d: datetime | None) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else ""


def expand_ids(cell: Any) -> list[str]:
    """'C-100..C-103; C-200' -> the single ids, ranges inclusive, in order (duplicates kept: re-sends add up)."""
    out: list[str] = []
    parts = cell if isinstance(cell, list) else re.split(r"[;,|]\s*|\s+(?=[A-Za-z])", str(cell or ""))
    for part in parts:
        part = str(part).strip().strip('[]"\'')
        if not part or part in ("-", "—", "–"):
            continue
        m = re.fullmatch(r"(.*?)(\d+)\s*(?:\.\.+|–|—|\bto\b)\s*(.*?)(\d+)", part)
        if m and m.group(3) in ("", m.group(1)):
            a, b, w = int(m.group(2)), int(m.group(4)), len(m.group(2))
            out += [f"{m.group(1)}{i:0{w}d}" for i in range(min(a, b), max(a, b) + 1)]
        else:
            out.append(part)
    return out


def domain_of(target: str) -> str:
    t = str(target or "").strip().lower()
    t = re.sub(r"^[a-z]+://", "", t).split("/")[0]
    return t.rsplit("@", 1)[-1].strip(" <>")


def domain_contacts(read: Callable[[str], bytes], paths: set[str], domains: list[str], opts: dict | None = None) -> str:
    """Per domain: every log event whose target lies in it (URL, e-mail address or host; subdomains included), by status."""
    off = float((opts or {}).get("local_utc_offset_h") or 1)
    ev = load_events(read, paths, off)
    L = ["Contacts per domain over all gateway logs (target matched by domain: URLs, e-mail addresses and subdomains "
         "count; blocked/declined attempts are listed and count as contact attempts):"]
    for d in dict.fromkeys(str(x).strip().lower().strip(".") for x in domains if str(x).strip()):
        d = domain_of(d)
        hits = [e for e in ev if (lambda t: t == d or t.endswith("." + d))(domain_of(e.get("target", "")))]
        if not hits:
            L.append(f"- {d}: NEVER contacted (0 events)")
            continue
        by = {}
        for e in hits:
            by[e.get("status") or "?"] = by.get(e.get("status") or "?", 0) + 1
        f = hits[0]
        L.append(f"- {d}: {len(hits)} events {json.dumps(by)}; agents {json.dumps(sorted({e['agent'] for e in hits})[:8])}; "
                 f"first {f['agent']} {f['action']} {f.get('target')} {f.get('status')} at {iso(f['ts'])} ({cite(f)})")
    return "\n".join(L)


# --- columns by content ---------------------------------------------------------------------------------------
def _classify_columns(header: list[str], rows: list[list[str]]) -> dict[str, int]:
    """role -> column index for a log-like table, decided by what the cells look like (sample of the rows)."""
    sample = rows[:400]
    cols: dict[int, list[str]] = {i: [r[i].strip() for r in sample if i < len(r) and r[i].strip()] for i in range(len(header))}

    def share(i: int, pred: Callable[[str], bool]) -> float:
        v = cols[i]
        return sum(1 for x in v if pred(x)) / len(v) if v else 0.0

    roles: dict[str, int] = {}

    def pick(role: str, pred: Callable[[str], bool], least: float = 0.6, name: str | None = None) -> None:
        best = max((i for i in cols if i not in roles.values()), key=lambda i: (share(i, pred), -i), default=None)
        if best is not None and share(best, pred) >= least:
            roles[role] = best
        elif name:
            for i, h in enumerate(header):
                if i not in roles.values() and re.search(name, h, re.I):
                    roles[role] = i
                    break

    pick("ts", lambda x: parse_ts(x) is not None, name=r"time|^ts$|date|when")
    pick("trace", lambda x: bool(re.match(r"tr[-_]", x)), name=r"trace|span|corr")
    pick("request", lambda x: bool(re.match(r"rq[-_]", x)), 0.9, name=r"request|^rq")
    pick("parent", lambda x: bool(re.match(r"(board|trace|msg|tr)[:\-]", x)), 0.9, name=r"parent|caused|origin")
    pick("status", lambda x: x.lower() in ("ok", "declined", "blocked", "denied", "error", "failed", "success"), 0.9,
         name=r"status|outcome|result")
    pick("action", lambda x: bool(re.fullmatch(r"[a-z]+(_[a-z]+)+", x)), 0.5, name=r"action|event|op|verb")
    pick("agent", lambda x: bool(AGENT_RX.match(x)) or x.startswith(("human:", "external:")), 0.7,
         name=r"agent|actor|who|subject")
    pick("records", lambda x: bool(re.search(r"\w-\d+\s*\.\.", x)) or bool(re.fullmatch(r"[A-Z]+-\d+", x)), 0.9,
         name=r"record|rows|payload")
    pick("ticket", lambda x: bool(re.fullmatch(r"(CHG|TCK|CR|RFC)[-_]\d+", x)), 0.9, name=r"ticket|change")
    pick("ip", lambda x: bool(re.fullmatch(r"\d+\.\d+\.\d+\.\d+", x)), 0.9, name=r"ip$|addr")
    rest = [i for i in cols if i not in roles.values()]
    named = {r: next((i for i in rest if re.search(rx, header[i], re.I)), None)
             for r, rx in (("target", r"target|object|resource|dest|^to$"), ("detail", r"detail|note|info|message|comment|descr"))}
    for r, i in named.items():
        if i is not None:
            roles[r] = i
    rest = [i for i in rest if i not in roles.values()]
    if "target" not in roles and rest:  # the fullest remaining column is what the action was applied to
        roles["target"] = max(rest, key=lambda i: (len(cols[i]), -i))
        rest.remove(roles["target"])
    if "detail" not in roles and rest:
        roles["detail"] = max(rest, key=lambda i: (sum(map(len, cols[i])), -i))
    return roles


JSON_ALIASES = {"ts": r"^(ts|time|timestamp|at|when|time_utc|time_local)$", "agent": r"^(agent|actor|who|agent_id|subject)$",
                "action": r"^(action|event|op|verb|activity)$", "target": r"^(target|object|resource|dest|to)$",
                "status": r"^(status|outcome|result)$", "trace": r"^(trace|trace_id|span|corr)$",
                "parent": r"^(parent|caused_by|origin)$", "records": r"^(records|record_ids|rows)$",
                "detail": r"^(detail|details|note|info|message)$", "request": r"^(request_id|request|rq)$",
                "ticket": r"^(ticket|change|change_ticket)$"}


def load_events(read: Callable[[str], bytes], paths: set[str], local_offset_h: float = 1.0) -> list[dict]:
    """Every event of the gateway logs under /logs (jsonl and csv), in UTC order. Each: ts (datetime), agent, action,
    target, status, trace, parent, records, detail, request, ticket, file, line."""
    out: list[dict] = []
    for p in sorted(paths):
        low = p.lower()
        if "/logs/" not in low and not low.startswith("/log"):
            continue
        try:
            text = read(p).decode("utf-8-sig", "replace")
        except Exception:  # noqa: BLE001
            continue
        if low.endswith((".jsonl", ".ndjson")):
            keymap: dict[str, str] = {}
            for n, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    o = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(o, dict):
                    continue
                for k in o:
                    if k not in keymap:
                        keymap[k] = next((r for r, rx in JSON_ALIASES.items() if re.match(rx, k, re.I)), k)
                e = {keymap[k]: v for k, v in o.items()}
                local = any("local" in k.lower() for k in o if keymap[k] == "ts")
                e["ts"] = parse_ts(e.get("ts"), local_offset_h, local)
                e["file"], e["line"] = p, n
                out.append(e)
        elif low.endswith(".csv"):
            rows = list(csv.reader(io.StringIO(text)))
            if len(rows) < 2:
                continue
            header = [h.strip() for h in rows[0]]
            roles = _classify_columns(header, rows[1:])
            if "ts" not in roles or "action" not in roles:
                continue
            # a rotated archive states its zone in the column name or its README; dd.mm.yyyy is local anyway
            local = "local" in header[roles["ts"]].lower() or _readme_says_local(read, paths, p)
            for n, r in enumerate(rows[1:], 2):
                e = {role: (r[i].strip() if i < len(r) else "") for role, i in roles.items()}
                e["ts"] = parse_ts(e.get("ts"), local_offset_h, local)
                e["file"], e["line"] = p, n
                out.append(e)
    out = [e for e in out if e.get("ts")]
    out.sort(key=lambda e: (e["ts"], e["file"], e["line"]))
    for e in out:
        for k in ("agent", "action", "target", "status", "trace", "parent", "detail"):
            e[k] = str(e.get(k) or "").strip()
    return out


def _readme_says_local(read: Callable[[str], bytes], paths: set[str], p: str) -> bool:
    d = p.rsplit("/", 1)[0]
    for q in paths:
        if q.rsplit("/", 1)[0] == d and q.lower().endswith((".md", ".txt")):
            try:
                t = read(q).decode("utf-8", "replace").lower()
            except Exception:  # noqa: BLE001
                continue
            if re.search(r"local time|ortszeit|\bcet\b|\bcest\b|utc\s*\+", t) and p.rsplit("/", 1)[1].lower() in t:
                return True
    return False


# --- artifacts ------------------------------------------------------------------------------------------------
REQUEST_RX = re.compile(
    r"\b(send|forward|post|export|share|upload|e-?mail|deliver|transfer|provide|return|grant|delegate|open|approve|"
    r"reveal|publish|submit|copy|disclose|hand over|add|give|attach|dispatch|"
    r"sende[nt]?|schick\w*|leite\w*|weiterleiten|übermittel\w*|exportier\w*|poste\w*|gewähr\w*|"
    r"envía\w*|envie\w*|envoy\w*|invia\w*|reenv\w*|transf[eé]r\w*|publi\w+)\b", re.I)
OBJECT_RX = re.compile(
    r"\b(tokens?|secrets?|credentials?|keys?|passwor[dt]\w*|customer\w*|contact table|records?|data|daten|datos|données|"
    r"files?|dateien?|delegations?|permissions?|scopes?|access|tickets?|board|notice|timeline|table|kund\w+|client\w*|"
    r"geheim\w*|zugang\w*|berechtig\w*)\b", re.I)
ADDRESSEE_RX = re.compile(
    r"\b(agents?|processors?|assistants?|automated|peers?|bots?|models?|llms?|ai|you|agenten?|ihr|sie|vous|ustedes|"
    r"system prompt|ignore (all|any|previous)|instructions?)\b", re.I)


def decode_layers(text: str) -> str:
    """The text plus what its encoded parts say: zero-width characters removed, base64 / hex blobs decoded."""
    text = text.translate(ZERO_WIDTH)
    extra = []
    for m in re.finditer(r"[A-Za-z0-9+/=_-]{24,}", text):
        blob = m.group(0)
        try:
            raw = base64.b64decode(blob.replace("-", "+").replace("_", "/") + "=" * (-len(blob) % 4), validate=False)
            dec = raw.decode("utf-8")
        except Exception:  # noqa: BLE001
            continue
        if dec and sum(c.isprintable() or c.isspace() for c in dec) / len(dec) > 0.95 and re.search(r"[a-zA-Z]{3,} [a-zA-Z]{2,}", dec):
            extra.append(dec)
    for m in re.finditer(r"\b(?:[0-9a-fA-F]{2}){16,}\b", text):
        try:
            dec = bytes.fromhex(m.group(0)).decode("utf-8")
        except Exception:  # noqa: BLE001
            continue
        if re.search(r"[a-zA-Z]{3,} [a-zA-Z]{2,}", dec):
            extra.append(dec)
    return text + ("\n" + "\n".join(extra) if extra else "")


def asks_agents(text: str) -> str:
    """The sentence in which the text asks its (automated) reader to move data / secrets / files or to change
    permissions, or "" if there is none. A description of what a prompt is, or a licence blob, is not a request."""
    t = decode_layers(text)
    for sent in re.split(r"(?<=[.!?:])\s+|\n+", t):
        s = " ".join(sent.split())
        if len(s) < 25 or not REQUEST_RX.search(s) or not OBJECT_RX.search(s):
            continue
        dest = re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)+|\b[\w-]+\.(test|invalid|example|com|net|org|io)\b", s)
        if dest or ADDRESSEE_RX.search(s):
            return s[:220]
    return ""


def _md_table(text: str) -> list[dict[str, str]]:
    rows, header = [], None
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            header = None if not line.strip() else header
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if header is None:
            header = cells
        else:
            rows.append(dict(zip(header, cells)))
    return rows


def _section(text: str, title_rx: str) -> str:
    m = re.search(rf"(?im)^#+\s*[^\n]*({title_rx})[^\n]*\n(?P<body>.*?)(?=^#+\s|\Z)", text, re.S)
    return m.group("body") if m else ""


def _extract_text(path: str, data: bytes) -> str:
    low = path.lower()
    try:
        if low.endswith(".pdf"):
            from pypdf import PdfReader
            return "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages)
        if low.endswith(".docx"):
            from docx import Document
            return "\n".join(p.text for p in Document(io.BytesIO(data)).paragraphs)
        if low.endswith((".png", ".jpg", ".jpeg", ".xlsx", ".ods", ".odt")):
            return ""
        return data.decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return ""


# --- the analysis ---------------------------------------------------------------------------------------------
_EMBED = re.compile(r"data:(image/(?:png|jpe?g|gif|webp));base64,([A-Za-z0-9+/=]{200,})")
EMBED_MARK = "#img"


def embedded_images(text: str) -> list[tuple[str, bytes]]:
    """Pictures carried inside a text artifact as data URLs (e.g. an MCP tool's `icon`): (mime, bytes)."""
    import base64
    out = []
    for m in _EMBED.finditer(text):
        try:
            out.append((m.group(1), base64.b64decode(m.group(2))))
        except Exception:  # noqa: BLE001
            pass
    return out


def read_embedded(read: Callable[[str], bytes], p: str) -> tuple[str, bytes] | None:
    """`<path>#img<n>` -> the n-th picture embedded in that file (mime, bytes); None for an ordinary path."""
    if EMBED_MARK not in p:
        return None
    base, n = p.rsplit(EMBED_MARK, 1)
    return embedded_images(read(base).decode("utf-8", "replace"))[int(n)]


def analyse(read: Callable[[str], bytes], paths: set[str], opts: dict | None = None,
            vision: Callable[[str], str] | None = None) -> dict:
    """`vision(path)` transcribes an image attachment (one model call, cached by the caller); it is only asked
    when an artifact's own text carries no request."""
    opts = opts or {}
    off = float(opts.get("local_utc_offset_h") if opts.get("local_utc_offset_h") is not None else 1)
    ev = load_events(read, paths, off)

    def text(p: str) -> str:
        try:
            return read(p).decode("utf-8-sig", "replace") if p in paths else ""
        except Exception:  # noqa: BLE001
            return ""

    changes_path = next((p for p in sorted(paths) if re.search(r"/changes?(_log)?\.md$", p.lower())), "")
    changes = text(changes_path)
    redteam_sec = _section(changes, r"red[- ]?team|exercise")
    redteam_ids = set(re.findall(r"\b[a-z][a-z_]*-\d{1,3}\b", redteam_sec)) | set(re.findall(r"\bexternal:[\w-]+", redteam_sec))
    redteam_marks = [m for m in re.findall(r"\b[A-Z]{2,}-[A-Z]{2,}-", redteam_sec)]  # e.g. RT-TEST-
    flagged = _section(changes, r"compromised|flagged")
    quarantined = {a for a in re.findall(r"\b[a-z][a-z_]*-\d{1,3}\b", "\n".join(
        l for l in flagged.splitlines() if "quarantin" in l.lower()))}

    # artifacts that reached agents: the quarantine index maps the original location to the kept copy
    index_path = next((p for p in sorted(paths) if re.search(r"quarantine/index\.md$", p.lower())), "")
    artifacts: dict[str, dict] = {}
    for row in _md_table(text(index_path)):
        vals = list(row.values())
        copy = next((v for v in vals if v.startswith("/") and v in paths), "")
        if not copy:
            continue
        atts = [a for v in vals for a in re.findall(r"/[\w./-]+", v) if a in paths and a != copy]
        keys = {k.lower(): v for k, v in row.items()}
        loc = next((v for k, v in keys.items() if "location" in k or "original" in k), "")
        by = next((v for k, v in keys.items() if "by" in k.split() or "uploader" in k), "")
        at = next((v for k, v in keys.items() if "uploaded at" in k or k.startswith("uploaded_at")), "")
        is_img = lambda q: q.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))  # noqa: E731
        body = ("" if is_img(copy) else _extract_text(copy, read(copy))) + "\n" + "\n".join(_extract_text(a, read(a)) for a in atts if not is_img(a))
        redteam = by in redteam_ids or by.replace("external:", "") in redteam_ids or any(m in body for m in redteam_marks)
        ask = asks_agents(body)
        images = ([copy] if is_img(copy) else []) + [a for a in atts if is_img(a)]  # the artifact itself may be a picture
        if not is_img(copy):  # run_iOrNuR6b10uJ t44: the request was only in the MCP tool's embedded icon
            try:
                raw = read(copy).decode("utf-8", "replace") if len(read(copy)) < 5_000_000 else ""
            except Exception:  # noqa: BLE001
                raw = ""
            images += [f"{copy}{EMBED_MARK}{i}" for i in range(len(embedded_images(raw)))]
        seen_images = False
        if not ask and not redteam and vision and images:
            seen_images = True
            for a in images[:3]:
                try:
                    seen = vision(a)
                    redteam = redteam or any(m in seen for m in redteam_marks)
                    ask = "" if redteam else asks_agents(seen)
                except Exception:  # noqa: BLE001
                    seen_images = False
                if ask:
                    break
        artifacts[loc or copy] = {"copy": copy, "location": loc, "uploaded_by": by, "uploaded_at": at, "redteam": redteam,
                                  "asks": ask, "images": [] if seen_images else images}
    override = opts.get("entry_artifacts")
    if isinstance(override, str):
        override = [override]
    for a in artifacts.values():
        a["entry"] = (a["copy"] in override or a["location"] in override) if override else bool(a["asks"]) and not a["redteam"]

    by_trace: dict[str, list[dict]] = {}
    for e in ev:
        if e["trace"]:
            by_trace.setdefault(e["trace"], []).append(e)
    attack: dict[str, str] = {}  # trace -> why
    for tr, es in by_trace.items():
        f = es[0]
        if "read_artifact" in f["action"] and f["target"] in artifacts and artifacts[f["target"]]["entry"]:
            attack[tr] = f"starts with {f['agent']} reading {f['target']}"
    changed = True
    while changed:  # a trace whose parent is a board message posted within an attack trace
        changed = False
        posted = {e["target"] for tr in attack for e in by_trace[tr] if "post" in e["action"] and "board" in e["action"]}
        for tr, es in by_trace.items():
            if tr in attack:
                continue
            par = next((e["parent"] for e in es if e["parent"]), "")
            msg = par.split(":", 1)[-1]
            if par and (msg in posted or par in attack):
                attack[tr] = f"parent {par} was posted within an attack trace"
                changed = True
    acts = [e for tr in attack for e in by_trace[tr]]
    acts.sort(key=lambda e: e["ts"])

    def is_agent(a: str) -> bool:
        return bool(AGENT_RX.match(a))

    declined = lambda e: "declin" in e["action"] or "declin" in e["status"]  # noqa: E731
    compromised: dict[str, dict] = {}
    for e in acts:
        if is_agent(e["agent"]) and not declined(e):
            compromised.setdefault(e["agent"], e)
    tokens: dict[str, dict] = {}
    for e in acts:
        if "secret" in e["action"] and not declined(e):
            tokens.setdefault(e["target"], e)
    own = set(opts.get("own_domains") or []) or {"muggingface.example"}
    m = re.search(r"\(([\w.-]+\.[a-z]+)\)", text("/AGENTS.md"))
    if m and not opts.get("own_domains"):
        own = {m.group(1).lower()}
    attacker_domains: dict[str, dict] = {}
    for e in acts:
        if re.search(r"http_post|send_email|upload|transfer|smtp|ftp|put", e["action"]) and not declined(e):
            d = domain_of(e["target"])
            if "." in d and not any(d == o or d.endswith("." + o) for o in own):
                attacker_domains.setdefault(d, e)
    for e in ev:  # quarantines and releases done so far (humans, tier 1)
        if "quarantine" in e["action"] and e["status"].lower() in ("ok", "success", ""):
            quarantined.add(e["target"])
        if "release" in e["action"] and e["status"].lower() in ("ok", "success", ""):
            quarantined.discard(e["target"])

    entry = sorted((a for a in artifacts.values() if a["entry"]), key=lambda a: a["uploaded_at"] or "9")
    first_reads = {}
    for loc, a in artifacts.items():
        r = next((e for e in ev if "read_artifact" in e["action"] and e["target"] == loc and not declined(e)), None)
        if r:
            first_reads[loc] = r
    uploads = [e for e in ev if "upload" in e["action"] and "artifact" in e["action"]]
    return {"events": ev, "artifacts": artifacts, "attack": attack, "by_trace": by_trace, "acts": acts,
            "compromised": compromised, "tokens": tokens, "attacker_domains": attacker_domains,
            "quarantined": quarantined, "entry": entry, "first_reads": first_reads, "uploads": uploads,
            "redteam_ids": redteam_ids, "changes_path": changes_path, "index_path": index_path, "own": own}


def cite(e: dict) -> str:
    return f"{e['file']} line {e['line']}"


def fact_sheet(read: Callable[[str], bytes], paths: set[str], opts: dict | None = None,
               vision: Callable[[str], str] | None = None, out: dict | None = None) -> str:
    r = analyse(read, paths, opts, vision)
    if out is not None:
        out.update(r)
    L: list[str] = ["INCIDENT FACTS computed from the gateway logs (tier 1), all times UTC (archive local time converted)."]
    L.append("Artifacts in quarantine (attack entry = contains a request aimed at agents and is not a red-team artifact):")
    for a in r["artifacts"].values():
        fr = r["first_reads"].get(a["location"])
        verdict = "red-team exercise, not an attack" if a["redteam"] else ("ATTACK ENTRY" if a["entry"] else "no request to agents found, not an entry")
        L.append(f"- {a['copy']} | uploaded {a['uploaded_at']} by {a['uploaded_by']} | {verdict}"
                 + (f" | request: \"{a['asks'][:120]}\"" if a["asks"] and not a["redteam"] else "")
                 + (f" | first read_artifact: {fr['agent']} at {iso(fr['ts'])} ({cite(fr)})" if fr else " | never read"))
    if any(a["images"] and not a["asks"] and not a["redteam"] for a in r["artifacts"].values()):
        L.append("  (image attachments were not inspected; if one carries the request, call incident_facts again with entry_artifacts=[copy paths])")
    if r["entry"]:
        a = r["entry"][0]
        fr = r["first_reads"].get(a["location"])
        if fr:
            L.append(f"Patient zero (first read_artifact of the earliest entry artifact {a['copy']}): {fr['agent']} at {iso(fr['ts'])} ({cite(fr)})")
    L.append(f"Attack traces ({len(r['attack'])}): " + "; ".join(f"{t} ({w})" for t, w in r["attack"].items()))
    L.append("Compromised agents = agents with an action in an attack trace, declined excluded (first such action):")
    for a, e in sorted(r["compromised"].items()):
        L.append(f"- {a}: {e['action']} {e['target']} at {iso(e['ts'])} ({cite(e)})" + (" [already quarantined]" if a in r["quarantined"] else ""))
    L.append("Quarantined so far: " + (", ".join(sorted(r["quarantined"])) or "none"))
    L.append("Tokens read within attack traces (exposed): " + ("; ".join(
        f"{t} by {e['agent']} at {iso(e['ts'])} ({cite(e)})" for t, e in r["tokens"].items()) or "none"))
    L.append("Attacker domains = destinations of transfers within attack traces: " + ("; ".join(
        f"{d} ({e['agent']} {e['action']} {e['status']} at {iso(e['ts'])}, {cite(e)})" for d, e in sorted(r["attacker_domains"].items())) or "none"))
    posts = [e for e in r["acts"] if "post" in e["action"] and "board" in e["action"]]
    if posts:
        L.append("Board posts made within attack traces: " + "; ".join(f"{e['target']} by {e['agent']} at {iso(e['ts'])} ({cite(e)})" for e in posts))
    grants = [e for e in r["events"] if re.search(r"add_delegation|remove_delegation|grant|revoke", e["action"]) and "token" not in e["action"]]
    if grants:
        L.append("Permission changes made in the logs (not in the change log): " + "; ".join(
            f"{e['agent']} {e['action']} {e['target']} {e['status']} at {iso(e['ts'])} ({cite(e)}{', attack trace' if e['trace'] in r['attack'] else ''})" for e in grants[:12]))
    try:
        t = transfers(read, paths, opts)
        by_rq = {e.get("request"): e for e in r["events"] if e.get("request")}
        for x in t.get("rows", []):
            x["log"] = by_rq.get(x.get("request"))
        L += transfer_lines(t)
        L += runbook_reading(read, paths, t, vision)
        L += timeline(read, paths, r, t)
    except Exception as e:  # noqa: BLE001 - the log facts above stand on their own
        L.append(f"(transfer register not analysed: {type(e).__name__}: {e})")
    return "\n".join(L)


# --- tables (csv / xlsx / ods) --------------------------------------------------------------------------------
def load_table(path: str, data: bytes) -> tuple[str | None, list[str], list[tuple[int, list[str]]]]:
    """(sheet name or None, header, [(row number as shown in the file, cells)]). Title rows above the table are
    skipped; hidden rows are kept (they are part of the register)."""
    low = path.lower()
    if low.endswith(".csv"):
        rows = list(csv.reader(io.StringIO(data.decode("utf-8-sig", "replace"))))
        return None, [h.strip() for h in rows[0]] if rows else [], [(n, r) for n, r in enumerate(rows[1:], 2)]
    if low.endswith((".xlsx", ".xlsm")):
        import warnings

        from openpyxl import load_workbook
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ws = load_workbook(io.BytesIO(data), data_only=True).worksheets[0]
        raw = [(r, ["" if v is None else str(v) for v in row]) for r, row in enumerate(ws.iter_rows(values_only=True), 1)]
        sheet = ws.title
    elif low.endswith(".ods"):
        import agent
        sheet, raw = agent._ods_rows(data, None)
    else:
        return None, [], []
    raw = [(r, v) for r, v in raw if any(x.strip() for x in v)]
    k = next((i for i, (_, v) in enumerate(raw) if sum(1 for x in v if x.strip()) >= 3), 0)
    return sheet, [h.strip() for h in raw[k][1]] if raw else [], raw[k + 1:]


def transfers(read: Callable[[str], bytes], paths: set[str], opts: dict | None = None) -> dict:
    """The outbound transfer register, each row judged by the runbook's exfiltration rule: destination outside
    our own domain and not covered by an approved change ticket to a verified partner."""
    opts = opts or {}
    off = float(opts.get("local_utc_offset_h") if opts.get("local_utc_offset_h") is not None else 1)
    path = next((p for p in sorted(paths) if re.search(r"egress|transfer|outbound", p.rsplit("/", 1)[-1].lower())
                 and p.lower().endswith((".csv", ".xlsx", ".ods"))), "")
    if not path:
        return {"path": "", "rows": []}
    sheet, header, rows = load_table(path, read(path))
    cells = [r for _, r in rows]
    cols = {i: [r[i].strip() for r in cells[:500] if i < len(r) and r[i].strip()] for i in range(len(header))}

    def best(pred: Callable[[str], bool], name: str, least: float = 0.5, skip: tuple = ()) -> int | None:
        cand = [(sum(map(pred, v)) / len(v) if v else 0.0, -i) for i, v in cols.items() if i not in skip]
        sc, i = max(cand, default=(0.0, 0))
        if sc >= least:
            return -i
        return next((j for j, h in enumerate(header) if j not in skip and re.search(name, h, re.I)), None)

    c_ts = best(lambda x: parse_ts(x) is not None, r"time|ts|date")
    c_dest = best(lambda x: bool(re.fullmatch(r"([\w.+-]+@)?[\w-]+(\.[\w-]+)+", x)) and not x[0].isdigit(), r"^to$|dest|recipient|target")
    c_agent = best(lambda x: bool(AGENT_RX.match(x)), r"agent|actor|sender|from")
    rec_rx = re.compile(r"[A-Z]+-\d+(\s*(\.\.+|–)\s*[A-Z]+-\d+)?([;,\s]+[A-Z]+-\d+(\s*(\.\.+|–)\s*[A-Z]+-\d+)?)*")
    c_rec = next((j for j, h in enumerate(header) if j and re.search(r"record|^ids?$|customer", h, re.I) and not re.search(r"count|num|^n_", h, re.I)), None)
    if c_rec is None:  # the column whose cells are id ranges; never the row id (column 0), the agent or the time
        cand = [j for j in cols if j not in (0, c_ts, c_dest, c_agent) and any(".." in x and rec_rx.fullmatch(x) for x in cols[j])]
        c_rec = cand[0] if cand else None
    c_status = best(lambda x: x.lower() in ("ok", "blocked", "denied", "failed", "success", "error"), r"status|outcome|result", 0.8)
    c_ticket = next((j for j, h in enumerate(header) if re.search(r"ticket|change|chg|approval", h, re.I)), None)
    local = c_ts is not None and "local" in header[c_ts].lower()

    def text(p: str) -> str:
        try:
            return read(p).decode("utf-8-sig", "replace") if p in paths else ""
        except Exception:  # noqa: BLE001
            return ""

    own = set(opts.get("own_domains") or [])
    m = re.search(r"\(([\w.-]+\.[a-z]+)\)", text("/AGENTS.md"))
    own = own or ({m.group(1).lower()} if m else {"muggingface.example"})
    partners: set[str] = set()  # domains of verified external contacts
    for p in sorted(paths):
        if re.search(r"contacts?\.csv$", p.lower()):
            for row in csv.DictReader(io.StringIO(text(p))):
                vals = {k.lower(): str(v or "").strip() for k, v in row.items() if k}
                addr = next((v for v in vals.values() if "@" in v), "")
                verified = next((v for k, v in vals.items() if "verif" in k), "yes").lower() in ("yes", "true", "1", "y")
                if addr and verified:
                    partners.add(domain_of(addr))
    changes = "".join(text(p) for p in sorted(paths) if re.search(r"/changes?(_log)?\.md$", p.lower()))
    approved = set(re.findall(r"\b[A-Z]{2,5}-\d{3,6}\b", _section(changes, r"approved (data )?transfers?")))
    for p in sorted(paths):  # change tickets as a table
        if re.search(r"change_tickets?\.csv$|approvals?\.csv$", p.lower()):
            for row in csv.DictReader(io.StringIO(text(p))):
                v = [str(x or "").strip() for x in row.values()]
                if any(x.lower() == "approved" for x in v) and v:
                    approved.add(v[0])
    # Where approvals are recorded varies (change log section, the on-call handover, ...): a ticket of the register
    # counts as approved when a tier-2 text file names it on a line that approves it.
    wanted = {r[c_ticket].strip() for _, r in rows if c_ticket is not None and c_ticket < len(r) and r[c_ticket].strip()} - approved
    for p in sorted(paths):
        if wanted and p.lower().endswith((".md", ".txt", ".docx", ".pdf", ".odt")) \
                and not re.search(r"^/(artifacts|board|inbox|intel|docs|notes|tickets|drafts|integrations)/", p.lower()):
            try:
                if p.lower().endswith(".odt"):
                    import agent
                    doc = agent._odf_text(p, read(p))
                else:
                    doc = _extract_text(p, read(p))
            except Exception:  # noqa: BLE001
                continue
            for line in doc.splitlines():
                for tk in [w for w in wanted if w in line]:
                    if re.search(r"approv|genehmig|authori[sz]ed|signed off", line, re.I) and not re.search(
                            r"not (yet )?approv|unapprov|reject|denied|pending|withdrawn|revoked|nicht genehmig", line, re.I):
                        approved.add(tk)
    out = []
    for n, r in rows:
        g = lambda i: r[i].strip() if i is not None and i < len(r) else ""  # noqa: E731
        ids = expand_ids(g(c_rec)) if g(c_rec) not in ("", "-") else []
        ids = [i for i in ids if re.search(r"\d", i)]
        ts = parse_ts(g(c_ts), off, local)
        if not ids or not ts:
            continue
        d = domain_of(g(c_dest))
        internal = any(d == o or d.endswith("." + o) for o in own)
        partner = any(d == q or d.endswith("." + q) or q.endswith("." + d) for q in partners)
        tk = g(c_ticket)
        covered = bool(tk) and tk in approved and partner
        out.append({"id": r[0].strip(), "row": n, "request": next((v.strip() for v in r if re.match(r"rq[-_]", v.strip())), ""), "ts": ts, "agent": g(c_agent), "dest": d, "records": g(c_rec), "ids": ids,
                    "status": g(c_status).lower(), "ticket": tk, "internal": internal, "covered": covered,
                    "counts": not internal and not covered,
                    "why": "internal destination" if internal else f"covered by approved ticket {tk} to a verified partner" if covered
                    else ("ticket " + tk + (" not approved" if tk not in approved else " but destination is not a verified partner")) if tk else "no ticket"})
    out.sort(key=lambda t: t["ts"])
    canaries: set[str] = set()
    cpath = next((p for p in sorted(paths) if re.search(r"canar|honey", p.lower()) and p.lower().endswith(".csv")), "")
    if cpath:
        canaries = {r[0].strip() for r in list(csv.reader(io.StringIO(text(cpath))))[1:] if r}
    return {"path": path, "sheet": sheet, "rows": out, "canaries": canaries, "canary_path": cpath}


def transfer_lines(t: dict) -> list[str]:
    if not t.get("rows"):
        return []
    loc = (lambda x: f"sheet {t['sheet']!r} row {x['row']}") if t["sheet"] else (lambda x: f"record {x['id']}")
    L = [f"Transfers carrying records in {t['path']} (cite by {'sheet + row' if t['sheet'] else 'record id'}; hidden rows included):"]
    for x in t["rows"]:
        L.append(f"- {x['id']} ({loc(x)}) {iso(x['ts'])} {x['agent']} -> {x['dest']} {x['records']} = {len(x['ids'])} records, "
                 f"status {x['status']}" + (f", log {cite(x['log'])}" if x.get("log") else "") + ": " + ("COUNTS as exfiltration (" + x["why"] + ")" if x["counts"] else "does not count (" + x["why"] + ")"))
    cnt = [x for x in t["rows"] if x["counts"]]
    if cnt:
        ok = [x for x in cnt if x["status"] in ("ok", "success")]
        allids = [i for x in cnt for i in x["ids"]]
        L.append(f"Exfiltration under the rule 'outside our domain and not covered by an approved ticket to a verified partner': "
                 f"{len(allids)} records summed over {len(cnt)} transfers (every transferred record, re-sends and overlaps add up; "
                 f"{len(set(allids))} distinct ids); successful transfers only: {sum(len(x['ids']) for x in ok)} summed, "
                 f"{len({i for x in ok for i in x['ids']})} distinct. Check the runbook for which of these it wants.")
        L.append("An answer (or draft) that rests on this count or these domains cites EVERY counting transfer above by its "
                 + ("sheet + row" if t["sheet"] else "record id") + f" in {t['path']} (not the log lines), plus any document it used.")
        L.append("Destination domains of the counting transfers: " + json.dumps(sorted({x["dest"] for x in cnt}))
                 + "; successful only: " + json.dumps(sorted({x["dest"] for x in ok})))
        L.append(f"First counting transfer (blocked or successful): {cnt[0]['id']} at {iso(cnt[0]['ts'])}"
                 + (f"; first successful: {ok[0]['id']} at {iso(ok[0]['ts'])}" if ok else "; none successful"))
        firsts: dict[str, dict] = {}
        for x in ok:
            firsts.setdefault(x["agent"], x)
        if ok:
            L.append("First SUCCESSFUL counting transfer per sending agent (a blocked transfer delivered nothing): " + "; ".join(
                f"{a}: {x['id']} to {x['dest']} at {iso(x['ts'])}" for a, x in firsts.items()))
        if t["canaries"]:
            hit = sorted(t["canaries"] & set(allids))
            hit_ok = sorted(t["canaries"] & {i for x in ok for i in x["ids"]})
            L.append(f"Canary records ({t['canary_path']}, cite each by record id) in counting transfers: {json.dumps(hit)}"
                     + ("" if hit == hit_ok else f"; in successful ones only: {json.dumps(hit_ok)}")
                     + "; per transfer: " + "; ".join(f"{x['id']}: {len(t['canaries'] & set(x['ids']))}" for x in cnt))
    cov = [x for x in t["rows"] if x["covered"]]
    if cov:
        L.append("Approved transfers to verified partners: " + "; ".join(f"{x['id']} at {iso(x['ts'])} to {x['dest']} ({x['ticket']})" for x in cov))
    return L


def other_times(read: Callable[[str], bytes], paths: set[str], r: dict) -> list[str]:
    """Time-stamped facts outside the gateway log that event-order questions ask about: change-log rows and the SIEM
    alerts that concern the attack (an exposed token, a compromised agent or an attacker domain)."""
    L: list[str] = []
    if r["changes_path"]:
        rows = []
        for n, line in enumerate(read(r["changes_path"]).decode("utf-8-sig", "replace").splitlines(), 1):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if line.strip().startswith("|") and parse_ts(c[0]):
                rows.append(f"{iso(parse_ts(c[0]))} {' '.join(c[1:4])} (line {n})")
        if rows:
            L.append(f"Change log {r['changes_path']} (humans, tier 2): " + "; ".join(rows[:10]))
    keys = set(r["tokens"]) | set(r["compromised"]) | set(r["attacker_domains"])
    for p in sorted(paths):
        if re.search(r"siem|alert", p.lower()) and p.lower().endswith((".csv", ".xlsx", ".ods")):
            sheet, header, rows = load_table(p, read(p))
            hits = []
            for n, row in rows:
                line = " | ".join(x.strip() for x in row)
                ts = next((parse_ts(x) for x in row if parse_ts(x)), None)
                if ts and re.search(r"secret|token|exfil|egress|outbound|transfer", line, re.I) and any(k in line for k in keys):
                    hits.append(f"{iso(ts)} {line[:110]} ({'sheet ' + repr(sheet) + ' row ' + str(n) if sheet else 'line ' + str(n)})")
            if hits:
                L.append(f"SIEM alerts in {p} about the attack (tier 2): " + "; ".join(hits[:6]))
    return L


def current_changes(read: Callable[[str], bytes], paths: set[str], opts: dict | None = None,
                    vision: Callable[[str], str] | None = None) -> dict:
    """Everything that changed permissions after the registry export, as arguments for agent.capabilities: the rows
    of the change log (humans) and the grants / delegations agents made themselves (gateway log), in time order,
    plus the agents that are quarantined now (they cannot act)."""
    r = analyse(read, paths, opts, vision)
    ops: list[tuple[datetime, str, str, str, str]] = []
    if r["changes_path"]:
        for n, line in enumerate(read(r["changes_path"]).decode("utf-8-sig", "replace").splitlines(), 1):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if line.strip().startswith("|") and len(c) >= 4 and parse_ts(c[0]):
                ops.append((parse_ts(c[0]), c[1], c[2], c[3], f"{r['changes_path']} line {n}"))
    for e in r["events"]:
        if re.fullmatch(r"(add|remove)_delegation|(grant|revoke)_scope", e["action"]) and e["status"].lower() in ("ok", "success", ""):
            ops.append((e["ts"], e["action"], e["agent"], e["target"], cite(e)))
    ops.sort(key=lambda o: o[0])
    out: dict[str, Any] = {"add_delegations": [], "remove_delegations": [], "grant_scopes": [], "revoke_scopes": [],
                           "exclude": sorted(r["quarantined"]), "compromised": sorted(r["compromised"]), "notes": []}
    for ts, change, agent, value, where in ops:
        key = {"add_delegation": ("add_delegations", "remove_delegations", {"from": agent, "to": value}),
               "remove_delegation": ("remove_delegations", "add_delegations", {"from": agent, "to": value}),
               "grant_scope": ("grant_scopes", "revoke_scopes", {"agent": agent, "scope": value}),
               "revoke_scope": ("revoke_scopes", "grant_scopes", {"agent": agent, "scope": value})}.get(change)
        if not key:
            continue
        if key[2] in out[key[1]]:
            out[key[1]].remove(key[2])  # a later change undoes the earlier opposite one
        out[key[0]].append(key[2])
        out["notes"].append(f"{iso(ts)} {change} {agent} {value} ({where})")
    return out


def timeline(read: Callable[[str], bytes], paths: set[str], r: dict, t: dict) -> list[str]:
    """One list of the dated facts that event-order questions ask about, sorted in code (UTC)."""
    items: list[tuple[datetime, str]] = []
    for e in r["uploads"]:
        a = r["artifacts"].get(e["target"])
        red = e["agent"] in r["redteam_ids"] or e["agent"].replace("external:", "") in r["redteam_ids"]
        if a or red:
            kind = "red-team canary artifact" if (red or (a and a["redteam"])) else "attack ENTRY artifact" if a["entry"] else "harmless quarantined artifact"
            items.append((e["ts"], f"{kind} uploaded by {e['agent']}: {e['target']} ({cite(e)})"))
    for loc, e in r["first_reads"].items():
        a = r["artifacts"][loc]
        if a["entry"]:
            items.append((e["ts"], f"entry artifact {loc} first processed (read_artifact) by {e['agent']} ({cite(e)}; cite the copy {a['copy']} by path too)"))
    seen_secret = False
    board: dict[str, str] = {}
    for p in sorted(paths):
        if "board" in p.lower() and p.lower().endswith((".jsonl", ".json", ".csv", ".md")):
            for n, line in enumerate(read(p).decode("utf-8", "replace").splitlines(), 1):
                for mid in re.findall(r"\b[A-Z]{1,4}-\d{2,6}\b", line[:200]):
                    board.setdefault(mid, f"{p} line {n}")
    for e in r["acts"]:
        if "post" in e["action"] and "board" in e["action"]:
            items.append((e["ts"], f"injected notice {e['target']} posted on the board by {e['agent']} within the attack ({board.get(e['target'], cite(e))})"))
        if "secret" in e["action"] and "declin" not in e["status"]:
            items.append((e["ts"], f"{'secret read' if seen_secret else 'FIRST secret read'} within the attack: {e['target']} by {e['agent']} ({cite(e)})"))
            seen_secret = True
    for e in r["events"]:
        if "quarantine" in e["action"] or "release" in e["action"]:
            items.append((e["ts"], f"{e['target']} {e['action']} by {e['agent']} ({cite(e)})"))
        elif re.fullmatch(r"(add|remove)_delegation|(grant|revoke)_scope", e["action"]):
            items.append((e["ts"], f"{e['agent']} {e['action']} {e['target']} in the gateway log{' (attack trace)' if e['trace'] in r['attack'] else ''} ({cite(e)})"))
    loc = (lambda x: f"sheet {t['sheet']!r} row {x['row']}") if t.get("sheet") else (lambda x: f"record {x['id']}")
    first_ok = False
    for x in t.get("rows", []):
        where = f"{t['path']} {loc(x)}" + (f"; {cite(x['log'])}" if x.get("log") else "")
        if x["covered"]:
            items.append((x["ts"], f"approved transfer {x['id']} sent to verified partner {x['dest']} ({where})"))
        elif x["counts"]:
            tag = ""
            if x["status"] in ("ok", "success") and not first_ok:
                first_ok, tag = True, " = FIRST successful exfiltrating transfer"
            items.append((x["ts"], f"exfiltrating transfer {x['id']} to {x['dest']} status {x['status']}{tag} ({where})"))
    if r["changes_path"]:
        for n, line in enumerate(read(r["changes_path"]).decode("utf-8-sig", "replace").splitlines(), 1):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            if line.strip().startswith("|") and parse_ts(c[0]):
                items.append((parse_ts(c[0]), f"change log: {' '.join(c[1:4])}{' (' + c[6] + ')' if len(c) > 6 and c[6] else ''} took effect ({r['changes_path']} line {n})"))
    keys = set(r["tokens"]) | set(r["compromised"]) | set(r["attacker_domains"])
    for p in sorted(paths):
        if re.search(r"siem|alert", p.lower()) and p.lower().endswith((".csv", ".xlsx", ".ods")):
            sheet, header, rows = load_table(p, read(p))
            for n, row in rows:
                line = " | ".join(x.strip() for x in row if x.strip())
                ts = next((parse_ts(x) for x in row if parse_ts(x)), None)
                if ts and re.search(r"secret|token|exfil|egress|outbound|transfer|upload|artifact", line, re.I) and any(k in line for k in keys):
                    items.append((ts, f"SIEM alert: {line[:100]} ({p} {'sheet ' + repr(sheet) + ' row ' + str(n) if sheet else 'line ' + str(n)})"))
    items.sort(key=lambda i: i[0])
    return ["TIMELINE, sorted earliest first (UTC). For an order-of-events question do not sort yourself: call incident_facts "
            "again with order=[{\"label\": \"A: <the event text of the question>\", \"entry\": <number below>}, ...] and submit the order it returns:"] + [f"{k}. {iso(ts)} {txt}" for k, (ts, txt) in enumerate(items[:40], 1)]


# --- board triage ---------------------------------------------------------------------------------------------
SENSITIVE_RX = re.compile(
    r"tokens?\b|jetons?\b|secret|geheim|credential|clave|contrase|passwor|passwort|schlüssel|delegat|délég|deleg|permis|berechtig|"
    r"\bscopes?\b|\bgrant|\baccess|accès|acceso|zugriff|zugang|customer|client|kund|contact|kontakt|\btabl|tabelle|records?\b|"
    r"\bdatos\b|données|\bdaten|\bdata\b|\bfiles?\b|fichier|archivo|datei|export|admin", re.I)


def board_candidates(read: Callable[[str], bytes], paths: set[str], path: str | None = None) -> tuple[str, list[dict]]:
    """Posts of the agents board that could ask for data / secrets / files to be sent or for permissions to change:
    every post (decoded: base64, hex, zero-width) that names an address or domain or a sensitive object. Posts split
    over several messages ([1/2], [2/2]) come as one unit. The verdict is not made here."""
    path = path if path in paths else next((p for p in sorted(paths) if "board" in p.lower() and p.lower().endswith((".jsonl", ".ndjson"))), "")
    if not path:
        return "", []
    posts = []
    for n, line in enumerate(read(path).decode("utf-8", "replace").splitlines(), 1):
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(o, dict):
            continue
        vals = [v for v in o.values() if isinstance(v, str)]
        mid = next((v for v in vals if re.fullmatch(r"[A-Z]{1,4}-\d{2,6}", v)), "")
        body = max(vals, key=len) if vals else ""
        author = next((v for v in vals if AGENT_RX.match(v) or v.startswith(("external:", "human:"))), "")
        dec = decode_layers(body)
        posts.append({"id": mid, "line": n, "author": author, "text": body, "decoded": dec[len(body.translate(ZERO_WIDTH)):].strip(),
                      "part": re.search(r"[\[(](\d+)\s*/\s*(\d+)[\])]", body)})
    units: list[dict] = []
    used: set[int] = set()
    for i, p in enumerate(posts):
        if i in used:
            continue
        ids, lines, text = [p["id"]], [p["line"]], (p["decoded"] or p["text"])
        if p["part"] and p["part"].group(1) == "1":  # collect the following parts k/n (they may be a few posts apart)
            total, want = int(p["part"].group(2)), 2
            for j in range(i + 1, min(i + 40, len(posts))):
                q = posts[j]
                if q["part"] and int(q["part"].group(2)) == total and int(q["part"].group(1)) == want and j not in used:
                    used.add(j)
                    ids.append(q["id"]); lines.append(q["line"]); text += " " + (q["decoded"] or q["text"])
                    want += 1
                    if want > total:
                        break
        dest = re.search(r"[\w.+-]+@[\w-]+(\.[\w-]+)+|\b[\w-]+\.(test|invalid|example|com|net|org|io)\b", text)
        if dest or SENSITIVE_RX.search(text) or p["decoded"]:
            units.append({"ids": ids, "lines": lines, "author": p["author"], "text": " ".join(text.split()),
                          "encoded": bool(p["decoded"]), "split": len(ids) > 1})
    return path, units


def agent_activity(read: Callable[[str], bytes], paths: set[str], agent: str, opts: dict | None = None) -> str:
    """What the gateway log (tier 1) says one agent did: every security-relevant event with its line, the routine
    ones as counts. For checking an agent's own status report claim by claim."""
    opts = opts or {}
    off = float(opts.get("local_utc_offset_h") if opts.get("local_utc_offset_h") is not None else 1)
    ev = load_events(read, paths, off)
    mine = [e for e in ev if e["agent"] == agent]
    to_me = [e for e in ev if e["target"] == agent and e["agent"] != agent]
    if not mine and not to_me:
        return f"ERROR: no event of or for {agent!r} in the gateway logs; check the agent id"
    key_rx = re.compile(r"secret|delegat|grant|revoke|quarantine|release|declin|post_board|upload")
    own = {"muggingface.example"}
    L = [f"GATEWAY LOG (tier 1) for {agent}, all times UTC: {len(mine)} own events from {iso(mine[0]['ts']) if mine else '-'} to {iso(mine[-1]['ts']) if mine else '-'}."]
    counts: dict[str, int] = {}
    for e in mine:
        counts[e["action"]] = counts.get(e["action"], 0) + 1
    L.append("Own events by action: " + ", ".join(f"{a} x{n}" for a, n in sorted(counts.items(), key=lambda kv: -kv[1])))
    def row(e: dict) -> str:
        rec = e.get("records")
        return (f"- {iso(e['ts'])} {e['agent']} {e['action']} {e['target']} status={e['status']}"
                + (f" records={rec}" if rec else "") + (f" detail={e['detail'][:70]!r}" if e["detail"] else "") + f" trace={e['trace']} ({cite(e)})")
    keyev = [e for e in mine if key_rx.search(e["action"]) or key_rx.search(e["status"])]
    L.append(f"Its secret reads, delegations, permission changes, board posts, declines ({len(keyev)}; none listed = none in the log):")
    L += [row(e) for e in keyev[:40]]
    ext = [e for e in mine if re.search(r"http_post|send_email|upload|transfer", e["action"])
           and "." in domain_of(e["target"]) and not any(domain_of(e["target"]).endswith(o) for o in own)]
    L.append(f"Its transfers / messages to destinations outside our domain ({len(ext)}):")
    L += [row(e) for e in ext[:25]]
    L.append(f"Events of OTHER agents or humans that target {agent} (delegations to it, quarantine, grants) ({len(to_me)}):")
    L += [row(e) for e in to_me[:25]]
    firsts = {}
    for e in mine:
        firsts.setdefault(e["action"], e)
    L.append("First event per action: " + "; ".join(f"{a} {iso(e['ts'])} (line {e['line']})" for a, e in firsts.items()))
    L.append("A claim is contradicted only if these tier-1 events show the opposite; cite the lines that contradict it.")
    return "\n".join(L)


# --- MCP / integration manifests ------------------------------------------------------------------------------
def manifest_audit(read: Callable[[str], bytes], paths: set[str], directory: str | None = None) -> dict:
    """Server manifests (.json) of one directory against its approval list (a csv with a sha256 column): the hash of
    each manifest exactly as served vs. the newest approved hash of that server, and every description string with
    its encoded parts decoded (for the 'instructions aimed at agents' rule, judged by the caller)."""
    import hashlib

    dirs: dict[str, list[str]] = {}
    for p in paths:
        if p.lower().endswith(".json"):
            dirs.setdefault(p.rsplit("/", 1)[0], []).append(p)
    d = directory.rstrip("/") if directory and directory.rstrip("/") in dirs else None
    if d is None:
        cand = [k for k, v in dirs.items() if len(v) >= 3 and (re.search(r"mcp|integration|server|plugin|connector", k.lower())
                or any(q.rsplit("/", 1)[0] == k and q.lower().endswith(".csv") for q in paths))]
        d = next((k for k in sorted(cand) if re.search(r"mcp|integration|server|plugin|connector", k.lower())), cand[0] if cand else None)
    if d is None:
        return {"dir": "", "servers": []}
    approved: dict[str, tuple[str, str]] = {}  # server -> (approved_at, sha256) of the newest row
    listed: set[str] = set()
    csv_path = ""
    for q in sorted(paths):
        if q.rsplit("/", 1)[0] == d and q.lower().endswith(".csv"):
            rows = list(csv.reader(io.StringIO(read(q).decode("utf-8-sig", "replace"))))
            if len(rows) < 2:
                continue
            body = rows[1:]
            hcol = next((i for i in range(len(rows[0])) if all(re.fullmatch(r"[0-9a-fA-F]{64}", r[i].strip()) for r in body if i < len(r))), None)
            if hcol is None:
                continue
            csv_path = q
            tcol = next((i for i in range(len(rows[0])) if all(parse_ts(r[i]) for r in body if i < len(r))), None)
            for r in body:
                name, at = r[0].strip(), (iso(parse_ts(r[tcol])) if tcol is not None else "")
                listed.add(name)
                if name not in approved or at >= approved[name][0]:
                    approved[name] = (at, r[hcol].strip().lower())
    servers = []
    for p in sorted(dirs[d]):
        data = read(p)
        try:
            o = json.loads(data.decode("utf-8-sig"))
        except Exception:  # noqa: BLE001
            o = {}
        name = str(o.get("name") or p.rsplit("/", 1)[1][:-5]) if isinstance(o, dict) else p.rsplit("/", 1)[1][:-5]
        descs: list[str] = []

        def walk(x: Any) -> None:
            if isinstance(x, dict):
                for k, v in x.items():
                    if isinstance(v, str) and re.search(r"desc|summary|note|help|title|instruction", k, re.I):
                        descs.append(v)
                    else:
                        walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)

        walk(o)
        sha = hashlib.sha256(data).hexdigest()
        key = name if name in approved else p.rsplit("/", 1)[1][:-5]
        want = approved.get(key, ("", ""))[1]
        servers.append({"name": name, "path": p, "sha256": sha, "approved": want, "listed": key in listed or not csv_path,
                        "hash_ok": (bool(want) and sha == want) or not csv_path,  # no approval list here: no hash rule
                        "descriptions": [" ".join(decode_layers(t).split()) for t in dict.fromkeys(descs)]})
    return {"dir": d, "csv": csv_path, "servers": servers}


def order_events(sheet: str, order: list) -> tuple[list[str], list[str], list[str]]:
    """(labels sorted by the time of their timeline entry, the entry lines used, problems). `order` maps each label
    of the question to the number of an entry of the sheet's timeline."""
    entries = {int(m.group(1)): m.group(0) for m in re.finditer(r"(?m)^(\d+)\. (\d{4}-\d\d-\d\dT\S+Z) .*$", sheet.split("TIMELINE", 1)[-1])}
    picked, bad = [], []
    for o in order if isinstance(order, list) else []:
        try:
            label, n = str(o["label"]).strip(), int(o["entry"])
        except Exception:  # noqa: BLE001
            bad.append(f"unreadable item {o!r}")
            continue
        if n not in entries:
            bad.append(f"{label}: no timeline entry {n}")
            continue
        picked.append((entries[n].split(" ", 2)[1], n, label))
    picked = _fix_matches(picked, entries)
    picked.sort()
    return [p[2] for p in picked], [entries[p[1]] for p in picked], bad


_STOP = {"the", "was", "its", "our", "about", "with", "within", "from", "that", "this", "and", "for", "were", "has", "been",
         "took", "effect", "cite", "copy", "path", "too", "line", "record", "sheet", "row", "logs", "audit", "archive", "jsonl", "csv"}


def _stems(t: str) -> set[str]:
    t = re.sub(r"\((?:/|\w+ \w+ /)[^)]*\)", " ", t)  # citations do not describe the event
    return {w[:6] for w in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", t.lower()) if len(w) >= 3 and w not in _STOP}


def _fix_matches(picked: list[tuple[str, int, str]], entries: dict[int, str]) -> list[tuple[str, int, str]]:
    """When a label carries its event text ("D: the entry artifact was uploaded"), the entry it describes best wins
    over the number the model chose (run_GXlstedXsIFN t40: labels mapped to entries 1..5 in turn, 0.4). Greedy,
    each entry once; the model's choice stands when the text gives no better match."""
    texts = {i: (lab.split(":", 1)[1] if ":" in lab else "") for i, (_, _, lab) in enumerate(picked)}
    if sum(1 for t in texts.values() if t.strip()) < 2:
        return picked
    est = {n: _stems(e.split(" ", 2)[2] if e.count(" ") >= 2 else e) for n, e in entries.items()}
    score = {(i, n): len(_stems(texts[i]) & est[n]) for i in texts for n in entries if texts[i].strip()}
    cands = sorted(((sc, i, n) for (i, n), sc in score.items() if sc > 0), reverse=True)
    taken_i, taken_n, assign = set(), set(), {}
    for sc, i, n in cands:
        if i in taken_i or n in taken_n:
            continue
        assign[i] = n
        taken_i.add(i)
        taken_n.add(n)
    out = []
    for i, (ts, n, lab) in enumerate(picked):
        m = assign.get(i)
        if m is not None and score.get((i, m), 0) > score.get((i, n), 0):
            out.append((entries[m].split(" ", 2)[1], m, lab))
        else:
            out.append((ts, n, lab))
    return out


def _rule_flags(text: str) -> tuple[bool | None, bool | None]:
    """(only successful transfers count?, each record once?) as a counting rule words it; None = not stated."""
    t = " ".join(text.split())
    only_ok = None
    if re.search(r"both successful and blocked|blocked (attempts|transfers|ones)? ?(count|are counted|are included)|include blocked|count blocked", t, re.I):
        only_ok = False
    if re.search(r"only successful|blocked (ones|transfers|attempts)? ?(do not|don't|do n't|are not|never) count|blocked[^.]*not count|"
                 r"never left|leave (the )?blocked[^.]*out|blocked[^.]*(left out|excluded|ignored)|exclude blocked|ignore blocked", t, re.I):
        only_ok = True
    once = None
    if re.search(r"counts? twice|add(s)? up|every time it|each time it|summed|\bsum (them|it|all)\b|do not merge|don't merge|count every transfer", t, re.I):
        once = False
    if re.search(r"counted once|count(s|ed)? only once|single time|only once|once across|distinct|unique|deduplicat", t, re.I):
        once = True
    return only_ok, once


def runbook_reading(read: Callable[[str], bytes], paths: set[str], t: dict,
                    vision: Callable[[str], str] | None = None) -> list[str]:
    """The exfiltration figures under the counting rule as the operator files word it in THIS workspace (blocked
    transfers count or not, records add up or count once). The wording is quoted so the reader can check it. When
    the runbook sets the rule per incident in another file (run_iOrNuR6b10uJ: a photographed standing order; the
    typed copy is not in force), exactly that file is read (an image through vision)."""
    cnt = [x for x in t.get("rows", []) if x["counts"]]
    if not cnt:
        return []
    rule = ""
    for p in sorted(paths):
        if p.count("/") == 1 and p.lower().endswith(".md"):
            for line in read(p).decode("utf-8", "replace").splitlines():
                if re.search(r"exfiltrat", line, re.I) and re.search(r"record", line, re.I) and re.search(r"count|blocked|successful", line, re.I):
                    rule = " ".join(line.split())
                    break
        if rule:
            break
    if not rule:
        return []
    # "whether blocked attempts count ... is set per incident" names the question, not the answer
    only_ok, once = _rule_flags(re.sub(r"\bwhether\b[^.]*", "", rule, flags=re.I))
    source = ""
    for ref in dict.fromkeys(re.findall(r"/[\w./-]+\.\w+", rule)):
        if ref not in paths or source:
            continue
        try:
            if ref.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                doc = vision(ref) if vision else ""
            else:
                doc = _extract_text(ref, read(ref))
        except Exception:  # noqa: BLE001
            doc = ""
        if doc.startswith("ERROR"):
            doc = ""
        lines = [" ".join(l.split()) for l in re.split(r"\n\s*(?=\d+\.|[-*] )", doc)
                 if re.search(r"record|blocked|transfer", l, re.I)]
        o2, n2 = _rule_flags(" ".join(lines))
        if o2 is not None or n2 is not None:
            only_ok = o2 if o2 is not None else only_ok  # the referenced, incident-specific rule wins
            once = n2 if n2 is not None else once
            source = f"; the rule is set in {ref}: \"" + " / ".join(lines)[:330] + "\""
    only_ok, once = bool(only_ok), bool(once)
    use = [x for x in cnt if x["status"] in ("ok", "success")] if only_ok else cnt
    ids = [i for x in use for i in x["ids"]]
    n = len(set(ids)) if once else len(ids)
    L = [f"READING OF THE RUNBOOK RULE in this workspace (\"{rule[:330]}\"{source}): {'only successful transfers count' if only_ok else 'successful and blocked transfers count'}; "
         f"{'each record once' if once else 'every transferred record adds up'} -> exfiltrated records: {n}; counting transfers: "
         f"{json.dumps([x['id'] for x in use])}; their domains: {json.dumps(sorted({x['dest'] for x in use}))}; first of them: {use[0]['id'] + ' at ' + iso(use[0]['ts']) if use else 'none'}"
         + (f"; canary records in them: {json.dumps(sorted(t['canaries'] & set(ids)))}" if t.get("canaries") else "")]
    per: dict[str, list[dict]] = {}
    for x in use:
        per.setdefault(x["agent"], []).append(x)
    if per:
        loc = (lambda x: f"row {x['row']}") if t.get("sheet") else (lambda x: x["id"])
        share = {a: (len({i for x in xs for i in x["ids"]}) if once else sum(len(x["ids"]) for x in xs)) for a, xs in per.items()}
        L.append("Exfiltrated records per sending agent under this reading (largest share first; cite that agent's transfers): " + "; ".join(
            f"{a}: {share[a]} records in {json.dumps([loc(x) for x in per[a]])}" for a in sorted(share, key=lambda a: -share[a])))
    return L


# --- contracts: which breach-notification clause is in force -----------------------------------------------------
def agreement_terms(read: Callable[[str], bytes], paths: set[str], text: str,
                    vision: Callable[[str], str] | None = None) -> tuple[dict | None, list[dict], str]:
    """For the organisation the text names (looked up in the accounts table): the breach-notification window in force
    now. Base clause from the agreement, replaced by every amendment that is signed by both sides, replaces the
    notification clause and is effective at or before now (the latest such wins). (answer, sources, explanation)."""
    def txt(p: str) -> str:
        try:
            if p.lower().endswith((".png", ".jpg", ".jpeg")):
                return vision(p) if vision else ""
            return _extract_text(p, read(p))
        except Exception:  # noqa: BLE001
            return ""

    agents_md = txt("/AGENTS.md") if "/AGENTS.md" in paths else ""
    m = re.search(r"(?:now|current time)[^\n]*?(\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d)?Z)", agents_md, re.I)
    if not m:
        return None, [], "no current time found in /AGENTS.md"
    now = m.group(1)
    acc = next((p for p in sorted(paths) if re.search(r"accounts?\.csv$", p.lower()) and "/docs/" in p.lower()), "") or \
        next((p for p in sorted(paths) if re.search(r"(accounts|agreements|customers)\.csv$", p.lower())), "")
    if not acc:
        return None, [], "no accounts table"
    rows = list(csv.DictReader(io.StringIO(txt(acc))))
    low = " ".join(text.lower().split())
    hit = None
    for r in rows:
        vals = [str(v or "").strip() for v in r.values()]
        org = next((v for k, v in r.items() if k and re.search(r"organi[sz]ation|company|customer|partner|name", k, re.I)), "")
        if org and org.lower() in low and (hit is None or len(org) > len(hit[1])):
            hit = (r, org, vals)
    if not hit:
        return None, [], "no organisation of the accounts table named in the task"
    r, org, vals = hit
    agr = vals[0]
    doc = next((v for v in vals if v.startswith("/") and v in paths), "")
    if not doc:
        return None, [], f"no agreement document for {org}"

    def clause(t: str) -> tuple[int | None, str]:
        for sent in re.split(r"(?<=[.\"”])\s+|\n\s*\n", t):  # a scan breaks sentences across lines
            sent = " ".join(sent.split())
            if re.search(r"notif", sent, re.I) and re.search(r"breach", sent, re.I):
                h = re.search(r"within (\d+)\s*hours", sent, re.I)
                if h:
                    return int(h.group(1)), sent
        return None, ""

    def signer(t: str) -> str:
        s_ = re.search(r"[Ss]igned[^\n]*?for " + re.escape(org) + r" by ([A-ZÀ-Ž][\w'’.-]+(?: [A-ZÀ-Ž][\w'’.-]+)+)", t)
        return s_.group(1).strip(" .") if s_ else ""

    base = txt(doc)
    hours, _ = clause(base)
    who = signer(base)
    line3 = next((i for i, l in enumerate(base.splitlines(), 1) if agr in l), None)
    best = None  # (effective, path, hours, signer)
    notes = []
    stem = doc.rsplit(".", 1)[0]
    for p in sorted(x for x in paths if x.startswith(stem + "_amendment") or x.startswith(stem + "-amendment")):
        t = txt(p)
        if not t:
            continue
        h, sent = clause(t)
        if h is None or re.search(r"\bunchanged\b", sent, re.I):
            notes.append(f"{p}: does not replace the notification clause")
            continue
        if re.search(r"not signed|unsigned|draft|_{4,}", t, re.I) or not signer(t):
            notes.append(f"{p}: not signed for {org}, not in force")
            continue
        e = re.search(r"[Ee]ffective (?:from|as of|on)?\s*(\d{4}-\d\d-\d\d(?:T\d\d:\d\d(?::\d\d)?Z)?)", t)
        sd = re.search(r"[Ss]igned (\d{4}-\d\d-\d\d)", t)
        eff = (e.group(1) if e else sd.group(1) if sd else "")
        eff_cmp = eff if "T" in eff else eff + "T00:00:00Z"
        if not eff or eff_cmp > now:
            notes.append(f"{p}: {h} h, effective {eff or '?'} is after now ({now}), not in force yet")
            continue
        notes.append(f"{p}: {h} h, signed, effective {eff}: in force from then")
        if best is None or eff_cmp >= best[0]:
            best = (eff_cmp, p, h, signer(t))
    if best:
        hours, who = best[2], best[3] or who
    if hours is None:
        return None, [], f"no notification clause found in {doc}"
    ans = {"agreement": agr, "notify_hours": hours, "signatory": who}
    src = [{"path": acc, "record": agr}] + ([{"path": doc, "line": line3}] if line3 else [{"path": doc}]) + ([{"path": best[1]}] if best else [])
    expl = (f"{org}: agreement {agr} ({doc}); base clause {clause(base)[0]} h; now {now}.\n" + "\n".join(notes)
            + f"\nIN FORCE NOW: {json.dumps(ans)}" + (f" (from {best[1]})" if best else " (base clause)"))
    return ans, src, expl


# --- leaked tokens: full values in a dump against the inventory's hash fingerprints ---------------------------------
def leak_check(read: Callable[[str], bytes], paths: set[str], text: str) -> tuple[list[str], list[dict], str]:
    """Every value in the dump(s) the task names (or text files under /intel) is hashed (SHA-256) and compared with the
    fingerprint column of the token inventory (hex prefix). A value broken across lines (continuation indented) is
    joined; a truncated value (… or ...) cannot match, so only values leaked in full count."""
    import hashlib
    fp = next((p for p in sorted(paths) if re.search(r"fingerprint|token_hash", p.lower()) and p.lower().endswith(".csv")), "")
    if not fp:
        return [], [], "no fingerprint table"
    rows = list(csv.reader(io.StringIO(read(fp).decode("utf-8-sig", "replace"))))
    if len(rows) < 2:
        return [], [], "empty fingerprint table"
    hcol = next((i for i in range(len(rows[0])) if all(re.fullmatch(r"[0-9a-f]{8,64}", (r[i] if i < len(r) else "").strip().lower())
                                                        for r in rows[1:] if r)), None)
    if hcol is None:
        return [], [], "no hash column"
    fps = {r[hcol].strip().lower(): r[0].strip() for r in rows[1:] if r}
    named = [p for p in re.findall(r"/[\w./-]+", text) if p in paths and not p.endswith(".csv")]
    dumps = named or [p for p in sorted(paths) if p.startswith("/intel/") and p.lower().endswith((".txt", ".md", ".log"))]
    if re.search(r"\bboard\b", text, re.I):  # run_iOrNuR6b10uJ t31: "in the dump or on the agents board"
        dumps += [p for p in sorted(paths) if "/board" in p.lower() and p.lower().endswith((".jsonl", ".json", ".ndjson")) and p not in dumps]
    found: dict[str, tuple[str, int]] = {}
    for d in dumps:
        try:
            lines = read(d).decode("utf-8", "replace").splitlines()
        except Exception:  # noqa: BLE001
            continue
        if d.lower().endswith((".jsonl", ".json", ".ndjson")):  # board posts: the strings of each record, unescaped
            def _strs(v: Any) -> list[str]:
                return [v] if isinstance(v, str) else [x for y in (v.values() if isinstance(v, dict) else v if isinstance(v, list) else []) for x in _strs(y)]
            un = []
            for line in lines:
                try:
                    un.append(" ".join(_strs(json.loads(line))))
                except Exception:  # noqa: BLE001
                    un.append(line)
            lines = un
        cands: list[tuple[str, int]] = []
        for n, line in enumerate(lines, 1):
            toks = re.findall(r"[A-Za-z0-9_\-+/=.]{8,}", line)
            cands += [(t.strip("."), n) for t in toks]
            nxt = lines[n] if n < len(lines) else ""
            if toks and re.match(r"\s+\S", nxt) and line.rstrip().endswith(toks[-1]):  # value continued on the next line
                cont = re.match(r"\s+([A-Za-z0-9_\-+/=]+)", nxt)
                if cont:
                    cands.append((toks[-1] + cont.group(1), n))
            for m in re.finditer(r"(?=[:=]\s*([^\s\"',;:=()]{8,}))", line):  # overlapping: "ID=value" after "label:"
                cands.append((m.group(1), n))
        for v, n in cands:
            h = hashlib.sha256(v.encode()).hexdigest()
            for pre, tid in fps.items():
                if h.startswith(pre) and tid not in found:
                    found[tid] = (d, n)
    ids = sorted(found)
    src = sorted({found[i][0] for i in ids})
    cites = [{"path": p} for p in src if not p.lower().endswith((".jsonl", ".json", ".ndjson"))] + \
        [{"path": fp, "record": i} for i in ids] + \
        [{"path": found[i][0], "line": found[i][1]} for i in ids if found[i][0].lower().endswith((".jsonl", ".json", ".ndjson"))]
    expl = (f"Values in {json.dumps(dumps)} hashed (SHA-256) and compared with {fp} column {rows[0][hcol]!r}; joined line "
            f"continuations, truncated values cannot match. Leaked in full: {json.dumps(ids)}"
            + "".join(f"\n- {i}: {found[i][0]} line {found[i][1]}" for i in ids))
    return ids, cites, expl
