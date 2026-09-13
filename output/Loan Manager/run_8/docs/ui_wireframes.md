# UI Wireframes — Loan Manager MVP1

Text-based wireframes. Proportions are indicative.

---

## Main Window

```
+===========================================================+
|  Loan Manager                              [_] [□] [X]    |
+===========================================================+
| [Entry] [View] [Calculator] [Pending Approval] [Settings] |
+-----------------------------------------------------------+
|                                                           |
|                  [TAB CONTENT AREA]                       |
|                                                           |
+-----------------------------------------------------------+
| Status bar: Ready                                         |
+===========================================================+
```

---

## Tab 1 — Entry

```
+-----------------------------------------------------------+
|  New Loan Entry                                           |
+-----------------------------------------------------------+
|                                                           |
|  Borrower Name:   [____________________________] ▼        |
|  Borrower Group:  [____________________________] ▼        |
|                                                           |
|  Depositor Name:  [____________________________] ▼        |
|  Depositor Group: [____________________________] ▼        |
|                                                           |
|  Amount (INR):    [____________________________]          |
|                                                           |
|  Giving Date:     [📅 2026-06-30              ]          |
|                                                           |
|  Due Period (mo): [____]  ← enter months here            |
|  Due Date:        [📅 auto-calculated          ]         |
|                   (or type / double-click to pick)        |
|                                                           |
|                              [Clear]  [Save Loan]         |
|                                                           |
+-----------------------------------------------------------+
| Status bar: Loan saved successfully. Reference ID: ...    |
+-----------------------------------------------------------+

Notes:
- Due Period appears before Due Date
- Giving Date and Due Date: Tab into field opens date-picker popup
- Double-click on date field also opens date-picker
- Autocomplete dropdown (▼) on name/group fields
- Borrower Group auto-fills when borrower_name matches history
- Depositor Group auto-fills when depositor_name matches history
```

---

## Tab 2 — View

```
+-----------------------------------------------------------+
|  Loan Records                                [🔍 Filter ▼]|
+-----------------------------------------------------------+
| [▼ Col filters row - per column ]                         |
+----+----------+------+------+-----+------+------+--------+----------+----------+--------+
| No | Ref ID   | B Nm | B Gp | Amt | D Nm | D Gp | G Date | D Date   | Status   |        |
+----+----------+------+------+-----+------+------+--------+----------+----------+--------+
|  1 | 2026_01_ | b1   | bg1  |10000| d1   | dg1  |2026-01 |2026-04-02| [Active▼]|        |
|  2 | 2026_01_ | b2   | bg2  |10000| d2   | dg1  |2026-01 |2026-05-04|[Overdue▼]|        |
|  3 | 2026_02_ | b3   | bg3  |15000| d3   | dg1  |2026-02 |2026-05-06|[Pending▼]|        |
| ...                                                                                       |
+-------------------------------------------------------------------------------------------+
|  Right-click menu:                                        |
|  ┌─────────────────────┐                                  |
|  │ Extend              │                                  |
|  │ Mark Paidoff        │  (disabled if no due_date        |
|  │ Delete              │   or pending paidoff report)     |
|  └─────────────────────┘                                  |
+-----------------------------------------------------------+

Notes:
- Status column: QComboBox; colour-coded cell backgrounds
  Active=#025c33, Overdue=#6b0307, Pending=#804001, Paidoff=#022a52 (defaults; configurable)
- All columns sortable (click header)
- Column filter dropdowns: text=checkbox list; dates=YYYY→MM hierarchy
- Inline edit: click any cell (except ref_id) to edit
- Date cells: clicking opens DatePickerDialog
- Missing values shown as "Unknown"
- SNo is display-only counter (1, 2, 3...) — not persisted
```

### Column Filter (Date Columns)
```
+------------------+
| G Date  ▼        |
+------------------+
| ▶ 2026           |
|   ▶ January      |
|   ▶ March        |
| ▶ 2025           |
|   ▶ December     |
+------------------+
| [Clear] [Apply]  |
+------------------+
```

---

## Tab 3 — Calculator

```
+-----------------------------------------------------------+
|  Interest Calculator          Mode: [Monthly ▼]           |
+-----------------------------------------------------------+
|  Filters:                                                 |
|  Borrower Group:  [All ▼]   Borrower Name:  [All ▼]     |
|  Depositor Name:  [All ▼]   Depositor Group:[All ▼]     |
|  By Month:        [-- ▼]                                  |
|                                                           |
+-----------------------------------------------------------+
|  Global Inputs:                                           |
|  Interest Rate (%): [____]   Commission Rate (%): [____] |
|  Extension Period:  [____]   Unit: [months ▼]            |
|  TDS: [ ] Apply TDS                                       |
|                                                           |
|              [Calculate]   [Generate Report] (disabled)   |
+-----------------------------------------------------------+

After Calculate → Calculation Dialog opens:

+===========================================================+
|  Calculation Results                          [×]         |
+===========================================================+
|  ref_id  | B Name | Amount | D Name | G Date | D Date    |
|  Int Rate | Comm % | Ext Per| Unit   | Interest| Comm     |
+----------+--------+--------+--------+--------+-----------+
|  2026_02 | b3     | 15000  | d3     |2026-02 |2026-05-06 |
|  [12.0%] |[2.0%]  |  [3]   |[months]| 450.00 | 75.00     |
+----------+--------+--------+--------+--------+-----------+
|  [editable cells for rate, period, unit per row]          |
+===========================================================+
|  Total Amount: 45000   Total Interest: 1350   Comm: 225   |
+-----------------------------------------------------------+
|                            [Cancel]  [Generate Report]    |
+===========================================================+

Notes:
- Mode selector: hover-dropdown (QMenu or QComboBox styled)
- Both mode: extension_period and unit editable per-row
- Changing global input overwrites all rows
- Generate Report button active only after Calculate
```

