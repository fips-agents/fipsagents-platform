"""Bearer token validation.

Two modes:

- ``none`` -- no validation; user_id defaults to ``"anonymous"``.
  Intended for development and single-tenant deployments behind a trusted gateway.
- ``keycloak`` -- validates the inbound ``Authorization: Bearer <jwt>`` header
  against a Keycloak issuer's JWKS. Same realm as the gateway, so the gateway's
  RFC 8693 token exchange tokens validate here.

The validated subject is exposed via :func:`require_user` as a dependency.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import Header, HTTPException, status
from jose import jwt

from .config import Settings, get_settings

logger = logging.getLogger(__name__)

_jwks_cache: dict[str, Any] = {"keys": None, "expires_at": 0.0}


async def _fetch_jwks(settings: Settings) -> Any:
    now = time.monotonic()
    if _jwks_cache["keys"] is not None and now < _jwks_cache["expires_at"]:
        return _jwks_cache["keys"]
    issuer = settings.keycloak_issuer.rstrip("/")
    url = f"{issuer}/protocol/openid-connect/certs"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        keys = resp.json()
    _jwks_cache["keys"] = keys
    _jwks_cache["expires_at"] = now + settings.keycloak_jwks_cache_seconds
    return keys


async def require_user(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: returns the authenticated subject (user_id).

    In ``none`` mode, returns ``"anonymous"`` regardless of header presence so
    behavior matches the existing per-agent FeedbackStore default.
    """

    settings = get_settings()

    if settings.auth_mode == "none":
        return "anonymous"

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()

    try:
        jwks = await _fetch_jwks(settings)
        unverified = jwt.get_unverified_header(token)
        kid = unverified.get("kid")
        key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if key is None:
            # JWKS may have rotated -- bust cache once and retry.
            _jwks_cache["keys"] = None
            jwks = await _fetch_jwks(settings)
            key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
        if key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="signing key not found",
            )
        claims = jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "RS256")],
            audience=settings.keycloak_audience,
            issuer=settings.keycloak_issuer,
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 -- jose raises a soup of exception types
        logger.warning("token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        ) from exc

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="token missing sub claim",
        )
    return sub
