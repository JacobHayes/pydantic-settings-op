#!/usr/bin/env bash
# Create 1Password test vaults and populate them with test secrets.
# Requires: `op` CLI authenticated (https://developer.1password.com/docs/cli)
#
# Usage: ./scripts/setup-test-vault.sh
set -euo pipefail

VAULT="pydantic-settings-op-test"
VAULT_ALT="pydantic-settings-op-test-alt"

echo "Creating vaults..."
op vault create "$VAULT" --description "Test vault for pydantic-settings-op" 2>/dev/null || echo "  $VAULT already exists"
op vault create "$VAULT_ALT" --description "Alt test vault for pydantic-settings-op" 2>/dev/null || echo "  $VAULT_ALT already exists"

create_item() {
  local vault="$1" item="$2" field_label="$3" field_value="$4"
  echo "  $vault/$item/$field_label"
  op item create --vault "$vault" --title "$item" --category "Secure Note" \
    "${field_label}=${field_value}" 2>/dev/null ||
    op item edit "$item" --vault "$vault" "${field_label}=${field_value}" 2>/dev/null ||
    echo "    WARNING: could not create or update $vault/$item"
}

echo "Creating secrets..."
create_item "$VAULT" "db_password" "password" "secret123"
create_item "$VAULT" "api_key" "credential" "api-secret"
create_item "$VAULT" "signing_key" "key" "signing-secret"
create_item "$VAULT_ALT" "api" "key" "other-api-key"

echo "Done. Run tests with: pytest --integration"
