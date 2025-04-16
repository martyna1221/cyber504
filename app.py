import os
import requests
import hvac
import time
import logging
import threading
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Set Flask secret key
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default-secret-key")

# Vault configuration
VAULT_ADDR = os.getenv('VAULT_ADDR', 'http://vault:8200')
VAULT_TOKEN = os.getenv('VAULT_TOKEN', 'dev-only-token')
VAULT_SECRET_PATH = os.getenv('VAULT_SECRET_PATH', 'secret/test-client')

# Keycloak configuration
KEYCLOAK_PUBLIC_HOST = 'localhost'
KEYCLOAK_INTERNAL_HOST = 'keycloak'
KEYCLOAK_REALM = 'cyber'
KEYCLOAK_CLIENT_ID = 'test-client'
KEYCLOAK_ADMIN_USER = 'admin'
KEYCLOAK_ADMIN_PASSWORD = 'admin'

# Initialize Keycloak client secret
KEYCLOAK_CLIENT_SECRET = None
SECRET_REGEN_INTERVAL = 30 * 60  # 30 minutes in seconds

def wait_for_keycloak():
    """Wait for Keycloak to be ready"""
    max_retries = 15
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/master/console",
                timeout=5
            )
            
            if response.status_code == 200:
                return True
                
        except Exception as e:
            logger.warning(f"Keycloak not ready: {e}")
            
        if attempt < max_retries:
            time.sleep(retry_delay)
        else:
            logger.error("Max retries reached waiting for Keycloak")
            return False
            
    return False

