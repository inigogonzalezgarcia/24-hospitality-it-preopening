"""Tests for preopen. Run: python -m unittest discover tests"""
import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from preopen import cli, report
from preopen.checks import (Config, check_data, check_gates, check_lead_times, check_opening, check_risks,
                            check_tasks, run_all)
from preopen.model import Gate, Project, Risk, Task, load, norm_status
from preopen.schedule import CycleError, critical_path, order, overall, plan, readiness, ready_date

T0 = date(2026, 10, 18)
OPEN = date(2027, 1, 15)


def proj(*tasks, risks=(), as_of=T0, opening=OPEN):
    return Project("Test hotel", opening, as_of, list(tasks), list(risks))


def t(tid, dur=5, deps="", gate="T-1", status="todo", pct=0, owner="Ana", **kw):
    return Task(tid, kw.pop("ws", "Network"), f"Task {tid}", owner, kw.pop("vendor", ""), dur,
                [x for x in deps.split(";") if x], gate, status, pct, kw.pop("note", ""))


class Model(unittest.TestCase):
    def test_remaining_work_rounds_up_and_done_is_zero(self):
        self.assertEqual(t("A", 10, pct=70).remaining, 3)
        self.assertEqual(t("A", 10, pct=75).remaining, 3)      # 2.5 -> 3
        self.assertEqual(t("A", 10, status="done", pct=100).remaining, 0)
        self.assertEqual(t("A", 10, pct=100).remaining, 1)     # 100% but not marked done: one day to close it

    def test_status_aliases(self):
        self.assertEqual(norm_status("In progress", 0), "in_progress")
        self.assertEqual(norm_status("Completed", 0), "done")
        self.assertEqual(norm_status("", 100), "done")
        self.assertEqual(norm_status("bloqueado", 0), "blocked")
        self.assertEqual(norm_status("En curso", 40), "in_progress")
        self.assertEqual(norm_status("weird", 0), "todo")


class Schedule(unittest.TestCase):
    def test_forward_pass_follows_dependencies(self):
        p = proj(t("A", 5), t("B", 3, "A"), t("C", 2, "A;B"), t("D", 4, status="done", pct=100), t("E", 2, "D"))
        s = plan(p)
        self.assertEqual((s["A"].start, s["A"].finish), (T0, T0 + timedelta(days=4)))
        self.assertEqual(s["B"].start, T0 + timedelta(days=5))
        self.assertEqual(s["C"].finish, T0 + timedelta(days=9))
        self.assertEqual(s["E"].start, T0)          # its only predecessor is done
        self.assertIsNone(s["D"].finish)
        self.assertEqual(ready_date(p, s), T0 + timedelta(days=9))

    def test_backward_pass_float_uses_gates_and_successors(self):
        # B must end by T-30 (16 Dec); A feeds B, so A's float is limited by B's late start
        p = proj(t("A", 10), t("B", 50, "A", gate="T-30"))
        s = plan(p)
        self.assertEqual(s["B"].deadline, date(2026, 12, 16))
        self.assertEqual(s["B"].late_start, date(2026, 10, 28))
        self.assertEqual(s["A"].late_finish, date(2026, 10, 27))
        self.assertEqual((s["A"].float_days, s["B"].float_days), (0, 0))
        self.assertTrue(s["A"].critical and not s["A"].late)

    def test_critical_path_is_the_driving_chain(self):
        p = proj(t("A", 10), t("X", 2), t("B", 5, "A;X"), t("C", 1, "B"), t("D", 30))
        self.assertEqual([x.task.id for x in critical_path(p, plan(p))], ["D"])
        p2 = proj(t("A", 10), t("X", 2), t("B", 25, "A;X"), t("C", 1, "B"), t("D", 30))
        self.assertEqual([x.task.id for x in critical_path(p2, plan(p2))], ["A", "B", "C"])

    def test_dependency_loop_is_reported(self):
        with self.assertRaises(CycleError):
            order(proj(t("A", 1, "C"), t("B", 1, "A"), t("C", 1, "B")))

    def test_readiness_is_weighted_by_duration(self):
        p = proj(t("A", 10, status="done", pct=100, ws="Net"), t("B", 30, pct=50, ws="Net"), t("C", 10, ws="PMS"))
        self.assertAlmostEqual(readiness(p)["Net"], 25 / 40)
        self.assertEqual(readiness(p)["PMS"], 0)
        self.assertAlmostEqual(overall(p), 25 / 50)


