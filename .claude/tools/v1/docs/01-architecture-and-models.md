# Architecture and Model Decisions

## System Overview

A production-ready Loan Tracker System with Python backend, React frontend, and secure data storage capabilities. Designed for easy deployment and use by non-technical users.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User's Local Machine                     │
│                                                               │
│  ┌──────────────────┐         ┌──────────────────────────┐  │
│  │  React Frontend  │────────▶│   Python Backend API     │  │
│  │   (Port 3000)    │◀────────│   Flask/FastAPI          │  │
│  │                  │         │   (Port 8000)            │  │
│  └──────────────────┘         └──────────────────────────┘  │
│                                         │                     │
│                                         ▼                     │
│                         ┌───────────────────────────┐        │
│                         │   Storage Layer           │        │
│                         │   - Encrypted SQLite DB   │        │
│                         │   - CSV Export/Backup     │        │
│                         └───────────────────────────┘        │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Monitoring & Logging                         │   │
│  │         - Application Logs (Rotating Files)          │   │
│  │         - Optional: Prometheus Metrics               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Backend
- **Framework**: FastAPI (modern, async, auto-documentation)
- **Database**: SQLite with SQLCipher for encryption
- **ORM**: SQLAlchemy (database abstraction, migrations)
- **Validation**: Pydantic (data validation, type safety)
- **Security**: python-jose (JWT tokens), passlib (password hashing)
- **Logging**: structlog (structured logging)

### Frontend
- **Framework**: React 18+ with TypeScript
- **UI Library**: Material-UI (MUI) or Ant Design (consistent, professional UI)
- **State Management**: React Query (server state) + Context API (local state)
- **Forms**: React Hook Form + Yup validation
- **HTTP Client**: Axios with interceptors

### Deployment & DevOps
- **Containerization**: Docker (multi-stage builds)
- **Orchestration**: Docker Compose (simpler than K8s for single-user deployment)
- **Distribution**: Single executable via PyInstaller + bundled React build

### Phase 2 Considerations (Future)
- **Kubernetes**: For multi-user/enterprise deployment
- **AI Agents**: LangChain for report generation, insights, payment predictions

## Data Model

### Core Entity: Loan Record

```python
class LoanRecord:
    id: UUID                      # Primary key
    borrower_name: str            # Required
    amount: Decimal               # Required, precision for currency
    depositor_name: str           # Required (lender/depositor)
    giving_date: date             # Required (loan disbursement date)
    due_date: date                # Optional default=1970-01-01
    borrower_group: str           # Optional categorization
    depositor_group: str          # Optional categorization
    status: LoanStatus            # ACTIVE, PAID_OFF, OVERDUE
    created_at: datetime          # Auto-generated
    updated_at: datetime          # Auto-updated
    deleted_at: datetime | None   # Soft delete timestamp
    audit_trail: JSON             # Change history
```

### Enums
```python
class LoanStatus(Enum):
    ACTIVE = "active"
    PAID_OFF = "paid_off"
    OVERDUE = "overdue"
```

### Supporting Tables (Future Enhancement)
```python
class Borrower:
    id: UUID
    name: str
    contact: str
    group: str

class Depositor:
    id: UUID
    name: str
    contact: str
    group: str
```

## Data Storage Architecture

### Recommended Approach: Encrypted SQLite + Backup Strategy

#### Primary Storage: SQLite with SQLCipher
- **Rationale**:
  - File-based, portable, zero-configuration
  - SQLCipher provides AES-256 encryption at rest
  - ACID compliance for data integrity
  - Suitable for single-user/small team usage

- **Implementation**:
  ```python
  # Database URL with encryption key
  DATABASE_URL = "sqlite+pysqlcipher:///:memory:?cipher=aes-256-cbc&key=<user-key>"
  ```

- **Key Management**:
  - User sets master password on first run
  - Key derivation using PBKDF2 (100,000 iterations)
  - Store derived key in OS keyring (keyring library)

#### Backup Strategy
1. **Automated Encrypted Backups**:
   - Daily backup to `backups/` directory
   - Encrypted with same master key
   - Retention: Keep last 30 days

2. **CSV Export (User-Initiated)**:
   - Generate encrypted CSV for external analysis
   - Option to export decrypted CSV (with warning)
   - Excel-compatible format (UTF-8 BOM)

#### Alternative Approaches Considered

