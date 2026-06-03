from flask import Blueprint, send_from_directory
from Security import admin_required

operations_bp = Blueprint("operations", __name__)


@operations_bp.route("/operations")
@admin_required
def operations():
    return send_from_directory("static", "Operations.html")
