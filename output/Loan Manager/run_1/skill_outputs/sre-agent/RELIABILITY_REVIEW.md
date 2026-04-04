# Loan Manager — SRE Reliability Review
**Date**: 2026-04-03
**Run**: run_1 / Wave 1
**Reviewer Role**: Site Reliability Engineer (SRE)
**Scope**: PySide6 desktop application, single user, CSV file storage, Windows + macOS

---

## 1. Adapted SLO Definition (Desktop App)

### 1.1 Data Durability SLO
**Target**: 100% of committed loan records must survive any single crash.

A "committed" record is one for which the user has received the status-bar confirmation `Loan saved successfully. Reference ID: {ref_id}`. Given that write_loan() appends synchronously to loans.csv and raises on error, this target is achievable. Any record appended before the exception propagates is durable.

**Exception — Paidoff operation**: The Paidoff flow involves two sequential writes (history.csv append + loans.csv rewrite). A crash between Step 2 and Step 3 in the recovery.tmp protocol leaves the record in both files (duplicated). A crash between Step 3 and Step 4 leaves a stale recovery.tmp. Both failure modes must be handled at startup. See Section 3 for protocol assessment.

### 1.2 Recovery Time Objective (RTO)
**Target**: User recoverable within 5 minutes after any crash, with no manual file editing required for common failure modes.

For this desktop application, "recovery" means the app restarts cleanly and all data that was committed before the crash is accessible in the View Tab. The app must detect recovery.tmp at startup and either complete or roll back the interrupted Paidoff operation automatically.

**Current status**: The app performs no startup recovery check for recovery.tmp (see Section 4.3). RTO target is not met until startup recovery logic is implemented.

### 1.3 Recovery Point Objective (RPO)
**Target**: Zero records lost for all operations except the Paidoff crash window.

- **Write new loan**: append-only; RPO = 0 records.
- **Update / Extend / Delete**: full CSV rewrite with no backup; RPO = 0 for normal shutdown. RPO for power-loss mid-rewrite = up to all records in loans.csv. See Section 2.3.
- **Paidoff crash window**: RPO = at most 1 record (the one being marked Paidoff). The recovery.tmp protocol is designed to handle this case but startup recovery is not yet implemented.

### 1.4 Crash Safety Target — Operations That Must Be Atomic

| Operation | Atomic? | Mechanism |
|---|---|---|
| write_loan (new entry) | Yes — append-only | OS-level buffered write; partial append leaves orphan row but does not corrupt existing rows |
| update_loan | No | Full rewrite of loans.csv with no backup; power loss mid-write can produce empty or partial file |
| delete_loan | No | Full rewrite; same risk as update_loan |
| extend_loan | No | Full rewrite; same risk as update_loan |
| batch_extend_loans | No | Single-pass full rewrite; same risk, larger blast radius |
| mark_paidoff | Partial | recovery.tmp sentinel exists; startup recovery handler is absent |

---

## 2. Architecture Reliability Review

### 2.1 Single Points of Failure
The application uses five CSV files as its sole storage layer:

| File | SPOF risk |
|---|---|
| loans.csv | Primary data store. Corruption or deletion causes total data loss for active loans. No backup. |
| history.csv | Paidoff record archive. Corruption loses Paidoff audit trail. No backup. |
| loans_meta.csv | Reference ID high-water mark. Corruption causes ID counter reset and potential ID collision on next entry. |
| pending_reports.csv | Report queue metadata. Corruption loses pending approval queue. |
| pending_report_records.csv | Report line items. Corruption loses in-flight calculation data. |
| recovery.tmp | Crash sentinel. Absence of startup check renders it inert beyond signaling. |

All five files reside in the same `./data/` directory. A single directory-level event (accidental deletion, disk failure, ransomware) destroys all state simultaneously.

### 2.2 Data Durability Patterns — recovery.tmp Protocol Assessment

The protocol as implemented in `loan_manager/csv_manager.py` `mark_paidoff()`:

