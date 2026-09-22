# Milestone Plan — FinHive MVP2

**Date**: 2026-09-08 · **Revision 2** (M1 split · M0 slimmed · encryption added · beautification deferred)
**Status**: FOR REVIEW
**Source**: `linear_import.csv` · 139 issues · 696 points
**Decisions**: `ARB_DECISIONS.md` · `mvp2_ard_v2.2.0.md` (ADR-2.3 encryption)

---

## The governing constraint

> **Business continuity is priority #1.** The MVP1 user validates real business on the
> `development` branch throughout. MVP1 functionality must not be affected.

Enforced mechanically, not by care:

| Mechanism | Where | Effect |
|---|---|---|
| **MVP1 regression gate** | M0, CI | Full MVP1 suite (150 + 22 smoke) on **every** PR, whatever paths changed |
| **MVP1 stays production** | M0 → M4 | Desktop app remains the system of record; the web app is validated alongside it |
| **Local-first M1** | M1a/M1b | Nothing hosted, nothing shared, nothing to break |
| **Parity sweep as a gate** | M1b exit | Persona A ~80 checks must report PARITY HELD |

---

## Milestone flow

```mermaid
flowchart TB
    subgraph BC["🔒 Business continuity — a property, not a phase"]
        direction LR
        BC1["MVP1 desktop remains the system of record"]
        BC2["MVP1 regression gate blocks every breaking PR"]
        BC3["M1 is local-only — nothing hosted can break"]
    end

    START(["Today · MVP1 live on development"]) --> M0

    M0["<b>M0 · Foundation &amp; Agent Toolchain</b><br/>15 issues · 59 pt<br/><br/>repo structure · orchestrator + run_builder<br/>CodeRabbit wired · GitHub Actions<br/>SQL-injection + import-linter gates<br/><b>MVP1 regression gate</b><br/><b>MVP1 multi-month ByMonth</b>"]

    M0 --> G0{{"Gate 0<br/>agents executable · CodeRabbit reviewing<br/>MVP1 suite green on every PR"}}

    G0 --> M11["<b>M1.1 · Ask FinHive</b> — rev 4 · KCH-222..253<br/>32 new · 85 pt  +  4 absorbed · 19 pt  =  36 · 104 pt · ~48 d<br/><br/>① <b>encrypted Postgres on the MVP1 desktop app</b><br/>Docker pgvector · migrations 0001-0005 · AES-256-GCM<br/>blind index · org-scoped · SQLAlchemy sync (D-1a)<br/>② agent — READ/PROPOSE tools · 6-step loop · resolver<br/><b>names + amounts tokenised before egress</b><br/>③ <b>Ask FinHive tab on SEEDED data</b> (row 20)<br/>④ real loans.db migration (row 26) · evals<br/><i>M1a paused after KCH-109</i>"]

    M11 --> G11{{"Gate 1.1<br/><b>no plaintext NPI in the database</b> · egress test: zero names or amounts leave<br/>E1 recall@1 ≥ 0.95 · E4 = 100% · unsafe-call = 0<br/>G-07/G-07b pass · cp.query_loans = 1.0 · faithfulness = 1.0 on E3<br/>real data migrated with a verified field-by-field round-trip"}}

    G11 --> M1A["<b>M1a · Web Shell</b> — rev 4: REDUCED<br/>KCH-101-104, 106-113<br/><br/>asyncpg pool · FastAPI · JWT · GET /api/me<br/>React SPA · login route · Chakra tokens · MDX help<br/><i>encryption + local schema DELIVERED by M1.1</i><br/><i>KCH-107 Supabase Auth: do not build as written</i>"]

    M1A --> G1A{{"Gate 1a<br/>user logs in through the web app<br/>on the same encrypted store M1.1 built"}}

    G1A --> M1B["<b>M1b · MVP1 Parity — Read then Write</b><br/>26 issues · 162 pt<br/><br/>④ read — Loans table, filters, totals<br/>⑤ write — entry, edit, Reports, Approvals<br/>multi-month ByMonth · parity sweep"]

    M1B --> G1B{{"Gate 1b<br/><b>Persona A · PARITY HELD</b><br/>MVP1 user validates business on the web app"}}

    G1B --> M2["<b>M2 · Agent Read-Only</b> — rev 3: PORT<br/>~40% of 140 pt<br/><br/>port application/agent → finhive/agent<br/>async · asyncpg · RLS · decrypt<br/>SSE encoder over TraceEvent · React trace UI<br/>pgvector only if E1 &lt; 0.95 (D-4a)"]

    M2 --> G2{{"Gate 2<br/>grounded answers · evals ≥ 90/85/85<br/>unsafe-call rate = 0"}}

    G2 --> M3["<b>M3 · Agent Write, UI Polish &amp; Hosted Infra</b><br/>20 issues · 96 pt<br/><br/>mutating tools propose, never write<br/>transactional apply · revert · OriginBadge<br/>component inventory · skeletons · empty states<br/>Supabase ap-south-1 · bom1 · RLS · Blob"]

    M3 --> G3{{"Gate 3<br/>zero direct agent writes, proven<br/>RLS isolation passes on hosted"}}

    G3 --> M4["<b>M4 · Multi-User Distribution</b><br/>12 issues · 60 pt<br/><br/>public signup · roles · invitations<br/>production deploy · Grafana · Amplitude<br/><b>collision validation</b> · Bot Readiness"]

    M4 --> G4{{"Gate 4<br/>Bot Readiness = READY<br/>no data or workflow collisions"}}

    G4 --> M5["<b>M5 · Completion &amp; Hardening</b><br/>16 issues · 69 pt<br/><br/>dbt contracts · real dashboard<br/>retention tiering · restore · purge<br/>DueSoon · MDX content"]

    M5 --> DONE(["MVP2 complete"])

    BC -.->|guards| M0 & M11 & M1A & M1B & M2 & M3 & M4

    style BC fill:#0f2e1f,stroke:#3ecf8e,color:#fff
    style M0 fill:#1f1f2e,stroke:#8b7ec8,color:#fff
    style M11 fill:#1a3a52,stroke:#4a9eff,color:#fff
    style G11 fill:#1a3a52,stroke:#4a9eff,color:#fff
    style M1A fill:#3d2914,stroke:#e0a336,color:#fff
    style M1B fill:#3d2914,stroke:#e0a336,color:#fff
    style M2 fill:#1a3a52,stroke:#4a9eff,color:#fff
    style M3 fill:#3d1f2e,stroke:#f472b6,color:#fff
    style M4 fill:#2e1f2e,stroke:#c084fc,color:#fff
    style M5 fill:#1f2e2e,stroke:#3ecf8e,color:#fff
    style G1A fill:#4a3a14,stroke:#e0a336,color:#fff
    style G1B fill:#4a3a14,stroke:#e0a336,color:#fff
```

