# FinHive Loan Manager — MVP1.1 release summary

MVP1.1 keeps everything MVP1 did and adds **Ask FinHive**: ask questions about your
ledger in plain English and let the assistant draft changes for you to approve. It also
encrypts your ledger on disk and tightens the approval flow.

Everything here runs on the **desktop app**. Nothing in MVP1 was removed.

> **One command, from the `FinHive` folder.** macOS: `./run_local_mac.sh demo` ·
> Windows (PowerShell): `.\run_local_windows.bat demo`. The launcher installs
> everything it needs and opens the app on a demo ledger. You never activate an
> environment or type `python`.

---

## Before you start: what to install

For MVP1.1 you need **only three things**. You do **not** need Node.js, npm, nvm,
Docker or Supabase. Those are only for the paused MVP2 web app (`--web`).

| What | Why | macOS | Windows |
|---|---|---|---|
| **Python 3.10 or newer** (3.12 recommended) | Runs the app. The launcher creates the app's own environment from it. | [python.org/downloads](https://www.python.org/downloads/macos/). After installing, `python3 --version` should print 3.10+. There is no `python` command on macOS, and you don't need one. | [python.org/downloads](https://www.python.org/downloads/windows/). In the installer, **tick "Add python.exe to PATH"**. Check with `py --version` in a **new** PowerShell window. |
| **Git** | Gets the code. | Run `xcode-select --install` in Terminal, or use [git-scm.com](https://git-scm.com/download/mac) | [git-scm.com/download/win](https://git-scm.com/download/win), with the default options |
| **An OpenRouter API key** | The AI service behind Ask FinHive. About $0.0004 per model call; a full tour costs under $0.10. | [openrouter.ai/keys](https://openrouter.ai/keys). Add a few dollars of credit, then create a key. | same |

Windows only:
- If PowerShell says *"running scripts is disabled"*, run
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- If typing `python` opens the Microsoft Store, turn off
  **Settings → Apps → Advanced app settings → App execution aliases → python.exe / python3.exe**.

Everything else (PySide6, SQLAlchemy, cryptography and the rest) is installed
automatically by the launcher on its first run. That takes a few minutes and about 500 MB.

<details><summary>Only if you want to try the paused MVP2 web app (<code>--web</code>)</summary>

| What | Link |
|---|---|
| Node.js 20+ | [nodejs.org](https://nodejs.org/en/download). To manage versions, use nvm on macOS ([github.com/nvm-sh/nvm](https://github.com/nvm-sh/nvm)) or nvm-windows ([github.com/coreybutler/nvm-windows](https://github.com/coreybutler/nvm-windows)). |
| Docker Desktop | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/) |
| Supabase CLI | [supabase.com/docs/guides/cli](https://supabase.com/docs/guides/cli) |

Even with all of these, `--web` still stops with a KCH-90 message today, because the web
backend is not built yet.
</details>

---

## What's new

| # | Capability | In one line | Try it |
|---|---|---|---|
| 1 | **Ask FinHive tab** | Ask about loans in plain English; see the steps it took and the loans behind the answer | [ask-finhive.md](ask-finhive.md) |
| 2 | **AI-drafted changes** | Ask it to extend or create loans; it drafts a batch, you approve it | [drafts-approvals-undo.md](drafts-approvals-undo.md) |
| 3 | **Approvals tab upgrades** | AGENT/FORM badges, the original request, conflict warnings, **Undo** | [drafts-approvals-undo.md](drafts-approvals-undo.md) |
| 4 | **Statuses refresh on approval** | Approved extensions show the new status immediately — no restart | [drafts-approvals-undo.md](drafts-approvals-undo.md#4-status-refreshes-right-away) |
| 5 | **Encryption at rest** | Names and amounts are encrypted in the database file; the key is created for you on first launch | [privacy-and-safety.md](privacy-and-safety.md#1-encryption-at-rest) |
| 6 | **Privacy with the AI** | Names and amounts are swapped for codes before anything is sent to the AI service | [privacy-and-safety.md](privacy-and-safety.md#2-what-the-ai-service-sees) |
| 7 | **Guardrails** | Read-only unless you ask for a change; loan topics only; 2,000-character limit | [privacy-and-safety.md](privacy-and-safety.md#3-guardrails) |
| 8 | **Demo ledger** | A synthetic 27-loan ledger to try everything without touching real data | Quick start, step 3 |

---

## Quick start (about 15 minutes)

Full detail for each step: [`docs/AskFinHive_instructions.md`](../../AskFinHive_instructions.md).

1. **Get the code.** On a new machine: `git clone https://github.com/K4nishk/FinHive.git`,
   then `cd FinHive` and `git checkout development`. As an MVP1 user: `git pull`. Read
   [§0](../../AskFinHive_instructions.md#0-already-using-mvp1-read-this-first) first.
2. **Set your OpenRouter key, once** (the AI service). See
   [§3.2](../../AskFinHive_instructions.md#32-openrouter-key-ai-set-once).
   *macOS:* put it in `ops/.env.local`. *Windows:* `setx`, then **open a new
   PowerShell window**. The **encryption key needs no setup**: the first launch creates
   `src/Loan Manager/data/encryption/master_key.key` and says so. **Back that file up**
   ([§3.1](../../AskFinHive_instructions.md#31-master-key-encryption-nothing-to-set-up-but-back-it-up)).
3. **Start on the demo ledger** from the `FinHive` folder:

   | macOS | Windows (PowerShell) |
   |---|---|
   | `./run_local_mac.sh demo` | `.\run_local_windows.bat demo` |

   The first run takes a few minutes while it installs. Expect a framed
   **"A new encryption key was created"** notice with the key file's path,
   `Seeded 27 demo loans…`, then the app window.
4. **Test each capability** using the pages linked in the table above.

Your real `data/loans.db` is never touched by steps 1–4. Moving it to MVP1.1 is a
separate, deliberate step: [§8 of the guide](../../AskFinHive_instructions.md#8-move-your-mvp1-ledger-to-mvp11-existing-users-once).

---

## Windows vs macOS at a glance

Inside the app, everything behaves the same on both. The differences are all in the
terminal:

| Task | Windows (PowerShell) | macOS (Terminal) |
|---|---|---|
| Start on the demo ledger | `.\run_local_windows.bat demo` | `./run_local_mac.sh demo` |
| Start the demo over | `.\run_local_windows.bat demo-reset` | `./run_local_mac.sh demo-reset` |
| Start on your real ledger | `.\run_local_windows.bat` (or double-click it) | `./run_local_mac.sh` |
| Encryption key | `src\Loan Manager\data\encryption\master_key.key` (created on first launch; back it up) | `src/Loan Manager/data/encryption/master_key.key` (same) |
| OpenRouter key | your user environment (`setx`, then a **new** window) | `ops/.env.local` |
| Python command (only if you need one) | `py` | `python3` (there is no `python`) |
| Demo ledger location | `%USERPROFILE%\finhive-demo\demo.db` | `~/finhive-demo/demo.db` |

A double-click on Windows cannot pass `demo`, so it always opens your real ledger.

---

## Known limits in this release

- **Stop** takes effect before the next request to the AI server, or at once while it is retrying. A request already sent still finishes or times out first (up to 60 s).
- Change requests must use English verbs (create, add, extend, renew, update, change,
  rename, correct, edit, modify). Hindi/Hinglish ("badha do") is not recognised yet.
- Undo works for extensions and newly created loans; paid-off and edit (UPDATE) batches
  cannot be undone from the tab.
- The real-ledger migration has been tested on synthetic ledgers only — keep the backup
  it asks you to take.
