import html
import logging
import os
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
DB_PATH = BASE_DIR / "keeply.db"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Validate required environment variables
if not os.environ.get("GOOGLE_CLIENT_ID") or not os.environ.get("GOOGLE_CLIENT_SECRET"):
    print("WARNING: GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set. OAuth will not work.")

app = Flask(__name__, static_folder="static")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "local-development-key-change-me")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
APP_BASE_URL = os.environ.get("APP_BASE_URL", "https://stratview.pythonanywhere.com").rstrip("/")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", f"https://stratview.pythonanywhere.com/api/auth/google/callback")


def google_redirect_uri():
    """Use the configured callback, or the current HTTPS host in deployment."""
    if request.host.endswith(".pythonanywhere.com"):
        return f"https://{request.host}/auth/google/callback"
    if os.environ.get("GOOGLE_REDIRECT_URI"):
        return GOOGLE_REDIRECT_URI
    return f"{request.host_url.rstrip('/')}/auth/google/callback"


def db():
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


# Input validation and sanitization
def sanitize_text(text, max_length=500):
    """Sanitize and validate text input to prevent XSS."""
    if not isinstance(text, str):
        return ""
    text = text.strip()[:max_length]
    return html.escape(text)


def validate_email(email):
    """Validate email format."""
    if not isinstance(email, str) or len(email) > 254:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_json_request():
    """Validate that request is JSON and has proper Content-Type."""
    if request.content_length and request.content_length > app.config["MAX_CONTENT_LENGTH"]:
        return False, "Request too large"
    if request.method in ("POST", "PUT"):
        if not request.is_json:
            return False, "Content-Type must be application/json"
    return True, None


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
    return {"name": name, "category": category, "vendor": vendor, "price": price, "purchased_on": purchased, "warranty_until": warranty, "return_until": (date.today() + timedelta(days=14)).isoformat(), "location": "Personal"}


@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    return send_from_directory(app.static_folder, "Index.html")


@app.get("/login")
def login():
    if "user" in session:
        return redirect(url_for("index"))
    return send_from_directory(app.static_folder, "login.html")


@app.get("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return send_from_directory(app.static_folder, "Index.html")


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
    if not profile.get("sub") or not profile.get("email"):
        return jsonify({"error": "Google profile missing required fields"}), 400
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
    try:
        with db() as connection:
            rows = connection.execute("SELECT * FROM assets WHERE status != 'archived' ORDER BY created_at DESC").fetchall()
        return jsonify([asset_dict(row) for row in rows])
    except Exception as e:
        logger.error(f"Error fetching assets: {e}")
        return jsonify({"error": "Failed to fetch assets"}), 500


@app.post("/api/assets")
def create_asset():
    valid, error = validate_json_request()
    if not valid:
        return jsonify({"error": error}), 400
    
    payload = request.get_json(silent=True) or {}
    name = sanitize_text(payload.get("name", ""), 200)
    if not name:
        return jsonify({"error": "Asset name is required"}), 400
    
    try:
        price = float(payload.get("price", 0) or 0)
        if price < 0:
            return jsonify({"error": "Price cannot be negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Price must be a valid number"}), 400
    
    category = sanitize_text(payload.get("category", "Other"), 100)
    vendor = sanitize_text(payload.get("vendor", ""), 200)
    location = sanitize_text(payload.get("location", "Personal"), 100)
    purchased_on = sanitize_text(payload.get("purchased_on", ""), 50)
    warranty_until = sanitize_text(payload.get("warranty_until", ""), 50)
    return_until = sanitize_text(payload.get("return_until", ""), 50)
    
    try:
        with db() as connection:
            connection.execute("BEGIN")
            cursor = connection.execute(
                "INSERT INTO assets (name, category, vendor, price, purchased_on, warranty_until, return_until, location, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, category, vendor, price, purchased_on, warranty_until, return_until, location, datetime.utcnow().isoformat())
            )
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
            connection.commit()
        return jsonify(asset_dict(row)), 201
    except Exception as e:
        logger.error(f"Error creating asset: {e}")
        return jsonify({"error": "Failed to create asset"}), 500


@app.post("/api/import")
def import_document():
    valid, error = validate_json_request()
    if not valid:
        return jsonify({"error": error}), 400
    
    upload = request.files.get("document")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a document to upload"}), 400
    
    # Validate file size (5MB max for documents)
    if len(upload.read()) > 5 * 1024 * 1024:
        return jsonify({"error": "File too large (max 5MB)"}), 413
    upload.seek(0)  # Reset file pointer
    
    filename = secure_filename(upload.filename)
    if not filename or len(filename) > 255:
        return jsonify({"error": "Invalid filename"}), 400
    
    try:
        content = upload.read()
        file_path = UPLOAD_DIR / filename
        file_path.write_bytes(content)
        
        extracted = parse_extraction(filename, content)
        extracted["document_name"] = filename
        
        with db() as connection:
            connection.execute("BEGIN")
            cursor = connection.execute(
                "INSERT INTO assets (name, category, vendor, price, purchased_on, warranty_until, return_until, location, document_name, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*extracted.values(), datetime.utcnow().isoformat())
            )
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (cursor.lastrowid,)).fetchone()
            connection.commit()
        
        return jsonify({"asset": asset_dict(row), "extracted": ["Item", "Price", "Purchase date", "Warranty", "Vendor"]}), 201
    except Exception as e:
        logger.error(f"Error importing document: {e}")
        return jsonify({"error": "Failed to import document"}), 500


