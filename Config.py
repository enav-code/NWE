import os

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

GOOGLE_CLIENT_ID = os.environ.get("77051269767-iv2mkdt5vhlpcuqookcqib1ssiqtc0oc.apps.googleusercontent.com", "")
GOOGLE_CLIENT_SECRET = os.environ.get("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", "")

GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "https://stratview.pythonanywhere.com/api/auth/google/callback"
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