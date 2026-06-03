from datetime import datetime
from flask import Blueprint, request, session, send_from_directory
from werkzeug.security import generate_password_hash
import Config
from Models import (
    create_user,
    get_user,
    paginate,
    password_policy_error,
    public_users,
    update_user,
    validate_role,
)
from Security import (
    active_sessions,
    api_errors,
    can,
    editable_fields_for,
    permission_required,
    permissions_matrix,
    revoke_sessions,
)
from Storage import (
    append_audit_log,
    list_backups,
    load_audit_logs,
    load_users,
    restore_latest_audit_backup,
    restore_latest_store_backup,
    save_users,
)

admin_api_bp = Blueprint("admin_api", __name__, url_prefix=Config.ADMIN_PREFIX)
admin_page_bp = Blueprint("admin_page", __name__)


@admin_page_bp.route("/admin")
@permission_required("view_users")
def admin_page():
    return send_from_directory("static", "Admin.html")


@admin_api_bp.route("/users", methods=["GET"])
@api_errors
@permission_required("view_users")
def get_users():
    try:
        page = int(request.args.get("page", Config.DEFAULT_USER_PAGE))
        per_page = int(request.args.get("per_page", Config.DEFAULT_USER_PER_PAGE))
    except Exception:
        return {"msg": "invalid pagination"}, 400

    include_deleted = request.args.get("include_deleted") == "1"
    users = [user for user in load_users() if include_deleted or not user.get("deleted")]
    safe = public_users(users)
    page_items, total = paginate(safe, page, per_page)
    return {"users": page_items, "total": total, "page": page, "per_page": per_page}


@admin_api_bp.route("/search-users", methods=["GET"])
@api_errors
@permission_required("view_users")
def search_users():
    q = (request.args.get("q") or "").lower().strip()
    include_deleted = request.args.get("include_deleted") == "1"
    users = [user for user in load_users() if include_deleted or not user.get("deleted")]
    safe = public_users(users)
    if q:
        safe = [user for user in safe if q in user.get("username", "").lower() or q in user.get("role", "").lower()]
    return {"users": safe, "total": len(safe)}


def write_log(actor, action, target, details=None):
    append_audit_log({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": actor,
        "action": action,
        "target": target,
        "details": details or {},
    })


@admin_api_bp.route("/create-user", methods=["POST"])
@api_errors
@permission_required("create_user")
def create_user_route():
    users = load_users()
    req = request.get_json() or {}
    username = req.get("username")
    password = req.get("password")
    role = req.get("role", "viewer")
    permissions = req.get("permissions", [])

    if any(u["username"] == username for u in users):
        return {"msg": "exists"}, 409

    try:
        new_user = create_user(username, password, role=role, permissions=permissions)
    except ValueError as exc:
        return {"msg": str(exc)}, 400

    users.append(new_user)
    save_users(users)
    write_log(session.get("user"), "create_user", username, {"role": role})
    return {"msg": "created"}


@admin_api_bp.route("/stats", methods=["GET"])
@api_errors
@permission_required("view_stats")
def stats():
    users = [user for user in load_users() if not user.get("deleted")]
    total = len(users)
    by_role = {role: 0 for role in ["admin", "operator", "moderator", "support", "readonly_admin", "viewer"]}
    for user in users:
        by_role[user.get("role", "viewer")] = by_role.get(user.get("role", "viewer"), 0) + 1
    return {"total": total, "by_role": by_role, "admins": by_role.get("admin", 0), "viewers": by_role.get("viewer", 0)}


@admin_api_bp.route("/logs", methods=["GET"])
@api_errors
@permission_required("view_logs")
def logs():
    try:
        page = int(request.args.get("page", Config.DEFAULT_LOG_PAGE))
        per_page = int(request.args.get("per_page", Config.DEFAULT_LOG_PER_PAGE))
    except Exception:
        return {"msg": "invalid pagination"}, 400

    logs = load_audit_logs()
    actor = request.args.get("actor")
    target = request.args.get("target")
    action = request.args.get("action")
    date = request.args.get("date")

    if actor:
        logs = [item for item in logs if item.get("actor") == actor]
    if target:
        logs = [item for item in logs if item.get("target") == target]
    if action:
        logs = [item for item in logs if item.get("action") == action]
    if date:
        logs = [item for item in logs if item.get("timestamp", "").startswith(date)]

    page_items, total = paginate(logs, page, per_page)
    return {"logs": page_items, "total": total, "page": page, "per_page": per_page}


@admin_api_bp.route("/set-role", methods=["POST"])
@api_errors
@permission_required("change_role")
def set_role():
    users = load_users()
    req = request.get_json() or {}
    username = req.get("username")
    role = req.get("role")

    if not username or not role:
        return {"msg": "invalid request"}, 400
    if not validate_role(role):
        return {"msg": "invalid role"}, 400

    user = get_user(users, username)
    if not user:
        return {"msg": "user not found"}, 404

    old_role = user.get("role")
    user["role"] = role
    save_users(users)
    write_log(session.get("user"), "set_role", username, {"from": old_role, "to": role})
    return {"msg": "role updated"}