class Findings(unittest.TestCase):
    def test_opening_at_risk_only_when_ready_after_the_day_before(self):
        ok = proj(t("A", 88))                      # finishes 13 Jan: one day spare
        self.assertEqual(check_opening(ok, plan(ok)), [])
        late = proj(t("A", 90))                    # finishes 15 Jan, the opening day
        f = check_opening(late, plan(late))
        self.assertEqual((f[0].code, f[0].severity), ("OPENING_AT_RISK", "critical"))

    def test_gate_missed_and_at_risk(self):
        p = proj(t("A", 5, gate="T-90"), t("B", 70, gate="T-30"), t("C", 1, gate="T-30"))
        got = {f.code: f for f in check_gates(p, plan(p))}
        self.assertEqual(got["GATE_MISSED"].severity, "critical")    # T-90 was 17 Oct
        self.assertEqual(got["GATE_AT_RISK"].severity, "warning")
        self.assertIn("1 of 2 tasks is", got["GATE_AT_RISK"].detail)

    def test_late_blocked_and_no_float(self):
        p = proj(t("A", 40, gate="T-60"), t("B", 3, status="blocked", note="licence"), t("C", 60, gate="T-30"))
        got = {f.ref: f for f in check_tasks(p, plan(p))}
        self.assertEqual((got["A"].code, got["A"].severity), ("LATE", "warning"))
        self.assertEqual((got["B"].code, got["B"].severity), ("BLOCKED", "warning"))
        self.assertIn("licence", got["B"].detail)
        self.assertEqual(got["C"].code, "NO_FLOAT")
        threat = proj(t("A", 40, gate="T-60"), t("Z", 60, "A"))           # A late, and its chain ends after opening-1
        self.assertEqual({f.ref: f.severity for f in check_tasks(threat, plan(threat))}["A"], "critical")

    def test_start_now_for_long_lead_times(self):
        p = proj(t("A", 55, gate="T-30", vendor="Acme"), t("B", 10, gate="T-30"), t("C", 55, gate="T-30", status="in_progress", pct=10))
        fs = check_lead_times(p, plan(p), Config())
        self.assertEqual([f.ref for f in fs], ["A"])
        self.assertIn("Acme", fs[0].detail)

    def test_risks_and_data_quality(self):
        rs = [Risk("R1", "x", likelihood=4, impact=5, mitigation="plan"), Risk("R2", "y", likelihood=3, impact=4),
              Risk("R3", "z", likelihood=1, impact=2), Risk("R4", "w", likelihood=5, impact=5, status="closed")]
        got = {f.ref: (f.code, f.severity) for f in check_risks(proj(risks=rs), Config())}
        self.assertEqual(got, {"R1": ("HIGH_RISK", "warning"), "R2": ("NO_MITIGATION", "warning"), "R3": ("NO_MITIGATION", "info")})
        dq = check_data(proj(t("A", owner=""), t("B", deps="Q"), t("C", gate="T-45")))
        self.assertEqual(sorted(f.code for f in dq), ["NO_OWNER", "UNKNOWN_DEPENDENCY", "UNKNOWN_GATE"])


class Loading(unittest.TestCase):
    def test_semicolon_csv_custom_gates_and_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "project.json").write_text(json.dumps({"property": "P", "opening_date": "2027-03-01", "as_of": "2027-01-01",
                                                       "gates": [{"code": "t-20", "name": "Ready", "days_before_opening": 20}]}))
            (d / "tasks.csv").write_text("﻿ID;Task;Duration_days;Depends_on;Gate;Status;Percent\n"
                                         "A;Cabling;10;;T-20;En curso;40\nB;Switches;5;A;T-20;;\n", encoding="utf-8")
            p = load(d)
            self.assertEqual([g.code for g in p.gates], ["T-20"])
            self.assertEqual((p.tasks[0].percent, p.tasks[1].depends_on), (40.0, ["A"]))
            self.assertEqual(plan(p)["B"].deadline, date(2027, 2, 9))
            (d / "project.json").write_text(json.dumps({"property": "P"}))
            self.assertEqual(cli.main(["report", str(d)]), 2)


class EndToEnd(unittest.TestCase):
    def test_demo_writes_all_outputs_and_fires_the_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, out = Path(tmp) / "data", Path(tmp) / "out"
            self.assertEqual(cli.main(["demo", "--data", str(data), "--out", str(out)]), 0)
            for name in ("report.html", "review.md", "golive_checklist.md", "findings.csv", "actions.csv"):
                self.assertTrue((out / name).stat().st_size > 300, name)
            with open(out / "findings.csv", encoding="utf-8") as fh:
                codes = {r["code"] for r in csv.DictReader(fh)}
            self.assertEqual({"GATE_MISSED", "GATE_AT_RISK", "LATE", "BLOCKED", "NO_FLOAT", "START_NOW", "HIGH_RISK",
                              "NO_MITIGATION", "NO_OWNER"} - codes, set())
            p = load(data)
            s = plan(p)
            self.assertEqual([x.task.id for x in critical_path(p, s)], ["N2", "N5", "P3", "H2", "P5", "X1", "X2"])
            self.assertEqual(report.summary(p, s, run_all(p, slots=s))["margin"], 2)
            self.assertIn("<svg", (out / "report.html").read_text(encoding="utf-8"))
            # the same plan reviewed three weeks later without progress puts the opening at risk
            later = load(data, date(2026, 11, 8))
            self.assertIn("OPENING_AT_RISK", {f.code for f in run_all(later)})


if __name__ == "__main__":
    unittest.main()
