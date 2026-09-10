from __future__ import annotations

import sys

sys.path.insert(0, ".")
from finhive.db.encryption import DecryptionError, decrypt_field, encrypt_field

key = bytes([1]) * 32
blob = encrypt_field("Sharma Traders", key)
print("blob len", len(blob))
print("roundtrip", decrypt_field(blob, key))
tampered = bytearray(blob)
tampered[-1] ^= 0xFF
try:
    decrypt_field(bytes(tampered), key)
    print("FAIL: no error raised")
    sys.exit(1)
except DecryptionError:
    print("tamper correctly rejected")
