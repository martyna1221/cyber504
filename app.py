import os
import requests
import hvac
import time
import logging
import threading
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Set Flask secret key
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default-secret-key")

# Keycloak configuration
KEYCLOAK_PUBLIC_HOST = 'localhost'
KEYCLOAK_INTERNAL_HOST = 'keycloak'
KEYCLOAK_REALM = 'cyber'
KEYCLOAK_CLIENT_ID = 'test-client'
KEYCLOAK_ADMIN_USER = 'admin'
KEYCLOAK_ADMIN_PASSWORD = 'admin'

# Initialize Keycloak client secret
KEYCLOAK_CLIENT_SECRET = None

def wait_for_keycloak():
    """Wait for Keycloak to be ready"""
    max_retries = 30
    retry_delay = 2
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Checking Keycloak readiness (attempt {attempt}/{max_retries})")
            response = requests.get(f"http://{KEYCLOAK_INTERNAL_HOST}:8080/health/ready", timeout=5)
            if response.status_code == 200:
                logger.info("Keycloak is ready")
                return True
        except Exception as e:
            logger.warning(f"Keycloak not ready yet: {e}")
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
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        logger.error(f"Error getting Keycloak admin token: {e}")
        return None

def get_client_secret():
    """Get client secret from Keycloak and store it in Vault"""
    global KEYCLOAK_CLIENT_SECRET
    max_retries = 10
    retry_delay = 5
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Getting client secret from Keycloak (attempt {attempt}/{max_retries})")
            
            # Get admin token
            admin_token = get_keycloak_token()
            if not admin_token:
                raise Exception("Failed to get admin token")
            
            # First, verify the realm exists
            headers = {
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            }
            realm_response = requests.get(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}",
                headers=headers,
                timeout=10
            )
            if realm_response.status_code != 200:
                logger.error(f"Realm {KEYCLOAK_REALM} not found or not accessible. Status: {realm_response.status_code}")
                raise Exception(f"Realm {KEYCLOAK_REALM} not found")
            
            # Then, verify the client exists
            client_response = requests.get(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}/clients",
                headers=headers,
                timeout=10
            )
            if client_response.status_code != 200:
                logger.error(f"Failed to get clients. Status: {client_response.status_code}")
                raise Exception("Failed to get clients")
            
            clients = client_response.json()
            client_exists = any(client["clientId"] == KEYCLOAK_CLIENT_ID for client in clients)
            if not client_exists:
                logger.error(f"Client {KEYCLOAK_CLIENT_ID} not found in realm {KEYCLOAK_REALM}")
                raise Exception(f"Client {KEYCLOAK_CLIENT_ID} not found")
            
            # Get client secret
            secret_response = requests.get(
                f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}/clients/{KEYCLOAK_CLIENT_ID}/client-secret",
                headers=headers,
                timeout=10
            )
            
            if secret_response.status_code != 200:
                logger.error(f"Failed to get client secret. Status: {secret_response.status_code}, Response: {secret_response.text}")
                raise Exception(f"Failed to get client secret: {secret_response.text}")
            
            secret_data = secret_response.json()
            if "value" in secret_data:
                KEYCLOAK_CLIENT_SECRET = secret_data["value"]
                logger.info("Successfully retrieved client secret from Keycloak")
                
                # Store secret in Vault
                vault_client = initialize_vault_client()
                if vault_client:
                    store_secret_in_vault(vault_client, KEYCLOAK_CLIENT_SECRET)
                
                return KEYCLOAK_CLIENT_SECRET
            else:
                logger.error(f"No secret value in response: {secret_data}")
                raise Exception("No secret value in response")
                
        except Exception as e:
            logger.error(f"Error getting client secret: {e}")
            if attempt < max_retries:
                logger.info(f"Waiting {retry_delay} seconds before retry...")
                time.sleep(retry_delay)
            else:
                logger.error("Max retries reached getting client secret")
                return None

def regenerate_client_secret():
    """Regenerate the client secret and update it in Vault"""
    global KEYCLOAK_CLIENT_SECRET
    
    try:
        logger.info("Regenerating client secret...")
        
        # Get admin token
        admin_token = get_keycloak_token()
        if not admin_token:
            logger.error("Failed to get admin token for secret regeneration")
            return
        
        # Regenerate client secret
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            f"http://{KEYCLOAK_INTERNAL_HOST}:8080/admin/realms/{KEYCLOAK_REALM}/clients/{KEYCLOAK_CLIENT_ID}/client-secret",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        
        secret_data = response.json()
        if "value" in secret_data:
            KEYCLOAK_CLIENT_SECRET = secret_data["value"]
            logger.info("Successfully regenerated client secret")
            
            # Store new secret in Vault with retries
            max_vault_retries = 3
            vault_retry_delay = 5
            
            for vault_attempt in range(1, max_vault_retries + 1):
                try:
                    logger.info(f"Attempting to store secret in Vault (attempt {vault_attempt}/{max_vault_retries})")
                    vault_client = initialize_vault_client()
                    if vault_client:
                        if store_secret_in_vault(vault_client, KEYCLOAK_CLIENT_SECRET):
                            logger.info("Successfully updated secret in Vault")
                            break
                    else:
                        logger.error("Failed to initialize Vault client")
                except Exception as e:
                    logger.error(f"Error storing secret in Vault: {e}")
                    if vault_attempt < max_vault_retries:
                        logger.info(f"Waiting {vault_retry_delay} seconds before retry...")
                        time.sleep(vault_retry_delay)
                    else:
                        logger.error("Max retries reached for Vault storage")
        else:
            logger.error("No secret value in regeneration response")
            
    except Exception as e:
        logger.error(f"Error regenerating client secret: {e}")
    
    # Schedule next regeneration
    threading.Timer(SECRET_REGEN_INTERVAL, regenerate_client_secret).start()

# Construct URLs
TOKEN_URL = f"http://{KEYCLOAK_INTERNAL_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
USERINFO_URL = f"http://{KEYCLOAK_INTERNAL_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
LOGOUT_URL = f"http://{KEYCLOAK_PUBLIC_HOST}:8080/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"

@app.before_first_request
def initialize_app():
    """Initialize the application before the first request"""
    global KEYCLOAK_CLIENT_SECRET
    if not KEYCLOAK_CLIENT_SECRET:
        logger.info("Initializing application configuration...")
        
        # Wait for Keycloak to be ready
        if not wait_for_keycloak():
            logger.error("Failed to wait for Keycloak")
            return
        
        # Get client secret from Keycloak
        KEYCLOAK_CLIENT_SECRET = get_client_secret()
        if not KEYCLOAK_CLIENT_SECRET:
            logger.error("Failed to get client secret from Keycloak")
            return

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
        session.clear()
        return redirect(LOGOUT_URL)
    except Exception as e:
        logger.error(f"Error in logout route: {e}")
        return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