@admin_api_bp.route("/edit-user", methods=["POST"])
@api_errors
@permission_required("edit_user")
def edit_user():
    users = load_users()
    req = request.get_json() or {}
    username = req.get("username")
    if not username:
        return {"msg": "invalid request"}, 400

    user = get_user(users, username)
    if not user:
        return {"msg": "user not found"}, 404

    allowed_fields = editable_fields_for(session.get("role"))
    changed = {}

    new_role = req.get("role")
    if new_role and new_role != user.get("role"):
        if "role" not in allowed_fields or not can("change_role"):
            return {"msg": "role changes are not allowed for this role"}, 403
        if not validate_role(new_role):
            return {"msg": "invalid role"}, 400
        changed["role"] = {"from": user.get("role"), "to": new_role}
        user["role"] = new_role

    new_password = req.get("password")
    if new_password:
        if "password" not in allowed_fields:
            return {"msg": "password changes are not allowed for this role"}, 403
        pw_error = password_policy_error(new_password)
        if pw_error:
            return {"msg": pw_error}, 400
        user["password"] = generate_password_hash(new_password)
        changed["password"] = True

    if "permissions" in req:
        if "permissions" not in allowed_fields:
            return {"msg": "permission changes are not allowed for this role"}, 403
        user["permissions"] = req.get("permissions") or []
        changed["permissions"] = True

    if "active" in req:
        new_active = bool(req.get("active"))
        if user.get("active", True) != new_active:
            if "active" not in allowed_fields:
                return {"msg": "active status changes are not allowed for this role"}, 403
            changed["active"] = {"from": user.get("active", True), "to": new_active}
            user["active"] = new_active

    save_users(users)
    write_log(session.get("user"), "edit_user", username, changed)
    return {"msg": "updated", "changed": changed}


@admin_api_bp.route("/delete-user", methods=["POST"])
@api_errors
@permission_required("delete_user")
def delete_user():
    users = load_users()
    req = request.get_json() or {}
    username = req.get("username")

    if not username:
        return {"msg": "invalid request"}, 400

    removed = False
    for user in users:
        if user["username"] == username and not user.get("deleted"):
            user["deleted"] = True
            user["active"] = False
            removed = True
            break

    if not removed:
        return {"msg": "user not found"}, 404

    save_users(users)
    write_log(session.get("user"), "delete_user", username)
    return {"msg": "user deleted"}


@admin_api_bp.route("/restore-user", methods=["POST"])
@api_errors
@permission_required("restore_user")
def restore_user():
    users = load_users()
    req = request.get_json() or {}
    username = req.get("username")

    if not username:
        return {"msg": "invalid request"}, 400

    user = get_user(users, username)
    if not user or not user.get("deleted"):
        return {"msg": "user not found"}, 404

    user["deleted"] = False
    user["active"] = True
    save_users(users)
    write_log(session.get("user"), "restore_user", username)
    return {"msg": "user restored"}


@admin_api_bp.route("/delete-users", methods=["POST"])
@api_errors
@permission_required("bulk_delete_users")
def delete_users():
    users = load_users()
    req = request.get_json() or {}
    usernames = req.get("usernames")

    if not isinstance(usernames, list) or not usernames:
        return {"msg": "invalid request"}, 400

    removed = 0
    for user in users:
        if user["username"] in usernames and not user.get("deleted"):
            user["deleted"] = True
            user["active"] = False
            removed += 1

    if removed == 0:
        return {"msg": "no users removed"}, 404

    save_users(users)
    write_log(session.get("user"), "bulk_delete", ", ".join(usernames), {"count": removed})
    return {"msg": "deleted", "removed": removed}


@admin_api_bp.route("/permissions", methods=["GET"])
@api_errors
@permission_required("view_permissions")
def permissions():
    return permissions_matrix()


@admin_api_bp.route("/sessions", methods=["GET"])
@api_errors
@permission_required("view_sessions")
def sessions():
    return {"sessions": active_sessions()}


@admin_api_bp.route("/force-logout", methods=["POST"])
@api_errors
@permission_required("force_logout_sessions")
def force_logout():
    req = request.get_json() or {}
    username = req.get("username") or None
    include_current = bool(req.get("include_current", False))
    exclude_roles = ["admin"] if req.get("exclude_admin") else []
    actor = session.get("user") or "system"
    count = revoke_sessions(username=username, include_current=include_current, exclude_roles=exclude_roles)
    write_log(actor, "force_logout", username or "all_sessions", {"count": count, "include_current": include_current, "exclude_roles": exclude_roles})
    return {"msg": "sessions revoked", "revoked": count}


@admin_api_bp.route("/backups", methods=["GET"])
@api_errors
@permission_required("view_backups")
def backups():
    return {"backups": list_backups()}


@admin_api_bp.route("/restore-backup", methods=["POST"])
@api_errors
@permission_required("restore_backup")
def restore_backup():
    req = request.get_json() or {}
    target = req.get("target")
    if target == "store":
        restored = restore_latest_store_backup()
    elif target == "audit":
        restored = restore_latest_audit_backup()
    else:
        return {"msg": "invalid target"}, 400

    write_log(session.get("user"), "restore_backup", target, {"restored": restored})
    return {"msg": "backup restored" if restored else "no backup available", "restored": restored}
