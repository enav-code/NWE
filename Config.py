import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://nhgaxciimpqgxwjxehul.supabase.co")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", os.environ.get("SUPABASE_KEY", ""))
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_KEY", ""))

# ================= SECURITY =================

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")

JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 8
JWT_REMEMBER_DAYS = 14

PASSWORD_MIN_LENGTH = 8


# ================= ENV =================

FLASK_ENV = os.environ.get("FLASK_ENV", "production")
DEBUG = FLASK_ENV != "production"


# ================= SESSION =================

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = FLASK_ENV == "production"

SESSION_TIMEOUT_HOURS = 2
REMEMBER_ME_DAYS = 14


# ================= ROLES =================

VALID_ROLES = {"admino", "BusinessAdmin", "Employee", "Client"}
ASSIGNABLE_ROLES = {"Employee", "Client"}


# ================= GOOGLE SSO =================

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")

SUPABASE_REST_URL = os.environ.get(
    "SUPABASE_REST_URL",
    "https://nhgaxciimpqgxwjxehul.supabase.co/rest/v1/profiles",
)

GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:5000/api/auth/google/callback"
)


# ================= ROUTING =================

API_PREFIX = "/api"
AUTH_PREFIX = f"{API_PREFIX}/auth"
TEAM_PREFIX = f"{API_PREFIX}/team"
ADMIN_PREFIX = f"{API_PREFIX}/admin"


# ================= PAGINATION =================

DEFAULT_USER_PAGE = 1
DEFAULT_USER_PER_PAGE = 20

DEFAULT_LOG_PAGE = 1
DEFAULT_LOG_PER_PAGE = 50


# ================= LOGGING =================

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
AUDIT_LOG_RETENTION_DAYS = 90