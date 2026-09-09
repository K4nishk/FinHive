# Architecture Reference Document — FinHive Loan Manager MVP2

**Version**: 2.3.0
**Status**: DRAFT — one decision needs your call (§5)
**Date**: 2026-09-08
**Extends**: `mvp2_ard_v2.2.0.md` (ADR-2.3) · `ARB_DECISIONS.md`
**Adds**: ADR-2.4 — NPI scope: encrypting financial values at rest

---

## What v2.3.0 adds

Decision 10 expanded encryption from names to **all financial values** — principal, interest, commission, TDS, CHQ, rates — on an NPI rationale.

That is a materially larger change than adding two more name columns, and it breaks things names did not. This version documents the scope, the mechanism difference, and the four consequences.

---

## 1. ADR-2.4 — NPI scope for encryption at rest

**Status**: Accepted (mechanism) · one open question in §5
**Extends**: ADR-2.3, which covered identity fields only

### Framing — mandatory, and where the mandate comes from

**NPI protection is mandatory on this project.** It is not a nice-to-have, not a phase-two hardening item, and not subject to trade-off against delivery speed. Any code path that writes an unencrypted NPI field is a defect of the same severity as a cross-tenant data leak.

The mandate is **FinHive engineering policy**, with its scope definition taken from GLBA and PIPEDA: *NPI is any information about a consumer resulting from a transaction* — loan balances, approved amounts, transaction history and the terms attached to them.

One precision that matters for the ARB submission, and only for the wording:

> GLBA binds US financial institutions; PIPEDA binds Canadian organisations. FinHive's current users are Indian SMBs, so neither statute reaches them *today*. The obligation here is therefore **self-imposed and internally binding**, and it is a **prerequisite for any future US or Canadian market entry** — where it would become statutory.
>
> Write it as *"FinHive mandates GLBA-equivalent NPI protection"*, not *"GLBA requires us to"*. The first is true, binding, and a strength in front of a board. The second is a factual claim an auditor can check and disprove, and disproving one claim invites scrutiny of every other claim in the document.

The engineering consequence is identical either way: everything below is mandatory.

### What is encrypted, revised

| Field | Encrypted | Blind index | Reason |
|---|---|---|---|
| `borrower_name`, `depositor_name` | ✅ | ✅ | Identity (ADR-2.3) |
| `borrower_group`, `depositor_group` | ✅ | ✅ | A business name identifies a business |
| **`amount`** (principal) | ✅ | ❌ **never** | NPI — loan balance |
| **`interest_amount`, `commission_amount`, `tds_amount`, `chq_amount`** | ✅ | ❌ **never** | NPI — computed transaction values |
| **`proposed_mutations.before_state` / `.after_state`** | ✅ | ❌ | JSONB snapshots contain amounts |
| **`agent_turns.react_trace`** | ✅ | ❌ | Tool outputs in the trace contain amounts |
| **Cold archive partitions (Blob)** | ✅ | — | 7-year retention of NPI |
| `interest_rate`, `commission_rate` | ❌ | — | **Decision 13** — a percentage is not a balance and identifies no one |
| `giving_date`, `due_date`, `due_period`, `extension_period` | ❌ | — | **Decision 14** — needed for date arithmetic and range filters |
| `reference_id`, `status`, `is_active`, `org_id` | ❌ | — | System-generated |

#### Leaving rates in plaintext is safe — the derivation check

Worth showing the working, because "encrypt the amount but not the rate" looks like a gap until you check whether the plaintext columns let you solve for the ciphertext ones.

MVP1's formula is `interest = (amount × rate × period) / 1200`. In plaintext an attacker with the database has `rate`, `period` and the dates. Encrypted are `amount`, `interest_amount`, `commission_amount`, `tds_amount`, `chq_amount`.

Recovering `amount` needs **two** of the three terms. The attacker has one — the rate — and every amount on both sides of the equation is ciphertext. `tds = 0.1 × interest` and `chq = interest − tds` are derived from encrypted values and add nothing. **There is no derivation path from the plaintext columns to any financial value.**

What a rate column does leak is the *distribution of terms* across the book — that some loans carry 12% and others 18%. That is commercially mildly interesting and identifies nobody. Acceptable.

> This check has to be redone if a plaintext column carrying a *derived* financial value is ever added. A `total_repayable` or `outstanding_days × rate` helper column in plaintext would immediately open a solve path back to `amount`. Encrypt any new financial column by default, and re-run this analysis before making an exception.

### ⚠️ Do **not** put a blind index on an amount

