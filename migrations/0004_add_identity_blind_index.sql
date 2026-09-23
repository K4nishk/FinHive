-- HMAC blind index for encrypted IDENTITY columns only (KCH-96).
-- ADR-2.3 (ARD v2.2.0 §1) and ADR-2.4 (ARD v2.3.0 §1, "Do not put a blind
-- index on an amount").
--
-- 0003 replaced borrower_name, borrower_group, depositor_name and
-- depositor_group with random-IV AES-256-GCM ciphertext (`_ct` columns),
-- which by design encrypts the same plaintext differently on every call and
-- so cannot back an equality lookup, sort, autocomplete or group auto-fill.
-- This migration adds the other half of the ADR-2.3 pattern for those four
-- identity columns only: one `_bidx` column per field, holding
-- HMAC-SHA256(key_index, normalize(plaintext))[:16] (finhive/db/blind_index.py),
-- indexed for O(log n) exact-match lookup (MVP1 parity A5.8), autocomplete
-- (A1.1) and group auto-fill (A1.2). `key_index` is derived directly from
-- the master key via HKDF, with an info string distinct from any other
-- derived key -- NEVER derived from `key_data` (the AES-GCM key), and
-- `key_data` is never derived from it either. Chaining one through the
-- other is exactly the design ADR-2.3 "Key management" rules out: it would
-- mean any exposure of `key_data`, which happens on every encrypt/decrypt
-- call, also hands over the blind-index key. See blind_index.py and
-- keys.py's `derive_key_data`/`derive_key_index`, both taking the master
-- directly.
--
-- amount, interest_amount, commission_amount, tds_amount and chq_amount are
-- NPI financial values (ADR-2.4) and get NO index of any kind here or ever:
-- they stay AES-256-GCM-only. Loan amounts cluster on round numbers, so a
-- deterministic index over them would be reversible by frequency analysis
-- without the key -- worse than the equality leakage a blind index already
-- accepts on identity fields, and order-preserving encryption would be worse
-- still, leaking the full ranking of the loan book. This is enforced as a
-- CI-blocking static check over every migration file, not left as a
-- comment -- see tests/unit/test_blind_index_lint.py.

ALTER TABLE loans
    ADD COLUMN borrower_name_bidx BYTEA NOT NULL,
    ADD COLUMN borrower_group_bidx BYTEA NOT NULL,
    ADD COLUMN depositor_name_bidx BYTEA NOT NULL,
    ADD COLUMN depositor_group_bidx BYTEA;

CREATE INDEX loans_borrower_name_bidx_idx ON loans (borrower_name_bidx);
CREATE INDEX loans_borrower_group_bidx_idx ON loans (borrower_group_bidx);
CREATE INDEX loans_depositor_name_bidx_idx ON loans (depositor_name_bidx);
CREATE INDEX loans_depositor_group_bidx_idx ON loans (depositor_group_bidx);

ALTER TABLE loan_history
    ADD COLUMN borrower_name_bidx BYTEA NOT NULL,
    ADD COLUMN borrower_group_bidx BYTEA NOT NULL,
    ADD COLUMN depositor_name_bidx BYTEA NOT NULL,
    ADD COLUMN depositor_group_bidx BYTEA;

CREATE INDEX loan_history_borrower_name_bidx_idx ON loan_history (borrower_name_bidx);
CREATE INDEX loan_history_borrower_group_bidx_idx ON loan_history (borrower_group_bidx);
CREATE INDEX loan_history_depositor_name_bidx_idx ON loan_history (depositor_name_bidx);
CREATE INDEX loan_history_depositor_group_bidx_idx ON loan_history (depositor_group_bidx);

ALTER TABLE report_records
    ADD COLUMN borrower_name_bidx BYTEA NOT NULL,
    ADD COLUMN depositor_name_bidx BYTEA NOT NULL,
    ADD COLUMN depositor_group_bidx BYTEA;

CREATE INDEX report_records_borrower_name_bidx_idx ON report_records (borrower_name_bidx);
CREATE INDEX report_records_depositor_name_bidx_idx ON report_records (depositor_name_bidx);
CREATE INDEX report_records_depositor_group_bidx_idx ON report_records (depositor_group_bidx);
