"""Custom exception classes."""


class LoanTrackerException(Exception):
    """Base exception for LoanTracker application."""
    pass


class LoanNotFoundException(LoanTrackerException):
    """Raised when a loan record is not found."""
    pass


class ValidationException(LoanTrackerException):
    """Raised when validation fails."""
    pass


class StorageException(LoanTrackerException):
    """Raised when storage operations fail."""
    pass


class EncryptionException(LoanTrackerException):
    """Raised when encryption/decryption operations fail."""
    pass
