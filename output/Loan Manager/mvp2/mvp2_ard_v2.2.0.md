# Architecture Reference Document — FinHive Loan Manager MVP2

**Version**: 2.2.0
**Status**: DRAFT — for review
**Date**: 2026-09-08
**Extends**: `mvp2_ard_v2.1.0.md` · `mvp2_ard_v2.0.0.md` · `ARB_DECISIONS.md`
**Adds**: ADR-2.3 (encryption at rest), the M1a/M1b split, and the local-first delivery posture

---

## What v2.2.0 adds

One architectural decision and one delivery-shape change:

1. **ADR-2.3 — PII encryption at rest with app-layer decryption.** Chosen mechanism, four rejected alternatives with reasons, and the three existing decisions it constrains.
2. **Local-first M1.** M1 splits into M1a (setup, login, encryption) and M1b (read then write). Hosted Supabase, RLS and region pinning defer to M3.

---

## 1. ADR-2.3 — Encryption at rest for PII

**Status**: Proposed — the mechanism is a decision for you
**Context**: ARB decision OQ-01 puts data in India and makes PII protection a compliance control, not hygiene. The M1 requirement is that PII is protected *before* it reaches the local database.
**Supersedes**: the "Mask PII at rest" ticket, which assumed deterministic tokenisation and would have failed MVP1 parity check A2.1.

### The constraint that eliminates most options

MVP1 supports **alphabetical sorting** on `borrower_name` and `depositor_name` (parity check A2.1), **exact-match filtering** on all four name/group fields (A5.8), **autocomplete** from existing values (A1.1), and **group auto-fill** by matching a name (A1.2).

Any mechanism that breaks sorting or equality fails the parity sweep. That is not a preference — it is the gate on M1b.

### Options considered

#### ❌ A · `pgcrypto` — encrypt inside Postgres

```sql
INSERT INTO loans (borrower_name) VALUES (pgp_sym_encrypt($1, $2));
```

**Rejected.** The key travels in the query. It lands in `pg_stat_statements`, in query logs, and in any connection trace — and the database process sees plaintext at encrypt time. The threat model here includes "someone reads the database file or its logs", so handing the database the key is circular. It also directly contradicts the requirement's wording: encrypted *before* it reaches the database.

#### ❌ B · Full-disk / filesystem encryption only (FileVault, BitLocker, TDE)

**Rejected as the sole control.** Protects a powered-off stolen laptop and nothing else. A running process, a support session, a backup copy, or a `pg_dump` all see plaintext. It satisfies no part of "masked before it is put into the database".

**Kept as defence in depth** — it costs nothing and covers a real case.

#### ❌ C · AES-GCM with a random IV, and nothing else

The correct primitive: authenticated encryption, tamper-evident, no plaintext leakage.

**Rejected alone.** A random IV means the same name encrypts differently every time. `WHERE borrower_name = ?` cannot match, `ORDER BY` sorts ciphertext, autocomplete cannot group. It breaks A1.1, A1.2, A2.1 and A5.8 simultaneously.

#### ❌ D · Deterministic encryption only (AES-SIV)

Same plaintext → same ciphertext, so equality works.

**Rejected.** Sorting still breaks (ciphertext order is not plaintext order), so A2.1 still fails. And determinism over a low-cardinality column leaks structure: anyone with the database sees that forty rows share a borrower, and can rank borrowers by frequency without decrypting anything. That is meaningful leakage for a loan book.

#### ✅ E · AES-256-GCM ciphertext + HMAC blind index, decrypt and sort in the app

**Selected.**

Two columns per protected field:

| Column | Contents | Purpose |
|---|---|---|
| `borrower_name_ct` | AES-256-GCM(key_data, random 96-bit IV, plaintext) — IV and tag stored with the ciphertext | Confidentiality + integrity |
| `borrower_name_bidx` | HMAC-SHA256(key_index, normalize(plaintext))[:16] | Equality lookup, grouping, autocomplete |
| `key_version` | small int | Rotation without a big-bang re-encrypt |

`normalize()` is the MVP1 rule already in force — trim and lowercase — so the blind index is computed over exactly the value MVP1 filters on.

**How each MVP1 behaviour survives:**

