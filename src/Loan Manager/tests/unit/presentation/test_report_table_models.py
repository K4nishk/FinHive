"""KCH-245: ReportListModel/ReportRecordModel are QAbstractTableModel, never
QTableWidget (hard rule). No QApplication is constructed here -- these are
plain data objects (verified: QColor/QBrush/QFont/QAbstractTableModel all
construct fine without one under QT_QPA_PLATFORM=offscreen)."""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

import pytest
from loan_manager.application.dtos.loan_dto import LoanDTO
from loan_manager.application.dtos.report_dto import ReportDTO, ReportRecordDTO
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    LoanStatus,
    ReportActor,
    ReportStatus,
)
from loan_manager.presentation.themes.theme_manager import THEMES_DIR
from loan_manager.presentation.widgets.report_table_models import (
    REC_COL_IDX,
    REPORT_COL_IDX,
    ReportListModel,
    ReportRecordModel,
)
from PySide6.QtCore import QSortFilterProxyModel, Qt


class _FakeTheme:
    """Mirrors ThemeManager.get_badge_colour/get_status_colour's shape
    without needing apply_theme()+QApplication."""

    _BADGES = {
        "AGENT": {"background": "#5b2a86", "text": "#ffffff", "bold": True},
        "FORM": {"background": "#1f4e5f", "text": "#ffffff", "bold": True},
        "CONFLICT": {"background": "#8a5300", "text": "#ffffff", "bold": True},
    }

    def get_badge_colour(self, key: str) -> dict:
        return self._BADGES.get(key, {"background": "#888888", "text": "#ffffff", "bold": False})

    def get_status_colour(self, status: str) -> dict:
        return {"background": "#888888", "text": "#ffffff", "bold": False}


def _report(
    report_id="RPT_20260410_001",
    actor=ReportActor.FORM,
    mode=CalculationMode.MONTHLY,
    records=None,
    conflict_ref_ids=None,
) -> ReportDTO:
    now = datetime(2026, 4, 10, 12, 0)
    return ReportDTO(
        id=1,
        report_id=report_id,
        report_mode=mode,
        status=ReportStatus.PENDING,
        records=records or [],
        created_at=now,
        updated_at=now,
        actor=actor,
        user_request="lend 5000 to ravi" if actor == ReportActor.AGENT else None,
        turn_id="turn-1" if actor == ReportActor.AGENT else None,
        conflict_ref_ids=conflict_ref_ids or [],
    )


def _record(**overrides) -> ReportRecordDTO:
    base = dict(
        id=1,
        report_id="RPT_20260410_001",
        reference_id="2026_01_001",
        borrower_name="ravi",
        depositor_name="meena",
        depositor_group=None,
        amount=10000,
        giving_date=date(2026, 1, 1),
        due_date=date(2026, 4, 1),
        extension_period=3,
        extension_period_unit=ExtensionPeriodUnit.MONTHS,
        interest_rate=Decimal("12"),
        commission_rate=Decimal("6"),
        tds_flag=False,
        interest_amount=Decimal("300.00"),
        commission_amount=Decimal("150.00"),
        tds_amount=Decimal("0.00"),
        chq_amount=Decimal("300.00"),
        post_extension_giving_date=date(2026, 4, 1),
        post_extension_due_date=date(2026, 7, 1),
        paidoff_date=None,
        borrower_group="bg1",
        due_period=None,
    )
    base.update(overrides)
    return ReportRecordDTO(**base)


def _create_row_record(**overrides) -> ReportRecordDTO:
    """CREATE-mode row convention (KCH-242): reference_id/giving_date/
    due_date/rates/derived amounts are all None until approval."""
    base = dict(
        id=2,
        report_id="RPT_20260410_002",
        reference_id=None,
        borrower_name="new borrower",
        depositor_name="depositor",
        depositor_group=None,
        amount=15000,
        giving_date=None,
        due_date=None,
        extension_period=0,
        extension_period_unit=ExtensionPeriodUnit.MONTHS,
        interest_rate=Decimal("0"),
        commission_rate=Decimal("0"),
        tds_flag=False,
        interest_amount=None,
        commission_amount=None,
        tds_amount=None,
        chq_amount=None,
        post_extension_giving_date=date(2026, 4, 10),
        post_extension_due_date=date(2026, 7, 10),
        paidoff_date=None,
        borrower_group="new-group",
        due_period=3,
    )
    base.update(overrides)
    return ReportRecordDTO(**base)


