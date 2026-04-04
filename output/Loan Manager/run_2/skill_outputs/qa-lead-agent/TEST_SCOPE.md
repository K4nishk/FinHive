# QA Lead: Test Scope — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 / Wave 2
**Author:** QA Lead Agent
**Scope:** Phase 3 prototype — 7 change items (CHG-01, CHG-02, BUG-01–04, DOC-01)

---

## QA Lead KT Receipt: Loan Manager run_2

**KT reviewed:** Yes — Dev Lead IMPLEMENTATION_PLAN.md consumed
**DM schema signoff pending:** No — DM confirmed no schema changes required. Signoff request is procedural.
**SRE reliability scope received:** Yes — RELIABILITY_REVIEW.md consumed (REL-01 through REL-05 + failure injection scenarios)
**Gaps / clarifications needed from Dev Lead:**
- confirm exact attribute names for the five filter combos in `interest_calculator_tab.py` before writing BUG-01 test fixtures (e.g., `self._borrower_group_combo` — confirm naming)
- confirm whether `extend_dialog.py` contains any `QDateEdit` instances (BUG-04 consumer list)

**Ready to issue QA briefs:** Yes (with above noted as low-risk items — backend QA can proceed; confirm during implementation)

---

## Master Test Scope: Loan Manager run_2

**Scope summary:** Phase 3 closes 4 user-reported defects and 2 new requirements. All changes are in UI layer files and one backend service. No schema migration. Testing is desktop app testing (PySide6) — backend-qa-agent covers all layers including desktop UI per agent selection matrix (no frontend-qa-agent for desktop apps).

---

### Backend Test Scope (desktop UI + service layer — backend-qa-agent)

