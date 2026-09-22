# ARB Decision Log — FinHive Loan Manager MVP2

**Status**: LIVE — this is the authoritative record. ARD `§24` (v2.0.0) and `§10` (v2.1.0) are superseded by this file where they disagree.
**Last updated**: 2026-09-07

---

## Architecture decisions — APPROVED 2026-09-07

All seven from ARD v2.0.0 §24, approved without modification.

| ID | Decision | Status |
|---|---|---|
| D-1 | Raw SQL instead of an ORM, with the four mandated mitigations | ✅ APPROVED |
| D-2 | Agent mutations always require human approval | ✅ APPROVED |
| D-3 | Modular monolith, not microservices; boundaries CI-enforced | ✅ APPROVED |
| D-4 | Groq as primary LLM via LiteLLM | ✅ APPROVED |
| D-5 | PII masking (not full anonymisation), scope stated honestly | ✅ APPROVED |
| D-6 | Vercel platform coupling (Blob, Analytics) | ✅ APPROVED |
| D-7 | dbt in CI rather than at runtime | ✅ APPROVED |

D-1's approval is conditional on its mitigations shipping *with* the data layer, not after it: parameterised-only rule, CI grep gate, query-shape contract tests, N+1 count assertions. If those slip, D-1 reverts to an open decision.

---

## OQ-01 · Data residency → **India (`ap-south-1`)**

**Decision**: All primary data resides in India. Supabase project region `ap-south-1` (Mumbai).

This is the decision with the largest blast radius of the three. Four consequences, in order of how easily they get missed.

### 1. Vercel functions must be pinned to `bom1` — this is the one that bites

Supabase in Mumbai with serverless functions defaulting to `iad1` (Washington) puts a ~200–250 ms round trip on **every database query**. A request making four queries pays a second of latency before any work happens, and at 3 DAU most requests are already cold.

```json
// vercel.json
{ "regions": ["bom1"] }
```

Pin it in Phase 1, before anyone measures performance and concludes the raw-SQL layer is slow. Add a startup assertion that logs the function region and the database region together, so a mismatch is visible rather than inferred from a latency chart.

### 2. PII masking is now a compliance control, not just hygiene

Groq has no India region. Inference happens in the US, which means an agent turn is a **cross-border transfer of personal data** unless the personal data never leaves.

Under the DPDP Act 2023, cross-border transfer is permitted except to countries on a government-notified restricted list; the US is not currently on it. So this is legal today. But the posture matters: with masking working, no borrower name or account identifier crosses the border at all — only `PERSON_1`, amounts, and dates.

That reclassifies ARD v2.0.0 §13 from a good practice to **the control that keeps personal data inside India**, with three follow-on obligations:

- The e2e check `C1.11` (masked outbound / rehydrated inbound) becomes a compliance test, not a hygiene test. It fails the build; it does not warn.
- Every **new field** carrying a name or identifier must be added to `MASKED_FIELDS`. A field added without masking is a cross-border disclosure. Add a test that fails when a model gains a string field not explicitly classified as maskable or non-maskable.
- The honest limitation in §13 stands and must stay in the doc: masking is not anonymisation, and a distinctive amount-plus-date pair can still be re-identifying. Do not upgrade the claim just because the stakes rose.

If a customer ever requires no cross-border transfer at all, the answer is a self-hosted model — which the LiteLLM abstraction (D-4) keeps as a config change.

### 3. Third-party processors are still US-based

Grafana Cloud, Amplitude and Vercel Analytics all process outside India.

- **Amplitude** must carry no PII whatsoever (already `C1.10`). With that held, it processes behavioural events, not personal data.
- **Grafana** receives logs and traces. Log redaction is now load-bearing — a correlation ID is fine, a borrower name in a log line is a transfer. Add a log-scrubbing filter and a test.
- **Vercel Analytics** is cookieless and collects no personal data.

### 4. Latency to the user improves

An incidental benefit: SMB users in India now hit Mumbai rather than the US. The p95 target of ≤ 4s for an agent turn gets easier, not harder — the only US round trip left is Groq inference, which is the fast part.