```
Step 1: Write reference_id to recovery.tmp
Step 2: Append to history.csv
Step 3: Rewrite loans.csv (remaining rows only)
Step 4: Delete recovery.tmp
```

**Failure mode analysis**:

| Crash point | State after crash | Data integrity | Recovery action needed |
|---|---|---|---|
| Before Step 1 | No recovery.tmp. No writes made. | Safe — record still in loans.csv | None |
| After Step 1, before Step 2 | recovery.tmp present. history.csv unchanged. loans.csv unchanged. | Safe — record still in loans.csv | Delete recovery.tmp; record is still active |
| After Step 2, before Step 3 | recovery.tmp present. Record in both history.csv and loans.csv. | Duplicated — record appears active but is in history | Complete Step 3: remove from loans.csv, then delete recovery.tmp |
| After Step 3, before Step 4 | recovery.tmp present. Record in history.csv only. loans.csv correct. | Correct data state; stale sentinel | Delete recovery.tmp only |
| After Step 4 | No recovery.tmp. Normal completed state. | Correct | None |

**Assessment**: The protocol design is sound for the two-write atomicity requirement stated in R3. However, the implementation has no startup recovery handler to act on a detected recovery.tmp, making the sentinel a diagnostic artifact rather than an automatic recovery mechanism. All four crash scenarios above require manual intervention or are silently ignored.

Additionally, the recovery.tmp stores only the `reference_id` string. This is sufficient for Steps 3 and 4 of the recovery action but requires the app to re-read loans.csv and history.csv at recovery time to determine which recovery action to take (complete vs. rollback).

### 2.3 Backup Strategy Adequacy
**Current state**: No automated backup is implemented.

Requirements explicitly identify a pre-destructive-operation backup of loans.csv as a deferred risk (R3: "The app should create a timestamped backup copy of loans.csv before any destructive operation... For prototype scope, this is not required but is a meaningful risk which has to be deferred for future.").

Risk implications that are active today despite the deferral:
- `update_loan()`, `delete_loan()`, `extend_loan()`, and `batch_extend_loans()` all perform full CSV rewrites with no backup. A power loss or OS crash mid-rewrite produces a zero-byte or partial loans.csv.
- The `_write_raw()` method in `loan_manager/csv_manager.py` opens the file in `"w"` mode, which truncates the file before writing. If the process is killed after truncation but before all rows are written, all records are lost.
- The bulk Approve path (R5 batch extension) compounds this risk: a single `_write_raw()` call updates multiple records atomically from the application's perspective but offers no crash safety.

**[REVIEW REQUIRED]**: For prototype acceptance, the team should decide whether write-through truncation is acceptable given the user's hardware environment (Windows laptop). Sudden power loss on a Windows laptop without a UPS makes this a real-world risk. A write-to-temp-then-rename pattern would mitigate it at low implementation cost.

### 2.4 File Write Atomicity
The `_write_raw()` implementation opens directly to the target path in write mode:
```python
with open(str(path), "w", newline="", encoding="utf-8") as fh:
```
This is a non-atomic write. The standard mitigation for single-user desktop apps is:
1. Write to `loans.csv.tmp`
2. On success, rename `loans.csv.tmp` → `loans.csv` (atomic on both Windows and POSIX for same-filesystem renames)
3. On failure, leave `loans.csv` intact

This pattern is not implemented. It is not required by the current requirements but is the standard SRE recommendation for all full-rewrite operations.

---

## 3. Data Model Reliability Review

### 3.1 Partial Write on Power Loss
If power is lost during `_write_raw()` after file truncation:
- loans.csv becomes empty (zero bytes) or contains a partial header plus partial rows.
- `_read_raw()` checks `path.stat().st_size == 0` and returns `[]` for the zero-byte case, which means the app starts with no data and shows an empty View Tab with no error message to the user.
- For a partially-written file (some rows present, last row truncated), `csv.DictReader` will return all rows up to the truncated line; the final truncated row is silently dropped by Python's CSV parser in most cases. This results in silent data loss of the last row.