---

## What changed in revision 4 (2026-09-22)

The Postgres + encryption pivot. M1.1 is no longer a slice on MVP1's SQLite layer —
it builds the encrypted data layer MVP2 keeps, behind the existing desktop UI.

| Change | Effect |
|---|---|
| **Encryption at rest moves M1a → M1.1** (ARB D-15) | Operator requirement: no plaintext at rest. Migrations 0003 + 0004 taken as built. M1.1 is not shippable without it |
| **Local Docker Postgres replaces Supabase** (ARB D-16) | `pgvector/pgvector:pg16`, extension available not enabled. No hosting bill at one user; `CREATE EXTENSION vector` stays one line |
| **SQLAlchemy over Postgres, sync** (ARB D-1a) | D-1's raw-SQL choice was scoped to the MVP2 web backend. Adopting asyncpg here would make every use case async and invalidate 161 tests for no user-visible gain |
| **OQ-01 amended** | Data at rest is now local, so only Groq *inference* crosses a border. Tokenisation survives as the sole control on the one remaining path |
| **M1a reduced to the web shell** | Encryption, local schema and setup are delivered by M1.1. KCH-99, 100, 105, 114 re-milestoned into it |
| **M1.1 issues created** | KCH-222..253, 32 new + 4 absorbed = 36 issues, 85 pt, ~48 d |
| **Test data first** | The tab ships on a seeded encrypted database (row 20); the real `loans.db` migration lands at row 26, after the encryption path has been exercised for weeks |
| **No login screen in M1.1** | One org, one owner, locally generated UUID. A credential check inside a process the user controls protects nobody; M1a's JWT path does it properly for the web |

