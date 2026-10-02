# AI-drafted changes, approvals and undo

[← Release summary](README.md)

**Before you start:** the app is running on the demo ledger
([Quick start](README.md#quick-start-about-15-minutes)). These steps change the demo
data. To start over, reset it (see the end of this page). Everything in the app is the
same on Windows and macOS.

**The rule:** the assistant only **drafts**. Nothing changes in the ledger until you
approve it in **Pending Approval**.

---

## 1. Ask for a change

1. In **Ask FinHive**, type `Extend all overdue loans in sharma group by 3 months`.
2. **Expect:**
   - The trace shows a **Proposal** row.
   - The answer says a draft was queued for approval.
   - The status bar mentions the queued draft.

Why 3 months? An extension moves each due date forward from the **old due date**:
rakesh 10 Jul → 10 Oct, vikram 15 Aug → 15 Nov. One month would leave both still in the
past, so they would stay overdue.

## 2. Review it in Pending Approval

1. Open **Pending Approval** and select the new batch.
2. **Expect:**
   - An **AGENT** badge, where batches you made with the Entry/Calculator forms show **FORM**.
   - **Your exact request** shown above the rows.
   - One row per loan, with old and new due dates.

**Conflict warning:** if the same loan appears in two pending batches, both are flagged.
Approving one first would silently make the other stale. To see it, run the step 1
question twice, then select either batch.

## 3. Approve it

1. Click **Approve** on the batch.
2. Open **View**.

## 4. Status refreshes right away

**Expect:** rakesh and vikram sharma show **Active**, with no restart.

(In MVP1 the status only refreshed on the next launch. It now also refreshes when you
approve. This holds while today is before their new due dates.)

## 5. Undo it

1. In **Pending Approval → Recently Approved**, select the batch you approved.
2. Click **Undo** and confirm.
3. **Expect:** in **View**, both loans are back to their original due dates and **Overdue**.

Undo works for **extensions** and **newly created loans**. Paid-off and edit (UPDATE)
batches show a message saying they cannot be undone here.

## 6. Ask to create a loan

1. Type `Create a new loan for sunita sharma in sharma group, depositor arjun rao, amount 50000, for 6 months`.
   A new loan needs a borrower, a group already in the ledger, a depositor, an amount
   and a term. If you leave one out, the assistant asks for it.
2. **Expect:** a draft row with a new reference id, in Pending Approval.
3. Approve it, then **Undo**. The loan disappears from View again.

## 7. Requests it should NOT draft

| Type | Expect |
|---|---|
| `Which loans are overdue?` | A read-only answer, with no Proposal row. |
| `Delete all loans` | Declined. There is no delete tool. |
| `Extend the menon traders loan by 2 months` | Refused. That loan has no due date, so there is nothing to extend from. It asks for an explicit new due date instead. |

---

## Reset the demo

**Windows (PowerShell)**, in the window where you set the demo path:
```powershell
python -m loan_manager.infrastructure.seed --db $env:FINHIVE_DB_PATH --replace
```
**macOS**
```bash
python -m loan_manager.infrastructure.seed --db "$FINHIVE_DB_PATH" --replace
```

Next: [privacy and safety →](privacy-and-safety.md)
