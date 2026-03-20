"""Unit tests for auth foundation: JWT decode, encryption, Invite model."""

from __future__ import annotations

import datetime
import time
from unittest.mock import patch
from uuid import UUID, uuid4

import jwt as pyjwt
import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from flywheel.auth.jwt import TokenPayload, decode_jwt
from flywheel.db.models import Invite

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-only"
TEST_ENCRYPTION_KEY = Fernet.generate_key().decode()


# ---------------------------------------------------------------------------
# JWT tests
# ---------------------------------------------------------------------------


class TestJWT:
    """Tests for JWT decode and TokenPayload."""

    def _make_token(
        self,
        secret: str = TEST_JWT_SECRET,
        sub: str | None = None,
        email: str = "user@test.com",
        is_anonymous: bool = False,
        aud: str = "authenticated",
        app_metadata: dict | None = None,
        expired: bool = False,
    ) -> str:
        now = int(time.time())
        payload: dict = {
            "sub": sub or str(uuid4()),
            "email": email,
            "is_anonymous": is_anonymous,
            "aud": aud,
            "app_metadata": app_metadata or {},
            "iat": now,
            "exp": now - 10 if expired else now + 3600,
        }
        return pyjwt.encode(payload, secret, algorithm="HS256")

    @patch("flywheel.auth.jwt.settings")
    def test_decode_valid_token(self, mock_settings):
        mock_settings.supabase_jwt_secret = TEST_JWT_SECRET
        tenant_id = str(uuid4())
        token = self._make_token(
            email="alice@test.com",
            app_metadata={"tenant_id": tenant_id, "role": "admin"},
        )
        result = decode_jwt(token)
        assert isinstance(result, TokenPayload)
        assert result.email == "alice@test.com"
        assert result.tenant_id == UUID(tenant_id)
        assert result.tenant_role == "admin"
        assert result.aud == "authenticated"

    @patch("flywheel.auth.jwt.settings")
    def test_decode_expired_token(self, mock_settings):
        mock_settings.supabase_jwt_secret = TEST_JWT_SECRET
        token = self._make_token(expired=True)
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @patch("flywheel.auth.jwt.settings")
    def test_decode_wrong_secret(self, mock_settings):
        mock_settings.supabase_jwt_secret = "wrong-secret"
        token = self._make_token(secret=TEST_JWT_SECRET)
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(token)
        assert exc_info.value.status_code == 401

    @patch("flywheel.auth.jwt.settings")
    def test_decode_wrong_audience(self, mock_settings):
        mock_settings.supabase_jwt_secret = TEST_JWT_SECRET
        token = self._make_token(aud="wrong")
        with pytest.raises(HTTPException) as exc_info:
            decode_jwt(token)
        assert exc_info.value.status_code == 401

    def test_token_payload_tenant_id_property(self):
        tid = uuid4()
        tp = TokenPayload(
            sub=uuid4(),
            app_metadata={"tenant_id": str(tid), "role": "admin"},
        )
        assert tp.tenant_id == tid
        assert tp.tenant_role == "admin"

    def test_token_payload_anonymous(self):
        tp = TokenPayload(
            sub=uuid4(),
            is_anonymous=True,
            app_metadata={},
        )
        assert tp.is_anonymous is True
        assert tp.tenant_id is None
        assert tp.tenant_role == "member"


# ---------------------------------------------------------------------------
# Encryption tests
# ---------------------------------------------------------------------------


class TestEncryption:
    """Tests for BYOK API key encryption."""

    @patch("flywheel.auth.encryption.settings")
    def test_encrypt_decrypt_round_trip(self, mock_settings):
        import flywheel.auth.encryption as enc_mod

        mock_settings.encryption_key = TEST_ENCRYPTION_KEY
        enc_mod._fernet = None  # Reset singleton

        from flywheel.auth.encryption import decrypt_api_key, encrypt_api_key

        original = "sk-test-1234567890abcdef"
        encrypted = encrypt_api_key(original)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original

    @patch("flywheel.auth.encryption.settings")
    def test_decrypt_invalid_data(self, mock_settings):
        import flywheel.auth.encryption as enc_mod

        mock_settings.encryption_key = TEST_ENCRYPTION_KEY
        enc_mod._fernet = None

        from flywheel.auth.encryption import decrypt_api_key

        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_api_key(b"garbage-data-not-fernet")

    @patch("flywheel.auth.encryption.settings")
    def test_encrypted_output_is_bytes(self, mock_settings):
        import flywheel.auth.encryption as enc_mod

        mock_settings.encryption_key = TEST_ENCRYPTION_KEY
        enc_mod._fernet = None

        from flywheel.auth.encryption import encrypt_api_key

        result = encrypt_api_key("test-key")
        assert isinstance(result, bytes)


# ---------------------------------------------------------------------------
# Invite model tests
# ---------------------------------------------------------------------------


class TestInviteModel:
    """Tests for the Invite ORM model structure."""

    def test_invite_model_columns(self):
        expected_columns = [
            "id",
            "tenant_id",
            "invited_by",
            "email",
            "role",
            "token_hash",
            "accepted_at",
            "expires_at",
            "created_at",
        ]
        actual_columns = list(Invite.__table__.columns.keys())
        for col in expected_columns:
            assert col in actual_columns, f"Missing column: {col}"

    def test_invite_tablename(self):
        assert Invite.__tablename__ == "invites"
