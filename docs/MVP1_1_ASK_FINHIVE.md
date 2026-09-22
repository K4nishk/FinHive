# MVP1.1 — Ask FinHive on the MVP1 desktop app

**Status:** plan reviewed 2026-09-21 against `src/`; corrected plan below supersedes
`~/Downloads/plan.md` §10. **Governs:** `FinHive M1.1 · Ask FinHive` (Linear project).
**Doctrines:** Ponytail (lowest rung that holds) · Caveman (dense, exact, honest).

---

## 1. Mental model

> **Revised 2026-09-22 (operator interview).** Encryption at rest became mandatory
> and the database moved to local Docker Postgres. The earlier framing — "a slice
> on MVP1's SQLite layer" — is superseded.

MVP1.1 is **MVP2's agent and MVP2's encrypted data layer, running behind MVP1's
desktop UI.** It is not a prototype on throwaway foundations: the data layer it
builds is the one MVP2 keeps. Only the PySide6 surface is temporary.

It **is**: local Docker Postgres (`pgvector/pgvector:pg16`) with migrations
0001–0005 applied · AES-256-GCM encryption at the repository boundary · HMAC blind
index for exact-match filtering · READ/PROPOSE tool contracts · the six-step
orchestration loop · local entity resolution over a decrypted in-memory index ·
name **and amount** tokenisation · the batch-shaped proposal
(`reports → report_records`) · telemetry on `agent_turns` column names · the eval
harness and the RAGAS-proxy metric trio.

It **is not**: a second data layer, a local HTTP API, a web UI, RBAC, a login
screen, RAG over documents, Supabase, or a change to any MVP1 business rule.

**One-way doors** (decided here, not revisited at M2):

1. **SQLAlchemy over Postgres, sync** — ARB D-1a. Not raw SQL + asyncpg; D-1's
   choice was scoped to the MVP2 web backend, and its four mitigations still bind.
2. **Encryption at rest is mandatory** — ARB D-15. Migrations 0003 + 0004 as built.
   Master key from `FINHIVE_MASTER_KEY` behind `keys.py`, **explicitly interim**.
3. **Local Docker Postgres replaces Supabase** — ARB D-16. pgvector image from day
   one so `CREATE EXTENSION vector` stays a one-line migration.
4. OpenAI-compatible client replaces LiteLLM — ARB D-4a.
5. Amounts *and* known names are tokenised before any LLM call — ARB Decision 12.
   Under D-16 this is the **only** control left on the one path that leaves the
   machine, since data at rest is now local (OQ-01 amended).
6. Proposals are batches; this shape is migration 0006's spec.
7. Null `due_date` stays **Overdue**.

**Sequencing: test data first.** The tab ships against a seeded encrypted database
(build order 20); the real `loans.db` migration lands after it (build order 26).
The encryption and repository paths get exercised for weeks before real data
touches them, and a working tab arrives roughly two weeks sooner.

**Consequences already priced.** `amount_ct` cannot be `SUM()`ed, so totals are
app-layer decrypt-then-aggregate (KCH-105). Ciphertext cannot be pattern-matched,
so fuzzy borrower matching leaves SQL entirely and becomes `EntityResolver`. Every
repository query becomes org-scoped, because retrofitting `org_id` after data
exists is far worse than carrying it now.

**Effect on MVP2:** M1a's encryption and local-schema scope is *delivered* by M1.1,
not deferred — KCH-99, KCH-100, KCH-105 and KCH-114 are re-milestoned into it. What
remains in M1a is genuinely web-only: the asyncpg pool, FastAPI, JWT, and React
(KCH-101–104, 106–113). M2 becomes "port `application/agent` to `finhive/agent`",
~40% of its original estimate.

---

## 2. Why the plan needed correcting

The plan was authored from `input/REQUIREMENTS.md:170` — *"Database is not needed
in the prototype … `.csv` for history maintenance is good enough"* — not from
`src/`. That document describes the MVP1 *spec*; run_8 superseded it (WIKI §16
CHG-001, CSV → SQLite + SQLAlchemy). Every false premise traces to that one
source. **Rule going forward: MVP1.1 is specified against `src/Loan Manager/`,
never against `input/`.**

### 2.1 Premises that are false

