# SRE Agent: Reliability Review — Loan Manager run_4
**Date:** 2026-04-04
**Run:** run_4 (Phase 3 Closure)
**Agent:** sre-agent (Wave 1)
**Application type:** PySide6 desktop CSV application — single-user, Windows primary + Mac secondary
**SLO adaptation:** Uptime SLOs not applicable. Reliability posture adapted to data durability, crash safety, and write atomicity.

---

## Adapted SLO Definition: Desktop CSV Application

For a single-user desktop application using CSV files as persistence, traditional availability and latency SLOs do not apply. The relevant reliability contract is:

| Signal | Metric | Target | Measurement |
|---|---|---|---|
| Data durability | Zero loan records permanently lost per session | 100% | Manual verification on test data set |
| Write atomicity | Zero partial-write corruptions of loans.csv per crash event | 100% | Crash injection test |
| Reference ID uniqueness | Zero duplicate reference_ids generated per 30-day run | 100% | Automated test — 10 consecutive rapid entries |
| Refresh safety | Zero unintended data overwrites per Refresh click when no status has changed | 100% | Log inspection — zero "Loan updated" entries |
| Startup recovery | App starts cleanly after crash, stale recovery.tmp detected and reported | 100% | Crash simulation on Windows |
| Log completeness | All write operations (create, update, delete, paidoff, extend, approve) emit a structured log line | 100% | Log audit |

**Error budget:** Not applicable — single-user, no SLA commitment. All reliability gaps are improvement candidates prioritised by impact severity.

---

## SRE Architecture Reliability Review: run_4 scope

**Reviewed:** SA architecture design for BUG-UTR-2 (atomic write), BUG-UTR-3 (refresh safety), CHG-02-EXT (paidoff pipeline), BC-301 (UI label), BUG-UTR-1, BUG-UTR-4.

### Reliability checklist

- [x] Single points of failure — loans.csv is the single authoritative store. This is accepted (R8: single-user, no DB needed). Recovery mechanisms exist for the most destructive operation (paidoff).
- [x] Retry logic — Not applicable for local CSV writes. Errors are raised and logged.
- [ ] **Circuit breakers** — No circuit breaker on CSV read/write. Failure during update_loan() currently raises without cleanup. For a desktop app this is acceptable, but a full-file rewrite mid-crash can leave loans.csv in a truncated state. **Status: known gap, deferred per R3 prototype scope note.**
- [x] Graceful degradation — load_data() wraps in try/except and shows QMessageBox.critical on failure. App continues running even if a Refresh fails.
- [ ] **Data durability — loans.csv write path** — `_write_rows()` opens with mode `"w"` (truncates immediately), then writes rows. If process is killed between open("w") and writerows completion, loans.csv is truncated to header only. This is the same non-atomic pattern as loans_meta.csv, but for the primary data file. **Status: not in run_4 scope per PO. Flag for Phase 4.**
- [x] loans_meta.csv atomic write — BUG-UTR-2 Fix B addresses this. temp+rename pattern eliminates corruption on crash.
- [x] recovery.tmp — covers the Paidoff two-write protocol.
- [x] approval_recovery.tmp — covers batch approval.
- [x] Stateless where possible — UI layer is stateless relative to CSV. All state is in CSV files.

### Observability checklist

- [x] Structured logs at key decision points — `logger.info()` on write_loan, update_loan, delete_loan, mark_paidoff, extend_loan, batch_extend_loans, generate_ref_id.
- [x] Log file location — `./data/logs/app.log` with rotating handler (configured in main.py).
- [x] Log format — `%(asctime)s [%(levelname)s] %(name)s: %(message)s` — includes timestamp, level, module name.
- [ ] **Log rotation** — main.py uses `FileHandler`, not `RotatingFileHandler`. Over months of daily use, app.log will grow unbounded. **Status: low risk at prototype scale (~1500 records), flag for Phase 4.**
- [ ] **No structured log on Refresh zero-writes** — After BUG-UTR-3 fix, the app should emit `logger.debug("No status changes on Refresh — skipping writes")` to confirm the optimisation is working. Without this, the user cannot verify the fix is effective by reading the log. Dev Lead must add this log line.
- [ ] **No startup recovery.tmp detection log** — If recovery.tmp exists on startup, the app silently proceeds. There is no startup check that reads recovery.tmp, warns the user, and offers guided recovery. **Status: gap — user cannot detect a partially-completed Paidoff operation from a prior crash.**

