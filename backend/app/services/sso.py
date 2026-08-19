from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from ldap3 import ALL, Connection, Server
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auth import hash_password
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import User


class SSOService:
    def status(self) -> dict:
        settings = get_settings()
        providers = []
        if settings.oidc_issuer and settings.oidc_client_id: providers.append("oidc")
        if settings.ldap_url and settings.ldap_base_dn: providers.append("ldap")
        return {"oidc_configured": "oidc" in providers, "ldap_configured": "ldap" in providers, "providers": providers}

    def oidc_start(self) -> dict:
        settings = get_settings()
        if not settings.oidc_issuer or not settings.oidc_client_id:
            raise AppError(503, "OIDC_NOT_CONFIGURED", "OIDC SSO 尚未配置")
        discovery = self._discovery(settings.oidc_issuer)
        nonce = secrets.token_urlsafe(24)
        state = jwt.encode({"type": "oidc_state", "nonce": nonce, "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        query = urlencode({"client_id": settings.oidc_client_id, "response_type": "code", "scope": "openid email profile", "redirect_uri": settings.oidc_redirect_uri, "state": state, "nonce": nonce})
        return {"authorizationUrl": f"{discovery['authorization_endpoint']}?{query}", "state": state}

    def oidc_callback(self, db: Session, code: str, state: str) -> User:
        settings = get_settings()
        try:
            claims = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        except jwt.PyJWTError as exc:
            raise AppError(400, "OIDC_STATE_INVALID", "OIDC state 无效或已过期") from exc
        if claims.get("type") != "oidc_state": raise AppError(400, "OIDC_STATE_INVALID", "OIDC state 类型错误")
        discovery = self._discovery(settings.oidc_issuer)
        with httpx.Client(timeout=20) as client:
            token_response = client.post(discovery["token_endpoint"], data={"grant_type": "authorization_code", "code": code, "redirect_uri": settings.oidc_redirect_uri, "client_id": settings.oidc_client_id, "client_secret": settings.oidc_client_secret})
            token_response.raise_for_status(); tokens = token_response.json()
        id_token = tokens.get("id_token")
        if not id_token: raise AppError(502, "OIDC_ID_TOKEN_MISSING", "OIDC 服务未返回 id_token")
        try:
            key = jwt.PyJWKClient(discovery["jwks_uri"]).get_signing_key_from_jwt(id_token)
            profile = jwt.decode(id_token, key.key, algorithms=[key.algorithm_name], audience=settings.oidc_client_id, issuer=settings.oidc_issuer)
        except jwt.PyJWTError as exc:
            raise AppError(401, "OIDC_TOKEN_INVALID", "OIDC 身份令牌校验失败") from exc
        email = str(profile.get("email", "")).lower()
        if not email: raise AppError(422, "OIDC_EMAIL_MISSING", "企业身份未提供邮箱")
        return self._provision(db, email, str(profile.get("name") or email.split("@")[0]), "oidc")

    def ldap_login(self, db: Session, username: str, password: str) -> User:
        settings = get_settings()
        if not settings.ldap_url or not settings.ldap_base_dn:
            raise AppError(503, "LDAP_NOT_CONFIGURED", "LDAP SSO 尚未配置")
        server = Server(settings.ldap_url, get_info=ALL, connect_timeout=8)
        search_conn = Connection(server, user=settings.ldap_bind_dn or None, password=settings.ldap_bind_password or None, auto_bind=True)
        safe_username = username.replace("*", "").replace("(", "").replace(")", "")
        search_conn.search(settings.ldap_base_dn, f"(|(mail={safe_username})(sAMAccountName={safe_username})(uid={safe_username}))", attributes=["mail", "displayName", "cn", "distinguishedName"])
        if not search_conn.entries: raise AppError(401, "LDAP_INVALID_CREDENTIALS", "LDAP 用户名或密码错误")
        entry = search_conn.entries[0]
        dn = str(entry.entry_dn)
        try:
            Connection(server, user=dn, password=password, auto_bind=True).unbind()
        except Exception as exc:
            raise AppError(401, "LDAP_INVALID_CREDENTIALS", "LDAP 用户名或密码错误") from exc
        email = str(entry.mail.value if "mail" in entry and entry.mail.value else username).lower()
        name = str(entry.displayName.value if "displayName" in entry and entry.displayName.value else (entry.cn.value if "cn" in entry else username))
        return self._provision(db, email, name, "ldap")

    def _provision(self, db: Session, email: str, display_name: str, source: str) -> User:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, display_name=display_name, password_hash=hash_password(secrets.token_urlsafe(32)), platform_role="user", auth_source=source, is_active=True)
            db.add(user); db.flush()
        else:
            user.display_name = display_name; user.auth_source = source
        user.last_login_at = datetime.now(timezone.utc)
        return user

    @staticmethod
    def _discovery(issuer: str) -> dict:
        try:
            response = httpx.get(f"{issuer}/.well-known/openid-configuration", timeout=15)
            response.raise_for_status(); return response.json()
        except httpx.HTTPError as exc:
            raise AppError(502, "OIDC_DISCOVERY_FAILED", "无法读取 OIDC Discovery 文档") from exc


sso_service = SSOService()
