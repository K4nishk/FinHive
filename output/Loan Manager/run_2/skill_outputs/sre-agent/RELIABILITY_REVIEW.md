# SRE: Reliability Review — Loan Manager run_2
**Date:** 2026-04-03
**Run:** run_2 / Wave 1
**Author:** SRE Agent
**Scope:** Desktop CSV application — SLO definitions adapted for data durability and startup reliability per SKILL.md directive

---

## 1. Scope Note: Desktop App SRE Adaptation

Loan Manager is a single-user PySide6 desktop application with no server, no network uptime requirements, and no concurrent users. Standard web SLOs (uptime %, p95 latency) do not apply. Per the SRE SKILL.md directive: "For desktop-CSV applications, adapt to cover data durability (atomic writes, backup) rather than uptime SLOs."

SRE reliability posture for Loan Manager is framed around:
1. **Data durability** — atomic write safety, recovery on crash, no data corruption
2. **Startup reliability** — launcher correctness, dependency checks
3. **Operation reliability** — no silent data loss on user actions
4. **Failure observability** — logging coverage for diagnosable failures

---

## 2. SLO Definitions (Desktop-Adapted)

| Signal | Metric | Target | Measurement |
|---|---|---|---|
| Data write durability | Atomic write with recovery.tmp — loan save must be all-or-nothing | 100% | Manual test: kill process mid-write, verify recovery on restart |
| Import atomicity | Import recovery.tmp present during batch — deleted on completion | 100% | Manual test: interrupt import, verify recovery sentinel |
| Paidoff write safety | mark_paidoff() must never leave loan in both loans.csv and history.csv | 100% | Test: verify mutual exclusivity post-Paidoff |
| Startup success rate | App launches and renders main window on first try (Python 3.10+, dependencies installed) | 100% | Launcher script with version check (CHG-03 — verified present) |
| Log observability | All data-modifying operations emit at least one INFO/WARNING log entry | 100% | Code review of all write paths |
| Paidoff report failure isolation | Report generation failure must NOT silently swallow the error | 100% | Verified: non-blocking warning + ERROR log required (CHG-02) |

---

## 3. SRE Architecture Reliability Review

## SRE Architecture Reliability Review: run_2 Change Items

**Reviewed:** SA architecture design for CHG-01, CHG-02, BUG-01–04, DOC-01

**Reliability checklist:**
- [x] Single points of failure identified — CSV files are the single store; no replication needed for single-user app
- [x] Atomic writes in place — `mark_paidoff()` uses recovery.tmp sentinel (confirmed in `data/csv_manager.py`)
- [x] Import atomicity — `import_recovery.tmp` pattern (confirmed in `data/import_service.py`)
- [ ] **CHG-02: Report writes are NOT atomic** — `write_report()` and `write_report_records()` do not use the recovery.tmp pattern. This means an OS crash between `write_report()` and `write_report_records()` could leave an orphan report header with no records. For Phase 3 this is acceptable (the user can manually delete the orphan row). Flag for Phase 4 improvement.
- [x] Graceful degradation — CHG-02 report failure is non-blocking to Paidoff write (per PD-R2-02)
- [x] Startup version check — CHG-03 verified present in run_windows.bat and run_mac.sh