**[REVIEW REQUIRED]**: The current behavior on zero-byte loans.csv (silent empty state) is indistinguishable from a freshly installed application. The user receives no warning. A startup check comparing last-known row count against current row count would provide early detection, but requires storing a record count in loans_meta.csv.

### 3.2 Header-Only CSV Edge Case
`_read_raw()` returns `[]` when `path.stat().st_size == 0`. However, a header-only loans.csv (written by `_write_raw()` with an empty `rows` list) has non-zero size. In this case `csv.DictReader` iterates zero rows and returns an empty list. This is correctly handled — a header-only file is treated as empty with no crash.

Test coverage confirms this: `test_read_loans_header_only_returns_empty_list` and `test_read_loans_empty_file_returns_empty_list` both pass.

### 3.3 recovery.tmp Present at Startup
The current application does not scan for recovery.tmp at startup. The behavior today is:

- The mark_paidoff() operation may have completed successfully but left a stale recovery.tmp (Step 4 failed silently — `recovery_path.unlink()` failure in `data/csv_manager.py` is logged as a warning only and does not raise).
- The app starts normally, does not notify the user, and the stale recovery.tmp persists indefinitely.
- On the next Paidoff operation, recovery.tmp is overwritten with the new reference_id (Step 1 uses `write_text()` which overwrites). The prior stale sentinel is silently discarded.

If the crash occurred between Steps 2 and 3 (record in both history and loans), the record remains duplicated across loans.csv and history.csv. The duplicate in loans.csv is visible in the View Tab as an Active record. The user is unaware of the inconsistency.

**Required startup recovery logic** (not yet implemented):
1. Check if `./data/recovery.tmp` exists.
2. Read the `reference_id` from recovery.tmp.
3. Check if reference_id is present in loans.csv.
   - If yes: the Step 3 write was not completed. Complete Step 3 (remove from loans.csv). Then delete recovery.tmp.
   - If no: loans.csv is already correct. Delete recovery.tmp.
4. Log the recovery action taken.

### 3.4 loans_meta.csv Corruption
If loans_meta.csv is corrupted or deleted, `RefIdManager._read_meta()` returns `{}` (empty dict), which resets all counters to zero. The next `next_ref_id()` call returns `YYYY_MM_001` regardless of existing records. This creates ID collisions with existing loans.

R4 requires: "When a legacy-format imported record is auto-assigned a standard ref_id that collides with an existing record, the service should increment until a non-colliding ID is found." This collision-avoidance logic should also apply to the counter-from-scratch scenario. **[REVIEW REQUIRED]**: Verify whether the current `next_ref_id()` implementation checks for existing IDs in loans.csv before returning, or whether it blindly uses the meta counter value. Based on code review, it does not check loans.csv — it trusts the counter. Collision avoidance on meta corruption is absent.

---

## 4. Implementation Reliability Review

### 4.1 Logging Strategy
**Status**: Implemented and correctly configured.

`main.py` calls `_setup_logging()` before any PySide6 import. The log configuration writes to `./data/logs/app.log` (as required by R7) and mirrors to `stderr`. The log directory is created with `mkdir(parents=True, exist_ok=True)`.

Observations:
- Log rotation is not configured. `app.log` grows unbounded. For a desktop app with 1500 records and infrequent use, this is acceptable for prototype scope, but the file will accumulate entries across all sessions indefinitely.
- `logging.basicConfig()` uses `FileHandler` without `mode='a'` specified. Python's `FileHandler` defaults to append mode, which is correct.
- Both csv_manager modules (`data/csv_manager.py` and `loan_manager/csv_manager.py`) use `logging.getLogger(__name__)`. The `loan_manager/csv_manager.py` does not call `logger.info/warning/error` at all — it is the class-based module used by tests. The module-level `data/csv_manager.py` has comprehensive logging. The discrepancy means that operations routed through the class-based path (e.g., batch_extend_loans called from `data/csv_manager.py` which delegates to `loan_manager/csv_manager.py`) log only at the outer wrapper level, not the inner class level.

