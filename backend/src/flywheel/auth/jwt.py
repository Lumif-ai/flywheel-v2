"""JWT verification for Supabase-issued tokens.

Decodes HS256 tokens locally using the project's JWT secret -- no network
round-trip to Supabase. The ``audience="authenticated"`` claim is required;
without it PyJWT silently rejects all Supabase tokens.
"""

from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import HTTPException, status
from pydantic import BaseModel

from flywheel.config import settings


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

    Raises:
        HTTPException 401: If the token is expired, malformed, or has a
            wrong secret / audience.
    """
    try:
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
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    return TokenPayload(**payload)