@app.delete("/api/assets/<int:asset_id>")
def archive_asset(asset_id):
    try:
        with db() as connection:
            asset = connection.execute("SELECT document_name FROM assets WHERE id = ?", (asset_id,)).fetchone()
            if not asset:
                return jsonify({"error": "Asset not found"}), 404
            
            connection.execute("BEGIN")
            connection.execute("UPDATE assets SET status = 'archived' WHERE id = ?", (asset_id,))
            connection.commit()
            
            # Clean up uploaded file if exists
            if asset["document_name"]:
                file_path = UPLOAD_DIR / asset["document_name"]
                if file_path.exists():
                    try:
                        file_path.unlink()
                    except Exception as e:
                        logger.warning(f"Could not delete file {asset['document_name']}: {e}")
        
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Error archiving asset: {e}")
        return jsonify({"error": "Failed to archive asset"}), 500


@app.get("/api/reminders")
def list_reminders():
    try:
        with db() as connection:
            rows = connection.execute("SELECT reminders.*, assets.name AS asset_name FROM reminders JOIN assets ON assets.id = reminders.asset_id WHERE assets.status != 'archived' ORDER BY due_on").fetchall()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        logger.error(f"Error fetching reminders: {e}")
        return jsonify({"error": "Failed to fetch reminders"}), 500


@app.post("/api/reminders")
def create_reminder():
    valid, error = validate_json_request()
    if not valid:
        return jsonify({"error": error}), 400
    
    payload = request.get_json(silent=True) or {}
    asset_id = payload.get("asset_id")
    title = sanitize_text(payload.get("title", ""), 300)
    due_on = sanitize_text(payload.get("due_on", ""), 50)
    kind = sanitize_text(payload.get("kind", "reminder"), 50)
    
    if not asset_id or not title or not due_on:
        return jsonify({"error": "asset_id, title, and due_on are required"}), 400
    
    try:
        with db() as connection:
            # Verify asset exists
            asset = connection.execute("SELECT id FROM assets WHERE id = ?", (asset_id,)).fetchone()
            if not asset:
                return jsonify({"error": "Asset not found"}), 404
            
            connection.execute("BEGIN")
            cursor = connection.execute(
                "INSERT INTO reminders (asset_id, title, due_on, kind) VALUES (?, ?, ?, ?)",
                (asset_id, title, due_on, kind)
            )
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (cursor.lastrowid,)).fetchone()
            connection.commit()
        return jsonify(dict(row)), 201
    except Exception as e:
        logger.error(f"Error creating reminder: {e}")
        return jsonify({"error": "Failed to create reminder"}), 500


