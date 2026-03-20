"""AES-256-GCM encryption for BYOK API keys.

API keys are encrypted before storage (LargeBinary column) and decrypted
on demand for outbound API calls. The encryption key is a base64-encoded
32-byte AES-256 key loaded from the ENCRYPTION_KEY env var.
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from flywheel.config import settings

_aesgcm: AESGCM | None = None


def _get_aesgcm() -> AESGCM:
    """Lazy-init AESGCM instance from settings."""
    global _aesgcm
    if _aesgcm is None:
        key_bytes = base64.b64decode(settings.encryption_key)
        _aesgcm = AESGCM(key_bytes)
    return _aesgcm


def encrypt_api_key(api_key: str) -> bytes:
    """Encrypt a plaintext API key. Returns nonce + ciphertext bytes for LargeBinary column."""
    nonce = os.urandom(12)
    ciphertext = _get_aesgcm().encrypt(nonce, api_key.encode(), None)
    return nonce + ciphertext


def decrypt_api_key(encrypted: bytes) -> str:
    """Decrypt an API key. Raises ValueError on tampered/invalid data."""
    try:
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        return _get_aesgcm().decrypt(nonce, ciphertext, None).decode()
    except Exception:
        raise ValueError("Failed to decrypt API key")
