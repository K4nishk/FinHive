# Persona A — MVP1 continuity

> Part of the `e2e-testing` skill — loaded only for `/e2e mvp1`. Rules of engagement and severity live in [`../SKILL.md`](../SKILL.md); log findings with [`../findings.md`](../findings.md).

## §A · Persona A — The MVP1 Incumbent

> **Who you are**: the single user who has run the MVP1 desktop app daily for months. You know every keystroke. You are suspicious of the rewrite. You will notice immediately if something you relied on is gone.
>
> **What you are testing**: that MVP2 lost nothing. Not just features — *infrastructure behaviour and UI/UX decisions* that were deliberate.

Work the matrix below. Mark each ✅ / ❌ / ⚠️ (works but degraded). Anything not ✅ becomes a finding.

### A1 · Loan entry (R1)

| # | Expected behaviour | Why it was decided |
|---|---|---|
| A1.1 | Autocomplete fires on `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group` from existing records | Reduces typos that fragment groups |
| A1.2 | Entering a known `borrower_name` auto-fills `borrower_group`; same for depositor | Explicit MVP1 requirement |
| A1.3 | `due_period` field appears **before** `due_date` in tab order and visually | Explicit ordering requirement |
| A1.4 | Entering `due_period` auto-computes `due_date = giving_date + N months` | Core derivation |
| A1.5 | Date picker opens on **Tab into** the field and on **double-click** — not just on a calendar icon click | UTR-1; the original bug that blocked release |
| A1.6 | Names are normalised to lowercase at write time | Filtering depends on it |
| A1.7 | Amount rejects negatives and non-integers | `Money` value object invariant |
| A1.8 | On save: status message `Loan saved successfully. Reference ID: {ref_id}.` | Exact string |
| A1.9 | App does **not** auto-switch to the View tab after save | Explicitly requested |

### A2 · View / loans table (R2)

| # | Expected behaviour | Why |
|---|---|---|
| A2.1 | Columns present: `SNo, ref_id, B Name, B Grp, Amt, D Name, D Grp, G Dt, D Dt, Status` | Agreed template |
| A2.2 | `SNo` sorts **numerically** (1, 2, 3, 10) — never as strings (1, 10, 2) | Fixed defect; regression-prone |
| A2.3 | Missing values render as `Unknown`, not blank or `null` | Explicit |
| A2.4 | `ref_id` is visible but **not editable** | Explicit |
| A2.5 | Inline edit works on every other column | Core |
| A2.6 | Editing a date column opens the **date picker**, not a text field | Explicit |
| A2.7 | Column filters behave like a spreadsheet: click selects, click again deselects, checkbox always matches internal state | Three architectural rewrites; highest historical defect density |
| A2.8 | Date filter offers year → month hierarchy from **existing records only** | Explicit |
| A2.9 | Selecting `2026-05` returns the May 2026 rows (not zero) | The exact defect from iteration 1 |
| A2.10 | Filter state survives closing and reopening the popup | The iteration-3 rewrite |
| A2.11 | Select All / Clear All update every checkbox visually | Same |
| A2.12 | Active filters are summarised above the table | Explicit |
| A2.13 | Empty result shows `No matching records found.` | Exact string |

### A3 · Status engine (R3)

| # | Expected behaviour |
|---|---|
| A3.1 | `giving_date > today` → **Pending** |
| A3.2 | `due_date` is null and `giving_date <= today` → **Overdue** |
| A3.3 | `giving_date <= today < due_date` → **Active** |
| A3.4 | `due_date <= today` → **Overdue** |
| A3.5 | Statuses recompute **on every app launch**, overriding stored values |
| A3.6 | Status colours carry MVP1 hue identity: Active green, Overdue red, Pending amber, Paidoff blue-grey |
| A3.7 | Colours come from theme config — no hardcoded hex anywhere in the UI |
| A3.8 | Manually setting an Overdue loan to Active **prompts for a new due date** (never silently reverts) |
| A3.9 | Mark Paidoff is **disabled** when the loan has no `due_date` |
| A3.10 | Mark Paidoff is **disabled** when a Paidoff report is already pending for that loan |
| A3.11 | Paidoff warning text appears: *"This report was generated for a Paidoff loan. The loan will be moved to history. No extension will be applied."* |
| A3.12 | On Paidoff approval the loan leaves the active view and lands in history |

