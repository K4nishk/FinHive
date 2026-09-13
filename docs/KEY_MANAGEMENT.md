# Key management (ADR-2.3, KCH-97)

How `key_data` and `key_index` are derived, how rotation works, and how to
back up and restore a master key. See `output/Loan Manager/mvp2/mvp2_ard_v2.2.0.md`
§"Key management" for the design rationale; this document is the operational
procedure. Code: `finhive/db/keys.py`, `finhive/db/encryption.py`,
`finhive/db/blind_index.py`.

## Derivation

One 32-byte master key per `key_version`. Everything else is derived, never
stored, and `key_data` and `key_index` are derived **independently** from
the master -- never one from the other:

```
master --HKDF(info="finhive-aes-gcm-key-v1")-->          key_data  (AES-256-GCM)
master --HKDF(info="finhive-blind-index-hmac-key-v1")--> key_index (HMAC-SHA256)
```

Distinct info strings mean `key_data` and `key_index` can never collide or
be swapped, and deriving both directly from the master rather than chaining
one through the other means exposure of `key_data` -- which happens on
every encrypt/decrypt call, far more often than the master itself is
touched -- never also reveals `key_index` (ADR-2.3: "Never the same key for
both -- reusing it lets a blind index leak information about the
encryption key's use").

## Where the master lives

| Phase | Where |
|---|---|
| M1a (local, single user) | Base64 in `ops/.env.local` (`FINHIVE_MASTER_KEY_V<n>`), gitignored, never committed; OS keychain if available |
| M3+ (hosted) | Supabase Vault or a KMS, fetched at boot and held in memory only |

`finhive/db/keys.load_key_ring` takes an `env` mapping so swapping the M1a
source for a KMS-backed one at M3 changes only what gets passed in, not any
caller.

## Rotation

Rotation is incremental -- never a big-bang re-encrypt of every row:

1. Generate a new master and set it alongside the old one:
   ```bash
   export FINHIVE_MASTER_KEY_V2="<new base64 master>"
   export FINHIVE_KEY_VERSION=2   # new writes now use version 2
   ```
   Version 1's master (`FINHIVE_MASTER_KEY_V1`) stays set -- rows still at
   `key_version = 1` need it to keep reading.
2. New writes are encrypted under version 2 immediately (`FINHIVE_KEY_VERSION`
   controls that).
3. Migrate existing rows in the background, a batch at a time, with
   `finhive.db.keys.rotate_field` (amount columns) or
   `rotate_identity_field` (identity columns -- also recomputes the paired
   `_bidx`, since `key_index` changes with the master too):
   ```python
   ring = load_key_ring()
   new_blob, new_bidx = rotate_identity_field(
       row.borrower_name_ct, from_version=1, to_version=2, ring=ring, column="borrower_name",
   )
   # UPDATE loans SET borrower_name_ct = new_blob, borrower_name_bidx = new_bidx,
   #                  key_version = 2 WHERE id = row.id
   ```
   Reads are unaffected while this runs: a row's own `key_version` says which
   master decrypts it, and both masters are loaded throughout the migration.
4. Once no row references `key_version = 1` (`SELECT 1 FROM loans WHERE
   key_version = 1 LIMIT 1` returns nothing, checked across every table with a
   `key_version` column) **and** every cold archive, audit snapshot, or
   backup that could contain `key_version = 1` ciphertext has also been
   inventoried and migrated (a `pg_dump`, a report export, a disk snapshot --
   anything taken before step 3 completed is still on version 1 even after
   every live table is clean), retire it: remove `FINHIVE_MASTER_KEY_V1` and
   destroy the backed-up copy of that master (see below).

   Do not destroy the old master until this full inventory is done -- a live
   table scan alone does not prove version 1 is unused, and a lost master
   makes any ciphertext still on that version permanently unrecoverable.
   Test a restore from each archive/snapshot and verify row-level equality
   against a known-good sample before considering it migrated.

## Backup and restore

A lost master key means every row still on that `key_version` is
unrecoverable -- there is no other copy of the plaintext anywhere. Back a
master up **before** it encrypts any real data, not after:

1. Generate and store the master's base64 value in a secrets manager or
   offline vault separate from `ops/.env.local` (e.g. a password manager
   entry, a hardware-backed secret store, or printed and stored physically)
   before running the app against real loan data with it.
2. Label the backup with its `FINHIVE_KEY_VERSION` number -- restoring the
   wrong version's master silently fails every `DecryptionError` check
   instead of restoring anything.
3. To restore: set `FINHIVE_MASTER_KEY_V<n>` in `ops/.env.local` (or the
   keychain/KMS equivalent) to the backed-up value and confirm it works
   before relying on it:
   ```python
   from finhive.db.keys import load_key_ring
   from finhive.db.encryption import decrypt_field

   ring = load_key_ring()
   decrypt_field(some_known_row.borrower_name_ct, ring.key_data(some_known_row.key_version))
   ```
   A successful decrypt of a known row is the restore verification -- an
   `ImportError`-free load or a well-formed base64 string is not enough proof
   the bytes are the *right* master.
4. Rotate away from any master that had its backup exposed (treat exposure
   like a compromise), following the rotation procedure above.
