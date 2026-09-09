# Architecture Reference Document — FinHive Loan Manager MVP2

**Version**: 2.0.0
**Status**: DRAFT — Submitted for ARB Review
**Date**: 2026-09-07
**Author**: Principal Engineer / Solution Architect
**Supersedes**: MVP1 ARD (`output/Loan Manager/run_8/ARD.md`)
**Audience**: Architecture Review Board (approval), Junior Engineers (implementation)

---

## Versioning Convention

| Version | Meaning | Example trigger |
|---|---|---|
| `vN.0.0` | New MVP generation; architecture-defining | MVP1 desktop → MVP2 web+agent |
| `v2.x.0` | Additive capability inside MVP2 | Adding a new bounded service |
| `v2.0.x` | Correction, clarification, ARB feedback | ARB asks for a deeper rollback plan |

This document is `v2.0.0` — the baseline ARB submission. ARB feedback lands as `v2.0.1`.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Why MVP2 Exists](#2-why-mvp2-exists)
3. [Scale Reality Check](#3-scale-reality-check)
4. [System Context](#4-system-context)
5. [Service Decomposition](#5-service-decomposition)
6. [Tech Stack — What Each Piece Owns](#6-tech-stack--what-each-piece-owns)
7. [Deployment Topology](#7-deployment-topology)
8. [Authentication & Authorization](#8-authentication--authorization)
9. [Data Layer — Raw SQL + Supabase](#9-data-layer--raw-sql--supabase)
10. [dbt Data Contracts](#10-dbt-data-contracts)
11. [The ReAct Agent](#11-the-react-agent)
12. [Agent Safety — The Mutation Approval Gate](#12-agent-safety--the-mutation-approval-gate)
13. [PII Masking Pipeline](#13-pii-masking-pipeline)
14. [LLM Observability, Cost & Evaluation](#14-llm-observability-cost--evaluation)
15. [Frontend Architecture](#15-frontend-architecture)
16. [Observability & Analytics](#16-observability--analytics)
17. [CI/CD Pipeline & Quality Gates](#17-cicd-pipeline--quality-gates)
18. [The Agentic Development Loop](#18-the-agentic-development-loop)
19. [Migration Strategy — MVP1 to MVP2](#19-migration-strategy--mvp1-to-mvp2)
20. [Tradeoffs & Gotchas](#20-tradeoffs--gotchas)
21. [Risk Register](#21-risk-register)
22. [North Star Metrics](#22-north-star-metrics)
23. [Phased Delivery Plan](#23-phased-delivery-plan)
24. [ARB Decision Log](#24-arb-decision-log)

---

## 1. Executive Summary

MVP1 delivered a **single-user PySide6 desktop application** with a clean four-layer domain model, 150 tests, and 89% coverage. It works. It is also unshippable to the actual target market: SMB owners and bookkeepers who will not install a Python desktop app.

MVP2 keeps the domain layer — the part that encodes real business value — and replaces everything around it:

| Layer | MVP1 | MVP2 |
|---|---|---|
| Presentation | PySide6 desktop | React + Chakra UI (web) |
| Interaction | Forms and tables only | Forms, tables, **and a ReAct agent chat** |
| API | None (direct in-process calls) | FastAPI (REST + SSE) |
| Persistence | SQLite + SQLAlchemy ORM | Supabase Postgres + **raw SQL** |
| Auth | None (single user) | Supabase Auth + Row Level Security |
| Deploy | `.bat` / `.sh` scripts | Vercel (CI/CD from GitHub) |
| Observability | Rotating log file | Grafana + Amplitude + Vercel Analytics |
| Data contracts | Pydantic DTOs only | Pydantic **+ dbt schema tests** |

**The centerpiece**: a Groq-backed ReAct agent that performs real loan operations — not a search box with a chat skin. It reasons, calls typed tools, and routes every mutation through a human approval gate that reuses MVP1's existing Pending Approval pattern.

**Golden rule applied**: *"Do not let a technically challenging solution be the reason for rejection."* Where this document picks the harder path — raw SQL over an ORM, a real ReAct loop over prompt-chaining, streaming over polling — it pairs that choice with an explicit mitigation so the ARB is approving a *managed* risk, not an unbounded one.

---

## 2. Why MVP2 Exists

### The user problem (unchanged from MVP1, better understood)

SMB owners track loans across multiple spreadsheets — monthly, quarterly, and yearly schedules scattered across files. No single view. No audit trail. Manual updates that silently drift.

### What MVP1 solved

Correctness. The interest engine, status engine, reference ID generation, and approval workflow are right, tested, and deterministic.

### What MVP1 did not solve

| Gap | Consequence |
|---|---|
| Desktop-only | Bookkeeper on a different machine cannot see the data |
| Single-user | No delegation; owner and bookkeeper cannot share |
| Form-driven only | Every question requires knowing which filter to click |
| No remote access | Data shared over git — unacceptable for non-technical users |
| No analytics | We cannot tell which features earn their keep |

### The MVP2 thesis

> A bookkeeper should be able to type *"what's due this quarter for the Sharma group?"* and get a correct, auditable answer in under three seconds — and be able to say *"extend all of those by one month"* and have a human-approvable change set land in the queue.

Everything in this architecture serves that sentence.

---

## 3. Scale Reality Check

**Target load: 10 registered users, 3 daily active users.**

This is deliberately stated up front because it disqualifies a large amount of architecture that would otherwise look impressive and be wrong.

| Not doing | Why |
|---|---|
| Kubernetes | 3 DAU. Vercel serverless is correct and free-tier viable. |
| Message queues (Kafka/SQS) | No throughput problem exists. Direct calls + a DB-backed job row is sufficient. |
| Read replicas / sharding | Dataset is ~1,500 rows per tenant. |
| Redis cache | Postgres at this size answers in single-digit ms. Caching would add a staleness bug class for zero gain. |
| True microservices (separate deploys, separate DBs) | Distributed-systems failure modes with none of the benefits. |
| Vector DB (Pinecone/Weaviate) | `pgvector` inside the existing Supabase Postgres. One less system. |

**What we build instead**: a **modular monolith with enforced service boundaries**, deployed as Vercel serverless functions. The boundaries are real — enforced by import-linting in CI — so any module *can* be extracted later. None are extracted now.

> **ARB talking point**: The engineering maturity signal here is not "can you build microservices." It is "can you correctly identify that you should not, and still leave the seams in place."

---

## 4. System Context

```mermaid
graph TB
    subgraph users["Users"]
        OWNER["SMB Owner<br/>(approves changes)"]
        BOOK["Bookkeeper<br/>(daily operations)"]
    end

    subgraph vercel["Vercel Platform"]
        WEB["React SPA<br/>Chakra UI"]
        API["FastAPI<br/>Python Serverless"]
        BLOB["Vercel Blob<br/>report PDFs, imports"]
        VA["Vercel Analytics<br/>web vitals"]
    end

    subgraph supabase["Supabase"]
        AUTH["Supabase Auth<br/>JWT + RLS"]
        PG[("Postgres<br/>+ pgvector")]
    end

    subgraph external["External Services"]
        GROQ["Groq<br/>LPU inference"]
        GRAF["Grafana Cloud<br/>metrics, logs, traces"]
        AMP["Amplitude<br/>product analytics"]
    end

    subgraph pipeline["Data Pipeline"]
        DBT["dbt Core<br/>contracts + tests"]
    end

    OWNER --> WEB
    BOOK --> WEB
    WEB -->|"JWT"| AUTH
    WEB -->|"REST + SSE"| API
    WEB --> VA
    WEB -->|"events"| AMP

    API -->|"verify JWT"| AUTH
    API -->|"raw SQL<br/>user JWT forwarded"| PG
    API -->|"LiteLLM"| GROQ
    API -->|"signed upload"| BLOB
    API -->|"OTLP"| GRAF
    API -->|"server events"| AMP

    DBT -->|"models + tests"| PG

    style users fill:#1a3a52,stroke:#4a9eff,color:#fff
    style vercel fill:#1f1f2e,stroke:#8b7ec8,color:#fff
    style supabase fill:#0f2e1f,stroke:#3ecf8e,color:#fff
    style external fill:#3d2914,stroke:#ff9f45,color:#fff
    style pipeline fill:#2e1f2e,stroke:#e879f9,color:#fff
```

### Trust boundaries

| Boundary | Crossing mechanism | Control |
|---|---|---|
| Browser → API | HTTPS + Supabase JWT in `Authorization` header | JWT signature verification on every request |
| API → Postgres | Postgres connection with user JWT forwarded | Row Level Security enforced per-tenant |
| API → Groq | HTTPS to LiteLLM → Groq | **PII masked before egress** (§13) |
| Agent → Database writes | Never direct | Proposal → approval queue → applied (§12) |

---

## 5. Service Decomposition

Six logical services. One repository. One deployment unit per Vercel function bundle.

```mermaid
graph LR
    subgraph edge["Edge"]
        BFF["<b>bff</b><br/>routing, auth,<br/>rate limit, SSE"]
    end

    subgraph core["Core Domain — ported from MVP1"]
        LOAN["<b>loan-service</b><br/>CRUD, status engine,<br/>reference IDs"]
        CALC["<b>calc-service</b><br/>interest, commission,<br/>TDS, CHQ"]
        RPT["<b>report-service</b><br/>generation, approval,<br/>PDF export"]
    end

    subgraph intelligence["Intelligence"]
        AGENT["<b>agent-service</b><br/>ReAct loop, tool registry,<br/>PII masking, cost meter"]
        RETR["<b>retrieval-service</b><br/>pgvector, schema RAG,<br/>intent routing"]
    end

    BFF --> LOAN
    BFF --> CALC
    BFF --> RPT
    BFF --> AGENT
    AGENT --> RETR
    AGENT -.->|"typed tool calls<br/>(reads execute,<br/>writes propose)"| LOAN
    AGENT -.-> CALC
    AGENT -.-> RPT

    style edge fill:#1a3a52,stroke:#4a9eff,color:#fff
    style core fill:#0f2e1f,stroke:#3ecf8e,color:#fff
    style intelligence fill:#3d2914,stroke:#ff9f45,color:#fff
```

### Responsibilities

| Service | Owns | Never does |
|---|---|---|
| **bff** | HTTP routing, JWT verification, rate limiting, SSE transport, request correlation IDs | Business logic, SQL |
| **loan-service** | Loan CRUD, status engine, reference ID generation, extend/paidoff lifecycle | LLM calls, HTTP concerns |
| **calc-service** | Interest, commission, TDS, CHQ. **Pure functions.** | I/O of any kind |
| **report-service** | Report generation, the approval queue, PDF rendering, Blob upload | Direct loan mutation outside an approved report |
| **agent-service** | ReAct loop, tool dispatch, PII masking, token/cost metering, retries | Direct SQL, direct writes |
| **retrieval-service** | pgvector embeddings over schema + business rules, intent routing | Mutations |

### How the boundary is *enforced* (not just documented)

```python
# pyproject.toml — import-linter contract, runs in CI
[tool.importlinter]
root_package = "finhive"

[[tool.importlinter.contracts]]
name = "calc-service is pure"
type = "forbidden"
source_modules = ["finhive.calc"]
forbidden_modules = ["finhive.db", "finhive.agent", "httpx", "asyncpg"]

[[tool.importlinter.contracts]]
name = "agent never touches SQL directly"
type = "forbidden"
source_modules = ["finhive.agent"]
forbidden_modules = ["asyncpg", "finhive.db.raw"]
```

If a junior engineer imports `asyncpg` inside `calc-service`, **CI fails**. The architecture diagram and the codebase cannot drift apart.

---

## 6. Tech Stack — What Each Piece Owns

| Layer | Choice | Owns | Chosen over | Because |
|---|---|---|---|---|
| Frontend | **React 18** | UI state, routing, optimistic updates | Next.js App Router | We need a pure SPA; the API is separately deployed FastAPI. Next.js would tempt us into a second backend. |
| Styling | **Chakra UI** | Design tokens, a11y primitives, dark/light | Tailwind, MUI | Accessible-by-default components. MVP1 already established themeable status colours — Chakra's token system maps 1:1. |
| Backend | **FastAPI** | HTTP, validation, OpenAPI, SSE | Flask, Django | Pydantic-native (MVP1's DTOs port with near-zero change), async-first, auto-generated OpenAPI feeds the agent's tool schema. |
| Hosting | **Vercel** | Build, deploy, CDN, preview envs | Fly.io, Railway | Preview deployment per PR is the single highest-leverage CI feature for this project. Python runtime supported. |
| Database | **Supabase Postgres** | Persistence, RLS, pgvector | Neon, RDS | Auth + Postgres + vector in one product. At 3 DAU, operational simplicity beats best-of-breed. |
| Data access | **Raw SQL** (`asyncpg`) | Queries, migrations | SQLAlchemy | See ADR-2.2 below. Deliberate, and deliberately mitigated. |
| Auth | **Supabase Auth** | Signup, login, JWT issuance, session | Auth0, Clerk | Native RLS integration — the JWT *is* the authorization context at the row level. |
| Blob | **Vercel Blob** | Report PDFs, CSV/XLSX uploads | S3 | Same platform, signed-URL uploads bypass the serverless body-size limit. |
| APM | **Grafana Cloud** | Metrics, logs, traces, alerts | Datadog | Free tier is genuinely sufficient at this scale; OTLP-native. |
| Product analytics | **Amplitude** | Funnels, retention, feature adoption | Mixpanel | North Star metric instrumentation (§22). |
| Web analytics | **Vercel Analytics** | Core Web Vitals, page performance | GA4 | Zero-config, no cookie banner, no PII. |
| LLM | **Groq** via **LiteLLM** | Inference | OpenAI direct | Groq LPU latency (~10x faster tokens/sec) is what makes a *multi-step* ReAct loop feel instant. LiteLLM keeps the provider swappable. |
| Content | **MDX** | Help docs, changelog, onboarding | Headless CMS | Content lives in git, reviewed in PRs, versioned with the code. |
| CI/CD | **GitHub Actions** | Tests, gates, deploys | CircleCI | Free for public repos; native CodeRabbit integration. |

### ADR-2.2 — Raw SQL over an ORM

**Status**: Accepted (with mandatory mitigations)

**Context**: MVP1 uses SQLAlchemy 2.x. MVP2 specifies raw SQL.

**Decision**: Raw parameterized SQL via `asyncpg`, in a thin repository layer that preserves MVP1's `ILoanRepository` interface.

**Why this is defensible**:
- Supabase RLS policies are the real authorization layer. An ORM abstracts away the session/JWT binding that RLS depends on, making the security model harder to audit.
- The query surface is small and known (~25 queries). ORM leverage is lowest exactly here.
- Explicit SQL is directly reviewable by CodeRabbit and by humans.

**Why this is dangerous, and what we do about it**:

| Risk | Mitigation | Enforced by |
|---|---|---|
| SQL injection | **Only** `asyncpg` numbered parameters (`$1`, `$2`). Never f-strings in SQL. | `ruff` custom rule + CodeRabbit + CI grep gate |
| No migration autogeneration | Numbered SQL migration files, forward-only, applied via CI | `migrations/NNNN_name.sql` + checksum table |
| Type drift between DB and Python | `pytest` contract tests assert every query's result shape against Pydantic models | CI test suite |
| N+1 queries | Every list endpoint has an explicit query-count assertion test | CI test suite |

**The repository interface does not change from MVP1.** Domain code cannot tell the difference. That is the point.

---

## 7. Deployment Topology

```mermaid
graph TB
    subgraph github["GitHub"]
        MAIN["main<br/>(production)"]
        DEV["development<br/>(stacked-PR base)"]
        FEAT["feature/xx-N"]
    end

    subgraph vercelenv["Vercel Environments"]
        PROD["Production<br/>finhive.app"]
        STAGE["Preview: development<br/>staging.finhive.app"]
        PREV["Preview: per-PR<br/>pr-N.vercel.app"]
    end

    subgraph sbenv["Supabase Projects"]
        SBPROD[("finhive-prod")]
        SBSTAGE[("finhive-staging")]
        SBBRANCH[("branch DB<br/>ephemeral")]
    end

    FEAT -->|"PR opened"| PREV
    FEAT -->|"merge"| DEV
    DEV --> STAGE
    DEV -->|"release PR"| MAIN
    MAIN --> PROD

    PREV -.-> SBBRANCH
    STAGE -.-> SBSTAGE
    PROD -.-> SBPROD

    style github fill:#1f1f2e,stroke:#8b7ec8,color:#fff
    style vercelenv fill:#1a3a52,stroke:#4a9eff,color:#fff
    style sbenv fill:#0f2e1f,stroke:#3ecf8e,color:#fff
```

### Serverless function bundles

Vercel splits the FastAPI app by route prefix. Each becomes an independently cold-starting function:

| Function | Routes | Timeout | Notes |
|---|---|---|---|
| `api/loans` | `/api/loans/*` | 15s | Hot path; keep dependencies minimal |
| `api/reports` | `/api/reports/*` | 60s | PDF rendering is the slow part |
| `api/agent` | `/api/agent/*` | 300s | **SSE streaming**; see gotcha below |
| `api/admin` | `/api/admin/*` | 30s | Migrations, health, dbt trigger |

> ### ⚠️ Gotcha 1 — Serverless timeouts vs. the ReAct loop
>
> A ReAct loop with 4 tool calls at ~800ms each plus 3 LLM round-trips can exceed 30 seconds. Vercel Hobby caps at 60s; Pro with Fluid Compute reaches 300s.
>
> **Mitigation (three layers)**:
> 1. **Stream immediately.** SSE emits the first `thought` token within ~400ms. The connection stays warm and the user sees progress. Perceived latency is what matters.
> 2. **Hard-cap the loop** at `MAX_STEPS = 6`. On exhaustion, return partial results plus a "refine your question" prompt — never a timeout error.
> 3. **Escape hatch for long work.** Report generation over >100 records writes a `job` row and returns `202 Accepted`; the client polls. This path is built in Phase 3, not deferred to "later".

> ### ⚠️ Gotcha 2 — Cold starts on Python serverless
>
> A FastAPI bundle importing pandas/numpy can cold-start in 3–5s. At 3 DAU, **most requests are cold**.
>
> **Mitigation**: Aggressive dependency discipline (no pandas in the request path — dbt owns aggregation), lazy imports for heavy modules, and a Vercel Cron ping every 5 minutes during business hours to keep the `agent` and `loans` bundles warm. Cost: negligible. Benefit: the demo does not stutter.

---

## 8. Authentication & Authorization

```mermaid
sequenceDiagram
    autonumber
    participant U as Browser
    participant SA as Supabase Auth
    participant API as FastAPI
    participant PG as Postgres (RLS)

    U->>SA: signInWithPassword(email, pw)
    SA-->>U: access_token (JWT, 1h) + refresh_token

    U->>API: GET /api/loans<br/>Authorization: Bearer JWT
    API->>API: verify JWT signature (JWKS, cached)
    Note over API: extract sub → user_id<br/>extract org_id claim

    API->>PG: SET LOCAL request.jwt.claims = '{...}'
    API->>PG: SELECT * FROM loans
    Note over PG: RLS policy filters<br/>WHERE org_id = claim.org_id
    PG-->>API: only this org's rows
    API-->>U: 200 + loans

    U->>API: GET /api/loans (expired JWT)
    API-->>U: 401
    U->>SA: refresh
    SA-->>U: new access_token
```

### Row Level Security — the actual policy

```sql
ALTER TABLE loans ENABLE ROW LEVEL SECURITY;

CREATE POLICY loans_tenant_isolation ON loans
  FOR ALL
  USING (org_id = (current_setting('request.jwt.claims', true)::jsonb ->> 'org_id')::uuid);

-- Bookkeepers read and propose; only owners approve.
CREATE POLICY reports_approve_owner_only ON reports
  FOR UPDATE
  USING (
    org_id = (current_setting('request.jwt.claims', true)::jsonb ->> 'org_id')::uuid
    AND (current_setting('request.jwt.claims', true)::jsonb ->> 'role') = 'owner'
  );
```

> ### ⚠️ Gotcha 3 — The service-role key silently disables all of this
>
> Supabase issues an `anon` key and a `service_role` key. **`service_role` bypasses RLS entirely.** The convenient thing — connecting FastAPI with `service_role` — deletes your entire authorization model while every test still passes.
>
> **Mitigation**:
> - `service_role` is available in exactly one place: the migration runner in `api/admin`, guarded by an env var absent from all other bundles.
> - A CI test asserts that a JWT for Org A **cannot** read Org B's rows. This test runs against a real ephemeral Supabase branch, not a mock.
> - A `ruff` rule bans importing the service-role client outside `finhive/db/admin.py`.

### Roles

| Role | Read loans | Create/edit loans | Run agent | Approve mutations |
|---|---|---|---|---|
| `owner` | ✅ | ✅ | ✅ | ✅ |
| `bookkeeper` | ✅ | ✅ | ✅ | ❌ |
| `viewer` | ✅ | ❌ | ✅ (read-only tools) | ❌ |

---

## 9. Data Layer — Raw SQL + Supabase

### Schema evolution from MVP1

MVP1's six tables carry over, plus multi-tenancy and agent tables:

```mermaid
erDiagram
    ORGS ||--o{ USERS : "has"
    ORGS ||--o{ LOANS : "owns"
    ORGS ||--o{ REPORTS : "owns"
    LOANS ||--o{ LOAN_HISTORY : "archives to"
    REPORTS ||--o{ REPORT_RECORDS : "contains"
    ORGS ||--o{ AGENT_SESSIONS : "owns"
    AGENT_SESSIONS ||--o{ AGENT_TURNS : "contains"
    AGENT_TURNS ||--o{ PROPOSED_MUTATIONS : "may produce"
    PROPOSED_MUTATIONS }o--|| LOANS : "targets"

    ORGS {
        uuid id PK
        text name
        timestamptz created_at
    }
    USERS {
        uuid id PK
        uuid org_id FK
        text role "owner|bookkeeper|viewer"
    }
    LOANS {
        bigint id PK
        uuid org_id FK
        text reference_id UK
        text borrower_name
        bigint amount
        date giving_date
        date due_date
        text status
        boolean is_active
    }
    AGENT_TURNS {
        uuid id PK
        uuid session_id FK
        text user_message
        jsonb react_trace
        int prompt_tokens
        int completion_tokens
        numeric cost_usd
        int latency_ms
        text feedback "up|down|null"
    }
    PROPOSED_MUTATIONS {
        uuid id PK
        uuid turn_id FK
        text operation
        jsonb before_state
        jsonb after_state
        text status "pending|approved|rejected"
    }
```

### New tables in MVP2

| Table | Purpose |
|---|---|
| `orgs` | Tenant root. Every business table gains `org_id`. |
| `users` | Maps Supabase `auth.users` → org + role. |
| `agent_sessions` | One conversation thread. |
| `agent_turns` | One user message + agent response. **Stores the full ReAct trace, token counts, cost, latency, and feedback.** This table is the observability and eval substrate. |
| `proposed_mutations` | Agent-proposed writes awaiting approval. Holds `before_state` and `after_state` as JSONB for exact diff rendering and rollback. |
| `schema_embeddings` | `pgvector` store for schema + business-rule RAG. |

### The repository layer

```python
# finhive/db/loan_repository.py
from typing import Optional
import asyncpg
from finhive.domain.entities.loan import Loan
from finhive.domain.repositories.loan_repository import ILoanRepository

_SELECT_BY_REF = """
    SELECT id, org_id, reference_id, borrower_name, borrower_group,
           depositor_name, depositor_group, amount, giving_date,
           due_period, due_date, status, is_active, created_at, updated_at
    FROM loans
    WHERE reference_id = $1 AND is_active = true
"""


class PostgresLoanRepository(ILoanRepository):
    """Implements the MVP1 domain interface. Domain code is unchanged."""

    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def get_by_reference_id(self, reference_id: str) -> Optional[Loan]:
        row = await self._conn.fetchrow(_SELECT_BY_REF, reference_id)
        return _row_to_loan(row) if row else None
```

Three properties to notice, junior engineer:

1. **The SQL is a module-level constant.** Reviewable in isolation, greppable, and impossible to accidentally build with string concatenation.
2. **`$1` is a real bind parameter.** `asyncpg` sends it separately from the query text. There is no injection surface.
3. **The class implements MVP1's interface.** Every domain test written against `ILoanRepository` still passes.

### Migrations

Forward-only numbered SQL. No down-migrations — rolling back a schema on a live DB is more dangerous than rolling forward.

```
migrations/
  0001_init_orgs_users.sql
  0002_loans_add_org_id.sql
  0003_rls_policies.sql
  0004_agent_tables.sql
  0005_pgvector_schema_embeddings.sql
```

A `schema_migrations` table stores `(version, checksum, applied_at)`. CI fails if a previously-applied file's checksum changed — you cannot silently edit history.

---

## 10. dbt Data Contracts

dbt is not here to move data. The dataset is small and lives in one Postgres. **dbt is here to make the contract between the transformation layer and everything downstream executable.**

```mermaid
graph LR
    subgraph src["Sources"]
        RAW["loans<br/>report_records<br/>loan_history"]
    end

    subgraph staging["Staging — cleaning"]
        STG1["stg_loans<br/>typed, normalized"]
        STG2["stg_payments"]
    end

    subgraph marts["Marts — canonical shapes"]
        M1["dim_borrower"]
        M2["fct_loan_schedule<br/>monthly/quarterly/yearly"]
        M3["fct_outstanding_balance"]
        M4["agg_portfolio_summary"]
    end

    subgraph consumers["Consumers"]
        DASH["React Dashboard"]
        AGENT["Agent tools"]
        RPT["Report service"]
    end

    RAW --> STG1 --> M2 --> DASH
    RAW --> STG2 --> M3 --> AGENT
    STG1 --> M1 --> M4 --> RPT
    M2 --> AGENT

    style src fill:#1f1f2e,stroke:#8b7ec8,color:#fff
    style staging fill:#1a3a52,stroke:#4a9eff,color:#fff
    style marts fill:#0f2e1f,stroke:#3ecf8e,color:#fff
    style consumers fill:#3d2914,stroke:#ff9f45,color:#fff
```

### A contract, made executable

```yaml
# models/marts/schema.yml
models:
  - name: fct_loan_schedule
    description: >
      Canonical per-period loan schedule. THE contract for the dashboard,
      the agent's query tools, and the report service.
    config:
      contract:
        enforced: true          # dbt fails the build if a type changes
    columns:
      - name: reference_id
        data_type: text
        constraints: [{type: not_null}]
        tests: [unique]
      - name: period_type
        data_type: text
        tests:
          - accepted_values:
              values: ['monthly', 'quarterly', 'yearly']
      - name: outstanding_amount
        data_type: numeric
        tests:
          - dbt_utils.accepted_range: {min_value: 0, inclusive: true}
      - name: interest_accrued
        data_type: numeric
        tests:
          # The MVP1 business rule, enforced in the warehouse
          - dbt_utils.expression_is_true:
              expression: "= (principal * interest_rate * extension_periods) / 1200"
              config: {where: "period_type = 'monthly'"}
```

**Why this earns its place**: the last test re-asserts MVP1's monthly interest formula *at the data layer*. If someone changes the Python calculator and forgets the warehouse — or vice versa — **dbt fails in CI**. The business rule now has two independent enforcers that must agree.

> ### ⚠️ Gotcha 4 — dbt in serverless
>
> dbt is a CLI. It does not belong inside a Vercel function.
>
> **Mitigation**: dbt runs in **GitHub Actions** — on every PR touching `models/`, and on a nightly schedule against production. Results post to the PR and to Grafana. The API never invokes dbt; it only reads the tables dbt produces.

---

## 11. The ReAct Agent

This is the part that makes the resume story real. A chatbot that only rephrases a search query is a wrapper. **ReAct — Reason + Act — is an agent that interleaves reasoning with tool execution and adapts based on what it observes.**

### The loop

```mermaid
stateDiagram-v2
    [*] --> Receive: user message
    Receive --> Retrieve: embed + fetch<br/>schema context (RAG)
    Retrieve --> Mask: strip PII
    Mask --> Reason: Groq inference

    Reason --> Decide

    Decide --> ExecuteRead: read-only tool
    Decide --> ProposeWrite: mutating tool
    Decide --> Respond: enough information

    ExecuteRead --> Observe: tool result
    ProposeWrite --> Observe: proposal receipt

    Observe --> StepCheck
    StepCheck --> Reason: steps < 6
    StepCheck --> Degrade: steps >= 6

    Degrade --> Respond: partial answer<br/>+ refine prompt
    Respond --> Meter: record tokens,<br/>cost, latency, trace
    Meter --> [*]

    Reason --> Retry: malformed tool call
    Retry --> Reason: attempt <= 2
    Retry --> Degrade: attempt > 2
```

### Worked example — trace this line by line

**User**: *"what's due this quarter for the sharma group?"*

```
┌─ STEP 1 ────────────────────────────────────────────────
│ Thought:  I need loans with due_date in the current
│           quarter, filtered by borrower_group. I don't
│           know today's date or the exact group spelling.
│ Action:   get_current_context()
│ Observation: {"today": "2026-09-07", "quarter": "2026-Q3",
│               "quarter_range": ["2026-07-01","2026-09-30"]}
├─ STEP 2 ────────────────────────────────────────────────
│ Thought:  Now resolve "sharma group" to a real value.
│ Action:   resolve_entity(field="borrower_group",
│                          query="sharma")
│ Observation: {"matches": ["sharma_traders"],
│               "confidence": 0.94}
├─ STEP 3 ────────────────────────────────────────────────
│ Thought:  I have both filters. Query.
│ Action:   query_loans(borrower_group="sharma_traders",
│                       due_date_from="2026-07-01",
│                       due_date_to="2026-09-30")
│ Observation: {"count": 4, "total_amount": 185000,
│               "records": [...]}
├─ STEP 4 ────────────────────────────────────────────────
│ Thought:  I have everything. Answer.
│ Final:    "Sharma Traders has 4 loans due in Q3 2026,
│            totalling ₹1,85,000. Two are already overdue:
│            2026_03_004 (₹45,000, due 12 Aug) and
│            2026_03_009 (₹60,000, due 28 Aug)."
└──────────────────────────────────────────────────────────
  4 steps · 2,840 prompt tok · 310 completion tok
  $0.00019 · 2.1s wall
```

Notice step 2. A naive implementation would query `borrower_group = 'sharma group'`, return zero rows, and confidently report "no loans found." **The ReAct loop's ability to resolve ambiguity before acting is the entire value proposition.**

### The tool registry

Tools are Pydantic models. The JSON schema handed to Groq is generated from them, so the schema and the implementation cannot drift.

```python
# finhive/agent/tools/query_loans.py
from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, Field
from finhive.agent.registry import tool

class QueryLoansArgs(BaseModel):
    """Search loans by any combination of filters. Read-only."""
    borrower_name: Optional[str] = Field(None, description="Exact borrower name, lowercase")
    borrower_group: Optional[str] = Field(None, description="Exact group name, lowercase")
    status: Optional[Literal["Active", "Overdue", "Pending", "Paidoff"]] = None
    due_date_from: Optional[date] = None
    due_date_to: Optional[date] = None
    limit: int = Field(50, ge=1, le=200)

@tool(
    name="query_loans",
    args_model=QueryLoansArgs,
    mutating=False,          # ← drives the approval gate
    required_role="viewer",  # ← drives authorization
)
async def query_loans(args: QueryLoansArgs, ctx: AgentContext) -> dict:
    rows = await ctx.loan_repo.search(**args.model_dump(exclude_none=True))
    return {"count": len(rows), "records": [r.to_summary() for r in rows]}
```

### Full tool inventory

| Tool | Mutating | Min role | Purpose |
|---|---|---|---|
| `get_current_context` | ❌ | viewer | Today's date, quarter boundaries, org name |
| `resolve_entity` | ❌ | viewer | Fuzzy name → canonical value (RAG-backed) |
| `query_loans` | ❌ | viewer | Filtered loan search |
| `get_portfolio_summary` | ❌ | viewer | Aggregates from `agg_portfolio_summary` |
| `calculate_interest` | ❌ | viewer | Preview calculation; no persistence |
| `create_loan` | ✅ | bookkeeper | Propose a new loan |
| `update_loan` | ✅ | bookkeeper | Propose a field change |
| `extend_loan` | ✅ | bookkeeper | Propose an extension |
| `generate_report` | ✅ | bookkeeper | Propose a report into the approval queue |

> ### ⚠️ Gotcha 5 — Groq's tool-calling is fast, not infallible
>
> Groq's LPU gives ~10x the tokens/sec of typical GPU inference, which is what makes a 4-step loop feel instant. But the open-weight models it serves produce malformed tool arguments more often than frontier models — wrong enum casing, a date as `"next quarter"` instead of ISO.
>
> **Mitigation**:
> - **Validate every tool call against its Pydantic model before dispatch.** On `ValidationError`, feed the error text back as an Observation and let the model self-correct. This recovers the large majority of failures on the first retry.
> - Cap at **2 retries** per step, then degrade gracefully.
> - LiteLLM keeps the provider abstract. If a specific tool's accuracy is unacceptable, route *that tool's* reasoning step to a stronger model. Config change, not a rewrite.

---

## 12. Agent Safety — The Mutation Approval Gate

**The single most important design decision in MVP2.**

An LLM must never write to the loans table. Not because it usually gets it wrong — it usually gets it right — but because "usually" is not a property you can put in front of someone's financial records.

MVP1 already solved this shape of problem: the Pending Approval queue, where a calculated report previews its post-approval state and a human commits it. **MVP2 generalizes that pattern to every agent-proposed mutation.**

```mermaid
sequenceDiagram
    autonumber
    participant U as Bookkeeper
    participant A as Agent
    participant DB as Postgres
    participant O as Owner

    U->>A: "extend all overdue sharma loans by 1 month"
    A->>DB: query_loans(group=sharma, status=Overdue)
    DB-->>A: 3 records

    Note over A: mutating tool → propose, do not execute
    A->>DB: INSERT proposed_mutations (×3)<br/>before_state, after_state
    DB-->>A: proposal_ids

    A-->>U: "I've prepared 3 extensions.<br/>Review the diff below."
    Note over U: sees exact before → after<br/>per record

    U->>O: requests approval
    O->>DB: UPDATE proposed_mutations<br/>SET status='approved'

    Note over DB: trigger applies after_state<br/>inside ONE transaction
    DB->>DB: BEGIN; UPDATE loans...; COMMIT
    DB-->>O: applied
    O-->>U: done
```

### The rules

1. **Reads execute immediately.** No friction on questions.
2. **Writes always propose.** `mutating=True` on a tool means the dispatcher writes a `proposed_mutations` row instead of calling the domain use case.
3. **The diff is exact.** `before_state` and `after_state` are full JSONB snapshots. The UI renders a literal field-by-field diff — not the agent's prose description of what it did.
4. **Approval is transactional.** All mutations in one proposal batch apply inside a single Postgres transaction. Partial application is impossible.
5. **Role-gated.** Only `owner` can approve. Enforced by RLS (§8), not by frontend logic.
6. **Reversible.** `before_state` is retained, so any applied batch can be inverted.

> **ARB talking point**: This converts "we trust the LLM" into "we do not need to trust the LLM." The blast radius of a hallucinated mutation is a rejected proposal row. That is what makes an agent shippable against financial data.

---

## 13. PII Masking Pipeline

Borrower names and account identifiers must not leave our infrastructure in an LLM prompt.

```mermaid
graph LR
    A["Raw record<br/>borrower: 'Rajesh Sharma'<br/>acct: 'HDFC...4471'"] --> B["Tokenizer"]
    B --> C["Masked<br/>borrower: PERSON_1<br/>acct: ACCT_1"]
    C --> D["Groq"]
    D --> E["Response<br/>'PERSON_1 has 3 loans'"]
    E --> F["Rehydrator"]
    F --> G["'Rajesh Sharma<br/>has 3 loans'"]

    B -.->|"session-scoped<br/>bidirectional map<br/>(memory only)"| F

    style A fill:#4a1f1f,stroke:#ff6b6b,color:#fff
    style C fill:#1f3d1f,stroke:#51cf66,color:#fff
    style D fill:#3d2914,stroke:#ff9f45,color:#fff
    style G fill:#4a1f1f,stroke:#ff6b6b,color:#fff
```

### Implementation

```python
class PIIMasker:
    """Session-scoped, deterministic, bidirectional PII substitution."""

    MASKED_FIELDS = {
        "borrower_name": "PERSON",
        "depositor_name": "PERSON",
        "account_number": "ACCT",
    }

    def __init__(self) -> None:
        self._forward: dict[str, str] = {}   # real → token
        self._reverse: dict[str, str] = {}   # token → real
        self._counters: dict[str, int] = {}

    def mask(self, value: str, field: str) -> str:
        if value in self._forward:
            return self._forward[value]           # stable within a session
        prefix = self.MASKED_FIELDS[field]
        self._counters[prefix] = self._counters.get(prefix, 0) + 1
        token = f"{prefix}_{self._counters[prefix]}"
        self._forward[value] = token
        self._reverse[token] = value
        return token

    def rehydrate(self, text: str) -> str:
        for token, real in self._reverse.items():
            text = text.replace(token, real)
        return text
```

**Why stability matters**: `"Rajesh Sharma"` maps to `PERSON_1` for the *entire* session. If it were random per-call, the agent could not reason across turns — *"the borrower you mentioned earlier"* would break.

**What is never masked**: amounts, dates, reference IDs, statuses. The agent needs these to reason, and none identify a person on their own.

> ### ⚠️ Gotcha 6 — Masking is not anonymization
>
> A single loan of ₹4,50,000 due 2026-03-15 in a 40-record dataset may be uniquely identifying even with the name stripped. This is a re-identification risk, not a solved problem.
>
> **Mitigation, stated honestly for the ARB**: masking meaningfully reduces exposure and satisfies "no plaintext names leave our infrastructure." It is not a compliance claim. Groq's zero-retention API terms are the second control. If a regulated customer ever appears, the answer is a self-hosted model — the LiteLLM abstraction is what keeps that a config change.

---

## 14. LLM Observability, Cost & Evaluation

Every agent turn is a measured, replayable transaction.

```mermaid
graph TB
    subgraph turn["Agent turn"]
        T1["ReAct loop"]
    end

    subgraph capture["Captured per turn"]
        C1["prompt_tokens<br/>completion_tokens"]
        C2["cost_usd<br/>(LiteLLM pricing)"]
        C3["latency_ms<br/>per step + total"]
        C4["full react_trace<br/>(JSONB)"]
        C5["tool_calls<br/>+ validation failures"]
        C6["user feedback<br/>👍 / 👎"]
    end

    subgraph sinks["Destinations"]
        S1[("agent_turns<br/>Postgres")]
        S2["Grafana<br/>dashboards + alerts"]
        S3["Amplitude<br/>product funnels"]
        S4["Eval dataset<br/>nightly CI"]
    end

    T1 --> C1 & C2 & C3 & C4 & C5 & C6
    C1 & C2 & C3 & C4 & C5 & C6 --> S1
    S1 --> S2
    S1 --> S3
    C6 --> S4
    C4 --> S4

    style turn fill:#3d2914,stroke:#ff9f45,color:#fff
    style capture fill:#1a3a52,stroke:#4a9eff,color:#fff
    style sinks fill:#0f2e1f,stroke:#3ecf8e,color:#fff
```

### Cost tracking

LiteLLM returns normalized usage across providers:

```python
response = await litellm.acompletion(
    model="groq/llama-3.3-70b-versatile",
    messages=messages,
    tools=tool_schemas,
)

await record_turn_metrics(
    turn_id=turn_id,
    prompt_tokens=response.usage.prompt_tokens,
    completion_tokens=response.usage.completion_tokens,
    cost_usd=litellm.completion_cost(completion_response=response),
    model=response.model,
    latency_ms=elapsed_ms,
)
```

**Budget guardrails**:

| Guard | Threshold | Action |
|---|---|---|
| Per-turn token cap | 8,000 prompt tokens | Truncate RAG context, warn |
| Per-user daily spend | $0.50 | Soft block, notify owner |
| Per-org monthly spend | $10.00 | Hard block, page on-call |
| Anomaly | 3× 7-day rolling mean | Grafana alert |

At 3 DAU × ~20 turns/day × ~$0.0002/turn, real spend is roughly **$0.36/month**. The guardrails exist to catch a runaway loop, not to manage a budget.

### Evaluation harness

A golden dataset of natural-language inputs with expected tool sequences, run nightly in CI.

```yaml
# evals/golden/quarterly_query.yaml
- id: q_due_this_quarter
  input: "what's due this quarter for the sharma group?"
  expect:
    tools_called: [get_current_context, resolve_entity, query_loans]
    tool_args:
      query_loans:
        borrower_group: sharma_traders
    must_not_call: [create_loan, update_loan, extend_loan]
    answer_contains: ["4", "1,85,000"]
    max_steps: 5
```

| Metric | Definition | Gate |
|---|---|---|
| **Tool-selection accuracy** | Correct tool chosen at each step | ≥ 90% |
| **Argument accuracy** | Args match expected after normalization | ≥ 85% |
| **Task completion** | Final answer contains required facts | ≥ 85% |
| **Unsafe-call rate** | Mutating tool invoked when not asked | **0%** — hard fail |
| **p95 latency** | Wall time, full loop | ≤ 4s |
| **Cost per task** | Mean USD | ≤ $0.001 |

**Unsafe-call rate is a release blocker.** A single unrequested mutation proposal fails the build.

### Feedback loop

```mermaid
graph LR
    A["👎 on a turn"] --> B["react_trace captured"]
    B --> C["Triage: prompt bug,<br/>tool bug, or data bug?"]
    C --> D["Add to golden dataset<br/>as a regression case"]
    D --> E["Fix"]
    E --> F["Nightly eval proves<br/>it stays fixed"]
    F -.-> A

    style A fill:#4a1f1f,stroke:#ff6b6b,color:#fff
    style F fill:#1f3d1f,stroke:#51cf66,color:#fff
```

Every thumbs-down becomes a permanent test case. The eval suite grows monotonically with real usage — this is the mechanism that makes agent quality improve rather than drift.

---

## 15. Frontend Architecture

```mermaid
graph TB
    subgraph shell["App Shell"]
        RT["React Router"]
        AUTH["AuthProvider<br/>(Supabase session)"]
        TH["ChakraProvider<br/>(status colour tokens)"]
    end

    subgraph pages["Routes"]
        DASH["/dashboard<br/>portfolio + alerts"]
        LOANS["/loans<br/>table, filter, inline edit"]
        CHAT["/chat<br/>agent interface"]
        APPR["/approvals<br/>mutation diffs"]
        DOCS["/help<br/>MDX content"]
    end

    subgraph state["State"]
        RQ["TanStack Query<br/>server state, cache"]
        ZS["Zustand<br/>UI state, chat buffer"]
        SSE["EventSource<br/>agent stream"]
    end

    RT --> DASH & LOANS & CHAT & APPR & DOCS
    AUTH --> RQ
    DASH & LOANS & APPR --> RQ
    CHAT --> SSE
    CHAT --> ZS
    RQ -->|"invalidate on approval"| LOANS

    style shell fill:#1f1f2e,stroke:#8b7ec8,color:#fff
    style pages fill:#1a3a52,stroke:#4a9eff,color:#fff
    style state fill:#0f2e1f,stroke:#3ecf8e,color:#fff
```

### Streaming the ReAct trace

The agent's reasoning is the product, not a loading spinner. Users see each step as it happens:

```tsx
function useAgentStream(sessionId: string) {
  const [steps, setSteps] = useState<ReActStep[]>([]);
  const [status, setStatus] = useState<"idle" | "thinking" | "done">("idle");

  const send = useCallback(async (message: string) => {
    setSteps([]);
    setStatus("thinking");

    const res = await fetch("/api/agent/stream", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ session_id: sessionId, message }),
    });

    for await (const event of parseSSE(res.body!)) {
      switch (event.type) {
        case "thought":   setSteps(s => [...s, { kind: "thought", text: event.text }]); break;
        case "action":    setSteps(s => [...s, { kind: "action", tool: event.tool, args: event.args }]); break;
        case "observation": setSteps(s => [...s, { kind: "observation", data: event.data }]); break;
        case "proposal":  queryClient.invalidateQueries({ queryKey: ["approvals"] }); break;
        case "final":     setStatus("done"); break;
      }
    }
  }, [sessionId]);

  return { steps, status, send };
}
```

**UX principle**: showing `Thought: I need to resolve "sharma" to a group name` builds trust in a way a spinner never can. When the agent is wrong, the user sees *where* it went wrong.

### Chakra tokens carry MVP1's palette forward

```ts
const theme = extendTheme({
  semanticTokens: {
    colors: {
      "status.active":  { default: "#025c33", _dark: "#0a7d47" },
      "status.overdue": { default: "#6b0307", _dark: "#8f0a10" },
      "status.pending": { default: "#804001", _dark: "#a35502" },
      "status.paidoff": { default: "#022a52", _dark: "#03407a" },
    },
  },
});
```

Same rule as MVP1: **no hardcoded hex in components.** The rule moves from `ThemeManager` to Chakra tokens; the discipline is identical.

> ### ⚠️ Gotcha 7 — SSE and buffering
>
> SSE through a CDN can be buffered, which defeats streaming entirely — the user waits the full duration then sees everything at once.
>
> **Mitigation**: set `X-Accel-Buffering: no` and `Cache-Control: no-cache, no-transform` on the stream response. Add a Playwright e2e test asserting the **first** SSE event arrives within 1s. That test is what stops a future config change from silently breaking the core UX.

---

## 16. Observability & Analytics

Three tools, three distinct questions. Do not confuse them.

| Tool | Question it answers | Owner |
|---|---|---|
| **Grafana** | *Is the system healthy?* | Engineering |
| **Amplitude** | *Are users getting value?* | Product |
| **Vercel Analytics** | *Is the page fast?* | Both |

```mermaid
graph LR
    subgraph app["Application"]
        FE["React"]
        BE["FastAPI"]
    end

    subgraph otel["OpenTelemetry"]
        TR["Traces"]
        ME["Metrics"]
        LO["Logs"]
    end

    subgraph obs["Grafana Cloud"]
        TEMPO["Tempo"]
        PROM["Prometheus"]
        LOKI["Loki"]
        ALERT["Alerting"]
    end

    BE --> TR & ME & LO
    TR --> TEMPO
    ME --> PROM
    LO --> LOKI
    TEMPO & PROM & LOKI --> ALERT

    FE -->|"web vitals"| VA["Vercel Analytics"]
    FE -->|"user events"| AMP["Amplitude"]
    BE -->|"server events"| AMP

    style app fill:#1a3a52,stroke:#4a9eff,color:#fff
    style otel fill:#1f1f2e,stroke:#8b7ec8,color:#fff
    style obs fill:#0f2e1f,stroke:#3ecf8e,color:#fff
```

### Grafana dashboards

| Dashboard | Panels |
|---|---|
| **API Health** | Request rate, p50/p95/p99 latency, 4xx/5xx by route, cold-start frequency |
| **Agent Health** | Turns/hour, steps per turn, tool-call failure rate, retry rate, p95 loop latency |
| **Cost** | Spend by user/day, tokens by model, cost per completed task |
| **Data Quality** | dbt test pass rate, rows per mart, freshness lag |

### Alerts that page

| Alert | Condition | Severity |
|---|---|---|
| API 5xx spike | >5% over 5 min | Critical |
| Agent unsafe call | Any mutating tool without user intent | **Critical** |
| Cost anomaly | >3× 7-day mean | Warning |
| dbt test failure | Any contract test fails | Critical |
| RLS violation | Cross-org read attempt in logs | **Critical** |

### Amplitude event taxonomy

```
loan_created            { source: "form" | "agent", org_id, role }
agent_turn_completed    { steps, tools_used[], latency_ms, cost_usd, had_proposal }
agent_feedback          { turn_id, sentiment: "up"|"down" }
mutation_proposed       { operation, record_count, source: "agent" }
mutation_approved       { operation, record_count, time_to_approve_s }
mutation_rejected       { operation, reason }
report_generated        { mode, record_count, source }
spreadsheet_op_replaced { op_type, method: "form"|"agent" }   ← North Star input
```

---

## 17. CI/CD Pipeline & Quality Gates

```mermaid
graph TB
    START["Push to feature/xx-N"] --> LINT

    subgraph fast["Fast gates — under 2 min"]
        LINT["ruff + mypy<br/>+ import-linter"]
        FMT["prettier + eslint"]
        SEC["gitleaks<br/>secret scan"]
    end

    LINT --> FMT --> SEC --> UNIT

    subgraph test["Test gates"]
        UNIT["pytest unit<br/>coverage >= 85%"]
        INTEG["pytest integration<br/>ephemeral Supabase branch"]
        RLS["RLS isolation test<br/>Org A cannot read Org B"]
        SQLI["SQL injection scan<br/>no f-strings in SQL"]
    end

    UNIT --> INTEG --> RLS --> SQLI --> DBT

    subgraph data["Data gates"]
        DBT["dbt build<br/>contracts + tests"]
    end

    DBT --> EVAL

    subgraph ai["AI gates"]
        EVAL["agent evals<br/>unsafe-call rate = 0"]
    end

    EVAL --> PREVIEW

    subgraph deploy["Deploy"]
        PREVIEW["Vercel preview<br/>pr-N.vercel.app"]
        E2E["Playwright e2e<br/>against preview"]
    end

    PREVIEW --> E2E --> CR

    subgraph review["Review"]
        CR["CodeRabbit<br/>automated review"]
        HUMAN["Human approval"]
    end

    CR --> HUMAN --> MERGE["Merge to development"]
    MERGE --> STAGING["Auto-deploy staging"]
    STAGING --> RELEASE["Release PR to main"]
    RELEASE --> PROD["Production"]

    style fast fill:#1a3a52,stroke:#4a9eff,color:#fff
    style test fill:#0f2e1f,stroke:#3ecf8e,color:#fff
    style data fill:#2e1f2e,stroke:#e879f9,color:#fff
    style ai fill:#3d2914,stroke:#ff9f45,color:#fff
    style deploy fill:#1f1f2e,stroke:#8b7ec8,color:#fff
    style review fill:#3d1f2e,stroke:#f472b6,color:#fff
```

### Gate definitions

| Gate | Blocks merge | Runtime | Notes |
|---|---|---|---|
| `ruff` + `mypy` | ✅ | ~20s | `mypy --strict` on `domain/` and `calc/` |
| `import-linter` | ✅ | ~5s | Enforces §5 boundaries |
| `gitleaks` | ✅ | ~10s | No Supabase/Groq keys in history |
| Unit tests | ✅ | ~45s | ≥85% coverage, inherited from MVP1 |
| Integration tests | ✅ | ~2min | Real Postgres on a Supabase branch |
| **RLS isolation** | ✅ | ~30s | The most important security test in the repo |
| SQL injection scan | ✅ | ~5s | Grep gate: no f-string/`%`/`.format()` in SQL constants |
| dbt build | ✅ (if `models/` touched) | ~1min | Contract enforcement |
| Agent evals | ✅ | ~3min | Nightly full suite; PR runs a fast subset |
| Playwright e2e | ✅ | ~4min | Runs against the actual Vercel preview |
| CodeRabbit | ⚠️ blocking findings only | ~2min | See §18 |

### The critical path is ordered by cost

Lint fails in 20 seconds. Agent evals cost money and take 3 minutes. **Cheap gates run first** so a missing type annotation never burns Groq credits.

---

## 18. The Agentic Development Loop

Your envisioned workflow, made concrete.

```mermaid
sequenceDiagram
    autonumber
    participant L as Linear
    participant D as Developer Agent
    participant G as GitHub
    participant CR as CodeRabbit CLI
    participant H as Human

    L->>D: issue assigned (FIN-42)
    D->>G: branch feature/fin-42<br/>from development
    D->>D: implement + tests
    D->>G: push, open PR

    G->>CR: coderabbit review --plain
    CR-->>D: findings (blocking + advisory)

    alt no blocking findings
        CR-->>H: ready for human review
    else cycle 1
        D->>D: fix blocking findings
        D->>G: push
        G->>CR: re-review
        alt clean
            CR-->>H: ready for human review
        else cycle 2
            D->>D: fix again
            D->>G: push
            G->>CR: re-review
            alt clean
                CR-->>H: ready for human review
            else still blocking
                D->>L: create FIN-42-followup
                Note over L: includes: findings,<br/>fixes attempted,<br/>why they failed
                D->>G: mark PR draft
                D-->>H: escalate
            end
        end
    end

    H->>G: approve + merge to development
```

### Escalation payload

After two failed cycles, the agent stops and files a Linear issue containing:

```markdown
## Escalated from FIN-42 (PR #128)

**Blocking finding (persisted through 2 fix cycles)**
CodeRabbit: "Potential N+1 query in `get_portfolio_summary` —
`resolve_borrower` called inside a loop over 200 rows."

**Attempt 1** — Added `functools.lru_cache` to `resolve_borrower`.
Rejected: cache is per-process; serverless cold starts make hit
rate ~0. Finding persisted.

**Attempt 2** — Batched with `WHERE borrower_id = ANY($1)`.
Rejected: broke RLS — the batch query bypassed the per-row
policy check. Integration test `test_rls_isolation` failed.

**Why this needs a human**
The fix requires an RLS policy change (adding a security-definer
function for batch reads). That is an architecture decision above
this agent's authority.

**Suggested direction**
Either (a) a `SECURITY DEFINER` function with an explicit org_id
guard, or (b) denormalize borrower_name onto the summary mart in
dbt and drop the join entirely. (b) is likely simpler.
```

**Why two cycles**: cycle 1 catches mechanical issues. Cycle 2 catches issues where the first fix was wrong. A third cycle almost always means the problem is a design constraint the agent cannot see — and burning more tokens on it is waste. This is the same bounded-retry philosophy as the ReAct loop (§11): **fail fast, escalate with context.**

### Stacked PRs

`development` is the integration base. Feature branches stack on it. A release PR promotes `development` → `main`. This keeps `main` always-deployable while allowing feature branches to build on each other's unmerged work.

---

## 19. Migration Strategy — MVP1 to MVP2

**Constraint**: the MVP1 domain layer is the asset. 150 tests, 89% coverage, correct business rules. It must survive.

```mermaid
graph LR
    subgraph keep["KEEP — lift as-is"]
        K1["domain/entities"]
        K2["domain/value_objects"]
        K3["domain/services<br/>StatusEngine<br/>InterestCalculator<br/>ReferenceIdService"]
        K4["domain/repositories<br/>(interfaces)"]
        K5["Unit tests"]
    end

    subgraph adapt["ADAPT — same contract, new impl"]
        A1["application/use_cases<br/>→ async"]
        A2["dtos → FastAPI models"]
        A3["repositories<br/>SQLAlchemy → raw SQL"]
    end

    subgraph replace["REPLACE"]
        R1["presentation/<br/>PySide6 → React"]
        R2["container.py<br/>→ FastAPI Depends"]
        R3["SQLite → Supabase"]
    end

    subgraph new["NEW"]
        N1["agent-service"]
        N2["retrieval-service"]
        N3["auth + RLS"]
        N4["dbt models"]
    end

    style keep fill:#0f2e1f,stroke:#3ecf8e,color:#fff
    style adapt fill:#1a3a52,stroke:#4a9eff,color:#fff
    style replace fill:#4a1f1f,stroke:#ff6b6b,color:#fff
    style new fill:#3d2914,stroke:#ff9f45,color:#fff
```

### What "keep" actually means

`InterestCalculator` is a pure static-method class with no I/O. It moves file-for-file into `finhive/calc/` and its tests move with it. **Zero changes.** The monthly formula `(amount × rate × months) / 1200` is identical in MVP2 — and now double-enforced by the dbt contract (§10).

### Data migration

```mermaid
graph LR
    A["SQLite<br/>loans.db"] --> B["export_to_csv.py<br/>(exists in MVP1)"]
    B --> C["migrate_to_supabase.py"]
    C --> D["assign org_id"]
    D --> E["validate:<br/>row counts, checksums,<br/>ref_id uniqueness"]
    E --> F[("Supabase<br/>Postgres")]
    E -.->|"mismatch"| G["ABORT<br/>keep SQLite"]

    style G fill:#4a1f1f,stroke:#ff6b6b,color:#fff
    style F fill:#0f2e1f,stroke:#3ecf8e,color:#fff
```

Migration is **idempotent and verified**. It reconciles row counts and per-record checksums before committing. On any mismatch it aborts and leaves SQLite untouched — the desktop app remains a working fallback throughout the transition.

---

## 20. Tradeoffs & Gotchas

Consolidated for ARB review. Each is a *managed* risk, not an unknown.

| # | Tradeoff | We accept | We mitigate with |
|---|---|---|---|
| 1 | **Serverless timeouts vs ReAct loops** | Complex queries may hit limits | SSE streaming, `MAX_STEPS=6`, job-row escape hatch |
| 2 | **Cold starts** | First request after idle is 3–5s | Dependency discipline, lazy imports, cron warming |
| 3 | **Service-role key bypasses RLS** | One misconfiguration voids authz | Single guarded location, CI isolation test, lint rule |
| 4 | **dbt cannot run serverless** | Transformations are not real-time | GitHub Actions on PR + nightly; API reads marts only |
| 5 | **Groq tool-call reliability** | Malformed args occur | Pydantic validation + 2 retries + provider abstraction |
| 6 | **Masking ≠ anonymization** | Re-identification is theoretically possible | Honest scoping, zero-retention terms, self-host path |
| 7 | **SSE buffering through CDN** | Streaming can silently break | Explicit headers + Playwright first-event assertion |
| 8 | **Raw SQL has no type safety** | Schema drift can reach runtime | Contract tests, query-count tests, CI grep gate |
| 9 | **Vercel Blob is platform lock-in** | Migration cost if we leave Vercel | Accepted — small surface, ~1 day to port to S3 |
| 10 | **No offline mode** | Web-only means no network, no app | Accepted for MVP2; MVP1 desktop remains as fallback |

---

## 21. Risk Register

| ID | Risk | Prob. | Impact | Response |
|---|---|---|---|---|
| R-201 | Agent proposes a mutation the user did not request | Med | **High** | Approval gate (§12); unsafe-call rate = 0 is a release blocker |
| R-202 | RLS misconfiguration leaks cross-tenant data | Low | **Critical** | CI isolation test on a real DB; service-role lint rule |
| R-203 | Groq degrades or changes pricing | Med | Med | LiteLLM abstraction; a provider swap is a config change |
| R-204 | Serverless timeout on a complex query | Med | Med | Streaming + step cap + job escape hatch |
| R-205 | Raw SQL injection via a careless contribution | Low | **Critical** | Parameterized-only rule, CI grep gate, CodeRabbit |
| R-206 | dbt and Python calculators diverge | Med | High | Same formula asserted in both; dbt test fails the build |
| R-207 | Cost runaway from a loop bug | Low | Med | Per-user/org budget caps; Grafana anomaly alert |
| R-208 | Migration loses or corrupts MVP1 data | Low | **Critical** | Checksum verification, abort-on-mismatch, SQLite retained |
| R-209 | Vercel free-tier limits hit during demo | Med | Low | Pro tier is $20/mo; budgeted |
| R-210 | Agent latency makes chat feel worse than forms | Med | High | Groq LPU + streaming; p95 ≤ 4s is an eval gate |

---

## 22. North Star Metrics

### North Star

> **Weekly Spreadsheet Operations Replaced (WSOR)**
>
> The count of loan operations — create, update, query, extend, report — completed in FinHive per active user per week that would otherwise have been manual spreadsheet work.

**Why this one**: it measures delivered value in the user's own terms. Not logins, not messages sent, not "AI interactions." A bookkeeper who replaces 40 spreadsheet operations a week has a product they will not give up. It is also directly instrumentable via the `spreadsheet_op_replaced` event (§16).

**Target**: 40 WSOR per active user by end of Phase 4.

### Supporting metrics (L2)

| Metric | Definition | Target | Why it matters |
|---|---|---|---|
| **Agent Task Completion Rate** | Turns resolving intent with no human correction | ≥ 85% | Below this, the agent is friction, not leverage |
| **Time to Insight (p95)** | Question asked → answer rendered | ≤ 4s | The threshold where chat beats clicking filters |
| **Proposal Approval Rate** | Approved ÷ proposed mutations | ≥ 90% | Low rate means the agent misunderstands intent |
| **Data Trust Score** | dbt tests passing × (1 − hallucination rate) | ≥ 0.95 | One wrong number destroys trust in every number |
| **Cost per Resolved Task** | LLM spend ÷ completed tasks | ≤ $0.001 | Unit economics for any future scaling |
| **Weekly Active Ratio** | WAU ÷ registered | ≥ 30% | At 10 users, 3 DAU — validates the target |

### Counter-metrics — what we watch to be sure we are not gaming the North Star

| Counter-metric | Guards against |
|---|---|
| Manual correction rate after agent ops | Inflating WSOR with wrong operations |
| Time-to-approve on proposals | Users rubber-stamping without reading diffs |
| Repeat-question rate within a session | Agent answering wrongly, user rephrasing |

---

## 23. Phased Delivery Plan

```mermaid
gantt
    title MVP2 Delivery
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section P1 Foundation
    Repo, CI, CodeRabbit      :p1a, 2026-09-08, 5d
    Supabase + RLS + migrations :p1b, after p1a, 5d
    Domain port (keep layer)  :p1c, after p1a, 4d

    section P2 API + Web
    FastAPI + raw SQL repos   :p2a, after p1b, 7d
    Supabase Auth wiring      :p2b, after p2a, 3d
    React + Chakra shell      :p2c, after p1c, 7d
    Loans table + dashboard   :p2d, after p2c, 7d

    section P3 Agent
    LiteLLM + tool registry   :p3a, after p2b, 5d
    ReAct loop + streaming    :p3b, after p3a, 7d
    PII masking + RAG         :p3c, after p3a, 5d
    Approval gate + diff UI   :p3d, after p3b, 5d

    section P4 Trust
    dbt contracts             :p4a, after p2a, 5d
    Grafana + Amplitude       :p4b, after p3b, 4d
    Eval harness + feedback   :p4c, after p3d, 5d
    Playwright e2e            :p4d, after p3d, 5d
```

### Phase gates

| Phase | Exit criteria |
|---|---|
| **P1 Foundation** | CI green; RLS isolation test passing; MVP1 domain tests passing unchanged |
| **P2 API + Web** | Full loan CRUD via web; auth working; MVP1 data migrated and verified |
| **P3 Agent** | ReAct loop answers the 3 canonical queries; every mutation routes through the approval gate; unsafe-call rate 0% |
| **P4 Trust** | dbt contracts enforced; Grafana dashboards live; eval suite in CI; e2e green against preview |

---

## 24. ARB Decision Log

Decisions requiring explicit ARB sign-off:

| ID | Decision | Recommendation | Risk if rejected |
|---|---|---|---|
| **D-1** | Raw SQL instead of an ORM | **Approve** with mandated mitigations (§6, ADR-2.2) | Rework of the entire data layer; ~2 weeks |
| **D-2** | Agent mutations always require human approval | **Approve** — non-negotiable | Unbounded blast radius on financial data |
| **D-3** | Modular monolith, not microservices | **Approve** — boundaries CI-enforced | Distributed complexity with no benefit at 3 DAU |
| **D-4** | Groq as primary LLM | **Approve** — LiteLLM keeps it swappable | Latency budget unachievable on typical GPU inference |
| **D-5** | PII masking (not full anonymization) | **Approve** with scope stated honestly (§13) | Blocks all LLM features |
| **D-6** | Vercel platform coupling (Blob, Analytics) | **Approve** — small, portable surface | Marginal benefit; adds ~1 week of abstraction work |
| **D-7** | dbt in CI rather than at runtime | **Approve** | Real-time transformation is not a requirement |

### Open questions for the board

1. **Data residency** — Supabase region defaults to US. If SMB customers are India-based, is `ap-south-1` required for MVP2 or deferrable? *(Impacts P1.)*
2. **Audit retention** — `proposed_mutations` holds full before/after snapshots. Indefinite retention, or a 24-month policy?
3. **Agent authority ceiling** — should `viewer` role be able to *invoke* the agent at all, or only see its outputs?

---

## Appendix A — Repository Layout

```
finhive/
├── api/                        # Vercel serverless entrypoints
│   ├── loans.py
│   ├── reports.py
│   ├── agent.py
│   └── admin.py
├── finhive/
│   ├── domain/                 # ← LIFTED FROM MVP1, UNCHANGED
│   │   ├── entities/
│   │   ├── value_objects/
│   │   ├── services/
│   │   └── repositories/       # interfaces
│   ├── calc/                   # ← LIFTED FROM MVP1 (pure functions)
│   ├── application/            # use cases, now async
│   ├── db/
│   │   ├── raw.py              # asyncpg pool
│   │   ├── loan_repository.py  # implements domain interface
│   │   └── admin.py            # ONLY place service_role is allowed
│   ├── agent/
│   │   ├── loop.py             # ReAct implementation
│   │   ├── registry.py         # @tool decorator
│   │   ├── tools/
│   │   ├── masking.py
│   │   └── metering.py
│   └── retrieval/
├── web/                        # React + Chakra SPA
│   ├── src/
│   │   ├── routes/
│   │   ├── components/
│   │   ├── hooks/useAgentStream.ts
│   │   └── theme.ts
│   └── content/                # MDX help docs
├── dbt/
│   ├── models/{staging,marts}/
│   └── tests/
├── migrations/                 # numbered forward-only SQL
├── evals/golden/               # agent eval dataset
├── tests/{unit,integration,e2e}/
└── .github/workflows/
```

## Appendix B — Resume Framing

The architecture above maps to these claims:

| Claim | Evidence in this document |
|---|---|
| Full-stack Python + React | §6, §15, Appendix A |
| Production AI agent integration | §11, §12 — ReAct loop with typed tools and a safety gate |
| LLM cost & observability ownership | §14 — per-turn metering, budget guards, eval harness |
| Data contract discipline | §10 — dbt contracts double-enforcing business rules |
| Security-first design | §8, §13 — RLS, JWT forwarding, PII masking, CI isolation tests |
| CI/CD and quality automation | §17, §18 — layered gates, CodeRabbit loop with bounded retries |
| Architectural judgment | §3 — explicitly *not* building microservices, and defending it |

> The strongest interview line in here is §3 plus §12: *"I chose not to build microservices at 3 DAU, and I made the agent incapable of writing to the database."* Both demonstrate restraint, which is scarcer than ambition.