## What changed in revision 3 (2026-09-21)

| Change | Effect |
|---|---|
| **M1.1 inserted between G0 and M1a** | The MVP2 agent (§11–§14 of ARD v2.0.0) is built as a vertical slice on the MVP1 desktop app first — 23 issues, 31 d — to prove the tool contracts, tokenisation, proposal batch and eval harness on real ledger data before the platform moves. Full model: `docs/MVP1_1_ASK_FINHIVE.md` |
| **M1a paused after KCH-109** | Outstanding M1a (KCH-81, 99, 100–108, 110–114) resumes after G1.1 |
| **M2 re-cut as a port** | `application/agent` → `finhive/agent`: async, asyncpg, RLS, decrypt, SSE encoder, React trace UI. ~40% of the original 140 pt. pgvector (KCH-161) only if E1 recall@1 < 0.95 |
| **LiteLLM → OpenAI-compatible client** (ARB D-4a, proposed) | KCH-153 re-scoped; KCH-169 cost from a price table |
| **Decision 12 binds M1.1** | Names *and* amounts tokenised before any LLM call from day one; the egress test is a G1.1 criterion |
| **KCH-188 / KCH-191 logic lands in M1.1** | Eval gates and feedback loop cross from M3; recorded in ARB D-8 |
| **Two live MVP1 bugs filed** | `ApproveReport` never recomputes `status`; undated-loan extend silently skipped on approve |

## What changed in revision 2

| Change | Effect |
|---|---|
| **M0 slimmed** 27 → **15** issues (101 → 59 pt) | Repo, agents, CodeRabbit, CI gates, regression gate only |
| **M1 split** into M1a (110 pt) + M1b (162 pt) | A checkpoint at 110 pt instead of 264 |
| **Encryption replaces masking at rest** | 4 new tickets, +23 pt — the old approach failed parity check A2.1 |
| **Hosted infra → M3** | Supabase provisioning, RLS, `bom1`, `service_role`, SQLite→hosted migration, Blob |
| **Beautification → M3** | Component inventory (13), skeletons (5), empty states (5) — 23 pt off the parity path |
| **North Star spec → M4** | Belongs with Amplitude instrumentation, not before code |

### M0 · what stayed and what left

**Stayed** — exactly your four concerns: repo structure · developer agents executable (orchestrator, run_builder, pr_gate, agent contract) · CodeRabbit wired · GitHub Actions + SQL-injection + import-linter gates · MVP1 regression gate. Plus MVP1 multi-month ByMonth, which changes the live system and belongs early behind the gate.

**Left** — Supabase provisioning, RLS policies, RLS isolation test, `service_role` restriction, SQLite→Supabase migration, `bom1` pinning, region assertion → **M3**. Local schema work (migration runner, `orgs`/`users`, MVP1 schema) → **M1a**, because the app cannot store a loan without it.

### M1a build order follows your priority

**setup → login → encryption → read → write**

Encryption lands *before* any real data is written. No row is ever stored in plaintext, and there is no backfill.

---

## Exit gates

