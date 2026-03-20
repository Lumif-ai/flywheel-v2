"""Fernet encryption for BYOK API keys.

API keys are encrypted before storage (LargeBinary column) and decrypted
on demand for outbound API calls. The encryption key is a Fernet-compatible
base64 string loaded from the ENCRYPTION_KEY env var.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from flywheel.config import settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Lazy-init Fernet instance from settings."""
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.encryption_key.encode())
    return _fernet


def encrypt_api_key(api_key: str) -> bytes:
    """Encrypt a plaintext API key. Returns bytes for LargeBinary column."""
    return _get_fernet().encrypt(api_key.encode())


def decrypt_api_key(encrypted: bytes) -> str:
    """Decrypt an API key. Raises ValueError on tampered/invalid data."""
    try:
        return _get_fernet().decrypt(encrypted).decode()
    except InvalidToken:
        raise ValueError("Failed to decrypt API key")
