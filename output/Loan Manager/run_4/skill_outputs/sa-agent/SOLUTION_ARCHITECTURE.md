# SA Agent: Solution Architecture — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Agent:** sa-agent (Wave 1)
**Source authority:** /Users/ishq_kan/Documents/Github/FinHive/input/REQUIREMENTS.md
**PO Decisions:** /Users/ishq_kan/Documents/Github/FinHive/output/Loan Manager/run_4/skill_outputs/po-agent/PO_Decisions.md

---

## Architecture Overview: Confirmed Layering

The Loan Manager application uses a three-layer architecture confirmed from source inspection:

```
┌─────────────────────────────────────────────────────────┐
│  ui/               PySide6 presentation layer            │
│  (view_tab, entry_tab, interest_calculator_tab,          │
│   pending_approval_tab, dialogs/)                        │
│  — imports from data/* only. Never from loan_manager/*   │
├─────────────────────────────────────────────────────────┤
│  data/             Application-layer adapter (shim)      │
│  (csv_manager, ref_id_manager, report_manager,           │
│   status_engine, export_service, import_service)         │
│  — resolves paths from ./data/, delegates to loan_manager│
├─────────────────────────────────────────────────────────┤
│  loan_manager/     Canonical business logic              │
│  (csv_manager, ref_id_manager, report_manager,           │
│   status_engine, interest_calculator)                    │
│  — pure functions / injectable-path classes, no UI dep   │
│  — used directly by tests                                │
├─────────────────────────────────────────────────────────┤
│  models/           Shared data contracts                 │
│  (loan.py, report.py)                                    │
│  — dataclasses with CSV serialisation, no business logic │
└─────────────────────────────────────────────────────────┘
```

**ADR-LAYER-001 (confirmed):** `loan_manager/` is the canonical business logic layer. `data/` is a thin adapter layer that resolves `./data/` paths and delegates all logic to `loan_manager/`. UI code imports from `data/*` only — never from `loan_manager/*`. Tests import from `loan_manager/*` directly using injectable paths. This separation is intact and correct. No changes to this layering are required in run_4.

---

## Architecture Design: run_4 Component Impact Map

```
┌─────────────────────────────────────────────────────────┐
│ BUG-UTR-1  │ ui/interest_calculator_tab.py              │
│            │ _on_apply_filters() — ordering fix only     │
│            │ No model/service layer changes              │
├─────────────────────────────────────────────────────────┤
│ BUG-UTR-2  │ data/ref_id_manager.py                     │
│            │ _active_year_months() — use reference_id    │
│            │ loan_manager/ref_id_manager.py              │
│            │ _write_meta() — atomic write via tmp+rename │
├─────────────────────────────────────────────────────────┤
│ BUG-UTR-3  │ ui/view_tab.py                             │
│            │ load_data() — status snapshot pattern       │
├─────────────────────────────────────────────────────────┤
│ BUG-UTR-4  │ ui/widgets.py (NEW FILE)                   │
│            │ ClickableDateEdit(QDateEdit)                │
│            │ ui/entry_tab.py — replace QDateEdit         │
│            │ ui/dialogs/paidoff_dialog.py — replace      │
├─────────────────────────────────────────────────────────┤
│ BC-301     │ ui/pending_approval_tab.py                  │
│            │ _build_ui() bottom panel — add QLabel       │
│            │ _on_report_selection_changed() — toggle     │
├─────────────────────────────────────────────────────────┤
│ CHG-02-EXT │ ui/dialogs/paidoff_dialog.py                │
│            │ Add QDoubleSpinBox x2 + QCheckBox           │
│            │ ui/view_tab.py — _on_paidoff() caller       │
│            │ data/report_manager.py — write_report()     │
│            │ models/report.py — no schema change         │
└─────────────────────────────────────────────────────────┘
```

---

## SA Technical Assessment: BUG-UTR-1 — Interest Calculator Filter Reset

**Feasibility:** High
**Complexity:** Low

**Architectural Impact:**
- `ui/interest_calculator_tab.py`: Single method `_on_apply_filters()` — reorder 3 lines

**Recommended Approach:**
Capture all five filter combo values into local variables at the start of `_on_apply_filters()` before calling `_load_loans()`. After load (and the resulting `_populate_filters()` clear+reset), re-apply the captured values to the combos using `setCurrentText()`. Then call `_get_filtered_loans()` which reads the now-restored combo values.

