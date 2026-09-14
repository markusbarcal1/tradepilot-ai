from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.repositories.users import UserRepository


ALLOWED_JWT_ALGORITHMS = ("RS256", "ES256")
bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    email: str | None = None


class SupabaseJWTVerifier:
    def __init__(self, issuer: str, audience: str, jwks_url: str, jwks_client=None):
        self.issuer = issuer
        self.audience = audience
        self.jwks_client = jwks_client or PyJWKClient(
            jwks_url,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=600,
        )

    def verify(self, token: str) -> dict:
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=ALLOWED_JWT_ALGORITHMS,
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        except (InvalidTokenError, PyJWKClientError, ValueError, TypeError) as exc:
            raise authentication_error() from exc


def authentication_error():
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


@lru_cache(maxsize=1)
def get_token_verifier():
    if not settings.auth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    return SupabaseJWTVerifier(
        issuer=settings.supabase_auth_issuer,
        audience=settings.supabase_auth_audience,
        jwks_url=settings.supabase_jwks_url,
    )


def get_auth_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
    ],
    session: Annotated[Session, Depends(get_auth_session)],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise authentication_error()

    claims = get_token_verifier().verify(credentials.credentials)
    try:
        user_id = UUID(claims["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise authentication_error() from exc

    user = UserRepository(session).get(user_id)
    if user is None or user.beta_status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to the private beta is not permitted",
        )

    email = claims.get("email")
    return CurrentUser(user_id=user_id, email=email if isinstance(email, str) else None)
