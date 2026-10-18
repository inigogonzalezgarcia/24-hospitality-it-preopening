"""Outputs: report.html (with a Gantt chart), review.md (weekly pre-opening meeting), actions.csv, findings.csv and
golive_checklist.md."""
from __future__ import annotations

import csv
import html
from datetime import date, timedelta
from pathlib import Path

from .checks import AREAS, CRITICAL, INFO, WARNING, Finding, area_status, d
from .model import Project
from .schedule import Slot, critical_path, overall, readiness, ready_date

e = html.escape


def summary(p: Project, slots: dict[str, Slot], findings: list[Finding]) -> dict:
    ready = ready_date(p, slots)
    nxt = next((g for g in sorted(p.gates, key=lambda g: g.days, reverse=True) if g.date(p.opening) >= p.as_of), None)
    return {"days_to_opening": (p.opening - p.as_of).days, "ready": ready,
            "margin": (p.opening - timedelta(days=1) - ready).days, "progress": overall(p),
            "tasks": len(p.tasks), "done": sum(t.status == "done" for t in p.tasks),
            "blocked": sum(t.status == "blocked" for t in p.tasks), "next_gate": nxt,
            "critical": sum(f.severity == CRITICAL for f in findings), "warning": sum(f.severity == WARNING for f in findings),
            "info": sum(f.severity == INFO for f in findings)}


def write_findings(findings: list[Finding], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["severity", "area", "code", "ref", "subject", "owner", "due", "detail", "next_step"])
        for f in findings:
            w.writerow([f.severity, f.area, f.code, f.ref, f.subject, f.owner, f.due or "", f.detail, f.fix])


def write_actions(p: Project, slots: dict[str, Slot], path: Path) -> int:
    """Open tasks in forecast order with dates and float: the list for the weekly meeting."""
    cp = {s.task.id for s in critical_path(p, slots)}
    rows = sorted([s for s in slots.values() if not s.done], key=lambda s: (s.float_days > 0, s.start, s.finish))
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "workstream", "task", "owner", "vendor", "status", "percent", "forecast_start", "forecast_finish",
                    "gate", "gate_date", "float_days", "critical_path", "note"])
        for s in rows:
            t = s.task
            w.writerow([t.id, t.workstream, t.task, t.owner, t.vendor, t.status, f"{t.percent:.0f}", s.start, s.finish,
                        t.gate, s.deadline, s.float_days, "yes" if t.id in cp else "", t.note])
    return len(rows)


def review_md(p: Project, slots: dict[str, Slot], findings: list[Finding]) -> str:
    sm, st = summary(p, slots, findings), area_status(findings)
    margin = (f"{sm['margin']} days of margin" if sm["margin"] >= 0 else f"{-sm['margin']} days LATE")
    lines = [f"# IT pre-opening review · {p.property} · {p.as_of:%Y-%m-%d}", "",
             f"Opening {p.opening:%a %d %b %Y} ({sm['days_to_opening']} days) · IT forecast ready {d(sm['ready'])} "
             f"({margin}) · {sm['progress']:.0%} of the work done · {sm['done']} of {sm['tasks']} tasks finished, "
             f"{sm['blocked']} blocked.", "", "| Area | Status |", "|---|---|"]
    lines += [f"| {a} | {'OK' if st[a] == 'ok' else st[a].upper()} |" for a in AREAS]
    for sev, title in ((CRITICAL, "Act now"), (WARNING, "This week")):
        items = [f for f in findings if f.severity == sev]
        if items:
            lines += ["", f"## {title}", ""]
            lines += [f"- **{f.subject}**{' · ' + f.owner if f.owner else ''}: {f.detail}  \n  Next step: {f.fix}" for f in items]
    lines += ["", "## Critical path to the ready date", "", "| Task | Owner | Forecast | Gate | Float |", "|---|---|---|---|---|"]
    for s in critical_path(p, slots):
        lines.append(f"| {s.task.id} · {s.task.task} | {s.task.owner or '?'} | {d(s.start)} – {d(s.finish)} | "
                     f"{s.task.gate} ({d(s.deadline)}) | {s.float_days} |")
    lines += ["", "## Gates", "", "| Gate | Date | Tasks | Done | Forecast late |", "|---|---|---|---|---|"]
    for g in p.gates:
        items = [s for s in slots.values() if s.task.gate == g.code]
        lines.append(f"| {g.code} · {g.name} | {g.date(p.opening):%Y-%m-%d} | {len(items)} | "
                     f"{sum(s.done for s in items)} | {sum(s.late for s in items)} |")
    lines += ["", "## Readiness by workstream", "", "| Workstream | Done |", "|---|---|"]
    lines += [f"| {w} | {v:.0%} |" for w, v in readiness(p).items()]
    infos = [f for f in findings if f.severity == INFO]
    if infos:
        lines += ["", "## Watch", ""] + [f"- {f.subject}: {f.detail}" for f in infos]
    lines += ["", "Task list with dates and float: `actions.csv` · go-live checklist: `golive_checklist.md`.", ""]
    return "\n".join(lines)


