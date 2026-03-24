# Coding Patterns and Style Guide

## General Principles

### Code Philosophy
1. **Readability over Cleverness**: Code is read 10x more than written
2. **Explicit over Implicit**: Favor clarity over magic
3. **Fail Fast**: Validate early, catch errors at the boundary
4. **DRY (Don't Repeat Yourself)**: Abstract common patterns, but avoid premature optimization
5. **YAGNI (You Aren't Gonna Need It)**: Build what's needed now, not what might be needed later
6. **Security by Default**: Every feature designed with security in mind

### Version Control
- **Git Flow**: Feature branches, PR reviews before merge
- **Commit Messages**: Conventional Commits format
  ```
  feat: add loan deletion with soft delete
  fix: resolve date validation bug in loan form
  docs: update API documentation for new endpoints
  test: add unit tests for loan service
  ```
- **Branch Naming**: `feature/loan-deletion`, `bugfix/date-validation`, `hotfix/security-patch`

## Python Backend Standards

### Style Guide
- **PEP 8**: Official Python style guide (enforced via `black`, `flake8`)
- **Type Hints**: Mandatory for all functions (enforced via `mypy`)
- **Docstrings**: Google style for all public functions/classes
- **Line Length**: 100 characters (black default)

### Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app initialization
│   ├── config.py               # Configuration (env variables)
│   ├── dependencies.py         # Dependency injection
│   │
│   ├── api/                    # API layer
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── loans.py    # Loan CRUD endpoints
│   │   │   │   ├── reports.py  # Report generation endpoints
│   │   │   │   └── health.py   # Health check
│   │   │   └── router.py       # API router aggregation
│   │
│   ├── core/                   # Core business logic
│   │   ├── __init__.py
│   │   ├── security.py         # Authentication, encryption
│   │   ├── logging.py          # Logging configuration
│   │   └── exceptions.py       # Custom exceptions
│   │
│   ├── models/                 # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── loan.py
│   │   └── audit_log.py
│   │
│   ├── schemas/                # Pydantic schemas (DTOs)
│   │   ├── __init__.py
│   │   ├── loan.py
│   │   └── report.py
│   │
│   ├── services/               # Business logic layer
│   │   ├── __init__.py
│   │   ├── loan_service.py
│   │   ├── report_service.py
│   │   └── backup_service.py
│   │
│   ├── repositories/           # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── loan_repository.py
│   │
│   └── utils/                  # Utility functions
│       ├── __init__.py
│       ├── encryption.py
│       └── validators.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── alembic/                    # Database migrations
│   └── versions/
│
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml              # Black, isort, mypy config
└── Dockerfile
```

### Coding Patterns

#### 1. Dependency Injection (FastAPI)

```python
# app/dependencies.py
from sqlalchemy.orm import Session
from app.core.database import SessionLocal

def get_db() -> Session:
    """Provide database session with automatic cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Usage in endpoint
from fastapi import Depends
from app.dependencies import get_db

@router.get("/loans")
async def get_loans(db: Session = Depends(get_db)):
    return loan_service.get_all(db)
```

#### 2. Repository Pattern (Data Access)

```python
# app/repositories/base.py
from typing import Generic, TypeVar, Type, List, Optional
from sqlalchemy.orm import Session
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    """Generic repository with common CRUD operations."""

    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: str) -> Optional[ModelType]:
        """Retrieve single record by ID."""
        return db.query(self.model).filter(
            self.model.id == id,
            self.model.deleted_at.is_(None)
        ).first()

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Retrieve all records with pagination."""
        return db.query(self.model).filter(
            self.model.deleted_at.is_(None)
        ).offset(skip).limit(limit).all()

    def create(self, db: Session, obj: ModelType) -> ModelType:
        """Create new record."""
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    def soft_delete(self, db: Session, id: str) -> bool:
        """Soft delete record by setting deleted_at timestamp."""
        obj = self.get(db, id)
        if obj:
            obj.deleted_at = datetime.utcnow()
            db.commit()
            return True
        return False

# app/repositories/loan_repository.py
from app.repositories.base import BaseRepository
from app.models.loan import Loan

class LoanRepository(BaseRepository[Loan]):
    def __init__(self):
        super().__init__(Loan)

    def get_by_borrower(self, db: Session, borrower_name: str) -> List[Loan]:
        """Custom query: Get loans by borrower."""
        return db.query(self.model).filter(
            self.model.borrower_name == borrower_name,
            self.model.deleted_at.is_(None)
        ).all()
```

#### 3. Service Layer (Business Logic)

```python
# app/services/loan_service.py
from typing import List
from sqlalchemy.orm import Session
from app.repositories.loan_repository import LoanRepository
from app.schemas.loan import LoanCreate, LoanUpdate, LoanResponse
from app.models.loan import Loan
from app.core.logging import get_logger

logger = get_logger(__name__)

class LoanService:
    """Business logic for loan operations."""

    def __init__(self):
        self.repository = LoanRepository()

    def create_loan(self, db: Session, loan_data: LoanCreate) -> LoanResponse:
        """Create new loan with validation and audit logging."""
        # Validation
        if loan_data.due_date < loan_data.giving_date:
            raise ValueError("Due date cannot be before giving date")

        # Create loan
        loan = Loan(**loan_data.dict())
        created_loan = self.repository.create(db, loan)

        # Audit log
        logger.info("loan_created", loan_id=str(created_loan.id),
                   borrower=created_loan.borrower_name)

        return LoanResponse.from_orm(created_loan)

    def delete_loan(self, db: Session, loan_id: str) -> bool:
        """Soft delete loan record."""
        success = self.repository.soft_delete(db, loan_id)
        if success:
            logger.info("loan_deleted", loan_id=loan_id)
        return success

loan_service = LoanService()
```

#### 4. Pydantic Schemas (Data Transfer Objects)

```python
# app/schemas/loan.py
from pydantic import BaseModel, Field, validator
from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional

class LoanBase(BaseModel):
    """Base schema with common fields."""
    borrower_name: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    depositor_name: str = Field(..., min_length=1, max_length=100)
    giving_date: date
    due_date: date
    borrower_group: Optional[str] = Field(None, max_length=50)
    depositor_group: Optional[str] = Field(None, max_length=50)

    @validator('due_date')
    def due_date_after_giving_date(cls, v, values):
        """Ensure due date is after giving date."""
        if 'giving_date' in values and v < values['giving_date']:
            raise ValueError('Due date must be after giving date')
        return v

class LoanCreate(LoanBase):
    """Schema for creating loan (request)."""
    pass

class LoanUpdate(BaseModel):
    """Schema for updating loan (partial updates allowed)."""
    amount: Optional[Decimal] = None
    due_date: Optional[date] = None
    status: Optional[str] = None

class LoanResponse(LoanBase):
    """Schema for loan response (includes generated fields)."""
    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True  # Allow ORM model conversion
```

#### 5. Error Handling

```python
# app/core/exceptions.py
class LoanTrackerException(Exception):
    """Base exception for application."""
    pass

class LoanNotFoundException(LoanTrackerException):
    """Raised when loan record not found."""
    pass

class ValidationException(LoanTrackerException):
    """Raised when validation fails."""
    pass

# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

@app.exception_handler(LoanNotFoundException)
async def loan_not_found_handler(request: Request, exc: LoanNotFoundException):
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)}
    )

