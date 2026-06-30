import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from loan_manager.infrastructure.database.models import Base
from loan_manager.infrastructure.database.session import DatabaseSession


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
