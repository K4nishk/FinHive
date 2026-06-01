# Proposal
## Enterprise MCP Tool — AI-Powered Code Generation Framework

# PART I — EXECUTIVE OVERVIEW

*The first 15–20 minutes of the conversation lives in this section. Everything below Part I is reference depth for the questions that come up.*

---

## 1. The Number

```
   ┌──────────────────────────────────────────────────────────────┐
   │                                                              │
   │   TODAY                              WITH THE TOOL           │
   │   ─────                              ──────────────          │
   │                                                              │
   │   240 data sources / year            240 data sources / year │
   │   ~130 hrs skilled work each         ~5 hrs review each      │
   │   2–3 weeks elapsed                   ~1 business day        │
   │   ~$15,000 per intake                 ~$600 per intake       │
   │                                                              │
   │   ═══════════════════                ═════════════════       │
   │   ~$3.6M / year                       ~$144K / year          │
   │                                                              │
   │                       ▼                                      │
   │                                                              │
   │           ANNUAL SAVINGS: ~$3.45M                            │
   │           STEADY-STATE ROI: ~170×                            │
   │           PHASE 1 PAYBACK: ~6 INTAKES                        │
   │                                                              │
   └──────────────────────────────────────────────────────────────┘
```

The bank spends approximately **$3.6 million per year** in skilled engineering time onboarding new data sources. The work is repetitive pattern-following at its core. The proposal is to automate the pattern-following with a governed AI tool, keeping humans on the decisions that genuinely require human judgment.

---

## 2. The Solution in One Picture

```
   Data Intake spec   ┌─────────────────────────────────────┐  Deployment-
   ───────────────►   │                                     │  ready bundle
                      │   MULTI-AGENT PIPELINE              │  ───────────►
   • source           │   (Bedrock: Claude + Codex)         │
   • load             │                                     │  • DDL / DCL
   • transform rules  │   1. Parse intake (+ PII anonymize) │  • ETL / SQL
   • target curation  │   2. Generate extraction code       │  • Liquibase
   • environments     │   ◄── Gate 1 (optional) ──►         │  • Airflow DAGs
                      │   3. Generate transform code        │  • DQ rules
                      │   4. Benchmark vs ground-truth      │  • Tests
                      │      (re-do if F1 < 0.85)           │  • AWS IaaC ◄──┐
                      │   5. Codex code review              │  • Per env:    │
                      │   ◄── Gate 2 (mandatory) ──►        │    DEV/QA/UAT  │
                      │   6. Generate curation artefacts    │    /PROD       │
                      │   7. Generate deployment + IaaC     │                │
                      │   ◄── Gate 3 (mandatory) ──►        │  + benchmark   │
                      │   8. Audit + ServiceNow record      │  + Codex review│
                      │                                     │  + audit trail │
                      └─────────────────────────────────────┘                │
                                                                             │
   ┌──────────────────────────────────────────────────────────────────────┐  │
   │  IaaC outputs include CDK / Terraform for Glue jobs, Lambda,         │ ◄┘
   │  IAM, S3, EventBridge, Step Functions — every AWS component          │
   │ the data pipeline depends on, generated alongside the data artefacts │
   └──────────────────────────────────────────────────────────────────────┘
```

**One submission. Eight specialized agents. Three human review gates. A complete artefact bundle including AWS infrastructure code.**

---

## 3. ROI Snapshot

| | Today | With the Tool | Δ |
|---|---:|---:|---:|
| Skilled hours per intake | 130 hrs | 5 hrs (review only) | **−96%** |
| Cost per intake | $15,000 | $600 | **−96%** |
| Elapsed time per intake | 2–3 weeks | ~1 business day | **−93%** |
| Annual cost (240 intakes) | **$3.6M** | $144K | **−$3.45M / yr** |
| | | | |
| Phase 1 PoC investment | | **~$55K** all-in | |
| Steady-state operating cost | | **~$6,500 / year** | |
| **Steady-state ROI** | | | **~170×** |

The $3.45M savings figure counts engineering effort only. Data sources landing 20 business days earlier each, 240 times per year, compounds into faster analytics, faster risk modelling, and faster product launches. That value is real but not in the savings line above.

---

## 4. Phased Delivery — Two Phases, Phase 3 Parked

