#!/bin/bash

echo "Defining variables..."
KEYCLOAK_URL="http://localhost:8080"
KEYCLOAK_REALM="master"
KEYCLOAK_USER="admin"
KEYCLOAK_SECRET="admin"
REALM_NAME="cyber"

echo "Obtaining access token..."
ACCESS_TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=${KEYCLOAK_USER}" \
  -d "password=${KEYCLOAK_SECRET}" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | jq -r '.access_token')

if [ -z "$ACCESS_TOKEN" ]; then
  echo "Failed to obtain access token"
  exit 1
fi

echo "Exporting realm..."
curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  > keycloak_${REALM_NAME}_realm.json

echo "Exporting users..."
curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/users" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  > keycloak_${REALM_NAME}_users.json

echo "Exporting roles..."
curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/roles" \
  -H "Accept: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  > keycloak_${REALM_NAME}_roles.json

echo "Combining exports..."
jq -s '.[0] + {users: .[1], roles: {"realm": .[2]}}' keycloak_${REALM_NAME}_realm.json keycloak_${REALM_NAME}_users.json keycloak_${REALM_NAME}_roles.json > realm-export.json

echo "Export complete. Files created:"
