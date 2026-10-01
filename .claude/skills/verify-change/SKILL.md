---
name: verify-change
description: Step-by-step gate to run before committing any FinHive change — CI-parity test commands, see-it-fail-first proof, NPI and layer checks, staging named paths, secret scan, and opening a stacked PR. Use before every commit or PR in this repo, when asked to "run the tests", "verify", "ship" or "open a PR", or when a test only ever skips locally.
---

# Verify a change, then ship it

Run these steps in order. Each step names what to paste as evidence in the PR body.
A step that did not run is a failure, never a pass — say so.

## 1. Environment

```bash
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1
export PATH="/home/user/FinHive/.venv_pg/bin:$PATH"      # absolute: lint-imports is run from a temp dir
export TEST_DATABASE_URL=postgresql://postgres@localhost:5433/finhive_test_disposable
```

- `TEST_DATABASE_URL` must point at a **dedicated, disposable** database — never the
  dev ledger (the lane drops and recreates schemas; the dev ledger lives in `public`).
  Check which database before running anything that drops tables.
- Never point anything at `src/Loan Manager/data/loans.db`.
- No local Postgres? Integration tests must SKIP cleanly — say they skipped.

## 2. See it fail first

For every new or changed test:

1. Break the property the test guards (mutate the code, or in a scratch copy).
2. Run only that test with `-p no:cacheprovider` and read the failure.
3. It must fail **for the reason its name states** — an assertion about that
   property. `NameError`, `ImportError`, `KeyError` or a config error does not count.
4. Restore and prove the restore (`md5sum` before and after).

Paste: test name → mutation → the failing assertion line.

## 3. Run the gates the way CI does

```bash
cd "src/Loan Manager" && python -m pytest tests/ -q -p no:cacheprovider --cov=loan_manager
cd ../.. && pytest tests/unit -q -p no:cacheprovider && lint-imports
pytest tests/integration -q -p no:cacheprovider
ruff check <changed .py files>
```

Paste the summary line of each (passed / skipped / xfailed). Name every skip you
introduced. Coverage: 85% minimum, domain services 100%. Never commit with a failure.
Required CI checks (`Fast gates`, `MVP1 regression`, `Postgres integration`) are a
backstop, not the gate.

## 4. Self-review checklist

Answer each against the diff (`git diff <base>...`):

- [ ] Layers: `domain/` imports no infrastructure/presentation/PySide6/sqlalchemy;
      `application/agent/` imports no PySide6, sqlalchemy, sqlite3 or mutating use
      case; presentation imports infrastructure only for the logger.
- [ ] No raw SQL outside `migrations/`; no `float` for money; no `datetime.utcnow()`;
      no hex colours in `presentation/`; no new `QTableWidget`.
- [ ] No plaintext NPI: a raw scan of a test DB (`-wal` too) shows no name, group or
      amount (principal or derived) in clear. No blind index on an amount.
- [ ] Nothing sent to an LLM without tokenising; nothing logged with `str(exc)` on a
      path that can carry names or amounts.
- [ ] Every bug fix has a regression test; every new use case has a test file.

Security-critical (CLAUDE.md agent policy item 3)? Request one Opus review now.

## 5. Stage and scan

```bash
git status --short
git add <named paths>                       # never git add -A / git add .
git diff --cached --name-only | grep -iE '\.db$|pyc|coverage|DS_Store|\.env' && echo STOP
git diff --cached | grep -iE '^\+.*(sk-[a-z0-9]{10}|password *=|MASTER_KEY_V[0-9]+ *= *.)' && echo CHECK
```

`.DS_Store` is tracked, so a blanket add sweeps it in. `*.db` and `.env*` are ignored —
never force-add them.

## 6. Commit and open the PR

- Conventional message: `feat(KCH-NNN): …` / `fix(KCH-NNN): …`.
- Branch `feature/kch-NNN` from the **previous PR's branch**; open the PR against that
  branch (lowest open PR → `development`). Open it **ready for review**, not draft.
- PR body: What · Verification (step 2 + 3 evidence) · `[REVIEW REQUIRED]` · DEBT.
  State plainly if an Opus review was required and did not run.
- Linear unreachable? Write the comment to `ops/linear/YYYYMMDD/kch-NNN.md`.