**Verdict:** Approved with conditions — BUG-UTR-2 Fix B is the critical reliability fix for run_4. The non-atomic loans.csv write is the largest outstanding gap but is deferred per prototype scope.

---

## SRE Data Model Review: run_4

**Reviewed:** DM agent data contract for run_4 (zero schema changes).

### Durability checks

- [x] No replication needed — single-user, single-machine.
- [ ] **No automated backup** — R3 notes: "The app should create a timestamped backup copy of loans.csv before any destructive operation (Paidoff/bulk Approve) — deferred for future." This gap remains open. **Failure scenario: user accidentally marks the wrong loan as Paidoff. Without a pre-operation backup, the only recovery is manual history.csv inspection.** Flag for Phase 4 — user impact is moderate, recovery is manual but possible.
- [x] Migration rollback — not applicable (no schema changes in run_4).
- [x] recovery.tmp RPO — covers the Paidoff two-write window. If crash occurs between history.csv append and loans.csv removal, the record exists in both files. Recovery: manually remove the duplicate row from loans.csv using reference_id in recovery.tmp.

**RPO (Recovery Point Objective):** Last successful CSV write — typically seconds. For a single-user app this is acceptable.
**RTO (Recovery Time Objective):** Time to manually identify and fix the partial write using recovery.tmp guidance — estimated 5 minutes with runbook.

**Feedback to DM:**
- reports_meta.csv has the same non-atomic write pattern as loans_meta.csv. Low risk (report_id collision is less severe than reference_id collision) but worth noting for Phase 4.

**Verdict:** Approved for run_4 scope. Two open items flagged for Phase 4 (backup and log rotation).

---

## Focus Area 1: BUG-UTR-2 — loans_meta.csv Atomic Write

### Current state (as-is)

`loan_manager/ref_id_manager.py` `_write_meta()` line 112:
```python
with self._meta_path.open("w", newline="", encoding="utf-8") as fh:
    writer.writeheader()
    writer.writerows(rows)
```

`open("w")` truncates the file immediately. If the process is killed between line 112 (truncation) and the end of `writerows()`, loans_meta.csv is left with header only (all counters lost) or partially written.

**Windows-specific risk:** On Windows, file system write caching means `open("w")` may not flush immediately, but the truncation is visible to other readers from the moment the file handle is opened. On a crash, the OS may not flush the write buffer, leaving a zero-byte or header-only file.

### After fix (to-be)

```python
tmp = self._meta_path.with_suffix(".tmp")
# write all rows to tmp
tmp.replace(self._meta_path)  # atomic rename
```

`Path.replace()` uses `os.replace()` which on POSIX maps to `rename(2)` (atomic) and on Windows uses `MoveFileEx` with `MOVEFILE_REPLACE_EXISTING` (atomic within the same NTFS volume). The original loans_meta.csv is never truncated until the rename succeeds.

### Crash scenario coverage

| Crash timing | Before fix | After fix |
|---|---|---|
| Before open("w") / before tmp creation | loans_meta.csv intact | loans_meta.csv intact |
| After open("w") truncates / after tmp created but incomplete | loans_meta.csv = header only (counters lost) | loans_meta.csv intact, loans_meta.tmp orphaned |
| After writerows but before close | loans_meta.csv = partial rows (OS buffer) | loans_meta.csv intact, loans_meta.tmp = partial |
| After file close but before rename | N/A | loans_meta.csv intact, loans_meta.tmp = complete |
| After rename | N/A | loans_meta.csv = updated (atomic) |

**Recovery from orphaned .tmp:** On next startup, if loans_meta.tmp exists, the app can safely ignore it (delete on next _write_meta call via Path.replace overwriting). No manual intervention needed.