**Backlog impact**: 4 tickets — region pinning, region assertion, log scrubbing, maskable-field classification test.

---

## OQ-02 · Audit retention → **7 years**

**Decision**: `proposed_mutations`, `agent_turns`, `reports` and `report_records` are retained for 7 years from creation.

This supersedes the 24-month recommendation in ARD v2.1.0 §10. Seven years is a regulatory-grade horizon consistent with Indian statutory bookkeeping periods, and it changes retention from a config value into an architectural requirement.

### Why 24 months was the wrong recommendation

I recommended 24 months on storage-growth grounds. That was the wrong axis. These tables hold the evidence of *who approved what change to a financial record*, and a retention period shorter than the statutory life of the underlying books makes the audit trail useless exactly when someone needs it.

### What 7 years requires that 24 months did not

**Tiered storage, because Postgres is the wrong home for year six.**

| Tier | Age | Where | Access |
|---|---|---|---|
| Hot | 0–12 months | Postgres, queryable | Normal app queries |
| Cold | 12 months – 7 years | Compressed JSONL in Blob, partitioned by month | Restore-on-demand |
| Purge | > 7 years | Deleted | — |

`proposed_mutations` stores full `before_state` and `after_state` JSONB per record per batch. It is the fastest-growing table in the system, and it grows without bound under an indefinite policy. Archival keeps the hot table small enough that the approvals queue stays fast in year five.

**A tested restore path.** Retention without retrieval is not retention. An archive nobody has restored from is a folder of files you *believe* contain something. The restore procedure gets a test that runs quarterly in CI against a synthetic archive.

**An index that survives archival.** A pointer table stays in Postgres for the full 7 years: `(batch_id, reference_id, operation, decided_by, decided_at, archive_path)`. So "who extended this loan in 2027" is answerable without restoring anything — only the full before/after payload needs a restore.

**An actual deletion job.** Without one, 7 years becomes indefinite by neglect, which is a different (and in privacy terms, worse) policy than the one being approved. The purge job is part of the decision, not a later cleanup.

**Backups are not the retention mechanism.** Supabase PITR is 7 days. It is a recovery tool. Conflating the two is how organisations discover in year four that they have 7 days of history.

### The tension worth writing down now

DPDP grants data principals a right to erasure. Statutory retention overrides that right for the retention period — but only for the records the statute covers.

Consequence: an erasure request must **not** be honoured by deleting rows from `proposed_mutations` or `report_records` inside the 7-year window. It also must not be silently ignored. The correct handling is documented refusal-with-reason, plus deletion of anything outside the statutory scope (agent chat transcripts, for instance, are arguably not books of account).

Nobody has asked yet. Write it down before someone does, while it is a design note rather than an incident.

**Backlog impact**: 5 tickets — tiering job, archive index table, restore procedure + quarterly test, purge job, erasure-request handling doc.

---

## OQ-03 · Agent authority ceiling → **viewer may invoke read-only tools**

**Decision**: A `viewer` may use the agent, restricted to the 7 read-only tools. Mutating tools remain `bookkeeper` and above.

Matches the ARD v2.1.0 §10 recommendation. No change to the design.

| Role | Tools | Can propose | Can approve |
|---|---|---|---|
| `viewer` | 7 read-only | ✗ | ✗ |
| `bookkeeper` | all 11 | ✓ | ✗ |
| `owner` | all 11 | ✓ | ✓ |

The `Composer` stays present for viewers. It is `RoleGate`-aware only in that a viewer's turn can never produce a `proposal` event — enforced by `required_role` on the `@tool` decorator, server-side, not by hiding the input.

Two things this makes true that are worth keeping:

- A viewer asking *"what's overdue?"* is the cheapest demonstration of the product's value, and the one most likely to convert a sceptical bookkeeper.
- Because a viewer's tool set is a strict subset, the role becomes a natural test fixture: any turn that produces a proposal under a viewer JWT is a `C7`/`unsafe-call` failure with an unambiguous cause.

---

## Design decisions — APPROVED 2026-09-08

