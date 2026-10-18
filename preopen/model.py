"""Data model and loaders: project.json, tasks.csv and risks.csv (see docs/data-format.md)."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

STATUSES = ("todo", "in_progress", "blocked", "done")


def parse_date(value) -> date | None:
    value = (str(value) if value is not None else "").strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def parse_num(value, default=0.0) -> float:
    value = (str(value) if value is not None else "").strip().replace(",", ".").rstrip("%")
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class Gate:
    code: str          # "T-30"
    name: str
    days: int          # days before opening

    def date(self, opening: date) -> date:
        return opening - timedelta(days=self.days)


@dataclass
class Task:
    id: str
    workstream: str
    task: str
    owner: str = ""
    vendor: str = ""
    duration: int = 1                 # calendar days of work left at 0 %
    depends_on: list[str] = field(default_factory=list)
    gate: str = ""                    # gate code the task must be finished by
    status: str = "todo"
    percent: float = 0.0
    note: str = ""

    @property
    def remaining(self) -> int:
        if self.status == "done":
            return 0
        left = round(self.duration * (1 - min(max(self.percent, 0), 100) / 100), 6)
        return max(1, int(-(-left // 1))) if left > 0 else 1


@dataclass
class Risk:
    id: str
    risk: str
    workstream: str = ""
    likelihood: int = 1
    impact: int = 1
    owner: str = ""
    mitigation: str = ""
    status: str = "open"

    @property
    def score(self) -> int:
        return self.likelihood * self.impact


DEFAULT_GATES = [Gate("T-90", "Design frozen", 90), Gate("T-60", "Infrastructure ready", 60),
                 Gate("T-30", "Systems installed", 30), Gate("T-14", "Integrations tested", 14),
                 Gate("T-7", "People trained", 7), Gate("T-1", "Ready to open", 1)]


@dataclass
class Project:
    property: str
    opening: date
    as_of: date
    tasks: list[Task]
    risks: list[Risk] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=lambda: list(DEFAULT_GATES))
    rooms: int | None = None
    outlets: list[str] = field(default_factory=list)

    def gate(self, code: str) -> Gate | None:
        return next((g for g in self.gates if g.code == code), None)

    def deadline(self, t: Task) -> date:
        g = self.gate(t.gate)
        return g.date(self.opening) if g else self.opening - timedelta(days=1)

    def task(self, tid: str) -> Task | None:
        return next((t for t in self.tasks if t.id == tid), None)


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(2048)
        fh.seek(0)
        delim = ";" if sample.count(";") > sample.count(",") else ","
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(fh, delimiter=delim)]


def norm_status(value: str, percent: float) -> str:
    v = value.strip().lower().replace(" ", "_").replace("-", "_")
    v = {"in_progress": "in_progress", "doing": "in_progress", "started": "in_progress", "wip": "in_progress",
         "complete": "done", "completed": "done", "closed": "done", "hecho": "done", "bloqueado": "blocked",
         "pendiente": "todo", "en_curso": "in_progress", "en_progreso": "in_progress", "not_started": "todo", "": "todo"}.get(v, v)
    if v not in STATUSES:
        v = "todo"
    if v == "todo" and percent >= 100:
        v = "done"
    return v


def load_tasks(path: Path) -> list[Task]:
    out = []
    for r in _rows(path):
        if not r.get("id") or not r.get("task"):
            continue
        pct = parse_num(r.get("percent"))
        out.append(Task(id=r["id"], workstream=r.get("workstream", "Other") or "Other", task=r["task"],
                        owner=r.get("owner", ""), vendor=r.get("vendor", ""),
                        duration=max(1, int(parse_num(r.get("duration_days"), 1))),
                        depends_on=[d for d in re.split(r"[;,\s]+", r.get("depends_on", "")) if d],
                        gate=r.get("gate", "").upper().replace(" ", ""), status=norm_status(r.get("status", ""), pct),
                        percent=100.0 if norm_status(r.get("status", ""), pct) == "done" else pct, note=r.get("note", "")))
    return out


def load_risks(path: Path) -> list[Risk]:
    return [Risk(r["id"], r.get("risk", ""), r.get("workstream", ""), int(parse_num(r.get("likelihood"), 1)),
                 int(parse_num(r.get("impact"), 1)), r.get("owner", ""), r.get("mitigation", ""),
                 (r.get("status") or "open").lower()) for r in _rows(path) if r.get("id")]


def load(data: Path, as_of: date | None = None) -> Project:
    data = Path(data)
    meta = json.loads((data / "project.json").read_text(encoding="utf-8"))
    opening = parse_date(meta.get("opening_date"))
    if not opening:
        raise ValueError("project.json needs opening_date (YYYY-MM-DD)")
    gates = [Gate(g["code"].upper().replace(" ", ""), g.get("name", g["code"]), int(g["days_before_opening"]))
             for g in meta.get("gates", [])] or list(DEFAULT_GATES)
    return Project(property=meta.get("property", "New property"), opening=opening,
                   as_of=as_of or parse_date(meta.get("as_of")) or date.today(),
                   tasks=load_tasks(data / "tasks.csv"), risks=load_risks(data / "risks.csv"),
                   gates=sorted(gates, key=lambda g: -g.days), rooms=meta.get("rooms"), outlets=meta.get("outlets", []))
