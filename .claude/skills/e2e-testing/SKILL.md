---
name: e2e-testing
description: Persona-driven end-to-end testing for FinHive Loan Manager. Invoke to run as a simulated user against the app — first-launch startup sweep on Windows and macOS, MVP1 parity sweep, new-user signup/onboarding, or a Bot Readiness crawler sweep for security, accessibility, and best-practice defects. Also use when the user reports a bug from manual testing, when converting testing feedback into permanent regression tests, or when asked to review user-journey coverage.
---

# E2E Testing — FinHive Loan Manager


## What this skill does

When invoked, **you stop being an assistant and become a test user.** You drive the app the way a real person would, notice what a real person would notice, and write down what broke.

This is a **living regression suite**. It starts thin and gets denser every time someone finds something. The rule that makes it work:

> **A finding closes when a permanent test covers it — not when the bug is fixed.**

```
Run a persona → find something → log it → write the regression test
    → test enters CI → that defect can never silently return
```

---

## Load only what the ask needs

This file is the router. **Read the one plan file the request needs — never all of them.**

| Say | Run | Read |
|---|---|---|
| `/e2e startup` | **Persona D** — first launch on a clean machine, Windows **and** macOS | [`plans/persona-d-startup.md`](plans/persona-d-startup.md) |
| `/e2e mvp1` | **Persona A** — MVP1 continuity sweep | [`plans/persona-a-mvp1.md`](plans/persona-a-mvp1.md) |
| `/e2e newuser` | **Persona B** — signup, onboarding, first value (MVP2 web) | [`plans/persona-b-newuser.md`](plans/persona-b-newuser.md) |
| `/e2e bot` | **Persona C** — Bot Readiness crawler sweep | [`plans/persona-c-bot.md`](plans/persona-c-bot.md) |
| `/e2e full` | All four, startup first, one consolidated report | each plan file in turn |
| A manual bug report, or `triage F-NNN` | Log it, then write its failing test | [`findings.md`](findings.md) |
| `/e2e cover <journey>`, or writing any regression test | Add automated coverage | [`automation.md`](automation.md) |

Which persona fits a manual report: launcher, install, keys, first screen, upgrade → **D**;
an MVP1 workflow behaving differently → **A**; web signup/login → **B**; leaks, crawl,
hostile input → **C**.

**Target resolution order**: the URL the user names → `BASE_URL` env var → the current
PR's Vercel preview → `http://localhost:5173`. For the desktop app (MVP1 / MVP1.1),
launch with `./run_local_mac.sh` / `.\run_local_windows.bat` from the repo root (add `demo`
for the demo ledger, `demo-reset` to reseed it); `--web` starts the paused MVP2 web app.

State the target you resolved before you start. Never assume production.

---

## Rules of engagement

1. **Behave like the persona, not like an author.** Do not read the source first to learn where things are. Find them the way a user would. Source-reading is for *triage*, after something breaks.
2. **Record everything, judge later.** Note friction, confusion, and ugliness alongside crashes. S3 findings are how a product stops being merely correct.
3. **Never fix while testing.** A run produces findings, not commits. Fixing mid-run destroys the run's integrity.
4. **The business rules are the oracle.** MVP1's rules (`giving_date` is never used in calculations; monthly interest is `amount × rate × months / 1200`) decide who is right when the app and your expectation disagree.
5. **Non-determinism is not a pass.** If something works twice and fails once, that is an S2 finding, not a flake to shrug at.
6. **Never use real credentials.** Test accounts only. Never type a real password, API key, or token into the app under test.

---

## Severity

| Level | Definition | Response |
|---|---|---|
| **S1** | Data loss, cross-tenant leak, unauthorized mutation, secret/PII exposure, wrong financial calculation, prompt injection that changes behaviour | Stop. Fix now. Test at the API layer, not just the UI |
| **S2** | Core journey broken, no workaround; keyboard or contrast failure | Fix before next merge |
| **S3** | Works but confusing, slow, or ugly | Ticket and batch |
| **S4** | Cosmetic | Backlog |

**Anything touching money, dates, credentials, or another tenant's data is S1 by default.**

---

## Anti-patterns

- ❌ **Do not** assert on the agent's exact prose. It is non-deterministic. Assert on tool calls, proposals created, and data changed.
- ❌ **Do not** use `waitForTimeout`. Use `waitForSelector` / `waitForResponse`.
- ❌ **Do not** test against localhost. Preview deployments catch edge-layer bugs.
- ❌ **Do not** delete a non-negotiable assertion to go green. If one fails, the app is broken, not the test.
- ❌ **Do not** close a finding because it was fixed. It closes when its test is in CI.
- ❌ **Do not** share auth state between role-boundary tests. Each logs in fresh.
- ❌ **Do not** run Persona C against production with hostile input. Preview or staging only.
- ❌ **Do not** let a Persona A ❌ pass as "acceptable in the rewrite" without the user's explicit sign-off. Lost capability is lost trust.

---

## Related

- Architecture, gotchas, safety model: `output/Loan Manager/mvp2/mvp2_ard_v2.0.0.md`
- MVP1 business rules (the correctness oracle): `output/Loan Manager/run_8/WIKI.md` §3
- MVP1 requirement source of truth: `input/REQUIREMENTS.md`
- Agent quality evals (complements this; covers model behaviour, not app flows): `evals/golden/`
