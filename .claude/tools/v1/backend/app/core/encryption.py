"""Encryption utilities for data protection."""
import base64
from typing import Optional

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    ENCRYPTION_AVAILABLE = True
except ImportError as e:
    ENCRYPTION_AVAILABLE = False
    IMPORT_ERROR = str(e)
    print(f"⚠️  Encryption not available: {e}")
    print("   Install cryptography: pip install cryptography")

from app.core.exceptions import EncryptionException
from app.core.logging import get_logger

logger = get_logger(__name__)


class EncryptionManager:
    """Handle encryption/decryption operations."""

    def __init__(self, key: Optional[str] = None):
        """Initialize encryption manager with optional key."""
        self.cipher = None
        if key:
            if not ENCRYPTION_AVAILABLE:
                logger.error(
                    "encryption_unavailable",
                    error=IMPORT_ERROR,
                    message="Encryption key provided but cryptography not installed"
                )
                raise EncryptionException(
                    f"Cannot enable encryption: cryptography library not available.\n"
                    f"Error: {IMPORT_ERROR}\n"
                    f"Fix: pip install cryptography\n"
                    f"Or: Set ENCRYPTION_KEY= (empty) in .env to disable encryption"
                )

            try:
                # Derive a proper Fernet key from the provided key
                derived_key = self._derive_key(key)
                self.cipher = Fernet(derived_key)
                logger.info("encryption_enabled", message="Encryption initialized successfully")
            except EncryptionException:
                raise
            except Exception as e:
                logger.error("encryption_init_failed", error=str(e))
                raise EncryptionException(f"Failed to initialize encryption: {str(e)}")

    @staticmethod
    def _derive_key(password: str, salt: bytes = b'loantracker_salt') -> bytes:
        """Derive encryption key from password using PBKDF2."""
        if not ENCRYPTION_AVAILABLE:
            raise EncryptionException(
                f"Encryption dependencies not available. {IMPORT_ERROR}\n"
                "Please install: pip install cryptography"
            )

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    def encrypt(self, data: str) -> str:
        """Encrypt string data. Returns original data if encryption is disabled."""
        if not self.cipher:
            return data
        try:
            return self.cipher.encrypt(data.encode()).decode()
        except Exception as e:
            raise EncryptionException(f"Encryption failed: {str(e)}")

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt string data. Returns original data if encryption is disabled."""
        if not self.cipher:
            return encrypted_data
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            raise EncryptionException(f"Decryption failed: {str(e)}")

    @property
    def is_enabled(self) -> bool:
        """Check if encryption is enabled."""
        return self.cipher is not None
