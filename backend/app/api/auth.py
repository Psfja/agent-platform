from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import audit, create_tokens, decode_token, get_current_user, verify_password
from app.core.errors import AppError
from app.database import get_db
from app.models import RefreshToken, User
from app.schemas import LDAPLoginRequest, LoginRequest, LogoutRequest, OIDCCallbackRequest, RefreshRequest, SSOStatusResponse, TokenResponse, UserResponse
from app.services.sso import sso_service

router = APIRouter(prefix="/auth", tags=["authentication"])


def user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name, platform_role=user.platform_role, department=user.department, is_active=user.is_active, auth_source=user.auth_source, last_login_at=user.last_login_at)


@router.get("/sso/status", response_model=SSOStatusResponse)
def sso_status() -> SSOStatusResponse:
    return SSOStatusResponse(**sso_service.status())


@router.get("/sso/oidc/start")
def oidc_start() -> dict:
    return sso_service.oidc_start()


@router.post("/sso/oidc/callback", response_model=TokenResponse)
def oidc_callback(payload: OIDCCallbackRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = sso_service.oidc_callback(db, payload.code, payload.state)
    access, refresh, expires = create_tokens(db, user)
    audit(db, user, "auth.sso.oidc", resource_type="user", resource_id=user.id, request=request)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires, user=user_response(user))


@router.post("/sso/ldap", response_model=TokenResponse)
def ldap_login(payload: LDAPLoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = sso_service.ldap_login(db, payload.username, payload.password)
    access, refresh, expires = create_tokens(db, user)
    audit(db, user, "auth.sso.ldap", resource_type="user", resource_id=user.id, request=request)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires, user=user_response(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise AppError(401, "INVALID_CREDENTIALS", "邮箱或密码错误")
    user.last_login_at = datetime.now(timezone.utc)
    access, refresh, expires = create_tokens(db, user)
    audit(db, user, "auth.login", resource_type="user", resource_id=user.id, request=request)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires, user=user_response(user))


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    claims = decode_token(payload.refresh_token, "refresh")
    token_hash = hashlib.sha256(str(claims["jti"]).encode()).hexdigest()
    record = db.scalar(select(RefreshToken).where(RefreshToken.jti_hash == token_hash))
    now = datetime.now(timezone.utc)
    if not record or record.revoked_at is not None or record.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise AppError(401, "REFRESH_TOKEN_REVOKED", "刷新凭据已撤销或过期")
    user = db.get(User, claims["sub"])
    if not user or not user.is_active:
        raise AppError(401, "USER_DISABLED", "用户不存在或已停用")
    record.revoked_at = now
    access, refresh, expires = create_tokens(db, user)
    audit(db, user, "auth.refresh", resource_type="user", resource_id=user.id, request=request)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh, expires_in=expires, user=user_response(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, request: Request, db: Session = Depends(get_db)):
    try:
        claims = decode_token(payload.refresh_token, "refresh")
        token_hash = hashlib.sha256(str(claims["jti"]).encode()).hexdigest()
        record = db.scalar(select(RefreshToken).where(RefreshToken.jti_hash == token_hash))
        if record and record.revoked_at is None:
            record.revoked_at = datetime.now(timezone.utc)
            user = db.get(User, claims["sub"])
            audit(db, user, "auth.logout", resource_type="user", resource_id=claims["sub"], request=request)
            db.commit()
    except AppError:
        pass
    return None


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> UserResponse:
    return user_response(user)
