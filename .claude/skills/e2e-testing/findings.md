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
| F-002 | Re-test of F-001 on Windows (2026-10-02): the refusal now names `src\Loan Manager\run_windows.bat` ✅, but only after a slow `npm install`, by which time the top-of-run banner had scrolled away. The refusal must come before the frontend install | D | S2 | 🟡 | `tests/unit/test_launcher_signposting.py::test_web_launcher_refuses_before_the_frontend_install` |
| F-001 | Windows user ran repo-root `run_local_windows.bat` (MVP2 web, paused) to test MVP1.1; it installed the frontend then failed on KCH-90 with no pointer to `src\Loan Manager\run_windows.bat`. Desktop launcher also pointed key setup to the MVP2 web guide (re-tested on Windows 2026-10-02: pointer shown) | D | S1 | 🟢 | `tests/unit/test_launcher_signposting.py` |