| Plan claim | Reality | Consequence |
|---|---|---|
| A1 "MVP1 is Python + CSV" | `infrastructure/database/models.py:17-33` SQLAlchemy `DeclarativeBase`; `csv_to_sqlite.py` is a one-time BL-24 migration | D2, FIN-101, FIN-102 rebuild what exists; `store.py` would be a second write path to `loans` |
| §2.3 "MVP1 writes `1970-01-01`" | `grep -rn 1970 loan_manager/` → 0; `due_date` nullable; live DB 0 epoch rows | Nothing to backfill |
| §2.3 null `due_date` → Pending | `status_engine.py:22-23` → OVERDUE; `REQUIREMENTS.md:162` "Assume that it is overdue"; CLAUDE.md authoritative; 2 tests pin it | Reverses a rule the operator set explicitly; hides undated loans from "what's overdue" |
| §2.3 `paid_off_at` column | Does not exist. Paidoff = `is_active=False` + `loan_history.paidoff_date` | §2.4 DDL is a schema fork |
| §1.2 "`depositor_group` is MVP2" | `models.py:25`, nullable, filterable (`ilike` at repo `:88-91`) | `resolve_entity` must index all four name fields |
| §2.4 integer paise | `money.py` int rupees; `interest_calculator.py` `Decimal` `ROUND_HALF_UP` | Changes the stored unit of every amount for no benefit |
| §11.3 "3 deps added" | pydantic present; fastapi never enters the desktop venv | Net new: `openai` (or 0) |
| §6.2 frozen clock reuses tests | `date.today()` unpatched in 6 use cases; `_pin_today` exists in one test module | Clock port on `Container` is a prerequisite |
| §5.4 FTS5 policy corpus | Only text is `user_guides/*` + `docs/*`, ~2,700 words of install docs | Indexes nothing; 15× under the plan's own trigger |
| `finhive.toml` | `tomllib` is 3.11+; Python floor is 3.10 | JSON in `data/settings.json` |
| Alembic "one migration" | Declared `requirements.txt:3`, no `alembic.ini`/`env.py`/`versions/`; schema is `create_all` | Bootstrap + stamp first (0.5d) |

### 2.2 Decisions that stand

D3 explicit loop · D5 projection (with amounts tokenised) · D6 agent never writes ·
D7 trace evals · D4 no vector store (live DB: 19 loans, 17 borrowers) · §5.2 "never
silently fall back to substring" (**the live failure mode** — `get_all_active`
uses `ilike('%bg1%')` and matches `bg13`) · §3.3 Groq quirks · §3.4 HF "designed-for,
not proven" · §4.4 turn-based trimming · §7.1 untrusted-data delimiting · §11.2
"$0.24/month, anyone presenting this as a win is selling something".

Genuinely absent and needed: audit/actor/provenance columns, per-batch undo
(`BackupService` is whole-file copy), INR formatter (`grep ₹` → 0),
`get_current_context`, a create-loan proposal path, input guardrails.

### 2.3 Live MVP1 bugs the agent would expose (file as their own KCH issues)

- **Stale status after batch approve.** `ApproveReport` → `bulk_update_dates`
  writes only `giving_date/due_date/updated_at`; `status` is recomputed only at
  launch (`main.py:45-47`). `query_loans(status='overdue')` reading the column
  returns a just-extended loan as overdue. Agent tools must derive status via
  `StatusEngine` at read; fix the use case regardless.
- **Silent skip on undated extend.** An extend proposal on a null-`due_date` loan
  → `calculate_interest.py:57-62` → `None` → `approve_report.py:86` skips it.
  The agent would say "3 extended" when 2 were. Extend proposals on undated loans
  require an explicit `new_due_date` or are rejected (G-07b).
- **Pydantic `extra='ignore'`.** Reproduced: `giving_date` passed to a tool arg
  model is dropped silently and the call succeeds. Every tool model gets
  `ConfigDict(extra='forbid')`; an eval asserts no schema property contains
  "date" except where the tool needs one.

---

## 3. Conflicts with authority