The name pattern is ciphertext **plus** an HMAC blind index for equality. Applying that same pattern to amounts would be actively harmful, and it is the mistake most likely to be made by someone implementing this from the ADR-2.3 pattern alone.

Loan amounts are **low-cardinality and highly clustered**: real books are full of ₹10,000, ₹15,000, ₹20,000, ₹50,000. A deterministic index over that distribution is trivially reversible — count the distinct index values, rank them by frequency, and map them onto the obvious round numbers. You would recover most of the loan book without touching the encryption key.

Names are also low-cardinality, but a name's frequency distribution does not have an obvious public prior to map onto. Round rupee amounts do.

**Therefore**: amounts get AES-256-GCM with a random IV and **no derived index of any kind** — no blind index, no order-preserving encryption, no format-preserving encryption. Order-preserving encryption is worse still: it leaks the full ranking of the loan book by design, which is close to leaking the book.

**Consequence**: no equality filter, no range filter and no `ORDER BY` on any amount at the database level. All three move to the application layer.

---

## 2. What this breaks, and what replaces it

### 2.1 Sorting and range filtering on amounts

MVP1 supports numerical sorting on `amount` (parity check A2.1) and the calculator filters do not range-filter on amount — so the loss is bounded.

**Replacement**: the same fetch-filtered-set → decrypt → sort → slice path already built for names (M1a). Amounts join it. Bounded at ~1,500 rows, so still sub-millisecond.

### 2.2 `LoanTotals` can no longer be summed in SQL

v2.1.0 §2 specified `totals` in every list response, computed over the filtered set, so the footer and the table could not disagree.

**Replacement**: the app decrypts the fetched set and sums in Python using `Decimal`. The guarantee is preserved — the totals still come from exactly the rows returned — but the computation moves. One upside: `Decimal` summation in the app is more obviously correct than relying on SQL numeric types.

**Constraint created**: totals cannot be computed over a set larger than the one fetched. At 1,500 rows that is never a problem; at 100k it would be. That is the trigger to revisit.

### 2.3 dbt loses financial aggregation — the real cost

This is the largest architectural loss and it deserves to be named plainly.

dbt is SQL in the warehouse. It has no key and cannot decrypt. So `fct_outstanding_balance`, `agg_portfolio_summary` and every amount-bearing mart cannot be computed in dbt.

Worse, the **dbt contract test asserting MVP1's monthly interest formula** — `interest_accrued = (principal × rate × periods) / 1200` — dies with it. That test was one of the strongest arguments in v2.0.0 §10: the business rule had two independent enforcers, in different languages, that had to agree.

**What replaces it:**

| dbt keeps | dbt loses |
|---|---|
| Shape contracts — column presence, types, nullability | Amount arithmetic |
| Enum validity (`status`, `period_type`) | Aggregation over financial values |
| Referential integrity, uniqueness of `reference_id` | The interest-formula assertion in SQL |
| Date logic and freshness | Outstanding-balance marts |
| Row counts and null rates | |

Financial aggregation moves to an **app-layer materialization job**: decrypt → compute with `Decimal` → re-encrypt → write the mart. Scheduled in GitHub Actions alongside dbt, not inside a Vercel function.

**The double-enforcement is genuinely weakened.** Two Python implementations of the same formula can share a Python bug in a way that a Python implementation and a SQL implementation cannot. The honest mitigation is a *property-based* test — generate random amounts, rates and periods, assert the materialization job and `InterestCalculator` agree across thousands of cases — which catches divergence even though it does not restore language independence. I am not going to claim it is as good. It is not.

### 2.4 Database-level constraints move to the app

`CHECK (amount >= 0)` cannot run on ciphertext, and the column becomes `BYTEA` rather than `INTEGER`, so the type guarantee is gone too.

**Replacement**: the `Money` value object (lifted unchanged from MVP1) becomes the *only* enforcement of non-negativity and integrality. That raises its importance — it goes from a nicety to the sole guard — so it needs a test asserting it rejects every invalid construction, and the repository layer must never bypass it.

---

## 3. The agent consequence — amounts and the LLM

**This is the part of the change with the widest blast radius, and it needs your decision (§5).**

ARD v2.0.0 §13 said explicitly: *"What is never masked: amounts, dates, reference IDs, statuses. The agent needs these to reason, and none identify a person on their own."*

If amounts are NPI, that sentence no longer holds. Sending ₹45,000 against a masked `PERSON_1` still transmits NPI to a US inference provider.

