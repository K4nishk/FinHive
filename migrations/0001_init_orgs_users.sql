-- Tenant root, and the mapping from a user identity to an org + role.
-- ARD v2.0.0 §9, as amended by ARB D-16: Supabase is replaced by local
-- Postgres in Docker for MVP1.1, so identities are issued locally.

CREATE TABLE orgs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per user, scoped to exactly one org.
--
-- `id` was a foreign key into Supabase's own `auth.users`. ARB D-16 replaced
-- Supabase with local Postgres, so that schema does not exist and this
-- migration could not run at all -- it failed with
-- `InvalidSchemaNameError: schema "auth" does not exist` on a clean database.
-- The identity is now issued locally by finhive/db/seed_service_account.py
-- (KCH-228), which generates the owner UUID itself.
--
-- When the web app lands and a real auth provider issues identities, the
-- provider's subject goes in this column and the FK comes back as a
-- migration against whatever that provider actually is -- not as an
-- assumption baked in before the provider is chosen.
CREATE TABLE users (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES orgs (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'bookkeeper', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX users_org_id_idx ON users (org_id);
