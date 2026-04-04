# QA Lead: Test Scope — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Agent:** qa-lead-agent (Wave 2)
**Baseline:** 197 passing tests (pre-run confirmed)
**Test runner:** `cd "/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager" && python -m pytest tests/ -v`
**Desktop app:** PySide6 — no frontend-qa-agent. Backend QA owns all desktop UI test scenarios at model/service layer.

---

## QA Lead KT Receipt: run_4 — All 6 Scope Items

**KT reviewed:** Yes — Dev Lead IMPLEMENTATION_PLAN.md read in full
**DM schema signoff pending:** No — zero schema changes confirmed by DM agent
**SRE reliability scope received:** Yes — integrated below (BUG-UTR-2 atomicity, BUG-UTR-3 Refresh log, CHG-02-EXT pipeline atomicity)
**Gaps / clarifications needed from Dev Lead:**
- [SA-401] `read_all_loans_including_paidoff()` reads loans.csv only, not history.csv — `_active_year_months()` will not see paidoff loans. Impact on uniqueness guarantee if a paidoff loan's YYYY_MM has no active loans. Dev Lead deferred to Phase 4. Test coverage: include scenario where the only record for a YYYY_MM is in history.csv to document current behaviour.
- [TC-401] No-due-date Paidoff: `extension_period = 0`, `interest = 0` — PO default confirmed as option a. Test must confirm this path explicitly in CHG-02-EXT tests.

**Ready to issue QA briefs:** Yes

---

## QA Brief: Backend QA — run_4 All Items

**What was built:** Six fixes/features across interest calculator UI, ref_id generation, view tab refresh, date picker widget, pending approval tab warning label, and paidoff dialog rate fields.
**Test scope:** Model/service layer — no web API surface. Tests are pytest unit/integration tests against loan_manager/, data/, and model modules. UI state scenarios are tested via model and data-layer assertions (PySide6 not instantiated in tests).
**Known risks from Dev Lead:** SA-401 (history.csv not in scope for _active_year_months), TC-401 (no-due-date paidoff), CHG-02-EXT report pipeline exception path.
**Code review required:** Yes — review BUG-UTR-2 Fix B (atomic write) and CHG-02-EXT pipeline for testability.
**Deliverable:** Test scenarios, pytest stubs, and testability review.

---

## QA Lead Testability Review: BUG-UTR-2 — Backend

**Snippet reviewed:** `_write_meta()` atomic write using `.tmp` + `Path.replace()`
**Testability verdict:** Good

**Feedback:**
- `Path.replace()` is atomic on POSIX and Windows NTFS — verifiable by monkeypatching `Path.replace` to raise mid-way and confirming the original file is intact.
- No hardcoded paths — `meta_path` is injected as a parameter, enabling tmp-dir testing.

**Blocker for test planning:** No

---

## QA Lead Testability Review: CHG-02-EXT — Backend

**Snippet reviewed:** `_action_paidoff()` in view_tab.py wiring PaidoffDialog getters to report pipeline
**Testability verdict:** Needs improvement

**Feedback:**
- `_action_paidoff()` mixes QDialog instantiation + report write in a single method — not unit-testable in isolation without a running QApplication.
- The report pipeline calls (`generate_report_id`, `write_report`, `write_report_records`) should be testable independently from the UI code. The Dev Lead plan confirms these are in `loan_manager/report_manager.py` — they are already unit-testable.
- **Recommendation:** Tests should exercise `generate_report_id`, `write_report`, and `write_report_records` directly with Paidoff-mode inputs, not via the dialog. The dialog getter values are tested by inspecting the data written to pending_reports.csv.

**Blocker for test planning:** No — report pipeline is testable independently.

---

## Master Test Scope: Loan Manager run_4

**Scope summary:** Six fixes: (1) Interest Calculator filter reset bug, (2) duplicate reference_id generation with two sub-fixes (wrong bucket derivation + non-atomic meta write), (3) View Tab Refresh unconditional overwrite, (4) ClickableDateEdit widget, (5) Paidoff warning label in Pending Approval Tab, (6) PaidoffDialog extended with rate/TDS fields wired to report pipeline.

