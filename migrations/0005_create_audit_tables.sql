-- Create proposed_mutations and agent_turns with encrypted JSONB (KCH-98).
-- ADR-2.4 (ARD v2.3.0 §1): "JSONB snapshots contain amounts" and "tool
-- outputs in the trace contain amounts".
--
-- These tables land as part of the agent features planned for M2/M3, but
-- 0003's header explicitly deferred encrypting their JSONB blobs to the
-- migration that creates them (this one). Creating the tables with `_ct`
-- columns from the start avoids the drop-and-add pattern 0003 used on
-- existing plaintext columns, and means no row ever holds a plaintext
-- snapshot.
--
-- Encryption strategy: whole-blob AES-256-GCM via encrypt_json/decrypt_json
-- (finhive/db/encryption.py, KCH-98), not per-field, because the JSONB
-- shape varies across rows -- proposed_mutations snapshots carry whichever
-- fields the mutation touched, and react_trace carries the full ReAct
-- tool-call chain whose structure is model-dependent. The approvals diff
-- renderer decrypts in the app layer (ADR-2.4 acceptance criteria).
--
-- No blind index on any column here: before_state/after_state are
-- variable-shape snapshots that never back a lookup, and react_trace is
-- write-once audit data. Amount columns in the snapshots are already
-- covered by the loan table's own blind indexes (KCH-96).

CREATE TABLE proposed_mutations (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         UUID NOT NULL REFERENCES orgs(id),
    -- BIGINT, not UUID: migrations/0002 defines loans.id as
    -- `BIGINT GENERATED ALWAYS AS IDENTITY`, so a UUID column here cannot
    -- carry the foreign key at all -- Postgres refuses it outright with
    -- "Key columns loan_id and id are of incompatible types: uuid and bigint".
    -- The other five FKs in this file DO target UUID keys (orgs.id,
    -- users.id), which is how the mismatch survived review.
    loan_id        BIGINT NOT NULL REFERENCES loans(id),
    mutation_type  TEXT NOT NULL,
    before_state_ct BYTEA NOT NULL,
    after_state_ct  BYTEA NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',
    created_by     UUID NOT NULL REFERENCES users(id),
    reviewed_by    UUID REFERENCES users(id),
    reviewed_at    TIMESTAMPTZ,
    key_version    SMALLINT NOT NULL DEFAULT 1,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX proposed_mutations_org_id_idx
    ON proposed_mutations (org_id);
CREATE INDEX proposed_mutations_loan_id_idx
    ON proposed_mutations (loan_id);
CREATE INDEX proposed_mutations_status_idx
    ON proposed_mutations (status);

CREATE TABLE agent_turns (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id            UUID NOT NULL REFERENCES orgs(id),
    user_id           UUID NOT NULL REFERENCES users(id),
    user_message      TEXT NOT NULL,
    react_trace_ct    BYTEA NOT NULL,
    prompt_tokens     INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cost_usd          NUMERIC(10, 6) NOT NULL,
    latency_ms        INTEGER NOT NULL,
    model             TEXT NOT NULL,
    feedback          TEXT,
    key_version       SMALLINT NOT NULL DEFAULT 1,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX agent_turns_org_id_idx
    ON agent_turns (org_id);
CREATE INDEX agent_turns_user_id_idx
    ON agent_turns (user_id);