@app.exception_handler(ValidationException)
async def validation_handler(request: Request, exc: ValidationException):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)}
    )
```

#### 6. Structured Logging

```python
# app/core/logging.py
import structlog
from pathlib import Path

def configure_logging(log_level: str = "INFO"):
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str):
    """Get logger instance."""
    return structlog.get_logger(name)

# Usage
logger = get_logger(__name__)
logger.info("event_occurred", user_id="123", action="create_loan")
logger.error("error_occurred", error=str(e), loan_id=loan_id)
```

### Testing Standards

#### Unit Tests (pytest)

```python
# tests/unit/test_loan_service.py
import pytest
from app.services.loan_service import LoanService
from app.schemas.loan import LoanCreate
from datetime import date, timedelta

@pytest.fixture
def loan_service():
    return LoanService()

@pytest.fixture
def valid_loan_data():
    return LoanCreate(
        borrower_name="John Doe",
        amount=1000.00,
        depositor_name="Jane Smith",
        giving_date=date.today(),
        due_date=date.today() + timedelta(days=30)
    )

def test_create_loan_success(loan_service, db_session, valid_loan_data):
    """Test successful loan creation."""
    loan = loan_service.create_loan(db_session, valid_loan_data)
    assert loan.borrower_name == "John Doe"
    assert loan.amount == 1000.00

def test_create_loan_invalid_dates(loan_service, db_session):
    """Test loan creation with invalid dates."""
    invalid_data = LoanCreate(
        borrower_name="John Doe",
        amount=1000.00,
        depositor_name="Jane Smith",
        giving_date=date.today(),
        due_date=date.today() - timedelta(days=1)  # Invalid
    )
    with pytest.raises(ValueError):
        loan_service.create_loan(db_session, invalid_data)
```

#### Integration Tests

```python
# tests/integration/test_loan_api.py
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_loan_endpoint():
    """Test loan creation via API."""
    response = client.post("/api/v1/loans", json={
        "borrower_name": "John Doe",
        "amount": 1000.00,
        "depositor_name": "Jane Smith",
        "giving_date": "2025-01-01",
        "due_date": "2025-02-01"
    })
    assert response.status_code == 201
    assert response.json()["borrower_name"] == "John Doe"

def test_get_loans_endpoint():
    """Test retrieving loans."""
    response = client.get("/api/v1/loans")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