**[REVIEW REQUIRED]**: The dev lead should confirm which of the two csv_manager implementations is the authoritative path for production UI calls. `data/csv_manager.py` and `loan_manager/csv_manager.py` appear to be partially redundant implementations. `data/csv_manager.py:batch_extend_loans()` calls `loan_manager/csv_manager.py:CSVManager().batch_extend_loans()`. This creates a two-layer delegation that is confusing and adds risk of behavioral divergence.

### 4.2 Error Handling on CSV Reads/Writes

**Reads** (`data/csv_manager.py:_read_all_rows()`):
- Wraps the file open in a try/except; on failure returns `[]` and logs error. This is a safe default but is silent to the user.
- `read_loans()` wraps `Loan.from_csv_row()` in try/except per row; malformed rows are logged as warnings and skipped. This is correct defensive behavior.

**Writes** (`data/csv_manager.py:_write_rows()`):
- No try/except wrapping. Raises directly to the caller.
- `write_loan()` wraps `_write_rows` equivalent (`path.open("a")`) in try/except, logs error, and re-raises. This is correct — the caller (UI) should handle the exception.
- `update_loan()` calls `_write_rows()` without a try/except wrapper. A write failure leaves loans.csv in an indeterminate state and is unhandled.
- `delete_loan()` has the same gap.
- `extend_loan()` has the same gap.

**Class-based CSVManager** (`loan_manager/csv_manager.py`):
- `_write_raw()` has no exception handling. Raises to caller.
- `mark_paidoff()` has no try/except around individual steps. If Step 2 (history append) raises, recovery.tmp is left present and the exception propagates. If Step 3 (loans rewrite) raises, recovery.tmp is left present and the exception propagates. Both of these are the intended behavior per the recovery protocol. However, there is no logging in the class-based implementation, which means a failure during batch_extend_loans leaves no diagnostic trace.

### 4.3 Startup Recovery Check — recovery.tmp Detection
**Status**: Not implemented in either `main.py` or the main window initialization.

`main.py` calls `_setup_logging()` then creates `MainWindow`. Neither performs a recovery.tmp check. The `_ensure_loans_csv()` and `_ensure_history_csv()` helpers in `data/csv_manager.py` are called lazily on first read, not at startup.

The absence of startup recovery means:
- Any Paidoff crash scenario requiring Step 3 completion goes undetected.
- The stale recovery.tmp from a Step 4 failure persists until the next Paidoff operation overwrites it.
- Users who experience a crash during Paidoff and restart the app see the loan still listed as Active in the View Tab, believing the Paidoff operation did not happen, when in fact it was partially completed (record is in history.csv).

**[REVIEW REQUIRED]**: Startup recovery handler must be implemented before user acceptance testing of the Paidoff feature. The User-Testing Requirement 1 already notes the user was unable to test marking a record as Paidoff — this gap should be resolved in the next development cycle.

### 4.4 Batch Write Optimization (R10)
R10 states: "Adding batch write option to avoid O(N^2) write operations on startup."

`batch_extend_loans()` is implemented in `loan_manager/csv_manager.py` with a single-pass CSV rewrite (`batch_extend_loans` in PD-30). This correctly avoids N separate rewrites for the Pending Approval batch approval path.

However, the startup status recomputation (R3: "The app auto-recomputes status on every app launch") is not visible in the files reviewed. If status recomputation triggers individual `update_loan()` calls per record (each doing a full CSV rewrite), that is O(N^2) for N records. For 1500 records, this is 1500 full rewrites of a ~150KB file — approximately 225MB of write I/O at startup.

**[REVIEW REQUIRED]**: The dev lead should confirm that the startup status recomputation is implemented as a single batch CSV rewrite (read all, update statuses in memory, write once), not as N individual `update_loan()` calls. This is a correctness-adjacent reliability concern because a slow startup on Windows (with antivirus scanning each write) can cause the app to appear hung.

---

## 5. Startup Reliability Section

### 5.1 Execution Failure Modes (Packaged App)