@app.put("/api/reminders/<int:reminder_id>")
def update_reminder(reminder_id):
    valid, error = validate_json_request()
    if not valid:
        return jsonify({"error": error}), 400
    
    payload = request.get_json(silent=True) or {}
    title = sanitize_text(payload.get("title", ""), 300)
    due_on = sanitize_text(payload.get("due_on", ""), 50)
    kind = sanitize_text(payload.get("kind", "reminder"), 50)
    
    try:
        with db() as connection:
            # Verify reminder exists
            reminder = connection.execute("SELECT id FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
            if not reminder:
                return jsonify({"error": "Reminder not found"}), 404
            
            connection.execute("BEGIN")
            connection.execute(
                "UPDATE reminders SET title = ?, due_on = ?, kind = ? WHERE id = ?",
                (title, due_on, kind, reminder_id)
            )
            row = connection.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
            connection.commit()
        return jsonify(dict(row))
    except Exception as e:
        logger.error(f"Error updating reminder: {e}")
        return jsonify({"error": "Failed to update reminder"}), 500


@app.delete("/api/reminders/<int:reminder_id>")
def delete_reminder(reminder_id):
    try:
        with db() as connection:
            reminder = connection.execute("SELECT id FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
            if not reminder:
                return jsonify({"error": "Reminder not found"}), 404
            
            connection.execute("BEGIN")
            connection.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
            connection.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Error deleting reminder: {e}")
        return jsonify({"error": "Failed to delete reminder"}), 500


@app.get("/api/people")
def list_people():
    try:
        with db() as connection:
            rows = connection.execute("SELECT * FROM people ORDER BY name COLLATE NOCASE").fetchall()
        return jsonify([person_dict(row) for row in rows])
    except Exception as e:
        logger.error(f"Error fetching people: {e}")
        return jsonify({"error": "Failed to fetch people"}), 500


@app.post("/api/people")
def create_person():
    valid, error = validate_json_request()
    if not valid:
        return jsonify({"error": error}), 400
    
    payload = request.get_json(silent=True) or {}
    name = sanitize_text(payload.get("name", ""), 200)
    if not name:
        return jsonify({"error": "Name is required"}), 400
    
    role = sanitize_text(payload.get("role", ""), 200)
    email = sanitize_text(payload.get("email", ""), 254)
    phone = sanitize_text(payload.get("phone", ""), 20)
    notes = sanitize_text(payload.get("notes", ""), 1000)
    
    if email and not validate_email(email):
        return jsonify({"error": "Invalid email format"}), 400
    
    try:
        with db() as connection:
            connection.execute("BEGIN")
            cursor = connection.execute(
                "INSERT INTO people (name, role, email, phone, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (name, role, email, phone, notes, datetime.utcnow().isoformat())
            )
            row = connection.execute("SELECT * FROM people WHERE id = ?", (cursor.lastrowid,)).fetchone()
            connection.commit()
        return jsonify(person_dict(row)), 201
    except Exception as e:
        logger.error(f"Error creating person: {e}")
        return jsonify({"error": "Failed to create person"}), 500


@app.delete("/api/people/<int:person_id>")
def delete_person(person_id):
    try:
        with db() as connection:
            person = connection.execute("SELECT id FROM people WHERE id = ?", (person_id,)).fetchone()
            if not person:
                return jsonify({"error": "Person not found"}), 404
            
            connection.execute("BEGIN")
            connection.execute("DELETE FROM people WHERE id = ?", (person_id,))
            connection.commit()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Error deleting person: {e}")
        return jsonify({"error": "Failed to delete person"}), 500


@app.get("/api/summary")
def summary():
    try:
        with db() as connection:
            totals = connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(price), 0) AS value FROM assets WHERE status != 'archived'").fetchone()
            categories = connection.execute("SELECT category, COUNT(*) AS count FROM assets WHERE status != 'archived' GROUP BY category ORDER BY count DESC").fetchall()
        return jsonify({"asset_count": totals["count"], "total_value": float(totals["value"]), "categories": [dict(row) for row in categories]})
    except Exception as e:
        logger.error(f"Error fetching summary: {e}")
        return jsonify({"error": "Failed to fetch summary"}), 500


init_db()

if __name__ == "__main__":
    app.run(debug=True)