```
   ┌─────────────────────────────────────────────────────────────────────┐
   │                                                                     │
   │   PHASE 1 — PROOF OF CONCEPT                          Weeks 1–12    │
   │   ─────────────────────────                                         │
   │   • Validate generation quality vs ground-truth                     │
   │   • Prove end-to-end ServiceNow gate flow                           │
   │   • Quantify real per-intake cost                                   │
   │   • 1–2 engineers · ~$3K cloud spend · ~$55K all-in                 │
   │                                  │                                  │
   │                                  ▼ acceptance gate                  │
   │                                                                     │
   │   PHASE 2 — PRODUCTION HARDENING                    Weeks 13–24     │
   │   ─────────────────────────────                                     │
   │   • SQS queue for durable async processing                          │
   │   • Prompt versioning with canary rollout regime                    │
   │   • Phoenix evaluation framework operational                        │
   │   • Confluence review surface fully live                            │
   │   • Operational runbooks, hook framework documented                 │
   │   • ~$6,500 / year steady-state operating cost                      │
   │                                  │                                  │
   │                                  ▼                                  │
   │                                                                     │
   │   PHASE 3 — PARKED                                  Future          │
   │   ────────────────                                                  │
   │ Multi-region DR + exponential scaling are not justified by the      │
   │ bank's actual workload (~1 intake / business day). The architecture │
   │ is DR-ready as a configuration change if requirements evolve.       │
   │                                                                     │
   └─────────────────────────────────────────────────────────────────────┘
```

The architecture is **deliberately right-sized** to the actual workload. Multi-region DR and ALB-tiered scaling were considered and rejected for Phase 2: with a 2-day SLA per intake and ~1 hour of machine processing time, a single worker clears a full month of volume in ~30 hours. Scaling is not the engineering problem to solve. Hardening is.

---

## 5. Architecture at a Glance

```
   Enterprise GPT / CLI
          │  MCP
          ▼
   ┌─────────────────────────┐
   │   MCP Server (Fargate)  │  thin, stateless, returns job ID
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │   Amazon SQS            │  durable buffering, DLQ, async
   └────────────┬────────────┘
                ▼
   ┌─────────────────────────┐
   │   Worker (Fargate)      │  LangGraph orchestrator
   │   8 specialized agents  │  • PII anonymize before any LLM
   │   Lifecycle hooks       │  • suspend at human gates
   └────────────┬────────────┘
                │
     ┌──────────┼──────────┬──────────────┬─────────────┐
     ▼          ▼          ▼              ▼             ▼
  Bedrock     S3        DynamoDB      Phoenix      ServiceNow
  ─ Opus 4.7  artefacts state +       LLM tracing  approval
   (GEN)      + IaaC    audit         + prompt     system of
  ─ Codex                              versioning   record
   (REVIEW)                            (self-host)
   ────────
   single egress: IAM, PrivateLink, Guardrails, CloudTrail
```

**Key architectural decisions** *(detail in Part II)*

| Decision | Choice | Why |
|----------|--------|-----|
| Queueing vs Load Balancing | SQS queue | Workload is async at ~1/day, not interactive at scale |
| Model egress | Single Bedrock path for both Claude and Codex | Eliminates external API egress concern |
| Durable state | DynamoDB | Pipelines suspend at human gates for days; cache is wrong tool |
| Approval system of record | ServiceNow | Bank-grade change management, not engineering ticketing |
| Knowledge layer | Hybrid RAG + CAG | Cache stable standards; retrieve large dynamic SOPs |
| Observability | Phoenix (self-hosted on Fargate) | Data stays in AWS boundary; native LangGraph |
| DR posture | DR-ready by configuration, not built up-front | Right-sized to actual criticality |

---

## 6. Stakeholders

```
   BUILT WITH                                USED BY
   ──────────                                ───────
   • Principal Engineers (standards)        • Data Engineers (submit + review)
   • Data Engineers (ground-truth + Gate 1) • Business Analysts (intake authors)
   • DBAs (DDL/DCL standards)               • Tech Leads (Gate 3 approval)
   • Data Modellers (schema standards)      • Release Managers (Gate 3)
   • Business Analysts (Gate 2)             • Business Owners (initiators)
   • QA Engineers (benchmark standards)     • Platform Engineers (hooks + ops)
   • SREs (IaaC conventions + platform)     • Managers (dashboards + approvals)
   • Directors (governance + funding)
   • Compliance / Audit (prompt gov.)
```