| Authority | Plan | Resolution | Sign-off |
|---|---|---|---|
| CLAUDE.md "No raw SQL outside migrations"; ARB D-1 raw SQL is scoped to **MVP2 Postgres** with 4 mitigations | `store.py` hand SQL on SQLite | Zero raw SQL. Tools → use cases → `ILoanRepository`. Add `exact: bool` to `get_all_active` | no |
| ARB D-4 Groq via LiteLLM (approved) | D1 bare OpenAI SDK | **D-4a** (below) | **yes** |
| ARB Decision 12 tokenise amounts (approved 2026-09-08) | §5.3 sends `total_amount: 185000` raw | Tokenise names *and* amounts from day one. Side effect: faithfulness becomes exact set membership; G-19 is structurally unviolable | **yes** |
| ARB OQ-01 cross-border: a Groq turn is a transfer unless personal data never leaves | §7.2 typed prompt "scrubbed only for account-number patterns" — a typed "sharma" crosses in clear | Ingress pass: run the difflib resolver over the prompt **before** the first LLM call, substitute `B001`/`G002`. Egress eval: recorded outbound bodies contain zero fixture names/amounts | **yes** (D-8) |
| Null `due_date` → Overdue | → Pending | Keep. `query_loans` returns `days_overdue=None` for undated, includes them in the overdue **count**, never in a days sum, flags "no due date agreed" | no |
| `giving_date` never in interest inputs | silent | `extra='forbid'` + schema eval | no |
| Python ≥ 3.10 | `tomllib` | JSON config | no |

---

## 4. Where each component lands

| Component | Layer / path | Reuses | Verdict |
|---|---|---|---|
| `store.py` | — | `sqlalchemy_loan_repo.py`, `unit_of_work.py` | **cut** |
| LLM client | `infrastructure/llm/openai_compat_client.py` | `data/settings.json['llm']`, `.env` | keep; **only** importer of `openai`; recorded fake beside it |
| Tool arg models + registry | `application/agent/tools/`, `tool_registry.py` | pydantic | keep; `extra='forbid'`; READ/PROPOSE mode; ast guard test |
| `query_loans` | `application/agent/tools/query_loans.py` | `GetAllLoans`, `get_all_active(exact=True)`, `StatusEngine.compute(…, today)` | projection `{count, total_amount, overdue, overdue_undated, ref_ids[], max_days_overdue\|None}` |
| `resolve_entity` | `domain/services/entity_resolver.py` | `GetAutocompleteValues` × 4 allowlisted fields | keep; also the ingress pre-step |
| `calculate_interest` | `application/agent/tools/` | `InterestCalculator.calculate` | 20-line wrapper; Decimal as string |
| `get_portfolio_summary` | same | `GetAllLoans` + ranking | **add** (KCH-155 lists it) |
| `get_current_context` | `domain/services/` | Clock port on `Container` | keep |
| FastAPI + SSE + token + Origin | — | — | **cut** |
| Orchestration loop | `application/use_cases/agent/run_agent_turn.py` | `Container`; `emit: Callable[[TraceEvent], None]` | keep; `TraceEvent` = KCH-157 vocabulary |
| Tokeniser | `application/agent/tokeniser.py` | resolver's dict | keep; names + amounts |
| Proposals | `models.py` + a numbered SQL migration (0006) — **not Alembic**, which is dropped | `reports`/`report_records` + `actor`, `user_request`, `turn_id` | **reuse the existing batch**; `report_records` needs `borrower_group`, `due_period`, nullable `reference_id/giving_date` for CREATE |
| Approvals tab | `presentation/tabs/pending_approval_tab.py` | existing | extend; AGENT/FORM badge |
| Ask FinHive tab | `presentation/tabs/ask_finhive_tab.py`, `workers/agent_worker.py`, `widgets/trace_model.py` | `LoanTableModel.load()`, `ThemeManager` | keep — throwaway by design |
| Telemetry | `AgentConversationModel`/`AgentTurnModel` | 0005 `agent_turns` names | keep + `prompt_version, step_count, finish_reason, eval_scores` |
| FTS5 + `Retriever` | — | — | **cut**; WIKI §3 rules (~400 tokens) inlined in the system prompt |

**In-process, not loopback HTTP.** `RunAgentTurn` on a `QThread`, trace steps as
`Signal(object)` carrying Pydantic `TraceEvent`. What HTTP would have bought:
process isolation, a curl-able endpoint, and "the same transport as MVP2" — the
last is false (MVP2 routes are async + JWT + asyncpg, `/api/agent/stream` not
`/api/agent/chat`). What it costs: fastapi + uvicorn in the desktop venv, child
lifecycle, and the DNS-rebind/CSRF/bearer/port-0 surface §4.1 creates and then
mitigates. What ports to MVP2: `TraceEvent` + tool models + `RunAgentTurn`; an SSE
encoder over them is ~20 lines. Required with the QThread: `PRAGMA
journal_mode=WAL` via an engine connect listener (current mode is `delete`).

