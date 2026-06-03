import hashlib
from datetime import datetime, timedelta

from flask import Blueprint, request, session
from werkzeug.security import generate_password_hash, check_password_hash

from Storage import load_users, save_users
from Security import (
    api_errors,
    create_tracked_session,
    log_security_event,
    login_required,
    permissions_for,
    rate_limited,
    revoke_current_session,
)
print("AUTH FILE LOADED")
auth_bp = Blueprint("auth", __name__)
print(auth_bp)
LOCKOUT_LIMIT = 5
LOCKOUT_MINUTES = 15


def parse_dt(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", ""))
    except ValueError:
        return None


@auth_bp.route("/login", methods=["POST"])
@api_errors
@rate_limited("login", limit=8, window=60)
def login():

    users = load_users()

    req = request.get_json() or {}

    username = req.get("username")
    password = req.get("password")
    remember = bool(req.get("remember"))

    if not username or not password:
        return {"msg": "invalid request"}, 400

    user = next(
        (u for u in users if u["username"] == username),
        None
    )

    if user:

        locked_until = parse_dt(user.get("locked_until"))

        if locked_until and locked_until > datetime.utcnow():
            return {"msg": "account locked"}, 423

        stored = user.get("password", "")

        try:
            valid = check_password_hash(stored, password)
        except Exception:
            valid = False

        if not valid:

            if len(stored) == 64:

                valid = (
                    hashlib.sha256(password.encode()).hexdigest()
                    == stored
                )

                if valid:
                    user["password"] = generate_password_hash(password)
                    save_users(users)

        if valid:

            if not user.get("active", True):
                return {"msg": "disabled"}, 403

            user["failed_logins"] = 0
            user.pop("locked_until", None)

            save_users(users)

            create_tracked_session(
                user["username"],
                user.get("role", "viewer"),
                remember,
                user.get("permissions", [])
            )

            log_security_event(
                "login_success",
                user["username"]
            )

            return {"msg": "ok"}

        user["failed_logins"] = int(
            user.get("failed_logins", 0)
        ) + 1

        if user["failed_logins"] >= LOCKOUT_LIMIT:

            until = datetime.utcnow() + timedelta(
                minutes=LOCKOUT_MINUTES
            )

            user["locked_until"] = until.isoformat() + "Z"

        save_users(users)

    log_security_event(
        "failed_login",
        username
    )

    return {"msg": "fail"}, 401


@auth_bp.route("/register", methods=["POST"])
@api_errors
@rate_limited("register", limit=5, window=60)
def register():

    users = load_users()

    req = request.get_json() or {}

    username = req.get("username")
    password = req.get("password")

    if not username or not password:
        return {"msg": "invalid request"}, 400

    if any(u["username"] == username for u in users):
        return {"msg": "exists"}, 409

    # First user becomes admin
    role = "admin" if len(users) == 0 else "viewer"
    
    users.append({
        "username": username,
        "password": generate_password_hash(password),
        "role": role,
        "active": True,
        "deleted": False,
        "permissions": []
    })

    save_users(users)

    log_security_event(
        "register_user",
        username
    )

    return {"msg": "created"}


@auth_bp.route("/me", methods=["GET"])
@login_required
@api_errors
def me():

    return {
        "username": session["user"],
        "role": session["role"],
        "permissions": permissions_for(
            session["role"],
            session.get("permissions", [])
        ),
        "session_id": session.get("sid")
    }


@auth_bp.route("/logout", methods=["POST"])
@api_errors
def logout():

    revoke_current_session()

    return {"msg": "ok"}