DAY_ONE = [
    ("T-7", "Network and Wi-Fi", "Failover test: unplug the main internet line and confirm PMS, card payments and guest Wi-Fi keep working."),
    ("T-7", "PMS and distribution", "Rates, packages and taxes checked on three sample bookings from each channel."),
    ("T-7", "POS and payments", "Every card terminal: sale, refund and end-of-day close; tips and room charge from each outlet."),
    ("T-7", "Door locks", "Encode, re-issue and cancel keys at every encoder; master and emergency keys signed out and logged."),
    ("T-7", "Training and go-live", "Escalation list printed at front office, back office and outlets: vendor, phone, hours, contract reference."),
    ("T-1", "PMS and distribution", "Arrivals for opening day loaded, rooms assigned, keys pre-encoded for groups."),
    ("T-1", "POS and payments", "Menus and prices final; printers and kitchen screens routed per outlet; float in the cash recyclers."),
    ("T-1", "TV and guest entertainment", "Welcome screen shows the guest name on three test rooms; channel line-up complete."),
    ("T-1", "Security and data protection", "Backups ran and a restore was tested; admin accounts have MFA; vendor remote access only on request."),
    ("T-1", "Back office", "Every member of staff has logged in once: email, PMS user, POS card or PIN."),
    ("Opening day", "Training and go-live", "IT and vendor engineers on site from the first check-in to the night audit."),
    ("Opening day", "PMS and distribution", "First check-in, room move and check-out done end to end; folio shows POS, phone and minibar charges."),
    ("Opening day", "Network and Wi-Fi", "Guest Wi-Fi login with room number and surname tested by a guest, not by IT."),
    ("Opening day", "PMS and distribution", "Night audit and end-of-day reports run; interface queues empty."),
    ("First week", "Training and go-live", "Daily 15-minute stand-up with heads of department: issues, owner, fixed by."),
    ("First week", "Training and go-live", "Issue log reviewed with each vendor; anything open after five days goes to the account manager."),
    ("First week", "Security and data protection", "Remove temporary accounts, installer passwords and test cards; record final configurations."),
]


def golive_md(p: Project, slots: dict[str, Slot]) -> str:
    lines = [f"# Go-live checklist · {p.property}", "", f"Opening {p.opening:%a %d %b %Y}. Tick each line and write who checked it.", ""]
    late_gates = [g for g in p.gates if g.days <= 14]
    lines += ["## Sign-offs from the plan", ""]
    for g in late_gates:
        items = [s for s in slots.values() if s.task.gate == g.code]
        if items:
            lines.append(f"**{g.code} · {g.name} ({g.date(p.opening):%Y-%m-%d})**")
            lines += [f"- [ ] {s.task.id} · {s.task.task} ({s.task.owner or 'owner?'})" + (" — done" if s.done else "") for s in items]
            lines.append("")
    streams = {t.workstream for t in p.tasks}
    for when in ("T-7", "T-1", "Opening day", "First week"):
        items = [(w, x) for (k, w, x) in DAY_ONE if k == when and (w in streams or w == "Training and go-live")]
        if items:
            lines += [f"## {when}", ""] + [f"- [ ] {x} *({w})*" for w, x in items] + [""]
    return "\n".join(lines)