### Option A — send amounts, rely on the service-provider posture

The transfer is TLS-protected and Groq holds zero-retention terms. Under GLBA's Safeguards Rule this is the ordinary service-provider pattern, and it is defensible.

But it sits oddly beside a decision to encrypt those same values at rest under a voluntarily stricter baseline. Encrypting a number in the database and then posting it to a third party is not incoherent, but it is a posture you would have to explain.

### Option B — tokenise amounts too, and let tools do all arithmetic

Extend the existing session-scoped tokeniser: `₹45,000` → `AMOUNT_1`, rehydrated on the way out, exactly as names already work.

The obvious objection is that the agent then cannot reason about magnitude — it cannot say which loan is largest or what the total is.

**The answer is that it should not have been doing that anyway.** LLMs are unreliable at arithmetic, and this application is about money. Under Option B:

- `get_portfolio_summary` decrypts, sums with `Decimal`, and returns `TOTAL_1`
- `query_loans` sorts server-side and returns rows already in order
- `calculate_interest` computes with the MVP1 calculator and returns `AMOUNT_7`
- The agent **narrates** results it did not compute

So the rule becomes: **tools compute, the agent narrates. The agent never performs arithmetic on a financial value.**

That is a compliance posture *and* a correctness improvement, and it is the kind of constraint that makes an agent more trustworthy rather than less capable.

**Cost, stated honestly**: any question whose answer requires reasoning over magnitudes the tools did not pre-compute becomes unanswerable until a tool is added for it. "Which borrower owes the most?" needs `query_loans` to support ranking. "Roughly what fraction is overdue?" needs the summary to carry it. That is a real constraint on agent flexibility, and it will surface as eval failures that look like capability gaps.

**Recommendation: Option B.** It keeps the at-rest and in-transit postures consistent, and it removes LLM arithmetic from a financial application — which I would want to do regardless of the compliance argument.

---

## 4. Consequences summary

| Area | Change |
|---|---|
| Sort / filter on amounts | DB → app layer (joins the existing decrypt-and-sort path) |
| `LoanTotals` | SQL `SUM` → app-layer `Decimal` summation |
| dbt | Keeps shape, enum, integrity, freshness contracts; loses financial aggregation and the interest-formula assertion |
| Financial marts | New app-layer materialization job (decrypt → compute → re-encrypt) |
| `amount >= 0` | DB CHECK → `Money` value object as sole guard |
| Cursor pagination | `amount` joins the encrypted set — cursors now only on `due_date`, `reference_id`, `created_at` |
| Audit tables | `proposed_mutations` snapshots and `agent_turns.react_trace` encrypted |
| 7-year archive | Cold Blob partitions encrypted |
| Agent | §5 decision — recommend tokenised amounts, tools compute |
| Performance | ~1 extra decrypt per loan row, 4–6 per report record. Negligible at this scale |

---

## 5. Decisions — all resolved 2026-09-08

| # | Question | Outcome |
|---|---|---|
| **12** | Amounts to the LLM | ✅ **Tokenise.** `AMOUNT_1`, rehydrated on the way out. Tools decrypt and compute; the agent narrates. No LLM arithmetic on financial values. |
| **13** | Encrypt `interest_rate` / `commission_rate`? | ✅ **No.** A percentage is not a balance and identifies no one. Derivation check above confirms no solve path back to `amount`. |
| **14** | Encrypt `due_period` / `extension_period`? | ✅ **No.** Small integers needed for date arithmetic and range queries. |

Decisions 1–11 are recorded in `ARB_DECISIONS.md`. **No open architectural decisions remain.**

---

## 6. Three things the ARB submission must state plainly

1. **NPI protection is mandatory, and the mandate is FinHive's own.** GLBA and PIPEDA supply the *definition* of NPI and the control standard; neither statute reaches Indian SMBs today. Write *"FinHive mandates GLBA-equivalent NPI protection"* — binding, true, and a prerequisite for US/Canadian market entry. Do not write *"GLBA requires us to"*: it is checkable, false today, and disproving one claim invites scrutiny of every other claim in the document.
2. **dbt's role shrinks materially.** The "two independent enforcers of the interest formula" property from v2.0.0 does not survive amount encryption. Property-based testing narrows the gap without restoring language independence. Accepted, and stated rather than glossed.
3. **No derived index on an amount is a hard rule, not a preference.** It is the one place where copying the ADR-2.3 identity pattern would create the exact vulnerability the encryption exists to prevent. It lives in the coding standards and in CI, not only in this document.