def _loan(**overrides) -> LoanDTO:
    now = datetime(2026, 1, 1)
    base = dict(
        id=1,
        reference_id="2026_01_001",
        borrower_name="old name",
        borrower_group="bg1",
        depositor_name="old depositor",
        depositor_group="dg1",
        amount=9000,
        giving_date=date(2026, 1, 1),
        due_period=None,
        due_date=date(2026, 4, 1),
        status=LoanStatus.ACTIVE,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    base.update(overrides)
    return LoanDTO(**base)


def _idx(model, row, col_name, col_map):
    return model.index(row, col_map[col_name])


class TestBadgesAreVisuallyDistinct:
    """ACCEPTANCE 1: agent and form batches are visually distinguishable."""

    def test_agent_and_form_badges_are_visually_distinct(self):
        model = ReportListModel(_FakeTheme())
        agent_report = _report(report_id="RPT_A", actor=ReportActor.AGENT)
        form_report = _report(report_id="RPT_B", actor=ReportActor.FORM)
        model.load([agent_report, form_report])

        agent_idx = _idx(model, 0, "Author", REPORT_COL_IDX)
        form_idx = _idx(model, 1, "Author", REPORT_COL_IDX)

        agent_bg = model.data(agent_idx, Qt.ItemDataRole.BackgroundRole)
        form_bg = model.data(form_idx, Qt.ItemDataRole.BackgroundRole)

        assert agent_bg is not None and form_bg is not None
        assert agent_bg.color().name() != form_bg.color().name(), (
            "AGENT and FORM badges must render with different colours"
        )
        # And the label text itself already distinguishes them, colour aside.
        assert model.data(agent_idx, Qt.ItemDataRole.DisplayRole) == "AGENT"
        assert model.data(form_idx, Qt.ItemDataRole.DisplayRole) == "FORM"


class TestCreateRowRendersWithoutNone:
    def test_create_row_renders_without_none(self):
        model = ReportRecordModel(_FakeTheme())
        rec = _create_row_record()
        model.load([rec], CalculationMode.CREATE)

        for col in range(model.columnCount()):
            index = model.index(0, col)
            value = model.data(index, Qt.ItemDataRole.DisplayRole)
            assert value is not None, f"column {col} rendered a bare None"
            assert value != "None", f"column {col} rendered the string 'None'"

        ref_idx = _idx(model, 0, "Ref ID", REC_COL_IDX)
        assert model.data(ref_idx, Qt.ItemDataRole.DisplayRole) == "(new)"


class TestUpdateRowShowsCurrentAndProposed:
    def test_update_row_shows_current_and_proposed(self):
        model = ReportRecordModel(_FakeTheme())
        rec = _record(
            reference_id="2026_01_001",
            borrower_name="new name",
            amount=20000,
        )
        current_loan = _loan(reference_id="2026_01_001", borrower_name="old name", amount=9000)
        model.load(
            [rec], CalculationMode.UPDATE,
            current_loans={"2026_01_001": current_loan},
        )

        b_name_idx = _idx(model, 0, "B Name", REC_COL_IDX)
        current_b_name_idx = _idx(model, 0, "Current B Name", REC_COL_IDX)
        amount_idx = _idx(model, 0, "Amount", REC_COL_IDX)
        current_amount_idx = _idx(model, 0, "Current Amount", REC_COL_IDX)

        assert model.data(b_name_idx, Qt.ItemDataRole.DisplayRole) == "new name"
        assert model.data(current_b_name_idx, Qt.ItemDataRole.DisplayRole) == "old name"
        assert model.data(amount_idx, Qt.ItemDataRole.DisplayRole) == "20000"
        assert model.data(current_amount_idx, Qt.ItemDataRole.DisplayRole) == "9000"

        # Proposed value differs from current -> bolded (R1 decision).
        font = model.data(b_name_idx, Qt.ItemDataRole.FontRole)
        assert font.bold() is True

    def test_update_row_missing_current_loan_shows_not_active(self):
        model = ReportRecordModel(_FakeTheme())
        rec = _record(reference_id="2026_01_099")
        model.load([rec], CalculationMode.UPDATE, current_loans={})

        current_b_name_idx = _idx(model, 0, "Current B Name", REC_COL_IDX)
        assert model.data(current_b_name_idx, Qt.ItemDataRole.DisplayRole) == "(loan not active)"

    def test_non_update_row_current_columns_are_not_applicable(self):
        model = ReportRecordModel(_FakeTheme())
        rec = _record()
        model.load([rec], CalculationMode.MONTHLY)

        current_b_name_idx = _idx(model, 0, "Current B Name", REC_COL_IDX)
        assert model.data(current_b_name_idx, Qt.ItemDataRole.DisplayRole) == "N/A"


class TestCreateAndUpdateRowsAreReadOnly:
    def test_create_and_update_rows_are_read_only(self):
        editable_cols = ["Rate %", "Comm %", "Period", "Unit", "TDS"]

        for mode, rec in (
            (CalculationMode.CREATE, _create_row_record()),
            (CalculationMode.UPDATE, _record()),
        ):
            model = ReportRecordModel(_FakeTheme())
            model.load([rec], mode)
            for col_name in editable_cols:
                index = _idx(model, 0, col_name, REC_COL_IDX)
                flags = model.flags(index)
                assert not (flags & Qt.ItemFlag.ItemIsEditable), (
                    f"{mode.value} row's {col_name!r} column must be read-only"
                )

    def test_rate_driven_modes_stay_editable(self):
        """Proves the read-only rule above is mode-specific, not universal:
        MONTHLY (a normal extend report) must still allow editing these
        fields -- exactly what the old QTableWidget-based tab did."""
        model = ReportRecordModel(_FakeTheme())
        model.load([_record()], CalculationMode.MONTHLY)
        index = _idx(model, 0, "Rate %", REC_COL_IDX)
        flags = model.flags(index)
        assert flags & Qt.ItemFlag.ItemIsEditable


class TestConflictColumnListsSharedRefs:
    def test_conflict_column_lists_shared_refs(self):
        model = ReportListModel(_FakeTheme())
        conflicted = _report(
            report_id="RPT_A", conflict_ref_ids=["2026_01_001", "2026_01_002"]
        )
        clean = _report(report_id="RPT_B", conflict_ref_ids=[])
        model.load([conflicted, clean])

        conflict_idx = _idx(model, 0, "Conflict", REPORT_COL_IDX)
        clean_idx = _idx(model, 1, "Conflict", REPORT_COL_IDX)

        assert model.data(conflict_idx, Qt.ItemDataRole.DisplayRole) == (
            "2026_01_001, 2026_01_002"
        )
        assert model.data(clean_idx, Qt.ItemDataRole.DisplayRole) == ""

        # Visually flagged too, not just text -- a background colour comes
        # from the CONFLICT badge for the conflicted row only.
        assert model.data(conflict_idx, Qt.ItemDataRole.BackgroundRole) is not None
        assert model.data(clean_idx, Qt.ItemDataRole.BackgroundRole) is None


class TestConflictRefCellIsColoured:
    """KCH-245 review cycle 1, R20: the per-RECORD Ref ID cell (not just the
    per-REPORT Conflict column tested above) must also be coloured when its
    own reference_id is one this report shares with another pending one."""

    def test_conflict_ref_id_cell_is_coloured(self):
        model = ReportRecordModel(_FakeTheme())
        conflicted_rec = _record(reference_id="2026_01_001")
        clean_rec = _record(id=2, reference_id="2026_01_099")
        model.load(
            [conflicted_rec, clean_rec], CalculationMode.MONTHLY,
            conflict_ref_ids=["2026_01_001"],
        )

        conflicted_idx = _idx(model, 0, "Ref ID", REC_COL_IDX)
        clean_idx = _idx(model, 1, "Ref ID", REC_COL_IDX)

        assert model.data(conflicted_idx, Qt.ItemDataRole.BackgroundRole) is not None
        assert model.data(clean_idx, Qt.ItemDataRole.BackgroundRole) is None


class TestRealThemeBadgeColoursDiffer:
    """KCH-245 review cycle 1, R5: T1's `_FakeTheme` baked in colours that
    already differed, so it could never catch a REAL theme JSON regression
    (e.g. the light config's AGENT colour accidentally matching FORM's).
    Reads dark_config.json/light_config.json directly -- no ThemeManager.
    apply_theme()/QApplication needed for a plain JSON read."""

    @pytest.mark.parametrize("theme_name", ["dark", "light"])
    def test_agent_and_form_colours_differ_in_the_real_theme_json(self, theme_name):
        config = json.loads((THEMES_DIR / f"{theme_name}_config.json").read_text())
        badges = config["badge_colours"]
        assert badges["AGENT"]["background"] != badges["FORM"]["background"], (
            f"{theme_name}_config.json: AGENT and FORM badge colours must differ"
        )


class TestRecentlyApprovedTimeHeader:
    """KCH-245 review cycle 1, m1: Recently Approved reuses ReportListModel,
    but its time column is when the report was APPROVED, not "Updated"."""

    def test_default_time_header_is_updated(self):
        model = ReportListModel(_FakeTheme())
        assert model.headerData(
            REPORT_COL_IDX["Updated"], Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
        ) == "Updated"

    def test_overridden_time_header_is_approved(self):
        model = ReportListModel(_FakeTheme(), time_header="Approved")
        assert model.headerData(
            REPORT_COL_IDX["Updated"], Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
        ) == "Approved"


class TestRecordsColumnSortsNumerically:
    """KCH-245 review cycle 1, m7: the Records column used to render a
    `str`, so the proxy's default DisplayRole sort compared lexically
    ("10" < "9"). Drives the REAL QSortFilterProxyModel, not just the
    model's own data(), since the bug is in how Qt compares the values."""

    def test_records_column_sorts_as_numbers_not_strings(self):
        model = ReportListModel(_FakeTheme())
        few = _report(report_id="RPT_FEW", records=[_record(id=i) for i in range(2)])
        many = _report(report_id="RPT_MANY", records=[_record(id=i) for i in range(10)])
        model.load([few, many])

        proxy = QSortFilterProxyModel()
        proxy.setSourceModel(model)
        proxy.sort(REPORT_COL_IDX["Records"], Qt.SortOrder.AscendingOrder)

        ordered_ids = [
            proxy.data(proxy.index(row, REPORT_COL_IDX["Report ID"]))
            for row in range(proxy.rowCount())
        ]
        assert ordered_ids == ["RPT_FEW", "RPT_MANY"], (
            "2 records must sort before 10 -- a string sort would put "
            "'10' before '2'"
        )


class TestFailedEditIsReportedAsFailure:
    """KCH-245 review cycle 1, R19: setData must return False (and leave the
    row unchanged) when the injected on_edit callback fails (returns None) --
    it must never claim success for a write that didn't happen."""

    def test_setdata_returns_false_when_on_edit_returns_none(self):
        rec = _record()
        model = ReportRecordModel(_FakeTheme(), on_edit=lambda *a: None)
        model.load([rec], CalculationMode.MONTHLY)

        index = _idx(model, 0, "Rate %", REC_COL_IDX)
        ok = model.setData(index, "24", Qt.ItemDataRole.EditRole)

        assert ok is False
        assert model.data(index, Qt.ItemDataRole.DisplayRole) == str(rec.interest_rate), (
            "a failed edit must not appear to have changed the row"
        )
