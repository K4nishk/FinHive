import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loan_manager.infrastructure.database.models import Base
from loan_manager.infrastructure.database.session import DatabaseSession
from loan_manager.infrastructure.security.key_provider import set_active_key_ring

# KCH-227 (ARB D-15): every test that writes a LoanModel/LoanHistoryModel/
# ReportRecordModel row now goes through an encrypted-column TypeDecorator,
# which raises KeyConfigurationError unless a key ring is active. In the
# real app that happens once, at startup, via Container.get_key_ring() --
# nothing in this test suite constructs a Container, so nothing would ever
# set it. This autouse fixture is the test-suite equivalent of that startup
# step: it gives every test a deterministic key ring so existing tests keep
# exercising real encrypt/decrypt round-trips transparently, and clears it
# afterwards so tests that assert the no-active-key failure mode
# (tests/unit/test_encrypted_types.py) can do so in isolation by overriding
# it locally.
try:
    from finhive.db.keys import KeyRing

    _TEST_KEY_RING = KeyRing(current_version=1, masters={1: b"\x42" * 32})
except ImportError:  # pragma: no cover - exercised only without finhive/cryptography
    _TEST_KEY_RING = None


@pytest.fixture(autouse=True)
def _active_test_key_ring():
    set_active_key_ring(_TEST_KEY_RING)
    yield
    set_active_key_ring(None)


@pytest.fixture(scope="function")
def in_memory_engine():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(in_memory_engine):
    Session = sessionmaker(bind=in_memory_engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
