#!/usr/bin/env bash
# Set the OP_SERVICE_ACCOUNT_TOKEN GitHub Actions secret from 1Password.
# Requires: `op` CLI authenticated, `gh` CLI authenticated with repo access.
#
# Usage: ./scripts/setup-ci-secret.sh
set -euo pipefail

TOKEN_URI="${TEST_OP_SA_TOKEN_URI:?TEST_OP_SA_TOKEN_URI must be set (e.g. in mise.local.toml)}"

echo "Reading service account token from 1Password..."
token=$(op read "$TOKEN_URI")

echo "Setting GitHub Actions secret OP_SERVICE_ACCOUNT_TOKEN..."
gh secret set OP_SERVICE_ACCOUNT_TOKEN --body "$token"

echo "Done."
