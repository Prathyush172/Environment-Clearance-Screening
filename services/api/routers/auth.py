"""Authentication router: login, registration, logout, and current user profile."""

import uuid
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from sqlalchemy import select, or_

from libs.common.db.session import get_db_session
from libs.common.db.models import User, UserSession, utcnow
from services.api.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    check_rate_limit,
    record_failed_attempt,
    clear_failed_attempts,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username_or_email: str = Field(..., min_length=3, description="Username or email address")
    password: str = Field(..., min_length=1, description="Account password")


class RegisterRequest(BaseModel):
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", description="Valid email address")
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    password: str = Field(..., min_length=8, description="Password (at least 8 characters)")
    full_name: Optional[str] = Field(None, max_length=255)
    client_id: Optional[str] = Field(None, max_length=64)


class UserProfileResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: Optional[str]
    role: str
    client_id: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfileResponse


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request, response: Response):
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{req.username_or_email.lower().strip()}"

    if not check_rate_limit(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 5 minutes before trying again.",
        )

    identifier = req.username_or_email.strip()
    async with get_db_session() as session:
        query = select(User).where(
            or_(
                User.username == identifier,
                User.email == identifier.lower(),
            )
        )
        res = await session.execute(query)
        user = res.scalar_one_or_none()

        if not user or not verify_password(req.password, user.hashed_password):
            record_failed_attempt(rate_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username/email or password",
            )

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated. Please contact an administrator.",
            )

        clear_failed_attempts(rate_key)
        token, jti, expires_at = create_access_token(user)

        # Record active session in DB for revocation tracking
        sess_record = UserSession(
            id=str(uuid.uuid4()),
            jti=jti,
            user_id=user.id,
            revoked=False,
            expires_at=expires_at,
        )
        session.add(sess_record)

    # Set secure session cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfileResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role,
            client_id=user.client_id,
        ),
    )


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, response: Response):
    async with get_db_session() as session:
        # Check duplicate username or email
        existing_query = select(User).where(
            or_(
                User.username == req.username,
                User.email == req.email.lower(),
            )
        )
        res = await session.execute(existing_query)
        existing = res.scalar_one_or_none()
        if existing:
            if existing.username == req.username:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username is already taken")
            else:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

        user_id = str(uuid.uuid4())
        client_id = req.client_id.strip() if req.client_id else f"client_{req.username}"
        new_user = User(
            id=user_id,
            email=req.email.lower().strip(),
            username=req.username.strip(),
            hashed_password=hash_password(req.password),
            full_name=req.full_name.strip() if req.full_name else req.username,
            role="user",
            client_id=client_id,
            is_active=True,
        )
        session.add(new_user)
        await session.flush()

        token, jti, expires_at = create_access_token(new_user)
        sess_record = UserSession(
            id=str(uuid.uuid4()),
            jti=jti,
            user_id=new_user.id,
            revoked=False,
            expires_at=expires_at,
        )
        session.add(sess_record)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfileResponse(
            id=new_user.id,
            email=new_user.email,
            username=new_user.username,
            full_name=new_user.full_name,
            role=new_user.role,
            client_id=new_user.client_id,
        ),
    )


@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    jti = getattr(current_user, "_active_jti", None)
    if jti:
        async with get_db_session() as session:
            q = select(UserSession).where(UserSession.jti == jti)
            r = await session.execute(q)
            sess = r.scalar_one_or_none()
            if sess:
                sess.revoked = True
                sess.revoked_at = utcnow()
                session.add(sess)

    response.delete_cookie(key="access_token")
    return {"status": "logged_out", "message": "Successfully logged out and session revoked"}


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        role=current_user.role,
        client_id=current_user.client_id,
    )
