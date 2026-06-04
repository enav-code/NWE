import os

# =========================================================
# CORE SECURITY
# =========================================================

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-key-in-production")

JWT_ALGORITHM = "HS256"


# =========================================================
# ENVIRONMENT
# =========================================================

FLASK_ENV = os.environ.get("FLASK_ENV", "production")
DEBUG = FLASK_ENV != "production"


# =========================================================
# GOOGLE SSO
# =========================================================

GOOGLE_CLIENT_ID = os.environ.get("77051269767-iv2mkdt5vhlpcuqookcqib1ssiqtc0oc.apps.googleusercontent.com", "")
GOOGLE_CLIENT_SECRET = os.environ.get("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", "")

GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "https://stratview.pythonanywhere.com/api/auth/google/callback"
)


# =========================================================
# ROUTING PREFIXES
# =========================================================

API_PREFIX = "/api"
AUTH_PREFIX = f"{API_PREFIX}/auth"
TEAM_PREFIX = f"{API_PREFIX}/team"
ADMIN_PREFIX = f"{API_PREFIX}/admin"


# =========================================================
# DATABASE
# =========================================================

DATABASE_FILE = "Store.json"


# =========================================================
# PAGINATION DEFAULTS
# =========================================================

DEFAULT_USER_PAGE = 1
DEFAULT_USER_PER_PAGE = 20

DEFAULT_LOG_PAGE = 1
DEFAULT_LOG_PER_PAGE = 50


# =========================================================
# RATE LIMITING
# =========================================================

RATE_LIMIT_LOGIN = 8
RATE_LIMIT_REGISTER = 5
RATE_LIMIT_TEAM_API = 120


# =========================================================
# SECURITY SETTINGS
# =========================================================

PASSWORD_MIN_LENGTH = 8

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

SESSION_COOKIE_SECURE = FLASK_ENV == "production"

SESSION_TIMEOUT_HOURS = 2
REMEMBER_ME_DAYS = 14


# =========================================================
# EMAIL (FUTURE)
# =========================================================

MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")


# =========================================================
# LOGGING
# =========================================================

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
AUDIT_LOG_RETENTION_DAYS = 90