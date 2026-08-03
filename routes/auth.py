from flask import Blueprint, request, g

import Config
from Security import (
    api_errors,
    create_csrf_token,
    current_user,
    log_security_event,
    login_required,
    password_policy_error,
    rate_limited,
    admino_required,
)
from Storage import (
    create_business,
    create_admino,
    find_admino_by_username,
    find_user_by_username,
    list_adminos,
    sign_in_with_supabase,
    sign_out_supabase,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/csrf", methods=["GET"])
def csrf():
    return {"csrf_token": create_csrf_token()}


@auth_bp.route("/register-business", methods=["POST"])
@api_errors
@rate_limited("register", limit=5, window=60)
def register_business():
    body = request.get_json() or {}
    company_name = (body.get("company_name") or "").strip()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    remember = bool(body.get("remember"))

    if not company_name or not username or not password:
        return {"msg": "company_name, username, and password are required"}, 400

    err = password_policy_error(password)
    if err:
        return {"msg": err}, 400

    biz_id, user_id, access_token = create_business(company_name, username, password)

    log_security_event("register_business", username, {
        "business_id": biz_id,
        "company_name": company_name,
    })

    return {
        "msg": "created",
        "token": access_token,
        "business_id": biz_id,
        "user_id": user_id,
    }


@auth_bp.route("/login", methods=["POST"])
@api_errors
@rate_limited("login", limit=8, window=60)
def login():
    body = request.get_json() or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    remember = bool(body.get("remember"))

    if not username or not password:
        return {"msg": "username and password are required"}, 400

    session = sign_in_with_supabase(username, password)
    if not session:
        log_security_event("failed_login", username, {"known_user": bool(find_user_by_username(username)[0])})
        return {"msg": "invalid credentials"}, 401

    user, biz_id, company_name = find_user_by_username(username)
    if not user:
        return {"msg": "invalid credentials"}, 401
    if not user.get("active", True):
        return {"msg": "account disabled"}, 403

    log_security_event("login_success", username, {"business_id": biz_id, "role": user.get("role")})
    return {
        "msg": "ok",
        "token": session["access_token"],
        "user_id": user.get("id") or user.get("user_id"),
        "business_id": biz_id,
        "company_name": company_name,
        "role": user.get("role"),
    }


@auth_bp.route("/logout", methods=["POST"])
@api_errors
def logout():
    user = current_user()
    if user:
        log_security_event("logout", user.get("username"))
    sign_out_supabase()
    return {"msg": "ok"}


@auth_bp.route("/me", methods=["GET"])
@api_errors
@login_required
def me():
    u = g.user
    return {
        "user_id": u["user_id"],
        "username": u["username"],
        "role": u["role"],
        "business_id": u.get("business_id"),
        "company_name": u.get("company_name"),
    }


@auth_bp.route("/register", methods=["POST"])
def register_alias():
    return register_business()


@auth_bp.route("/setup-admino", methods=["POST"])
@api_errors
def setup_admino():
    """
    One-time bootstrap endpoint. Creates the first admino account.
    Locked out once any admino exists.
    """
    body = request.get_json() or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return {"msg": "username and password are required"}, 400

    if find_admino_by_username(username):
        return {"msg": "admino already exists – use /api/admino/create-admino"}, 403

    err = password_policy_error(password)
    if err:
        return {"msg": err}, 400

    user_id = create_admino(username, password)
    log_security_event("setup_admino", username)
    return {"msg": "admino created", "user_id": user_id}