**Frontend test scope:** Not applicable — PySide6 desktop app. Backend QA owns all test layers.

**Backend test scope:** (delegated to backend-qa-agent)

| ID | Scenario | Module/File | Priority | Type | Runner Invocation |
|---|---|---|---|---|---|
| BE-UTR1-01 | Filter retained after apply — single filter | test_interest_calculator_tab.py | P1 | Unit | `python -m pytest tests/test_interest_calculator_tab.py::test_filter_retained_after_apply_single -v` |
| BE-UTR1-02 | Multiple filters combined — all retained | test_interest_calculator_tab.py | P1 | Unit | `python -m pytest tests/test_interest_calculator_tab.py::test_filter_retained_after_apply_multi -v` |
| BE-UTR1-03 | Filter value no longer exists post-reload — falls back to All | test_interest_calculator_tab.py | P2 | Unit | `python -m pytest tests/test_interest_calculator_tab.py::test_filter_fallback_to_all_when_value_removed -v` |
| BE-UTR2-01 | _active_year_months uses reference_id not giving_date | test_ref_id_manager.py | P1 | Unit | `python -m pytest tests/test_ref_id_manager.py::test_active_year_months_uses_reference_id -v` |
| BE-UTR2-02 | Back-dated loan buckets to entry month not giving month | test_ref_id_manager.py | P1 | Unit | `python -m pytest tests/test_ref_id_manager.py::test_backdated_loan_buckets_to_entry_month -v` |
| BE-UTR2-03 | 10 rapid consecutive entries — all unique sequential IDs | test_ref_id_manager.py | P1 | Integration | `python -m pytest tests/test_ref_id_manager.py::test_ten_rapid_consecutive_unique_ids -v` |
| BE-UTR2-04 | Atomic write: crash between tmp write and rename — original intact | test_ref_id_manager.py | P1 | Chaos | `python -m pytest tests/test_ref_id_manager.py::test_atomic_write_original_intact_on_crash -v` |
| BE-UTR2-05 | Atomic write: normal write — meta file correct after write | test_ref_id_manager.py | P1 | Unit | `python -m pytest tests/test_ref_id_manager.py::test_atomic_write_normal_success -v` |
| BE-UTR2-06 | Only paidoff loan in YYYY_MM — _active_year_months gap (SA-401 known) | test_ref_id_manager.py | P2 | Regression | `python -m pytest tests/test_ref_id_manager.py::test_active_year_months_excludes_history_csv -v` |
| BE-UTR3-01 | Refresh with no status changes — zero update_loan() calls | test_csv_manager.py or test_status_engine.py | P1 | Unit | `python -m pytest tests/test_status_engine.py::test_refresh_no_changes_zero_writes -v` |
| BE-UTR3-02 | Refresh with one status change — only changed loan updated | test_status_engine.py | P1 | Unit | `python -m pytest tests/test_status_engine.py::test_refresh_partial_update_only_changed -v` |
| BE-UTR3-03 | Refresh with all statuses changed — all loans updated | test_status_engine.py | P1 | Unit | `python -m pytest tests/test_status_engine.py::test_refresh_all_changed_all_written -v` |
| BE-UTR3-04 | Refresh zero-writes emits debug log line | test_status_engine.py | P2 | Observability | `python -m pytest tests/test_status_engine.py::test_refresh_zero_writes_log_emitted -v` |
| BE-UTR4-01 | ClickableDateEdit class exists and is importable | test_widgets.py | P2 | Unit | `python -m pytest tests/test_widgets.py::test_clickable_date_edit_importable -v` |
| BE-UTR4-02 | ClickableDateEdit setCalendarPopup True on init | test_widgets.py | P2 | Unit | `python -m pytest tests/test_widgets.py::test_clickable_date_edit_calendar_popup_enabled -v` |
| BE-BC301-01 | Paidoff warning label exists in pending_approval_tab build | test_pending_approval_tab.py | LOW | Unit | `python -m pytest tests/test_pending_approval_tab.py::test_paidoff_warning_label_exists -v` |
| BE-BC301-02 | Warning label visible when Paidoff report selected | test_pending_approval_tab.py | LOW | Unit | `python -m pytest tests/test_pending_approval_tab.py::test_paidoff_warning_visible_on_paidoff_selection -v` |
| BE-BC301-03 | Warning label hidden when non-Paidoff report selected | test_pending_approval_tab.py | LOW | Unit | `python -m pytest tests/test_pending_approval_tab.py::test_paidoff_warning_hidden_on_regular_selection -v` |
| BE-CHG02-01 | Report written with correct interest_rate from dialog | test_report_manager.py | P2 | Integration | `python -m pytest tests/test_report_manager.py::test_paidoff_report_interest_rate -v` |
| BE-CHG02-02 | Report written with correct commission_rate from dialog | test_report_manager.py | P2 | Integration | `python -m pytest tests/test_report_manager.py::test_paidoff_report_commission_rate -v` |
| BE-CHG02-03 | Report written with tds_flag True from dialog | test_report_manager.py | P2 | Integration | `python -m pytest tests/test_report_manager.py::test_paidoff_report_tds_flag_true -v` |
| BE-CHG02-04 | Report written with tds_flag False from dialog | test_report_manager.py | P2 | Integration | `python -m pytest tests/test_report_manager.py::test_paidoff_report_tds_flag_false -v` |
| BE-CHG02-05 | No-due-date Paidoff: extension_period=0, interest=0 (TC-401) | test_report_manager.py | P1 | Unit | `python -m pytest tests/test_report_manager.py::test_paidoff_no_due_date_zero_interest -v` |
| BE-CHG02-06 | Report pipeline failure (IOError) does not crash app — logs error | test_report_manager.py | P2 | Error path | `python -m pytest tests/test_report_manager.py::test_paidoff_report_pipeline_failure_handled -v` |

