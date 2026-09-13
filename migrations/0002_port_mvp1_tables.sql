-- Port MVP1's six loan-tracking tables to Postgres, adding org_id to every
-- business table for multi-tenancy. ARD v2.0.0 §9 "Schema evolution from
-- MVP1" -- loans, loan_meta, loan_history, reports, report_records and
-- report_meta carry over with their MVP1 columns, constraints and indexes
-- unchanged, plus an org_id FK into orgs (0001) on every row.
--
-- reference_id and report_id were globally unique in MVP1's single-tenant
-- SQLite schema because a single counter (loan_meta / report_meta, keyed by
-- year_month / report_date) generated them. Each tenant now has its own
-- counter, so two orgs will legitimately mint the same reference_id/report_id
-- -- the uniqueness guarantee is preserved per-tenant via UNIQUE (org_id, ...)
-- rather than a bare UNIQUE, and loan_meta/report_meta's primary keys gain
-- org_id so each org's counter is independent.

CREATE TABLE loans (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES orgs (id) ON DELETE CASCADE,
    reference_id TEXT NOT NULL,
    borrower_name TEXT NOT NULL,
    borrower_group TEXT NOT NULL,
    depositor_name TEXT NOT NULL,
    depositor_group TEXT,
    amount BIGINT NOT NULL,
    giving_date DATE NOT NULL,
    due_period INTEGER,
    due_date DATE,
    status TEXT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, reference_id)
);

CREATE INDEX loans_borrower_name_idx ON loans (borrower_name);
CREATE INDEX loans_depositor_name_idx ON loans (depositor_name);
CREATE INDEX loans_status_idx ON loans (status);

-- Per-org, per-month sequence counter that reference_id order numbers are
-- drawn from (ReferenceIdService.next_id in MVP1).
CREATE TABLE loan_meta (
    org_id UUID NOT NULL REFERENCES orgs (id) ON DELETE CASCADE,
    year_month TEXT NOT NULL,
    last_order INTEGER NOT NULL,
    PRIMARY KEY (org_id, year_month)
);

CREATE TABLE loan_history (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES orgs (id) ON DELETE CASCADE,
    reference_id TEXT NOT NULL,
    borrower_name TEXT NOT NULL,
    borrower_group TEXT NOT NULL,
    depositor_name TEXT NOT NULL,
    depositor_group TEXT,
    amount BIGINT NOT NULL,
    giving_date DATE NOT NULL,
    due_date DATE,
    paidoff_date DATE,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX loan_history_org_id_idx ON loan_history (org_id);
CREATE INDEX loan_history_reference_id_idx ON loan_history (reference_id);

CREATE TABLE reports (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES orgs (id) ON DELETE CASCADE,
    report_id TEXT NOT NULL,
    report_mode TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (org_id, report_id)
);

CREATE TABLE report_records (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES orgs (id) ON DELETE CASCADE,
    report_id TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    borrower_name TEXT NOT NULL,
    depositor_name TEXT NOT NULL,
    depositor_group TEXT,
    amount BIGINT NOT NULL,
    giving_date DATE NOT NULL,
    due_date DATE,
    extension_period INTEGER NOT NULL,
    extension_period_unit TEXT NOT NULL,
    interest_rate NUMERIC(5, 2) NOT NULL,
    commission_rate NUMERIC(5, 2) NOT NULL,
    tds_flag BOOLEAN NOT NULL DEFAULT false,
    interest_amount NUMERIC(12, 2),
    commission_amount NUMERIC(12, 2),
    tds_amount NUMERIC(12, 2),
    chq_amount NUMERIC(12, 2),
    post_extension_giving_date DATE,
    post_extension_due_date DATE,
    paidoff_date DATE,
    FOREIGN KEY (org_id, report_id) REFERENCES reports (org_id, report_id) ON DELETE CASCADE
);

CREATE INDEX report_records_org_id_report_id_idx ON report_records (org_id, report_id);
CREATE INDEX report_records_reference_id_idx ON report_records (reference_id);

-- Per-org, per-report-date sequence counter that report_id order numbers are
-- drawn from, mirroring loan_meta.
CREATE TABLE report_meta (
    org_id UUID NOT NULL REFERENCES orgs (id) ON DELETE CASCADE,
    report_date TEXT NOT NULL,
    last_order INTEGER NOT NULL,
    PRIMARY KEY (org_id, report_date)
);
