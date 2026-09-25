"""Domain-level errors that cross layer boundaries.

Pure Python, no infrastructure imports -- the domain may not know that
storage is encrypted, that SQLAlchemy exists, or that `finhive.db` is where
the crypto lives. What it CAN express is the business-meaningful outcome:
"this record exists but cannot be read".

That distinction is the point. `finhive.db.encryption.DecryptionError` and
`KeyConfigurationError` are infrastructure concerns; a PySide6 tab must not
import either to decide what to show the user. The repository translates
them into `DataUnreadableError` at the boundary where it already imports
both worlds, and the presentation layer catches this instead.
"""

from __future__ import annotations


class DataUnreadableError(Exception):
    """Stored records could not be decrypted with the configured key.

    Raised when the data is intact but the key cannot open it -- a wrong or
    regenerated master key, a missing key version after a rotation, or a
    database encrypted under a key that is no longer configured.

    This is deliberately NOT the same as "no records matched". Before
    KCH-227's follow-up, a wrong key produced silently empty dropdowns and
    zero-row filters, so an intact loan book presented as an empty one. An
    empty result and an unreadable one must never look alike to the user.
    """

    def __init__(self, detail: str = "") -> None:
        super().__init__(
            "Stored records could not be decrypted with the configured "
            "master key. The data is intact, but the key does not open it "
            "-- check FINHIVE_KEY_VERSION and the matching "
            "FINHIVE_MASTER_KEY_V<n>."
            + (f"\n\n{detail}" if detail else "")
        )
        self.detail = detail
