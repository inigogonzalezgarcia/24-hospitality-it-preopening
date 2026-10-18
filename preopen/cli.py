"""Command line: `demo` builds everything from a fictional hotel opening, `report` runs on your own plan."""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from . import report, simulate
from .checks import Config, run_all
from .model import load, parse_date
from .schedule import CycleError, plan


def run(data: Path, out: Path, title: str, c: Config, as_of: date | None = None) -> dict:
    p = load(data, as_of)
    slots = plan(p)
    findings = run_all(p, c, slots)
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.html").write_text(report.render_html(p, slots, findings, title), encoding="utf-8")
    (out / "review.md").write_text(report.review_md(p, slots, findings), encoding="utf-8")
    (out / "golive_checklist.md").write_text(report.golive_md(p, slots), encoding="utf-8")
    report.write_findings(findings, out / "findings.csv")
    report.write_actions(p, slots, out / "actions.csv")
    return report.summary(p, slots, findings)


def _date(value: str) -> date:
    d = parse_date(value)
    if not d:
        raise argparse.ArgumentTypeError(f"not a date (YYYY-MM-DD): {value}")
    return d


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="preopen", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    dm = sub.add_parser("demo", help="write the fictional hotel plan to sample_data/ and build the outputs")
    dm.add_argument("--data", type=Path, default=Path("sample_data"))
    dm.add_argument("--out", type=Path, default=Path("output"))
    r = sub.add_parser("report", help="build the outputs from your own folder (project.json, tasks.csv, risks.csv)")
    r.add_argument("data", type=Path)
    r.add_argument("--out", type=Path, default=Path("output"))
    r.add_argument("--title", default="IT pre-opening review")
    r.add_argument("--as-of", type=_date, help="review date, YYYY-MM-DD (default: project.json or today)")
    r.add_argument("--start-soon-days", type=int, default=Config.start_soon_days)
    a = p.parse_args(argv)
    try:
        if a.cmd == "demo":
            simulate.write(a.data)
            sm = run(a.data, a.out, "IT pre-opening review · Hotel Mirador del Puerto", Config())
        else:
            sm = run(a.data, a.out, a.title, Config(start_soon_days=a.start_soon_days), a.as_of)
    except (FileNotFoundError, ValueError, CycleError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    margin = f"{sm['margin']} days of margin" if sm["margin"] >= 0 else f"{-sm['margin']} days late"
    print(f"{sm['days_to_opening']} days to opening · IT ready {sm['ready']:%Y-%m-%d} ({margin}) · {sm['progress']:.0%} done · "
          f"{sm['critical']} critical, {sm['warning']} warnings · outputs in {a.out}/")
    return 0
