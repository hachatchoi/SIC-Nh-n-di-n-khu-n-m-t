"""Teacher sessions; passwords and session tokens are never stored in plaintext."""
import hashlib
import hmac
import os
import re
import secrets
import time
from contextvars import ContextVar

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/auth")
actor = ContextVar("teacher", default=None)
COOKIE = "attendance_session"
TTL = 8 * 60 * 60


def database():
    from classroom import database as connect
    return connect()


def password_hash(password):
    if not 6 <= len(password) <= 128:
        raise ValueError("Mật khẩu phải dài từ 6 đến 128 ký tự.")
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return salt + ":" + digest


def verify(password, encoded):
    salt, digest = encoded.split(":")
    result = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(result, digest)


def current_teacher():
    user = actor.get()
    if user is None:
        raise HTTPException(401, "Vui lòng đăng nhập.")
    return user


def same_origin(request):
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site" or (
        origin and origin != str(request.base_url).rstrip("/")
    ):
        raise HTTPException(403, "Yêu cầu không cùng nguồn.")


def session_user(request):
    token = request.cookies.get(COOKIE, "")
    digest = hashlib.sha256(token.encode()).hexdigest()
    with database() as db:
        row = db.execute("""SELECT t.id,t.username,t.name,t.role FROM teachers t
            JOIN auth_sessions s ON s.teacher_id=t.id
            WHERE s.token_hash=? AND s.expires_at>? AND t.active=1""", (digest, time.time())).fetchone()
    if row is None:
        raise HTTPException(401, "Phiên đăng nhập đã hết hạn hoặc chưa đăng nhập.")
    return dict(row)


async def require_teacher(request: Request):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        same_origin(request)
        if request.headers.get("x-requested-with") != "attendance-web":
            raise HTTPException(403, "Thiếu thông tin xác thực yêu cầu.")
    token = actor.set(session_user(request))
    try:
        yield
    finally:
        actor.reset(token)


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=128)


DUMMY = password_hash("unused-dummy-password")


@router.post("/login")
def login(data: LoginInput, request: Request, response: Response):
    same_origin(request)
    username = data.username.strip().lower()
    # Persistent rate limit per client and username, shared by server workers.
    key = hashlib.sha256(f"{request.client.host if request.client else ''}:{username}".encode()).hexdigest()
    now = time.time()
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("DELETE FROM login_attempts WHERE started_at<?", (now-900,))
        attempt = db.execute("SELECT count FROM login_attempts WHERE key=?", (key,)).fetchone()
        if attempt and attempt[0] >= 10:
            raise HTTPException(429, "Thử đăng nhập quá nhiều lần. Vui lòng thử lại sau 15 phút.")
        db.execute("INSERT INTO login_attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1", (key, now))
        row = db.execute("SELECT * FROM teachers WHERE username=? AND active=1", (username,)).fetchone()
    if not verify(data.password, row['password_hash'] if row else DUMMY) or row is None:
        raise HTTPException(401, "Tên đăng nhập hoặc mật khẩu không đúng.")
    token = secrets.token_urlsafe(32)
    with database() as db:
        db.execute("DELETE FROM login_attempts WHERE key=?", (key,))
        db.execute("DELETE FROM auth_sessions WHERE expires_at<=?", (now,))
        db.execute("INSERT INTO auth_sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(),row['id'],now+TTL))
    response.set_cookie(COOKIE, token, max_age=TTL, httponly=True, samesite="strict",
                        secure=request.url.scheme == "https" or os.getenv("AUTH_COOKIE_SECURE") == "1")
    response.headers['Cache-Control'] = 'no-store'
    return {"id":row['id'], "username":row['username'], "name":row['name'], "role":row['role']}


@router.get("/me")
def me(request: Request):
    return session_user(request)


@router.post("/logout")
def logout(request: Request, response: Response):
    same_origin(request)
    digest = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
    with database() as db:
        db.execute("DELETE FROM auth_sessions WHERE token_hash=?", (digest,))
    response.delete_cookie(COOKIE)
    return {"status":"logged_out"}


def require_admin():
    user = current_teacher()
    if user.get('role') != 'admin':
        raise HTTPException(403, "Chỉ admin được quản lý lớp môn học và ghi danh sinh viên.")
    return user