| # | Decision | Outcome |
|---|---|---|
| 02 | Optimistic concurrency on inline edit | ✅ `If-Match` + `409` |
| 03 | Report async threshold | ✅ 100 records, frozen as a constant + fixture boundary |
| 04 | `revert` as a first-class endpoint | ✅ Yes — and **not** an agent tool |
| **05** | **Cursor pagination scope** | ✅ **Cursor on non-encrypted sort keys only.** With amounts now encrypted (§ below), that leaves `due_date`, `reference_id`, `created_at`. Encrypted-column sorts paginate in the app. |
| **08** | **`DueSoon`** | ✅ **Derived, never persisted.** `StatusEngine` keeps returning four values; a CHECK constraint blocks a `DueSoon` write. |
| **09** | **Encryption mechanism** | ✅ **AES-256-GCM + HMAC blind index, app-side sort** (ADR-2.3). Rejected: pgcrypto, full-disk-only, GCM-alone, deterministic-alone. |
| **10** | **Encryption scope** | ✅ **Expanded to all NPI** — see below |
| **11** | Blind index truncation | ✅ 16 bytes |
| — | `org_id` NOT NULL from M1a | ✅ Column stays even though RLS defers to M3 |
| — | "Delay database migrations" | ✅ Defer hosted work, keep the local schema |
| — | Encryption constraints on #05, dbt, agent masking | ✅ All accepted |

### OQ-04 · Encryption scope → **all NPI, not just identity**

**Decision**: extend encryption at rest from names and groups to **all financial values** — principal, interest, commission, TDS, CHQ, and rates — plus the JSONB audit snapshots that contain them.

**Basis**: a voluntary adoption of the GLBA/PIPEDA treatment of Nonpublic Personal Information, under which any information resulting from a transaction — loan balances, approved amounts, transaction terms — is protected.

> **State this accurately in the ARB submission.** GLBA binds US financial institutions; FinHive's users are Indian SMBs, so it does not legally apply. This is a *stricter-than-required baseline chosen deliberately*, which is a strength. Claiming a mandate that does not exist would be a finding.

Full scope, mechanism and consequences: **`mvp2_ard_v2.3.0.md` ADR-2.4**. Four things follow:

1. **No blind index on any amount — ever.** Loan amounts cluster on round numbers (₹10,000, ₹15,000, ₹20,000). A deterministic index over that distribution is reversible by frequency analysis without the key. Order-preserving encryption is worse — it leaks the full ranking. Amounts get randomised AES-GCM and no derived index. This belongs in the coding standards, not only in the ADR.
2. **dbt loses financial aggregation**, including the SQL assertion of MVP1's interest formula. Financial marts move to an app-layer materialization job. The "two independent enforcers" property from v2.0.0 is genuinely weakened; property-based testing narrows the gap without closing it.
3. **`amount >= 0` moves from a DB CHECK to the `Money` value object**, which becomes the sole guard and needs a test to match its new importance.
4. **Amounts to the LLM is now an open question** — see below.

---

## Encryption decisions — APPROVED 2026-09-08

| # | Question | Outcome |
|---|---|---|
| **12** | Amounts to the LLM | ✅ **Tokenise.** `₹45,000` → `AMOUNT_1`, rehydrated on the way out, exactly as names work. Tools decrypt and compute; **the agent narrates results it did not calculate**. Known cost: questions needing magnitude reasoning the tools did not pre-compute are unanswerable until a tool is added, and will surface as eval failures resembling capability gaps. |
| **13** | Encrypt `interest_rate` / `commission_rate`? | ✅ **No** — a percentage is not a balance and identifies no one. Derivation check below. |
| **14** | Encrypt `due_period` / `extension_period`? | ✅ **No** — small integers needed for date arithmetic and range queries. |
| — | NPI protection status | ✅ **Mandatory** — mandated by FinHive engineering policy, scope taken from GLBA/PIPEDA |
| — | dbt role shrink | ✅ Accepted |
| — | No derived index on amounts | ✅ **Hard rule** — CI-enforced and in the coding standards |

### Wording for the ARB submission

