-- Encrypt NPI columns at rest before any real data is written (KCH-95).
-- ADR-2.3 (ARD v2.2.0) and ADR-2.4 (ARD v2.3.0).
--
-- Every identity field (borrower_name, borrower_group, depositor_name,
-- depositor_group) and every financial value (amount, interest_amount,
-- commission_amount, tds_amount, chq_amount) is NPI and must never be
-- written to the database in plaintext. Each such column is replaced by a
-- `<column>_ct` BYTEA column holding AES-256-GCM(key_data, random 96-bit IV,
-- plaintext) with the IV and auth tag stored alongside the ciphertext
-- (finhive/db/encryption.py), plus one `key_version` column per table for
-- incremental key rotation.
--
-- interest_rate, commission_rate, extension_period and the date columns stay
-- plaintext (decisions 13 and 14) -- a percentage is not a balance, and
-- ADR-2.4's derivation check shows the plaintext columns give no solve path
-- back to amount.
--
-- 0002 created these columns and this migration replaces them before any
-- application code writes through them, so DROP + ADD needs no backfill.
-- The equality/sort indexes on plaintext borrower_name and depositor_name
-- are dropped automatically along with their columns; their replacement --
-- an HMAC blind index over the ciphertext -- is a separate migration
-- (KCH-96), not this one.

ALTER TABLE loans
    DROP COLUMN borrower_name,
    DROP COLUMN borrower_group,
    DROP COLUMN depositor_name,
    DROP COLUMN depositor_group,
    DROP COLUMN amount,
    ADD COLUMN borrower_name_ct BYTEA NOT NULL,
    ADD COLUMN borrower_group_ct BYTEA NOT NULL,
    ADD COLUMN depositor_name_ct BYTEA NOT NULL,
    ADD COLUMN depositor_group_ct BYTEA,
    ADD COLUMN amount_ct BYTEA NOT NULL,
    ADD COLUMN key_version SMALLINT NOT NULL DEFAULT 1;

ALTER TABLE loan_history
    DROP COLUMN borrower_name,
    DROP COLUMN borrower_group,
    DROP COLUMN depositor_name,
    DROP COLUMN depositor_group,
    DROP COLUMN amount,
    ADD COLUMN borrower_name_ct BYTEA NOT NULL,
    ADD COLUMN borrower_group_ct BYTEA NOT NULL,
    ADD COLUMN depositor_name_ct BYTEA NOT NULL,
    ADD COLUMN depositor_group_ct BYTEA,
    ADD COLUMN amount_ct BYTEA NOT NULL,
    ADD COLUMN key_version SMALLINT NOT NULL DEFAULT 1;

ALTER TABLE report_records
    DROP COLUMN borrower_name,
    DROP COLUMN depositor_name,
    DROP COLUMN depositor_group,
    DROP COLUMN amount,
    DROP COLUMN interest_amount,
    DROP COLUMN commission_amount,
    DROP COLUMN tds_amount,
    DROP COLUMN chq_amount,
    ADD COLUMN borrower_name_ct BYTEA NOT NULL,
    ADD COLUMN depositor_name_ct BYTEA NOT NULL,
    ADD COLUMN depositor_group_ct BYTEA,
    ADD COLUMN amount_ct BYTEA NOT NULL,
    ADD COLUMN interest_amount_ct BYTEA,
    ADD COLUMN commission_amount_ct BYTEA,
    ADD COLUMN tds_amount_ct BYTEA,
    ADD COLUMN chq_amount_ct BYTEA,
    ADD COLUMN key_version SMALLINT NOT NULL DEFAULT 1;
