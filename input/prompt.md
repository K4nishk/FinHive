# LoanManager — Master Build Prompt (Stage-Gated Execution)

You are a senior software architect and implementation agent.

Read:
1. LoanManager.md (authoritative business requirements)
2. prompt.md (this file)

Do not preserve MVP implementation.
Preserve business behaviour.

CRITICAL:
Execution is stage-gated.
Never continue automatically.

After completing a stage:
- STOP
- Produce outputs
- Produce review summary
- Await explicit user response

Allowed user responses:
- PROCEED
- PROCEED WITH MODIFICATIONS

If user chooses PROCEED WITH MODIFICATIONS:
1. Review changes requested.
2. Update ONLY impacted artifacts from previous stage.
3. Revalidate outputs.
4. Reissue review summary.
5. Wait again.

Never advance stages without approval.

---

# Delivery Model

Total stages = 6

Each stage must:
- have deliverables
- have acceptance checklist
- halt execution

Output folder:

docs/
artifacts/
reports/

Maintain:
docs/stage_log.md

Template:

Stage:
Inputs:
Outputs:
Assumptions:
Open Questions:
Review Decision:
Next Stage:

---

# Stage 1 — Discovery + Requirements

Goal:
Convert LoanManager.md into implementable requirements.

Produce:

docs/
├── business_requirements.md
├── assumptions.md
├── risks_and_tradeoffs.md
├── backlog.md
├── open_questions.md

Required:

- extract requirements
- remove ambiguity
- classify MUST/SHOULD/NICE
- identify contradictions
- estimate MVP phases
- identify future-ready capabilities

Deliver:
stage_review.md

STOP.

Await:
PROCEED
or
PROCEED WITH MODIFICATIONS

---

# Stage 2 — Architecture + System Design

Input:
approved Stage 1

Produce:

docs/
├── technical_design_document.md
├── architecture_decision_records/
├── data_model.md
├── migration_strategy.md
├── api_boundaries.md
├── ui_wireframes.md

Requirements:

Architecture:
- Clean Architecture
- Lightweight DDD
- Repository Pattern
- UoW
- DI
- Event-driven workflows

Tech:

Python
PySide6
SQLite
SQLAlchemy
Alembic
Pydantic

Produce:

- component diagrams
- sequence diagrams
- schema
- folder structure

Deliver:
stage_review.md

STOP.

Await review.

---

# Stage 3 — Project Scaffold + Persistence

Input:
approved architecture

Produce:

src/
tests/
migrations/

Implement:

- project structure
- dependency setup
- SQLite
- repositories
- migrations
- logging
- configuration
- startup scripts

No UI.

No business workflows.

Deliver:
build verification

STOP.

Await review.

---

# Stage 4 — Domain + Application

Input:
approved scaffold

Implement:

- loan lifecycle
- status engine
- reference IDs
- calculator
- approvals
- import/export
- recovery

No polish.

Tests mandatory.

Deliver:

coverage
domain diagrams
validation report

STOP.

Await review.

---

# Stage 5 — UI + UX

Input:
approved domain

Implement:

PySide6 UI

Tabs:
- Entry
- View
- Calculator
- Approval
- Settings

Requirements:

- keyboard-first
- spreadsheet UX
- accessibility
- themes

Fix:
date picker interaction bug.

Deliver:

screens
UX review
known limitations

STOP.

Await review.

---

# Stage 6 — Finalization

Input:
approved UI

Implement:

- packaging
- docs
- guides
- export/import
- optimization
- smoke tests

Produce:

README
run_windows.bat
run_mac.sh
user_guides

Finalize:

tests
verification
release notes

Deliver:

FINAL_REVIEW.md

STOP.

Await final signoff.

---

# Global Rules

Never rewrite previous stages unless requested.

Always reuse approved outputs.

Track:

docs/change_log.md

Each modification request:

Change ID
Reason
Impact
Affected Stages

Always estimate:
- token usage
- remaining work
- complexity

Coverage target:
85%

No hidden assumptions.

End.