**Integration test scope:** (QA Lead owns)

| ID | Scenario | Priority | Runner Invocation |
|---|---|---|---|
| INT-01 | End-to-end: new loan entry → next_ref_id unique → write → Refresh → no redundant writes | P1 | `python -m pytest tests/ -k "ref_id and status_engine" -v` |
| INT-02 | End-to-end: Paidoff flow — dialog rates → generate_report_id → write_report → write_report_records → pending_reports.csv correct | P1 | `python -m pytest tests/test_report_manager.py -v` |
| INT-03 | Full test suite passes — 197 baseline + new tests all green | P1 | `python -m pytest tests/ -v` |

**Reliability test scope:** (from SRE agent)

| ID | Scenario | Type | Priority | Runner Invocation |
|---|---|---|---|---|
| REL-01 | loans_meta.csv atomic write — crash injection mid-rename | Chaos | P1 | `python -m pytest tests/test_ref_id_manager.py::test_atomic_write_original_intact_on_crash -v` |
| REL-02 | Refresh emits zero-write log line — log inspection | Observability | P2 | `python -m pytest tests/test_status_engine.py::test_refresh_zero_writes_log_emitted -v` |
| REL-03 | 10 rapid consecutive ref_id generations — all unique | Durability | P1 | `python -m pytest tests/test_ref_id_manager.py::test_ten_rapid_consecutive_unique_ids -v` |

**Regression scope:**
- `test_ref_id_manager.py` — all existing 19 tests must remain green after BUG-UTR-2 Fix A+B
- `test_csv_manager.py` — all existing tests must remain green (no csv_manager changes, but shim chain touched)
- `test_status_engine.py` — existing tests must pass; BUG-UTR-3 fix must not alter status computation
- `test_report_manager.py` — existing tests must pass; CHG-02-EXT extends, not modifies, existing report pipeline
- `test_interest_calculator.py` — all 197 baseline tests must remain green

