# FinHive Loan Manager — MVP1.1 release summary

MVP1.1 keeps everything MVP1 did and adds **Ask FinHive**: ask questions about your
ledger in plain English and let the assistant draft changes for you to approve. It also
encrypts your ledger on disk and tightens the approval flow.

Everything here runs on the **desktop app**. Nothing in MVP1 was removed.

> **Which launcher?** Use the one inside `src/Loan Manager/`:
> **Windows:** `src\Loan Manager\run_windows.bat` · **macOS:** `src/Loan Manager/run_mac.sh`.
> The `run_local_*` scripts at the repo root start the future **web** app (MVP2),
> which is paused and will stop with a "KCH-90" message.

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

Each step links to the exact section of the setup guide,
[`docs/AskFinHive_instructions.md`](../../AskFinHive_instructions.md), which has
separate **Windows (PowerShell)** and **macOS** commands for every step.

1. **Install or update** — new machine: [§2 Install](../../AskFinHive_instructions.md#2-install).
   MVP1 user: `git pull`, then run your launcher as usual — read [§0](../../AskFinHive_instructions.md#0-already-using-mvp1-read-this-first) first.
2. **Set two keys, once** — a master key (encryption) and an OpenRouter key (AI):
   [§3](../../AskFinHive_instructions.md#3-set-your-keys-once).
   *Windows and macOS differ here:* Windows uses `setx` and needs a **new** window
   afterwards; macOS uses `ops/.env.local` or `export`.
3. **Create the demo ledger and launch on it** — [§4](../../AskFinHive_instructions.md#4-create-a-demo-ledger) and
   [§5](../../AskFinHive_instructions.md#5-launch-the-demo).
   *Windows:* start the app **from the same PowerShell window**. A double-clicked
   launcher does not see the demo setting and opens your real ledger instead.
4. **Test each capability** with the pages linked in the table above.

Your real `data/loans.db` is never touched by steps 1–4. Moving it to MVP1.1 is a
separate, deliberate step: [§8 of the guide](../../AskFinHive_instructions.md#8-move-your-mvp1-ledger-to-mvp11-existing-users-once).

---

## Windows vs macOS at a glance

Inside the app, everything behaves the same on both. The differences are all in the
terminal:

| Task | Windows (PowerShell) | macOS (Terminal) |
|---|---|---|
| Activate the environment | `.\.venv\Scripts\Activate.ps1` | `source .venv/bin/activate` |
| Save a key for future windows | `setx NAME "value"` (open a new window after) | line in `ops/.env.local` |
| Set a value for this window only | `$env:NAME = "value"` | `export NAME="value"` |
| Launcher | `run_windows.bat` | `./run_mac.sh` |
| Copy a file | `Copy-Item a b` | `cp a b` |
| Paths | `src\Loan Manager` | `src/Loan Manager` |

---

## Known limits in this release

- No **Stop** button while a question is being answered (each AI call can take up to 60 s).
- Change requests must use English verbs (create, add, extend, renew, update, change,
  rename, correct, edit, modify). Hindi/Hinglish ("badha do") is not recognised yet.
- Undo works for extensions and newly created loans; paid-off and edit (UPDATE) batches
  cannot be undone from the tab.
- The real-ledger migration has been tested on synthetic ledgers only — keep the backup
  it asks you to take.