---

## 5. Port-forward contract

Everything below **must import neither PySide6, SQLAlchemy nor sqlite3**. Enforced
by an ast guard test in 1.1 and import-linter at M2 (root `pyproject.toml` lints
`finhive` only today — `loan_manager` is never linted).

- Tool Pydantic arg models + generated JSON schemas
- `TraceEvent` models (KCH-157 vocabulary: thought / action / observation / proposal / final)
- System prompt + its content hash (`finhive.prompt_version`)
- `EntityResolver`
- `RunAgentTurn` (behind a `LoanReadPort` Protocol)
- Tokeniser
- `grounding.py` (fact extraction + faithfulness)
- Golden cases (JSONL) + fixture rows
- Metric names + `baseline.json`
- `agent_turns` column names (0005 + the 0006 additions)

**Throwaway by design ≈ 7d:** Ask FinHive tab 3.5, PendingApprovalTab extension
1.5, Qt worker bridge 0.5, SQLAlchemy models for turns/proposal columns 1, Alembic
bootstrap 0.5. Honest framing: the original plan carried ~6d throwaway (two tabs)
**plus 14.5d of zero-value rebuild**; this revision removes the 14.5d and adds ~1d.

---

## 6. Metrics: `context_precision`, `faithfulness`, `answer_relevancy`

Scope stated out loud: with FTS5 cut there is no document retrieval. "Retrieved
context" = tool returns — `query_loans`' ref_id set (unranked SQL) and
`resolve_entity`'s ranked candidates. Every context item is labelled by the
fixture, so two of the three reduce to exact checks. The stored numbers are
**proxies with definitions that differ from RAGAS**; store them as `*_proxy` or
document the definition beside the column so KCH-188 thresholds are not read as
RAGAS-comparable.

### context_precision

- **Definition.** Fraction of items each retrieval tool put into context that
  belong to the golden set; rank-weighted where the tool ranks.
- **Formula.** `cp.query_loans = |R ∩ G| / |R|` — R = ∪ ref_ids across the turn's
  `query_loans` calls; G from `gen_expected.py` via ORM + `StatusEngine` +
  injected `today`. `|R|=|G|=0 → 1.0`; `|R|=0, |G|>0 → 0.0`.
  `cp.resolve_entity = AP@k`; single golden → `1/rank`; ambiguous (G-23) →
  `|top2 ∩ G_e| / 2`. Turn = min over calls (gate), mean (trend). Also
  `context_recall = |R ∩ G| / |G|`.
- **Threshold.** `cp.query_loans = 1.0` on every case — it is a deterministic
  path; `< 1` means wrong args or a filter bug, never prose variance.
  `cp.resolve_entity` = seed-fixture value committed to `tests/evals/baseline.json`,
  ratcheted up. E1 recall@1 ≥ 0.95 stays.
- **Telemetry.** `finhive.eval.context_precision` (min), `.context_precision.mean`,
  `.context_recall`, `.cp.query_loans`, `.cp.resolve_entity`.
- **Suite.** E1 (≡ `cp.resolve_entity@1`), E2. **Catches:** G-07 undated ref_id
  one layer before prose; G-23 rank-1 wrong entity → 0.5; substring over-match
  (fixture adds `bg10` beside `bg1`).
- **Judge fallback.** RAGAS `LLMContextPrecisionWithoutReference`, nightly only,
  production turns, trend not gate.

### faithfulness

- **Definition.** Every typed fact in the model's **raw, pre-rehydration** final
  message is present in this turn's context.
- **Formula.** `faithfulness = |F_a ∩ F_c| / |F_a|`. `F_a` = ref_ids
  (`\b\d{4}_\d{2}_\d{3,}\b`), `AMOUNT_n` / `B00n` / `G00n` tokens, dates (ISO +
  `d Mon yyyy`), counts (`\d+ loans?`), rates (`\d+%`), entity-dictionary hits.
  `F_c` = tool returns (JSON walk) ∪ tokens issued ∪ facts in the user prompt ∪
  `get_current_context`. `F_a = ∅ → 1.0` with `fact_count=0` flagged.
  **Hard check `raw_money_leak`:** any `₹?\d[\d,]{3,}` in raw model text, in or
  out, fails the case — Decision 12 makes this structural.