### A4 · Reference IDs, delete, extend (R4)

| # | Expected behaviour |
|---|---|
| A4.1 | Format is `YYYY_MM_<order>`, zero-padded to 3 (`2026_03_001`) |
| A4.2 | Order 1000+ works (`2026_12_1000`) — no wrap, no crash |
| A4.3 | Counter is **per YYYY_MM** |
| A4.4 | Deleting `2026_03_005` then adding gives `2026_03_006` — the number is not reused |
| A4.5 | Deleting all records for a month resets that month's counter to 001 |
| A4.6 | Extend: new `giving_date` = old `due_date`; new `due_date` = old `due_date + extension_period` |
| A4.7 | Extend on a loan with **no** `due_date`: `giving_date` = today, `due_date` = user-picked |
| A4.8 | `ref_id` is reused on extend (record overwritten) |

### A5 · Interest calculator (R5) — the correctness core

| # | Expected behaviour |
|---|---|
| A5.1 | Monthly: `(amount × rate × months) / 1200` |
| A5.2 | Daily: `(amount × rate × days) / 36500` |
| A5.3 | **`giving_date` is never a calculation input.** ₹10,000 @ 12%, 3-month term + 1-month extension → **₹100**, not ₹400 |
| A5.4 | Commission uses the same formula with `commission_rate` |
| A5.5 | `TDS = 0.1 × interest` when the flag is on; zero when off |
| A5.6 | `CHQ = interest − TDS` |
| A5.7 | All three modes selectable; `Both` takes per-record unit |
| A5.8 | Five filters combinable: Borrower Group, Borrower Name, Depositor Name, Depositor Group, ByMonth |
| A5.9 | Depositor Group filter offers an `Unknown`/blank option |
| A5.10 | **ByMonth excludes** no-due-date records; other filters include them if matching |
| A5.11 | Sample checkpoint: `bg3` → **2 records**; `dg3` → **4 records** |
| A5.12 | Global rate changes overwrite **all** rows, including manually edited ones |
| A5.13 | `Generate Report` is disabled until `Calculate` has been clicked |
| A5.14 | Summary shows `total_loan_amount`, `total_interest`, `total_commission` |

### A5b · ByMonth multi-select (new requirement — validate once development completes)

ByMonth changed from single-selection radio buttons to **multi-selection checkboxes**. The predicate moved from equality on one month to membership in a selected set. Test both the new capability and the rules it must not have broken.

| # | Expected behaviour | Why it matters |
|---|---|---|
| A5b.1 | ByMonth renders **checkboxes**, not radio buttons | The interaction change itself |
| A5b.2 | Two or more months can be selected simultaneously | The requirement |
| A5b.3 | **Success metric**: with months selected, the result is exactly the **union** — every loan whose `due_date` month is in ANY selected month, and no others | The acceptance criterion. Assert both directions: nothing missing, nothing extra |
| A5b.4 | Selecting one month returns exactly what the old single-select returned | Backward compatibility — the regression most likely to slip |
| A5b.5 | Selecting **none** behaves as the no-filter case, **not** as select-all | Ambiguous by nature; the easiest thing to get backwards |
| A5b.6 | Deselecting a month removes only that month's records | Set removal, not a full reset |
| A5b.7 | No-due-date records stay **excluded** whenever any month is selected | MVP1 rule A5.10 must survive |
| A5b.8 | Current-calendar-year scoping still applies | MVP1 rule |
| A5b.9 | Overdue records are still included | MVP1 rule |
| A5b.10 | ByMonth combines correctly with the other four filters — intersection across filter types, union within ByMonth | The composition rule; easy to get wrong |
| A5b.11 | Checkbox visual state always matches the applied filter, including after reopening | The MVP1 filter-desync defect class (three rewrites) — do not let it return through a new control |
| A5b.12 | Generated report contains exactly the multi-month filtered set | The filter must reach the report, not just the preview |
| A5b.13 | Selected months appear in the report's active-filter summary and in print/PDF output | A report that does not state its filter is unauditable |

