# Backend QA Agent: Test Specification — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Agent:** backend-qa-agent (Wave 2)
**Source:** Backend Dev sync received — all 6 tasks implemented, 197 baseline tests passing
**Test runner:** `cd "/Users/ishq_kan/Documents/Github/FinHive/src/Loan Manager" && python3 -m pytest tests/ -v`
**Desktop app:** PySide6 — no web API surface. All tests are pytest unit/integration tests.

---

## QA Sync Receipt from Backend Dev

**Sync received:** Yes — BACKEND_IMPLEMENTATION.md reviewed in full
**Implementation status:** All 6 tasks complete. 197 baseline tests green.
**Schema changes:** None. Zero.
**New files:** `ui/widgets.py`
**Modified files:** 8 files across ui/, data/, loan_manager/

**Error conditions confirmed by Backend Dev:**
- BUG-UTR-2 Fix B: crash during `Path.replace()` — original file intact
- BUG-UTR-3: snapshot must be taken before `recompute_all()` mutates Loan objects in place
- CHG-02-EXT: IOError during report write after paidoff archival — warning shown, paidoff NOT undone
- TC-401: no-due-date Paidoff → extension_period=0, interest=0

---

## Testability Review

### BUG-UTR-1 — `_on_apply_filters()`
**Testability:** Good at data layer. `_get_filtered_loans()` is a pure function of combo state and `self._loans`. Tests can drive `self._loans` directly and check returned list. No QApplication needed for model-layer tests.

### BUG-UTR-2 — `_active_year_months()` + `_write_meta()`
**Testability:** Excellent. `RefIdManager` takes an injected `meta_path` — all tests use `tmp_path` fixture. `_active_year_months()` reads `loans.csv` via injected `_data_dir` — conftest already patches this.
**Chaos test for Fix B:** Monkeypatch `Path.replace` to raise `OSError` mid-call; confirm original file unchanged.

### BUG-UTR-3 — `load_data()` status snapshot
**Testability:** Good. `update_loan` can be monkeypatched; snapshot logic is testable by confirming call count.
**Mutation risk:** `recompute_all()` confirmed to mutate Loan objects in place. Tests must create snapshot copies, not references.

### BUG-UTR-4 — `ClickableDateEdit`
**Testability:** Limited without QApplication. Import test is headless-safe. `setCalendarPopup` state test requires `QApplication` instance — use `pytest-qt` or a fixture that instantiates `QApplication` once per session.

### BC-301 — `_paidoff_warning` label
**Testability:** Requires QApplication for widget instantiation. Logic is simple: `label.isVisible()` after a selection change.

### CHG-02-EXT — Paidoff report pipeline
**Testability:** Excellent. `generate_report_id`, `write_report`, `write_report_records` are all injectable-path functions in `loan_manager/report_manager.py`. Tests can call them directly with `tmp_path` and inspect CSV output.

---

## Test Specifications: BUG-UTR-1

### BE-UTR1-01: `test_get_filtered_loans_single_filter`
**File:** `tests/test_interest_calculator_tab.py` (new)
**Type:** Unit
**What it tests:** After `_on_apply_filters()` fix, `_get_filtered_loans()` returns only loans matching the borrower_group filter when that filter is set to a non-All value.
**Setup:** Build a list of 3 Loan objects with different borrower_groups. Monkeypatch `self._loans`. Set `_filter_borrower_group.currentText()` to one group value.
**Assert:** Returned list contains only loans for that group.
**Edge case:** If borrower_group value is removed from combos after reload (loan deleted), `setCurrentText()` falls back to "All" — assert result contains all loans.

### BE-UTR1-02: `test_get_filtered_loans_multi_filter`
**File:** `tests/test_interest_calculator_tab.py`
**Type:** Unit
**What it tests:** Combination of two active filters both applied correctly (AND logic).
**Assert:** Only loans matching both filter values are returned.

### BE-UTR1-03: `test_filter_fallback_all_when_value_missing`
**File:** `tests/test_interest_calculator_tab.py`
**Type:** Unit
**What it tests:** `QComboBox.setCurrentText()` with a value not in the combo silently stays at current selection or "All".
**Assert:** `currentText()` after `setCurrentText("missing_value")` returns "All" (Qt default behaviour).

---

## Test Specifications: BUG-UTR-2

### BE-UTR2-01: `test_active_year_months_uses_reference_id` (ADD to test_ref_id_manager.py)
**Type:** Unit
**What it tests:** `_active_year_months()` derives bucket from `reference_id`, not `giving_date`. A loan with `reference_id = "2026_04_001"` and `giving_date = date(2026, 3, 15)` (March) must appear in bucket `2026_04`, not `2026_03`.
**Setup:** Write one loan to `loans.csv` with `reference_id = "2026_04_001"` and `giving_date = date(2026, 3, 15)`. Call `_active_year_months()`.
**Assert:** `"2026_04" in result`. `"2026_03" not in result`.

