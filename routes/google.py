import requests
from flask import Blueprint, request, redirect
from werkzeug.security import generate_password_hash
import Config
from Security import create_jwt, api_errors, log_security_event
from Storage import find_user_by_username, find_admino_by_username, load_store, save_store, new_user_id, _now_iso

google_bp = Blueprint("google", __name__, url_prefix="/api/auth/google")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@google_bp.route("/login")
def google_login():
    params = (
        f"?client_id={Config.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={Config.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=openid email profile"
        f"&access_type=offline"
    )
    return redirect(GOOGLE_AUTH_URL + params)


@google_bp.route("/callback")
@api_errors
def google_callback():
    code = request.args.get("code")
    if not code:
        return redirect("/?error=google_denied")

    # Exchange code for token
    token_res = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": Config.GOOGLE_CLIENT_ID,
        "client_secret": Config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": Config.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    token_data = token_res.json()
    access_token = token_data.get("access_token")
    if not access_token:
        return redirect("/?error=google_token_failed")

    # Get user info from Google
    userinfo_res = requests.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
    userinfo = userinfo_res.json()
    email = userinfo.get("email")
    name = userinfo.get("name") or email.split("@")[0]
    google_id = userinfo.get("sub")

    if not email:
        return redirect("/?error=google_no_email")

    # Check if user already exists
    user, biz_id, company_name = find_user_by_username(email)
    if user:
        if not user.get("active"):
            return redirect("/?error=account_disabled")
        token = create_jwt(user["user_id"], biz_id, email, user["role"], company_name)
        return redirect(f"/dashboard?token={token}")

    # New user — send to onboarding
    import jwt as pyjwt
    temp_token = pyjwt.encode(
        {"email": email, "name": name, "google_id": google_id},
        Config.SECRET_KEY, algorithm="HS256"
    )
    return redirect(f"/onboarding?t={temp_token}")


@google_bp.route("/complete", methods=["POST"])
@api_errors
def google_complete():
    """Called after onboarding choice — create business or join existing."""
    import jwt as pyjwt
    body = request.get_json() or {}
    temp_token = body.get("temp_token")
    choice = body.get("choice")  # "create" or "join"

    try:
        payload = pyjwt.decode(temp_token, Config.SECRET_KEY, algorithms=["HS256"])
    except Exception:
        return {"msg": "invalid or expired token"}, 400

    email = payload["email"]
    name = payload["name"]

    if choice == "create":
        company_name = (body.get("company_name") or "").strip()
        if not company_name:
            return {"msg": "company_name is required"}, 400

        from Storage import create_business
        try:
            biz_id, user_id = create_business(company_name, email, generate_password_hash(email + Config.SECRET_KEY))
        except ValueError as e:
            return {"msg": str(e)}, 409

        log_security_event("google_register_business", email, {"business_id": biz_id})
        token = create_jwt(user_id, biz_id, email, "BusinessAdmin", company_name)
        return {"msg": "created", "token": token}

    elif choice == "join":
        invite_code = (body.get("invite_code") or "").strip()
        if not invite_code:
            return {"msg": "invite_code is required"}, 400

        store = load_store()
        matched_biz = None
        for biz_id, biz in store["businesses"].items():
            if biz.get("invite_code") == invite_code:
                matched_biz = (biz_id, biz)
                break

        if not matched_biz:
            return {"msg": "invalid invite code"}, 404

        biz_id, biz = matched_biz
        user_id = new_user_id()
        biz["users"][user_id] = {
            "user_id": user_id,
            "username": email,
            "password": generate_password_hash(email + Config.SECRET_KEY),
            "role": "Employee",
            "active": True,
            "created_at": _now_iso(),
        }
        save_store(store)
        log_security_event("google_join_business", email, {"business_id": biz_id})
        token = create_jwt(user_id, biz_id, email, "Employee", biz["company_name"])
        return {"msg": "joined", "token": token}

    return {"msg": "invalid choice"}, 400