The obligation is mandatory and non-negotiable. Only the *wording* needs precision:

> GLBA binds US financial institutions; PIPEDA binds Canadian organisations. FinHive's current users are Indian SMBs, so neither statute reaches them today. The obligation is **self-imposed, internally binding, and a prerequisite for US or Canadian market entry**, where it becomes statutory.
>
> Write **"FinHive mandates GLBA-equivalent NPI protection."** True, binding, and a strength in front of a board.
> Not **"GLBA requires us to."** Checkable, false today — and disproving one claim invites scrutiny of every other claim in the document.

Nothing about the implementation changes. Everything in ADR-2.4 is mandatory either way.

### Derivation check — why plaintext rates are safe

`interest = (amount × rate × period) / 1200`. An attacker holding the database has `rate`, `period` and dates in plaintext; `amount` and every computed amount are ciphertext. Recovering `amount` needs **two** of the three terms and they have one. `tds` and `chq` derive from encrypted values and add nothing. **No solve path exists.**

A rate column leaks the *distribution of terms* across the book — that some loans carry 12% and others 18%. Commercially mild, identifies nobody. Acceptable.

> **Re-run this check before adding any plaintext column carrying a derived financial value.** A `total_repayable` helper in plaintext would immediately open a path back to `amount`. Encrypt new financial columns by default; make exceptions only after redoing this analysis.

---

## MVP1.1 pull-forward — PROPOSED 2026-09-21, awaiting approval

Raised by the MVP1.1 plan review (`docs/MVP1_1_ASK_FINHIVE.md`). The plan pulls
the Ask FinHive agent and the proposal path forward onto the MVP1 desktop app,
ahead of M1a. Two approved decisions are affected and one new scope decision is
needed. **Nothing has been built on either side of D-4** (`grep -rn litellm\|openai
src/ finhive/` → 0), so the cost of D-4a is governance only.

| # | Decision | Status |
|---|---|---|
| D-4a | LLM transport is an OpenAI-compatible client; LiteLLM not adopted | ⏳ PROPOSED |
| D-8 | MVP1.1 scope binds D-2, Decision 12 and OQ-01 from day one | ⏳ PROPOSED |
| D-1a | MVP1.1 uses SQLAlchemy over Postgres, sync — not raw SQL + asyncpg | ⏳ PROPOSED |
| D-15 | Encryption at rest is mandatory **in MVP1.1**, not deferred to M1a | ⏳ PROPOSED |
| D-16 | Local Docker Postgres (`pgvector/pgvector:pg16`) replaces Supabase for M1.1 | ⏳ PROPOSED |
| D-12 (existing) | Binds MVP1.1. Supersedes the OQ-01 line "amounts cross" (`:47`) | ⏳ confirm |
| OQ-01 | **Amended** — data at rest is now local; only inference crosses | ⏳ PROPOSED |

### D-1a — amends D-1 for the MVP1.1 runtime

D-1 chose raw SQL over an ORM for the **MVP2 web backend**, with four mitigations.
MVP1.1 is the existing PySide6 desktop app, so it uses **SQLAlchemy 2.0 against
Postgres, synchronously**.

Adopting `finhive/`'s raw-SQL + asyncpg stack here would make every use case async,
force the Qt worker to host an event loop, and invalidate 161 passing tests — for
no user-visible gain on a single-user desktop app. D-1's reasoning was about a
hosted multi-tenant API; it does not transfer to this runtime.

**D-1's four mitigations still bind**, restated for the ORM: parameterised-only
(SQLAlchemy Core/ORM constructs, never string-built SQL), the CI grep gate stays,
query-shape contract tests stay, N+1 count assertions stay.

Consequence accepted: `loan_manager/` (SQLAlchemy) and `finhive/` (raw SQL) coexist
until the MVP2 port. That is two data-access styles in one repo — tolerable only
because the boundary is a whole application, not a layer, and because MVP1.1's
port-forward contract keeps `application/agent/` free of both.

### D-15 — encryption at rest is mandatory in MVP1.1

