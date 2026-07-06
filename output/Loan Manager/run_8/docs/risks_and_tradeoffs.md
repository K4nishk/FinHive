# Risks and Tradeoffs — Loan Manager

## R-01 — Data Loss on Extend (Accepted)
**Risk**: Extending a loan overwrites `giving_date` and `due_date` with no history preserved.
**Tradeoff**: Simplicity over auditability. Explicitly accepted by user for both single Extend (R4) and batch Pending Approval (R5).
**Mitigation**: None for prototype. Post-prototype: consider append-only audit log.

## R-02 — Crash Between Dual CSV Writes (Medium Risk)
**Risk**: App crash between `loans.csv` write and `history.csv` write during Paidoff operation = record permanently lost.
**Mitigation in scope**: Write target row to `approval_recovery.tmp` before first write. On startup, warn user if file exists.
**Deferred**: Atomic rollback, full transactional safety.

## R-03 — No CSV File Locking (Accepted)
**Risk**: If user opens two instances, writes could conflict.
**Tradeoff**: Single-user app; acceptable risk. No locking implemented.

## R-04 — Duplicate ref_id Across Pending Reports
**Risk**: Two reports containing the same loan record; approving one silently overwrites the other.
**Mitigation**: Warn user on approval. User must explicitly proceed. On proceed, silent overwrite is the defined behaviour.

## R-05 — Delete During Pending Approval
**Risk**: Loan deleted from View Tab while present in a pending report. On approval, record no longer exists.
**Mitigation**: Warn user on approval: "Records in this report have been deleted." User chooses skip-deleted or decline.

## R-06 — Status Recompute on Launch Overrides Manual Toggles
**Risk**: User manually sets Active on an Overdue loan; on next launch, it reverts to Overdue.
**Exception**: Manual Active override always prompts for new due_date (Extend flow). The recompute evaluates against the new due_date — not the original.
**Tradeoff**: Predictable automation over persistent manual state (except Extend path).

## R-07 — Performance at 1500 Records
**Risk**: PySide6 QTableWidget with 1500 rows + inline editing + real-time filter/sort may be sluggish.
**Mitigation**: Use QTableWidget with lazy loading or QAbstractTableModel + QSortFilterProxyModel for scalability.
**Architectural Decision**: Required to be documented in Stage 2 (ADR).

## R-08 — PySide6 Date Picker Bug (Known, MUST FIX)
**Risk**: `showCalendarWidget()` method does not exist on `QDateEdit`; causes `AttributeError`.
**Fix**: Use `calendarPopup(True)` or open a separate `QCalendarWidget` dialog on Tab/double-click.
**Priority**: MUST fix — blocks core UX workflow.

## R-09 — PDF Export Complexity
**Risk**: PDF generation adds a dependency (reportlab or weasyprint); may be overkill for prototype.
**Tradeoff**: Deliver Print option via system print dialog (`QPrintDialog`); native PDF on macOS, PDF printer on Windows.
**Deferred**: Styled PDF generation post-prototype.

## R-10 — Legacy Import (Low Relevance)
**Risk**: Imported records with non-standard ref_ids may collide after auto-assignment.
**Mitigation**: Collision detection and increment loop in import service.
**User Guarantee**: 80% of data will follow standard format; edge cases are acceptable risk.

## R-11 — Interest Calculation Breaking Change
**Risk**: Previous implementation may have used `giving_date` in time calculations.
**Decision**: Authoritative overhaul. `giving_date` is reference-only. Only `extension_period` counts.
**Action**: All calculator logic and tests must be rewritten from scratch. No legacy code reuse.

## R-12 — Windows/macOS Parity
**Risk**: PySide6 may behave differently on Windows vs macOS (date picker, font rendering, theme).
**Mitigation**: User forbids testing drift between OS implementations. Cross-platform testing is mandatory.
