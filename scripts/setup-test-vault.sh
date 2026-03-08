#!/usr/bin/env bash
# Create 1Password test vaults and populate them with test secrets.
# Requires: `op` CLI authenticated (https://developer.1password.com/docs/cli)
#
# Usage: ./scripts/setup-test-vault.sh
#
# NOTE: 1Password Environments must be created manually via the desktop app
# (Developer > View Environments > New environment). See the "Environment setup"
# section below for required variables. Set TEST_OP_ENVIRONMENT_ID to the
# environment ID after creation.
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

# ---------------------------------------------------------------------------
# Environment setup (manual — Environments cannot be created via CLI/SDK)
# ---------------------------------------------------------------------------
# Create an Environment in the 1Password desktop app with these variables:
#
#   db_password = env-secret123
#   api_key     = env-api-secret
#
# Then copy the environment ID (Manage environment > Copy environment ID) and
# set TEST_OP_ENVIRONMENT_ID before running integration tests.
# ---------------------------------------------------------------------------

echo ""
echo "Done."
echo ""
echo "Vault tests:       pytest --integration=desktop (or service-account)"
echo "Environment tests: also requires TEST_OP_ENVIRONMENT_ID (see script comments)"
