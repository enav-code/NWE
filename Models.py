from werkzeug.security import generate_password_hash

from Storage import (
    VALID_PERMISSIONS,
    VALID_ROLES,
    load_users,
    normalize_user,
    public_user,
    save_users,
)


def validate_role(role):
    return role in VALID_ROLES


def validate_permissions(permissions):
    if permissions is None:
        return []
    if not isinstance(permissions, list):
        raise ValueError("permissions must be a list")
    return [perm for perm in permissions if perm in VALID_PERMISSIONS]


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


def create_user(username, password, role="viewer", permissions=None):
    if not username or not password:
        raise ValueError("username and password are required")
    if not validate_role(role):
        raise ValueError("invalid role")
    policy_error = password_policy_error(password)
    if policy_error:
        raise ValueError(policy_error)
    return normalize_user({
        "username": username,
        "password": generate_password_hash(password),
        "role": role,
        "active": True,
        "deleted": False,
        "permissions": validate_permissions(permissions),
    })


def update_user(user, *, role=None, password=None, active=None, permissions=None):
    if role is not None:
        if not validate_role(role):
            raise ValueError("invalid role")
        user["role"] = role
    if password is not None:
        policy_error = password_policy_error(password)
        if policy_error:
            raise ValueError(policy_error)
        user["password"] = generate_password_hash(password)
    if active is not None:
        user["active"] = bool(active)
    if permissions is not None:
        user["permissions"] = validate_permissions(permissions)
    return normalize_user(user)


def get_user(users, username):
    return next((user for user in users if user.get("username") == username), None)


def paginate(items, page, per_page):
    if page < 1 or per_page < 1:
        raise ValueError("invalid pagination")
    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], total


def public_users(users):
    return [public_user(user) for user in users]


def refresh_users(users):
    save_users([normalize_user(user) for user in users])
