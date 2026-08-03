import jwt
import requests
from datetime import datetime, timedelta
from flask import Blueprint, request, redirect
import Config
from Security import api_errors, log_security_event
from Storage import add_user_to_business, find_user_by_username, get_supabase_client, sign_in_with_supabase

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
    try:
        token_res = requests.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": Config.GOOGLE_CLIENT_ID,
            "client_secret": Config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": Config.GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }, timeout=10)
    except requests.RequestException:
        return redirect("/?error=google_token_failed")

    try:
        token_data = token_res.json()
    except ValueError:
        token_data = {}

    access_token = token_data.get("access_token")
    if not access_token or token_res.status_code != 200:
        return redirect("/?error=google_token_failed")

    # Get user info from Google
    try:
        userinfo_res = requests.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        userinfo = userinfo_res.json()
    except requests.RequestException:
        return redirect("/?error=google_no_email")

    email = userinfo.get("email")
    name = userinfo.get("name") or (email.split("@")[0] if email else "")
    google_id = userinfo.get("sub")

    if not email:
        return redirect("/?error=google_no_email")

    # Check if user already exists
    user, biz_id, company_name = find_user_by_username(email)
    if user:
        if not user.get("active"):
            return redirect("/?error=account_disabled")
        session = sign_in_with_supabase(email, email + Config.SECRET_KEY)
        if not session:
            return redirect("/?error=google_login_failed")
        return redirect(f"/dashboard?token={session['access_token']}")

    # New user — send to onboarding using a short-lived temp cookie
    temp_token = jwt.encode(
        {
            "email": email,
            "name": name,
            "google_id": google_id,
            "exp": datetime.utcnow() + timedelta(minutes=10),
        },
        Config.SECRET_KEY,
        algorithm="HS256"
    )
    return redirect(f"/onboarding?temp_token={temp_token}")


@google_bp.route("/complete", methods=["POST"])
@api_errors
def google_complete():
    """Called after onboarding choice — create business or join existing."""
    body = request.get_json() or {}
    temp_token = body.get("temp_token") or request.args.get("temp_token") or request.cookies.get("google_temp_token")
    choice = body.get("choice")  # "create" or "join"

    try:
        payload = jwt.decode(temp_token, Config.SECRET_KEY, algorithms=["HS256"])
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
            biz_id, user_id, access_token = create_business(company_name, email, email + Config.SECRET_KEY)
        except ValueError as e:
            return {"msg": str(e)}, 409

        log_security_event("google_register_business", email, {"business_id": biz_id})
        return {"msg": "created", "token": access_token, "business_id": biz_id, "user_id": user_id}

    elif choice == "join":
        invite_code = (body.get("invite_code") or "").strip()
        if not invite_code:
            return {"msg": "invite_code is required"}, 400

        client = get_supabase_client()
        matched_biz = None
        if client:
            result = client.table("businesses").select("*").eq("invite_code", invite_code).limit(1).execute()
            rows = result.data or []
            if rows:
                matched_biz = (rows[0].get("id") or rows[0].get("business_id"), rows[0])

        if not matched_biz:
            return {"msg": "invalid invite code"}, 404

        biz_id, biz = matched_biz
        try:
            user_id = add_user_to_business(biz_id, email, email + Config.SECRET_KEY, "Employee")
        except ValueError as exc:
            return {"msg": str(exc)}, 409

        log_security_event("google_join_business", email, {"business_id": biz_id})
        session = sign_in_with_supabase(email, email + Config.SECRET_KEY)
        token = session["access_token"] if session else None
        return {"msg": "joined", "token": token, "business_id": biz_id, "user_id": user_id}

    return {"msg": "invalid choice"}, 400