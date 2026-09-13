# Loan Manager -- Platform and Python Compatibility

## Python Version Compatibility

| Python Version | Support Level | Notes |
|---|---|---|
| 3.10 | Supported (minimum) | All features work |
| 3.11 | Supported | Recommended for best performance |
| 3.12 | Supported | `datetime.utcnow()` deprecation resolved |
| 3.13 | Supported | Requires PySide6 >= 6.8.0 |
| 3.14 | Untested | Monitor PySide6 release notes |

## Platform Compatibility

| Platform | Status | Notes |
|---|---|---|
| Windows 10/11 | Supported | Primary target platform |
| macOS 12+ (Intel & Apple Silicon) | Supported | Popup rendering uses deferred render for compositor compatibility |
| Linux (Ubuntu 22.04+) | Untested | PySide6 available; should work |

## PySide6 Requirements

- **Minimum version**: 6.8.0
- Python 3.13 support was added in PySide6 6.8.0.
- Earlier versions (6.6.x, 6.7.x) work with Python 3.10-3.12 only.

## Key Dependency Versions

| Package | Minimum Version | Reason |
|---|---|---|
| PySide6 | 6.8.0 | Python 3.13 support |
| SQLAlchemy | 2.0.0 | Modern ORM API |
| alembic | 1.13.0 | Python 3.12+ compatible |
| pydantic | 2.5.0 | Python 3.13 compatible |
| python-dateutil | 2.8.2 | Stable date arithmetic |
| openpyxl | 3.1.2 | Python 3.12+ compatible |
| pytest | 8.0.0 | Python 3.12+ test discovery |
| pytest-cov | 5.0.0 | Compatible with pytest 8+ |

## Known Limitations

- macOS popup windows (`Qt.WindowType.Popup`) require deferred rendering
  via `QTimer.singleShot(0, ...)` to ensure proper visual state after `show()`.
- Python 3.14 support depends on PySide6 releasing a compatible version.
