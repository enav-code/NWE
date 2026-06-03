from flask import Blueprint, request, g
from werkzeug.security import generate_password_hash, check_password_hash

from Security import (
    api_errors,
    create_jwt,
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
    load_store,
)

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register-business", methods=["POST"])
@api_errors
@rate_limited("register", limit=5, window=60)
def register_business():
    body = request.get_json() or {}
    company_name = (body.get("company_name") or "").strip()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not company_name or not username or not password:
        return {"msg": "company_name, username, and password are required"}, 400

    err = password_policy_error(password)
    if err:
        return {"msg": err}, 400

    hashed = generate_password_hash(password)
    biz_id, user_id = create_business(company_name, username, hashed)

    log_security_event("register_business", username, {
        "business_id": biz_id,
        "company_name": company_name,
    })

    token = create_jwt(user_id, biz_id, username, "BusinessAdmin", company_name)
    return {"msg": "created", "token": token, "business_id": biz_id, "user_id": user_id}


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

    # Check adminos first
    admino = find_admino_by_username(username)
    if admino:
        if not check_password_hash(admino["password"], password):
            log_security_event("failed_login", username, {"known_user": True})
            return {"msg": "invalid credentials"}, 401
        if not admino.get("active"):
            return {"msg": "account disabled"}, 403
        log_security_event("login_success", username, {"role": "admino"})
        token = create_jwt(admino["user_id"], None, username, "admino", "Platform", remember)
        return {"msg": "ok", "token": token}

    # Then check business users
    user, biz_id, company_name = find_user_by_username(username)
    if not user or not check_password_hash(user["password"], password):
        log_security_event("failed_login", username, {"known_user": bool(user)})
        return {"msg": "invalid credentials"}, 401
    if not user.get("active"):
        return {"msg": "account disabled"}, 403

    log_security_event("login_success", username, {"business_id": biz_id})
    token = create_jwt(user["user_id"], biz_id, username, user["role"], company_name, remember)
    return {"msg": "ok", "token": token}


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


@auth_bp.route("/setup-admino", methods=["POST"])
@api_errors
def setup_admino():
    """
    One-time bootstrap endpoint. Creates the first admino account.
    Locked out once any admino exists.
    """
    store = load_store()
    if store["adminos"]:
        return {"msg": "admino already exists – use /api/admino/create-admino"}, 403

    body = request.get_json() or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return {"msg": "username and password are required"}, 400

    err = password_policy_error(password)
    if err:
        return {"msg": err}, 400

    user_id = create_admino(username, generate_password_hash(password))
    log_security_event("setup_admino", username)
    token = create_jwt(user_id, None, username, "admino", "Platform")
    return {"msg": "admino created", "user_id": user_id, "token": token}