The tool **concentrates skilled engineering time on the decisions that require judgment** (the three gates) and removes it from the work that doesn't (boilerplate generation, environment differentiation, repeating the same patterns). It is not a role-replacement tool.

---

## 7. The Ask

```
   1. ENDORSE the phased approach
      Phase 1 → Phase 2 → (Phase 3 parked)
      Each phase gated to the next by acceptance criteria.

   2. FUND Phase 1
      12 weeks · 1–2 engineers · ~$3K cloud spend · ~$55K all-in
      Output: working PoC + measured quality + measured cost.

   3. DIRECT on two open architectural questions
      • MCP connectivity model to the Enterprise GPT
      • Cheaper-tier model selection for low-complexity intakes
      (Both isolated behind abstractions; neither blocks Phase 1.)

   4. UNLOCK stakeholder access
      • Principal Engineer time for CAG standards curation (~6 hrs)
      • DBA + Data Modeller validation time (~6 hrs)
      • Compliance review of prompt-versioning governance (~3 hrs)

   5. SPONSOR Phase 2
      Conditional on Phase 1 acceptance, MD-level sponsorship so the
      Phase 2 commitment doesn't require re-pitching from cold.
```

---

# PART II — TECHNICAL DEPTH

*Reference material for the detailed technical conversation. Organized by topic for easy navigation.*

---

## 8. System Design

### 8.1 Why a Queue, Not a Load Balancer

The architectural reasoning is workload-shape, not preference. An intake takes minutes to hours of machine time to fully process — and *days* when human gate suspensions are counted. The caller does not wait synchronously; the caller submits and gets notified on completion. A load balancer is the right primitive for interactive, synchronous, throughput-constrained traffic. None of those characteristics describe this workload.

SQS provides exactly what is needed: durable buffering, natural async semantics, retries via visibility timeouts, a dead-letter queue for failed intakes, and effectively zero idle cost. Scaling, when and if it ever becomes a real concern, is a configuration change — add more worker tasks consuming the same queue. There is no coordination problem, no session affinity, no load-balancer tuning.

The arithmetic for right-sizing: with a 2-day SLA per intake, ~1 hour of average machine processing time, a single worker clears ~30 intakes (a month of volume) in just over 30 hours. The bank's workload is roughly one intake per business day. The architecture is sized appropriately; it is not over-engineered for a scaling scenario that does not exist.

### 8.2 The Multi-Agent Pipeline in Detail

| # | Agent | What it does | Model |
|---|-------|-------------|-------|
| 1 | **Intake Parser** | Validates intake against schema, anonymizes PII column names before any AI sees them, retrieves source-specific SOP context from Confluence via RAG | none (deterministic + RAG) |
| 2 | **Extraction Agent** | Generates SQL/PySpark for source extraction including watermarking, partitioning, connection handling | Claude Opus 4.7 |
| 3 | **Transform Agent** | Two-step generation: decomposes business rules into structured intermediate components, validates, then synthesizes final transformation SQL | Claude Opus 4.7 |
| 4 | **Benchmark Agent** | Scores generated output against ground-truth in `input/sql/` (1000+ objects) and `input/py/` (100+ objects); F1, accuracy, structural similarity | none (deterministic) |
| 5 | **Review Agent** | Independent Codex code review of generated artefacts — correctness, security, standards drift | GPT-5.3 Codex |
| 6 | **Curation Agent** | Produces Gold-layer DDL, DCL grants, DQ rules, Liquibase changesets | Claude Opus 4.7 |
| 7 | **Deploy Agent** | Produces per-environment configs (DEV/QA/UAT/PROD), Airflow DAGs, and **AWS Infrastructure-as-Code** (CDK/Terraform for Glue, Lambda, IAM, S3, EventBridge, Step Functions) | Claude Opus 4.7 |
| 8 | **Audit Agent** | Records immutable audit event chain with prompt version, model invocation, gate decisions | none (integration) |

