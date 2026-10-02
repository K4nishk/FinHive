# Persona D — first launch (startup)

> Part of the `e2e-testing` skill — loaded only for `/e2e startup`. Rules of engagement and severity live in [`../SKILL.md`](../SKILL.md); log findings with [`../findings.md`](../findings.md).

## §D · Persona D — First launch (startup)

**Who:** someone with the repo and a README, on **Windows (PowerShell / double-click)**
and on **macOS (Terminal)** — run both; behaviour differs. They have never started the
app before, or are an MVP1 user upgrading. They follow the docs literally and click
the most obvious file.

The question this persona answers: *can a person go from `git clone` to the app's first
screen without asking anyone?* Every dead end, misleading message or wrong launcher is
a finding — a startup failure is S1 for that user, however correct the code behind it.

### D1 · Find the right launcher
| Check | Pass when |
|---|---|
| List every launcher in the repo (`*.bat`, `*.sh`, `python -m …main`) | Each one says, **in its first screen of output**, which app it starts and whether that app is runnable today |
| Run the repo-root `run_local_windows.bat` / `run_local_mac.sh` (MVP2 web, paused) | It names the desktop launcher `src/Loan Manager/run_*` **before** installing anything, and again in its refusal (F-001) |
| Same, and time it | The refusal and its pointer appear **before** the slow frontend `npm install`, i.e. within the backend install time, and are still on screen at the `Press any key` prompt (F-002) |
| Run `src/Loan Manager/run_windows.bat` (double-click **and** from PowerShell) and `run_mac.sh` | Reaches the app or a message that names the exact fix |
| Every doc path a launcher prints | Exists, and documents *that* app (not the other one) |

### D2 · Missing prerequisites, one at a time
Run each with exactly one thing missing; the message must name the fix, never a traceback.
- No Python 3.10+ · no venv · `finhive` package not installed
- No `FINHIVE_KEY_VERSION` / `FINHIVE_MASTER_KEY_V1` (Windows: set with `setx`, launched from an **old** window — `setx` does not reach it)
- No `OPENROUTER_API_KEY` → app opens; Ask FinHive shows the "not configured" text
- `data/settings.json` without the `"llm"` block (MVP1 file kept through a local edit) → same "not configured" text, not "Something went wrong"
- PowerShell execution policy blocks `Activate.ps1`

### D3 · MVP1 upgrade path
- MVP1 `data/loans.db` (plaintext) → app refuses, prints numbered steps, ledger unchanged (hash before/after)
- Follow those steps verbatim on **both** OSes (`cp` vs `Copy-Item`, `/` vs `\`) → app opens, every MVP1 loan present and correct in View
- `git pull` with a locally edited `data/settings.json` → the documented stash/pull/pop works

### D4 · Demo ledger isolation
- `FINHIVE_DB_PATH` set in the shell → demo opens; a **double-clicked** launcher does not see it and opens the real ledger (expected — the docs must say so)
- Seeder refuses `data/loans.db` and refuses to overwrite without `--replace`

### D5 · Reporting Persona D
One row per launcher × OS: reached first screen (✅/❌), minutes taken, every message that
did not name its own fix. Each ❌ becomes a finding with a test that fails without the fix
(static: the script/doc text; runtime: a subprocess launch with the prerequisite removed).
