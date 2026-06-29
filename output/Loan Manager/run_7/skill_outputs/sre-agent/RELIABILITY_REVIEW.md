# Loan Manager — Reliability Review
**Agent:** sre-agent (Wave 1)
**Run:** run_7
**Date:** 2026-04-05
**Phase:** Phase 3 Closure / Phase 4 MVP

---

## SRE: Reliability Review — Desktop CSV Application

This is a single-user desktop application backed by CSV files. Standard uptime SLOs are not applicable. SRE scope covers: data durability, crash safety, startup integrity, and operational observability.

---

## SRE-01: Startup Recovery File Check — STATUS: ALREADY IMPLEMENTED

**Finding:** Full review of `ui/main_window.py` confirms `_check_recovery_file()` handles all three recovery scenarios:

1. `recovery.tmp` — warns if a paidoff operation was interrupted
2. `import_recovery.tmp` — warns if an import was interrupted
3. `approval_recovery.tmp` — warns if a batch approval was interrupted (R10 requirement)

Message for approval_recovery.tmp:
> "A previous approval for report '{token}' may not have completed. Please check if the report status and loan records are consistent before continuing."

**SRE Assessment:** SRE-01 is DONE. Close this item with no further action.

---

## SRE: Crash Safety Review

### Two-Phase Write Protocol (mark_paidoff)
```
1. Write target row reference_id to recovery.tmp
2. Append to history.csv
3. Remove from loans.csv
4. Delete recovery.tmp
```
**Assessment:** Correct implementation. If crash occurs between steps 2 and 3, recovery.tmp exists on next startup and user is warned. Manual reconciliation required. Acceptable for prototype.

**Deferred (PD-09):** Timestamped backup copy of loans.csv before destructive operations. This is explicitly deferred to post-MVP.

### Batch Approval Write Protocol (batch_extend_loans)
```
1. Write report_id to approval_recovery.tmp
2. Call batch_extend_loans() → single CSV rewrite pass
3. Mark report Approved in pending_reports.csv
4. Delete approval_recovery.tmp
```
**Assessment:** Correct. Single-pass CSV rewrite reduces the crash window. approval_recovery.tmp survives startup and triggers warning.

---

## SRE: Data Durability Assessment

| Risk | Severity | Status | Mitigation |
|---|---|---|---|
| Crash between loans.csv and history.csv write | HIGH | Mitigated | recovery.tmp + startup warning |
| Crash during batch approval | MEDIUM | Mitigated | approval_recovery.tmp + startup warning |
| Corrupt CSV (manual edit by user) | MEDIUM | Partial | _read_all_rows() logs malformed rows, skips them |
| loans.csv deleted accidentally | HIGH | Not mitigated | Out of prototype scope (PD-09 deferred) |
| Concurrent sessions (two app windows) | LOW | Not applicable | R8: single user, no file locking needed |

---

## SRE: Observability Review

### Logging Assessment
- Application logs: `./data/logs/app.log` (R7 confirmed)
- Log format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- All major operations emit INFO logs (loan saved, updated, deleted, extended, paidoff)
- Failed writes emit ERROR logs
- Status recompute emits INFO (count changed) or DEBUG (no changes)

**SRE Observation:** Log rotation is not implemented. For a 1500-loan single-user app, log growth is slow. Acceptable for prototype. Post-MVP: add RotatingFileHandler.

### Startup Observability
- `_startup_recompute()` logs loan count
- `_check_recovery_file()` logs ERROR if stale recovery files detected
- Seed operation logs if sample data was loaded

**Assessment:** Observability is adequate for prototype scope.

---

## SRE: TC-05 Reliability Impact

Adding `has_pending_paidoff_report()` call at context menu open:
- Performs 1 read of `pending_reports.csv` + 1 read of `pending_report_records.csv`
- At 1500 max loans and typical <10 pending reports, this is <1ms I/O
- No caching needed for prototype scope
- SRE accepts this approach

---

## SRE: Phase 4 Readiness Checklist

- [x] Data durability: Two-phase paidoff write implemented
- [x] Crash safety: All three recovery file types checked on startup
- [x] Logging: File + stderr, INFO level
- [x] Startup integrity: Status recompute on every launch
- [x] Error handling: All CSV reads wrapped in try/except with logging
- [x] Test coverage: 237 tests passing (confirmed by pytest run)
- [ ] TC-05 guard: Implementation pending (Phase 4)
- [ ] TC-08 Option B (if chosen): Schema addition pending user decision
- [ ] Missing test files: 4 test files pending Phase 4

---

## SRE: Phase 5 UAT Pre-flight Recommendations

1. Run `pytest --tb=short` from `src/Loan Manager/` on both Mac and Windows environments
2. Verify `run_mac.sh` exits correctly after venv setup and app launch
3. Verify `run_windows.bat` Python version check triggers correctly on Python < 3.10
4. Verify seed data loads on first launch with empty loans.csv
5. Verify approval_recovery.tmp warning appears after simulated crash (manual test)
6. Verify log file is created at `./data/logs/app.log` on first launch

**SRE Phase 4 sign-off condition:** All 5 checklist items above confirmed + TC-05 implemented.