def get_keycloak_token():
    """Get admin token from Keycloak"""
    try:
        data = {
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": KEYCLOAK_ADMIN_USER,
            "password": KEYCLOAK_ADMIN_PASSWORD
        }
        
        response = requests.post(
            f"http://{KEYCLOAK_INTERNAL_HOST}:8080/realms/master/protocol/openid-connect/token",
            data=data,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            logger.error(f"Failed to get admin token. Status: {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting admin token: {e}")
        return None

def initialize_vault_client():
    """Initialize the Vault client"""
    try:
        client = hvac.Client(
            url=VAULT_ADDR,
            token=VAULT_TOKEN
        )
        
        if not client.is_authenticated():
            logger.error("Vault client not authenticated")
            return None
            
        return client
    except Exception as e:
        logger.error(f"Error initializing Vault client: {e}")
        return None

def store_secret_in_vault(vault_client, secret):
    """Store the client secret in Vault"""
    try:
        secret_data = {
            "data": {
                "client_secret": secret
            }
        }
        
        vault_client.secrets.kv.v2.create_or_update_secret(
            path="test-client",
            secret=secret_data
        )
        return True
    except Exception as e:
        logger.error(f"Error storing secret in Vault: {e}")
        return False

def get_client_secret():
    """Get client secret from Keycloak and store it in Vault"""
    global KEYCLOAK_CLIENT_SECRET
    max_retries = 10
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            admin_token = get_keycloak_token()
            if not admin_token:
                raise Exception("Failed to get admin token")
            
            headers = {
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}/clients",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            clients = response.json()
            client = next((c for c in clients if c["clientId"] == KEYCLOAK_CLIENT_ID), None)
            
            if not client:
                raise Exception(f"Client {KEYCLOAK_CLIENT_ID} not found")
            
            client_id = client["id"]
            
            response = requests.get(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}/clients/{client_id}/client-secret",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            secret_data = response.json()
            if "value" in secret_data:
                KEYCLOAK_CLIENT_SECRET = secret_data["value"]
                
                vault_client = initialize_vault_client()
                if vault_client and store_secret_in_vault(vault_client, KEYCLOAK_CLIENT_SECRET):
                    return KEYCLOAK_CLIENT_SECRET
                
        except Exception as e:
            logger.error(f"Error getting client secret: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)
            else:
                return None
                
    return None

def rotate_secret_periodically():
    """Background thread to rotate the client secret every 30 minutes"""
    while True:
        try:
            admin_token = get_keycloak_token()
            if not admin_token:
                time.sleep(300)
                continue

            headers = {
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}/clients",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            clients = response.json()
            client = next((c for c in clients if c["clientId"] == KEYCLOAK_CLIENT_ID), None)
            
            if not client:
                time.sleep(300)
                continue
            
            client_id = client["id"]
            
            response = requests.post(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}/clients/{client_id}/client-secret",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            response = requests.get(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}/clients/{client_id}/client-secret",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            secret_data = response.json()
            if "value" in secret_data:
                new_secret = secret_data["value"]
                
                vault_client = initialize_vault_client()
                if vault_client:
                    if store_secret_in_vault(vault_client, new_secret):
                        global KEYCLOAK_CLIENT_SECRET
                        KEYCLOAK_CLIENT_SECRET = new_secret
                        logger.info(f"Secret rotated at {datetime.now()}")
            
        except Exception as e:
            logger.error(f"Secret rotation error: {e}")
        
        time.sleep(120)

# Construct URLs
TOKEN_URL = f"http://{KEYCLOAK_INTERNAL_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
USERINFO_URL = f"http://{KEYCLOAK_INTERNAL_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
LOGOUT_URL = f"http://{KEYCLOAK_PUBLIC_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"

# Initialize the application
def initialize_app():
    """Initialize the application"""
    global KEYCLOAK_CLIENT_SECRET
    if not KEYCLOAK_CLIENT_SECRET:
        logger.info("Initializing application configuration...")
        
        # Wait for Keycloak to be ready
        if not wait_for_keycloak():
            logger.error("Failed to wait for Keycloak")
            return
        
        # Get client secret from Keycloak and store in Vault
        KEYCLOAK_CLIENT_SECRET = get_client_secret()
        if not KEYCLOAK_CLIENT_SECRET:
            logger.error("Failed to get client secret from Keycloak")
            return
            
        # Schedule secret regeneration
        threading.Timer(SECRET_REGEN_INTERVAL, rotate_secret_periodically).start()

# Initialize the app when it starts
initialize_app()

@app.route("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Check Keycloak connection
        try:
            response = requests.get(f"http://{KEYCLOAK_INTERNAL_HOST}:8080/health/ready", timeout=5)
            keycloak_status = "connected" if response.status_code == 200 else "disconnected"
        except:
            keycloak_status = "disconnected"
        
        return jsonify({
            "status": "healthy" if KEYCLOAK_CLIENT_SECRET else "unhealthy",
            "keycloak": keycloak_status,
            "client_secret": "configured" if KEYCLOAK_CLIENT_SECRET else "missing"
        }), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 503

@app.route("/")
def index():
    try:
        if "user" in session:
            user = session["user"]
            first_name = user.get("given_name", "")
            last_name = user.get("family_name", "")
            username = user.get("preferred_username", "User")
            full_name = f"{first_name} {last_name}".strip()
            return render_template("index.html", full_name=full_name, username=username)
        return redirect(url_for("login"))
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    try:
        if request.method == "POST":
            form_username = request.form.get("username")
            form_password = request.form.get("password")
            
            if not form_username or not form_password:
                flash("Please provide both username and password.", "error")
                return redirect(url_for("login"))
            
            logger.info(f"Attempting login for user: {form_username}")
            
            data = {
                "grant_type": "password",
                "client_id": KEYCLOAK_CLIENT_ID,
                "client_secret": KEYCLOAK_CLIENT_SECRET,
                "username": form_username,
                "password": form_password,
                "scope": "openid email profile",
            }
            
            try:
                response = requests.post(TOKEN_URL, data=data, timeout=10)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"Error during token request: {str(e)}")
                flash("Error connecting to authentication server. Please try again.", "error")
                return redirect(url_for("login"))
            
            if response.status_code == 200:
                token = response.json()
                session["id_token"] = token.get("id_token", None)
                access_token = token.get("access_token")
                
                if not access_token:
                    flash("Invalid response from authentication server.", "error")
                    return redirect(url_for("login"))
                
                # Get user info
                headers = {"Authorization": f"Bearer {access_token}"}
                user_info_response = requests.get(USERINFO_URL, headers=headers, timeout=10)
                
                if user_info_response.status_code == 200:
                    user_info = user_info_response.json()
                    session["user"] = user_info
                    session["access_token"] = access_token
                    return redirect(url_for("index"))
                else:
                    flash("Failed to get user information.", "error")
                    return redirect(url_for("login"))
            else:
                flash("Invalid username or password.", "error")
                return redirect(url_for("login"))
        
        return render_template("login.html")
    except Exception as e:
        logger.error(f"Error in login route: {e}")
        flash("An error occurred. Please try again.", "error")
        return redirect(url_for("login"))

@app.route("/logout")
def logout():
    try:
        id_token = session.get("id_token", None)
        session.clear()
        logout_url = (
            f"http://{KEYCLOAK_PUBLIC_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
            f"?post_logout_redirect_uri=http://localhost:5000/login"
        )
        if id_token:
            logout_url += f"&id_token_hint={id_token}"
        return redirect(logout_url)
    except Exception as e:
        logger.error(f"Error in logout route: {e}")
        return redirect(url_for("login"))

if __name__ == "__main__":
    # Start the secret rotation thread
    rotation_thread = threading.Thread(target=rotate_secret_periodically, daemon=True)
    rotation_thread.start()
    
    # Start the Flask application
    app.run(host="0.0.0.0", port=5000, debug=True)
