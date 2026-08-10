import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "keeply.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-development-key-change-me")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://127.0.0.1:5000").rstrip("/")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", f"{APP_BASE_URL}/auth/google/callback")


def google_redirect_uri():
    """Use the configured callback, or the current HTTPS host in deployment."""
    if request.host.endswith(".pythonanywhere.com"):
        return f"https://{request.host}/auth/google/callback"
    if os.environ.get("GOOGLE_REDIRECT_URI"):
        return GOOGLE_REDIRECT_URI
    return f"{request.host_url.rstrip('/')}/auth/google/callback"


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Other',
                vendor TEXT DEFAULT '',
                price REAL DEFAULT 0,
                purchased_on TEXT DEFAULT '',
                warranty_until TEXT DEFAULT '',
                return_until TEXT DEFAULT '',
                location TEXT DEFAULT 'Personal',
                status TEXT NOT NULL DEFAULT 'active',
                document_name TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                due_on TEXT NOT NULL,
                kind TEXT NOT NULL DEFAULT 'reminder',
                FOREIGN KEY(asset_id) REFERENCES assets(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT DEFAULT '',
                email TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            """
        )


def asset_dict(row):
    item = dict(row)
    item["price"] = float(item["price"] or 0)
    return item


def person_dict(row):
    return dict(row)


def parse_extraction(filename, content):
    text = (content or b"").decode("utf-8", errors="ignore")
    source = f"{filename} {text}".lower()
    category = "Other"
    for keyword, value in (("subscription", "Subscription"), ("car", "Vehicle"), ("camry", "Vehicle"), ("macbook", "Electronics"), ("laptop", "Electronics"), ("hvac", "Home"), ("invoice", "Equipment")):
        if keyword in source:
            category = value
            break
    name = Path(filename).stem.replace("_", " ").replace("-", " ").title() or "Untitled asset"
    price_match = re.search(r"(?:\$|usd\s*)([0-9,]+(?:\.\d{1,2})?)", text, re.I)
    price = float(price_match.group(1).replace(",", "")) if price_match else 0
    vendor = ""
    vendor_match = re.search(r"vendor\s*[:\-]\s*([^\n]+)", text, re.I)
    if vendor_match:
        vendor = vendor_match.group(1).strip()
    purchased = date.today().isoformat()
    warranty = (date.today() + timedelta(days=365)).isoformat()
    return {"name": name, "category": category, "vendor": vendor, "price": price, "purchased_on": purchased, "warranty_until": warranty, "return_until": (date.today() + timedelta(days=14)).isoformat()}


@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return send_from_directory(app.static_folder, "index.html")


@app.get("/login")
def login():
    if "user" in session:
        return redirect(url_for("index"))
    return send_from_directory(app.static_folder, "login.html")


@app.get("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return send_from_directory(app.static_folder, "index.html")


@app.get("/terms")
def terms():
    return send_from_directory(app.static_folder, "terms.html")


@app.get("/privacy")
def privacy():
    return send_from_directory(app.static_folder, "privacy.html")


@app.get("/auth/google")
def google_login():
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return jsonify({"error": "Google OAuth is not configured"}), 503
    session["oauth_state"] = os.urandom(24).hex()
    query = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": google_redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
        "state": session["oauth_state"],
    }
    from urllib.parse import urlencode
    return redirect("https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(query))


@app.get("/auth/google/callback")
def google_callback():
    if request.args.get("error"):
        return redirect("/?auth_error=" + request.args["error"])
    if not request.args.get("state") or request.args["state"] != session.pop("oauth_state", None):
        return jsonify({"error": "Invalid OAuth state"}), 400
    code = request.args.get("code")
    if not code:
        return jsonify({"error": "Google did not return an authorization code"}), 400
    token_response = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": google_redirect_uri(),
        "grant_type": "authorization_code",
    }, timeout=15)
    if not token_response.ok:
        return jsonify({"error": "Google token exchange failed"}), 502
    access_token = token_response.json().get("access_token")
    profile_response = requests.get("https://openidconnect.googleapis.com/v1/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=15)
    if not profile_response.ok:
        return jsonify({"error": "Could not retrieve Google profile"}), 502
    profile = profile_response.json()
    session["user"] = {key: profile.get(key, "") for key in ("sub", "name", "email", "picture")}
    return redirect(url_for("dashboard"))


@app.post("/auth/logout")
def logout():
    session.pop("user", None)
    return jsonify({"ok": True})


@app.get("/api/me")
def current_user():
    return jsonify(session.get("user"))


@app.get("/api/assets")
def list_assets():
    with db() as connection:
        rows = connection.execute("SELECT * FROM assets WHERE status != 'archived' ORDER BY created_at DESC").fetchall()
    return jsonify([asset_dict(row) for row in rows])


@app.post("/api/assets")
def create_asset():
    payload = request.get_json(silent=True) or {}
    if not payload.get("name"):
        return jsonify({"error": "Asset name is required"}), 400
    fields = {key: payload.get(key, "") for key in ("name", "category", "vendor", "price", "purchased_on", "warranty_until", "return_until", "location", "document_name")}
    with db() as connection:
        cursor = connection.execute("INSERT INTO assets (name, category, vendor, price, purchased_on, warranty_until, return_until, location, document_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*fields.values(), datetime.utcnow().isoformat()))
        row = connection.execute("SELECT * FROM assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(asset_dict(row)), 201


@app.post("/api/import")
def import_document():
    upload = request.files.get("document")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a document to upload"}), 400
    filename = secure_filename(upload.filename)
    content = upload.read()
    (UPLOAD_DIR / filename).write_bytes(content)
    extracted = parse_extraction(filename, content)
    extracted["document_name"] = filename
    with db() as connection:
        cursor = connection.execute("INSERT INTO assets (name, category, vendor, price, purchased_on, warranty_until, return_until, location, document_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (*extracted.values(), datetime.utcnow().isoformat()))
        row = connection.execute("SELECT * FROM assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify({"asset": asset_dict(row), "extracted": ["Item", "Price", "Purchase date", "Warranty", "Vendor"]}), 201


@app.delete("/api/assets/<int:asset_id>")
def archive_asset(asset_id):
    with db() as connection:
        connection.execute("UPDATE assets SET status = 'archived' WHERE id = ?", (asset_id,))
    return jsonify({"ok": True})


@app.get("/api/reminders")
def reminders():
    with db() as connection:
        rows = connection.execute("SELECT reminders.*, assets.name AS asset_name FROM reminders JOIN assets ON assets.id = reminders.asset_id ORDER BY due_on").fetchall()
    return jsonify([dict(row) for row in rows])


@app.get("/api/people")
def list_people():
    with db() as connection:
        rows = connection.execute("SELECT * FROM people ORDER BY name COLLATE NOCASE").fetchall()
    return jsonify([person_dict(row) for row in rows])


@app.post("/api/people")
def create_person():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400
    values = (name, payload.get("role", ""), payload.get("email", ""), payload.get("phone", ""), payload.get("notes", ""), datetime.utcnow().isoformat())
    with db() as connection:
        cursor = connection.execute("INSERT INTO people (name, role, email, phone, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)", values)
        row = connection.execute("SELECT * FROM people WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return jsonify(person_dict(row)), 201


@app.delete("/api/people/<int:person_id>")
def delete_person(person_id):
    with db() as connection:
        connection.execute("DELETE FROM people WHERE id = ?", (person_id,))
    return jsonify({"ok": True})


@app.get("/api/summary")
def summary():
    with db() as connection:
        totals = connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(price), 0) AS value FROM assets WHERE status != 'archived'").fetchone()
        categories = connection.execute("SELECT category, COUNT(*) AS count FROM assets WHERE status != 'archived' GROUP BY category ORDER BY count DESC").fetchall()
    return jsonify({"asset_count": totals["count"], "total_value": float(totals["value"]), "categories": [dict(row) for row in categories]})


init_db()

if __name__ == "__main__":
    app.run(debug=True)
