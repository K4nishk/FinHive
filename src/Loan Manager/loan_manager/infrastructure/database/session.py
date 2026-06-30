from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from loan_manager.config import DATABASE_URL, DATA_DIR, LOG_DIR, BACKUP_DIR, EXPORT_DIR
from loan_manager.infrastructure.database.models import Base


class DatabaseSession:
    _engine = None
    _SessionLocal = None

    @classmethod
    def initialize(cls) -> None:
        # Create required directories
        for d in [DATA_DIR, LOG_DIR, BACKUP_DIR, EXPORT_DIR]:
            d.mkdir(parents=True, exist_ok=True)

        cls._engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},
            echo=False,
        )
        Base.metadata.create_all(cls._engine)
        cls._SessionLocal = sessionmaker(bind=cls._engine, expire_on_commit=False)

    @classmethod
    def get_session(cls) -> Session:
        if cls._SessionLocal is None:
            raise RuntimeError("DatabaseSession not initialized. Call initialize() first.")
        return cls._SessionLocal()

    @classmethod
    def get_engine(cls):
        return cls._engine