| Behaviour | Mechanism |
|---|---|
| Exact filter (A5.8) | `WHERE borrower_name_bidx = HMAC(key, normalize(input))` — indexed, O(log n) |
| Autocomplete (A1.1) | Distinct blind indexes → decrypt the small result set → return names |
| Group auto-fill (A1.2) | Blind-index lookup on the name, read the group off the row |
| **Alphabetical sort (A2.1)** | Fetch the filtered set → decrypt → sort in the app |
| Import / export | Encrypt on write, decrypt on read — CSV round-trips unchanged |

**Why app-side sort is acceptable *here***: the dataset is bounded at ~1,500 rows and the table already loads its filtered set. Sorting 1,500 decrypted strings is sub-millisecond. The usual objection to app-side sort — millions of rows behind pagination — does not apply. It would apply at a different scale, and that is the trigger to revisit.

**Residual leakage, stated honestly**: the blind index still reveals *equality* and therefore frequency — the same weakness as option D, deliberately confined to a 16-byte derived column rather than the data itself. Truncating to 16 bytes introduces intentional collisions, which blunts frequency analysis slightly at the cost of occasional false-positive matches that the app filters out after decrypting. If frequency leakage ever becomes unacceptable, the fix is a per-org index key, which we can add without re-encrypting the ciphertext column.

### What is encrypted

| Field | Encrypted | Why |
|---|---|---|
| `borrower_name`, `depositor_name` | ✅ | Directly identifying |
| `borrower_group`, `depositor_group` | ✅ | "Sharma Traders" identifies a business |
| Account identifiers | ✅ | Directly identifying |
| `amount`, `giving_date`, `due_date`, `due_period` | ❌ | Needed for calculation, range filtering and DB-side sorting; not identifying alone |
| `reference_id`, `status` | ❌ | System-generated |

> The exclusion of amounts and dates is the same honest limitation recorded in ARD v2.0.0 §13: a distinctive amount-and-date pair can still be re-identifying to someone who already knows the borrower. Encryption at rest narrows the exposure; it does not make the row anonymous.

### Key management

| Phase | Where the key lives |
|---|---|
| M1a (local, single user) | 32 random bytes in `ops/.env.local`, never committed; OS keychain if available |
| M3+ (hosted) | Supabase Vault or a KMS; the app fetches at boot and holds it in memory only |

Two keys, derived from one master via HKDF with distinct info strings: `key_data` for AES-GCM, `key_index` for the HMAC. Never the same key for both — reusing it lets a blind index leak information about the encryption key's use.

`key_version` on every row makes rotation incremental: bump the version, encrypt new writes with the new key, migrate old rows in the background, retire the old key when no rows reference it.

### Three decisions this constrains