```

### Security Patterns

#### 1. Input Sanitization

```python
# app/utils/validators.py
import re
from typing import Optional

def sanitize_string(value: str, max_length: int = 100) -> str:
    """Remove potentially harmful characters from string input."""
    # Remove control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value)
    # Trim whitespace
    sanitized = sanitized.strip()
    # Enforce max length
    return sanitized[:max_length]

def validate_amount(amount: Decimal) -> bool:
    """Validate monetary amount."""
    return amount > 0 and amount < Decimal('999999999.99')
```

#### 2. Encryption Utilities

```python
# app/utils/encryption.py
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import base64

class EncryptionManager:
    """Handle encryption/decryption operations."""

    def __init__(self, master_password: str, salt: bytes):
        self.key = self._derive_key(master_password, salt)
        self.cipher = Fernet(self.key)

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2."""
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data."""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
```

#### 3. SQL Injection Prevention

```python
# ALWAYS use ORM or parameterized queries

# ✅ GOOD: Using SQLAlchemy ORM
loans = db.query(Loan).filter(Loan.borrower_name == user_input).all()

# ✅ GOOD: Parameterized query
loans = db.execute(
    "SELECT * FROM loans WHERE borrower_name = :name",
    {"name": user_input}
).fetchall()

# ❌ BAD: String concatenation (NEVER DO THIS)
loans = db.execute(f"SELECT * FROM loans WHERE borrower_name = '{user_input}'")
```

## Code Quality Tools

### Linting and Formatting
```bash
# Install dev dependencies
pip install black flake8 isort mypy bandit safety

# Auto-format code
black app/ tests/

# Sort imports
isort app/ tests/

# Lint code
flake8 app/ tests/

# Type checking
mypy app/

# Security scanning
bandit -r app/
safety check
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.0
    hooks:
      - id: mypy
```

## Performance Patterns

### Database Optimization

```python
# Use eager loading to avoid N+1 queries
from sqlalchemy.orm import joinedload

loans = db.query(Loan).options(
    joinedload(Loan.borrower)
).all()

# Create indexes for frequent queries
class Loan(Base):
    __tablename__ = "loans"

    borrower_name = Column(String, index=True)  # Indexed
    due_date = Column(Date, index=True)         # Indexed
    status = Column(String, index=True)         # Indexed
```

### Caching (Future Enhancement)

```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_borrower_stats(borrower_name: str) -> dict:
    """Cache expensive statistical calculations."""
    # Compute stats
    return stats
```

## Documentation Standards

### API Documentation (OpenAPI/Swagger)
```python
@router.post("/loans", response_model=LoanResponse, status_code=201)
async def create_loan(
    loan: LoanCreate,
    db: Session = Depends(get_db)
) -> LoanResponse:
    """
    Create a new loan record.

    Args:
        loan: Loan data including borrower, amount, dates
        db: Database session (injected)

    Returns:
        Created loan record with generated ID

    Raises:
        ValidationException: If loan data is invalid
        DatabaseException: If database operation fails

    Example:
        ```json
        {
            "borrower_name": "John Doe",
            "amount": 1000.00,
            "depositor_name": "Jane Smith",
            "giving_date": "2025-01-01",
            "due_date": "2025-02-01"
        }
        ```
    """
    return loan_service.create_loan(db, loan)
```

### Function Docstrings (Google Style)
```python
def calculate_interest(principal: Decimal, rate: float, days: int) -> Decimal:
    """
    Calculate simple interest for a loan.

    Args:
        principal: Loan principal amount in currency units
        rate: Annual interest rate as decimal (e.g., 0.05 for 5%)
        days: Number of days to calculate interest for

    Returns:
        Interest amount rounded to 2 decimal places

    Raises:
        ValueError: If principal is negative or rate is invalid

    Example:
        >>> calculate_interest(Decimal('1000'), 0.05, 365)
        Decimal('50.00')
    """
    if principal < 0:
        raise ValueError("Principal cannot be negative")
    if not 0 <= rate <= 1:
        raise ValueError("Rate must be between 0 and 1")

    interest = principal * Decimal(str(rate)) * Decimal(days) / Decimal('365')
    return interest.quantize(Decimal('0.01'))
```

## Code Review Checklist

- [ ] Code follows PEP 8 style guide
- [ ] All functions have type hints
- [ ] All public functions have docstrings
- [ ] Unit tests cover new functionality (min 80% coverage)
- [ ] No hardcoded credentials or secrets
- [ ] Input validation implemented
- [ ] Error handling implemented
- [ ] Logging added for important operations
- [ ] No SQL injection vulnerabilities
- [ ] No XSS vulnerabilities (backend validation)
- [ ] Database migrations created (if schema changed)
- [ ] API documentation updated (if endpoints changed)

---

**Last Updated**: 2026-03-07
**Status**: Draft - Awaiting Review
