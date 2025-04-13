import os
import requests
from flask import Flask, render_template, request, redirect, session, url_for, flash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

KEYCLOAK_PUBLIC_HOST = os.getenv("KEYCLOAK_PUBLIC_HOST")  
KEYCLOAK_INTERNAL_HOST = os.getenv("KEYCLOAK_INTERNAL_HOST")  
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")

TOKEN_URL = f"http://{KEYCLOAK_INTERNAL_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
USERINFO_URL = f"http://{KEYCLOAK_INTERNAL_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
LOGOUT_URL = f"http://{KEYCLOAK_PUBLIC_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"

@app.route("/")
def index():
    if "user" in session:
        user = session["user"]
        first_name = user.get("given_name", "")
        last_name = user.get("family_name", "")
        username = user.get("preferred_username", "User")
        full_name = f"{first_name} {last_name}".strip()
        return render_template("index.html", full_name=full_name, username=username)
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        form_username = request.form.get("username")
        form_password = request.form.get("password")
        if not form_username or not form_password:
            flash("Please provide both username and password.", "error")
            return redirect(url_for("login"))
        data = {
            "grant_type": "password",
            "client_id": KEYCLOAK_CLIENT_ID,
            "client_secret": KEYCLOAK_CLIENT_SECRET,
            "username": form_username,
            "password": form_password,
            "scope": "openid email profile",
        }
        response = requests.post(TOKEN_URL, data=data)
        if response.status_code == 200:
            token = response.json()
            access_token = token.get("access_token")
            if not access_token:
                flash("Access token not found in response.", "error")
                return redirect(url_for("login"))
            session["token_data"] = token
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_resp = requests.get(USERINFO_URL, headers=headers)
            if userinfo_resp.status_code == 200:
                session["user"] = userinfo_resp.json()
                return redirect(url_for("index"))
            else:
                flash("Failed to retrieve user info.", "error")
                return redirect(url_for("login"))
        else:
            flash("Invalid credentials. Please try again.", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    token_data = session.get("token_data", {})
    id_token = token_data.get("id_token")
    session.pop("user", None)
    session.pop("token_data", None)
    post_logout_redirect = url_for("login", _external=True)
    if id_token:
        keycloak_logout_url = (
            f"{LOGOUT_URL}?id_token_hint={id_token}"
            f"&post_logout_redirect_uri={post_logout_redirect}"
        )
        return redirect(keycloak_logout_url)
    else:
        return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
