-- Tenant root and the mapping from Supabase auth.users to an org + role.
-- ARD v2.0.0 §9 "Data Layer -- Raw SQL + Supabase".

CREATE TABLE orgs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per Supabase-authenticated user, scoped to exactly one org. `id`
-- is a foreign key into Supabase's own `auth.users`, not a locally-issued
-- identity -- this table only adds the org + role a JWT's `sub` resolves to.
CREATE TABLE users (
    id UUID PRIMARY KEY REFERENCES auth.users (id) ON DELETE CASCADE,
    org_id UUID NOT NULL REFERENCES orgs (id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'bookkeeper', 'viewer')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX users_org_id_idx ON users (org_id);
