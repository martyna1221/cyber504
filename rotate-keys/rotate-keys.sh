#!/bin/sh

VAULT_ADDR="http://vault:8200"
VAULT_TOKEN="dev-only-token"
KEY_PATH="secret/data/keycloak/signing-key"

echo "[*] Rotating JWT signing key..."

PRIVATE_KEY=$(openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 | base64 | tr -d '\n')

cat <<EOF > /tmp/key.json
{
 "data": {
  "private_key": "$PRIVATE_KEY"
 }
}
EOF


curl --header "X-Vault-Token: $VAULT_TOKEN" \
     --request POST \
     --data @/tmp/key.json \
     "$VAULT_ADDR/v1/$KEY_PATH"

echo "[*] Key rotated at $(date)"