| Gate | Criteria |
|---|---|
| **G0** | CI green · developer agents run a queued issue end to end · CodeRabbit blocking findings prevent merge · MVP1 suite passes on every PR |
| **G1.1** | **No plaintext NPI in the database, index or WAL** · tampered ciphertext rejected · no blind index on any amount column · **egress test: recorded outbound bodies contain zero fixture names or amounts** · E1 recall@1 ≥ 0.95 · E2 per reconciled threshold · E4 = 100% · unsafe-call = 0 · G-07 and G-07b pass · `cp.query_loans` = 1.0 on every case · faithfulness = 1.00 on E3 · real `loans.db` migrated with a verified field-by-field round-trip · MVP1 suite green, Postgres tests skipping cleanly without a container · agent package imports neither PySide6, SQLAlchemy nor sqlite3 |
| **G1a** | Web app runs locally from one command · MVP1 user logs in through it · reads and writes the **same encrypted store M1.1 built** — no second data layer, no re-encryption |
| **G1b** | **Persona A: PARITY HELD** · Loans, Reports, Approvals fully functional · multi-month ByMonth matches MVP1 · no ❌ in A5 (calculations) or A8 (infrastructure) |
| **G2** | Three canonical queries answered with grounded output · tool-selection ≥ 90%, argument ≥ 85%, completion ≥ 85% · p95 ≤ 4s · **unsafe-call = 0** |
| **G3** | Every mutating tool proposes, never writes · batch apply transactional · agent-class invariant enforced · **RLS isolation passes on hosted** |
| **G4** | Bot Readiness **READY** · second user onboarded with no data or workflow collisions |

---

## Concerns worth your attention

### 1 · One place I did not fully defer the data work

**`org_id` stays NOT NULL on every table from M1a's first migration**, even though RLS is off until M3.

Deferring the *policy* is cheap. Deferring the *column* is not — adding tenancy later means a schema migration plus a backfill across every table, on data the user is actively working in. The column costs nothing now and turns M3's RLS work into adding policies rather than reshaping the schema.

### 2 · How I read "delay all database migrations"

As **defer hosted database work, keep the local schema**. M1a keeps the migration runner, `orgs`/`users` and the MVP1 schema, because M1b cannot read or write a loan without them. Everything Supabase-hosted moved to M3.

If you meant no schema work at all in M1, then M1b collapses to a login screen — say so and I will re-cut again.

### 3 · Encryption interacts with three existing decisions

Detail in ADR-2.3. In short:

- **Cursor pagination (#05)** — a cursor needs a DB-orderable key, and ciphertext is not one. Cursors work on `due_date`, `amount`, `reference_id`, `created_at`; sorting by an encrypted column paginates in the app. Bounded at 1,500 rows.
- **dbt marts (M5)** — cannot `GROUP BY` an encrypted name. Borrower aggregation groups by blind index; the display name is decrypted at read.
- **Agent masking (M2)** — the order becomes ciphertext → decrypt → real name → mask to `PERSON_1` → LLM. Two protections at two boundaries. Never mask ciphertext; never let a decrypted name skip the masker.

### 4 · M3 now carries three unrelated workstreams

Agent-write (9), UI polish (3), hosted infra (8). That is where each was individually placed, and it makes M3 the most crowded milestone after M2. It splits cleanly along those seams if it feels wrong on review — say the word.

### 5 · Three decisions still open

| # | Question | Recommendation |
|---|---|---|
| 09 | Encryption mechanism | **AES-256-GCM + HMAC blind index** (ADR-2.3) |
| 10 | Encrypt group fields too? | **Yes** — a business name identifies a business |
| 05 | Cursor pagination scope | **Non-encrypted sort keys only** |

---

## Import

Row order **is** build order — issues are created top to bottom so Linear numbering runs in milestone sequence. Do not sort the file.

```bash
python3 ops/seed_linear.py --milestone M0
```

Then, per milestone or all at once:

```bash
LINEAR_API_KEY=lin_api_xxx LINEAR_TEAM_KEY=FIN python3 ops/seed_linear.py --apply
```
