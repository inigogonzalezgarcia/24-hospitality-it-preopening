# Data format

One folder with `project.json` and `tasks.csv` (required) and `risks.csv` (optional). Comma or semicolon separators
both work, headers are case-insensitive and a UTF-8 BOM from Excel is fine. Dates are `YYYY-MM-DD`.

## project.json

```json
{
  "property": "Hotel Mirador del Puerto",
  "rooms": 120,
  "outlets": ["Restaurant", "Lobby bar", "Pool bar", "Spa"],
  "opening_date": "2027-01-15",
  "as_of": "2026-10-18",
  "gates": [
    {"code": "T-90", "name": "Design frozen", "days_before_opening": 90},
    {"code": "T-60", "name": "Infrastructure ready", "days_before_opening": 60},
    {"code": "T-30", "name": "Systems installed", "days_before_opening": 30},
    {"code": "T-14", "name": "Integrations tested", "days_before_opening": 14},
    {"code": "T-7", "name": "People trained", "days_before_opening": 7},
    {"code": "T-1", "name": "Ready to open", "days_before_opening": 1}
  ]
}
```

Only `opening_date` is required. Without `gates`, the six above are used. Without `as_of` (and without `--as-of`)
the review date is today.

## tasks.csv

| Column | Example | Meaning |
|---|---|---|
| `id` | `N2` | Required, unique. Used in `depends_on`. |
| `workstream` | `Network and Wi-Fi` | Groups tasks in the chart and the readiness table. |
| `task` | `Internet circuits delivered` | Required. |
| `owner` | `Iván Soto` | One person who reports progress every week. |
| `vendor` | `Northwind Telecom` | Who does the work, if not the hotel team. |
| `duration_days` | `75` | Calendar days for the whole task, including vendor lead time. |
| `depends_on` | `N2;N4` | IDs that must finish first, separated by `;`, `,` or spaces. |
| `gate` | `T-30` | The gate it must be finished by. Empty: the day before opening. |
| `status` | `todo`, `in_progress`, `blocked`, `done` | Also accepts *completed*, *started*, *not started* and the Spanish *pendiente*, *bloqueado*, *hecho*. Anything else counts as `todo`. |
| `percent` | `40` | Progress of an open task. The work left is `duration_days × (1 − percent)`, rounded up. |
| `note` | `Waiting for the interface licence` | Shown on blocked tasks. |

The schedule uses calendar days because pre-openings run seven days a week and vendor lead times are quoted in
calendar days. Tasks start as soon as their predecessors finish; finished tasks take no time.

## risks.csv

| Column | Example | Meaning |
|---|---|---|
| `id` | `R1` | |
| `risk` | `Internet circuits not delivered in time` | |
| `workstream` | `Network and Wi-Fi` | |
| `likelihood`, `impact` | `4`, `5` | 1 to 5 each. Score = likelihood × impact. |
| `owner` | `Iván Soto` | |
| `mitigation` | `Bonded 4G/5G router as temporary internet` | Empty raises a finding (warning from a score of 10). |
| `status` | `open` / `closed` | Closed risks are left out. |
