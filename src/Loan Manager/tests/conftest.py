import pytest
from pathlib import Path
from datetime import date


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Isolated data directory for each test."""
    d = tmp_path / "data"
    d.mkdir()
    return d


@pytest.fixture
def sample_loans() -> list[tuple]:
    """15 sample loan records from requirements.

    Columns:
        reference_id, borrower_name, borrower_group, amount,
        giving_date, depositor_name, depositor_group, due_date, status
    """
    return [
        ("2026_01_001", "b1",  "bg1", 10000, date(2026, 1, 2),  "d1",  "dg1",  date(2026, 4, 2),  "Active"),
        ("2026_01_002", "b2",  "bg2", 10000, date(2026, 1, 4),  "d2",  "dg1",  date(2026, 5, 4),  "Active"),
        ("2026_02_001", "b3",  "bg3", 15000, date(2026, 2, 6),  "d3",  "dg1",  date(2026, 5, 6),  "Active"),
        ("2026_02_002", "b4",  "bg3", 20000, date(2026, 2, 7),  "d4",  "dg2",  date(2026, 6, 7),  "Active"),
        ("2026_02_003", "b5",  "bg4", 20000, date(2026, 2, 8),  "d5",  "dg2",  date(2026, 6, 8),  "Active"),
        ("2026_02_004", "b6",  "bg4", 15000, date(2026, 2, 8),  "d6",  "dg3",  date(2026, 7, 8),  "Active"),
        ("2026_02_005", "b7",  "bg5", 15000, date(2026, 2, 15), "d7",  "dg3",  date(2026, 7, 15), "Active"),
        ("2026_02_006", "b8",  "bg5", 20000, date(2026, 2, 18), "d8",  "dg3",  date(2026, 6, 18), "Active"),
        ("2026_02_007", "b9",  "bg1", 20000, date(2026, 2, 20), "d9",  "dg3",  date(2026, 6, 20), "Active"),
        ("2026_02_008", "b10", "bg6", 10000, date(2026, 2, 25), "d10", "dg1",  date(2026, 5, 25), "Active"),
        ("2026_02_009", "b11", "bg6", 15000, date(2026, 2, 28), "d11", "dg2",  date(2026, 5, 28), "Active"),
        ("2026_03_001", "b12", "bg7", 15000, date(2026, 3, 2),  "d12", "dg4",  date(2026, 7, 2),  "Active"),
        ("2026_03_002", "b13", "bg7", 10000, date(2026, 3, 5),  "d13", "dg4",  date(2026, 7, 5),  "Active"),
        ("2026_03_003", "b14", "bg8", 15000, date(2026, 3, 10), "d14", None,   date(2026, 7, 10), "Active"),
        ("2026_03_004", "b15", "bg8", 20000, date(2026, 3, 14), "d15", None,   date(2026, 7, 14), "Active"),
    ]