**SRE verdict on BUG-UTR-2 Fix B:** Required for run_4. Eliminates the primary crash-corruption vector for reference_id uniqueness.

---

## Focus Area 2: BUG-UTR-3 — Unconditional CSV Rewrite on Refresh

### Current state (as-is)

`ui/view_tab.py` `load_data()`:
```python
loans = recompute_all(loans, date.today())
for loan in loans:
    update_loan(loan)  # full loans.csv rewrite per loan
```

For N=1500 loans, this triggers 1500 sequential full-file rewrites on every Refresh click. Each `update_loan()` call:
1. Reads all rows from loans.csv
2. Rebuilds the full row list with one row replaced
3. Writes the entire file back (open "w" + writerows)

**Data integrity risk:** Each `update_loan()` write truncates loans.csv and rewrites it. If a crash occurs during any of the 1500 writes, loans.csv is left truncated at the point of the crash. With 1500 loans, the probability of a crash during at least one write is non-trivial on an unstable Windows machine. The bug also means that any in-flight manual edit the user has not yet saved is overwritten by the status-only refresh.

**Performance impact:** With 1500 rows, 1500 full-file rewrites = 1500 * O(N) operations = O(N^2) per Refresh. At 1500 rows this is measurable latency (seconds on a slow disk).

### After fix (to-be)

```python
snapshot = {loan.reference_id: loan.status for loan in loans}
loans = recompute_all(loans, date.today())
for loan in loans:
    if loan.status != snapshot.get(loan.reference_id):
        update_loan(loan)
```

In the common case (no status transitions today), zero writes occur. Only genuine status changes trigger writes.

**SRE verdict on BUG-UTR-3 fix:** Required for run_4. Both a data integrity fix and a performance fix.

**Required log line (SRE mandate):** After the fix, Dev Lead must add:
```python
changed = [l for l in loans if l.status != snapshot.get(l.reference_id)]
if not changed:
    logger.debug("Refresh: no status changes — skipping all writes")
else:
    logger.info("Refresh: %d loan(s) status changed — writing", len(changed))
```
This enables users to verify the fix is working by checking app.log.

---

## Focus Area 3: recovery.tmp and approval_recovery.tmp — Coverage Assessment

### recovery.tmp (Paidoff two-write protocol)

**Coverage:** Covers the window between history.csv append (step 2) and loans.csv removal (step 3) in `mark_paidoff()`.

**Gap 1 — No startup detection:** On application startup, there is no code that checks whether recovery.tmp exists and warns the user. If the app crashed after step 2 (history.csv append) but before step 3 (loans.csv removal), the loan is in both files. Without a startup check, the user continues working with a duplicate record — the loan is visible in View Tab AND in history.csv.

**Gap 2 — No guided recovery:** The recovery.tmp contains only the reference_id. There is no in-app workflow to detect and resolve the duplicate. The user must manually edit CSV files.

**Recommended startup check (Phase 4):**
```python
if recovery_path.exists():
    ref_id = recovery_path.read_text().strip()
    # Check if ref_id still in loans.csv — if yes, complete step 3
    # Log WARNING: "Incomplete Paidoff detected for {ref_id}, completing recovery"
    logger.warning("Startup recovery: completing Paidoff for %s", ref_id)
    # delete from loans.csv, delete recovery.tmp
```

**Impact if not fixed:** User sees a "ghost" loan in View Tab that was already paid off. If they edit or extend it, data diverges between loans.csv and history.csv permanently.

**[REVIEW REQUIRED — SRE-001]:** Should startup recovery for recovery.tmp be added in run_4 or deferred to Phase 4? Impact: rare event (requires a crash between two fast writes), but when it occurs the user sees a duplicate loan with no in-app explanation. Recommended: defer to Phase 4 as it requires a startup check and guided recovery dialog.

### approval_recovery.tmp (batch approval protocol)

**Coverage:** Analogous to recovery.tmp for the batch approval flow. Not inspected in full detail — assumed same pattern.

**Gap:** Same startup detection gap as recovery.tmp. No in-app workflow to recover from a partially-completed batch approval.

---