- **Threshold.** `1.00` on E3 (arithmetic/money — policy). Other suites = min of 3
  seed runs on `llama-3.1-8b-instant`, ratcheted; pre-release on the 70b = `1.00`.
- **Telemetry.** `finhive.eval.faithfulness`, `.faithfulness.unsupported` (JSON
  list of failed facts — the actionable part), `.fact_count`. Production per turn:
  `finhive.turn.faithfulness`, `.fact_count`, `.unsupported` on `agent_turns`.
- **Suite.** E3 (generalises it), E4, G-19, G-07. **Catches:** ₹350 stated where
  the tool returned 300.00; an undated loan's amount summed into an overdue total
  the tool did not return; a mis-transcribed ref_id.
- **Judge fallback.** Nightly claim-level RAGAS faithfulness on the production
  model, stored separately as `faithfulness_llm ≥ 0.90`, trend.

### answer_relevancy

- **Definition.** No deterministic equivalent for prose topicality exists. What
  *is* measurable: did the agent work on the right question — **trace relevancy**.
- **Formula.** Per case `focus: {entity, metric, period}`. `entity_match` = slug
  passed to `query_loans` ∈ `focus.entity`; `metric_match` = ≥1 answer fact traces
  to a tool field ∈ `focus.metric`; `period_match` = date args ⊆ `focus.period`,
  or `get_current_context` called for relative periods. `proxy = mean(3)`.
  `wrong_entity` = any answer fact traced to a tool return for an entity ∉
  `focus.entity` → **hard fail**. `capability_gap` = `metric_match=0 ∧
  faithfulness=1.0` — the honest "tool missing" signal.
- **Judge.** Nightly only: `llama-3.1-8b-instant`, rubric "does A answer Q?
  yes/no + one line", temp 0.1, N=1, `FINHIVE_EVAL_JUDGE=0` default, PR CI never
  sets it. ~6k tokens/night. **Written trigger to enable:** over any 50 production
  turns, ≥3 thumbs-down triaged "answered a different question" where
  `proxy=1.0 ∧ wrong_entity=false`. True RAGAS (embeddings) only if the rubric
  proves noisy.
- **Threshold.** `wrong_entity = 0` on E1/E2; proxy baseline ratchet; judge
  ≥ 0.85 trend, no gate.
- **Telemetry.** `finhive.eval.answer_relevancy.proxy`, `.wrong_entity`,
  `.capability_gap`, `.answer_relevancy.judge` (nullable), `finhive.eval.judge.model`.
  Production signal = thumbs rate per `prompt_version` + proposal reject rate
  (KCH-191).
- **Suite.** E2/E3 via the `focus` field. **Catches:** G-23 model picks depositor
  Meera Iyer for "iyer" — third independent detector.

### Implementation

`loan_manager/application/agent/grounding.py`: `extract_facts(text) -> set[Fact]`,
`faithfulness(answer, tool_returns, tokens, prompt) -> (float, list[Fact])`, 100%
unit-tested (Indian grouping, lakh/crore, three date formats, ref_id boundary),
shared with production. `tests/evals/`: `cases/*.jsonl` with fields `id, suite,
question, frozen_today, expected_trace, expected_ref_ids, expected_entity{slug |
ambiguous[]}, expected_facts, focus{}, must_not_call`; `fixture.py` (15 existing
rows + undated-with-giving≤today, future-giving, `iyer chem` / `meera iyer`,
`bg10`); `gen_expected.py`; `metrics.py`; `baseline.json`; markers `eval / llm /
judge` in `pytest.ini`. **CI:** PR lane = recorded traces, zero network, must
auto-skip when `GROQ_API_KEY` is unset because `mvp1-regression` runs all of
`src/Loan Manager/tests/` as a required check; nightly = live 8b + optional judge.
Assert faithfulness on raw tokenised output; assert task completion on the
rehydrated render (ARD v2.0.0:971 `answer_contains: ['1,85,000']` predates
Decision 12 — rewrite in KCH-166).

---

## 7. Corrected execution plan

**Single source of truth: `output/Loan Manager/mvp1.1/linear_import.csv`**,
generated by `python3 ops/gen_m11_csv.py`. Row order is build order and is never
re-sorted. The table below is a summary; if the two disagree, the CSV wins.

