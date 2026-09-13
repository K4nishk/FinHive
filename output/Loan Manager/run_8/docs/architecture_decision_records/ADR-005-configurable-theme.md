# ADR-005 — Configurable Theme + Status Colours

**Date**: 2026-06-30
**Status**: Accepted

## Context
User confirmed (CHG-002) that status colours must be configurable, not hardcoded. Default colours are recommendations only. User also wants multiple theme options (at least 2).

## Decision
Implement `ThemeManager` that:
1. Loads a QSS stylesheet file (`dark.qss` / `light.qss`)
2. Loads a companion JSON config (`dark_config.json` / `light_config.json`) containing status colours and other palette values
3. Provides `theme.get_status_colour(status: LoanStatus) -> str` used by all UI components
4. Persists selected theme + colour overrides in `./data/settings.json`

## Theme Config Format
```json
{
  "name": "dark",
  "status_colours": {
    "Active":  {"background": "#025c33", "text": "#FFFFFF", "bold": true},
    "Overdue": {"background": "#6b0307", "text": "#FFFFFF", "bold": true},
    "Pending": {"background": "#804001", "text": "#FFFFFF", "bold": true},
    "Paidoff": {"background": "#022a52", "text": "#FFFFFF", "bold": true}
  }
}
```

## Themes Delivered
- `dark` — dark backgrounds; default colour palette per requirements
- `light` — light backgrounds; adjusted status colour tints for readability

## User Customisation
- Settings Tab exposes colour pickers per status
- Changes saved to `./data/settings.json` (overrides theme defaults)
- Applied immediately without restart

## Consequences
- No hardcoded hex colour strings in any widget or model code
- All colour references go through `ThemeManager.get_status_colour()`
- Settings Tab must call `ThemeManager.apply_theme()` on change