CSS = """
:root{--bg:#f6f7f8;--card:#fff;--ink:#1b2128;--muted:#66717c;--line:#e2e5e9;--ok:#1e7a4c;--warn:#a46200;--bad:#b42318;--info:#0b6bcb;--bar:#5b8def;--done:#c9ced4}
@media (prefers-color-scheme:dark){:root{--bg:#13171b;--card:#1b2127;--ink:#e7eaee;--muted:#9aa5b0;--line:#2b333b;--ok:#4cc38a;--warn:#f0a83a;--bad:#f2685c;--info:#5aa9f0;--bar:#5b8def;--done:#3a434c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1180px;margin:0 auto;padding:28px 18px 60px}h1{font-size:26px;margin:0 0 4px}h2{font-size:18px;margin:34px 0 12px}
.muted{color:var(--muted)}.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:20px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}.tile b{display:block;font-size:26px}
.areas{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.area{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--ok);border-radius:10px;padding:10px 14px}
.area.critical{border-left-color:var(--bad)}.area.warning{border-left-color:var(--warn)}.area.info{border-left-color:var(--info)}
.area .lbl{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-bottom:4px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
tr:last-child td{border-bottom:0}.wrap{overflow-x:auto}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.pill{display:inline-block;white-space:nowrap;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:600;border:1px solid currentColor}
.critical{color:var(--bad)}.warning{color:var(--warn)}.info{color:var(--info)}.ok{color:var(--ok)}
.area.critical,.area.warning,.area.info,.area.ok{color:inherit}
.bar{display:inline-block;vertical-align:middle;height:10px;width:180px;background:var(--line);border-radius:5px;overflow:hidden;margin-right:8px}.bar i{display:block;height:100%;background:var(--ok)}
.gantt{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;overflow-x:auto}
.gantt svg{display:block;font:12px system-ui,-apple-system,Segoe UI,sans-serif}
.g-lbl{fill:var(--ink)}.g-ws{fill:var(--muted);font-weight:700;text-transform:uppercase;letter-spacing:.04em;font-size:11px}
.g-grid{stroke:var(--line)}.g-today{stroke:var(--info);stroke-width:2}.g-gate{stroke:var(--muted);stroke-dasharray:4 3}
.g-open{stroke:var(--bad);stroke-width:2}.g-txt{fill:var(--muted);font-size:11px}
.b-norm{fill:var(--bar)}.b-cp{fill:var(--bad)}.b-late{fill:var(--warn)}.b-blocked{fill:var(--muted)}.b-done{fill:var(--done)}
.legend span{display:inline-flex;align-items:center;gap:6px;margin-right:16px;font-size:13px}.legend i{width:14px;height:10px;border-radius:2px;display:inline-block}
.matrix{display:grid;grid-template-columns:28px repeat(5,minmax(0,1fr));gap:3px;max-width:520px}
.matrix div{min-height:46px;border-radius:6px;padding:3px 5px;font-size:12px;background:var(--line)}.matrix .ax{background:none;color:var(--muted);text-align:center}
.matrix .h3{background:rgba(180,35,24,.22)}.matrix .h2{background:rgba(164,98,0,.20)}.matrix .h1{background:rgba(30,122,76,.16)}
td.nw{white-space:nowrap}td.fix{font-size:13px;color:var(--muted);max-width:380px}footer{margin-top:40px;font-size:13px}
"""


def _pill(s: str) -> str:
    return f"<span class='pill {s}'>{'OK' if s == 'ok' else s.upper()}</span>"