**Critical architectural constraint:** `_populate_filters()` must remain called on initial tab load — its behaviour of resetting combos to "All" is correct for the initial load case. The fix is localised to the Apply Filters flow only. Do not remove or skip `_populate_filters()`.

**Implementation pattern:**
```
def _on_apply_filters(self) -> None:
    # 1. Capture before any reload
    bg = self._filter_borrower_group.currentText()
    bn = self._filter_borrower_name.currentText()
    dn = self._filter_depositor_name.currentText()
    dg = self._filter_depositor_group.currentText()
    mo = self._filter_by_month.currentText()
    # 2. Reload data (clears combos via _populate_filters)
    self._load_loans()
    # 3. Restore captured values
    self._filter_borrower_group.setCurrentText(bg)
    self._filter_borrower_name.setCurrentText(bn)
    self._filter_depositor_name.setCurrentText(dn)
    self._filter_depositor_group.setCurrentText(dg)
    self._filter_by_month.setCurrentText(mo)
    # 4. Apply filter with restored values
    self._filtered_loans = self._get_filtered_loans()
    self._populate_table(self._filtered_loans)
    self._calculated = False
    self._btn_generate.setEnabled(False)
```

**Technical Risks:**
- If a previously selected filter value is no longer in the combo (loan deleted between Opens), `setCurrentText()` silently falls back to "All" — acceptable behaviour

**Estimated Technical Effort:** XS (0.5 day)

---

## SA Technical Assessment: BUG-UTR-2 — Duplicate Reference IDs

**Feasibility:** High
**Complexity:** Medium (two separate fixes in two different layers)

**Architectural Impact:**
- `data/ref_id_manager.py` (adapter layer): `_active_year_months()` function
- `loan_manager/ref_id_manager.py` (canonical layer): `_write_meta()` method

**Fix A — `_active_year_months()` in `data/ref_id_manager.py`:**

