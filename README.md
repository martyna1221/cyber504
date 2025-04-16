# Flask Application with Keycloak and Vault Integration

This application demonstrates integration between Flask, Keycloak, and Vault for secure authentication and secret management.

## Main Components

### Configuration
- `VAULT_ADDR`: Vault server address
- `VAULT_TOKEN`: Vault authentication token
- `KEYCLOAK_PUBLIC_HOST`: Public hostname for Keycloak
- `KEYCLOAK_INTERNAL_HOST`: Internal hostname for Keycloak
- `KEYCLOAK_REALM`: Keycloak realm name
- `KEYCLOAK_CLIENT_ID`: Keycloak client ID
- `KEYCLOAK_ADMIN_USER`: Keycloak admin username
- `KEYCLOAK_ADMIN_PASSWORD`: Keycloak admin password

### Core Functions

#### `wait_for_keycloak()`
- Purpose: Ensures Keycloak is ready before proceeding
- Behavior:
  - Attempts to connect to Keycloak's admin console
  - Retries up to 15 times with 5-second delays
  - Returns True when Keycloak is ready, False otherwise

#### `get_keycloak_token()`
- Purpose: Obtains an admin token from Keycloak
- Behavior:
  - Authenticates with Keycloak using admin credentials
  - Returns the access token if successful
  - Returns None if authentication fails

#### `initialize_vault_client()`
- Purpose: Creates and authenticates a Vault client
- Behavior:
  - Initializes a new Vault client with configured address and token
  - Verifies client authentication
  - Returns the client if successful, None otherwise

#### `store_secret_in_vault(vault_client, secret)`
- Purpose: Stores a secret in Vault
- Behavior:
  - Creates a secret data structure
  - Stores the secret in Vault at path 'secret/data/test-client'
  - Returns True if successful, False otherwise

#### `get_client_secret()`
- Purpose: Retrieves and manages the client secret
- Behavior:
  - Gets admin token from Keycloak
  - Retrieves client ID for the configured client
  - Gets the client secret
  - Stores the secret in Vault
  - Returns the secret if successful, None otherwise

#### `rotate_secret_periodically()`
- Purpose: Automatically rotates the client secret
- Behavior:
  - Runs as a background thread
  - Regenerates the client secret every 30 minutes
  - Updates the secret in both Keycloak and Vault
  - Logs rotation events and errors

### Application Routes

#### `@app.route("/health")`
- Purpose: Health check endpoint
- Behavior:
  - Checks Keycloak connection status
  - Returns application health status
  - Includes client secret configuration status

#### `@app.route("/")`
- Purpose: Main application route
- Behavior:
  - Redirects to login if user is not authenticated
  - Displays user information if authenticated

#### `@app.route("/login")`
- Purpose: Handles user authentication
- Behavior:
  - Processes login form submissions
  - Authenticates with Keycloak
  - Manages user session
  - Redirects to appropriate pages based on authentication status

#### `@app.route("/logout")`
- Purpose: Handles user logout
- Behavior:
  - Clears user session
  - Redirects to Keycloak logout endpoint

## Security Features

1. Automatic Secret Rotation
   - Client secret rotates every 30 minutes
   - Secrets stored securely in Vault
   - Seamless integration with Keycloak

2. Secure Authentication
   - OAuth2/OpenID Connect with Keycloak
   - Session management
   - Secure token handling

3. Error Handling
   - Comprehensive error logging
   - Graceful failure handling
   - Retry mechanisms for critical operations

## Dependencies

- Flask: Web application framework
- hvac: HashiCorp Vault client
- requests: HTTP client
- python-dotenv: Environment variable management

Project specifications document: https://docs.google.com/document/d/1I36S6lHBOS_8Y0obdqbV9QHCZuPZmXLyRHPsV7EtCxo/edit?tab=t.0

** Initial setup **

1. Download Docker
2. Run the command `docker-compose up`

** Keycloak **

1. Access Keycloak via `http://localhost:8080/admin`
2. Sign in with username: `admin` & password: `admin`
3. Select `cyber` as the realm

** HashiCorp Vault **

1. Access HashiCorp Vault via `http://localhost:8200`
2. Sign in with the token `dev-only-token`

03/23/2025
- Created client: `test-client`
- Created user username: `martyna` & password: `123` -> can login here: `http://localhost:8080/realms/cyber/account`
- Statically generated JWT can be seen by going into Inspect -> Network -> token -> Response -> access_token
- You can use this tool (https://www.jstoolset.com/jwt) to decode JWTs
- Created user username: `eggbtr` & password: `345` -> can login here: `http://localhost:8080/realms/cyber/account`

03/30/2025
- Created `main.py` - our simple Flask app will run on localhost:5000
- Added a `Dockerfile` and refrenced it in `docker-compose.yml` - this is how our Flask app will run
  (the `Dockerfile` has instructions on how to run the Flask app; the .yml file points to it when `docker-compose up` is ran)
- Created a `venv` (for running `main.py` w/o using `docker-compose up`)

How to create a `venv` & activate it (on Windows):
1. `python -m venv venv` -> venv creation
2. `.\venv\Scripts\activate` -> venv activation
3. `pip install -r requirements.txt` -> downloading requirements to run `main.py`

04/13/2025
1. The `cyber` realm now has the Access settings configured
2. We are able to login and out using the users configured in the `cyber` realm