# Report Calculation and Approval Flow

```
Source Loan Data
      |
      v
CalculateInterest (use case)
  - Applies interest formula (monthly/daily/both)
  - Computes post_extension_giving_date = loan.due_date
  - Computes post_extension_due_date = loan.due_date + extension_period (in unit)
  - Returns CalculationResultDTO with CalculationLineDTO per record
      |
      v
CalculationDialog (UI review)
  - User reviews per-record values
  - User can adjust rates, period, unit before generating report
      |
      v
GenerateReport (use case)
  - Creates Report + ReportRecords in database
  - Stores BOTH pre-extension (giving_date, due_date)
    AND post-extension (post_extension_giving_date, post_extension_due_date)
      |
      v
PendingApprovalTab (UI)
  - Displays "Orig G.Date" / "Orig D.Date" = pre-extension dates (read-only reference)
  - Displays "New G.Date" / "New D.Date" = post-extension dates (preview of approval)
  - Inline editing of Rate/Comm/Period/Unit/TDS triggers recalculation
  - Post-extension dates recalculate when extension_period or unit changes
      |
      v
ApproveReport (use case)
  - Persists post_extension_giving_date -> loan.giving_date
  - Persists post_extension_due_date -> loan.due_date
  - Approved values MATCH exactly what was previewed in the tab
  - For Paidoff reports: archives loan to history instead
```

## Date Field Semantics

| Field | Meaning | Editable? |
|---|---|---|
| `giving_date` | Original giving date (pre-extension) | No (on report) |
| `due_date` | Original due date (pre-extension) | No (on report) |
| `post_extension_giving_date` | New giving date after approval | Computed |
| `post_extension_due_date` | New due date after approval | Computed |

## Recalculation Rules

When `extension_period` or `extension_period_unit` is edited inline:
- `post_extension_giving_date = due_date` (unchanged)
- `post_extension_due_date = due_date + extension_period` (in unit: months or days)
- Interest, commission, TDS, CHQ amounts are recalculated
