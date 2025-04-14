#!/bin/sh
set -e

echo "Starting import-client-secret.sh"

# Wait for Keycloak to be ready
echo "Waiting for Keycloak to be ready..."
until curl -s -f http://keycloak:8080/health/ready; do
    echo "Keycloak is not ready yet. Waiting..."
    sleep 5
done

# Wait for Vault to be ready
echo "Waiting for Vault to be ready..."
until curl -s -f http://vault:8200/v1/sys/health; do
    echo "Vault is not ready yet. Waiting..."
    sleep 5
done

# Get access token from Keycloak
echo "Getting access token from Keycloak..."
ACCESS_TOKEN=$(curl -s -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=admin-cli" \
    -d "username=admin" \
    -d "password=admin" \
    -d "grant_type=password" \
    "http://keycloak:8080/realms/master/protocol/openid-connect/token" | \
    jq -r '.access_token')

if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
    echo "Failed to get access token from Keycloak"
    exit 1
fi

# Get all clients
echo "Getting clients from Keycloak..."
CLIENTS=$(curl -s \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "http://keycloak:8080/admin/realms/cyber/clients")

# Find a client with client authentication enabled
echo "Finding client with authentication enabled..."
CLIENT_ID=$(echo "$CLIENTS" | jq -r '.[] | select(.clientAuthenticatorType == "client-secret") | .id')
if [ -z "$CLIENT_ID" ]; then
    echo "No client with client authentication enabled found"
    exit 1
fi

# Get client secret
echo "Getting client secret for client $CLIENT_ID..."
CLIENT_SECRET=$(curl -s \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "http://keycloak:8080/admin/realms/cyber/clients/$CLIENT_ID/client-secret" | \
    jq -r '.value')

if [ -z "$CLIENT_SECRET" ] || [ "$CLIENT_SECRET" = "null" ]; then
    echo "Failed to get client secret"
    exit 1
fi

# Vault configuration
VAULT_ADDR="http://vault:8200"
VAULT_TOKEN="dev-only-token"
VAULT_SECRET_PATH="secret/data/test-client"

# Store configuration in Vault
echo "Storing configuration in Vault..."
curl -s -X POST \
  -H "X-Vault-Token: $VAULT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"data\":{\"client_secret\":\"$CLIENT_SECRET\",\"client_id\":\"$CLIENT_ID\",\"realm\":\"cyber\",\"public_host\":\"localhost\",\"internal_host\":\"keycloak\"}}" \
  "$VAULT_ADDR/v1/$VAULT_SECRET_PATH"

echo "Configuration stored in Vault successfully" 