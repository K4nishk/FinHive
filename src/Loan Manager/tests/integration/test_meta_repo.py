"""Meta repository integration tests."""
import pytest

from loan_manager.infrastructure.repositories.sqlalchemy_meta_repo import (
    SqlAlchemyLoanMetaRepository,
    SqlAlchemyReportMetaRepository,
)


class TestLoanMetaRepository:
    def test_get_last_order_returns_none_when_empty(self, db_session):
        repo = SqlAlchemyLoanMetaRepository(db_session)
        assert repo.get_last_order("2026_03") is None

    def test_set_and_get_last_order(self, db_session):
        repo = SqlAlchemyLoanMetaRepository(db_session)
        repo.set_last_order("2026_03", 5)
        db_session.commit()
        assert repo.get_last_order("2026_03") == 5

    def test_update_existing_order(self, db_session):
        repo = SqlAlchemyLoanMetaRepository(db_session)
        repo.set_last_order("2026_03", 5)
        db_session.commit()
        repo.set_last_order("2026_03", 10)
        db_session.commit()
        assert repo.get_last_order("2026_03") == 10


class TestReportMetaRepository:
    def test_get_last_order_returns_none_when_empty(self, db_session):
        repo = SqlAlchemyReportMetaRepository(db_session)
        assert repo.get_last_order("20260315") is None

    def test_set_and_get_last_order(self, db_session):
        repo = SqlAlchemyReportMetaRepository(db_session)
        repo.set_last_order("20260315", 3)
        db_session.commit()
        assert repo.get_last_order("20260315") == 3

    def test_update_existing_order(self, db_session):
        repo = SqlAlchemyReportMetaRepository(db_session)
        repo.set_last_order("20260315", 3)
        db_session.commit()
        repo.set_last_order("20260315", 7)
        db_session.commit()
        assert repo.get_last_order("20260315") == 7
