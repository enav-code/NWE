from datetime import datetime
from flask import Blueprint, request, session
from Storage import (
    append_audit_log,
    list_backups,
    load_audit_logs,
    load_users,
    public_user,
    restore_latest_audit_backup,
    restore_latest_store_backup,
    save_users,
)
from Security import (
    active_sessions,
    api_errors,
    can,
    editable_fields_for,
    permission_required,
    permissions_matrix,
    revoke_sessions,
    roles,
)
from werkzeug.security import generate_password_hash

admin_bp = Blueprint("admin", __name__)


def valid_role(role):
    return role in roles()


def password_policy_error(password):
    if len(password) < 10:
        return "password must be at least 10 characters"
    classes = [
        any(ch.islower() for ch in password),
        any(ch.isupper() for ch in password),
        any(ch.isdigit() for ch in password),
        any(not ch.isalnum() for ch in password),
    ]
    if sum(classes) < 3:
        return "password must use at least 3 character types"
    return None


# -------------------------
# Get all users
# -------------------------
@admin_bp.route("/admin/users", methods=["GET"])
@api_errors
@permission_required("view_users")
def get_users():
    # pagination
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except Exception:
        return {"msg": "invalid pagination"}, 400

    include_deleted = request.args.get("include_deleted") == "1"
    safe = [
        public_user(user)
        for user in load_users()
        if include_deleted or not user.get("deleted")
    ]

    total = len(safe)
    start = (page - 1) * per_page
    end = start + per_page
    return {"users": safe[start:end], "total": total, "page": page, "per_page": per_page}


@admin_bp.route("/admin/search-users", methods=["GET"])
@api_errors
@permission_required("view_users")
def search_users():
    q = (request.args.get("q") or "").lower().strip()
    include_deleted = request.args.get("include_deleted") == "1"
    users = [
        public_user(user)
        for user in load_users()
        if include_deleted or not user.get("deleted")
    ]
    if q:
        users = [
            user for user in users
            if q in user.get("username", "").lower() or q in user.get("role", "").lower()
        ]
    return {"users": users, "total": len(users)}


def write_log(actor, action, target, details=None):
    append_audit_log({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "actor": actor,
        "action": action,
        "target": target,
        "details": details or {}
    })


@admin_bp.route("/admin/create-user", methods=["POST"])
@api_errors
@permission_required("create_user")
def create_user():
    users = load_users()
    req = request.get_json() or {}
    username = req.get("username")
    password = req.get("password")
    role = req.get("role", "viewer")

    if not username or not password:
        return {"msg": "invalid request"}, 400
    policy_error = password_policy_error(password)
    if policy_error:
        return {"msg": policy_error}, 400
    if not valid_role(role):
        return {"msg": "invalid role"}, 400

    if any(u["username"] == username for u in users):
        return {"msg": "exists"}, 409

    users.append({
        "username": username,
        "password": generate_password_hash(password),
        "role": role,
        "active": True,
        "deleted": False,
        "permissions": req.get("permissions", [])
    })
    save_users(users)
    write_log(session.get("user"), "create_user", username, {"role": role})
    return {"msg": "created"}


@admin_bp.route("/admin/stats", methods=["GET"])
@api_errors
@permission_required("view_stats")
def stats():
    users = [user for user in load_users() if not user.get("deleted")]
    total = len(users)
    by_role = {role: 0 for role in roles()}
    for user in users:
        by_role[user.get("role", "viewer")] = by_role.get(user.get("role", "viewer"), 0) + 1
    return {"total": total, "by_role": by_role, "admins": by_role.get("admin", 0), "viewers": by_role.get("viewer", 0)}


@admin_bp.route("/admin/logs", methods=["GET"])
@api_errors
@permission_required("view_logs")
def logs():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))
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

    total = len(logs)
    start = (page - 1) * per_page
    end = start + per_page
    return {"logs": logs[start:end], "total": total, "page": page, "per_page": per_page}