## Focus Area 4: CHG-02-EXT — Paidoff Report Pipeline Write Path

### New write path introduced by CHG-02-EXT

After the CHG-02-EXT fix, marking a loan as Paidoff now involves:
1. `mark_paidoff(reference_id, paidoff_date)` — existing, with recovery.tmp coverage
2. `generate_report_id(today)` — writes to reports_meta.csv (non-atomic, low risk)
3. `write_report(PendingReport)` — appends to pending_reports.csv (append, low risk)
4. `write_report_records([ReportRecord])` — appends to pending_report_records.csv (append, low risk)

**Atomicity assessment:**
- Step 1 is covered by recovery.tmp protocol.
- Steps 2–4 are append operations, not full-file rewrites. A crash after step 1 but before steps 2–4 means: loan is paid off (in history.csv), but no report appears in Pending Approval. The loan is correctly archived; only the interest report is missing.
- A crash after step 3 but before step 4 means: report header exists in pending_reports.csv but no line items in pending_report_records.csv. The report will appear in Pending Approval as an empty report.

**Recommended handling:** Dev Lead should wrap steps 2–4 in a try/except. If report generation fails after mark_paidoff succeeds, log an error and inform the user that the Paidoff was completed but the interest report could not be generated. User can manually create the report via the Interest Calculator Tab if needed.

**SRE verdict on CHG-02-EXT:** Write path is acceptable for prototype scope. The empty-report edge case (crash between report header and records write) is low probability and low impact — user can re-generate the report. No additional atomicity mechanism required in run_4.

---

## Focus Area 5: Application Logging — Observability Assessment