| ID | Scenario | Module | Priority | Type | Runner |
|---|---|---|---|---|---|
| BE-01 | CHG-01: Form initialises with No Due Date checkbox checked=True | entry_tab.py | P1 | Unit | `pytest tests/ui/test_entry_tab.py::test_no_due_date_default_checked` |
| BE-02 | CHG-01: _reset_form() restores No Due Date checkbox to checked=True | entry_tab.py | P1 | Unit | `pytest tests/ui/test_entry_tab.py::test_reset_form_no_due_date_checked` |
| BE-03 | CHG-01: Due Date field disabled when No Due Date is checked on init | entry_tab.py | P1 | Unit | `pytest tests/ui/test_entry_tab.py::test_due_date_disabled_when_no_due_date_checked` |
| BE-04 | CHG-02: Paidoff with due_date → report created in pending_reports.csv with mode=Daily | view_tab.py | P1 | Integration | `pytest tests/ui/test_view_tab_paidoff.py::test_paidoff_report_created` |
| BE-05 | CHG-02: Paidoff with paidoff_date = due_date → extension_period_days = 0, interest = 0.00 | view_tab.py | P1 | Unit | `pytest tests/ui/test_view_tab_paidoff.py::test_paidoff_same_day_zero_interest` |
| BE-06 | CHG-02: Paidoff with paidoff_date < due_date → extension_period_days clamped to 0 | view_tab.py | P1 | Unit | `pytest tests/ui/test_view_tab_paidoff.py::test_paidoff_early_clamp_to_zero` |
| BE-07 | CHG-02: Paidoff with no due_date → no report generated, WARNING logged | view_tab.py | P1 | Unit | `pytest tests/ui/test_view_tab_paidoff.py::test_paidoff_no_due_date_skips_report` |
| BE-08 | CHG-02: Report generation exception after Paidoff write → loan in history.csv, user warned | view_tab.py | P1 | Integration | `pytest tests/ui/test_view_tab_paidoff.py::test_paidoff_report_failure_non_blocking` |
| BE-09 | CHG-02: Paidoff report appears in Pending Approval tab after creation | pending_approval_tab.py | P2 | Integration | `pytest tests/ui/test_pending_approval.py::test_paidoff_report_visible` |
| BE-10 | BUG-01: Filter combo retains selected value after Apply Filters | interest_calculator_tab.py | P1 | Unit | `pytest tests/ui/test_interest_calculator_tab.py::test_filter_persists_after_apply` |
| BE-11 | BUG-01: All five filter combos retain values simultaneously | interest_calculator_tab.py | P1 | Unit | `pytest tests/ui/test_interest_calculator_tab.py::test_all_filters_persist` |
| BE-12 | BUG-01: Filter gracefully reverts to "All" when selected value no longer present | interest_calculator_tab.py | P2 | Unit | `pytest tests/ui/test_interest_calculator_tab.py::test_filter_reverts_when_value_missing` |
| BE-13 | BUG-02: Active row sets dark green background and white foreground | view_tab.py | P1 | Unit | `pytest tests/ui/test_view_tab_colors.py::test_active_row_color` |
| BE-14 | BUG-02: Overdue row sets dark red background and white foreground | view_tab.py | P1 | Unit | `pytest tests/ui/test_view_tab_colors.py::test_overdue_row_color` |
| BE-15 | BUG-02: All status types have both bg and fg explicitly set | view_tab.py | P1 | Unit | `pytest tests/ui/test_view_tab_colors.py::test_all_status_colors_have_fg` |
| BE-16 | BUG-03: Context menu "Mark Paidoff" action is connected to _action_paidoff() | view_tab.py | P1 | Unit | `pytest tests/ui/test_view_tab_context_menu.py::test_mark_paidoff_action_connected` |
| BE-17 | BUG-04: ClickableDateEdit.mousePressEvent calls showPopup() | clickable_date_edit.py | P1 | Unit | `pytest tests/ui/test_clickable_date_edit.py::test_mouse_press_calls_show_popup` |
| BE-18 | BUG-04: entry_tab giving_date field is ClickableDateEdit instance | entry_tab.py | P2 | Unit | `pytest tests/ui/test_entry_tab.py::test_giving_date_is_clickable` |
| BE-19 | DOC-01: YYYY-MM-DD format giving_date imported correctly | import_service.py | P1 | Unit | `pytest tests/test_import_service.py::test_iso_date_accepted` |
| BE-20 | DOC-01: DD-MM-YYYY format giving_date imported and stored as ISO | import_service.py | P1 | Unit | `pytest tests/test_import_service.py::test_dd_mm_yyyy_date_accepted` |
| BE-21 | DOC-01: Invalid date format → row skipped, WARNING logged, skipped counter incremented | import_service.py | P1 | Unit | `pytest tests/test_import_service.py::test_invalid_date_skipped` |
| BE-22 | DOC-01: DD-MM-YYYY due_date imported and stored as ISO | import_service.py | P1 | Unit | `pytest tests/test_import_service.py::test_due_date_dd_mm_yyyy` |
| BE-23 | REL-01: mark_paidoff() — loan not in loans.csv, is in history.csv | csv_manager.py | P1 | Integration | `pytest tests/test_csv_manager.py::test_mark_paidoff_mutual_exclusivity` |
| BE-24 | REL-03: Import 100 rows with 10 malformed → result.skipped=10, result.inserted=90 | import_service.py | P2 | Integration | `pytest tests/test_import_service.py::test_import_batch_skip_count` |
| BE-25 | TC-02: App startup with missing loans_meta.csv → no unhandled exception | ref_id_manager.py | P2 | Unit | `pytest tests/test_ref_id_manager.py::test_missing_meta_graceful` |
| BE-26 | TC-02: App startup with missing reports_meta.csv → no unhandled exception | report_manager.py | P2 | Unit | `pytest tests/test_report_manager.py::test_missing_meta_graceful` |

---

### Integration Test Scope (QA Lead owns)

| ID | Scenario | Priority |
|---|---|---|
| INT-01 | Full Paidoff flow: select loan in View Tab → right-click → Mark Paidoff → enter date → confirm → loan absent from View Tab → present in history.csv → Paidoff report present in Pending Approval tab | P1 |
| INT-02 | New loan entry → No Due Date default → submit loan → giving_date stored, due_date = null in loans.csv | P1 |
| INT-03 | Import CSV with mixed ISO and DD-MM-YYYY dates → all loans created with ISO dates in storage | P1 |
| INT-04 | Interest Calculator: apply BorrowerGroup filter → table filtered → filter retained → apply again → filter still retained | P1 |