# -------------------------
# Change user role
# -------------------------
@admin_bp.route("/admin/set-role", methods=["POST"])
@api_errors
@permission_required("change_role")
def set_role():
    users = load_users()
    req = request.get_json() or {}

    username = req.get("username")
    role = req.get("role")

    if not username or not role:
        return {"msg": "invalid request"}, 400
    if not valid_role(role):
        return {"msg": "invalid role"}, 400

    for user in users:
        if user["username"] == username:
            old_role = user.get("role")
            user["role"] = role
            save_users(users)
            write_log(session.get("user"), "set_role", username, {"from": old_role, "to": role})
            return {"msg": "role updated"}

    return {"msg": "user not found"}, 404


@admin_bp.route("/admin/edit-user", methods=["POST"])
@api_errors
@permission_required("edit_user")
def edit_user():
    users = load_users()
    req = request.get_json() or {}
    username = req.get("username")
    if not username:
        return {"msg": "invalid request"}, 400
    allowed_fields = editable_fields_for(session.get("role"))

    for user in users:
        if user["username"] == username:
            changed = {}
            new_role = req.get("role")
            if new_role and new_role != user.get("role"):
                if "role" not in allowed_fields or not can("change_role"):
                    return {"msg": "role changes are not allowed for this role"}, 403
                if not valid_role(new_role):
                    return {"msg": "invalid role"}, 400
                changed["role"] = {"from": user.get("role"), "to": new_role}
                user["role"] = new_role

            new_pw = req.get("password")
            if new_pw:
                if "password" not in allowed_fields:
                    return {"msg": "password changes are not allowed for this role"}, 403
                policy_error = password_policy_error(new_pw)
                if policy_error:
                    return {"msg": policy_error}, 400
                user["password"] = generate_password_hash(new_pw)
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

    return {"msg": "user not found"}, 404


# -------------------------
# Delete user
# -------------------------
@admin_bp.route("/admin/delete-user", methods=["POST"])
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


@admin_bp.route("/admin/restore-user", methods=["POST"])
@api_errors
@permission_required("restore_user")
def restore_user():
    users = load_users()
    req = request.get_json() or {}
    username = req.get("username")

    if not username:
        return {"msg": "invalid request"}, 400

    for user in users:
        if user["username"] == username and user.get("deleted"):
            user["deleted"] = False
            user["active"] = True
            save_users(users)
            write_log(session.get("user"), "restore_user", username)
            return {"msg": "user restored"}

    return {"msg": "user not found"}, 404


# -------------------------
# Bulk delete users
# -------------------------
@admin_bp.route("/admin/delete-users", methods=["POST"])
@api_errors
@permission_required("bulk_delete_users")
def delete_users():
    users = load_users()
    req = request.get_json() or {}
    usernames = req.get("usernames")

    if not isinstance(usernames, list) or not usernames:
        return {"msg": "invalid request"}, 400

    before = len(users)
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


@admin_bp.route("/admin/permissions", methods=["GET"])
@api_errors
@permission_required("view_permissions")
def permissions():
    return permissions_matrix()


@admin_bp.route("/admin/sessions", methods=["GET"])
@api_errors
@permission_required("view_sessions")
def sessions():
    return {"sessions": active_sessions()}


@admin_bp.route("/admin/force-logout", methods=["POST"])
@api_errors
@permission_required("force_logout_sessions")
def force_logout():
    req = request.get_json() or {}
    username = req.get("username") or None
    include_current = bool(req.get("include_current", False))
    exclude_roles = ["admin"] if req.get("exclude_admin") else []
    actor = session.get("user") or "system"
    count = revoke_sessions(
        username=username,
        include_current=include_current,
        exclude_roles=exclude_roles
    )
    write_log(
        actor,
        "force_logout",
        username or "all_sessions",
        {"count": count, "include_current": include_current, "exclude_roles": exclude_roles}
    )
    return {"msg": "sessions revoked", "revoked": count}


@admin_bp.route("/admin/backups", methods=["GET"])
@api_errors
@permission_required("view_backups")
def backups():
    return {"backups": list_backups()}


@admin_bp.route("/admin/restore-backup", methods=["POST"])
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