### BE-UTR2-02: `test_backdated_loan_buckets_to_entry_month` (ADD to test_ref_id_manager.py)
**Type:** Unit
**What it tests:** Back-dated loan (giving_date in prior month) still uses entry-month bucket.
**Setup:** Two loans — one regular `2026_04_001`, one back-dated `2026_04_002` with giving_date in March.
**Assert:** Both loans appear in `2026_04` bucket. Counter advances correctly.

### BE-UTR2-03: `test_ten_rapid_consecutive_unique_ids` (ADD to test_ref_id_manager.py)
**Type:** Integration
**What it tests:** 10 consecutive `next_ref_id(2026, 4)` calls in same month all produce unique, sequentially incremented IDs.
**Setup:** Empty `tmp_path` meta file.
**Assert:** Result list == `["2026_04_001", ..., "2026_04_010"]`. No duplicates. `len(set(result)) == 10`.

### BE-UTR2-04: `test_atomic_write_original_intact_on_crash` (ADD to test_ref_id_manager.py)
**Type:** Chaos
**What it tests:** If `Path.replace()` raises `OSError`, the original `loans_meta.csv` is untouched.
**Setup:** Write known meta content to `meta_path`. Monkeypatch `pathlib.Path.replace` to raise `OSError`. Call `_write_meta()`.
**Assert:** `OSError` is raised. `meta_path` contents unchanged. `.tmp` file may or may not exist — not required to clean up.

### BE-UTR2-05: `test_atomic_write_normal_success` (ADD to test_ref_id_manager.py)
**Type:** Unit
**What it tests:** Normal `_write_meta()` call produces correct meta file with correct content. No `.tmp` file left behind.
**Setup:** Call `_write_meta({"2026_04": 5, "2026_03": 2})`.
**Assert:** `loans_meta.csv` exists and contains two rows with correct year_month/counter values. `loans_meta.tmp` does not exist.

### BE-UTR2-06: `test_active_year_months_excludes_history_csv` (ADD to test_ref_id_manager.py)
**Type:** Regression (known gap SA-401)
**What it tests:** Documents current behaviour: `_active_year_months()` does NOT include loans in `history.csv`. If all loans for `2026_02` are in history.csv and none in loans.csv, `"2026_02"` is NOT in the returned set.
**Assert:** `"2026_02" not in result`. This is expected (not a bug in run_4 scope). Test documents the boundary.

---

## Test Specifications: BUG-UTR-3

### BE-UTR3-01: `test_refresh_no_status_changes_zero_update_calls` (ADD to test_status_engine.py)
**Type:** Unit
**What it tests:** When `recompute_all()` produces no status changes, `update_loan()` is called zero times.
**Setup:** Create 3 Active loans with future due dates. Monkeypatch `update_loan` to record call count. Run snapshot + recompute + conditional write logic.
**Assert:** `update_loan` call count == 0.

### BE-UTR3-02: `test_refresh_partial_update_only_changed` (ADD to test_status_engine.py)
**Type:** Unit
**What it tests:** Only the loan whose status changed is passed to `update_loan()`.
**Setup:** 3 loans: 2 Active (future due), 1 Active but due date = yesterday (should become Overdue). Run snapshot + recompute + conditional write.
**Assert:** `update_loan` called exactly 1 time. Called loan is the one with yesterday's due date.

### BE-UTR3-03: `test_refresh_all_statuses_changed` (ADD to test_status_engine.py)
**Type:** Unit
**What it tests:** When all loan statuses change, all loans are passed to `update_loan()`.
**Setup:** 3 Active loans with past due dates (all become Overdue). Run snapshot + recompute + conditional write.
**Assert:** `update_loan` called 3 times.

### BE-UTR3-04: `test_refresh_zero_writes_emits_debug_log` (ADD to test_status_engine.py)
**Type:** Observability
**What it tests:** When zero loans change status, the debug log line "Refresh: no status changes — skipping all writes" is emitted.
**Setup:** Monkeypatch logger. 3 stable Active loans. Run load_data snapshot logic.
**Assert:** `logger.debug` called with message containing "no status changes".

---

## Test Specifications: BUG-UTR-4

### BE-UTR4-01: `test_clickable_date_edit_importable` (tests/test_widgets.py, new)
**Type:** Unit
**What it tests:** `ClickableDateEdit` can be imported from `ui.widgets` without error.
**Assert:** `from ui.widgets import ClickableDateEdit` succeeds. `ClickableDateEdit` is a class.