| Approach | Pros | Cons | Verdict |
|----------|------|------|---------|
| **Encrypted CSV Only** | Simple, Excel-compatible | No relational integrity, poor query performance | ❌ Not recommended |
| **PostgreSQL + Docker** | Production-grade, scalable | Overkill for single-user, complex setup | ⚠️ Phase 2 option |
| **Cloud Storage (AWS S3 + encryption)** | Offsite backup, accessible | Network dependency, privacy concerns, cost | ⚠️ Optional enhancement |
| **SQLite + Encryption** | Balanced, portable, secure | Limited concurrency (not an issue here) | ✅ **Recommended** |

## Security Architecture

### Data Security Measures

1. **Encryption at Rest**:
   - Database: AES-256 via SQLCipher
   - Backups: AES-256 via cryptography library
   - CSV exports: Optional GPG encryption

2. **Encryption in Transit**:
   - HTTPS for API (self-signed cert for local, Let's Encrypt for remote)
   - TLS 1.3 minimum

3. **Authentication & Authorization**:
   - Simple password protection for single-user mode
   - JWT tokens for session management
   - Password requirements: min 12 chars, complexity rules

4. **Input Validation**:
   - Pydantic models for all API inputs
   - SQL injection prevention via ORM (parameterized queries)
   - XSS prevention via React auto-escaping + CSP headers

5. **Audit Trail**:
   - All CRUD operations logged
   - Immutable audit log (append-only)
   - Tracks: who, what, when, IP address

6. **Soft Deletes**:
   - Records never truly deleted (set `deleted_at` timestamp)
   - Maintain data integrity for historical reports
   - Permanent deletion requires admin action + confirmation

### Secure Coding Practices
- Dependency scanning: `safety`, `bandit`
- SAST: SonarQube or CodeQL
- Secrets management: Environment variables, never hardcoded
- Principle of least privilege

## Non-Functional Requirements

### User Experience (Critical Priority)
- **Ease of Installation**:
  - Zero-friction setup for non-technical users
  - Graceful handling of missing dependencies
  - Clear, actionable error messages
  - Fallback modes when optional dependencies unavailable

- **Dependency Resilience**:
  - **Core principle**: System must function with minimal dependencies
  - **Optional dependencies**: pandas (CSV performance), cryptography (encryption)
  - **Graceful degradation**: Auto-detect and fallback to built-in alternatives
  - **Clear messaging**: Inform users about missing features, not technical errors

- **Error Communication**:
  - User-friendly error messages (no stack traces to end users)
  - Suggest specific fixes: "Install X" or "Set Y to empty in .env"
  - Log technical details for debugging (separate from user-facing messages)
  - Prevent startup with clear guidance if configuration conflicts exist

### Dependency Management Strategy
- **Required (Core)**:
  - fastapi, uvicorn (API server)
  - pydantic (validation)
  - python-dotenv (configuration)
  - structlog (logging)

- **Optional (Degradable)**:
  - pandas → fallback to built-in csv module
  - cryptography → disable encryption, warn user clearly
  - SQLAlchemy → only needed for SQLite mode

- **Installation Approach**:
  1. Install minimal core dependencies first
  2. Attempt optional dependencies separately
  3. Continue on optional dependency failure
  4. Validate configuration matches available dependencies
  5. Fail fast with clear guidance if mismatch detected

### Logging
- **Framework**: structlog (structured JSON logs)
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Outputs**:
  - Console (development) - user-friendly messages only
  - Rotating file handler (production, 10MB max, 5 backups) - technical details
- **Contents**: timestamp, level, message, context (user_id, request_id)
- **Error Logging Strategy**:
  - Log all dependency import failures with context
  - Track configuration validation failures
  - Record graceful fallback activations
  - Separate user-facing messages from technical logs

### Monitoring (Optional for Phase 1)
- **Metrics**: Prometheus + Grafana
  - Request latency
  - Error rates
  - Database query performance
  - Dependency availability tracking
- **Health Checks**: `/health` endpoint (DB connection, disk space, dependency status)

### Performance
- **Response Time**: < 200ms for API calls
- **Database**: Indexed columns (borrower_name, due_date, status)
- **Frontend**: Code splitting, lazy loading
- **Degraded Performance Modes**:
  - Built-in CSV module: 5-10% slower than pandas (acceptable for <10k records)
  - No encryption: Same performance as encrypted

### Reliability
- **Backups**: Automated daily backups
- **Data Validation**: Client + server-side validation
- **Error Handling**: Graceful degradation, user-friendly messages
- **Startup Validation**:
  - Check dependency availability
  - Validate configuration consistency
  - Fail fast with actionable guidance
  - Never start in broken state

### Scalability (Phase 2)
- Horizontal scaling via Kubernetes
- PostgreSQL migration for multi-user
- Redis caching for reports

## Deployment Architecture

### Phase 1: Standalone Desktop Application

```
┌─────────────────────────────────────┐
│  LoanTracker.exe / LoanTracker.app  │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  Embedded Python Backend    │   │
│  │  (PyInstaller bundle)       │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  Static React Build         │   │
│  │  (Served by FastAPI)        │   │
│  └─────────────────────────────┘   │
│                                     │
│  ┌─────────────────────────────┐   │
│  │  SQLite DB (encrypted)      │   │
│  │  Location: ~/LoanTracker/   │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
```

- **Distribution**: Single executable via PyInstaller
- **Installation**: Drag-and-drop (macOS), Installer wizard (Windows)
- **Updates**: Built-in update checker (GitHub releases)

### Phase 2: Docker Compose (Advanced Users)

```yaml
version: '3.8'
services:
  backend:
    image: loantracker-backend:latest
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - DB_ENCRYPTION_KEY=${DB_ENCRYPTION_KEY}

  frontend:
    image: loantracker-frontend:latest
    ports:
      - "3000:80"
    depends_on:
      - backend
```

### Phase 3: Kubernetes (Enterprise)
- Helm charts for deployment
- Persistent volumes for database
- Ingress for HTTPS
- HPA (Horizontal Pod Autoscaler)

## AI/Agent Integration (Phase 2)

### Potential Use Cases
1. **Report Generation Agent**:
   - Natural language queries: "Show me overdue loans from Q1 2025"
   - Automated insights: "Borrower X has 3 active loans totaling $15,000"

2. **Payment Prediction**:
   - ML model to predict default risk based on historical patterns
   - Alerting system for high-risk loans

3. **Data Entry Assistance**:
   - OCR for loan document scanning
   - Auto-fill suggestions based on historical data

### Technology Options
- **LangChain**: For LLM orchestration, retrieval-augmented generation
- **LangGraph**: For complex multi-agent workflows
- **Hugging Face Transformers**: Local NLP models (privacy-preserving)

### Implementation Approach
- Start with simple rule-based alerts
- Phase 2: Integrate GPT-4 API for report generation
- Phase 3: Fine-tuned local models for privacy

## Migration Path

### V1.0 (Current Scope)
- CRUD operations (Create, Read, Update, Delete)
- Excel export
- Basic reporting (filter by borrower, date range, status)
- Encrypted SQLite storage
- Docker packaging

### V1.5 (3-6 months)
- Advanced filtering and search
- Dashboard with charts (Chart.js or Recharts)
- Email notifications for due dates
- Multi-user support (role-based access)

### V2.0 (6-12 months)
- AI-powered insights
- Mobile app (React Native)
- Cloud sync option (opt-in)
- API integrations (accounting software)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Data loss | Medium | Critical | Automated backups, soft deletes |
| Security breach | Low | Critical | Encryption, security audits |
| User adoption issues | Medium | High | Simple UI, comprehensive docs, graceful dependency handling |
| Performance degradation | Low | Medium | Indexing, query optimization |
| Dependency vulnerabilities | Medium | High | Regular updates, scanning |
| **Dependency installation failures** | **High** | **Critical** | **Multi-layer fallback strategy, minimal core dependencies** |
| **Configuration mismatches** | **Medium** | **High** | **Startup validation, clear error messages** |
| **Poor error messaging** | **High** | **Medium** | **User-friendly errors, separate logging channels** |

## Dependency Resolution Strategy (Critical NFR)

### Problem Statement
Python package installation can fail due to:
- Missing system dependencies (compilers, build tools)
- Platform-specific compilation issues
- Version conflicts between packages
- Network/package index issues

**Impact on UX**: Installation failure = No demo, frustrated users, poor adoption

### Multi-Layer Mitigation Strategy

#### Layer 1: Minimal Core Dependencies
```python
# requirements-minimal.txt - MUST install successfully
fastapi>=0.100.0      # Pure Python, always works
uvicorn>=0.20.0       # Pure Python, always works
pydantic>=2.0.0       # Pure Python, always works
structlog>=23.0.0     # Pure Python, always works
```

**Guarantee**: These packages have pre-built wheels for all platforms

#### Layer 2: Optional Dependencies with Fallbacks
```python
# Installed separately, failure is acceptable
pandas>=2.0.0         # Fallback: built-in csv module
cryptography>=41.0.0  # Fallback: disable encryption
```

**Implementation**:
```python
# storage_service.py
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    # Use csv_storage.py instead

if HAS_PANDAS:
    storage_service = StorageService()  # pandas-based
else:
    storage_service = CSVStorageService()  # built-in csv
```

#### Layer 3: Configuration Validation
```python
# At startup, validate configuration matches capabilities
if settings.encryption_key and not ENCRYPTION_AVAILABLE:
    raise ConfigurationError(
        "Encryption key provided but cryptography not installed.\n"
        "Fix: pip install cryptography\n"
        "Or: Set ENCRYPTION_KEY= (empty) in .env"
    )
```

#### Layer 4: User-Friendly Error Messages

**Bad (Technical)**:
```
ImportError: cannot import name 'PBKDF2' from 'cryptography.hazmat.primitives.kdf.pbkdf2'
```

**Good (Actionable)**:
```
⚠️  Encryption not available: cryptography library not installed

Cannot start with encryption enabled.

Fix this by choosing ONE option:

  Option 1: Install cryptography
    pip install cryptography

  Option 2: Disable encryption
    Edit .env and set: ENCRYPTION_KEY=

Current setting in .env: ENCRYPTION_KEY=my_password

For support, see TROUBLESHOOTING.md
```

### Installation Flow

```
start-dev.sh
    ↓
1. Install minimal core (MUST succeed)
    ├─ Success → Continue
    └─ Failure → Exit with clear error
    ↓
2. Try install cryptography
    ├─ Success → Log "Encryption available"
    └─ Failure → Log "Encryption disabled", set flag
    ↓
3. Try install pandas
    ├─ Success → Log "Using pandas for CSV"
    └─ Failure → Log "Using built-in CSV module", set flag
    ↓
4. Validate configuration
    ├─ ENCRYPTION_KEY set + no cryptography → FAIL with guidance
    ├─ STORAGE_TYPE=sqlite + no sqlalchemy → FAIL with guidance
    └─ Valid → Continue
    ↓
5. Start server
```

### Logging Strategy for Dependencies

```python
# Good: Separate technical logs from user messages

# User-facing (console)
print("⚠️  Pandas installation skipped (will use built-in CSV module)")
print("   App will work fine without pandas!")

# Technical (log file)
logger.warning(
    "pandas_unavailable",
    error=str(import_error),
    fallback="csv_module",
    performance_impact="5-10%_slower",
    max_recommended_records=10000
)
```

### Error Message Guidelines

1. **User-Facing Errors** (Console):
   - Use symbols: ✅ ❌ ⚠️
   - Plain English, no jargon
   - Provide exact commands to fix
   - Offer alternatives
   - Reference documentation

2. **Technical Logs** (File):
   - Full stack traces
   - Import errors verbatim
   - System context (OS, Python version)
   - Configuration state
   - Structured JSON for parsing

## Open Questions for Review

1. **Master Password Management**: Should we implement password recovery? Not yet
2. **Multi-tenancy**: Will multiple users ever need to access the same database? Not yet
3. **Cloud Backup**: Do you want optional cloud backup (encrypted)? potentially as a future MVP
4. **Reporting Complexity**: What specific reports are needed beyond basic filtering? More details to come from user after initial demo
5. **Kubernetes**: Is K8s truly needed for Phase 1, or should we defer to Phase 2? not needed for phase1

## Recommendations

### For First Iteration (MVP)
1. **Simplify Deployment**: Use Docker Compose instead of Kubernetes
2. **Focus on Core CRUD**: Defer AI agents to Phase 2
3. **Prioritize Security**: Implement encryption from day one
4. **User Experience**: Invest in intuitive UI, comprehensive onboarding
5. **Documentation**: Write clear README, setup guide, user manual

### Technology Choices
- ✅ FastAPI (over Flask for better performance, async support)
- ✅ SQLite + SQLCipher (over PostgreSQL for simplicity)
- ✅ Docker Compose (over Kubernetes for MVP)
- ✅ TypeScript (over JavaScript for type safety)
- ⏸️ Defer LangChain/AI to Phase 2

---

**Last Updated**: 2026-03-07
**Status**: Draft - Awaiting Review
