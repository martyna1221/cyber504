#!/bin/bash
set -e

# Check if the realm has been imported by looking for a marker file
if [ ! -f /opt/keycloak/data/import_done ]; then
    echo 'Starting Keycloak with realm import...'
    # Import the realm on first run
    /opt/keycloak/bin/kc.sh start-dev --import-realm
    # Create a marker so that subsequent runs skip the import
    touch /opt/keycloak/data/import_done
else
    echo 'Realm already imported, starting Keycloak normally...'
    # Regular startup without importing realm again
    /opt/keycloak/bin/kc.sh start-dev
fi