Project `FinHive M1.1 · Ask FinHive`. Labels `product:finhive` first, then
workstream. Import with the `write-linear-issue` skill via `ops/seed_linear.py`.

| Phase | Rows | Pts | Delivers |
|---|---|---|---|
| **0 · Postgres data layer** | 1–11 | 27 | Docker pgvector, model port, migrations 0001–0005, master key, encryption at the boundary, seeded org+owner, blind index, test split, dev fixture, queue rebuild |
| **1 · Agent core → working tab** | 12–20 | 27 | Clock port + status bug, LLM client, tool registry, `EntityResolver`, READ tools, tokeniser, `RunAgentTurn`, telemetry, **Ask FinHive tab** |
| **2 · Mutation safety** | 21–25 | 12 | Report batch as proposal, PROPOSE tools, undo, approvals tab, guardrails |
| **3 · Real data** | 26 | 3 | `loans.db` → encrypted Postgres, verified round-trip |
| **4 · Evals** | 27–32 | 16 | Fixture + harness, suites E1–E5, metric trio, CI lanes, spike, feedback loop |
| | **32 new** | **85** | |

Plus **4 absorbed, re-milestoned not recreated** — they keep their own points from
`mvp2/linear_import.csv`: KCH-99 (amount-index CI rule, 3), KCH-100 (lift the domain
layer, 3), KCH-105 (decrypt-and-sort, 8), KCH-114 (prove encryption at rest, 5) =
**19 pt**. **M1.1 total: 36 issues, 104 points, ~48 days.**

**Critical path:** 2 → 3 → 4 → 6 → 10 → 16 → 18 → 20. No agent work starts before
the encrypted data layer exists.

**A working tab arrives at row 20, not row 26** — it runs on the seeded fixture,
and the real-data migration follows. Deliberate: the encryption and repository
paths are exercised for weeks before real loan data touches them.

Separate KCH bugs filed outside M1.1: `ApproveReport` stale status; 0005 → 0006
(`batch_id`, nullable `created_by`); `pending_approval_tab.py` QTableWidget debt;
`ILoanHistoryRepository` has no read method; four application→infrastructure
imports; `run_local_*` Supabase assumptions; KCH-107 "Supabase Auth flow" must not
be built as written.

### FIN → KCH

| FIN | Status | Note |
|---|---|---|
| 101, 102, 103, 114 | REDUNDANT | exists in `src/` |
| 104, 105 | REJECTED | reverse a rule / change a unit; keep `format_inr` 0.25d |
| 116, 117, 138 | CUT | HTTP, SSE, FTS5 |
| 110 | SUBSUMES KCH-153 | retitle per D-4a |
| 111, 112, 113 | OVERLAPS KCH-154/155 | 113 gates KCH-161 (pgvector) on E1 |
| 115 | SUBSUMES KCH-156/150/152 | async port remains for M2 |
| 120 | OVERLAPS KCH-98 | becomes 0006's spec |
| 121 | SUBSUMES KCH-186 | |
| 122, 123, 125 | REUSE / OVERLAPS KCH-179/180/124 | |
| 132 | SUBSUMES KCH-144/146 | |
| 133, 134 | OVERLAPS KCH-169 | |
| 135, 136, 137 | SUBSUMES KCH-165/166/188/191 | 188/191 are M3 — crossing milestones, recorded in D-8 |
| 118, 124, 130, 131 | NEW | 118/124 throwaway; 131 has no MVP2 equivalent (queue gap) |
| 140, 141 | OUT OF SCOPE | dev-loop; separate ops issue |

**Queue.** New CSV `output/Loan Manager/mvp1.1/linear_import.csv`; do not insert
into `mvp2/linear_import.csv` (never-re-sort rule). `ops/seed_linear.py:204` sorts
by KCH number so new ids land behind M5 — change `write_queue` to sort by
`(project_rank, number)` with rank `[M0, M1.1, M1a, M1b, M2, M3, M4, M5]`.
Re-milestone existing rows to M1.1 rather than duplicating: KCH-144, 146, 153,
154, 155, 156, 162, 164, 165, 166, 169, 186, 188, 191. KCH-100 "Lift MVP1 domain
layer unchanged" collides with adding `entity_resolver.py` — sequence it.
