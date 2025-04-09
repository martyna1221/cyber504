#!/bin/bash

VAULT_ADDR="http://vault:8200"
VAULT_TOKEN="dev-only-token"
KEY_PATH="secret/data/keycloak/signing-key"
OUTPUT_PATH="/keys/key.pem"

echo "[*] Syncing signing key from Vault..."

# Fetch private key
PRIVATE_KEY=$(curl -s \
  --header "X-Vault-Token: $VAULT_TOKEN" \
  "$VAULT_ADDR/v1/$KEY_PATH" | jq -r '.data.data.private_key')

# Decode and save it
echo "$PRIVATE_KEY" | base64 -d > "$OUTPUT_PATH"

echo "[*] Key synced to $OUTPUT_PATH at $(date)"
