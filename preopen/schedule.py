"""Forward and backward pass over the task network: forecast dates, float, critical path and forecast ready date.

Calendar days, starting from the review date. Finished tasks take no time. Each task must end by its gate date
(opening minus the gate's days); a task without a gate must end the day before opening."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .model import Project, Task


class CycleError(ValueError):
    pass


@dataclass
class Slot:
    task: Task
    start: date | None      # None for finished tasks
    finish: date | None
    deadline: date
    late_start: date | None
    late_finish: date | None
    float_days: int         # late_finish - finish: negative means it cannot meet its gate (or a successor's)
    chain_finish: date | None   # latest forecast finish of this task and everything that depends on it

    @property
    def done(self) -> bool:
        return self.task.status == "done"

    @property
    def critical(self) -> bool:
        return not self.done and self.float_days <= 0

    @property
    def late(self) -> bool:
        return not self.done and self.finish is not None and self.finish > self.deadline


def order(project: Project) -> list[Task]:
    """Tasks in dependency order. Unknown dependencies are ignored here (reported as data quality)."""
    ids = {t.id: t for t in project.tasks}
    state, out = {}, []

    def visit(t: Task, path: list[str]) -> None:
        if state.get(t.id) == 2:
            return
        if state.get(t.id) == 1:
            raise CycleError("dependency loop: " + " -> ".join(path + [t.id]))
        state[t.id] = 1
        for d in t.depends_on:
            if d in ids:
                visit(ids[d], path + [t.id])
        state[t.id] = 2
        out.append(t)

    for t in project.tasks:
        visit(t, [])
    return out


def successors(project: Project) -> dict[str, list[str]]:
    succ = {t.id: [] for t in project.tasks}
    for t in project.tasks:
        for d in t.depends_on:
            if d in succ:
                succ[d].append(t.id)
    return succ


def plan(project: Project) -> dict[str, Slot]:
    seq = order(project)
    succ = successors(project)
    day = timedelta(days=1)
    t0 = project.as_of
    es, ef = {}, {}
    for t in seq:
        if t.status == "done":
            es[t.id] = ef[t.id] = None
            continue
        ready = [ef[d] for d in t.depends_on if ef.get(d)]
        start = max([t0] + [f + day for f in ready])
        es[t.id], ef[t.id] = start, start + timedelta(days=t.remaining - 1)
    lf, ls = {}, {}
    for t in reversed(seq):
        bound = project.deadline(t)
        for s in succ[t.id]:
            if ls.get(s):
                bound = min(bound, ls[s] - day)
        lf[t.id] = bound
        ls[t.id] = bound - timedelta(days=t.remaining - 1) if t.status != "done" else None
    chain = {}
    for t in reversed(seq):
        ends = [ef[t.id]] if ef[t.id] else []
        ends += [chain[s] for s in succ[t.id] if chain.get(s)]
        chain[t.id] = max(ends) if ends else None
    out = {}
    for t in project.tasks:
        fl = (lf[t.id] - ef[t.id]).days if ef[t.id] else 0
        out[t.id] = Slot(t, es[t.id], ef[t.id], project.deadline(t), ls[t.id], lf[t.id], fl, chain[t.id])
    return out


def ready_date(project: Project, slots: dict[str, Slot]) -> date:
    """The day everything is forecast to be finished (the review date if it already is)."""
    ends = [s.finish for s in slots.values() if s.finish]
    return max(ends) if ends else project.as_of


def critical_path(project: Project, slots: dict[str, Slot]) -> list[Slot]:
    """The driving chain to the forecast ready date: from the last task to finish, walk back through the
    predecessor that finishes the day before each task starts. Delay any of them and the ready date moves."""
    open_ = [s for s in slots.values() if s.finish]
    if not open_:
        return []
    last = max(open_, key=lambda s: (s.finish, -s.float_days))
    chain, cur = [last], last
    while True:
        prev = [slots[d] for d in cur.task.depends_on
                if d in slots and slots[d].finish and slots[d].finish + timedelta(days=1) == cur.start]
        if not prev:
            break
        cur = min(prev, key=lambda s: s.float_days)
        chain.append(cur)
    return list(reversed(chain))


def readiness(project: Project) -> dict[str, float]:
    """Share of work done per workstream, weighted by duration."""
    tot, done = {}, {}
    for t in project.tasks:
        tot[t.workstream] = tot.get(t.workstream, 0) + t.duration
        got = t.duration if t.status == "done" else t.duration * min(max(t.percent, 0), 100) / 100
        done[t.workstream] = done.get(t.workstream, 0) + got
    return {w: done[w] / tot[w] if tot[w] else 1.0 for w in tot}


def overall(project: Project) -> float:
    tot = sum(t.duration for t in project.tasks)
    got = sum(t.duration if t.status == "done" else t.duration * min(max(t.percent, 0), 100) / 100 for t in project.tasks)
    return got / tot if tot else 1.0
