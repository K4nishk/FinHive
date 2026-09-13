"""CSV import/export service unit tests."""
import csv
import os
import tempfile
from datetime import date

import pytest

from loan_manager.infrastructure.csv.import_service import CsvImportService
from loan_manager.infrastructure.csv.export_service import CsvExportService


class TestCsvImportService:
    def test_parse_csv_basic(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "borrower_name,borrower_group,amount,giving_date,depositor_name,depositor_group,due_date,reference_id\n"
            "alice,bg1,10000,2026-01-15,dan,dg1,2026-04-15,2026_01_001\n"
            "bob,bg2,20000,15-02-2026,eve,dg2,15-05-2026,\n"
        )

        service = CsvImportService()
        records = service.parse(str(csv_file))

        assert len(records) == 2

        # First record: YYYY-MM-DD format
        assert records[0]["borrower_name"] == "alice"
        assert records[0]["amount"] == 10000
        assert records[0]["giving_date"] == date(2026, 1, 15)
        assert records[0]["reference_id"] == "2026_01_001"

        # Second record: DD-MM-YYYY format, no ref_id
        assert records[1]["borrower_name"] == "bob"
        assert records[1]["giving_date"] == date(2026, 2, 15)
        assert records[1]["reference_id"] is None

    def test_parse_csv_with_extra_whitespace(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            " Borrower_Name , Amount , Giving_Date \n"
            " Alice , 10000 , 2026-01-15 \n"
        )

        service = CsvImportService()
        records = service.parse(str(csv_file))
        assert records[0]["borrower_name"] == "alice"
        assert records[0]["amount"] == 10000

    def test_parse_csv_empty_dates(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "borrower_name,amount,giving_date,due_date,depositor_name,borrower_group,depositor_group,reference_id\n"
            "alice,10000,2026-01-15,,dan,bg1,dg1,\n"
        )

        service = CsvImportService()
        records = service.parse(str(csv_file))
        assert records[0]["due_date"] is None

    def test_parse_csv_invalid_date_returns_none(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "borrower_name,amount,giving_date,depositor_name,borrower_group,depositor_group,due_date,reference_id\n"
            "alice,10000,not-a-date,dan,bg1,dg1,,\n"
        )

        service = CsvImportService()
        records = service.parse(str(csv_file))
        assert records[0]["giving_date"] is None

    def test_parse_empty_csv(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(
            "borrower_name,amount,giving_date\n"
        )

        service = CsvImportService()
        records = service.parse(str(csv_file))
        assert len(records) == 0


class TestCsvExportService:
    def test_write_loans_csv(self, tmp_path):
        from types import SimpleNamespace

        loans = [
            SimpleNamespace(
                reference_id="2026_01_001",
                borrower_name="alice",
                borrower_group="bg1",
                depositor_name="dan",
                depositor_group="dg1",
                amount=10000,
                giving_date=date(2026, 1, 15),
                due_date=date(2026, 4, 15),
                status="Active",
                is_active=True,
            ),
        ]

        path = str(tmp_path / "export.csv")
        service = CsvExportService()
        service.write_loans(loans, path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["reference_id"] == "2026_01_001"
        assert rows[0]["amount"] == "10000"

    def test_write_report_csv(self, tmp_path):
        from types import SimpleNamespace

        unit = SimpleNamespace(value="months")
        report = SimpleNamespace(
            records=[
                SimpleNamespace(
                    reference_id="2026_01_001",
                    borrower_name="alice",
                    depositor_name="dan",
                    depositor_group="dg1",
                    amount=10000,
                    giving_date=date(2026, 1, 15),
                    due_date=date(2026, 4, 15),
                    extension_period=3,
                    extension_period_unit=unit,
                    interest_rate="12.00",
                    commission_rate="6.00",
                    tds_flag=False,
                    interest_amount="300.00",
                    commission_amount="150.00",
                    tds_amount="0.00",
                    chq_amount="300.00",
                    post_extension_giving_date=date(2026, 4, 15),
                    post_extension_due_date=date(2026, 7, 15),
                    paidoff_date=None,
                )
            ]
        )

        path = str(tmp_path / "report.csv")
        service = CsvExportService()
        service.write_report(report, path)

        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["interest_amount"] == "300.00"

    def test_write_loans_xlsx(self, tmp_path):
        from types import SimpleNamespace

        loans = [
            SimpleNamespace(
                reference_id="2026_01_001",
                borrower_name="alice",
                borrower_group="bg1",
                depositor_name="dan",
                depositor_group="dg1",
                amount=10000,
                giving_date=date(2026, 1, 15),
                due_date=date(2026, 4, 15),
                status="Active",
                is_active=True,
            ),
        ]

        path = str(tmp_path / "export.xlsx")
        service = CsvExportService()
        service.write_loans_xlsx(loans, path)

        assert os.path.exists(path)