### Current logging setup (from main.py)

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
```

**Strengths:**
- Dual handler (file + stderr) — useful for both user diagnosis and developer debugging.
- Structured format with timestamp, level, module name.
- Log file in `./data/logs/app.log` — predictable location.
- Key write operations all emit `logger.info()` messages.

**Gaps:**

| Gap | Severity | Recommended Fix | Phase |
|---|---|---|---|
| FileHandler not RotatingFileHandler — app.log grows unbounded | Low | Replace with RotatingFileHandler (maxBytes=5MB, backupCount=3) | Phase 4 |
| No "Refresh: no changes" log line | Medium | Add logger.debug/info after BUG-UTR-3 fix — see Focus Area 2 | run_4 |
| No startup recovery.tmp check log | Medium | Add logger.warning if recovery.tmp found on startup | Phase 4 |
| No log on startup recompute completing — only per-loan changes logged | Low | Add startup summary: "Startup: recomputed N loans, M status changes" | Phase 4 |
| No log on filter apply in interest_calculator_tab | Low | Add logger.debug with filter selections applied | Phase 4 |
| DEBUG level entries suppressed in production (level=INFO) | Acceptable | DEBUG available to developers via --debug flag if needed | Not required |

**Overall observability verdict:** Adequate for prototype scope. The most important addition for run_4 is the "Refresh: zero writes" log line (tied to BUG-UTR-3 fix) so the user can confirm the fix is working.

---

## SRE Reliability Test Scope (input to QA Lead)

### Crash recovery tests

| ID | Scenario | Expected Behaviour | How to Test |
|---|---|---|---|
| SRE-T-001 | Kill process during _write_meta() (loans_meta.csv write) | loans_meta.csv intact after restart; next entry gets correct sequential ID | Simulate via debug breakpoint; verify file content before/after |
| SRE-T-002 | Kill process after history.csv append, before loans.csv removal | recovery.tmp exists; loan visible in loans.csv and history.csv | Manual kill during mark_paidoff(); inspect both files |
| SRE-T-003 | Corrupt loans_meta.csv manually (header only) | App starts cleanly; next entry gets _001 for affected month | Delete file contents, leave header only |
| SRE-T-004 | Corrupt loans_meta.csv giving_date scenario (BUG-UTR-2) | Enter back-dated loan; next same-month entry gets sequential ID | Create loan with giving_date = last month, verify current month counter |

### Write safety tests

| ID | Scenario | Expected Behaviour | How to Test |
|---|---|---|---|
| SRE-T-005 | Refresh with no status changes | app.log shows "no status changes — skipping all writes" | Click Refresh, inspect app.log |
| SRE-T-006 | Refresh when one loan transitions Active → Overdue | app.log shows exactly 1 "Loan updated" entry | Set due_date to yesterday, click Refresh |
| SRE-T-007 | Rapid entry of 10 loans in same month | All 10 have unique, sequential reference_ids | Manual entry test, inspect loans.csv |

### Startup tests

| ID | Scenario | Expected Behaviour |
|---|---|---|
| SRE-T-008 | Start app with orphaned loans_meta.tmp | App starts cleanly; .tmp file is either ignored or cleaned up |
| SRE-T-009 | Start app with empty loans_meta.csv (header only) | App starts cleanly; next entry gets _001 |
| SRE-T-010 | Start app with missing data/ directory | App creates data/ directory; starts cleanly |

---

## Production Readiness Checklist: Phase 3 Closure

**Data Durability**
- [ ] BUG-UTR-2 Fix B: loans_meta.csv atomic write implemented and tested (SRE-T-001)
- [ ] BUG-UTR-3: Refresh snapshot fix implemented and zero-write log confirmed (SRE-T-005, SRE-T-006)
- [ ] recovery.tmp crash scenario documented in user guide (R10)
- [ ] CHG-02-EXT report pipeline failure handled gracefully (log + user message if report write fails)

**Observability**
- [ ] "Refresh: N loans changed / no changes" log line added by Dev Lead
- [ ] All 6 run_4 items produce appropriate log entries at INFO or DEBUG level

**Testing**
- [ ] SRE-T-001 through SRE-T-007 pass on Windows
- [ ] Existing 197 tests pass + new tests for BUG-UTR-2 and BUG-UTR-3

**Known deferred items (Phase 4)**
- Pre-operation timestamped backup of loans.csv before Paidoff / batch approve (R3 prototype deferral)
- RotatingFileHandler for app.log
- Startup recovery.tmp detection and guided recovery
- reports_meta.csv atomic write (low risk, same pattern as loans_meta.csv)

**Verdict:** Conditional go for Phase 3 close. BUG-UTR-2 Fix B and BUG-UTR-3 must ship. Deferred items do not block Phase 3 closure but must be logged in Phase 4 backlog.

---

## Runbook: Reference ID Duplication Recovery

**Alert:** User reports two loans with same reference_id
**Severity:** P1
**Applicable to:** Windows user

**Symptoms:**
- Two rows in loans.csv with identical reference_id values
- User sees duplicate entries in View Tab

**Diagnosis steps:**
1. Open `./data/loans.csv` in a text editor
2. Search for the duplicate reference_id
3. Check `./data/loans_meta.csv` — what is the counter value for the affected YYYY_MM?
4. Check `./data/logs/app.log` for "Generated reference_id" entries to see the sequence

**Remediation (pre-fix):**
1. Rename one of the duplicate loans to the next available ID (e.g., 2026_04_002 if 2026_04_001 is duplicated)
2. Update loans_meta.csv: set counter for 2026_04 to the highest order number used

**Remediation (post-fix — BUG-UTR-2 applied):**
Should not occur. If it does, check if giving_date ≠ entry month on any loan — may indicate Fix A was not applied correctly.

**Post-incident action:**
- File as regression if it occurs after run_4 fix is deployed
- Run SRE-T-007 (10 rapid entries) to verify

---

## Runbook: Incomplete Paidoff Recovery

**Alert:** User reports loan still visible in View Tab after marking Paidoff
**Severity:** P2

**Diagnosis steps:**
1. Check if `./data/recovery.tmp` exists
2. If yes: read the reference_id from the file
3. Check if the reference_id appears in both `loans.csv` and `history.csv`

**Remediation:**
1. If reference_id in both files: manually remove from loans.csv (the history.csv entry is correct)
2. Delete recovery.tmp
3. Restart the application and verify the loan no longer appears in View Tab

**Post-incident action:**
- Phase 4 item: implement startup recovery.tmp detection to automate this