**Python not installed / wrong version**
- `run_windows.bat` performs Python version detection using `FOR /F` parsing of `python --version` output. This correctly checks major >= 3 and minor >= 10.
- `run_mac.sh` performs equivalent checks using `python3 -c "import sys; ..."`.
- **Gap**: `run_windows.bat` calls `python` (not `python3`). On Windows, `python` may resolve to the Microsoft Store stub which returns a non-error exit code but launches the Store. The version parsing then receives unexpected output. The bat file does not handle this edge case.
- **Gap**: `run_mac.sh` uses `set -euo pipefail` which causes the script to exit immediately on any command failure, including the pip install step. If pip install fails partway through (e.g., network unavailable for a dependency), the script exits with no cleanup message. The user sees a failure but no diagnostic output because `--quiet` suppresses pip output.

**PySide6 not installed**
- Handled by `pip install -r requirements.txt` in both launchers. If installation fails, the subsequent `python main.py` call will fail with `ModuleNotFoundError: No module named 'PySide6'`. Neither launcher catches this error and provides a user-friendly message.

**data/ directory missing**
- `_data_dir()` in `data/csv_manager.py` calls `data.mkdir(parents=True, exist_ok=True)`. The data directory is created on first access. This is handled correctly.
- The `./data/logs/` directory is created by `_setup_logging()` in `main.py` before any other import. This is also handled correctly.

**loans.csv corrupted**
- `_read_raw()` in `loan_manager/csv_manager.py` returns `[]` for zero-byte files. For a non-zero-byte corrupted file (e.g., binary garbage), Python's `csv.DictReader` will raise `UnicodeDecodeError` or return rows with None keys. The module-level `_read_all_rows()` in `data/csv_manager.py` wraps this in try/except and returns `[]`, logging an error. The app continues and shows an empty View Tab.
- **User experience gap**: The user sees an empty View Tab with no banner or dialog indicating that loans.csv could not be read. This is indistinguishable from a clean installation. The user may enter new records on top of a corrupted file, overwriting it.

**recovery.tmp detected at startup**
- Not detected. App starts normally. See Section 4.3 for full analysis.

---

## 6. Production Readiness Checklist (Desktop Adaptation)

```
## Desktop App Readiness Checklist

**Data Safety**
- [x] Atomic write protocol for Paidoff operation implemented (recovery.tmp) — sentinel write exists
- [ ] Recovery.tmp detected and handled at app startup — NOT IMPLEMENTED
- [x] Logging configured to ./data/logs/app.log — IMPLEMENTED in main.py
- [ ] Backup copy before bulk Approve noted as deferred risk — DEFERRED (documented in R3)
- [ ] Write-to-temp-then-rename pattern for full CSV rewrites — NOT IMPLEMENTED (low priority but meaningful risk)

**Resilience**
- [x] App handles missing loans.csv gracefully — _ensure_loans_csv() creates it; _read_raw() returns [] for absent file
- [x] Malformed CSV rows logged and skipped (not crash) — read_loans() wraps from_csv_row() per-row with warning log
- [x] Header-only CSV treated as empty (no crash) — confirmed by test coverage
- [ ] Corrupted loans.csv (non-zero size, non-parseable) surfaces a user-visible warning — NOT IMPLEMENTED
- [ ] Counter-reset-on-meta-corruption collision check — NOT IMPLEMENTED (loans_meta.csv corruption causes silent ID reuse risk)

**Deployment**
- [x] run_windows.bat checks Python version — IMPLEMENTED
- [x] run_mac.sh checks Python version — IMPLEMENTED
- [x] Virtual env setup automated — IMPLEMENTED in both launchers
- [ ] run_windows.bat handles Microsoft Store Python stub edge case — NOT HANDLED
- [ ] pip install failure provides user-friendly error message — NOT HANDLED (quiet mode suppresses output)

**Verdict**: Hold
```

**Hold reasons** (blocking for user acceptance testing):
1. Startup recovery.tmp handler is absent. Paidoff crash scenarios result in invisible data inconsistency.
2. Corrupted loans.csv produces silent empty state with no user notification.
3. Batch write at startup for status recomputation is unconfirmed — O(N^2) risk for 1500 records.

