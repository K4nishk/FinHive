"""ReportDTO actor-required unit test (KCH-242 review cycle 1, MAJOR;
cycle 2 test gap, MINOR-3).

`ReportDTO.actor` (application/dtos/report_dto.py) is intentionally a
required field with NO default: a defaulted `actor: ReportActor =
ReportActor.FORM` let a call site that forgot to map `actor` silently
mislabel an AGENT report as FORM (GetPendingReports did exactly this before
the cycle-1 fix). Nothing in the suite constructs `ReportDTO` without
`actor` and checks it raises, so a regression back to a defaulted field
would pass silently. This is that check.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from loan_manager.application.dtos.report_dto import ReportDTO
from loan_manager.domain.value_objects.status import CalculationMode, ReportStatus
from pydantic import ValidationError

_NOW = datetime(2026, 3, 15, 12, 0, 0)


def test_report_dto_requires_actor_explicitly():
    with pytest.raises(ValidationError, match="actor"):
        ReportDTO(
            id=1,
            report_id="RPT_20260315_001",
            report_mode=CalculationMode.MONTHLY,
            status=ReportStatus.PENDING,
            records=[],
            created_at=_NOW,
            updated_at=_NOW,
            # actor deliberately omitted
        )