---

## Tab 4 — Pending Approval

```
+-----------------------------------------------------------+
|  Pending Approval Queue                                   |
+-----------------------------------------------------------+
|  Report ID       | Created    | Updated    | Status       |
|  RPT_20260320_001| 2026-03-20 | 2026-03-20 | [Pending]   |
|  RPT_20260321_002| 2026-03-21 | 2026-03-22 | [Pending]   |
+-----------------------------------------------------------+
|  [Selected Report Detail — expandable below]              |
+-----------------------------------------------------------+
|  ref_id  |B Name| Amt  |D Name| G Dt |D Dt  |Ext|Unit    |
|  Int%|Comm%|TDS|Interest|Comm |TDS_Amt|CHQ   |PostGDt|PostDDt|
|  ── pre-extension values ──── | ─── post-extension preview ─ |
+-----------------------------------------------------------+
|  [editable: Int%, Comm%, Ext, Unit, TDS checkbox]         |
|  [auto-recalculate on edit]                               |
+-----------------------------------------------------------+
|               [Print/PDF]    [Decline]    [Approve]       |
+-----------------------------------------------------------+

Notes:
- Reports persist across restarts
- Duplicate ref_id warning shown on Approve (with Proceed/Cancel)
- Deleted loan warning shown on Approve (with Ignore/Decline)
- Print opens system QPrintDialog
- Approved reports: post-extension values written to loans table
```

---

## Tab 5 — Settings

```
+-----------------------------------------------------------+
|  Settings                                                 |
+-----------------------------------------------------------+
|  Theme:        [Dark ▼]   [Apply]                         |
|                                                           |
|  Status Colours (editable):                               |
|  Active:  [#025c33] [Pick]    Overdue:  [#6b0307] [Pick] |
|  Pending: [#804001] [Pick]    Paidoff:  [#022a52] [Pick] |
|                                                           |
|  Data Directory: [./data/            ] [Browse]           |
|                                                           |
|  Import Legacy Data: [Import CSV/XLSX...]                 |
|  Export All Loans:   [Export CSV] [Export XLSX]           |
|                                                           |
|  Log Level:    [INFO ▼]                                   |
+-----------------------------------------------------------+

Notes:
- Theme applies QSS stylesheet + colour config
- Colour pickers update theme_config.json
- Import Legacy Data triggers CSV-to-SQLite migration (BL-24)
```

---

## Dialogs

### DatePickerDialog
```
+========================+
|  Select Date     [×]   |
+========================+
|  [← June 2026 →]       |
|  Mo Tu We Th Fr Sa Su  |
|  ...  calendar grid .. |
+------------------------+
|       [Cancel] [OK]    |
+========================+
```
Triggered by: Tab into date field, or double-click date cell.

### ExtendDialog
```
+=================================+
|  Extend Loan: 2026_03_001  [×]  |
+=================================+
|  Extension Period:  [3   ]      |
|  Unit:              [months ▼]  |
|                                 |
|  New Giving Date: 2026-05-06    |  ← old due_date
|  New Due Date:    2026-08-06    |  ← calculated
|                                 |
|          [Cancel]  [Extend]     |
+=================================+
```

### PaidOffDialog
```
+==================================+
|  Mark Paidoff: 2026_03_001  [×]  |
+==================================+
|  Paidoff Date:    [📅           ]|
|  Interest Rate (%): [12.0]       |
|  Commission Rate (%): [2.0]      |
|  Apply TDS: [ ]                  |
|                                  |
|  ⚠ This report will be sent to  |
|  Pending Approval. The loan will |
|  be moved to history on approve. |
|                                  |
|           [Cancel]  [Submit]     |
+==================================+
```

### ImportPreviewDialog
```
+=========================================+
|  Import Preview                   [×]   |
+=========================================+
|  File: loans_import.csv                 |
|  New records:       12                  |
|  Records to overwrite: 3               |
|  Sample overwrites: 2026_01_003,        |
|                     2026_02_007,        |
|                     2026_03_001         |
|                                         |
|  ⚠ Imported data will overwrite        |
|  existing records with same ref_id.     |
|                                         |
|             [Cancel]  [Proceed]         |
+=========================================+
```
