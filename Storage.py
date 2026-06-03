import json
import os
import uuid
import shutil
from contextlib import contextmanager
from datetime import datetime

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


# ---------------------------------------------------------------------------
# Admino operations (platform-level super admins)
# ---------------------------------------------------------------------------

def create_admino(username, hashed_password):
    store = load_store()
    for a in store["adminos"].values():
        if a["username"] == username:
            raise ValueError("username already taken")
    _assert_username_unique(store, username)

    user_id = new_user_id()
    store["adminos"][user_id] = {
        "user_id": user_id,
        "username": username,
        "password": hashed_password,
        "role": "admino",
        "active": True,
        "created_at": _now_iso(),
    }
    save_store(store)
    return user_id


def find_admino_by_username(username):
    store = load_store()
    for a in store["adminos"].values():
        if a["username"] == username:
            return dict(a)
    return None


def list_adminos():
    store = load_store()
    return [{k: v for k, v in a.items() if k != "password"} for a in store["adminos"].values()]


def deactivate_admino(user_id):
    store = load_store()
    if user_id not in store["adminos"]:
        raise ValueError("admino not found")
    store["adminos"][user_id]["active"] = False
    save_store(store)


def delete_business(business_id):
    store = load_store()
    if business_id not in store["businesses"]:
        raise ValueError("business not found")
    del store["businesses"][business_id]
    save_store(store)


def set_business_active(business_id, active):
    store = load_store()
    biz = store["businesses"].get(business_id)
    if not biz:
        raise ValueError("business not found")
    biz["active"] = active
    for user in biz["users"].values():
        user["active"] = active
    save_store(store)


def platform_stats():
    store = load_store()
    total_biz = len(store["businesses"])
    total_users = sum(len(b["users"]) for b in store["businesses"].values())
    active_biz = sum(1 for b in store["businesses"].values() if b.get("active", True))
    return {
        "total_businesses": total_biz,
        "active_businesses": active_biz,
        "total_users": total_users,
        "total_adminos": len(store["adminos"]),
    }


# ---------------------------------------------------------------------------
# Business operations
# ---------------------------------------------------------------------------

def list_businesses():
    store = load_store()
    return [
        {k: v for k, v in biz.items() if k != "users"}
        for biz in store["businesses"].values()
    ]


def get_business(business_id):
    store = load_store()
    return store["businesses"].get(business_id)


def create_business(company_name, admin_username, hashed_password):
    store = load_store()
    for biz in store["businesses"].values():
        if biz.get("company_name", "").lower() == company_name.lower():
            raise ValueError("company name already exists")
    _assert_username_unique(store, admin_username)

    biz_id = new_business_id()
    user_id = new_user_id()
    store["businesses"][biz_id] = {
        "business_id": biz_id,
        "company_name": company_name,
        "active": True,
        "created_at": _now_iso(),
        "users": {
            user_id: {
                "user_id": user_id,
                "username": admin_username,
                "password": hashed_password,
                "role": "BusinessAdmin",
                "active": True,
                "created_at": _now_iso(),
            }
        }
    }
    save_store(store)
    return biz_id, user_id


def add_user_to_business(business_id, username, hashed_password, role):
    from Config import ASSIGNABLE_ROLES
    if role not in ASSIGNABLE_ROLES:
        raise ValueError(f"invalid role; must be one of {sorted(ASSIGNABLE_ROLES)}")
    store = load_store()
    biz = store["businesses"].get(business_id)
    if not biz:
        raise ValueError("business not found")
    for u in biz["users"].values():
        if u["username"] == username:
            raise ValueError("username already exists in this company")
    user_id = new_user_id()
    biz["users"][user_id] = {
        "user_id": user_id,
        "username": username,
        "password": hashed_password,
        "role": role,
        "active": True,
        "created_at": _now_iso(),
    }
    save_store(store)
    return user_id


def get_team(business_id):
    store = load_store()
    biz = store["businesses"].get(business_id)
    if not biz:
        return []
    return [
        {k: v for k, v in u.items() if k != "password"}
        for u in biz["users"].values()
        if u.get("active")
    ]


def find_user_by_username(username):
    """Scan all businesses. Returns (user_dict, biz_id, company_name) or (None, None, None)."""
    store = load_store()
    for biz_id, biz in store["businesses"].items():
        for user in biz["users"].values():
            if user["username"] == username:
                return dict(user), biz_id, biz.get("company_name", "")
    return None, None, None


def get_user_in_business(business_id, user_id):
    store = load_store()
    biz = store["businesses"].get(business_id)
    if not biz:
        return None
    return biz["users"].get(user_id)


def deactivate_user(business_id, user_id):
    store = load_store()
    biz = store["businesses"].get(business_id)
    if not biz or user_id not in biz["users"]:
        raise ValueError("user not found")
    biz["users"][user_id]["active"] = False
    save_store(store)


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