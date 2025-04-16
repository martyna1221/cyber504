#!/bin/bash
set -e

# Function to wait for Vault to be ready
wait_for_vault() {
    echo "Waiting for Vault to be ready..."
    MAX_RETRIES=10
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        echo "Attempt $((RETRY_COUNT + 1))/$MAX_RETRIES: Checking Vault..."
        
        # Check if Vault is responding
        RESPONSE=$(curl -v -s -f http://vault:8200/v1/sys/health 2>&1)
        if [ $? -eq 0 ]; then
            echo "✓ Vault is ready"
            echo "Vault health response: $RESPONSE"
            
            # Check if KV v2 engine is enabled
            echo "Checking if KV v2 engine is enabled..."
            MOUNTS_RESPONSE=$(curl -s -X GET \
                -H "X-Vault-Token: dev-only-token" \
                "http://vault:8200/v1/sys/mounts")
            
            echo "Vault mounts response: $MOUNTS_RESPONSE"
            
            if echo "$MOUNTS_RESPONSE" | grep -q "\"secret/\""; then
                echo "✓ KV v2 engine is enabled"
                
                # Verify the secret path exists
                echo "Verifying secret path exists..."
                SECRET_RESPONSE=$(curl -s -X GET \
                    -H "X-Vault-Token: dev-only-token" \
                    "http://vault:8200/v1/secret/data/test-client")
                
                if [ $? -eq 0 ]; then
                    echo "✓ Secret path exists"
                    return 0
                else
                    echo "Secret path does not exist, creating it..."
                    # Create the secret path with initial data
                    INIT_DATA="{\"data\": {\"initialized\": true}}"
                    curl -s -X POST \
                        -H "X-Vault-Token: dev-only-token" \
                        -H "Content-Type: application/json" \
                        -d "$INIT_DATA" \
                        "http://vault:8200/v1/secret/data/test-client"
                    
                    if [ $? -eq 0 ]; then
                        echo "✓ Secret path created successfully"
                        return 0
                    else
                        echo "Failed to create secret path"
                        return 1
                    fi
                fi
            else
                echo "KV v2 engine is not enabled, enabling it..."
                # Enable KV v2 engine
                ENABLE_RESPONSE=$(curl -s -X POST \
                    -H "X-Vault-Token: dev-only-token" \
                    -H "Content-Type: application/json" \
                    -d '{"type": "kv-v2"}' \
                    "http://vault:8200/v1/sys/mounts/secret")
                
                if [ $? -eq 0 ]; then
                    echo "✓ KV v2 engine enabled successfully"
                    # Create the secret path with initial data
                    INIT_DATA="{\"data\": {\"initialized\": true}}"
                    curl -s -X POST \
                        -H "X-Vault-Token: dev-only-token" \
                        -H "Content-Type: application/json" \
                        -d "$INIT_DATA" \
                        "http://vault:8200/v1/secret/data/test-client"
                    
                    if [ $? -eq 0 ]; then
                        echo "✓ Secret path created successfully"
                        return 0
                    else
                        echo "Failed to create secret path"
                        return 1
                    fi
                else
                    echo "Failed to enable KV v2 engine"
                    return 1
                fi
            fi
        fi
        
        echo "Vault is not ready yet"
        echo "Curl response: $RESPONSE"
        sleep 2
        RETRY_COUNT=$((RETRY_COUNT + 1))
    done
    
    echo "Timeout waiting for Vault to be ready"
    return 1
}

# Function to get admin token from Keycloak
get_admin_token() {
    echo "Getting admin token from Keycloak..."
    TOKEN_RESPONSE=$(curl -v -s -X POST \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "client_id=admin-cli" \
        -d "username=admin" \
        -d "password=admin" \
        -d "grant_type=password" \
        "http://localhost:8080/realms/master/protocol/openid-connect/token" 2>&1)
    
    echo "Token response: $TOKEN_RESPONSE"
    
    ACCESS_TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*' | sed 's/"access_token":"//')
    
    if [ -z "$ACCESS_TOKEN" ]; then
        echo "Failed to get admin token from Keycloak"
        return 1
    fi
    
    echo "✓ Admin token obtained"
    echo "$ACCESS_TOKEN"
    return 0
}

# Function to get client secret from Keycloak
get_client_secret() {
    local ACCESS_TOKEN=$1
    local CLIENT_ID=$2
    
    echo "Getting client secret for $CLIENT_ID..."
    SECRET_RESPONSE=$(curl -v -s -X GET \
        -H "Authorization: Bearer $ACCESS_TOKEN" \
        "http://localhost:8080/admin/realms/cyber/clients/$CLIENT_ID/client-secret" 2>&1)
    
    echo "Secret response: $SECRET_RESPONSE"
    
    CLIENT_SECRET=$(echo "$SECRET_RESPONSE" | grep -o '"value":"[^"]*' | sed 's/"value":"//')
    
    if [ -z "$CLIENT_SECRET" ]; then
        echo "Failed to get client secret from Keycloak"
        return 1
    fi
    
    echo "✓ Client secret obtained"
    echo "$CLIENT_SECRET"
    return 0
}

# Function to store secret in Vault
store_secret_in_vault() {
    local CLIENT_SECRET=$1
    local CLIENT_ID=$2
    
    echo "Storing configuration in Vault..."
    VAULT_DATA="{\"data\": {\"client_secret\": \"$CLIENT_SECRET\", \"client_id\": \"$CLIENT_ID\", \"realm\": \"cyber\", \"public_host\": \"localhost\", \"internal_host\": \"keycloak\"}}"
    echo "Vault data to be stored: $VAULT_DATA"

    # Store the secret in Vault with retries
    MAX_RETRIES=3
    RETRY_COUNT=0
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        echo "Attempting to store secret in Vault (Attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)..."
        echo "Using Vault URL: http://vault:8200/v1/secret/data/test-client"
        echo "Using Vault token: dev-only-token"
        
        VAULT_RESPONSE=$(curl -v -s -X POST \
            -H "X-Vault-Token: dev-only-token" \
            -H "Content-Type: application/json" \
            -d "$VAULT_DATA" \
            "http://vault:8200/v1/secret/data/test-client" 2>&1)
        
        CURL_EXIT_CODE=$?
        echo "Vault response: $VAULT_RESPONSE"
        echo "Curl exit code: $CURL_EXIT_CODE"
        
        if [ $CURL_EXIT_CODE -eq 0 ] && echo "$VAULT_RESPONSE" | grep -q "request_id"; then
            echo "Successfully stored secret in Vault"
            
            # Verify the secret was stored correctly
            echo "Verifying secret was stored correctly..."
            VERIFY_RESPONSE=$(curl -v -s -X GET \
                -H "X-Vault-Token: dev-only-token" \
                "http://vault:8200/v1/secret/data/test-client" 2>&1)
            
            echo "Verify response: $VERIFY_RESPONSE"
            
            if [ $? -eq 0 ]; then
                echo "✓ Secret verified in Vault"
                echo "Stored data:"
                echo "$VERIFY_RESPONSE" | jq '.'
                
                # Verify all required fields are present
                REQUIRED_FIELDS=("client_secret" "client_id" "realm" "public_host" "internal_host")
                for field in "${REQUIRED_FIELDS[@]}"; do
                    if ! echo "$VERIFY_RESPONSE" | grep -q "\"$field\""; then
                        echo "Error: Required field '$field' is missing from stored secret"
                        return 1
                    fi
                done
                
                return 0
            else
                echo "Secret verification failed"
                echo "Verify response: $VERIFY_RESPONSE"
            fi
        else
            echo "Failed to store secret in Vault (curl exit code: $CURL_EXIT_CODE)"
            echo "Response: $VAULT_RESPONSE"
        fi
        
        sleep 2
        RETRY_COUNT=$((RETRY_COUNT + 1))
    done

    echo "Failed to store secret in Vault after $MAX_RETRIES attempts"
    return 1
}

# Function to import secrets
import_secrets() {
    echo "Starting secret import process..."
    
    # Wait for Vault to be ready first
    if ! wait_for_vault; then
        echo "Failed to connect to Vault"
        return 1
    fi
    
    # Wait for Keycloak to be ready
    echo "Waiting for Keycloak to be ready..."
    MAX_RETRIES=10
    RETRY_COUNT=0
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        echo "Attempt $((RETRY_COUNT + 1))/$MAX_RETRIES: Checking Keycloak..."
        
        # Check if Keycloak is responding
        echo "1. Checking if Keycloak is responding..."
        RESPONSE=$(curl -v -s -f http://localhost:8080/health/ready 2>&1)
        if [ $? -ne 0 ]; then
            echo "Keycloak is not responding yet"
            echo "Curl response: $RESPONSE"
            sleep 2
            RETRY_COUNT=$((RETRY_COUNT + 1))
            continue
        fi
        echo "✓ Keycloak is responding"
        
        # Get admin token
        ADMIN_TOKEN=$(get_admin_token)
        if [ $? -ne 0 ]; then
            echo "Failed to get admin token"
            sleep 2
            RETRY_COUNT=$((RETRY_COUNT + 1))
            continue
        fi
        
        # Get all clients from the realm
        echo "Getting all clients from Keycloak..."
        CLIENTS_RESPONSE=$(curl -v -s -X GET \
            -H "Authorization: Bearer $ADMIN_TOKEN" \
            "http://localhost:8080/admin/realms/cyber/clients" 2>&1)
        
        echo "Clients response: $CLIENTS_RESPONSE"
        
        # Get the test-client ID
        CLIENT_ID=$(echo "$CLIENTS_RESPONSE" | grep -o '"id":"[^"]*","clientId":"test-client"' | grep -o '"id":"[^"]*' | sed 's/"id":"//')
        
        if [ -z "$CLIENT_ID" ]; then
            echo "Failed to find test-client"
            sleep 2
            RETRY_COUNT=$((RETRY_COUNT + 1))
            continue
        fi
        
        echo "Found test-client with ID: $CLIENT_ID"
        
        # Get client secret
        CLIENT_SECRET=$(get_client_secret "$ADMIN_TOKEN" "$CLIENT_ID")
        if [ $? -ne 0 ]; then
            echo "Failed to get client secret"
            sleep 2
            RETRY_COUNT=$((RETRY_COUNT + 1))
            continue
        fi
        
        # Store secret in Vault
        if store_secret_in_vault "$CLIENT_SECRET" "test-client"; then
            echo "✓ Secret import process completed successfully"
            return 0
        else
            echo "Failed to store secret in Vault"
            sleep 2
            RETRY_COUNT=$((RETRY_COUNT + 1))
        fi
    done
    
    echo "Failed to import secrets after $MAX_RETRIES attempts"
    return 1
}

# Check if the realm has been imported by looking for a marker file
if [ ! -f /opt/keycloak/data/import_done ]; then
    echo 'Starting Keycloak with realm import...'
    # Import the realm on first run
    /opt/keycloak/bin/kc.sh start-dev --import-realm &
    # Wait for Keycloak to start
    sleep 10
    # Import secrets
    import_secrets
    # Create a marker so that subsequent runs skip the import
    touch /opt/keycloak/data/import_done
    # Stop Keycloak after importing
    pkill -f "kc.sh"
else
    echo 'Realm already imported, starting Keycloak normally...'
    # Regular startup without importing realm again
    /opt/keycloak/bin/kc.sh start-dev
fi