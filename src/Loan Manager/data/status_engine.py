"""Re-export from loan_manager.status_engine.

The authoritative implementation lives in loan_manager/status_engine.py.
This module is the application-layer adapter: UI code imports from here.
"""
from loan_manager.status_engine import (  # noqa: F401
    LoanDict,
    LoanLike,
    compute_status,
    recompute_all,
)

__all__ = ["compute_status", "recompute_all", "LoanDict", "LoanLike"]
