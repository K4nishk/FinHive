# Ask FinHive — ask questions in plain English

[← Release summary](README.md)

**Before you start:** the app is running on the demo ledger
([Quick start](README.md#quick-start-about-15-minutes), steps 1–3). Open the
**Ask FinHive** tab. Everything below is the same on Windows and macOS.

The AI's wording changes from run to run. Check the **steps** and the **numbers**, not
the exact sentence.

---

## The screen

| Area | What it shows |
|---|---|
| Input box + **Ask** | Your question. Press Enter or click Ask. |
| Two grey notes under the input | What not to type (see [privacy](privacy-and-safety.md#2-what-the-ai-service-sees)) |
| **Step n / 6 · elapsed** | Progress. One question takes at most 6 steps. |
| Bold answer line | The answer, with real names and ₹ amounts |
| **Trace** (left) | Each step the assistant took, with names shown as codes |
| **Table** (right) | The exact loans behind the answer |
| **New conversation** | Starts fresh (follow-ups otherwise remember earlier questions) |

---

## 1. A plain question

1. Type `What is overdue for the sharma group?` and click **Ask**.
2. **Expect:**
   - The trace fills in: `get_current_context` → `resolve_entity` → `query_loans`.
   - The answer gives about **₹5,50,000** overdue.
   - The table lists **rakesh sharma** (₹2,50,000) and **vikram sharma** (₹3,00,000) only.

## 2. A follow-up

1. Without clicking New conversation, type `And which of them is due soonest?`
2. **Expect:** it answers about the same two loans. It remembers your earlier question.

## 3. An ambiguous name

1. Click **New conversation**, then type `How much does iyer owe?`
2. **Expect:** a clarifying question (lakshmi iyer or suresh iyer?). The trace has **no**
   `query_loans` step yet.

## 4. Edge cases the ledger rules handle

| Type | Expect |
|---|---|
| `Is anything overdue for menon traders?` | **Yes.** deepak menon's loan has no due date, and the rules count that as overdue. It is left out of any "days overdue" figure. |
| `Is anything pending for verma textiles?` | **Yes**, pooja verma's loan. It starts in the future. |
| `What is the interest on <ref id from the table> at 12% for 3 months?` | A `calculate_interest` step appears. The app does the arithmetic (`amount × rate × months / 1200`), not the AI. |

### Ask about one person (F-004, fixed)

| Type | Expect |
|---|---|
| `Is deepak menon overdue?` | **Yes**, one loan with no due date. The trace shows `query_loans` with `borrower_name` set to a code (`B00n`), not a group. |
| `Is pooja verma's loan active?` | **No, it is pending**: it starts in the future. |
| `How much has arjun rao deposited that is active?` | A count and total filtered by `depositor_name`. |

Before this fix the lookup could only filter by group, so these questions failed with
"I could not form a valid request…".

## 5. Failure messages are plain

| Do this | Expect |
|---|---|
| Unset `OPENROUTER_API_KEY` and restart the app (see note below) | The answer line says the AI service is **not configured**, naming the key. No crash. |
| Paste more than 2,000 characters | "That question is too long…". Nothing is sent. |
| Close the window while a question is running | The app closes within about 5 seconds, without an error. |

To run once without the AI key:

**Windows (PowerShell)**: this removes the key for this window only.
```powershell
Remove-Item Env:OPENROUTER_API_KEY; .\run_local_windows.bat demo
```
**macOS**: the launcher reloads `ops/.env.local` on every start, so put `#` in front of
the `OPENROUTER_API_KEY` line there, run `./run_local_mac.sh demo`, then remove the `#`.

---

Next: [drafts, approvals and undo →](drafts-approvals-undo.md)