def gantt_svg(p: Project, slots: dict[str, Slot]) -> str:
    cp = {s.task.id for s in critical_path(p, slots)}
    start = p.as_of - timedelta(days=7)
    end = max(p.opening + timedelta(days=3), max((s.finish for s in slots.values() if s.finish), default=p.opening) + timedelta(days=3))
    days = (end - start).days
    lw, pxd, rh, top = 300, max(5.0, 760 / days), 20, 34
    x = lambda dt: lw + (dt - start).days * pxd
    groups = {}
    for t in p.tasks:
        groups.setdefault(t.workstream, []).append(slots[t.id])
    rows = []
    for ws, items in groups.items():
        rows.append(("ws", ws, None))
        rows += [("t", None, s) for s in sorted(items, key=lambda s: (not s.done, s.start or date.min))]
    w, h = lw + days * pxd + 60, top + len(rows) * rh + 10
    out = [f"<svg width='{w:.0f}' height='{h:.0f}' viewBox='0 0 {w:.0f} {h:.0f}' role='img' aria-label='Gantt chart'>"]
    m = date(start.year, start.month, 1)
    while m <= end:
        if m >= start:
            out.append(f"<line class='g-grid' x1='{x(m):.1f}' y1='{top - 8}' x2='{x(m):.1f}' y2='{h}'/>"
                       f"<text class='g-txt' x='{x(m) + 3:.1f}' y='{top - 12}'>{m:%b %Y}</text>")
        m = date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    for g in p.gates:
        gx = x(g.date(p.opening))
        if lw <= gx <= w:
            out.append(f"<line class='g-gate' x1='{gx:.1f}' y1='{top - 4}' x2='{gx:.1f}' y2='{h}'/>"
                       f"<text class='g-txt' x='{gx + 2:.1f}' y='{top - 1}'>{e(g.code)}</text>")
    out.append(f"<line class='g-today' x1='{x(p.as_of):.1f}' y1='{top - 22}' x2='{x(p.as_of):.1f}' y2='{h}'/>"
               f"<text class='g-txt' x='{x(p.as_of) + 3:.1f}' y='{top - 24}'>today</text>"
               f"<line class='g-open' x1='{x(p.opening):.1f}' y1='{top - 22}' x2='{x(p.opening):.1f}' y2='{h}'/>"
               f"<text class='g-txt' x='{x(p.opening) + 3:.1f}' y='{top - 24}'>opening</text>")
    y = top
    for kind, ws, s in rows:
        if kind == "ws":
            out.append(f"<text class='g-ws' x='4' y='{y + 14}'>{e(ws)}</text>")
        else:
            t = s.task
            label = f"{t.id} · {t.task}"
            label = label if len(label) <= 42 else label[:41] + "…"
            out.append(f"<text class='g-lbl' x='12' y='{y + 14}'><title>{e(t.task)}</title>{e(label)}</text>")
            if s.done:
                out.append(f"<text class='g-txt' x='{x(p.as_of) - 6:.1f}' y='{y + 14}' text-anchor='end'>done ✓</text>")
            else:
                cls = "b-blocked" if t.status == "blocked" else "b-cp" if t.id in cp else "b-late" if s.late else "b-norm"
                bx = x(s.start)
                bw = max(pxd, (s.finish - s.start).days * pxd + pxd)
                out.append(f"<rect class='{cls}' x='{bx:.1f}' y='{y + 4}' width='{bw:.1f}' height='12' rx='3'>"
                           f"<title>{e(t.task)}: {s.start} – {s.finish}, float {s.float_days} days</title></rect>")
        y += rh
    out.append("</svg>")
    return "".join(out)