---

### Reliability Test Scope (from SRE agent)

| ID | Scenario | Type | Priority |
|---|---|---|---|
| REL-01 | mark_paidoff(): verify loan mutual exclusivity between loans.csv and history.csv | Data durability | P1 |
| REL-02 | Simulate orphan pending_reports.csv row (no matching records) → Pending Approval tab renders without crash | Fault injection | P2 |
| REL-03 | Import batch with malformed rows → correct skip count | Batch integrity | P1 |
| REL-04 | Import DD-MM-YYYY dates → ISO stored | Data format | P1 |
| REL-05 | Launcher on Python 3.9 → version check message, no app launch | Startup safety | P1 |

---

### Regression Scope

Areas at risk from run_2 changes:

| Area | Risk Source | Regression Tests |
|---|---|---|
| `entry_tab.py` form submission | CHG-01 checkbox change may affect due_date submission logic | Verify due_date=null when No Due Date checked; verify due_date stored when unchecked and date entered |
| `view_tab.py` `_action_paidoff()` | CHG-02 adds new code path after mark_paidoff() | Verify existing Paidoff write behaviour unchanged (loan moves to history.csv) |
| `pending_approval_tab.py` approval flow | CHG-02 adds Paidoff reports to queue | Verify existing extension report approval unchanged |
| `interest_calculator_tab.py` filter UX | BUG-01 fix changes _on_apply_filters() ordering | Verify "All" filter still shows all loans; verify table row count |
| `import_service.py` existing ISO imports | DOC-01 adds fallback parse | Verify ISO dates that worked before still work (backward compatibility) |

---

### Out of Scope (Phase 3)

- QComboBox StatusDelegate for inline Status editing (Phase 4 — PD-R2-06)
- BC-05 interest_rate/commission_rate at Paidoff time (pending PO BC-05 decision)
- BC-06 Paidoff report approval semantic conflict resolution (Phase 4)
- R6 full import/export date hierarchy filter (Phase 4)
- R9 theme chooser (Phase 4)
- XLSX date serial number import (pre-existing limitation, out of scope DOC-01)

---

### Entry Criteria

- All 7 change items implemented per IMPLEMENTATION_PLAN.md
- `ui/widgets/clickable_date_edit.py` file present in source tree
- No Python import errors on app startup
- DM DATA_MODEL.md confirmed: no schema migration required

### Exit Criteria

- All P1 test scenarios passing
- INT-01 Paidoff full flow verified manually
- REL-01 and REL-03 passing
- Zero P1 regressions in entry_tab, view_tab, pending_approval_tab
- BC-05 and BC-06 documented as known open items (not blocking Phase 3 UAT)

---

## QA Lead Test Scope Signoff

**Master test scope reviewed:** Yes
**Dev Lead co-sign received:** Pre-authorized in IMPLEMENTATION_PLAN.md (co-sign after QA scope produced)
**Backend QA ready:** Yes (see BACKEND_QA_SPEC.md)
**Frontend QA:** Not applicable — desktop app, backend-qa-agent covers all layers

**Formal Signoff:** Testing may begin once all change items are implemented

**UAT Handoff Note:**
Phase 3 prototype delivers 4 bug fixes and 2 new features. The key UAT scenarios for end-user acceptance are:
1. Verify No Due Date checkbox is pre-checked on form open (CHG-01)
2. Mark a loan as Paidoff via right-click context menu and verify an interest report appears in Pending Approval (CHG-02) — note: report approval will show "deleted records" warning; this is expected and documented (BC-06)
3. Verify filter selections persist in Interest Calculator after Apply Filters (BUG-01)
4. Verify View Tab loan rows are readable with dark color palette (BUG-02)
5. Verify date fields open calendar on click without requiring arrow button (BUG-04 — Windows-specific)
6. Import a CSV with DD-MM-YYYY date format and verify loans are created correctly (DOC-01)

Open item for user to confirm at UAT: BC-04 (is the right-click context menu for Paidoff sufficient, or is the QComboBox Status delegate required before sign-off?); BC-02 (color palette preference confirmation).
