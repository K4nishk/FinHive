"""
Sample data from REQUIREMENTS.md for testing.
15 records: b1-b15
"""
from datetime import date

SAMPLE_LOANS = [
    {"borrower_name": "b1",  "borrower_group": "bg1", "amount": 10000, "giving_date": date(2026, 1, 2),  "depositor_name": "d1",  "depositor_group": "dg1", "due_date": date(2026, 4, 2)},
    {"borrower_name": "b2",  "borrower_group": "bg2", "amount": 10000, "giving_date": date(2026, 1, 4),  "depositor_name": "d2",  "depositor_group": "dg1", "due_date": date(2026, 5, 4)},
    {"borrower_name": "b3",  "borrower_group": "bg3", "amount": 15000, "giving_date": date(2026, 2, 6),  "depositor_name": "d3",  "depositor_group": "dg1", "due_date": date(2026, 5, 6)},
    {"borrower_name": "b4",  "borrower_group": "bg3", "amount": 20000, "giving_date": date(2026, 2, 7),  "depositor_name": "d4",  "depositor_group": "dg2", "due_date": date(2026, 6, 7)},
    {"borrower_name": "b5",  "borrower_group": "bg4", "amount": 20000, "giving_date": date(2026, 2, 8),  "depositor_name": "d5",  "depositor_group": "dg2", "due_date": date(2026, 6, 8)},
    {"borrower_name": "b6",  "borrower_group": "bg4", "amount": 15000, "giving_date": date(2026, 2, 8),  "depositor_name": "d6",  "depositor_group": "dg3", "due_date": date(2026, 7, 8)},
    {"borrower_name": "b7",  "borrower_group": "bg5", "amount": 15000, "giving_date": date(2026, 2, 15), "depositor_name": "d7",  "depositor_group": "dg3", "due_date": date(2026, 7, 15)},
    {"borrower_name": "b8",  "borrower_group": "bg5", "amount": 20000, "giving_date": date(2026, 2, 18), "depositor_name": "d8",  "depositor_group": "dg3", "due_date": date(2026, 6, 18)},
    {"borrower_name": "b9",  "borrower_group": "bg1", "amount": 20000, "giving_date": date(2026, 2, 20), "depositor_name": "d9",  "depositor_group": "dg3", "due_date": date(2026, 6, 20)},
    {"borrower_name": "b10", "borrower_group": "bg6", "amount": 10000, "giving_date": date(2026, 2, 25), "depositor_name": "d10", "depositor_group": "dg1", "due_date": date(2026, 5, 25)},
    {"borrower_name": "b11", "borrower_group": "bg6", "amount": 15000, "giving_date": date(2026, 2, 28), "depositor_name": "d11", "depositor_group": "dg2", "due_date": date(2026, 5, 28)},
    {"borrower_name": "b12", "borrower_group": "bg7", "amount": 15000, "giving_date": date(2026, 3, 2),  "depositor_name": "d12", "depositor_group": "dg4", "due_date": date(2026, 7, 2)},
    {"borrower_name": "b13", "borrower_group": "bg7", "amount": 10000, "giving_date": date(2026, 3, 5),  "depositor_name": "d13", "depositor_group": "dg4", "due_date": date(2026, 7, 5)},
    {"borrower_name": "b14", "borrower_group": "bg8", "amount": 15000, "giving_date": date(2026, 3, 10), "depositor_name": "d14", "depositor_group": None,   "due_date": date(2026, 7, 10)},
    {"borrower_name": "b15", "borrower_group": "bg8", "amount": 20000, "giving_date": date(2026, 3, 14), "depositor_name": "d15", "depositor_group": None,   "due_date": date(2026, 7, 14)},
]