Current code derives year_month from `loan.giving_date`. The year_month bucket in `loans_meta.csv` represents when the loan was entered (i.e., today's YYYY_MM at time of entry), not when it was given. The canonical source for this bucket is the `reference_id` field itself — the first two underscore-separated segments.

```python
# CURRENT (wrong)
ym = f"{loan.giving_date.year:04d}_{loan.giving_date.month:02d}"

# CORRECT
ym = "_".join(loan.reference_id.split("_")[:2])  # e.g. "2026_04" from "2026_04_001"
```

This also means `read_all_loans_including_paidoff()` must be called — not just `read_loans()` — to ensure loans moved to history.csv are also counted. Verify that `read_all_loans_including_paidoff()` reads both loans.csv and history.csv. [Developer must confirm before implementing.]

**Fix B — `_write_meta()` in `loan_manager/ref_id_manager.py`:**

Replace direct open("w") with atomic temp-file pattern:

```python
def _write_meta(self, meta: Dict[str, int]) -> None:
    self._meta_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = self._meta_path.with_suffix(".tmp")
    rows = [{"year_month": ym, "counter": str(order)}
            for ym, order in sorted(meta.items())]
    with tmp.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_META_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(self._meta_path)  # atomic on POSIX + Windows NTFS
```

`pathlib.Path.replace()` is atomic on both POSIX (rename syscall) and Windows NTFS (MoveFileEx with MOVEFILE_REPLACE_EXISTING semantics). If the process crashes after writing tmp but before the replace call, the original loans_meta.csv is intact and the .tmp file is an orphan (can be cleaned up on next read if desired, but is harmless).

**Technical Risks:**
- On Windows, `Path.replace()` can fail if the destination file is held open by another process. Since this is a single-user application with no concurrent sessions (R8), this risk is low.
- If `loan.reference_id` contains fewer than 2 underscore-separated segments (malformed ID from import), `split("_")[:2]` returns a partial result. Add a guard: if the split result has fewer than 2 segments, skip the loan rather than adding a malformed key to ym_set.

**Estimated Technical Effort:** S (1 day including tests)

---

## SA Technical Assessment: BUG-UTR-3 — View Tab Refresh Overwrites All Records

**Feasibility:** High
**Complexity:** Low

**Architectural Impact:**
- `ui/view_tab.py`: `load_data()` method only

**Key architectural finding — `recompute_all()` mutation behaviour:**
Source inspection of `loan_manager/status_engine.py` `recompute_all()` (lines 78-119) confirms:
- For Loan dataclass objects: `loan.status = new_status` — **mutates in place**
- Returns the same Loan objects (not copies) in a new list
- The snapshot must therefore be taken from the pre-mutation loan objects, **before** `recompute_all()` is called

**Implementation pattern:**
```python
def load_data(self) -> None:
    try:
        loans = read_loans()
        # Snapshot BEFORE recompute_all() mutates loan.status in place
        snapshot = {loan.reference_id: loan.status for loan in loans}
        loans = recompute_all(loans, date.today())
        # Only write loans whose status actually changed
        for loan in loans:
            if loan.status != snapshot.get(loan.reference_id):
                update_loan(loan)
    except Exception as exc:
        ...
```

**Technical Risks:**
- If a loan in the recomputed list has a reference_id not in the snapshot (e.g., a new loan added between read_loans() and recompute_all() — impossible in single-user scenario), `snapshot.get()` returns None and the comparison fails safely (updates the loan).
- Paidoff loans: `recompute_all()` skips Paidoff loans (status remains "Paidoff"). Since loans.csv should not contain Paidoff loans, this is moot — but the guard is correct regardless.

**Estimated Technical Effort:** XS (0.5 day)

---

## SA Technical Assessment: BUG-UTR-4 — Date Picker UX (ClickableDateEdit)

**Feasibility:** High
**Complexity:** Low

**Architectural Impact:**
- New file: `ui/widgets.py` — single shared widget definition
- `ui/entry_tab.py` — replace 2 `QDateEdit` instances
- `ui/dialogs/paidoff_dialog.py` — replace 1 `QDateEdit` instance

**Architecture Decision: New shared widgets module**

**ADR-WIDGET-001:** Create `ui/widgets.py` as the single source for all custom PySide6 widgets. This avoids copy-paste of the same subclass across multiple files and ensures future custom widgets follow the same pattern.

**Implementation:**
```python
# ui/widgets.py
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDateEdit

class ClickableDateEdit(QDateEdit):
    """QDateEdit subclass that opens the calendar popup on any mouse click.

    Addresses BUG-UTR-4: the default QDateEdit only opens the calendar
    when the user clicks the small dropdown arrow on the right edge.
    """
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self.showCalendarWidget()
```

**Apply in entry_tab.py:**
- Replace `self._giving_date = QDateEdit()` with `self._giving_date = ClickableDateEdit()`
- Replace `self._due_date = QDateEdit()` with `self._due_date = ClickableDateEdit()`
- Add import: `from ui.widgets import ClickableDateEdit`

**Apply in paidoff_dialog.py:**
- Replace `self._date_edit = QDateEdit()` with `self._date_edit = ClickableDateEdit()`
- Add import: `from ui.widgets import ClickableDateEdit`

**Cross-platform constraint (R-007):** `mousePressEvent` + `showCalendarWidget()` is pure Qt — no OS-specific code path. The calendar widget is a built-in QCalendarWidget. Qt renders it identically on Windows and Mac via their respective Qt platform plugins.

**Fallback if platform issues arise:** Replace `mousePressEvent` with `focusInEvent` override calling `showCalendarWidget()`. This catches keyboard Tab navigation as well.

**Technical Risks:**
- If `showCalendarWidget()` is called on a `QDateEdit` where `calendarPopup` is False, it is a no-op. The existing code already calls `setCalendarPopup(True)` on both date fields — the subclass must retain this. `ClickableDateEdit.__init__` should call `self.setCalendarPopup(True)` to make the widget self-contained.

**Estimated Technical Effort:** XS (0.5 day)

---

## SA Technical Assessment: BC-301 — Paidoff Warning Label

**Feasibility:** High
**Complexity:** Low

**Architectural Impact:**
- `ui/pending_approval_tab.py`: `_build_ui()` (insert QLabel) and `_on_report_selection_changed()` (toggle visibility)

**Layout confirmed from source (lines 170-205):**
```
bottom_widget (QWidget)
  bottom_layout (QVBoxLayout)
    detail_header (QHBoxLayout)  ← Approve/Decline buttons
    [INSERT WARNING LABEL HERE]
    self._rec_table (QTableWidget)
```

The bottom panel uses a QVBoxLayout. The records table (`_rec_table`) is added after `detail_header`. The warning label must be inserted between `bottom_layout.addLayout(detail_header)` and `bottom_layout.addWidget(self._rec_table)`.

**Implementation:**
```python
# In _build_ui(), after bottom_layout.addLayout(detail_header)
self._paidoff_warning = QLabel(
    "This report was generated for a Paidoff loan. "
    "The loan has been moved to history. No extension was applied."
)
self._paidoff_warning.setWordWrap(True)
self._paidoff_warning.setStyleSheet(
    "background-color: #ca6702; color: white; padding: 6px; font-weight: bold;"
)
self._paidoff_warning.setVisible(False)
bottom_layout.addWidget(self._paidoff_warning)
# then: bottom_layout.addWidget(self._rec_table)
```

**Toggle in `_on_report_selection_changed()`:**
```python
# When a report is selected and its records loaded:
is_paidoff = (selected_report.mode == "Paidoff")
self._paidoff_warning.setVisible(is_paidoff)
```

**Technical Risks:**
- If `_on_report_selection_changed()` is called when no report is selected, `mode` is undefined. Guard: default to `setVisible(False)` when no report is selected.

**Estimated Technical Effort:** XS (0.5 day — includes reading the file first)

---

## SA Technical Assessment: CHG-02-EXT — PaidoffDialog Rate Fields

**Feasibility:** High
**Complexity:** Medium (dialog extension + report pipeline wiring)

**Architectural Impact:**
- `ui/dialogs/paidoff_dialog.py`: Add 3 input fields + update return interface
- `ui/view_tab.py`: `_on_paidoff()` method — read new dialog outputs, build ReportRecord, call write_report()
- `data/report_manager.py`: existing `write_report()` and `write_report_records()` API is sufficient — no changes
- `models/report.py`: `REPORT_RECORD_FIELDNAMES` already includes all required fields — no schema change

**Confirmed from models/report.py — no schema change required:**
`REPORT_RECORD_FIELDNAMES` already contains: `interest_rate`, `commission_rate`, `extension_period`, `extension_period_unit`, `tds_flag`, `interest_amount`, `commission_amount`, `tds_amount`. The mode="Paidoff" value is stored in `PENDING_REPORT_FIELDNAMES.mode` — already supports arbitrary mode strings.

**PaidoffDialog extended interface:**

```python
class PaidoffDialog(QDialog):
    # New return interface (getter methods)
    def paidoff_date(self) -> date: ...
    def interest_rate(self) -> float: ...
    def commission_rate(self) -> float: ...
    def tds_flag(self) -> bool: ...
```

**New fields to add in `_build_ui()`:**
```python
# interest_rate: QDoubleSpinBox, range 0.0–100.0, decimals=2, default=12.0, suffix=" %"
self._interest_rate = QDoubleSpinBox()
self._interest_rate.setRange(0.0, 100.0)
self._interest_rate.setDecimals(2)
self._interest_rate.setValue(12.0)
self._interest_rate.setSuffix(" %")

# commission_rate: QDoubleSpinBox, range 0.0–100.0, decimals=2, default=2.0, suffix=" %"
self._commission_rate = QDoubleSpinBox()
self._commission_rate.setRange(0.0, 100.0)
self._commission_rate.setDecimals(2)
self._commission_rate.setValue(2.0)
self._commission_rate.setSuffix(" %")

# tds_flag: QCheckBox, default unchecked
self._tds_flag = QCheckBox("Apply TDS (10% of Interest)")
self._tds_flag.setChecked(False)
```

**Caller in `view_tab.py` `_on_paidoff()` must be updated:**
After `dialog.exec() == QDialog.Accepted`:
1. Read `paidoff_date`, `interest_rate`, `commission_rate`, `tds_flag` from dialog
2. Compute `extension_period = (paidoff_date - loan.due_date).days` if `loan.due_date` else `0`
3. Compute interest: `(loan.amount * interest_rate * extension_period) / (365 * 100)`
4. Compute commission: `(loan.amount * commission_rate * extension_period) / (365 * 100)`
5. Compute tds: `0.1 * interest_amount` if `tds_flag` else `0.0`
6. Build `ReportRecord` with: `extension_period_unit="days"`, `new_giving_date=None`, `new_due_date=None` (Paidoff loans have no post-extension dates)
7. Build `PendingReport` with `mode="Paidoff"`, `status="Pending"`
8. Call `generate_report_id()`, `write_report()`, `write_report_records()` from `data.report_manager`
9. Emit signal to refresh Pending Approval Tab

**TC-401 no-due-date guard:**
```python
if loan.due_date is None:
    extension_period = 0
    interest_amount = 0.0
    commission_amount = 0.0
    tds_amount = 0.0
else:
    extension_period = (paidoff_date - loan.due_date).days
    interest_amount = (loan.amount * interest_rate * extension_period) / (365 * 100)
    commission_amount = (loan.amount * commission_rate * extension_period) / (365 * 100)
    tds_amount = 0.1 * interest_amount if tds_flag else 0.0
```

**Estimated Technical Effort:** M (1 day — dialog extension + report pipeline wiring + test)

---

## Integration Impact Analysis: run_4 Cross-Cutting Concerns

**Affected Systems:**

| System / Service | Type of Impact | Action Required |
|---|---|---|
| `ui/interest_calculator_tab.py` | Additive (ordering fix) | Fix `_on_apply_filters()` only |
| `data/ref_id_manager.py` | Additive (logic fix) | Fix `_active_year_months()` |
| `loan_manager/ref_id_manager.py` | Additive (durability fix) | Fix `_write_meta()` atomic write |
| `ui/view_tab.py` | Additive (performance + correctness fix) | Fix `load_data()` snapshot |
| `ui/widgets.py` | New file | Create `ClickableDateEdit` |
| `ui/entry_tab.py` | Additive (replace QDateEdit) | Import + replace 2 instances |
| `ui/dialogs/paidoff_dialog.py` | Additive (extend dialog) | Add 3 fields + new getter methods |
| `ui/pending_approval_tab.py` | Additive (UI label) | Add QLabel to bottom panel |

**API / Contract Changes:**
- `PaidoffDialog`: new getter methods `interest_rate()`, `commission_rate()`, `tds_flag()`. Callers must be updated to read these new values.
- `_write_meta()` in `loan_manager/ref_id_manager.py`: signature unchanged, behaviour changed (atomic write). No API contract change.
- `_active_year_months()` in `data/ref_id_manager.py`: signature unchanged, return type unchanged (set of YYYY_MM strings). Callers unaffected.
- `ClickableDateEdit` is a drop-in subclass of `QDateEdit` — all existing attribute accesses (`setDate()`, `date()`, `setCalendarPopup()`) remain valid.

**Migration / Rollout Considerations:**
- No schema changes to any CSV file — zero migration risk
- No changes to loans.csv, history.csv, pending_reports.csv, pending_report_records.csv column definitions
- loans_meta.csv: content unchanged, write process changed (atomic). Existing files remain valid.
- `ui/widgets.py` is a new file — no import conflicts

---

## Architecture Decision Records (ADRs) — run_4

### ADR-001 (Confirmed): data/ adapter pattern

**Decision:** `data/` adapter functions resolve paths and delegate all logic to `loan_manager/` classes.
**Status:** Confirmed in source. No changes.
**Rationale:** Tests import from `loan_manager/` with injectable paths. UI imports from `data/` only. This separation enables full unit test coverage without UI dependencies.

### ADR-002 (New): Atomic meta file writes via temp+rename

**Decision:** `loan_manager/ref_id_manager.py` `_write_meta()` writes to a `.tmp` file first, then atomically renames to the target via `pathlib.Path.replace()`.
**Status:** New — to be implemented in run_4.
**Rationale:** Windows NTFS does not guarantee atomic in-place overwrites when the process crashes mid-write. The temp+rename pattern is atomic on both POSIX (rename syscall) and Windows (MoveFileEx semantics). This eliminates the BUG-UTR-2 meta corruption risk on Windows.

### ADR-003 (New): Reference ID bucket key from reference_id field

**Decision:** `_active_year_months()` in `data/ref_id_manager.py` derives the YYYY_MM bucket from `loan.reference_id` (first two underscore-separated segments), not from `loan.giving_date`.
**Status:** New — to be implemented in run_4.
**Rationale:** The reference_id encodes the entry month (today's YYYY_MM at time of creation), not the giving month. Using `giving_date` causes incorrect counter resets when back-dated loans are present.

### ADR-004 (New): Status snapshot before recompute_all()

**Decision:** `view_tab.py` `load_data()` snapshots `{reference_id: status}` from the loaded loan list before calling `recompute_all()`, then calls `update_loan()` only for loans where status changed.
**Status:** New — to be implemented in run_4.
**Rationale:** `recompute_all()` mutates Loan objects in place. The snapshot must be taken before mutation. The fix prevents O(N) unconditional CSV rewrites on every Refresh.

### ADR-005 (New): Shared custom widget module

**Decision:** `ui/widgets.py` is the single location for all custom PySide6 widget subclasses.
**Status:** New — to be implemented in run_4.
**Rationale:** DRY principle. `ClickableDateEdit` is used in at least 3 locations. Centralising in `ui/widgets.py` avoids copy-paste and establishes a pattern for future custom widgets.

### ADR-006 (New): PaidoffDialog extended interface — getter methods

**Decision:** `PaidoffDialog` exposes new getter methods `interest_rate() -> float`, `commission_rate() -> float`, `tds_flag() -> bool` in addition to the existing `paidoff_date() -> date`.
**Status:** New — to be implemented in run_4.
**Rationale:** The dialog stores values as instance variables set in `_on_accept()`. Getter methods are the correct PySide6 dialog pattern — callers read values after `exec()` returns `QDialog.Accepted`.

---

## Non-Functional Requirements Confirmation

| NFR | Status | Notes |
|---|---|---|
| Windows/Mac parity (User-Testing Req 1) | Addressed | All fixes use pure Python/Qt — no OS-specific code paths |
| No new dependencies (R10) | Confirmed | All fixes use pathlib, csv, PySide6 built-ins only |
| Atomic write safety (R3) | Addressed by ADR-002 | temp+rename pattern for loans_meta.csv |
| Performance — O(N) refresh (R10) | Addressed by ADR-004 | Only changed loans trigger CSV write |
| CSV schema stability | Confirmed | Zero schema changes in run_4 |
| Test coverage (R-baseline 197) | Not broken | All fixes are additive/method-scoped |

---

## Component Interaction Diagram — CHG-02-EXT Report Flow

```
User right-clicks loan in View Tab
  → _show_context_menu() → PaidoffDialog.exec()
      PaidoffDialog collects:
        paidoff_date, interest_rate, commission_rate, tds_flag
      Returns QDialog.Accepted
  → _on_paidoff() in view_tab.py:
      mark_paidoff(loan, paidoff_date)         ← data/csv_manager
      report_id = generate_report_id(today)    ← data/report_manager
      write_report(PendingReport(mode="Paidoff"))
      write_report_records([ReportRecord(...)])
      emit data_changed signal
  → PendingApprovalTab.load_reports() triggered
      reads pending_reports.csv
      shows Paidoff report in list
      on selection: _paidoff_warning.setVisible(True)  ← BC-301
```

---

## Open Items for Dev Lead

1. **BUG-UTR-2**: Confirm that `read_all_loans_including_paidoff()` in `data/csv_manager.py` reads from both `loans.csv` and `history.csv`. If it reads only `loans.csv`, then loans moved to history would not be counted in `_active_year_months()` — leading to incorrect counter resets for months where all active loans were paid off but history records exist.

2. **BUG-UTR-4**: Confirm `ClickableDateEdit.__init__` calls `self.setCalendarPopup(True)` to make the widget self-contained. Callers currently set this explicitly — it should be the widget's default.

3. **CHG-02-EXT**: Confirm the signal used to notify `PendingApprovalTab` of a new report. Source shows `data_changed = Signal()` in `view_tab.py` — verify this signal is connected to `pending_approval_tab.load_reports()` in `main_window.py`.

---

## [REVIEW REQUIRED — SA-401]

**Item:** `read_all_loans_including_paidoff()` scope for `_active_year_months()`
**Priority:** Low
**Description:** After Fix A for BUG-UTR-2, `_active_year_months()` derives buckets from `loan.reference_id`. This correctly handles active loans in loans.csv. However, for months where all loans have been paid off (moved to history.csv), loans.csv has no records for that month but history.csv does. If `read_all_loans_including_paidoff()` does not include history.csv records, the counter for that month would be incorrectly reset to 000 on the next entry, potentially generating a reference_id that collides with a historical record.
**Options:**
- (a) Include history.csv loans in `_active_year_months()` — correct semantics, prevents collisions with archived records
- (b) Accept collision with archived records — R4 states paidoff records are removed from loans.csv and the counter tracks active loans only
**SA recommendation:** Option (a) is safer for data integrity. Verify `read_all_loans_including_paidoff()` implementation before finalising Fix A.
