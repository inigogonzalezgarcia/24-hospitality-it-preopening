# Weekly IT pre-opening meeting: runbook

45 minutes every week from about T-120, every day from T-7. Attendees: IT lead, the owner of each workstream,
the pre-opening or general manager and, when their tasks are on the critical path, the vendors.

## Before the meeting (20 minutes)

1. Ask each owner to update `status`, `percent` and `note` for their tasks in `tasks.csv` (a shared spreadsheet
   exported to CSV works well).
2. Update `risks.csv`: new risks, new scores, mitigations that are now ready.
3. Run the review:
   ```bash
   python -m preopen report data/ --out output --title "IT pre-opening · week 12"
   ```
4. Send `output/review.md` and `output/report.html` with the agenda.

## In the meeting

1. **Opening date** (5 min). The forecast ready date and the margin. If the margin is negative, the meeting is about
   the critical path and nothing else.
2. **Critical path** (10 min). For each task on it: is the date real, what would make it shorter (more people,
   overlap, a temporary solution such as a 4G router while the fixed lines arrive), who confirms it in writing.
3. **Gates** (10 min). A gate that has passed with open tasks: close them or move them to a later gate on purpose.
   The next gate: which tasks are forecast late and what the owner commits to.
4. **Blocked and start-now tasks** (10 min). Every blocked task leaves with an escalation and a date. Every task that
   must start this week leaves with an order number or a delivery date.
5. **Risks** (5 min). Scores of 15 and above every week; mitigations that are only written down are not ready.
6. **Actions** (5 min). Owner and date for each, recorded in `tasks.csv` for next week.

## Gate reviews

At each gate date, walk the gate's tasks in the report one by one with the owner and, for vendor work, the vendor's
sign-off (test results, as-built drawings, handover documents). A gate is passed when all its tasks are `done`; a
task moved to a later gate is a decision, written in the minutes with the reason and the new date.

## From T-7

Print `output/golive_checklist.md`. Each line gets a name and a time when it is checked. Run the dress rehearsal with
real people doing real check-ins, room charges and check-outs, not with IT testing its own systems.