The operator's requirement: data cannot be left plaintext at rest. Encryption moves
from M1a into M1.1, and MVP1.1 is not shippable without it.

Scope is exactly what migrations 0003 and 0004 already implement — no new crypto
design. That is **nine columns**, across `loans`, `loan_history` **and**
`report_records`:

| | Columns |
|---|---|
| Identity | `borrower_name`, `borrower_group`, `depositor_name`, `depositor_group` |
| Principal | `amount` |
| **Derived financial** | `interest_amount`, `commission_amount`, `tds_amount`, `chq_amount` |

All become `_ct BYTEA` with `key_version`; identity columns additionally get an HMAC
blind index. Applied at the repository boundary only — three repositories touch
encrypted tables (loan, history, report) and must be done together, since 0003 makes
those columns `NOT NULL`.

**The derived four are not optional.** `interest_rate` and `extension_period` stay
plaintext by Decisions 13 and 14, so a plaintext `interest_amount` solves for the
principal: `amount = interest × 1200 / (rate × months)`. Leaving any one of them in
clear re-opens the path ADR-2.4 closed, and is exactly the case the derivation check
at the end of this document exists to catch.

**Master key location is INTERIM.** `FINHIVE_MASTER_KEY` from `ops/.env.local`,
behind `keys.py`. Stated plainly: the key sits beside the ciphertext, so this
defends a stolen backup or a synced folder and **not** an attacker with read access
to the home directory. Written trigger to move to the OS keychain: a second user,
any hosted deployment, or the database file leaving this machine.

Consequence, already priced: `amount_ct` cannot be `SUM()`ed, so every total is
app-layer decrypt-then-aggregate (KCH-105). Ciphertext cannot be pattern-matched,
so fuzzy borrower matching leaves SQL and becomes `EntityResolver` over an
in-memory decrypted index.

### D-16 — local Docker Postgres replaces Supabase for MVP1.1

`pgvector/pgvector:pg16` in `docker-compose.yml`, extension available but not
enabled. Reasons: no hosting bill at single-user scale, no Supabase dependency, and
`CREATE EXTENSION vector` stays a one-line migration if retrieval ever needs it.

Follows: `seed_service_account.py` is de-Supabased (locally generated owner UUID,
no `SUPABASE_SERVICE_ROLE_KEY`); `run_local_mac.sh:146-159` and the Windows script
stop assuming the Supabase CLI on port 54322; **KCH-107 "Implement Supabase Auth
flow in React" must not be built as written**. No login screen in M1.1 — a
credential check inside a process the user fully controls protects nobody.

### OQ-01 amended — the transfer is now inference-only

OQ-01 recorded that Groq has no India region, so an agent turn is a cross-border
transfer unless personal data never leaves, and pointed at Supabase `ap-south-1`
for residency.

Under D-16 the database is local, so **data at rest no longer crosses a border at
all** and the `ap-south-1` provisioning is moot for M1.1. What remains is Groq
**inference**. Tokenisation is therefore still mandatory — for a narrower and more
precise reason than the ARB previously recorded: it is the only control left on the
one path that still leaves the machine.

### D-4a — amends D-4's transport clause

LLM transport for MVP1.1 and, unless M2 shows a need only LiteLLM meets, for MVP2
is an OpenAI-compatible `/v1/chat/completions` client configured by `base_url`,
`model`, `api_key_env`. LiteLLM is not adopted.

**D-4 intent preserved:** Groq primary; provider swap is config. The self-hosted
exit that OQ-01 relies on survives as `base_url` + server launch flags + model
family: vLLM requires `--enable-auto-tool-choice --tool-call-parser <family>`;
Ollama's `/v1` supports `tools` only on tool-capable tags. Transport portability
is config; **tool-call fidelity is per-server and is verified, not assumed** — the
spike (M1.1 issue 18) must pass suite E2 against Groq and one non-Groq target
before D-4 is marked superseded.

**Cost accepted:** provider quirks (plan §3.3) and the price table (JSON,
hash-versioned as `finhive.eval.price_version`) become FinHive-maintained,
replacing `litellm.completion_cost`. Per-tool model routing (ARD Gotcha 5) is a
`model` argument on `complete()`.

