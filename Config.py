import os

# ============ SECRET KEY (used in google.py & Security.py for JWT) ============
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-key-in-production")

# ============ ENVIRONMENT ============
FLASK_ENV = os.environ.get("FLASK_ENV", "production")
DEBUG = FLASK_ENV != "production"

# ============ GOOGLE SSO (used in google.py) ============
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "https://stratview.pythonanywhere.com/api/auth/google/callback"
)