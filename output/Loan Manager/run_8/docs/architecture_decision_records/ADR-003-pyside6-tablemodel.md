# ADR-003 — QAbstractTableModel over QTableWidget for Loan View

**Date**: 2026-06-30
**Status**: Accepted

## Context
View Tab must display up to 1500 rows with inline editing, sorting, per-column filtering (including date hierarchy), status colour coding, and a right-click context menu. Previous prototype likely used QTableWidget which creates one widget object per cell.

## Decision
Use `QAbstractTableModel` + `QSortFilterProxyModel` for the View Tab loan table. QTableWidget is rejected for this use case.

## Rationale
- QAbstractTableModel + proxy: virtual rendering; only visible rows are rendered
- QSortFilterProxyModel provides sort + filter without duplicating data
- 1500 rows × 10 columns = 15,000 widgets with QTableWidget; noticeable lag on scroll/load
- Model-View separation aligns with Clean Architecture (ViewModel maps DTOs to display data)

## Implementation Notes
- `LoanTableModel(QAbstractTableModel)`: data(), headerData(), flags(), setData()
- `LoanSortFilterProxy(QSortFilterProxyModel)`: filterAcceptsRow() for multi-column filters
- `ColumnFilterWidget`: per-column dropdown; date columns show YYYY→MM hierarchy
- Status column: delegate (`QStyledItemDelegate`) renders QComboBox in-place with colour background

## Consequences
- More boilerplate than QTableWidget (requires custom model class)
- Better performance and scalability
- Easier to unit-test (model is pure Python, no UI dependency)
