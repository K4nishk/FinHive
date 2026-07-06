# Assumptions — Loan Manager

## A-01 — Storage
- All data stored in `./data/` relative to application root
- CSV format is sufficient for expected volume (~1500 records max)
- No concurrent session handling required (single user)
- No database required for prototype; CSV with Pandas or stdlib csv module
- Database SQLite required for MVP1

## A-02 — Dates
- All dates stored in ISO 8601 format (`YYYY-MM-DD`)
- `giving_date` is reference-only and never used in interest/period calculations
- A loan with no `due_date` and a past `giving_date` is treated as Overdue
- A loan with no `due_date` and a future `giving_date` is treated as Pending
- "today" = application launch date (system clock)

## A-03 — Currency
- Amount is always INR
- Amount is a non-negative integer (no decimal support in prototype)

## A-04 — Reference IDs
- Max 999 loans/month is a safe upper bound; overflow to 4-digit order is supported
- Counter high-water mark stored in `loans_meta.csv`
- Deletion does not reuse vacated order numbers

## A-05 — Calculator
- `giving_date` is NOT used in time-period calculations — only extension_period counts
- This is an authoritative overhaul of previous implementation behaviour
- Mode = Both requires orchestrator function in core calculator for testability
- Global input values override per-record values when changed

## A-06 — Reports
- History loss on Extend is explicitly accepted by user
- Approved reports overwrite loan records without preserving prior state
- Paidoff report sent to Pending Approval; loan not moved to history until approved

## A-07 — Import
- At least 80% of imported data will follow the standard `YYYY_MM_<order>` ref_id format
- Free-text legacy IDs are low-relevance; auto-assign + collision check is sufficient

## A-08 — Platform
- Primary user: Windows (end-user)
- Secondary user: macOS (tester/developer bridging git)
- Python >= 3.10 assumed installed; launchers validate this
- PySide6 is the GUI framework
- No network requirements; data shared via git

## A-09 — Sample Data
- 15-record sample dataset (b1–b15) used for developer testing and demo only
- Production ships with empty data files
- Sample data answers:
  - Loans b14, b15 have no depositor_group → shown as "Unknown"
  - `bg3` filter → 2 records (b3, b4)
  - `dg3` filter → 4 records (b6, b7, b8, b9)

## A-10 — Backup / Recovery
- Timestamped backup before destructive operations (Paidoff, bulk Approve) is deferred to post-prototype
- `approval_recovery.tmp` crash-safety mechanism is in scope for prototype
- Atomic Paidoff write (logs to recovery file before each CSV write) is in scope

## A-11 — UI
- No "fill all rows" / "copy down" shortcut needed for prototype
- Filtered record count post-filtering is expected to stay under 10 records for prototype

## A-12 — Themes
- Theme preference is deferred to user feedback after first prototype build; at least 2 options delivered