> **Test on both surfaces.** The requirement lands in MVP1 (desktop, live system) first and MVP2 (web) second. Run A5b against each. MVP2 must match MVP1's behaviour on the same dataset — that is the parity check, and it is why the MVP1 change ships first.

### A6 · Approvals (R5/R6)

| # | Expected behaviour |
|---|---|
| A6.1 | `report_id` format `RPT_YYYYMMDD_<order>` |
| A6.2 | Report shows pre-extension **and** projected post-extension dates side by side |
| A6.3 | Editing rate / period / unit / TDS recalculates amounts immediately |
| A6.4 | Editing bumps the report's last-update date |
| A6.5 | Duplicate ref across pending reports warns: *"This report shares loan records with another pending report. Approving may overwrite previous updates."* with Proceed / Cancel |
| A6.6 | Deleted-loan case warns: *"Records in this report have been deleted."* with skip / decline |
| A6.7 | Decline deletes the report and changes no loan data |
| A6.8 | Approve updates loans **and** the report records |
| A6.9 | The queue survives a restart |
| A6.10 | Approved reports are printable / exportable to PDF |
| A6.11 | Printed report is borrower-grouped, alphabetical, one row per record, with per-borrower totals |

### A7 · Import / export (R6)

| # | Expected behaviour |
|---|---|
| A7.1 | CSV and XLSX both import |
| A7.2 | Rows without `ref_id` get auto-assigned IDs |
| A7.3 | Conflicting `ref_id`: imported record wins, completely |
| A7.4 | Preview dialog shows new count, overwrite count, and sample overwritten ref_ids |
| A7.5 | Preview is **skipped** for new-only imports |
| A7.6 | Export produces CSV and XLSX |

### A8 · Infrastructure & operational behaviour

The category most likely to be silently dropped in a rewrite. **Test these deliberately.**

| # | Expected behaviour | How to force it |
|---|---|---|
| A8.1 | Status recompute runs at launch | Set a due date to yesterday directly in storage, relaunch, confirm it flips to Overdue |
| A8.2 | Crash-recovery warning appears when a recovery marker exists | Create `approval_recovery.tmp`, launch, expect the non-blocking warning |
| A8.3 | The warning is **non-blocking** — the app remains usable | — |
| A8.4 | A timestamped backup is written before destructive operations | Approve a report, check the backup location |
| A8.5 | Logs are written and rotate | Check `./data/logs/app.log` exists and grows |
| A8.6 | Launcher checks the Python version and fails with a readable message | Point the launcher at Python 3.9 |
| A8.7 | Both themes apply cleanly; theme choice persists across restart | — |
| A8.8 | Data directory is created on first run if absent | Delete `./data/`, launch |
| A8.9 | Dates are stored ISO 8601 | Inspect storage |
| A8.10 | Amounts are integers — no float drift | Inspect storage after a calculation |

### A9 · UI/UX decisions that were deliberate

| # | Expected behaviour |
|---|---|
| A9.1 | Keyboard-first: the full entry form is completable without a mouse |
| A9.2 | Focus indicators stay visible throughout |
| A9.3 | Minimal horizontal scrolling at the default window size |
| A9.4 | Spreadsheet-like feel: click a cell, type, Tab commits |
| A9.5 | Status colours carry meaning without relying on colour alone (text label present) |
| A9.6 | Dark and light themes both legible; no unreadable contrast pairs |

### A9b · Encryption at rest (ADR-2.3 — validate from M1a onward)

PII is AES-256-GCM encrypted at rest with an HMAC blind index for lookups. These checks prove the protection is real *and* that it did not cost an MVP1 behaviour.