The re-work loop fires when the Benchmark Agent scores fall below threshold (F1 < 0.85 or accuracy < 0.90) — the Transform Agent regenerates with feedback up to 3 times, then escalates to mandatory human review regardless of score.

### 8.3 Model Strategy — Single Bedrock Egress

| Role | Model | Why this model | Pricing |
|------|-------|----------------|---------|
| **Generation** | Claude Opus 4.7 via Bedrock | Strongest agentic code generation; 1M context window enables CAG; prompt caching drops cached-token reads to one-tenth price | $5 / $25 per MTok (in/out) |
| **Review** | GPT-5.3 Codex via Bedrock | Purpose-built for code review; the model OpenAI's own review feature uses; independent second opinion from a different family | $1.75 / $14 per MTok (in/out) |

**Both models reach inference through Amazon Bedrock.** Codex on Bedrock has been generally available since April 28, 2026. The architectural consequence is significant: a single egress path under IAM, PrivateLink, Guardrails, and CloudTrail. No external API egress. No separate credential management. No governed-egress security concern.

Both are addressed through a configurable model-role abstraction; adopting a newer Opus or Codex release is a config change, not a redesign.

### 8.4 State Architecture

| State Class | Lifetime | Access Pattern | Store |
|------------|---------|---------------|-------|
| Durable pipeline state | Hours to days (human gates) | Write-once-per-step, read at gate resolution | **DynamoDB** with PITR enabled |
| Audit trail | Compliance retention | Append-only, read at audit time | **DynamoDB** (or DynamoDB → S3 archive) |
| Ephemeral working memory | One pipeline run | High-frequency reads within a run | **Deferred** — volume doesn't justify a Redis cluster yet |

A pipeline can be suspended at a human gate for 24–72 hours. The Fargate worker running it will be recycled long before the human responds. State must survive that — which is a durability requirement, not a caching opportunity. DynamoDB on-demand fits the access pattern (write-once-per-step, bursty) and the criticality (single-digit-ms reads with full durability and point-in-time recovery).

Redis was scoped for the original Phase 2 to accelerate a hot path that does not yet exist at this workload. Adding a standing Redis cluster for a workload of one intake per business day is paying for capacity that isn't used. Redis is deferred until production usage demonstrates a hot path that justifies it.

### 8.5 Human-in-the-Loop Gates — ServiceNow as System of Record

| Gate | Trigger | Reviewers | Status |
|------|---------|-----------|--------|
| **Gate 1** | After extraction generation | Senior Data Engineer | **Optional** — auto-passed via `PreGate` hook for low-complexity sources with established SOPs |
| **Gate 2** | After transform generation + Codex review | BSA + Data Engineer | **Mandatory** — reviewed in Confluence side-by-side surface |
| **Gate 3** | After deployment bundle assembly | Tech Lead + Release Manager | **Mandatory** — change-management approval |

ServiceNow is the system of record because the artefact being approved is a deployment-ready bundle bound for production data pipelines in a regulated bank — that is a change-management event in the regulator's language, not an engineering task. ServiceNow models approvers as roles with delegation, escalation, and substitution; it produces audit evidence in the format compliance already accepts. Putting approvals where audit already inspects removes a class of evidence-gathering work. Confluence is the review-content surface (artefacts beside ground-truth, with benchmark scores). Microsoft Teams carries notifications. JIRA continues to track engineering work, decoupled from the approval lifecycle.

### 8.6 Lifecycle Hooks — Governed Extensibility

Nine intercept points where engineer-registered handlers can observe, mutate, or veto:

```
   PreIntake  PreGeneration    PreReview          PreGate           PreDeploy
       │           │                │                │                  │
       ▼           ▼                ▼                ▼                  ▼
   [intake]─────────[generate]─────────[review]────────[gate decision]────[deploy bundle]────[audit]
                              ▲                ▲                      ▲                   ▲
                              │                │                      │                   │
                        PostGeneration    PostReview              PostGate             OnError
```

Hooks are the governed extension point. A team enforces a bank-specific masking rule at `PostGeneration`; security adds a custom scan at `PreReview`; the Gate 1 auto-pass for low-complexity sources is a `PreGate` hook — not a special case in the orchestrator. Hook registration, ordering, and what each hook touched are themselves audited.

---

## 9. Knowledge Layer — RAG + CAG

