# Stage 1 Review — Discovery + Requirements

**Stage**: 1 of 6
**Model**: claude-sonnet-4-6 (Sonnet — planning tier)
**Date**: 2026-06-29
**Status**: COMPLETE — AWAITING APPROVAL

---

## Outputs Produced

| Artifact | Path | Summary |
|---|---|---|
| Business Requirements | docs/business_requirements.md | 10 BRs (BR-01 to BR-10) covering all R1–R10 + UTR1 |
| Assumptions | docs/assumptions.md | 12 documented assumptions (A-01 to A-12) |
| Risks & Tradeoffs | docs/risks_and_tradeoffs.md | 12 risks (R-01 to R-12) with mitigations |
| Backlog | docs/backlog.md | 23 items (BL-01 to BL-23); MUST/SHOULD/NICE classification |
| Open Questions | docs/open_questions.md | 10 items requiring user confirmation |
| Stage Log | docs/stage_log.md | Initialized; will track all stage decisions |

---

## Requirements Classification Summary

| Priority | Count | Items |
|---|---|---|
| MUST | 13 | BL-01 through BL-13 |
| SHOULD | 5 | BL-14 through BL-18 |
| NICE | 56 | BL-19 through BL-24 |

---

## Key Decisions Made

1. **giving_date excluded from calculations** — Authoritative ruling. Extension window only. Previous implementation must be rewritten.
2. **CSV-only storage** — No SQLite for prototype. All data in `./data/`.
3. **Crash safety scoped** — `approval_recovery.tmp` log in scope; full atomic rollback deferred.
4. **History loss on Extend** — Explicitly accepted. No audit trail for overwritten records.
5. **Date picker fix** — MUST fix efore UI delivery. `showCalendarWidget` → `calendarPopup(True)`.
6. **PDF export** — System print dialog (QPrintDialog); styled PDF deferred post-prototype.
7. **Model strategy** — Stages 1–2: Sonnet; Stages 3–5: Opus; Stage 6: Sonnet.

---

## Contradictions / Ambiguities Identified

1. **R3 vs Status Recompute**: Manual status toggles are persisted, but app auto-recomputes on launch and overrides them. Exception: Active override via Extend uses the new due_date for recompute. This means toggling Active without Extend WILL be reverted on next launch. [OQ resolved: this is intended behaviour per spec]

2. **R5 Filter + No-Due-Date**: No filter = show no-due-date records. Any filter = exclude no-due-date records. Combined filter + a record that has no due_date but matches the filter → excluded. [OQ-01]

3. **ByMonth filter definition** includes "Overdue records" but the exact scope (all Overdue, or only those in selected month) is ambiguous. [OQ-02]

---

## Risks Flagged for Stage 2

- **R-07**: QTableWidget performance at 1500 rows — must use QAbstractTableModel + proxy model
- **R-08**: Date picker bug — must be designed correctly from scratch in Stage 5
- **R-11**: Calculator breaking change — all calculation logic and tests written fresh

---

## Estimated Complexity per Stage

| Stage | Complexity | Model | Notes |
|---|---|---|---|
| Stage 2 — Architecture | Medium | Sonnet | Clean Architecture + DDD patterns; no code |
| Stage 3 — Scaffold | Low | Opus | Boilerplate; folder structure, CSV layer |
| Stage 4 — Domain | High | Opus | Calculator, status engine, approval flow, ref_id |
| Stage 5 — UI | High | Opus | PySide6 full UI; date picker fix; inline editing |
| Stage 6 — Finalize | Low | Sonnet | Docs, launchers, smoke tests |

---

## Open Questions Requiring User Input Before Stage 2

The following questions may affect architecture decisions:

- **OQ-02**: ByMonth filter + Overdue scope definition
- **OQ-06**: Windows PDF output mechanism
- **OQ-09**: Theme preferences (light/dark?)

All others are assumed confirmed and noted.

---

## Acceptance Checklist

- [x] All 10 requirements extracted and classified (R1–R10 + UTR1)
- [x] Ambiguities identified and documented (10 open questions)
- [x] Contradictions flagged (3 noted above)
- [x] MUST/SHOULD/NICE classification complete
- [x] MVP phases mapped to stages
- [x] Future-ready capabilities identified (BL-19 to BL-23)
- [x] Risks documented with mitigations
- [x] Assumptions documented
- [x] Stage log initialized

---

## Awaiting Response

Reply with:
- **PROCEED** — to advance to Stage 2 (Architecture + System Design)
- **PROCEED WITH MODIFICATIONS** — to request changes to Stage 1 artifacts before advancing
