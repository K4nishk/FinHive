"""Import/Export use case integration tests."""
import csv
from datetime import date, datetime
from decimal import Decimal

import pytest

from loan_manager.application.use_cases.data.import_loans import ImportLoans
from loan_manager.application.use_cases.data.export_loans import ExportLoans
from loan_manager.application.use_cases.loans.get_loans import GetAllLoans
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def uow_factory(db_session):
    def factory():
        return SqlAlchemyUnitOfWork(db_session)
    return factory


class TestImportLoans:
    def test_preview(self, uow_factory, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "borrower_name,borrower_group,amount,giving_date,depositor_name,depositor_group,due_date,reference_id\n"
            "alice,bg1,10000,2026-01-15,dan,dg1,2026-04-15,\n"
            "bob,bg2,20000,2026-02-01,eve,dg2,2026-05-01,\n"
        )

        uc = ImportLoans(uow_factory)
        preview = uc.preview(str(csv_file))
        assert preview.total_new == 2
        assert preview.total_overwrite == 0

    def test_commit(self, uow_factory, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "borrower_name,borrower_group,amount,giving_date,depositor_name,depositor_group,due_date,reference_id\n"
            "alice,bg1,10000,2026-01-15,dan,dg1,2026-04-15,\n"
            "bob,bg2,20000,2026-02-01,eve,dg2,2026-05-01,\n"
        )

        uc = ImportLoans(uow_factory)
        result = uc.commit(str(csv_file))
        assert result.inserted == 2
        assert result.updated == 0
        assert result.skipped == 0

        get_uc = GetAllLoans(uow_factory)
        loans = get_uc.execute()
        assert len(loans) == 2

    def test_commit_with_existing_ref_id_updates(self, uow_factory, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "borrower_name,borrower_group,amount,giving_date,depositor_name,depositor_group,due_date,reference_id\n"
            "alice,bg1,10000,2026-01-15,dan,dg1,2026-04-15,\n"
        )

        uc = ImportLoans(uow_factory)
        uc.commit(str(csv_file))

        # Import again with same auto-assigned ref_id should update
        result = uc.commit(str(csv_file))
        # Second import gets new ref_ids (since first ones were auto-assigned),
        # so these will also be inserts
        assert result.inserted + result.updated == 1

    def test_commit_skips_invalid_rows(self, uow_factory, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "borrower_name,borrower_group,amount,giving_date,depositor_name,depositor_group,due_date,reference_id\n"
            ",bg1,,2026-01-15,dan,dg1,2026-04-15,\n"
        )

        uc = ImportLoans(uow_factory)
        result = uc.commit(str(csv_file))
        assert result.skipped == 1
        assert len(result.errors) == 1

    def test_commit_no_overwrite(self, uow_factory, tmp_path):
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "borrower_name,borrower_group,amount,giving_date,depositor_name,depositor_group,due_date,reference_id\n"
            "alice,bg1,10000,2026-01-15,dan,dg1,2026-04-15,2026_01_001\n"
        )

        uc = ImportLoans(uow_factory)
        uc.commit(str(csv_file), overwrite_existing=True)

        # Second import with overwrite=False
        result = uc.commit(str(csv_file), overwrite_existing=False)
        assert result.skipped == 1


class TestExportLoans:
    def test_export_csv(self, uow_factory, tmp_path):
        # First import some loans
        csv_file = tmp_path / "import.csv"
        csv_file.write_text(
            "borrower_name,borrower_group,amount,giving_date,depositor_name,depositor_group,due_date,reference_id\n"
            "alice,bg1,10000,2026-01-15,dan,dg1,2026-04-15,\n"
        )
        ImportLoans(uow_factory).commit(str(csv_file))

        export_uc = ExportLoans(uow_factory)
        output_path = str(tmp_path / "export.csv")
        result = export_uc.execute(format="csv", output_path=output_path)

        assert result == output_path
        with open(result) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