**Observability checklist:**
- [x] `logging.getLogger(__name__)` used consistently across loan_manager/* and data/* modules
- [x] `import_service.py` emits WARNING on malformed rows (confirmed line 68)
- [x] `status_engine.py` emits DEBUG on status recompute changes (confirmed lines 96–102)
- [ ] **CHG-02: Must emit WARNING when no due_date prevents report generation** — requirement per PD-R2-02. Confirm in implementation.
- [ ] **CHG-02: Must emit ERROR on report generation failure** — distinguish from WARNING. A WARNING implies "expected situation"; report generation failure is unexpected and should be ERROR.

**Feedback to SA:**
- CHG-02 report atomicity: Phase 3 acceptable; Phase 4 should extend atomic write pattern to pending_reports.csv + pending_report_records.csv writes
- Logging severity discipline: WARNING vs ERROR distinction must be documented in coding standards and enforced in CHG-02 implementation

**Verdict:** Approved with conditions — see items above

---

## 4. SRE Data Model Review

## SRE Data Model Review: run_2

**Reviewed:** DM agent data contract for CHG-02 and DOC-01

**Durability checks:**
- [x] No schema migration required — no data at risk
- [x] CSV files are the durable store — single-file, local, no network dependency
- [x] Backup strategy: not automated. Single-user personal app. Acceptable. Document limitation.
- [ ] **CHG-02 partial write risk:** If `write_report()` writes the header row to `pending_reports.csv` and then the process crashes before `write_report_records()` completes, `pending_reports.csv` will contain an orphan report with no records. The Pending Approval UI must handle this gracefully (show empty report without crashing). Verify this is already handled in `pending_approval_tab.py`.

**Recovery posture:**
- RPO (Recovery Point Objective): Last successfully written CSV state. In practice: the current session's last completed write.
- RTO (Recovery Time Objective): App restart. Recovery sentinel check on startup cleans up partial writes for loan saves and imports.

**Feedback to DM agent:**
- BC-05 flag (rate fields defaulting to global values) has data quality implications. If a future audit requires per-loan rate accuracy, the current model is insufficient. DM-R01 risk is correctly flagged.
- BC-06 flag (reference_id pointing to history.csv after Paidoff) is a structural concern. The `source_table` column suggestion is the correct Phase 4 fix.

**Verdict:** Approved with Phase 4 improvement items logged

---

## 5. SRE Implementation Review: CHG-02

## SRE Implementation Review: CHG-02 Paidoff Report Generation

**Reviewed:** SA implementation approach for `_generate_paidoff_report()`

**Instrumentation check:**
- [ ] WARNING log when `loan.due_date is None` — required, confirm in code
- [ ] ERROR log on report generation exception — required, distinguish from WARNING
- [x] INFO log on successful report generation — add `logger.info("Paidoff report %s generated for loan %s", report_id, loan.reference_id)`
- [ ] The non-blocking QMessageBox must show the report_id or loan reference in the warning text so the user can investigate

**Resilience check:**
- [x] Report generation failure does NOT rollback Paidoff write — per PD-R2-02 and SA ADR-001
- [x] No external calls — all operations are local CSV file writes
- [x] No concurrent access risk — single-user desktop application
- [ ] The `try/except` wrapping `_generate_paidoff_report()` must be broad (catch `Exception`) not narrow (catch specific file errors) because the failure modes span file I/O, data computation, and report manager logic

**Feedback to Dev Lead:**
1. Log severity discipline: `loan.due_date is None` → WARNING (expected business condition). Report generation crash → ERROR (unexpected).
2. The QMessageBox warning text should include the loan reference_id so the user can look up the record.
3. The `try/except` block in `_action_paidoff()` around `_generate_paidoff_report()` must catch `Exception` broadly, not just `IOError` or `OSError`.

**Verdict:** Approved with three instrumentation conditions above

---

## 6. SRE Reliability Test Scope

## SRE Reliability Test Scope: run_2

**Input to:** QA Lead agent

**Data durability tests (adapted from load tests for desktop app):**
| ID | Scenario | Target | SLO to Validate |
|---|---|---|---|
| REL-01 | `mark_paidoff()` completes: verify loan NOT in loans.csv and IS in history.csv | Single write | Mutual exclusivity — 100% |
| REL-02 | Simulate crash after `write_report()` but before `write_report_records()` — verify Pending Approval tab handles orphan report without crash | Fault injection (manual) | Graceful handling — no unhandled exception |
| REL-03 | Import CSV with 100 rows including 10 malformed rows — verify result.skipped = 10, result.inserted = 90 | Batch import | Correct skip count — 100% |
| REL-04 | Import with DD-MM-YYYY dates — verify giving_date stored as ISO 8601 | Single-format | No data corruption — 100% |
| REL-05 | Launcher on Python 3.9 — verify version check exits with message before app launches | Startup | Startup safety — 100% |

**Failure injection tests:**
| Scenario | Expected behaviour |
|---|---|
| Report CSV directory is read-only when `_generate_paidoff_report()` is called | `IOError` caught, ERROR logged, non-blocking QMessageBox shown, loan correctly in history.csv |
| `loans_meta.csv` is missing on startup | App logs ERROR and handles missing meta gracefully (existing behaviour — regression check) |
| giving_date = "invalid" in import CSV | Row skipped, WARNING logged, `result.skipped` incremented by 1 |

**Recovery tests:**
- [x] `import_recovery.tmp` present on startup → import recovery triggered (existing; regression check)
- [x] `recovery.tmp` present on startup → loan recovery triggered (existing; regression check)

---

## 7. Production Readiness Checklist: Phase 3 Prototype

## Production Readiness Checklist: Loan Manager Phase 3 Prototype

**SLO and Observability**
- [x] Desktop-adapted SLOs defined (data durability, startup safety, write atomicity)
- [ ] All CHG-02 log entries confirmed in implementation (WARNING for no due_date, ERROR for report failure, INFO for success)
- [ ] QMessageBox warning text includes loan reference_id

**Resilience**
- [ ] REL-02 orphan report test executed (pending approval tab handles empty records list)
- [x] Atomic write pattern confirmed for mark_paidoff() (existing, verified)
- [x] Import atomicity confirmed (import_recovery.tmp, existing, verified)

**Deployment (Desktop)**
- [x] Python version check in run_windows.bat (CHG-03 — confirmed present)
- [x] Python version check in run_mac.sh (CHG-03 — confirmed present)
- [ ] run_windows.bat and run_mac.sh tested on clean Python 3.10 environment after Phase 3 changes
- [ ] No new Python dependencies introduced by run_2 changes (verify requirements.txt unchanged)

**Operational**
- [x] Single-user desktop app — no on-call rotation needed
- [ ] Phase 3 known limitation documented: Paidoff report approval shows "deleted records" warning (expected — BC-06; user guide update recommended)

**Verdict:** Hold — pending CHG-02 instrumentation confirmation and REL-02 orphan report test

---

## 8. Startup Reliability Section

**Execution failure modes for packaged desktop app:**

| Failure Mode | Trigger | Current Mitigation | Gap |
|---|---|---|---|
| Python < 3.10 installed | User runs launcher on older Python | Version check in run_windows.bat and run_mac.sh (CHG-03 confirmed) | None |
| PySide6 not installed | Missing dependency | Launcher activates virtualenv; if venv setup fails, Python ImportError at startup | No user-friendly error message — ImportError is raw Python traceback |
| CSV data directory missing | First run on new machine or data dir deleted | `_data_dir()` in `csv_manager.py` creates directory if not exists (verify) | If creation fails (permissions), raw exception — no user-friendly message |
| loans_meta.csv missing | File deleted manually | `ref_id_manager.generate_ref_id()` must handle missing meta gracefully | [REVIEW REQUIRED — TC-02] Verify `loans_meta.csv` missing is handled without unhandled exception |
| reports_meta.csv missing | File deleted manually | `report_manager.generate_report_id()` must handle missing meta | [REVIEW REQUIRED — TC-02] Same — verify graceful handling |

**[REVIEW REQUIRED — TC-02]:** Startup resilience for missing meta CSV files (loans_meta.csv, reports_meta.csv) should be verified by QA as part of Phase 3 regression scope. If these files are absent, the app must either recreate them with seed values or present a clear error dialog — not an unhandled Python exception.
