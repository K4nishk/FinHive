"""KCH-245 offscreen smoke test (owner Q13: model/view-model tests plus ONE
offscreen smoke test, no broader UI suite -- CLAUDE.md's "no UI tests in
prototype scope" is overridden only this far).

Builds a real `PendingApprovalTab` against a real (in-memory) database and
drives it through Qt's own selection model and button handlers -- not just
the models in isolation (that is what test_report_table_models.py/
test_approval_messages.py already cover). Requires QT_QPA_PLATFORM=offscreen
(set by the gate commands; also set here as a safety net for direct runs).

Screenshots are written to FINHIVE_SMOKE_SHOT_DIR when that env var is set;
the test still runs and asserts everything else when it is not.

KCH-245 review cycle 1 additions (kept inside this ONE smoke test per the
Q13 limit, rather than adding more smoke test functions):
  - a real pixel check that the actor badge's rendered background matches
    ThemeManager's AGENT colour (M1 -- the stylesheet fix, not just that
    the model's data() role returns a colour)
  - the pending AND recently-approved lists are sorted before selecting, so
    a selection bug that skips `mapToSource` (R7/R8) would pick the wrong
    row instead of accidentally being right
  - QMessageBox is patched to capture calls, so a refused-approve /
    not-pending-approve / refused-undo path being silently swallowed (R9,
    R10, R11) would leave no captured dialog, not just "no exception"
  - a genuine UPDATE-mode selection whose live loan differs from the
    proposal, asserting the "Current" columns show the ACTUAL live values
    (R12 -- proves GetAllLoans was really called, not just that the branch
    didn't crash)
`test_refresh_survives_a_failing_uow` is a second, much smaller function in
this same file (R13) -- it needs no widget selection, just construction, so
folding it into the big flow above would only make failures harder to read.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from loan_manager.application.dtos.loan_dto import LoanCreateDTO, PaidOffRequestDTO
from loan_manager.application.dtos.report_dto import GenerateReportDTO, ReportRecordDTO
from loan_manager.application.event_bus import EventBus
from loan_manager.application.interfaces.clock import FixedClock
from loan_manager.application.use_cases.loans.create_loan import CreateLoan
from loan_manager.application.use_cases.loans.mark_paidoff import MarkPaidOff
from loan_manager.application.use_cases.reports.approve_report import ApproveReport
from loan_manager.application.use_cases.reports.generate_report import GenerateReport
from loan_manager.domain.errors import DataUnreadableError
from loan_manager.domain.services.reference_id_service import ReferenceIdService
from loan_manager.domain.value_objects.status import (
    CalculationMode,
    ExtensionPeriodUnit,
    ReportActor,
)
from loan_manager.infrastructure.database.models import Base
from loan_manager.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork
from loan_manager.infrastructure.recovery.backup_service import BackupService
from loan_manager.infrastructure.recovery.recovery_service import RecoveryService
from loan_manager.presentation.tabs.pending_approval_tab import PendingApprovalTab
from loan_manager.presentation.themes.theme_manager import ThemeManager
from loan_manager.presentation.widgets.report_table_models import REC_COL_IDX, REPORT_COL_IDX
from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# A user_request containing HTML-looking text -- proves the label renders it
# verbatim as PlainText rather than interpreting <b> as a tag (which would
# make "ravi" render bold instead of the literal characters showing).
_AGENT_USER_REQUEST = "add <b>ravi</b> 5000"


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _monthly_record(ref_id: str, **overrides) -> ReportRecordDTO:
    base = dict(
        id=None, report_id="placeholder", reference_id=ref_id,
        borrower_name="ravi", depositor_name="meena", depositor_group=None,
        amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
        extension_period=3, extension_period_unit=ExtensionPeriodUnit.MONTHS,
        interest_rate=Decimal("12"), commission_rate=Decimal("6"), tds_flag=False,
        interest_amount=Decimal("300.00"), commission_amount=Decimal("150.00"),
        tds_amount=Decimal("0.00"), chq_amount=Decimal("300.00"),
        post_extension_giving_date=date(2026, 4, 1),
        post_extension_due_date=date(2026, 7, 1), paidoff_date=None,
    )
    base.update(overrides)
    return ReportRecordDTO(**base)


def _create_record() -> ReportRecordDTO:
    return ReportRecordDTO(
        id=None, report_id="placeholder", reference_id=None,
        borrower_name="new borrower", depositor_name="new depositor",
        depositor_group=None, amount=5000, giving_date=None, due_date=None,
        extension_period=0, extension_period_unit=ExtensionPeriodUnit.MONTHS,
        interest_rate=Decimal("0"), commission_rate=Decimal("0"), tds_flag=False,
        interest_amount=None, commission_amount=None, tds_amount=None, chq_amount=None,
        post_extension_giving_date=date(2026, 4, 10),
        post_extension_due_date=date(2026, 7, 10), paidoff_date=None,
        borrower_group="new-group", due_period=3,
    )


def _update_record(ref_id: str, giving_date, due_date, **overrides) -> ReportRecordDTO:
    """An UPDATE-mode proposal (KCH-243 agent update_loan): only
    borrower_name/depositor_name/amount are applied on approval -- dates
    come along unchanged (propose_update.py), post_extension_* stay None."""
    base = dict(
        id=None, report_id="placeholder", reference_id=ref_id,
        borrower_name="proposed name", depositor_name="depositor",
        depositor_group=None, amount=99000, giving_date=giving_date, due_date=due_date,
        extension_period=0, extension_period_unit=ExtensionPeriodUnit.MONTHS,
        interest_rate=Decimal("0"), commission_rate=Decimal("0"), tds_flag=False,
        interest_amount=None, commission_amount=None, tds_amount=None, chq_amount=None,
        post_extension_giving_date=None, post_extension_due_date=None, paidoff_date=None,
    )
    base.update(overrides)
    return ReportRecordDTO(**base)


def _build_container(session):
    def uow_factory():
        return SqlAlchemyUnitOfWork(session)

    return SimpleNamespace(
        get_uow=uow_factory,
        recovery_service=SimpleNamespace(write=lambda *a, **k: None, clear=lambda: None),
        backup_service=SimpleNamespace(create_backup=lambda: None),
        event_bus=EventBus(),
        clock=FixedClock(date(2026, 4, 10)),
    )


def _select_report(tab, report_id: str) -> None:
    model = tab._report_model
    row = next(
        i for i in range(model.rowCount()) if model.report_at(i).report_id == report_id
    )
    proxy_index = tab._report_proxy.mapFromSource(model.index(row, 0))
    tab._report_table.selectionModel().setCurrentIndex(
        proxy_index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )


def _select_approved(tab, report_id: str) -> None:
    model = tab._approved_model
    row = next(
        i for i in range(model.rowCount()) if model.report_at(i).report_id == report_id
    )
    proxy_index = tab._approved_proxy.mapFromSource(model.index(row, 0))
    tab._approved_table.selectionModel().setCurrentIndex(
        proxy_index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )


def _maybe_screenshot(widget, name: str, shot_dir) -> str | None:
    if not shot_dir:
        return None
    Path(shot_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(shot_dir) / f"{name}.png"
    widget.grab().save(str(out_path))
    return str(out_path)


class _CapturedDialogs:
    """Patches QMessageBox.{warning,information,question} to record every
    call instead of blocking on a real (nonexistent, offscreen) user -- KCH-245
    review cycle 1: R9/R10/R11 exist specifically to prove a refusal is
    SHOWN, not merely that nothing raised."""

    def __init__(self, monkeypatch):
        self.calls: list[tuple[str, str, str]] = []
        for kind in ("warning", "information", "question", "critical"):
            monkeypatch.setattr(QMessageBox, kind, self._recorder(kind))

    def _recorder(self, kind):
        def _f(parent, title, text, *a, **k):
            self.calls.append((kind, title, text))
            return QMessageBox.StandardButton.Yes
        return staticmethod(_f)

    def last(self, kind: str) -> tuple[str, str, str] | None:
        for call in reversed(self.calls):
            if call[0] == kind:
                return call
        return None


def test_pending_approval_tab_offscreen(qapp, tmp_path, monkeypatch):
    from loan_manager.infrastructure.security.key_provider import set_active_key_ring

    from finhive.db.keys import KeyRing

    set_active_key_ring(KeyRing(current_version=1, masters={1: b"\x42" * 32}))

    shot_dir = os.environ.get("FINHIVE_SMOKE_SHOT_DIR")
    dialogs = _CapturedDialogs(monkeypatch)

    engine = create_engine(
        f"sqlite:///{tmp_path / 'smoke.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    container = _build_container(session)

    def uow_factory():
        return SqlAlchemyUnitOfWork(session)

    ref_service = ReferenceIdService()
    event_bus = EventBus()
    create_loan_uc = CreateLoan(uow_factory, ref_service, event_bus)

    loan = create_loan_uc.execute(LoanCreateDTO(
        borrower_name="ravi", borrower_group="g1", depositor_name="meena",
        amount=10000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
    ))
    # A second, live loan an UPDATE report proposes changing -- its "Current"
    # column must show what THIS loan actually holds (R12).
    loan_update_target = create_loan_uc.execute(LoanCreateDTO(
        borrower_name="pooja", borrower_group="g2", depositor_name="depositor2",
        amount=15000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
    ))
    # A third loan that will be paid off (made inactive) AFTER its own
    # UPDATE proposal is generated -- the exact sequence approve_report.py's
    # inactive-UPDATE refusal (R9) exists to catch.
    loan_to_go_stale = create_loan_uc.execute(LoanCreateDTO(
        borrower_name="stale", borrower_group="g3", depositor_name="depositor3",
        amount=20000, giving_date=date(2026, 1, 1), due_date=date(2026, 4, 1),
    ))

    gen_uc = GenerateReport(uow_factory, event_bus)

    # Two FORM reports sharing the same loan -- a conflict, per KCH-245.
    report_x = gen_uc.execute(GenerateReportDTO(
        mode=CalculationMode.MONTHLY, records=[_monthly_record(loan.reference_id)],
        actor=ReportActor.FORM,
    ))
    gen_uc.execute(GenerateReportDTO(
        mode=CalculationMode.MONTHLY, records=[_monthly_record(loan.reference_id)],
        actor=ReportActor.FORM,
    ))

    # One AGENT CREATE report -- the row this smoke test approves.
    agent_report = gen_uc.execute(GenerateReportDTO(
        mode=CalculationMode.CREATE, records=[_create_record()],
        actor=ReportActor.AGENT, user_request=_AGENT_USER_REQUEST, turn_id="turn-smoke",
    ))

    # A FORM report referencing a loan that was never created -- exactly
    # ApproveReport's own `deleted_ref_ids` case (test_approval_flow.py's
    # TestDeletedLoanWarning uses the identical fabricated-ref pattern).
    # Approving it needs one confirm (Yes), then succeeds with
    # deleted_ref_ids still set -- the scenario m4 exists for.
    deleted_ref_report = gen_uc.execute(GenerateReportDTO(
        mode=CalculationMode.MONTHLY, records=[_monthly_record("9999_99_999")],
        actor=ReportActor.FORM,
    ))

    # An AGENT UPDATE report that stays approvable (R12).
    update_report = gen_uc.execute(GenerateReportDTO(
        mode=CalculationMode.UPDATE,
        records=[_update_record(
            loan_update_target.reference_id, loan_update_target.giving_date,
            loan_update_target.due_date, borrower_name="pooja renamed", amount=16000,
        )],
        actor=ReportActor.AGENT, user_request="rename pooja's loan", turn_id="turn-upd",
    ))

    # An AGENT UPDATE report whose target loan goes stale (paid off) before
    # this report is ever approved (R9).
    stale_update_report = gen_uc.execute(GenerateReportDTO(
        mode=CalculationMode.UPDATE,
        records=[_update_record(
            loan_to_go_stale.reference_id, loan_to_go_stale.giving_date,
            loan_to_go_stale.due_date, borrower_name="stale renamed",
        )],
        actor=ReportActor.AGENT, user_request="rename stale's loan", turn_id="turn-stale",
    ))

    # Pay off loan_to_go_stale NOW, via the real use cases, bypassing the
    # tab -- exactly the "since this report was proposed" sequence.
    recovery, backup = RecoveryService(), BackupService()
    recovery.write, recovery.clear = lambda *a, **k: None, lambda: None
    backup.create_backup = lambda: None
    paidoff_uc = MarkPaidOff(uow_factory, event_bus)
    paidoff_report = paidoff_uc.execute(loan_to_go_stale.reference_id, PaidOffRequestDTO(
        paidoff_date=date(2026, 4, 2), interest_rate=Decimal("12"), commission_rate=Decimal("6"),
    ))
    approve_direct = ApproveReport(
        uow_factory, recovery, backup, event_bus, clock=container.clock,
    )
    # force=True: paidoff_report and stale_update_report both name
    # loan_to_go_stale.reference_id (one pending Paidoff, one pending
    # Update on the same loan) -- exactly the fixture this smoke test
    # wants, so the duplicate-ref confirmation is answered Yes directly.
    paidoff_result = approve_direct.execute(paidoff_report.report_id, force=True)
    assert paidoff_result.success, "fixture setup: paying off the stale loan must itself succeed"

    ThemeManager.apply_theme("dark", qapp)

    tab = PendingApprovalTab(container, ThemeManager, parent=None)
    tab.resize(1200, 800)
    tab.show()  # offscreen platform: no real display, but isVisible()/grab()
    # need the top-level actually shown, not just resized.
    qapp.processEvents()

    assert tab._report_model.rowCount() == 6, (
        "report_x, report_y, agent_report, deleted_ref_report, update_report, "
        "stale_update_report"
    )
    assert tab._approved_model.rowCount() == 1, "the stale loan's own paidoff report"

    # -- AGENT/FORM badges are visually distinguishable (ACCEPTANCE 1),
    # BEFORE any row is selected -- the list itself carries the signal. ----
    agent_row = next(
        i for i in range(tab._report_model.rowCount())
        if tab._report_model.report_at(i).report_id == agent_report.report_id
    )
    form_row = next(
        i for i in range(tab._report_model.rowCount())
        if tab._report_model.report_at(i).report_id == report_x.report_id
    )
    agent_bg = tab._report_model.data(
        tab._report_model.index(agent_row, 1), Qt.ItemDataRole.BackgroundRole
    )
    form_bg = tab._report_model.data(
        tab._report_model.index(form_row, 1), Qt.ItemDataRole.BackgroundRole
    )
    assert agent_bg.color().name() != form_bg.color().name()

    # PySide's QTableView sets an initial "current" index (row 0) as soon as
    # a non-empty model is attached and the view is shown, purely for
    # keyboard navigability -- that current-row focus rectangle is not a
    # real selection, but it DOES fire `currentRowChanged` and populate the
    # detail strip. Clear it explicitly so this screenshot shows the list
    # with genuinely NO row selected/expanded, AGENT rows included.
    tab._report_table.clearSelection()
    tab._report_table.setCurrentIndex(QModelIndex())
    qapp.processEvents()
    assert tab._selected_report is None
    shot_unselected = _maybe_screenshot(tab, "unselected_pending_badges", shot_dir)

    # -- R7: sort the PROXY before selecting -- a selection bug that reads
    # current.row() as a SOURCE row instead of mapToSource(current).row()
    # would pick the wrong report the moment sort order != insertion order. --
    tab._report_proxy.sort(REPORT_COL_IDX["Report ID"], Qt.SortOrder.DescendingOrder)
    qapp.processEvents()
    _select_report(tab, agent_report.report_id)
    qapp.processEvents()
    assert tab._selected_report.report_id == agent_report.report_id
    _select_report(tab, report_x.report_id)
    qapp.processEvents()
    assert tab._selected_report.report_id == report_x.report_id

    # -- select the AGENT CREATE report: verbatim PlainText, no None cells,
    # and the badge is ACTUALLY styled (M1 -- not just that the model's
    # data() role returns a colour: the rendered pixel must match it). -----
    _select_report(tab, agent_report.report_id)
    qapp.processEvents()

    assert tab._user_request_label.text() == _AGENT_USER_REQUEST
    assert tab._user_request_label.textFormat() == Qt.TextFormat.PlainText

    for col in range(tab._record_model.columnCount()):
        value = tab._record_model.data(tab._record_model.index(0, col), Qt.ItemDataRole.DisplayRole)
        assert value is not None and value != "None", f"column {col} rendered None"
    assert tab._record_model.data(
        tab._record_model.index(0, 0), Qt.ItemDataRole.DisplayRole
    ) == "(new)"

    expected_agent_colour = QColor(ThemeManager.get_badge_colour("AGENT")["background"])
    rendered_colour = tab._actor_badge.grab().toImage().pixelColor(2, 2)
    assert rendered_colour.name() == expected_agent_colour.name(), (
        f"actor badge must actually RENDER {expected_agent_colour.name()}, "
        f"got {rendered_colour.name()} (M1: a stylesheet, not a QPalette, "
        "since the app-wide QSS always wins over QPalette)"
    )

    shot_badge = _maybe_screenshot(tab._actor_badge, "actor_badge_styled", shot_dir)
    shot1 = _maybe_screenshot(tab, "pending_agent_create_row", shot_dir)

    # -- select a conflicting FORM report: conflict label visible ----------
    _select_report(tab, report_x.report_id)
    qapp.processEvents()
    assert tab._conflict_label.isVisible()
    assert loan.reference_id in tab._conflict_label.text()

    # -- KCH-245 review cycle 2, MINOR-1: the conflict label's styling must
    # actually RENDER, same reasoning as the actor badge pixel check above
    # (M1) -- `isVisible()` and the text alone don't prove the CONFLICT
    # colour was ever applied (C1 deletes the styling call and still passes
    # both of those). ------------------------------------------------------
    expected_conflict_colour = QColor(ThemeManager.get_badge_colour("CONFLICT")["background"])
    rendered_conflict_colour = tab._conflict_label.grab().toImage().pixelColor(2, 2)
    assert rendered_conflict_colour.name() == expected_conflict_colour.name(), (
        f"conflict label must actually RENDER {expected_conflict_colour.name()}, "
        f"got {rendered_conflict_colour.name()}"
    )

    # -- R12: select the UPDATE report -- "Current" must be the LIVE loan's
    # actual values (GetAllLoans really ran), not "(loan not active)". -----
    _select_report(tab, update_report.report_id)
    qapp.processEvents()
    current_b_name = tab._record_model.data(
        tab._record_model.index(0, REC_COL_IDX["Current B Name"]),
        Qt.ItemDataRole.DisplayRole,
    )
    assert current_b_name == "pooja", (
        f"UPDATE row's Current B Name must be the LIVE loan's own name, got {current_b_name!r}"
    )

    # -- R9: approving a report whose target loan went inactive since
    # proposal must be REFUSED WITH A DIALOG, never silently. --------------
    _select_report(tab, stale_update_report.report_id)
    qapp.processEvents()
    tab._on_approve()
    qapp.processEvents()
    warned = dialogs.last("warning")
    assert warned is not None and "Cannot approve" in warned[1]
    assert loan_to_go_stale.reference_id in warned[2]
    assert "Proceed" not in warned[2]
    # And it must still be sitting in the pending list, not silently dropped.
    assert any(
        tab._report_model.report_at(i).report_id == stale_update_report.report_id
        for i in range(tab._report_model.rowCount())
    )

    # -- approve the AGENT CREATE report (no dialog expected: no dup/del) --
    _select_report(tab, agent_report.report_id)
    qapp.processEvents()
    tab._on_approve()
    qapp.processEvents()

    assert tab._report_model.rowCount() == 5, "approved report must leave the pending list"
    assert all(
        tab._report_model.report_at(i).report_id != agent_report.report_id
        for i in range(tab._report_model.rowCount())
    )
    assert tab._approved_model.rowCount() == 2
    assert any(
        tab._approved_model.report_at(i).report_id == agent_report.report_id
        for i in range(tab._approved_model.rowCount())
    )

    # -- m4: approving a report with a deleted reference needs one confirm
    # (dialogs.last defaults to Yes), then succeeds -- the "skipped" note
    # must reach the user (an info box), not just the status bar's fixed
    # "Report X approved." one-liner. -------------------------------------
    _select_report(tab, deleted_ref_report.report_id)
    qapp.processEvents()
    tab._on_approve()
    qapp.processEvents()
    confirmed = dialogs.last("warning")
    assert confirmed is not None and "Confirmation Required" in confirmed[1]
    approved_info = dialogs.last("information")
    assert approved_info is not None and "skipped" in approved_info[2].lower()
    assert "9999_99_999" in approved_info[2]
    assert tab._report_model.rowCount() == 4
    assert tab._approved_model.rowCount() == 3

    # -- R10: re-approving a report that is no longer pending (a stale
    # selection -- e.g. a double-click race) must inform, never silently
    # no-op. `_selected_report` is set directly here to reproduce exactly
    # that stale-reference shape without depending on Qt's click timing. ---
    tab._selected_report = agent_report
    tab._on_approve()
    qapp.processEvents()
    informed = dialogs.last("information")
    assert informed is not None and "No longer pending" in informed[1]

    # -- R8: sort the APPROVED proxy before selecting, same reasoning as R7. -
    tab._approved_proxy.sort(REPORT_COL_IDX["Report ID"], Qt.SortOrder.DescendingOrder)
    qapp.processEvents()
    _select_approved(tab, agent_report.report_id)
    qapp.processEvents()
    assert tab._selected_approved.report_id == agent_report.report_id
    assert tab._undo_btn.isEnabled()

    shot2 = _maybe_screenshot(tab, "recently_approved_with_undo", shot_dir)

    # -- KCH-245 review cycle 2, MINOR-2(a): undoing an UNDOABLE report
    # (CREATE here, still selected from the R8 check above) must ask "Are
    # you sure?" FIRST -- m3's skip-confirm applies to PAIDOFF/UPDATE only.
    # Kills C8 (skip confirm for ALL modes) without touching m3's own mode
    # tuple, so a mutation that over-broadens the skip is caught here even
    # though it would leave the PAIDOFF-only check below untouched. --------
    tab._on_undo()
    qapp.processEvents()
    asked = dialogs.last("question")
    assert asked is not None and "Confirm Undo" in asked[1], (
        "undoing a CREATE report must ask for confirmation first"
    )
    assert not any(
        tab._approved_model.report_at(i).report_id == agent_report.report_id
        for i in range(tab._approved_model.rowCount())
    ), "a confirmed, successful CREATE undo must leave Recently Approved"

    # -- R11 + m3: undoing a PAIDOFF report is refused UNCONDITIONALLY --
    # m3 means no "Are you sure?" first; go straight to a warning dialog
    # showing the refusal, and the report must stay in Recently Approved. --
    _select_approved(tab, paidoff_report.report_id)
    qapp.processEvents()
    calls_before_paidoff_undo = len(dialogs.calls)
    tab._on_undo()
    qapp.processEvents()
    undo_warned = dialogs.last("warning")
    assert undo_warned is not None and "Cannot undo" in undo_warned[1]
    assert "cannot be undone" in undo_warned[2]
    assert not any(
        c[0] == "question" for c in dialogs.calls[calls_before_paidoff_undo:]
    ), "PAIDOFF undo must skip the Are you sure? confirm (m3)"
    assert any(
        tab._approved_model.report_at(i).report_id == paidoff_report.report_id
        for i in range(tab._approved_model.rowCount())
    ), "a refused undo must not remove the report from Recently Approved"

    if shot_dir:
        for shot in (shot_unselected, shot_badge, shot1, shot2):
            assert shot and Path(shot).exists()

    set_active_key_ring(None)


def test_refresh_survives_a_failing_uow(qapp, monkeypatch):
    """KCH-245 review cycle 1, R13: `refresh()` must stay wrapped in
    `surfacing_storage_errors` -- a `uow_factory` that raises
    `DataUnreadableError` (a wrong/rotated master key, in the real app) must
    NOT crash tab construction (which calls `refresh()`); the tab should
    come up with empty lists rather than propagate the exception."""

    def _failing_uow():
        raise DataUnreadableError("smoke test: simulated bad key")

    container = SimpleNamespace(
        get_uow=_failing_uow,
        recovery_service=SimpleNamespace(write=lambda *a, **k: None, clear=lambda: None),
        backup_service=SimpleNamespace(create_backup=lambda: None),
        event_bus=EventBus(),
        clock=FixedClock(date(2026, 4, 10)),
    )

    # QMessageBox.critical would otherwise pop a real (offscreen) dialog
    # from surfacing_storage_errors' own reporting path.
    monkeypatch.setattr(QMessageBox, "critical", staticmethod(lambda *a, **k: None))

    ThemeManager.apply_theme("dark", qapp)
    tab = PendingApprovalTab(container, ThemeManager, parent=None)  # must not raise

    assert tab._report_model.rowCount() == 0
    assert tab._approved_model.rowCount() == 0
