# Loan Manager — Reliability Review
**Agent:** sre-agent (Wave 1)
**Run:** run_6
**Date:** 2026-04-04
**Phase:** Phase 3 Closure / Phase 4 Reliability Audit

---

## Reliability Status: GOOD — No New Critical Gaps

Phase 3 implementation introduced no new reliability regressions. All previously-identified crash safety patterns are in place. This review focuses on Phase 4 items and confirms existing protections.

---

## Data Durability Audit (Desktop-CSV Context)

### Implemented Protections (Confirmed)

| Protection | Location | Status |
|---|---|---|
| approval_recovery.tmp written before batch_extend_loans() | pending_approval_tab._on_approve() | CONFIRMED |
| approval_recovery.tmp written before mark_paidoff() | pending_approval_tab._on_approve() | CONFIRMED |
| approval_recovery.tmp deleted after successful approval | pending_approval_tab._on_approve() | CONFIRMED |
| Seed guard: seeding skips if data rows present | data/seed.py | CONFIRMED |
| loans_meta.csv updated after seeding | data/seed.py | CONFIRMED |
| Logging to ./data/logs/app.log | main.py _setup_logging() | CONFIRMED |
| Python version check in run scripts | run_mac.sh, run_windows.bat | CONFIRMED |
| ISO 8601 date format enforced on all writes | csv_manager.py, view_tab.py, entry_tab.py | CONFIRMED |

### Deferred Protections (Documented per R3)

| Risk | Deferred Item | Priority for Post-MVP |
|---|---|---|
| Backup copy of loans.csv before Paidoff/bulk Approve | Timestamped .bak file before destructive write | Recommended P2 |
| Full atomic write for loans.csv + history.csv pair | Two-phase commit or temp-file swap | Recommended P2 |
| CSV corruption on mid-write crash | approval_recovery.tmp handles detection; full recovery not automated | P2 |

These are explicitly accepted for prototype scope per R3 requirements text.

---

## Phase 4 Reliability Considerations

### TC-05: Paidoff Guard — SRE Perspective

If TC-05 is not implemented (no guard), the following failure scenario exists:
1. User generates Paidoff report #1 for loan L1
2. User generates Paidoff report #2 for loan L1 (duplicate)
3. User approves report #1 → mark_paidoff(L1) succeeds → L1 moved to history.csv
4. User approves report #2 → mark_paidoff(L1) called again → ValueError raised (L1 not in loans.csv)

**SRE Assessment:** The ValueError in step 4 is caught by the error handler and logged. No data corruption occurs. But the report stays in Pending Approval queue in "stuck" state (neither approved nor declined automatically). The user must manually decline the orphaned report.

**SRE Recommendation:** Implement TC-05 Option A (disable guard) to prevent the stuck report scenario. The error recovery is graceful but confusing for the user.

### TC-08: paidoff_date Recovery Scenario

With the current Option A (field reuse), the approval recovery scenario is:

1. approval_recovery.tmp written with report_id
2. mark_paidoff() called → crash between loans.csv write and history.csv write
3. On restart: approval_recovery.tmp exists → recovery UI should detect and prompt user

**SRE Gap:** The current implementation writes approval_recovery.tmp but does NOT read it on startup to prompt recovery. This means a crash mid-approval leaves an inconsistent state with no automatic detection.

**SRE Recommendation for Phase 4 (Low priority):** Add startup check for approval_recovery.tmp existence in `main.py` and display a warning: "An approval was in progress when the application last closed. Please check the Pending Approval queue and manually verify loan records." This is a safe-to-defer warning, not a blocking issue.

### [REVIEW REQUIRED] SRE-01 — Startup Recovery Warning
Should Phase 4 include a startup check for approval_recovery.tmp? Recommended: Yes, as a non-blocking informational warning. Effort: Small (15 lines in main.py).

---

## Platform Reliability (Cross-Platform)

### Mac vs Windows Path Handling
Confirmed: `pathlib.Path` used throughout. No hardcoded path separators. No OS-specific file handling. UTR1 fix uses `.lower()` which is OS-agnostic (Python built-in). No testing drift between platforms.

### Python Version Compatibility
Requirements.txt constrains PySide6 and dateutil. Python 3.10+ confirmed. Both run scripts check Python version. No f-string or walrus operator features requiring Python 3.10+ minimum that aren't guarded.

### PySide6 Stability
`ClickableDateEdit.showCalendarWidget()` was previously raising AttributeError. Fix confirmed in widgets.py — the correct PySide6 API `showCalendarWidget()` is used. No other known PySide6 API mismatches.

---

## Operational Observability

| Log Event | Level | Verified |
|---|---|---|
| Application start | INFO | Yes — logging setup before imports |
| Sample data seeded | INFO | Yes — data/seed.py |
| Loan saved | INFO | Yes — entry_tab.py |
| Loan updated | INFO | Yes — view_tab.py |
| Loan deleted | INFO | Yes — view_tab.py |
| Loan extended | INFO | Yes — view_tab.py |
| Report generated | INFO | Yes — calculation_dialog.py |
| Report approved | INFO | Yes — pending_approval_tab.py |
| Report declined | INFO | Yes — pending_approval_tab.py |
| Paidoff archived | INFO | Yes — pending_approval_tab.py |
| Status recomputed | INFO | Yes — view_tab.py (only logs when changes occur) |
| Errors | ERROR | Yes — all exception handlers log before QMessageBox |

Logging is comprehensive. Log file rotation is not implemented (single app.log) — acceptable for prototype with ~1500 records.

---

## Phase 4 Readiness — SRE Verdict

**READY for Phase 4 implementation** with the following notes:
1. TC-05 implementation is a reliability improvement (prevents stuck Pending reports)
2. Startup recovery.tmp check is a low-effort reliability improvement (defer to Phase 4 if user prefers)
3. No blocking reliability issues remain
