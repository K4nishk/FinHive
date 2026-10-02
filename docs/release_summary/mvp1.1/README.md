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

## What's new

| # | Capability | In one line | Try it |
|---|---|---|---|
| 1 | **Ask FinHive tab** | Ask about loans in plain English; see the steps it took and the loans behind the answer | [ask-finhive.md](ask-finhive.md) |
| 2 | **AI-drafted changes** | Ask it to extend or create loans; it drafts a batch, you approve it | [drafts-approvals-undo.md](drafts-approvals-undo.md) |
| 3 | **Approvals tab upgrades** | AGENT/FORM badges, the original request, conflict warnings, **Undo** | [drafts-approvals-undo.md](drafts-approvals-undo.md) |
| 4 | **Statuses refresh on approval** | Approved extensions show the new status immediately — no restart | [drafts-approvals-undo.md](drafts-approvals-undo.md#4-status-refreshes-right-away) |
| 5 | **Encryption at rest** | Names and amounts are encrypted in the database file; a master key is required | [privacy-and-safety.md](privacy-and-safety.md#1-encryption-at-rest) |
| 6 | **Privacy with the AI** | Names and amounts are swapped for codes before anything is sent to the AI service | [privacy-and-safety.md](privacy-and-safety.md#2-what-the-ai-service-sees) |
| 7 | **Guardrails** | Read-only unless you ask for a change; loan topics only; 2,000-character limit | [privacy-and-safety.md](privacy-and-safety.md#3-guardrails) |
| 8 | **Demo ledger** | A synthetic 27-loan ledger to try everything without touching real data | Quick start, step 3 |

---

## Quick start (about 15 minutes)

Full detail for each step: [`docs/AskFinHive_instructions.md`](../../AskFinHive_instructions.md).

1. **Get the code.** On a new machine: `git clone https://github.com/K4nishk/FinHive.git`,
   then `cd FinHive` and `git checkout development`. As an MVP1 user: `git pull`. Read
   [§0](../../AskFinHive_instructions.md#0-already-using-mvp1-read-this-first) first.
2. **Set two keys, once:** a master key (encryption) and an OpenRouter key (AI). See
   [§3](../../AskFinHive_instructions.md#3-set-your-keys-once).
   *macOS:* put them in `ops/.env.local`. *Windows:* `setx`, then **open a new
   PowerShell window**.
3. **Start on the demo ledger** from the `FinHive` folder:

   | macOS | Windows (PowerShell) |
   |---|---|
   | `./run_local_mac.sh demo` | `.\run_local_windows.bat demo` |

   The first run takes a few minutes while it installs. Expect
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
| Where the keys live | your user environment (`setx`, then a **new** window) | `ops/.env.local` |
| Python command (only if you need one) | `py` | `python3` (there is no `python`) |
| Demo ledger location | `%USERPROFILE%\finhive-demo\demo.db` | `~/finhive-demo/demo.db` |

A double-click on Windows cannot pass `demo`, so it always opens your real ledger.

---

## Known limits in this release

- No **Stop** button while a question is being answered (each AI call can take up to 60 s).
- Change requests must use English verbs (create, add, extend, renew, update, change,
  rename, correct, edit, modify). Hindi/Hinglish ("badha do") is not recognised yet.
- Undo works for extensions and newly created loans; paid-off and edit (UPDATE) batches
  cannot be undone from the tab.
- The real-ledger migration has been tested on synthetic ledgers only — keep the backup
  it asks you to take.
