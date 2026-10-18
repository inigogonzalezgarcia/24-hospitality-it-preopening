"""Findings for the weekly pre-opening meeting: opening at risk, gates, late and blocked work, lead times, risks and
data quality."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .model import Project
from .schedule import Slot, plan, ready_date

CRITICAL, WARNING, INFO = "critical", "warning", "info"
SEV_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}
AREAS = ["Opening date", "Gates", "Tasks", "Lead times", "Risks", "Data quality"]


@dataclass
class Config:
    start_soon_days: int = 7      # a not-started task whose latest start is within this many days
    risk_high: int = 15           # likelihood x impact (1-5 each)
    risk_watch: int = 10


@dataclass
class Finding:
    severity: str
    area: str
    code: str
    ref: str
    subject: str
    detail: str
    fix: str
    owner: str = ""
    due: date | None = None


def d(x: date | None) -> str:
    return f"{x:%a %d %b}" if x else "?"


def check_opening(p: Project, slots: dict[str, Slot]) -> list[Finding]:
    ready = ready_date(p, slots)
    must = p.opening - timedelta(days=1)
    if ready > must:
        late = (ready - must).days
        drivers = [s for s in slots.values() if not s.done and s.finish == ready]
        return [Finding(CRITICAL, "Opening date", "OPENING_AT_RISK", "opening", p.property,
                        f"On the current plan IT is ready on {d(ready)}, {late} days after the day before opening "
                        f"({d(must)}). Last task: {', '.join(s.task.task for s in drivers)}.",
                        "Work the critical path: shorten or overlap tasks, add a temporary workaround, or agree "
                        "which services open later (and how guests are served meanwhile).", due=must)]
    return []


def check_gates(p: Project, slots: dict[str, Slot]) -> list[Finding]:
    out = []
    for g in p.gates:
        gd = g.date(p.opening)
        items = [s for s in slots.values() if s.task.gate == g.code]
        open_ = [s for s in items if not s.done]
        if not items:
            continue
        if gd < p.as_of and open_:
            out.append(Finding(CRITICAL, "Gates", "GATE_MISSED", g.code, f"{g.code} · {g.name}",
                               f"Gate date {d(gd)} has passed with {len(open_)} of {len(items)} tasks still open: "
                               + "; ".join(f"{s.task.id} {s.task.task}" for s in open_) + ".",
                               ("Close it this week or move it" if len(open_) == 1 else "Close them this week or move them")
                               + " to a later gate on purpose, and check what depends on it.",
                               due=gd))
        elif gd >= p.as_of:
            late = [s for s in open_ if s.late]
            if late:
                sev = WARNING
                out.append(Finding(sev, "Gates", "GATE_AT_RISK", g.code, f"{g.code} · {g.name}",
                                   f"{len(late)} of {len(items)} tasks {'is' if len(late) == 1 else 'are'} forecast to finish after the gate date "
                                   f"({d(gd)}): " + "; ".join(f"{s.task.id} ({d(s.finish)})" for s in late) + ".",
                                   "Agree recovery dates with the owners and vendors before the gate review.", due=gd))
    return out


def check_tasks(p: Project, slots: dict[str, Slot]) -> list[Finding]:
    out, must = [], p.opening - timedelta(days=1)
    for s in sorted(slots.values(), key=lambda s: (s.finish or date.min)):
        t = s.task
        if s.done:
            continue
        threatens = s.chain_finish is not None and s.chain_finish > must
        if t.status == "blocked":
            out.append(Finding(CRITICAL if s.critical or threatens else WARNING, "Tasks", "BLOCKED", t.id,
                               f"{t.id} · {t.task}",
                               f"Blocked{': ' + t.note if t.note else ''}. Forecast if unblocked today: {d(s.finish)} "
                               f"(gate {t.gate or 'opening'}: {d(s.deadline)}, float {s.float_days} days).",
                               f"Escalate to {t.vendor or 'the vendor'} with a date to unblock; until then plan the work around it.",
                               t.owner, s.late_start))
        elif s.late:
            out.append(Finding(CRITICAL if threatens else WARNING, "Tasks", "LATE", t.id, f"{t.id} · {t.task}",
                               f"Forecast to finish {d(s.finish)}, {(s.finish - s.deadline).days} days after its gate "
                               f"{t.gate or 'opening'} ({d(s.deadline)})" + (", and it delays the opening chain." if threatens else "."),
                               "Ask the owner for a recovery plan: more people, overlap with the next task or a temporary workaround.",
                               t.owner, s.deadline))
        elif s.critical:
            out.append(Finding(INFO, "Tasks", "NO_FLOAT", t.id, f"{t.id} · {t.task}",
                               f"On time but with no float: any day lost here moves {t.gate or 'the opening'}.",
                               "Watch it daily and confirm the vendor's dates in writing.", t.owner, s.finish))
    return out


def check_lead_times(p: Project, slots: dict[str, Slot], c: Config) -> list[Finding]:
    out = []
    for s in slots.values():
        t = s.task
        if t.status != "todo" or not s.late_start:
            continue
        if s.late_start <= p.as_of + timedelta(days=c.start_soon_days):
            when = "should already have started" if s.late_start < p.as_of else f"must start by {d(s.late_start)}"
            out.append(Finding(WARNING, "Lead times", "START_NOW", t.id, f"{t.id} · {t.task}",
                               f"Not started and {when} to meet {t.gate or 'the opening'} ({t.duration} days of work"
                               f"{', vendor ' + t.vendor if t.vendor else ''}).",
                               "Confirm the order or purchase order this week and get a delivery date in writing.",
                               t.owner, s.late_start))
    return out


def check_risks(p: Project, c: Config) -> list[Finding]:
    out = []
    for r in p.risks:
        if r.status in {"closed", "done"}:
            continue
        if not r.mitigation.strip():
            out.append(Finding(WARNING if r.score >= c.risk_watch else INFO, "Risks", "NO_MITIGATION", r.id,
                               f"{r.id} · {r.risk}", f"Score {r.score} ({r.likelihood}×{r.impact}) with no mitigation.",
                               "Write the mitigation and the trigger that activates it.", r.owner))
        elif r.score >= c.risk_high:
            out.append(Finding(WARNING, "Risks", "HIGH_RISK", r.id, f"{r.id} · {r.risk}",
                               f"Score {r.score} ({r.likelihood}×{r.impact}). Mitigation: {r.mitigation}",
                               "Check the mitigation is ready to use, not just written, and review it every week.", r.owner))
    return out


def check_data(p: Project) -> list[Finding]:
    out, ids, gates = [], {t.id for t in p.tasks}, {g.code for g in p.gates}
    for t in p.tasks:
        if not t.owner and t.status != "done":
            out.append(Finding(WARNING, "Data quality", "NO_OWNER", t.id, f"{t.id} · {t.task}", "No owner.",
                               "Name one person who reports progress on it every week."))
        missing = [x for x in t.depends_on if x not in ids]
        if missing:
            out.append(Finding(WARNING, "Data quality", "UNKNOWN_DEPENDENCY", t.id, f"{t.id} · {t.task}",
                               f"Depends on {', '.join(missing)}, which is not in the plan.",
                               "Fix the ID or add the missing task.", t.owner))
        if t.gate and t.gate not in gates:
            out.append(Finding(WARNING, "Data quality", "UNKNOWN_GATE", t.id, f"{t.id} · {t.task}",
                               f"Gate {t.gate} is not defined in project.json; the day before opening is used.",
                               "Use one of: " + ", ".join(g.code for g in p.gates) + ".", t.owner))
    return out


def run_all(p: Project, c: Config | None = None, slots: dict[str, Slot] | None = None) -> list[Finding]:
    c = c or Config()
    slots = slots or plan(p)
    fs = (check_opening(p, slots) + check_gates(p, slots) + check_tasks(p, slots) + check_lead_times(p, slots, c)
          + check_risks(p, c) + check_data(p))
    return sorted(fs, key=lambda f: (SEV_ORDER[f.severity], AREAS.index(f.area), f.due or date.max))


def area_status(findings: list[Finding]) -> dict[str, str]:
    st = {a: "ok" for a in AREAS}
    for f in findings:
        if st[f.area] == "ok" or SEV_ORDER[f.severity] < SEV_ORDER.get(st[f.area], 9):
            st[f.area] = f.severity
    return st