**1. Cursor pagination (v2.1.0 §10 #05).** A cursor needs a stable, DB-orderable sort key. `borrower_name_ct` is not orderable. So: cursor pagination applies to `due_date`, `amount`, `reference_id` and `created_at`; sorting by an encrypted column uses fetch-filtered-set → decrypt → sort → slice in the app. Bounded at 1,500 rows, this is fine, and the boundary must be documented at the endpoint rather than discovered.

**2. dbt marts (M5).** A mart cannot `GROUP BY` an encrypted name. Borrower-level aggregation groups by `borrower_name_bidx`; the display name is decrypted at read time by the app, not stored in the mart. The MVP1-interest-formula contract test is unaffected — it operates on amounts and rates.

**3. Agent PII masking (M2).** The order is now: **ciphertext → app decrypt → real name → mask to `PERSON_1` → LLM.** Two distinct protections at two boundaries. Never mask the ciphertext, and never let a decrypted name skip the masker. The maskable-field classification test (M2) must therefore cover encrypted fields specifically.

### Consequences

- Every read path touching a name pays a decrypt. At this scale, negligible.
- A lost key means unrecoverable data. Key backup is part of the ticket, not an afterthought.
- Two columns per protected field grows the schema; acceptable.
- Raw SQL (ADR-2.2) makes this *easier* — encryption and blind-index derivation happen in the repository layer, in plain sight, rather than behind ORM type-casting magic.

---

## 2. Local-first delivery posture

### The M1 split

M1 was 264 points — 39% of the plan and a long time before the MVP1 user could touch anything.

| | Scope | Exit |
|---|---|---|
| **M1a — Log in and see the shell** | Local setup (mac/win) · local schema · service account · auth · **encryption at rest** · placeholders for dashboard, chat · Help | The user logs in on their own machine. Encryption is provably working. |
| **M1b — Do my work** | Read data, then write data · Loans · Reports · Approvals · full MVP1 parity | Persona A: **PARITY HELD** |

Build order inside M1a follows the stated priority: **setup → login → encryption → (read) → (write)**. Encryption lands *before* any real data is written, so no row is ever stored in plaintext and no backfill is needed.

### Hosted infrastructure defers to M3

M1 is local-only. That removes from the critical path everything that exists only because the app is hosted:

| Deferred to M3 | Why it can wait |
|---|---|
| Supabase `ap-south-1` provisioning | Local Postgres serves M1 |
| Vercel `bom1` pinning, region assertion | No deployed functions yet |
| RLS policies + cross-tenant isolation test | One user, one org, locally |
| `service_role` key restriction | No hosted key yet |
| SQLite → hosted Supabase migration | M1 imports from git-tracked CSV instead |
| Vercel Blob | PDFs write to a local directory in M1 |

> ### ⚠️ One insurance policy I kept in M1a
>
> **`org_id` stays NOT NULL on every table from the first local migration**, even though RLS is off until M3.
>
> Deferring the *policy* is cheap. Deferring the *column* is not: adding tenancy later means a schema migration plus a backfill across every table, on data the user is actively working in. Keeping the column costs nothing now and turns M3's RLS work into adding policies rather than reshaping the schema.
>
> This is the one place I did not fully defer the data work, and it is deliberate.

### Interpretation of "delay all database migrations"

Read as: **defer hosted database work; keep the local schema.** The migration runner, the `orgs`/`users` tables and the MVP1 schema stay in M1a because the app cannot store a loan without them. Everything Supabase-hosted moves to M3.

If the intent was stricter — no schema work at all in M1 — then M1b cannot read or write data, and the milestone collapses to a login screen. Flagging in case the reading is wrong.

### Beautification moves to M3

| Ticket | Points | Why it is not parity |
|---|---|---|
| Component inventory with all variants | 13 | 31 components × every variant is a design-system build, not a working app |
| Skeleton states matching row geometry | 5 | Cold-start polish; a plain loading state passes parity |
| EmptyState variants that name the cause | 5 | The "name the cause" behaviour is real, but crude empty states pass parity |

**23 points out of the parity path.** Kept in M1: status colour tokens (they carry meaning — A3.6/A3.7) and `SessionExpiredDialog` (data-loss prevention, not decoration).

---

## 3. Revised milestone shape

| Milestone | Focus |
|---|---|
| **M0 · Foundation & Agent Toolchain** | Repo structure · developer agents executable · CodeRabbit wired · GitHub Actions + SQL-injection gate · **MVP1 regression gate** · MVP1 multi-month ByMonth |
| **M1a · Local Setup, Login & Encryption** | Runs locally on mac + windows · service account login · **encryption at rest working** · placeholder routes |
| **M1b · MVP1 Parity — Read then Write** | Loans, Reports, Approvals at full MVP1 parity · parity sweep green |
| **M2 · Agent Read-Only** | LiteLLM + Groq · 7 read tools · ReAct loop · masking before egress · evals |
| **M3 · Agent Write, UI Polish & Hosted Infra** | Mutating tools propose · approval gate proven · design system · Supabase hosted + RLS |
| **M4 · Multi-User Distribution** | Public signup · roles · production deploy · observability · collision validation |
| **M5 · Completion & Hardening** | dbt contracts · retention · real dashboard · docs |

> **M3 now carries three unrelated workstreams** — agent-write, UI polish and hosted infrastructure — because that is where each was individually placed. It is the most crowded milestone in the plan and the obvious candidate for a further split if it feels unwieldy on review.

---

## 4. Open for your decision

| # | Question | Recommendation |
|---|---|---|
| **09** | Encryption mechanism | **Option E** — AES-256-GCM + HMAC blind index, app-side sort. Rejections documented above. |
| **10** | Encrypt `borrower_group` / `depositor_group`? | **Yes.** A business name identifies a business. Cheap to include now, a re-encryption migration to add later. |
| **11** | Blind index truncation length | **16 bytes.** Deliberate collisions blunt frequency analysis; the app filters false positives after decrypt. |
| 05 | Cursor pagination (carried forward) | **Cursor on non-encrypted keys only** — see §1. Encrypted-column sorts paginate in the app. |
| 08 | `DueSoon` derived vs persisted (carried) | **Derived.** Unchanged. |

Decisions 02, 03 and 04 from v2.1.0 §10 remain as recorded there.
