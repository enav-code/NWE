import json
import os
from datetime import datetime, timezone
from flask import Flask, send_from_directory, request
from werkzeug.exceptions import HTTPException
from routes.google import google_bp

import Config
from routes.auth import auth_bp
from Storage import sync_all_users_to_supabase
from Security import create_csrf_token, verify_csrf_token
from routes.team import team_bp
from routes.Admino import admino_bp

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = Config.SECRET_KEY

app.register_blueprint(auth_bp)
app.register_blueprint(team_bp)
app.register_blueprint(admino_bp)
app.register_blueprint(google_bp)

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visitor_log.jsonl")
BAN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "banned_ips.json")


def _get_client_ip():
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.headers.get("X-Real-IP") or request.remote_addr or "unknown"


def _log_visit():
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip": _get_client_ip(),
        "method": request.method,
        "path": request.path,
        "user_agent": request.headers.get("User-Agent", ""),
    }
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def _load_banned_ips():
    if not os.path.exists(BAN_FILE):
        return []
    try:
        with open(BAN_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    except (OSError, json.JSONDecodeError):
        return []
    return []


def _save_banned_ips(ips):
    with open(BAN_FILE, "w", encoding="utf-8") as handle:
        json.dump(sorted(set(ips)), handle, indent=2)


def _is_banned_ip(ip):
    return bool(ip) and str(ip).strip() in _load_banned_ips()


def _ban_ip(ip):
    normalized = str(ip).strip()
    if not normalized:
        return False
    ips = _load_banned_ips()
    if normalized in ips:
        return True
    ips.append(normalized)
    _save_banned_ips(ips)
    return True


def _unban_ip(ip):
    normalized = str(ip).strip()
    if not normalized:
        return False
    ips = _load_banned_ips()
    updated = [existing for existing in ips if existing != normalized]
    if len(updated) == len(ips):
        return False
    _save_banned_ips(updated)
    return True


def _is_admin_request():
    provided = request.headers.get("X-Admin-Token", "")
    return bool(provided) and provided == Config.SECRET_KEY


sync_all_users_to_supabase()


@app.before_request
def log_visit_and_enforce_csrf():
    _log_visit()

    client_ip = _get_client_ip()
    if _is_banned_ip(client_ip) and not _is_admin_request():
        return {"msg": "ip blocked", "status": 403}, 403

    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return

    exempt_paths = {
        "/csrf-token",
        "/api/auth/csrf",
        "/api/auth/google/login",
        "/api/auth/google/callback",
    }

    if request.path in exempt_paths:
        return

    token = request.headers.get("X-CSRF-Token", "")
    if not verify_csrf_token(token):
        return {"msg": "invalid csrf token"}, 400


@app.route("/admin/bans", methods=["GET"])
def list_bans():
    if not _is_admin_request():
        return {"msg": "unauthorized"}, 401
    return {"banned_ips": _load_banned_ips()}


@app.route("/admin/bans", methods=["POST"])
def add_ban():
    if not _is_admin_request():
        return {"msg": "unauthorized"}, 401

    payload = request.get_json(silent=True) or {}
    ip = payload.get("ip") or request.args.get("ip")
    if not ip:
        return {"msg": "ip is required"}, 400

    _ban_ip(ip)
    return {"msg": "ip banned", "ip": ip, "banned_ips": _load_banned_ips()}


@app.route("/admin/bans/<ip>", methods=["DELETE"])
def remove_ban(ip):
    if not _is_admin_request():
        return {"msg": "unauthorized"}, 401

    _unban_ip(ip)
    return {"msg": "ip unbanned", "ip": ip, "banned_ips": _load_banned_ips()}


@app.route("/csrf-token")
def csrf_token():
    return {"csrf_token": create_csrf_token()}


@app.errorhandler(HTTPException)
def handle_http(exc):
    return {"msg": exc.description, "status": exc.code}, exc.code

@app.after_request
def set_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer-when-downgrade")
    response.headers.setdefault("Permissions-Policy", "interest-cohort=()")
    if Config.FLASK_ENV == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains; preload")
    return response

@app.errorhandler(Exception)
def handle_unexpected(exc):
    return {"msg": "server error", "status": 500}, 500

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/dashboard")
def dashboard():
    return send_from_directory("static", "dashboard.html")

@app.route("/admino")
def admino_panel():
    return send_from_directory("static", "Admino.html")

@app.route("/onboarding")
def onboarding():
    return send_from_directory("static", "onboarding.html")

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=Config.DEBUG)
