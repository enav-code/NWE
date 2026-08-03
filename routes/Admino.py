from flask import Blueprint, request, g

from Security import (
    admino_required,
    api_errors,
    log_security_event,
    password_policy_error,
)
from Storage import (
    add_user_to_business,
    create_admino,
    deactivate_admino,
    delete_business,
    get_business,
    get_team,
    list_adminos,
    list_businesses,
    load_audit_logs,
    platform_stats,
    set_business_active,
)

admino_bp = Blueprint("admino", __name__, url_prefix="/api/admino")


# ── Platform overview ────────────────────────────────────────────────────────

@admino_bp.route("/stats", methods=["GET"])
@api_errors
@admino_required
def stats():
    return platform_stats()


@admino_bp.route("/businesses", methods=["GET"])
@api_errors
@admino_required
def businesses():
    return {"businesses": list_businesses()}


@admino_bp.route("/business/<biz_id>", methods=["GET"])
@api_errors
@admino_required
def business_detail(biz_id):
    biz = get_business(biz_id)
    if not biz:
        return {"msg": "business not found"}, 404
    # Return full detail including users (no passwords)
    safe_users = [
        {k: v for k, v in u.items() if k != "password"}
        for u in biz["users"].values()
    ]
    return {
        "business_id": biz["business_id"],
        "company_name": biz["company_name"],
        "active": biz.get("active", True),
        "created_at": biz.get("created_at"),
        "users": safe_users,
        "total_users": len(safe_users),
    }


@admino_bp.route("/business/<biz_id>/team", methods=["GET"])
@api_errors
@admino_required
def business_team(biz_id):
    team = get_team(biz_id)
    return {"team": team, "total": len(team)}


# ── Business control ─────────────────────────────────────────────────────────

@admino_bp.route("/suspend-business", methods=["POST"])
@api_errors
@admino_required
def suspend_business():
    body = request.get_json() or {}
    biz_id = (body.get("business_id") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not biz_id:
        return {"msg": "business_id is required"}, 400
    set_business_active(biz_id, False)
    log_security_event("suspend_business", biz_id, {"reason": reason, "admino": g.user["username"]})
    return {"msg": "business suspended"}


@admino_bp.route("/reinstate-business", methods=["POST"])
@api_errors
@admino_required
def reinstate_business():
    body = request.get_json() or {}
    biz_id = (body.get("business_id") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not biz_id:
        return {"msg": "business_id is required"}, 400
    set_business_active(biz_id, True)
    log_security_event("reinstate_business", biz_id, {"reason": reason, "admino": g.user["username"]})
    return {"msg": "business reinstated"}


@admino_bp.route("/delete-business", methods=["POST"])
@api_errors
@admino_required
def remove_business():
    body = request.get_json() or {}
    biz_id = (body.get("business_id") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not biz_id:
        return {"msg": "business_id is required"}, 400
    delete_business(biz_id)
    log_security_event("delete_business", biz_id, {"reason": reason, "admino": g.user["username"]})
    return {"msg": "business deleted"}


# ── User control across any business ─────────────────────────────────────────

@admino_bp.route("/add-user-to-business", methods=["POST"])
@api_errors
@admino_required
def add_user():
    body = request.get_json() or {}
    biz_id = (body.get("business_id") or "").strip()
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = (body.get("role") or "Employee").strip()

    if not biz_id or not username or not password:
        return {"msg": "business_id, username, and password are required"}, 400

    err = password_policy_error(password)
    if err:
        return {"msg": err}, 400

    user_id = add_user_to_business(biz_id, username, password, role)
    log_security_event("admino_add_user", username, {"business_id": biz_id, "role": role})
    return {"msg": "user created", "user_id": user_id}


# ── Admino management ────────────────────────────────────────────────────────

@admino_bp.route("/adminos", methods=["GET"])
@api_errors
@admino_required
def get_adminos():
    return {"adminos": list_adminos()}


@admino_bp.route("/create-admino", methods=["POST"])
@api_errors
@admino_required
def make_admino():
    body = request.get_json() or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""

    if not username or not password:
        return {"msg": "username and password are required"}, 400

    err = password_policy_error(password)
    if err:
        return {"msg": err}, 400

    user_id = create_admino(username, password)
    log_security_event("create_admino", username, {"created_by": g.user["username"]})
    return {"msg": "admino created", "user_id": user_id}


@admino_bp.route("/deactivate-admino", methods=["POST"])
@api_errors
@admino_required
def remove_admino():
    body = request.get_json() or {}
    user_id = (body.get("user_id") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not user_id:
        return {"msg": "user_id is required"}, 400
    if user_id == g.user["user_id"]:
        return {"msg": "you cannot deactivate yourself"}, 400
    deactivate_admino(user_id)
    log_security_event("deactivate_admino", user_id, {"reason": reason, "admino": g.user["username"]})
    return {"msg": "admino deactivated"}


@admino_bp.route("/delete-admino", methods=["POST"])
@api_errors
@admino_required
def destroy_admino():
    body = request.get_json() or {}
    user_id = (body.get("user_id") or "").strip()
    reason = (body.get("reason") or "").strip()
    if not user_id:
        return {"msg": "user_id is required"}, 400
    if user_id == g.user["user_id"]:
        return {"msg": "you cannot delete yourself"}, 400
    delete_admino(user_id)
    log_security_event("delete_admino", user_id, {"reason": reason, "admino": g.user["username"]})
    return {"msg": "admino deleted"}


# ── Audit logs (all businesses) ───────────────────────────────────────────────

@admino_bp.route("/logs", methods=["GET"])
@api_errors
@admino_required
def logs():
    all_logs = load_audit_logs()
    biz_filter = request.args.get("business_id")
    action_filter = request.args.get("action")
    if biz_filter:
        all_logs = [l for l in all_logs if l.get("business_id") == biz_filter]
    if action_filter:
        all_logs = [l for l in all_logs if l.get("action") == action_filter]
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))
    except ValueError:
        return {"msg": "invalid pagination"}, 400
    total = len(all_logs)
    start = (page - 1) * per_page
    return {"logs": all_logs[start:start + per_page], "total": total, "page": page}
