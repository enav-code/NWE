from flask import Blueprint, request, g
from werkzeug.security import generate_password_hash

from Security import (
    api_errors,
    business_admin_required,
    log_security_event,
    login_required,
    password_policy_error,
    rate_limited,
)
from Storage import add_user_to_business, deactivate_user, get_team

team_bp = Blueprint("team", __name__, url_prefix="/api/team")


@team_bp.route("/add-user", methods=["POST"])
@api_errors
@business_admin_required          # ← server-side gate; 403 if not BusinessAdmin
def add_user():
    """
    Add a new Employee or Client to the admin's own business.
    Body: { username, password, role }
    """
    body = request.get_json() or {}
    username = (body.get("username") or "").strip()
    password = body.get("password") or ""
    role = (body.get("role") or "Employee").strip()

    if not username or not password:
        return {"msg": "username and password are required"}, 400

    err = password_policy_error(password)
    if err:
        return {"msg": err}, 400

    biz_id = g.user["business_id"]
    hashed = generate_password_hash(password)
    user_id = add_user_to_business(biz_id, username, hashed, role)

    log_security_event("add_user", username, {"role": role, "new_user_id": user_id})
    return {"msg": "user created", "user_id": user_id}


@team_bp.route("/get-team", methods=["GET"])
@api_errors
@login_required
def get_team_route():
    """
    Returns active members of the caller's own business.
    BusinessAdmins see everyone; Employees/Clients see only themselves.
    """
    u = g.user
    team = get_team(u["business_id"])

    # Non-admins can only see their own record
    if u["role"] != "BusinessAdmin":
        team = [m for m in team if m["user_id"] == u["user_id"]]

    return {"team": team, "total": len(team)}


@team_bp.route("/deactivate-user", methods=["POST"])
@api_errors
@business_admin_required
def deactivate_user_route():
    """
    Soft-deactivate a user within the admin's business.
    Body: { user_id }
    """
    body = request.get_json() or {}
    user_id = body.get("user_id") or ""
    if not user_id:
        return {"msg": "user_id is required"}, 400

    biz_id = g.user["business_id"]
    deactivate_user(biz_id, user_id)
    log_security_event("deactivate_user", user_id)
    return {"msg": "user deactivated"}