Two complementary approaches to putting enterprise knowledge in front of the AI models, used together because they solve different problems.

```
   ┌────────────────────────────────────────────────────────────┐
   │                  GENERATION PROMPT ASSEMBLY                │
   │                                                            │
   │   ┌──────────────────────┐    ┌──────────────────────┐     │
   │   │ CACHED PREFIX (CAG)  │    │  RETRIEVED (RAG)     │     │
   │   │                      │    │                      │     │
   │   │ • coding standards   │    │ • source-specific    │     │
   │   │ • naming conventions │    │   SOP sections       │     │
   │   │ • Liquibase templates│    │   (from Confluence)  │     │
   │   │ • IaaC conventions   │    │ • similar past       │     │
   │   │ • curated exemplars  │    │   intake examples    │     │
   │   │   from 1000+ SQL /   │    │                      │     │
   │   │   100+ Python objects│    │                      │     │
   │   │                      │    │                      │     │
   │   │ STABLE + REUSED      │    │ LARGE + DYNAMIC      │     │
   │   │ $0.50 / MTok cached  │    │ retrieved per-intake │     │
   │   │ (vs $5.00 standard)  │    │                      │     │
   │   └──────────────────────┘    └──────────────────────┘     │
   │                │                            │              │
   │                └────────────┬───────────────┘              │
   │                             ▼                              │
   │                + per-intake dynamic input                  │
   │                  (the specific intake payload)             │
   └────────────────────────────────────────────────────────────┘
```

**The design rule:** cache what is stable and reused; retrieve what is large and varies. The hybrid minimizes retrieval risk (RAG can miss; CAG cannot) and token cost (most-repeated tokens billed at one-tenth the standard rate via cache reads). For the actual numbers: per-intake model cost is ~$1.94 interactive / ~$1.15 batched, with the cached prefix contributing ~$0.03 versus ~$0.28 unbatched and uncached.

---

## 10. What the Tool Produces

```
   artefacts/
   └── INTAKE-2026-0531-001/
       ├── DEV/
       │   ├── ddl/              table, view, schema definitions
       │   ├── dcl/              role grants, access control
       │   ├── etl/              Glue jobs, PySpark scripts
       │   ├── liquibase/        versioned changesets
       │   ├── airflow/          orchestration DAGs
       │   ├── dq/               data quality rules
       │   ├── tests/            test fixtures + assertions
       │   ├── config/           environment configuration
       │   └── iaac/             ◄── AWS Infrastructure as Code
       │       ├── cdk/              • Glue stacks
       │       │   ├── glue-stack.ts • Lambda configs
       │       │   ├── lambda-stack.ts • IAM roles + policies
       │       │   ├── iam-stack.ts  • S3 buckets + KMS
       │       │   ├── s3-stack.ts   • EventBridge schedules
       │       │   └── eventbridge-stack.ts  • Step Functions
       │       └── terraform/        (alternative IaaC option)
       ├── QA/   (same structure, QA-specific configs)
       ├── UAT/  (same structure, UAT-specific configs)
       ├── PROD/ (same structure, PROD-specific configs)
       └── reports/
           ├── benchmark_report.json    F1, accuracy vs ground-truth
           ├── codex_review.md          automated code review
           ├── prompt_versions.json     ◄── exact prompts used (audit)
           ├── audit_trail.json         full event log
           └── servicenow_decisions.json human approvals captured
```

**Why IaaC outputs matter.** The same SRE bottleneck that exists today on data-layer artefacts exists on the AWS infrastructure that supports them — Glue jobs, Lambda, IAM, S3, EventBridge are all hand-rolled per onboarding. The Deploy Agent generates them from the intake against SRE-approved conventions, just as it generates the data-layer artefacts. Auditability also closes: every cloud component is traceable back to the intake and the prompt version that produced it.

---

## 11. Prompt Versioning & Governance

*This is the section compliance and legal will read carefully.*

### 11.1 The Audit Question

If an artefact in production is later found to have a defect, the auditor asks three questions: (1) what exactly was generated, (2) what prompt produced it, and (3) who approved the prompt. The system answers all three in seconds.

### 11.2 The Versioning Architecture

