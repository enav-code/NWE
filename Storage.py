import json
import os
import re
import uuid
import shutil
from contextlib import contextmanager
from datetime import datetime

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from supabase import create_client
except ImportError:  # pragma: no cover
    create_client = None

try:
    import fcntl
except ImportError:
    fcntl = None

try:
    import msvcrt
except ImportError:
    msvcrt = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORE_FILE = os.path.join(BASE_DIR, "Store.json")
AUDIT_FILE = os.path.join(BASE_DIR, "AuditLog.json")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
MAX_BACKUPS = 20
DEFAULT_SUPABASE_URL = "https://nhgaxciimpqgxwjxehul.supabase.co"
DEFAULT_SUPABASE_PROFILES_URL = "https://nhgaxciimpqgxwjxehul.supabase.co/rest/v1/profiles"


# ---------------------------------------------------------------------------
# File locking
# ---------------------------------------------------------------------------

@contextmanager
def _file_lock(path):
    lock_path = path + ".lock"
    with open(lock_path, "a+b") as lf:
        if fcntl:
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        elif msvcrt:
            msvcrt.locking(lf.fileno(), msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
            elif msvcrt:
                lf.seek(0)
                msvcrt.locking(lf.fileno(), msvcrt.LK_UNLCK, 1)


# ---------------------------------------------------------------------------
# Low-level read / write
# ---------------------------------------------------------------------------

def _ensure(path, default):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(default, f, indent=4)


def _read(path, default):
    _ensure(path, default)
    with _file_lock(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return default


def _write(path, data, backup=True):
    if backup:
        _backup(path)
    with _file_lock(path):
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

def _backup(path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(path):
        return
    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    name = os.path.splitext(os.path.basename(path))[0]
    dest = os.path.join(BACKUP_DIR, f"{name}-{stamp}.json")
    shutil.copy2(path, dest)
    existing = sorted(
        [os.path.join(BACKUP_DIR, x) for x in os.listdir(BACKUP_DIR)
         if x.startswith(f"{name}-") and x.endswith(".json")],
        key=os.path.getmtime, reverse=True
    )
    for old in existing[MAX_BACKUPS:]:
        os.remove(old)


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def _short_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def new_business_id():
    return _short_id("biz")


def new_user_id():
    return _short_id("user")


# ---------------------------------------------------------------------------
# Store access
# ---------------------------------------------------------------------------

def load_store():
    data = _read(STORE_FILE, {"businesses": {}, "adminos": {}})
    if not isinstance(data, dict):
        data = {"businesses": {}, "adminos": {}}
    data.setdefault("businesses", {})
    data.setdefault("adminos", {})
    return data


def save_store(data, backup=True):
    _write(STORE_FILE, data, backup=backup)


def get_supabase_client():
    from Config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY

    url = SUPABASE_URL or os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_REST_URL") or DEFAULT_SUPABASE_URL
    key = (
        SUPABASE_SERVICE_ROLE_KEY
        or SUPABASE_ANON_KEY
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if not url or not key:
        return None
    if create_client is None:
        raise RuntimeError("supabase-py is not installed")
    return create_client(url, key)


def _looks_like_email(value):
    return bool(value) and "@" in value and "." in value


def _build_supabase_auth_email(username):
    value = (username or "").strip()
    if _looks_like_email(value):
        return value
    safe = re.sub(r"[^a-z0-9._%+-]+", "", value.lower()) or "user"
    return f"{safe}+{uuid.uuid4().hex[:8]}@local.invalid"


def _get_profile_by_username(username):
    client = get_supabase_client()
    if not client:
        return None
    result = client.table("profiles").select("*").eq("username", username).limit(1).execute()
    data = result.data or []
    return dict(data[0]) if data else None


def _get_auth_email_for_username(username):
    profile = _get_profile_by_username(username)
    if profile and profile.get("auth_email"):
        return profile["auth_email"]
    if profile and _looks_like_email(profile.get("username")):
        return profile["username"]
    return _build_supabase_auth_email(username)


def _build_profile_payload(user_payload, business_id=None, company_name=None, auth_email=None):
    payload = {
        "id": user_payload.get("user_id") or user_payload.get("id"),
        "username": user_payload.get("username"),
        "role": user_payload.get("role"),
        "business_id": business_id,
        "company_name": company_name,
        "active": bool(user_payload.get("active", True)),
        "created_at": user_payload.get("created_at") or _now_iso(),
        "auth_email": auth_email,
    }
    return {k: v for k, v in payload.items() if v is not None}


def _post_profile_to_supabase(payload):
    if not payload.get("id") or not payload.get("username"):
        return False

    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("profiles").upsert(payload, on_conflict="id").execute()
        return True
    except Exception:
        return False


def _sync_user_to_supabase(user_payload, business_id=None, company_name=None):
    payload = _build_profile_payload(user_payload, business_id=business_id, company_name=company_name)
    return _post_profile_to_supabase(payload)


def sync_all_users_to_supabase():
    store = load_store()
    for business_id, biz in store.get("businesses", {}).items():
        company_name = biz.get("company_name", "")
        for user in biz.get("users", {}).values():
            _sync_user_to_supabase(user, business_id=business_id, company_name=company_name)
    for user in store.get("adminos", {}).values():
        _sync_user_to_supabase(user, company_name="Platform")
    return []


def sign_in_with_supabase(username, password):
    client = get_supabase_client()
    if not client:
        return None
    email_to_use = username
    if not _looks_like_email(username):
        profile = _get_profile_by_username(username)
        if profile and profile.get("auth_email"):
            email_to_use = profile["auth_email"]
        else:
            email_to_use = _build_supabase_auth_email(username)
    try:
        response = client.auth.sign_in_with_password({"email": email_to_use, "password": password})
    except Exception:
        return None
    if not getattr(response, "session", None):
        return None
    user = getattr(response, "user", None)
    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token,
        "user": {
            "id": str(user.id) if user and getattr(user, "id", None) else None,
            "email": getattr(user, "email", None),
        },
    }


def sign_out_supabase():
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.auth.sign_out()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Admino operations (platform-level super admins)
# ---------------------------------------------------------------------------

def create_admino(username, password):
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not configured")

    auth_email = _build_supabase_auth_email(username)
    auth_response = client.auth.sign_up({"email": auth_email, "password": password})
    user = getattr(auth_response, "user", None)
    if not user:
        raise RuntimeError("Supabase sign-up did not return a user")

    user_id = str(user.id)
    profile_payload = {
        "id": user_id,
        "username": username,
        "role": "admino",
        "business_id": None,
        "company_name": "Platform",
        "active": True,
        "created_at": _now_iso(),
        "auth_email": auth_email,
    }
    client.table("profiles").insert(profile_payload).execute()
    _post_profile_to_supabase(profile_payload)
    return user_id


def find_admino_by_username(username):
    client = get_supabase_client()
    if not client:
        return None
    result = client.table("profiles").select("*").eq("username", username).eq("role", "admino").limit(1).execute()
    data = result.data or []
    return dict(data[0]) if data else None


def list_adminos():
    client = get_supabase_client()
    if not client:
        return []
    result = client.table("profiles").select("*").eq("role", "admino").execute()
    return result.data or []


def deactivate_admino(user_id):
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not configured")
    client.table("profiles").update({"active": False}).eq("id", user_id).execute()


def delete_business(business_id):
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not configured")
    result = client.table("businesses").delete().eq("id", business_id).execute()
    if not result.data:
        raise ValueError("business not found")
    client.table("profiles").delete().eq("business_id", business_id).execute()


def set_business_active(business_id, active):
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not configured")
    result = client.table("businesses").update({"active": active}).eq("id", business_id).execute()
    if not result.data:
        raise ValueError("business not found")
    client.table("profiles").update({"active": active}).eq("business_id", business_id).execute()


def platform_stats():
    client = get_supabase_client()
    if not client:
        return {"total_businesses": 0, "active_businesses": 0, "total_users": 0, "total_adminos": 0}
    businesses = client.table("businesses").select("*").execute().data or []
    profiles = client.table("profiles").select("*").execute().data or []
    adminos = [p for p in profiles if p.get("role") == "admino"]
    return {
        "total_businesses": len(businesses),
        "active_businesses": sum(1 for b in businesses if b.get("active", True)),
        "total_users": len(profiles),
        "total_adminos": len(adminos),
    }


# ---------------------------------------------------------------------------
# Business operations
# ---------------------------------------------------------------------------

def list_businesses():
    client = get_supabase_client()
    if not client:
        return []
    return client.table("businesses").select("*").execute().data or []


def get_business(business_id):
    client = get_supabase_client()
    if not client:
        return None
    business_result = client.table("businesses").select("*").eq("id", business_id).limit(1).execute()
    rows = business_result.data or []
    if not rows:
        return None
    biz = dict(rows[0])
    users_result = client.table("profiles").select("*").eq("business_id", business_id).execute()
    biz["users"] = {u.get("id"): u for u in (users_result.data or [])}
    return biz


def create_business(company_name, admin_username, password):
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not configured")

    auth_email = _build_supabase_auth_email(admin_username)
    auth_response = client.auth.sign_up({"email": auth_email, "password": password})
    user = getattr(auth_response, "user", None)
    if not user:
        raise RuntimeError("Supabase sign-up did not return a user")

    invite_code = str(uuid.uuid4())[:8].upper()
    business_payload = {
        "id": str(uuid.uuid4()),
        "company_name": company_name,
        "invite_code": invite_code,
        "active": True,
        "created_at": _now_iso(),
    }
    business_result = client.table("businesses").insert(business_payload).execute()
    business_row = (business_result.data or [{}])[0]
    biz_id = business_row.get("id") or business_row.get("business_id") or business_payload["id"]

    profile_payload = {
        "id": str(user.id),
        "username": admin_username,
        "role": "BusinessAdmin",
        "business_id": biz_id,
        "company_name": company_name,
        "active": True,
        "created_at": _now_iso(),
        "auth_email": auth_email,
    }
    client.table("profiles").insert(profile_payload).execute()
    _post_profile_to_supabase(profile_payload)

    access_token = None
    session = getattr(auth_response, "session", None)
    if session:
        access_token = session.access_token
    else:
        login_session = sign_in_with_supabase(auth_email, password)
        if login_session:
            access_token = login_session["access_token"]
    return biz_id, str(user.id), access_token


def add_user_to_business(business_id, username, password, role):
    from Config import ASSIGNABLE_ROLES
    if role not in ASSIGNABLE_ROLES:
        raise ValueError(f"invalid role; must be one of {sorted(ASSIGNABLE_ROLES)}")

    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not configured")

    auth_email = _build_supabase_auth_email(username)
    auth_response = client.auth.sign_up({"email": auth_email, "password": password})
    user = getattr(auth_response, "user", None)
    if not user:
        raise RuntimeError("Supabase sign-up did not return a user")

    profile_payload = {
        "id": str(user.id),
        "username": username,
        "role": role,
        "business_id": business_id,
        "company_name": None,
        "active": True,
        "created_at": _now_iso(),
        "auth_email": auth_email,
    }
    client.table("profiles").insert(profile_payload).execute()
    _post_profile_to_supabase(profile_payload)
    return str(user.id)


def get_team(business_id):
    client = get_supabase_client()
    if not client:
        return []
    result = client.table("profiles").select("*").eq("business_id", business_id).eq("active", True).execute()
    data = result.data or []
    return [dict(user) for user in data]


def find_user_by_username(username):
    client = get_supabase_client()
    if not client:
        return None, None, None
    result = client.table("profiles").select("*").eq("username", username).limit(1).execute()
    data = result.data or []
    if not data:
        return None, None, None
    user = dict(data[0])
    return user, user.get("business_id"), user.get("company_name")


def get_profile_from_access_token(token):
    client = get_supabase_client()
    if not client or not token:
        return None
    try:
        user_response = client.auth.get_user(token)
    except Exception:
        return None
    user = getattr(user_response, "user", None)
    if not user:
        return None
    user_id = str(getattr(user, "id", ""))
    if not user_id:
        return None
    result = client.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    data = result.data or []
    if not data:
        return None
    profile = dict(data[0])
    return {
        "user_id": profile.get("id"),
        "username": profile.get("username") or getattr(user, "email", None),
        "role": profile.get("role"),
        "business_id": profile.get("business_id"),
        "company_name": profile.get("company_name"),
        "active": profile.get("active", True),
    }


def get_user_in_business(business_id, user_id):
    store = load_store()
    biz = store["businesses"].get(business_id)
    if not biz:
        return None
    return biz["users"].get(user_id)


def deactivate_user(business_id, user_id):
    client = get_supabase_client()
    if not client:
        raise RuntimeError("Supabase client not configured")
    result = client.table("profiles").update({"active": False}).eq("id", user_id).eq("business_id", business_id).execute()
    if not result.data:
        raise ValueError("user not found")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def append_audit(entry):
    logs = _read(AUDIT_FILE, [])
    if not isinstance(logs, list):
        logs = []
    logs.insert(0, entry)
    _write(AUDIT_FILE, logs, backup=False)


def load_audit_logs():
    logs = _read(AUDIT_FILE, [])
    return logs if isinstance(logs, list) else []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _assert_username_unique(store, username):
    for biz in store["businesses"].values():
        for user in biz["users"].values():
            if user["username"] == username:
                raise ValueError("username already taken")
    for a in store["adminos"].values():
        if a["username"] == username:
            raise ValueError("username already taken")


def delete_admino(user_id):
    store = load_store()
    if user_id not in store["adminos"]:
        raise ValueError("admino not found")
    del store["adminos"][user_id]
    save_store(store)