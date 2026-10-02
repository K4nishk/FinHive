# Findings — logging, triage and the feedback log

> Part of the `e2e-testing` skill — load when logging a finding or running `triage F-NNN`.

## Logging a finding

Append to the Feedback Log. Do not diagnose — describe.

```markdown
### F-NNN · <short title>
- **Date**: YYYY-MM-DD
- **Persona**: A / B / C  (or Manual)
- **Check**: e.g. C1.11, A5.3  (blank if found off-script)
- **Where**: screen, route, or endpoint
- **Did**: exact steps
- **Expected**:
- **Got**:
- **Severity**: your best guess is fine
- **Evidence**: screenshot, payload, console dump, ref_id
```

Then say **`triage F-NNN`**.

### Triage procedure

1. Reproduce; note whether it is consistent or intermittent.
2. Classify severity; locate the layer (UI / API / domain / data / agent). Use the correlation ID to trace it in Grafana.
3. **Write the failing test first.** It must fail for the stated reason.
4. Fix.
5. Confirm the test passes; add it to the permanent suite.
6. Update the log row to 🟢 with the test path.

---

## Feedback Log

> 🔴 open · 🟡 test written, fix pending · 🟢 fixed + test in CI · ⚪️ won't fix (reason required)

<!-- Newest first. Claude maintains Status and Test; the user owns the finding text. -->

| ID | Title | Persona | Sev | Status | Test |
|---|---|---|---|---|---|
| F-006 | Windows test 2026-10-02: the master key was set with `$env:` in one PowerShell window, so it vanished with the window; the next launch blocked again and the demo ledger encrypted under the old key became unreadable. Root cause: the key existed only in the environment and onboarding made the user manage it before the first launch. Fixed: with no key in the environment the app creates `data/encryption/master_key.key` (0600, git-ignored) on first launch, announces the path, and reuses it; refuses to mint a key when a database it would serve already holds encrypted data (points at restore or `demo-reset`); env and file with different keys for one version refuse | D | S1 | 🟢 | `src/Loan Manager/tests/unit/test_key_file.py`, `tests/integration/test_demo_seed.py` (first seed creates key; kept demo under lost key refused), `tests/unit/test_launcher_signposting.py` |
| F-005 | `Extend the menon traders loan by 2 months` (doc: refused for no due date). The model asked for the loan's reference id instead of looking it up, so the documented refusal never showed. The structural refusal (`UNDATED_LOAN` in `propose_extend.py`) is intact; the doc over-promised model behaviour. Doc corrected; lookup improves with the F-004 fix | A | S3 | 🟡 | — (doc fix; eval case planned in KCH-249) |
| F-004 | macOS manual test 2026-10-02: `Is deepak menon overdue?` → "could not form a valid request"; `Is pooja verma's loan active?` → clarifying question. Trace: `query_loans(borrower_group="B003")` → `UNKNOWN_TOKEN` ×3. Root cause: `QueryLoans` (`tools/args.py:158`) exposes only group filters, so a borrower token has nowhere valid to go, although `GetAllLoans` and the tokeniser already support `borrower_name`/`depositor_name`. Safe failure (no leak, no mutation); capability gap. Fixed: `QueryLoans` gains `borrower_name`/`depositor_name`, validated per field like groups | A | S2 | 🟢 | `tests/unit/application/agent/test_read_query_loans.py` (F-004 block, incl. token round-trip) |
| F-003 | macOS user following the guide ran `python3 -m loan_manager.infrastructure.seed …` on the system Python and got `No module named 'sqlalchemy'`; the venv only exists inside the launcher's run, `python` does not exist on macOS, and the root launchers (which the user tried first) never started the desktop app. Root launchers now start the desktop app by default (`--web` for MVP2); `demo` / `demo-reset` seed with the launcher's own Python; docs need no `python` or activation | D | S1 | 🟢 | `tests/unit/test_launcher_signposting.py` + scripted run of `run_local_mac.sh demo` / `demo` / `demo-reset` / no-arg |
| F-002 | Re-test of F-001 on Windows (2026-10-02): the refusal now names `src\Loan Manager\run_windows.bat` ✅, but only after a slow `npm install`, by which time the top-of-run banner had scrolled away. The refusal must come before the frontend install | D | S2 | 🟢 | `tests/unit/test_launcher_signposting.py::test_web_launcher_refuses_before_the_frontend_install` |
| F-001 | Windows user ran repo-root `run_local_windows.bat` (MVP2 web, paused) to test MVP1.1; it installed the frontend then failed on KCH-90 with no pointer to `src\Loan Manager\run_windows.bat`. Desktop launcher also pointed key setup to the MVP2 web guide (re-tested on Windows 2026-10-02: pointer shown) | D | S1 | 🟢 | `tests/unit/test_launcher_signposting.py` |