def render_html(p: Project, slots: dict[str, Slot], findings: list[Finding], title: str) -> str:
    sm, st = summary(p, slots, findings), area_status(findings)
    margin_cls = "critical" if sm["margin"] < 0 else "warning" if sm["margin"] < 5 else "ok"
    nxt = sm["next_gate"]
    h = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
         f"<title>{e(title)}</title><style>{CSS}</style></head><body><main>",
         f"<h1>{e(title)}</h1><p class='muted'>{e(p.property)}"
         + (f" · {p.rooms} rooms" if p.rooms else "") + (f" · {', '.join(map(e, p.outlets))}" if p.outlets else "")
         + f" · review of {p.as_of:%d %b %Y}</p><div class='tiles'>"]
    tiles = [("Opening", f"{sm['days_to_opening']} days", f"{p.opening:%a %d %b %Y}", ""),
             ("IT ready (forecast)", f"{sm['ready']:%d %b}", (f"{sm['margin']} days of margin" if sm["margin"] >= 0 else f"{-sm['margin']} days late"), margin_cls),
             ("Work done", f"{sm['progress']:.0%}", f"{sm['done']} of {sm['tasks']} tasks · {sm['blocked']} blocked", ""),
             ("Next gate", nxt.code if nxt else "–", f"{nxt.name} · {nxt.date(p.opening):%d %b}" if nxt else "", ""),
             ("Critical", str(sm["critical"]), f"{sm['warning']} warnings · {sm['info']} to watch", "")]
    h += [f"<div class='tile'><span class='muted'>{e(a)}</span><b class='{c}'>{e(b)}</b><span class='muted'>{e(x)}</span></div>"
          for a, b, x, c in tiles]
    h.append("</div><h2>Status by area</h2><div class='areas'>")
    h += [f"<div class='area {st[a]}'><span class='lbl'>{e(a)}</span>{_pill(st[a])}</div>" for a in AREAS]
    h.append("</div><h2>Plan</h2><div class='gantt'>" + gantt_svg(p, slots) + "</div>"
             "<p class='legend muted'><span><i class='b-cp' style='background:var(--bad)'></i>critical path to the ready date</span>"
             "<span><i style='background:var(--warn)'></i>late for its gate</span><span><i style='background:var(--muted)'></i>blocked</span>"
             "<span><i style='background:var(--bar)'></i>on time</span></p>")
    act = [f for f in findings if f.severity in (CRITICAL, WARNING)]
    if act:
        h.append("<h2>To act on</h2><div class='wrap'><table><tr><th>Severity</th><th>Subject</th><th>What</th><th>Next step</th><th>Owner</th></tr>")
        h += [f"<tr><td>{_pill(f.severity)}</td><td><b>{e(f.subject)}</b><br><span class='muted'>{e(f.area)}</span></td>"
              f"<td>{e(f.detail)}</td><td class='fix'>{e(f.fix)}</td><td class='nw'>{e(f.owner or '—')}</td></tr>" for f in act]
        h.append("</table></div>")
    h.append("<h2>Gates</h2><div class='wrap'><table><tr><th>Gate</th><th>Date</th><th class='num'>Tasks</th><th class='num'>Done</th>"
             "<th class='num'>Forecast late</th><th>Status</th></tr>")
    for g in p.gates:
        items = [s for s in slots.values() if s.task.gate == g.code]
        late = sum(s.late for s in items)
        missed = g.date(p.opening) < p.as_of and any(not s.done for s in items)
        status = "critical" if missed else "warning" if late else "ok"
        h.append(f"<tr><td>{e(g.code)} · {e(g.name)}</td><td class='nw'>{g.date(p.opening):%a %d %b %Y}</td><td class='num'>{len(items)}</td>"
                 f"<td class='num'>{sum(s.done for s in items)}</td><td class='num'>{late}</td><td>{_pill(status)}</td></tr>")
    h.append("</table></div><h2>Readiness by workstream</h2><div class='wrap'><table>")
    for wsn, v in readiness(p).items():
        h.append(f"<tr><td>{e(wsn)}</td><td><span class='bar'><i style='width:{v * 100:.0f}%'></i></span>{v:.0%}</td></tr>")
    h.append("</table></div>")
    open_risks = [r for r in p.risks if r.status not in {"closed", "done"}]
    if open_risks:
        h.append("<h2>Risks</h2><div class='matrix'>")
        for imp in range(5, 0, -1):
            h.append(f"<div class='ax'>{imp}</div>")
            for lik in range(1, 6):
                sc = imp * lik
                cls = "h3" if sc >= 15 else "h2" if sc >= 8 else "h1"
                ids = " ".join(r.id for r in open_risks if r.impact == imp and r.likelihood == lik)
                h.append(f"<div class='{cls}'><b>{e(ids)}</b></div>")
        h.append("<div class='ax'></div>" + "".join(f"<div class='ax'>{i}</div>" for i in range(1, 6)))
        h.append("</div><p class='muted'>Impact (rows) by likelihood (columns).</p><div class='wrap'><table><tr><th>Risk</th>"
                 "<th class='num'>Score</th><th>Mitigation</th><th>Owner</th></tr>")
        h += [f"<tr><td>{e(r.id)} · {e(r.risk)}</td><td class='num'>{r.score}</td><td class='fix'>{e(r.mitigation) or '<span class=warning>none</span>'}</td>"
              f"<td class='nw'>{e(r.owner)}</td></tr>" for r in sorted(open_risks, key=lambda r: -r.score)]
        h.append("</table></div>")
    h.append("<footer class='muted'>Generated by preopen from the project plan. Fictional demo data unless you ran it on your own files.</footer></main></body></html>")
    return "".join(h)