**Out of scope:**
- history.csv inclusion in `_active_year_months()` (SA-401) — Phase 4
- loans.csv non-atomic write (SRE gap) — Phase 4
- Startup recovery.tmp detection (SRE-001) — Phase 4
- Log rotation (SRE gap) — Phase 4
- Automated pre-operation backup — Phase 4
- BC-03 status display options A-E — Phase 4

**Entry criteria:**
- All 6 source file changes implemented per Dev Lead IMPLEMENTATION_PLAN.md
- 197 existing tests passing before new tests are added
- New test file stubs written (see New Test Files section below)

**Exit criteria:**
- All 197 baseline tests still passing
- All new test scenarios (BE-UTR1-01 through BE-CHG02-06 + INT-01 through INT-03 + REL-01 through REL-03) passing
- BUG-UTR-2 Fix B: `test_atomic_write_original_intact_on_crash` passing
- TC-401: `test_paidoff_no_due_date_zero_interest` passing
- Zero regressions in existing test suite

---

## New Test Files Required

Backend QA must create the following test file stubs. Dev Lead implementation adds these alongside source changes.

### `tests/test_interest_calculator_tab.py` (NEW)
```python
"""
Tests for ui/interest_calculator_tab.py filter retention fix (BUG-UTR-1).

These tests exercise _get_filtered_loans() logic at the data layer without
instantiating QApplication. Filter state is simulated via mock objects.
"""
import pytest


def test_filter_retained_after_apply_single():
    """BE-UTR1-01: Single filter value is retained after apply."""
    pass


def test_filter_retained_after_apply_multi():
    """BE-UTR1-02: Multiple filter values all retained after apply."""
    pass


def test_filter_fallback_to_all_when_value_removed():
    """BE-UTR1-03: setCurrentText with missing value silently falls back to All."""
    pass
```

### `tests/test_widgets.py` (NEW)
```python
"""
Tests for ui/widgets.py shared widget classes (BUG-UTR-4).

Requires QApplication. Use pytest-qt or mock QApplication for headless CI.
"""
import pytest


def test_clickable_date_edit_importable():
    """BE-UTR4-01: ClickableDateEdit can be imported from ui.widgets."""
    pass


def test_clickable_date_edit_calendar_popup_enabled():
    """BE-UTR4-02: ClickableDateEdit has calendarPopup=True on init."""
    pass
```

### `tests/test_pending_approval_tab.py` (NEW)
```python
"""
Tests for ui/pending_approval_tab.py paidoff warning label (BC-301).

Warning label visibility toggles based on report mode selection.
"""
import pytest


def test_paidoff_warning_label_exists():
    """BE-BC301-01: _paidoff_warning QLabel exists after _build_ui()."""
    pass


def test_paidoff_warning_visible_on_paidoff_selection():
    """BE-BC301-02: Warning label visible when mode=Paidoff report selected."""
    pass


def test_paidoff_warning_hidden_on_regular_selection():
    """BE-BC301-03: Warning label hidden when non-Paidoff report selected."""
    pass
```

### New tests to add to `tests/test_ref_id_manager.py` (EXTEND)
```python
def test_active_year_months_uses_reference_id():
    """BE-UTR2-01: _active_year_months derives YYYY_MM from reference_id not giving_date."""
    pass


def test_backdated_loan_buckets_to_entry_month():
    """BE-UTR2-02: Back-dated loan (giving_date prior month) uses entry-month bucket."""
    pass


def test_ten_rapid_consecutive_unique_ids():
    """BE-UTR2-03: 10 consecutive next_ref_id() calls in same month all unique and sequential."""
    pass


def test_atomic_write_original_intact_on_crash():
    """BE-UTR2-04: If Path.replace raises, original loans_meta.csv is unchanged."""
    pass


def test_atomic_write_normal_success():
    """BE-UTR2-05: Normal _write_meta() produces correct meta file."""
    pass


def test_active_year_months_excludes_history_csv():
    """BE-UTR2-06: Known gap SA-401 — history.csv loans not in _active_year_months scope."""
    pass
```