```
   ┌──────────────────────────────────────────────────────────────┐
   │                                                              │
   │  SOURCE OF TRUTH — Git                                       │
   │  ────────────────────                                        │
   │  prompts/extraction/v3.2.0.md     semver-tagged, PR-reviewed │
   │  prompts/transform/v4.1.0.md      immutable once merged      │
   │  prompts/curation/v2.8.0.md                                  │
   │  prompts/deploy/v1.5.0.md                                    │
   │  prompts/review/v2.0.0.md                                    │
   │                          │                                   │
   │                          ▼                                   │
   │  CI/CD                                                       │
   │  ────                                                        │
   │  • runs prompt regression suite against curated intakes      │
   │  • publishes to S3 with object versioning enabled            │
   │  • tags S3 object with Git commit hash + semver              │
   │  • canary rollout: 10% traffic × 48 hrs, monitored by Phoenix│
   │                          │                                   │
   │                          ▼                                   │
   │  RUNTIME — S3 versioned, immutable                           │
   │  ────────────────────────────                                │
   │  Workers read a SPECIFIC version, never "latest"             │
   │                          │                                   │
   │                          ▼                                   │
   │  AUDIT — DynamoDB record for every generation                │
   │  ────────────────────────────────────────                    │
   │  {                                                           │
   │    intake_id, agent, prompt_name, prompt_version,            │
   │    prompt_sha256, git_commit, s3_version_id,                 │
   │    model_id, model_invocation_id, phoenix_trace_id           │
   │  }                                                           │
   │                                                              │
   └──────────────────────────────────────────────────────────────┘
```

### 11.3 The Approval Workflow for Prompt Changes

A prompt change is a control change. The PR review process carries the same weight as a production application code change:

1. Engineer raises a PR against the prompts repository
2. CI runs the prompt regression test suite — must pass
3. Required approvers sign off: **Principal Engineer + DE Lead + Compliance Officer**
4. For prompts affecting regulated outputs (DDL, DCL grants), an additional **ServiceNow Change Request** must be approved
5. Merge triggers CI/CD which publishes to S3 (immutable, versioned)
6. Canary rollout — new version takes 10% of traffic for 48 hours
7. Full rollout — only after canary holds against Phoenix eval scores

**This regime inherits BMO's existing engineering and change-management controls rather than inventing a parallel regime.** That property matters — it means the prompt-versioning approach is novel only in its applicability to AI prompts, not in its governance model.

### 11.4 Operational Benefits Beyond Audit

| Capability | Mechanism |
|------------|-----------|
| **Regression analysis** | Phoenix evals score production traces continuously; a regression after a prompt change surfaces in the dashboard before it surfaces as a defect |
| **A/B comparison** | Two versions run side-by-side on partitioned traffic; Phoenix reports which performs better against eval rubrics |
| **Replay** | Given a past generation, retrieve the exact prompt version and re-run for diagnostic investigation |
| **Instant rollback** | Workers configured against a specific S3 version — rollback is a config update, not a code deployment |

---

## 12. Observability with Phoenix

### 12.1 Why Phoenix Was Chosen

Phoenix is open source (Elastic License 2.0), self-hostable, and built on OpenTelemetry with native LangChain/LangGraph instrumentation via OpenInference. The selection was made against four credible alternatives:

| Option | Why Not |
|--------|---------|
| LangSmith | SaaS; self-host requires Enterprise tier; vendor coupling to LangChain ecosystem |
| Langfuse | Strong option; Phoenix chosen for stronger built-in eval framework + prompt management |
| Datadog LLM | Heavy per-host pricing; weaker LLM-specific eval support |
| CloudWatch alone | Insufficient — no multi-agent tracing, no token-level analysis, no eval framework |

**The decisive property for a regulated bank: self-hostable.** Phoenix runs as a Docker container on Fargate, backed by RDS PostgreSQL. All telemetry, all prompts, all evaluations stay inside the AWS boundary. Nothing leaves to a third-party SaaS.

### 12.2 What Phoenix Captures Per Pipeline Run