---

## 7. Reliability Risks Register

| Risk ID | Description | Source | Severity | Status |
|---|---|---|---|---|
| RR-01 | recovery.tmp startup handler absent — crashed Paidoff leaves duplicate record silently | R3, Section 4.3 | High | [REVIEW REQUIRED] — must implement before UAT of Paidoff feature |
| RR-02 | Full CSV rewrite uses write-truncate pattern — power loss mid-write destroys all loans.csv data | Section 2.3, 2.4 | High | [REVIEW REQUIRED] — write-to-temp-then-rename not implemented; deferred backup also absent |
| RR-03 | Corrupted loans.csv (non-zero, non-parseable) silently presents as empty application state | Section 5.1 | Medium | [REVIEW REQUIRED] — no user-visible warning on read failure |
| RR-04 | loans_meta.csv corruption causes counter reset; no collision check against existing loans.csv IDs | Section 3.4 | Medium | [REVIEW REQUIRED] — ID collision on meta corruption is silent |
| RR-05 | Stale recovery.tmp from Step 4 failure (unlink warning) persists indefinitely and is overwritten by next Paidoff | Section 3.3 | Low | Acceptable for prototype; document expected behavior |
| RR-06 | O(N^2) startup write risk if status recomputation uses N individual update_loan() calls | R10, Section 4.4 | Medium | [REVIEW REQUIRED] — confirm single batch rewrite is used |
| RR-07 | No log rotation — app.log grows unbounded across all sessions | Section 4.1 | Low | Acceptable for prototype scope; address before production |
| RR-08 | Two csv_manager implementations (data/csv_manager.py and loan_manager/csv_manager.py) with partial behavioral overlap — divergence risk on future changes | Section 4.1 | Medium | [REVIEW REQUIRED] — dev lead to designate authoritative implementation and consolidate |
| RR-09 | pip install failure during launcher execution not surfaced to user — silent with --quiet flag | Section 5.1 | Low | Acceptable for prototype; add error output redirection |
| RR-10 | No automated backup of any data file — a single accidental deletion of ./data/ is total and unrecoverable | Section 2.1 | High | Deferred per R3; risk accepted by product owner; must be documented in user guide |
| RR-11 | run_windows.bat python version check may fail against Microsoft Store Python stub | Section 5.1 | Low | [REVIEW REQUIRED] — test on target Windows environment |
| RR-12 | Pending reports queue (pending_reports.csv, pending_report_records.csv) has no crash safety or recovery protocol | Not covered by current recovery.tmp implementation | Medium | [REVIEW REQUIRED] — if approval operation crashes mid-write, report queue state is indeterminate |
| RR-13 | batch_extend_loans() skips unknown reference_ids silently — if approval of a report with a deleted loan fires batch extend, the deleted record is silently ignored | loan_manager/csv_manager.py line 215-228 | Low | Acceptable per R5 requirement ("approval updates only the records that still exist") but confirmation warning is expected |

---

## 8. Summary

The Loan Manager prototype has a sound basic architecture for a single-user CSV-based desktop application. The recovery.tmp sentinel for the Paidoff atomic write is correctly designed and test-covered. Logging infrastructure is in place and functioning.

The primary reliability gap is the absence of a startup recovery handler. This makes the recovery.tmp protocol a detection mechanism only, not a recovery mechanism. Until a startup check is implemented, the Paidoff crash scenario results in a record being duplicated across loans.csv and history.csv with no user notification and no automatic correction.

The second significant risk is the write-truncate pattern used for all full CSV rewrites. While acceptable under normal operating conditions for a desktop application, it offers no protection against power loss mid-write. The write-to-temp-then-rename pattern is the standard low-cost mitigation and should be considered before the prototype is handed to the Windows end-user.

The dual csv_manager implementation (data/ vs loan_manager/) should be consolidated by the dev lead to reduce maintenance surface area and ensure consistent logging and error handling across all code paths.