### BE-UTR4-02: `test_clickable_date_edit_is_qdate_edit_subclass` (tests/test_widgets.py)
**Type:** Unit
**What it tests:** `ClickableDateEdit` is a subclass of `QDateEdit`.
**Assert:** `issubclass(ClickableDateEdit, QDateEdit)` is True. (Headless — no QApplication needed for class inspection.)

---

## Test Specifications: BC-301

### BE-BC301-01: `test_paidoff_warning_exists_and_hidden_by_default` (tests/test_pending_approval_tab.py, new)
**Type:** Unit (requires QApplication)
**What it tests:** After `_build_ui()`, `_paidoff_warning` attribute exists and `isVisible()` is False.
**Assert:** `tab._paidoff_warning` exists. `tab._paidoff_warning.isVisible()` is False.

### BE-BC301-02: `test_paidoff_warning_visible_on_paidoff_mode`
**Type:** Unit (requires QApplication)
**What it tests:** After selecting a Paidoff-mode report, `_paidoff_warning.isVisible()` is True.
**Setup:** Create `PendingApprovalTab`. Set `self._reports` to a list containing a `PendingReport(mode="Paidoff")`. Call `_on_report_selection_changed()` with that report selected.
**Assert:** `tab._paidoff_warning.isVisible()` is True.

### BE-BC301-03: `test_paidoff_warning_hidden_on_non_paidoff_mode`
**Type:** Unit (requires QApplication)
**What it tests:** After selecting a Monthly-mode report, `_paidoff_warning.isVisible()` is False.
**Assert:** `tab._paidoff_warning.isVisible()` is False.

---

## Test Specifications: CHG-02-EXT

### BE-CHG02-01 through BE-CHG02-06 (ADD to tests/test_report_manager.py)

All 6 tests exercise the `loan_manager/report_manager.py` pipeline directly with `tmp_path` — no UI or QApplication needed.

**BE-CHG02-01:** `test_paidoff_report_record_interest_rate`
Write a `ReportRecord` with `interest_rate=15.0, mode="Paidoff"`. Read back from CSV. Assert `interest_rate == 15.0`.

**BE-CHG02-02:** `test_paidoff_report_record_commission_rate`
Write a `ReportRecord` with `commission_rate=3.5`. Read back. Assert `commission_rate == 3.5`.

**BE-CHG02-03:** `test_paidoff_report_record_tds_flag_true`
Write a `ReportRecord` with `tds_flag=True`, `interest_amount=100.0`. Read back. Assert `tds_amount == 10.0`.

**BE-CHG02-04:** `test_paidoff_report_record_tds_flag_false`
Write a `ReportRecord` with `tds_flag=False`. Read back. Assert `tds_amount == 0.0`.

**BE-CHG02-05:** `test_paidoff_no_due_date_zero_interest` — TC-401 coverage
Compute `extension_period` when `loan.due_date is None`. Assert `extension_period == 0`, `interest_amount == 0.0`, `commission_amount == 0.0`.

**BE-CHG02-06:** `test_paidoff_report_pipeline_failure_does_not_raise`
Monkeypatch `write_report` to raise `IOError`. Confirm that the outer try/except in `_action_paidoff()` catches it and does not propagate. (Tested at the service layer — the mark_paidoff call preceding this is a separate concern.)

---

## Regression Scope

All 197 existing tests must remain green. Key regression points:

| Test file | Why it could regress | Risk level |
|---|---|---|
| `test_ref_id_manager.py` | BUG-UTR-2 changes bucket derivation and write path | High — run this first |
| `test_status_engine.py` | BUG-UTR-3 touches the same module | Medium |
| `test_report_manager.py` | CHG-02-EXT extends pipeline | Low — additive only |
| `test_csv_manager.py` | Shim chain touched by BUG-UTR-2 | Low |
| `test_interest_calculator.py` | No changes to interest_calculator.py | None |

**Post-run confirmation:** `python3 -m pytest tests/ -v` = 197 passed (confirmed by Backend Dev).

---

## Known Gaps (Out of scope run_4)

| Gap | Owner | Phase |
|---|---|---|
| SA-401: history.csv not in `_active_year_months()` | Dev Lead | Phase 4 |
| loans.csv non-atomic write | SRE | Phase 4 |
| SRE-001: startup recovery.tmp detection | SRE | Phase 4 |
| Log rotation (FileHandler → RotatingFileHandler) | SRE | Phase 4 |
| Pre-operation CSV backup | SRE | Phase 4 |
| reports_meta.csv non-atomic write | SRE | Phase 4 |

---

## Backend QA Signoff

**Implementation reviewed:** Yes
**Testability verdict:** All 6 tasks testable. BUG-UTR-4 and BC-301 require QApplication fixture (pytest-qt or session-scoped fixture).
**Baseline confirmed:** 197 passing
**Test stubs issued:** Yes — 21 new test scenarios specified above
**Ready for QA Lead review:** Yes