```
   Phoenix Trace (one intake)
   ├── intake_parser   (35ms)
   ├── extraction_agent
   │   ├── prompt_load     (5ms, prompt v3.2.0)
   │   ├── bedrock_call    (12s, opus-4-7)
   │   │     • input: 47K tokens (cached: 42K)
   │   │     • output: 8K tokens
   │   │     • cost: $0.21
   │   └── post_processing (60ms)
   ├── transform_agent
   │   ├── intermediary_decomposition
   │   ├── intermediary_validation
   │   └── sql_synthesis (bedrock_call)
   ├── benchmark_agent
   │   • F1: 0.91, accuracy: 0.94 → passes
   ├── review_agent
   │   • bedrock_call (codex)
   │   • 3 findings, 0 blocking
   ├── [gate_2 — suspended 4h 32m]
   ├── curation_agent
   ├── deploy_agent
   └── audit_agent
```

Captured per generation: prompt name + version + content hash; model + invocation ID; input/output tokens including cached reads; latency; errors and retries; benchmark scores; gate decisions and reviewer identity.

### 12.3 Phoenix and CloudWatch — Complementary Stacks

```
   Phoenix (self-hosted Fargate + RDS)     CloudWatch (AWS native)
   ───────────────────────────────────     ───────────────────────
   • multi-agent traces                    • Fargate CPU / memory
   • prompt-version tracking               • SQS queue depth + age
   • token + cost per call                 • DynamoDB request metrics
   • continuous evaluations                • Bedrock invocation logs
   • A/B prompt comparison                 • IAM / CloudTrail audit
                  │                                  │
                  └──────────────┬───────────────────┘
                                 ▼
                  Microsoft Teams alerts on:
                  • F1 regression (Phoenix)
                  • Cost anomaly (CloudWatch)
                  • Queue stalled (CloudWatch)
                  • Bedrock throttling (CloudWatch)
                  • Prompt eval failure (Phoenix)
```

### 12.4 Continuous Evaluation

Phoenix's evaluation framework continuously scores production traces against quality rubrics. A drop in F1 against the rolling baseline alerts, the offending prompt version is identifiable from the trace, and the canary regime catches problematic versions in the 48-hour window before they reach full traffic.

---

## 13. Cost Model — Detailed

### 13.1 Per-Intake Token Economics

| Component | Tokens | Rate | Cost |
|-----------|--------|------|------|
| Generation — cached prefix (CAG) | ~50K | $0.50/MTok | ~$0.03 |
| Generation — dynamic input (intake + RAG) | ~25K | $5.00/MTok | ~$0.13 |
| Generation — output (4-env artefacts + IaaC) | ~40K | $25.00/MTok | ~$1.00 |
| Re-work amortization (~0.5 extra pass avg) | — | — | ~$0.55 |
| Review — Codex input | ~50K | $1.75/MTok | ~$0.09 |
| Review — Codex output | ~10K | $14.00/MTok | ~$0.14 |
| **Per-intake model cost (interactive, cached)** | | | **~$1.94** |
| Same intake via Batch API (50% off generation) | | | **~$1.15** |

### 13.2 Monthly Operating Cost

| Line item | Phase 1 (PoC) | Phase 2 (Production) |
|-----------|--------------:|---------------------:|
| Model — Bedrock (Claude + Codex) | ~$50 | ~$50 |
| Fargate (MCP + worker) | ~$80 | ~$120 |
| Phoenix (Fargate + RDS) | ~$60 | ~$120 |
| SQS | $0 | <$5 |
| DynamoDB | ~$20 | ~$30 |
| S3 (artefacts + prompts) | ~$10 | ~$30 |
| OpenSearch Serverless (RAG) | ~$80 | ~$120 |
| Bedrock VPC endpoint | ~$20 | ~$30 |
| CloudWatch | ~$20 | ~$40 |
| **Monthly total** | **~$340** | **~$545** |
| **Annual total** | **~$4,100** | **~$6,500** |

### 13.3 Cost Levers (Order of Impact)

1. **Prompt caching** on static context — most-repeated tokens at $0.50/MTok vs $5.00/MTok. Effectively free to adopt.
2. **Batch API** for non-interactive intakes — flat 50% off generation, for any intake tolerant of async return. Most onboarding work qualifies.
3. **Complexity-based routing** — reserve Opus 4.7 for intakes that need it; route lower-complexity work to a cheaper tier *(model TBD pending direction)*.
4. **Output discipline** — generate diffs across environments rather than full re-emission per environment.

