"""Fictional demo: IT pre-opening of a 120-room resort hotel (Hotel Mirador del Puerto, contoso.example) with a
restaurant, two bars and a spa, opening on 15 January 2027 and reviewed on 18 October 2026. Vendor names are
Microsoft's fictional sample companies; people and dates are invented. Delays are placed on purpose (see README)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

PROJECT = {
    "property": "Hotel Mirador del Puerto (fictional)",
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
        {"code": "T-1", "name": "Ready to open", "days_before_opening": 1},
    ],
}

T_FIELDS = ["id", "workstream", "task", "owner", "vendor", "duration_days", "depends_on", "gate", "status", "percent", "note"]

NET, PMS, POS, TV, LOCK, TEL, BO, SEC, GO = ("Network and Wi-Fi", "PMS and distribution", "POS and payments",
                                             "TV and guest entertainment", "Door locks", "Telephony",
                                             "Back office", "Security and data protection", "Training and go-live")
TASKS = [
    ("N1", NET, "Network design and Wi-Fi survey signed off", "Iván Soto", "Proseware Networks", 10, "", "T-90", "in_progress", 70, ""),
    ("N2", NET, "Internet circuits delivered, two diverse providers", "Iván Soto", "Northwind Telecom", 75, "", "T-60", "in_progress", 20, "Ordered on 3 October; provider lead time 75 days"),
    ("N3", NET, "Structured cabling and comms rooms", "Iván Soto", "Adventure Works Cabling", 30, "N1", "T-60", "in_progress", 40, ""),
    ("N4", NET, "Switches, firewall and Wi-Fi access points installed", "Iván Soto", "Proseware Networks", 14, "N3", "T-30", "todo", 0, ""),
    ("N5", NET, "Internet live and failover tested", "Iván Soto", "Northwind Telecom", 3, "N2;N4", "T-30", "todo", 0, ""),
    ("N6", NET, "Guest Wi-Fi portal with room-number login", "Iván Soto", "Proseware Networks", 5, "N5;P3", "T-14", "todo", 0, ""),
    ("P1", PMS, "PMS contract and configuration workshop", "Elena Vidal", "Fabrikam Hospitality", 10, "", "T-90", "done", 100, ""),
    ("P2", PMS, "PMS build: rooms, rates, taxes, users", "Elena Vidal", "Fabrikam Hospitality", 21, "P1", "T-30", "in_progress", 50, ""),
    ("P3", PMS, "Cloud PMS reachable from the hotel network", "Elena Vidal", "Fabrikam Hospitality", 2, "N5;P2", "T-30", "todo", 0, ""),
    ("P4", PMS, "Channel manager and booking engine connected", "Elena Vidal", "Fabrikam Hospitality", 7, "P2", "T-30", "in_progress", 20, ""),
    ("P5", PMS, "PMS interfaces tested end to end: POS, locks, TV, phones", "Elena Vidal", "Fabrikam Hospitality", 7, "P3;S3;L2;T2;H2", "T-14", "todo", 0, ""),
    ("S1", POS, "POS and back-office licences ordered", "Raúl Ortega", "Tailspin POS", 5, "", "T-90", "done", 100, ""),
    ("S2", POS, "POS menus, prices, printers and kitchen screens", "Raúl Ortega", "Tailspin POS", 14, "S1", "T-30", "todo", 0, ""),
    ("S3", POS, "POS to PMS room-charge interface licence", "Raúl Ortega", "Tailspin POS", 10, "S1", "T-30", "blocked", 0, "Waiting for the PMS vendor to issue the interface licence"),
    ("S4", POS, "Card terminals installed and certified with the acquirer", "Raúl Ortega", "Woodgrove Payments", 21, "N4", "T-14", "todo", 0, ""),
    ("S5", POS, "Cash recyclers installed in two outlets", "Raúl Ortega", "Tailspin POS", 3, "S2", "T-14", "todo", 0, ""),
    ("T1", TV, "IPTV headend and room TVs installed", "Iván Soto", "Litware Media", 14, "N4", "T-30", "todo", 0, ""),
    ("T2", TV, "Channel line-up and welcome screen with guest name", "", "Litware Media", 5, "T1", "T-14", "todo", 0, ""),
    ("T3", TV, "TV content and background music licences signed", "Elena Vidal", "Adatum Media Rights", 55, "", "T-30", "todo", 0, ""),
    ("L1", LOCK, "Door lock encoders and readers delivered", "Raúl Ortega", "Contoso Locks", 40, "", "T-30", "in_progress", 30, "Shipped from the factory on request"),
    ("L2", LOCK, "Lock system installed and linked to the PMS, test cards", "Raúl Ortega", "Contoso Locks", 7, "L1;N4", "T-14", "todo", 0, ""),
    ("H1", TEL, "Phone system and room phones", "Iván Soto", "Relecloud Voice", 10, "N4", "T-30", "todo", 0, ""),
    ("H2", TEL, "Call charges posted to the PMS folio", "Iván Soto", "Relecloud Voice", 3, "H1;P3", "T-14", "todo", 0, ""),
    ("B1", BO, "Laptops, printers and Microsoft 365 accounts for 45 staff", "Marina Pons", "", 10, "N5", "T-14", "todo", 0, ""),
    ("B2", BO, "Back-office access: HR, purchasing and accounting", "Marina Pons", "", 7, "B1", "T-14", "todo", 0, ""),
    ("G1", SEC, "Guest privacy notices, retention rules and processor agreements", "Marina Pons", "", 14, "", "T-30", "in_progress", 50, ""),
    ("G2", SEC, "Backups, admin accounts with MFA and vendor remote access rules", "Iván Soto", "", 7, "N5", "T-14", "todo", 0, ""),
    ("X1", GO, "Staff training: front office, restaurant and bars, housekeeping", "Marina Pons", "", 10, "P5;S2", "T-7", "todo", 0, ""),
    ("X2", GO, "Dress rehearsal: check-in to check-out with friends and family", "Marina Pons", "", 2, "X1;N6;S4;S5;B2;G2", "T-1", "todo", 0, ""),
    ("X3", GO, "Go-live support plan: vendor engineers on site, escalation list", "Iván Soto", "", 3, "", "T-7", "todo", 0, ""),
]

R_FIELDS = ["id", "risk", "workstream", "likelihood", "impact", "owner", "mitigation", "status"]
RISKS = [
    ("R1", "Internet circuits not delivered in time", NET, 4, 5, "Iván Soto", "Bonded 4G/5G router as temporary internet, ordered as a back-up", "open"),
    ("R2", "Room-charge interface licence delayed by the vendors", POS, 3, 4, "Raúl Ortega", "", "open"),
    ("R3", "Lock encoders delayed at customs", LOCK, 2, 5, "Raúl Ortega", "Mechanical master keys and paper key log for the first week", "open"),
    ("R4", "Staff hired late, less time for training", GO, 3, 3, "Marina Pons", "Train the heads of department first; short videos per role", "open"),
    ("R5", "Card acquirer certification takes longer than planned", POS, 3, 4, "Raúl Ortega", "Start the paperwork now; one terminal certified early as a pilot", "open"),
    ("R6", "Wi-Fi coverage gaps around the pool", NET, 2, 2, "Iván Soto", "Two outdoor access points added to the design", "closed"),
]


def write(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "project.json").write_text(json.dumps(PROJECT, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with open(folder / "tasks.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(T_FIELDS)
        w.writerows(TASKS)
    with open(folder / "risks.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(R_FIELDS)
        w.writerows(RISKS)
    return folder