**Queue effects:** re-scope KCH-153 → "OpenAI-compatible client, ported to
`AsyncOpenAI`/httpx at M2"; KCH-169 cost source → price table; KCH-155's
"resolve_entity is RAG-backed" → stdlib difflib in 1.1, and E1 recall@1 ≥ 0.95 on
the seed fixture **cancels** KCH-161 (pgvector), < 0.95 reinstates it. Client
library choice is coupled to the M2 port — `openai` SDK now → `AsyncOpenAI` free
later; `urllib` now → rewrite to httpx at M2 — decide once, in the client issue.

### D-8 — MVP1.1 scope

MVP1.1 binds D-2 (human approval), Decision 12 (tokenised amounts) and OQ-01
(no personal data leaves) from day one:

- Amounts **and** known entity names are tokenised before any LLM call. The
  user's typed prompt is passed through the local resolver *before* the first
  model call and known names are substituted — a typed "sharma" must not cross
  to a US endpoint in clear. Egress eval: recorded outbound bodies contain zero
  fixture names or amounts.
- Proposals are batches. MVP1.1 reuses `reports → report_records`; this shape is
  the spec for migration 0006 (0005 as merged cannot apply unchanged:
  `organizations` vs `orgs`, `loan_id UUID` vs `BIGINT`, no `batch_id`).
- Null `due_date` stays **Overdue** (`REQUIREMENTS.md:162`, `status_engine.py:22`).
  The plan's §2.3 reversal is rejected; the hazard is handled in `query_loans`
  (`days_overdue=None`, excluded from day sums, included in the count).
- Deliberate queue reorder: M1.1 ahead of remaining M1a (KCH-81, 99, 100–108,
  110–114). KCH-188 and KCH-191 are M3 today; their logic lands in M1.1 —
  recorded here as a milestone crossing.

### Open until approved

- D-4a — evidence required: spike passes E2 on Groq + one non-Groq target.
- D-8 — operator sign-off on the queue reorder.
  > **D-8's original second clause is superseded by D-15.** It read: "binding
  > Decision 12 to a desktop app that has no encryption at rest — the tokeniser
  > protects egress only; `loans.db` stays plaintext until M1a." That is no longer
  > true and must not be approved as written. Under D-15 MVP1.1 encrypts at rest,
  > and the tokeniser is the **egress** control rather than the only control.
- D-8's M1a list is likewise pre-pivot. "Remaining M1a" is now KCH-81, 101–104,
  106–113. KCH-99, 100, 105 and 114 are re-milestoned into M1.1.

---

## Change history

| Date | Change |
|---|---|
| 2026-09-07 | D-1 … D-7 approved. OQ-01 India / `ap-south-1`. OQ-02 7-year retention (supersedes 24-month recommendation). OQ-03 viewer read-only agent. |
| 2026-09-08 | Decisions 02–05, 08–11 approved. OQ-04 encryption scope expanded to all NPI. Decisions 12–14: tokenise amounts to the LLM; rates and periods stay plaintext. NPI protection confirmed mandatory under FinHive policy. All architectural decisions closed. |
| 2026-09-21 | **Reopened.** MVP1.1 pull-forward proposed D-4a (OpenAI-compatible client, no LiteLLM) and D-8 (M1.1 scope: tokenise names + amounts from day one, proposals as batches, null due_date stays Overdue, M1.1 ahead of M1a). Decision 12 confirmed binding on MVP1.1. Awaiting approval. |
| 2026-09-22 | **Postgres pivot.** Operator interview added D-1a (SQLAlchemy over Postgres, sync — D-1's raw-SQL choice scoped to the MVP2 web backend), D-15 (encryption at rest mandatory in M1.1; master key interim in env), D-16 (local Docker `pgvector/pgvector:pg16` replaces Supabase). OQ-01 amended: data at rest is local, so only Groq inference crosses. M1a's encryption and schema scope absorbed into M1.1; KCH-99/100/105/114 re-milestoned. Awaiting approval. |
