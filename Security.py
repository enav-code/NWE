import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import request, g

import Config
from Storage import append_audit


# ---------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------

def password_policy_error(password):
    if not password or len(password) < 10:
        return "password must be at least 10 characters"
    classes = [
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ]
    if sum(classes) < 3:
        return "password must include at least 3 character types (upper, lower, digit, symbol)"
    return None


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_jwt(user_id, business_id, username, role, company_name, remember=False):
    expiry = timedelta(days=Config.JWT_REMEMBER_DAYS) if remember else timedelta(hours=Config.JWT_EXPIRY_HOURS)
    payload = {
        "user_id": user_id,
        "business_id": business_id,   # Always None for adminos — they belong to no business
        "username": username,
        "role": role,
        "company_name": company_name, # Always "Platform" for adminos
        "exp": datetime.utcnow() + expiry,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm=Config.JWT_ALGORITHM)


def decode_jwt(token):
    return jwt.decode(token, Config.SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])


def get_token_from_request():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("token")


def current_user():
    token = get_token_from_request()
    if not token:
        return None
    try:
        return decode_jwt(token)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Decorators
#
# Three tiers, strictly separated:
#
#   login_required       — any authenticated user (all roles)
#   business_admin_required — BusinessAdmin within a specific business ONLY
#                             adminos are BLOCKED; they use /api/admino/* instead
#   admino_required      — platform-level admino ONLY, no business context
# ---------------------------------------------------------------------------

def login_required(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        user = current_user()
        if not user:
            return {"msg": "unauthorized"}, 401
        # Adminos must use /api/admino/* routes, not business routes
        if user.get("role") == "admino":
            log_security_event("permission_denied", user.get("username"), {
                "reason": "adminos must use /api/admino/* endpoints",
                "path": request.path,
            })
            return {"msg": "adminos do not belong to a business — use /api/admino/* endpoints"}, 403
        g.user = user
        return fn(*args, **kwargs)
    return inner


def business_admin_required(fn):
    """
    Requires the caller to be a BusinessAdmin within their own business.
    Adminos are explicitly REJECTED — they are platform-level and have
    no business_id. They manage businesses via /api/admino/* only.
    """
    @wraps(fn)
    def inner(*args, **kwargs):
        user = current_user()
        if not user:
            return {"msg": "unauthorized"}, 401
        if user.get("role") == "admino":
            log_security_event("permission_denied", user.get("username"), {
                "reason": "adminos are not connected to businesses",
                "path": request.path,
            })
            return {"msg": "adminos are not connected to businesses — use /api/admino/* endpoints"}, 403
        if user.get("role") != "BusinessAdmin":
            log_security_event("permission_denied", user.get("username"), {
                "required": "BusinessAdmin",
                "actual": user.get("role"),
                "path": request.path,
            })
            return {"msg": "forbidden – BusinessAdmin role required"}, 403
        g.user = user
        return fn(*args, **kwargs)
    return inner


def admino_required(fn):
    """
    Requires the caller to be a platform-level admino.
    BusinessAdmins and all other business roles are rejected.
    Adminos have no business_id and never touch business-scoped routes.
    """
    @wraps(fn)
    def inner(*args, **kwargs):
        user = current_user()
        if not user:
            return {"msg": "unauthorized"}, 401
        if user.get("role") != "admino":
            log_security_event("permission_denied", user.get("username"), {
                "required": "admino",
                "actual": user.get("role"),
                "path": request.path,
            })
            return {"msg": "forbidden – admino role required"}, 403
        g.user = user
        return fn(*args, **kwargs)
    return inner


def api_errors(fn):
    @wraps(fn)
    def inner(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            return {"msg": str(exc)}, 400
        except Exception as exc:
            log_security_event("server_error", request.path, {"error": type(exc).__name__})
            return {"msg": "server error"}, 500
    return inner


# ---------------------------------------------------------------------------
# Rate limiting (in-memory)
# ---------------------------------------------------------------------------

_RATE_BUCKETS = defaultdict(deque)


def rate_limited(name, limit=10, window=60):
    def outer(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            ip = _client_ip()
            key = (name, ip)
            now = time.time()
            bucket = _RATE_BUCKETS[key]
            while bucket and bucket[0] <= now - window:
                bucket.popleft()
            if len(bucket) >= limit:
                log_security_event("rate_limited", name, {"ip": ip})
                return {"msg": "rate limited – try again later"}, 429
            bucket.append(now)
            return fn(*args, **kwargs)
        return inner
    return outer


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------

def log_security_event(action, target=None, details=None):
    user = current_user()
    append_audit({
        "timestamp": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "actor": user.get("username") if user else "system",
        "business_id": user.get("business_id") if user else None,  # None for adminos
        "action": action,
        "target": target,
        "details": details or {},
    })


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()