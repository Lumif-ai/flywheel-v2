"""JWT verification for Supabase-issued tokens.

Supports both HS256 (older Supabase projects using shared secret) and
ES256 (newer projects using ECDSA key pairs via JWKS). The algorithm is
detected from the token header; ES256 keys are fetched once from
Supabase's JWKS endpoint and cached for the process lifetime.
"""

from __future__ import annotations

import logging
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient
from pydantic import BaseModel

from flywheel.config import settings

logger = logging.getLogger(__name__)

# Lazy-initialized JWKS client for ES256 verification
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


class TokenPayload(BaseModel):
    """Parsed JWT claims from a Supabase access token."""

    sub: UUID
    email: str | None = None
    is_anonymous: bool = False
    aud: str = "authenticated"
    app_metadata: dict = {}

    @property
    def tenant_id(self) -> UUID | None:
        """Extract tenant UUID from app_metadata, if present."""
        tid = self.app_metadata.get("tenant_id")
        if tid is None:
            return None
        return UUID(str(tid))

    @property
    def tenant_role(self) -> str:
        """Tenant role from app_metadata, defaults to 'member'."""
        return self.app_metadata.get("role", "member")


def decode_jwt(token: str) -> TokenPayload:
    """Decode and validate a Supabase JWT.

    Detects algorithm from the token header:
    - HS256: verifies with supabase_jwt_secret (shared secret)
    - ES256: verifies with public key fetched from Supabase JWKS endpoint

    Raises:
        HTTPException 401: If the token is expired, malformed, or has a
            wrong secret / audience.
    """
    try:
        # Peek at header to determine algorithm
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")

        if alg == "ES256":
            # Fetch signing key from JWKS endpoint
            signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
            )
        else:
            # Legacy HS256 with shared secret
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.PyJWTError as e:
        logger.warning("JWT decode failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return TokenPayload(**payload)