| # | Expected behaviour | Why |
|---|---|---|
| A9b.1 | No plaintext borrower or depositor name appears anywhere in the database file, its indexes, or WAL segments | The core claim. Inspect the file, do not take the app's word |
| A9b.2 | A row written through the app reads back with the correct plaintext | Round-trip works |
| A9b.3 | A tampered ciphertext is **rejected by the GCM auth tag**, not decrypted to garbage | Integrity, not just confidentiality |
| A9b.4 | Exact-match filter on borrower and depositor returns the right rows (A5.8 via blind index) | Equality survived |
| A9b.5 | Autocomplete (A1.1) and group auto-fill (A1.2) still work | Blind index covers them |
| A9b.6 | **Alphabetical sort (A2.1) is correct** — by name, not by ciphertext | The check the earlier tokenisation approach would have failed |
| A9b.7 | `borrower_group` and `depositor_group` are encrypted too | A business name identifies a business |
| A9b.8 | **All financial values are encrypted** — `amount`, `interest_amount`, `commission_amount`, `tds_amount`, `chq_amount` | NPI under the mandated GLBA-equivalent baseline (ADR-2.4) |
| A9b.8a | **No `_bidx`, order-preserving or format-preserving column exists on any amount** | The one mistake that would undo the encryption. Amounts cluster on round numbers, so a deterministic index is reversible by frequency analysis |
| A9b.8b | **Numerical sort on `amount` (A2.1) is correct** — by value, not by ciphertext | App-side decrypt-and-sort covers amounts too |
| A9b.8c | `LoanTotals` sums exactly the rows returned, computed with `Decimal` | SQL `SUM` is gone; the footer must still reconcile with the table |
| A9b.8d | `proposed_mutations` snapshots and `agent_turns.react_trace` hold no plaintext amount | JSONB blobs are NPI and are retained 7 years |
| A9b.8e | Cold archive partitions in Blob are encrypted | The longest-lived copy must not be the weakest protected |
| A9b.8f | A negative or fractional amount is rejected by `Money` | The DB CHECK is gone; the value object is now the sole guard |
| A9b.9x | `interest_rate`, `commission_rate`, dates, `due_period`, `extension_period`, `reference_id`, `status` are **not** encrypted | Decisions 13/14 — a percentage is not a balance; periods and dates are needed for arithmetic and range filters |
| A9b.9y | **No plaintext column carries a *derived* financial value** (e.g. `total_repayable`) | Such a column would open a solve path back to `amount` through the plaintext rate. Re-run ADR-2.4's derivation check before any exception |
| A9b.9 | Key rotation re-encrypts a subset while the app reads both `key_version`s | Rotation is incremental, not big-bang |
| A9b.10 | Import and export round-trip correctly (encrypt on write, decrypt on read) | CSV/XLSX unaffected |
| A9b.11 | From M2: the outbound LLM payload carries `PERSON_1` **and `AMOUNT_1`** — never ciphertext, never a real name, never a raw figure | Ordering: decrypt → mask → send. See C1.11 |
| A9b.12 | From M2: **no tool returns a raw figure for the model to operate on**, and the agent performs no arithmetic on financial values | ADR-2.4 decision 12 — tools compute, the agent narrates |

> **A9b.1 must run before the first real data import.** Once a plaintext row exists, the file test can pass on new rows while old ones remain exposed.

### A10 · Reporting Persona A

```markdown
## MVP1 Continuity Report — <target> — <date>

**Verdict**: PARITY HELD / PARITY LOST / DEGRADED

| Area | ✅ | ⚠️ | ❌ | Lost capability |
|---|---|---|---|---|
| A1 Entry | | | | |
| A2 View | | | | |
| ... | | | | |

### Parity breaks (each becomes a finding)
### Degradations (works, but worse than MVP1)
### Improvements worth keeping
```

**Any ❌ in A5 (calculations) or A8 (infrastructure) blocks release.** Everything else is negotiable.