---

# PART III — GOVERNANCE & RISK

---

## 14. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| AI generates subtly wrong output that passes benchmark | Medium | High | Mandatory Gates 2 + 3; Codex independent review visible to reviewer; benchmark threshold F1 ≥ 0.85 |
| Reviewer bottleneck at gates | Medium | Medium | ServiceNow timeouts + escalation; reviewer rotation; Gate 1 optional via hook |
| Prompt regression after a prompt change | Medium | Medium | PR approval gates; regression test suite; canary rollout monitored by Phoenix evals; S3 versioning enables instant rollback |
| Ground-truth coverage gaps for new intake types | High initially | Medium | Structural-similarity fallback flagged for mandatory human review; evidence-driven corpus expansion after Phase 2 |
| PII leakage in prompts | Low | High | PII column names anonymized before prompt assembly; Bedrock Guardrails screen responses; CloudTrail audits every model call |
| Cost overrun | Low | Medium | Per-intake cost dashboard; AWS Budgets + Cost Anomaly Detection; queue architecture means runaway cost requires runaway volume |
| ServiceNow workflow change-resistance | Medium | Medium | Modelled on existing CAB process; reviewer onboarding sessions; runbook |
| Tool failure during a pipeline run | Low | Low | SQS DLQ; LangGraph checkpointing enables resumption from last completed agent |
| MCP connectivity uncertainty | Medium | Low | Transport layer isolates auth mechanism; interim mechanism for PoC if standard not finalized |

---

## 15. Open Questions Requiring Direction

Two questions remain open. Neither blocks Phase 1.

**MCP connectivity model to the Enterprise GPT.** Handshake, token issuance, and trust model depend on the enterprise's MCP connectivity standard. The transport layer is built to absorb whatever mechanism is ultimately chosen.

**Cheaper generation tier for low-complexity intakes.** Model selection and complexity threshold for routing — Opus 4.7 reserved for intakes that need it, cheaper tier for the rest.

Both are isolated behind abstractions in the design.

---

## 16. Phase 1 Acceptance Criteria

Phase 1 is accepted when **all six** are demonstrably met:

1. End-to-end intake-to-artefact-bundle generation runs successfully on 20+ representative intakes from the existing corpus
2. Benchmark F1 ≥ 0.85 and accuracy ≥ 0.90 against ground-truth on 80%+ of intakes
3. ServiceNow gate flow operates end-to-end with reviewer decisions resuming the suspended pipeline
4. Phoenix captures full traces with prompt-version correlation
5. Every artefact is auditable back to the exact prompt version that produced it
6. Per-intake cost (model + infrastructure) measured and within projected range (~$1.94 interactive / ~$1.15 batched + amortized infra)

---

## 17. Phase 2 Acceptance Criteria

Phase 2 is accepted when **all six** are demonstrably met:

1. Service operates as a shared utility with at least 20 successful production onboardings
2. Prompt versioning operates end-to-end including a canary rollout exercise
3. Phoenix evaluation framework continuously scores production traces and surfaces regressions
4. Tool operating cost measured within projection (~$545/month)
5. Average onboarding elapsed time reduced from baseline 2–3 weeks to ≤ 2 business days
6. Documentation and runbooks complete; platform team operates the service without builder involvement

---

## 18. Closing

The proposal compressed to one paragraph: BMO spends ~$3.6M / year on engineering effort onboarding data sources. The work is repetitive pattern-following at its core. A governed AI tool — eight specialized agents, three mandatory human gates, single Bedrock egress for both Claude and Codex, ServiceNow as approval system of record, Phoenix self-hosted for LLM observability, prompt versioning that inherits the bank's existing change-management regime — automates the pattern-following and concentrates skilled engineering time on the gate decisions that genuinely require human judgment. The architecture is right-sized to the actual workload (~1 intake / business day) rather than to a hypothetical enterprise scaling scenario. Phase 1 is 12 weeks and ~$55K all-in. Steady-state annual saving is ~$3.45M. Steady-state ROI is ~170×. Phase 1 payback is ~6 intakes.

The ask: endorse the phased approach, fund Phase 1, direct on the two open architectural questions, unlock the stakeholder access needed, sponsor Phase 2 conditional on Phase 1 acceptance.

---
