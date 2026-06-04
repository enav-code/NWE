from .auth import auth_bp
from .team import team_bp
from .admino import admino_bp
from .google import google_bp

__all__ = ["auth_bp", "team_bp", "admino_bp", "google_bp"]