### New tests to add to `tests/test_status_engine.py` (EXTEND)
```python
def test_refresh_no_changes_zero_writes():
    """BE-UTR3-01: Refresh with no status changes calls update_loan() zero times."""
    pass


def test_refresh_partial_update_only_changed():
    """BE-UTR3-02: Refresh updates only the loan whose status changed."""
    pass


def test_refresh_all_changed_all_written():
    """BE-UTR3-03: Refresh with all statuses changed updates all loans."""
    pass


def test_refresh_zero_writes_log_emitted():
    """BE-UTR3-04: Refresh with no changes emits debug log 'No status changes'."""
    pass
```

### New tests to add to `tests/test_report_manager.py` (EXTEND)
```python
def test_paidoff_report_interest_rate():
    """BE-CHG02-01: Paidoff report record contains correct interest_rate value."""
    pass


def test_paidoff_report_commission_rate():
    """BE-CHG02-02: Paidoff report record contains correct commission_rate value."""
    pass


def test_paidoff_report_tds_flag_true():
    """BE-CHG02-03: Paidoff report record with tds_flag=True has non-zero tds_amount."""
    pass


def test_paidoff_report_tds_flag_false():
    """BE-CHG02-04: Paidoff report record with tds_flag=False has tds_amount=0."""
    pass


def test_paidoff_no_due_date_zero_interest():
    """BE-CHG02-05: TC-401 — Paidoff with no due_date: extension_period=0, interest=0."""
    pass


def test_paidoff_report_pipeline_failure_handled():
    """BE-CHG02-06: IOError in report pipeline is caught and logged, app does not crash."""
    pass
```

---

## QA Lead Test Scope Signoff: run_4

**Master test scope reviewed:** Yes
**Dev Lead co-sign received:** Yes — IMPLEMENTATION_PLAN.md reviewed, all 6 items have exact fix specifications
**Frontend QA ready:** Not applicable — PySide6 desktop app
**Backend QA ready:** Pending — briefs issued, stubs defined

**Formal Signoff:** Testing may begin once all source changes are implemented per Dev Lead plan.

**UAT Handoff Note:**
Six items ready for end-user acceptance:
1. BUG-UTR-1: Verify Interest Calculator filter dropdowns retain selection after Apply Filters click.
2. BUG-UTR-2: Verify 10 consecutive rapid loan entries in the same month all get unique sequential reference_ids. Verify no corruption of loans_meta.csv on force-close.
3. BUG-UTR-3: Verify Refresh button on View Tab does not visibly re-save all loans when nothing changed (log line confirms).
4. BUG-UTR-4: Verify clicking anywhere on the date entry field opens the calendar picker, not just the arrow.
5. BC-301: Verify Pending Approval Tab shows a visible warning label when a Paidoff report is selected, and the label is hidden for other report types.
6. CHG-02-EXT: Verify PaidoffDialog presents interest_rate, commission_rate, and TDS fields and that submitted values appear correctly in the pending report record.

**[REVIEW REQUIRED — TC-401]:** For UAT item 6, when a loan has no due_date, confirm with the user that extension_period defaults to 0 and interest is 0 upon Paidoff — or whether a date entry should be forced. PO default is option a (0/0) but requires user confirmation before UAT sign-off.

---

## Test Coverage Targets (per module)

| Module | Current Tests | New Tests | Coverage Target |
|---|---|---|---|
| loan_manager/ref_id_manager.py | 19 | +6 | 95% |
| data/ref_id_manager.py (shim) | 0 | +0 (shim only) | N/A |
| ui/view_tab.py load_data() | 0 | +4 | 80% of snapshot logic |
| ui/interest_calculator_tab.py | 0 | +3 | 80% of filter logic |
| ui/widgets.py | 0 (new file) | +2 | 100% of ClickableDateEdit |
| ui/pending_approval_tab.py | 0 | +3 | 80% of warning toggle |
| loan_manager/report_manager.py | existing | +6 | 90% of Paidoff path |
