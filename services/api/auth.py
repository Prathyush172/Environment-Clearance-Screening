"""Authentication, password hashing, and JWT token management for EIA Pre-Screening."""

import uuid
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Dict, List
import bcrypt
import jwt
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy import select

from libs.common.config import settings
from libs.common.db.session import get_db_session
from libs.common.db.models import User, UserSession, utcnow


# In-memory failed login tracking for brute-force mitigation
# Keyed by username or client IP -> list of timestamps
_failed_login_attempts: Dict[str, List[float]] = {}


def hash_password(password: str) -> str:
    """Hash password using bcrypt with a unique salt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def check_rate_limit(key: str) -> bool:
    """Return True if under rate limit; False if locked out."""
    now = time.time()
    lockout_sec = getattr(settings, "AUTH_LOCKOUT_MINUTES", 5) * 60
    max_attempts = getattr(settings, "AUTH_MAX_FAILED_ATTEMPTS", 5)

    attempts = _failed_login_attempts.get(key, [])
    # Filter attempts within lockout window
    recent = [t for t in attempts if now - t < lockout_sec]
    _failed_login_attempts[key] = recent
    return len(recent) < max_attempts


def record_failed_attempt(key: str) -> None:
    """Record a failed login attempt."""
    now = time.time()
    attempts = _failed_login_attempts.get(key, [])
    attempts.append(now)
    _failed_login_attempts[key] = attempts


def clear_failed_attempts(key: str) -> None:
    """Clear failed attempts upon successful login."""
    _failed_login_attempts.pop(key, None)


def create_access_token(user: User) -> Tuple[str, str, datetime]:
    """Create signed JWT access token and return (token, jti, expires_at)."""
    now = datetime.now(timezone.utc)
    expire_minutes = getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 1440)
    expires_at = now + timedelta(minutes=expire_minutes)
    jti = str(uuid.uuid4())

    payload = {
        "sub": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "client_id": user.client_id,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    secret = getattr(settings, "JWT_SECRET_KEY", "change-me-jwt-secret-key-32chars-min-dev-only")
    algo = getattr(settings, "JWT_ALGORITHM", "HS256")
    token = jwt.encode(payload, secret, algorithm=algo)
    return token, jti, expires_at


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    secret = getattr(settings, "JWT_SECRET_KEY", "change-me-jwt-secret-key-32chars-min-dev-only")
    algo = getattr(settings, "JWT_ALGORITHM", "HS256")
    return jwt.decode(token, secret, algorithms=[algo])


async def get_current_user(request: Request) -> User:
    """Extract and validate bearer token or cookie; return authenticated User."""
    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif "access_token" in request.cookies:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    user_id = payload.get("sub")

    if not jti or not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token claims",
        )

    # Check database session revocation & user state
    async with get_db_session() as session:
        # Check revocation
        s_query = select(UserSession).where(UserSession.jti == jti)
        s_res = await session.execute(s_query)
        user_sess = s_res.scalar_one_or_none()
        if user_sess and user_sess.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked. Please log in again.",
            )

        # Check user
        u_query = select(User).where(User.id == user_id)
        u_res = await session.execute(u_query)
        user = u_res.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive or not found",
            )

        # Attach active jti to user object for reference during logout
        user._active_jti = jti
        return user


def require_role(*allowed_roles: str):
    """Dependency factory checking user role."""
    async def _role_checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{user.role}' lacks permission for this resource",
            )
        return user
    return _role_checker
