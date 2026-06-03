import os
from flask import Flask, send_from_directory
from werkzeug.exceptions import HTTPException

import Config
from routes.auth import auth_bp
from routes.Team import team_bp
from routes.Admino import admino_bp

app = Flask(__name__, static_folder="static")
app.config["SECRET_KEY"] = Config.SECRET_KEY

app.register_blueprint(auth_bp)
app.register_blueprint(team_bp)
app.register_blueprint(admino_bp)


@app.errorhandler(HTTPException)
def handle_http(exc):
    return {"msg": exc.description, "status": exc.code}, exc.code

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
    return send_from_directory("static", "admino.html")

if __name__ == "__main__":
    app.run(port=3000, debug=Config.DEBUG)