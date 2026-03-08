# Contributing

## Setup

```bash
mise trust
mise install
```

## Checks

```bash
mise run check  # format, lint, typecheck, test
```

## Integration tests

Tests run against a mock 1Password client by default. To run against a real account:

1. Install and authenticate the [1Password CLI](https://developer.1password.com/docs/cli/get-started/).
2. Create the test vaults and secrets:
   ```bash
   ./scripts/setup-test-vault.sh
   ```
3. Set up auth for one or both methods:

   - **Service account**: [Create a service account](https://developer.1password.com/docs/service-accounts/get-started/) on 1password.com (Developer > Directory > Service Account), grant it access to the test vaults, and save the token to 1Password.
   - **Desktop app**: [Enable SDK integration](https://developer.1password.com/docs/sdks/desktop-app-integrations/) in the 1Password desktop app. Your account name is shown in Settings > Accounts.

4. Configure credentials in `mise.local.toml` (git-ignored):
   ```toml
   [env]
   TEST_OP_ACCOUNT_NAME = "..."
   TEST_OP_SA_TOKEN_URI = "op://vault/item/credential"  # where you saved the SA token
   ```

5. Run with the `--integration` flag:
   ```bash
   pytest --integration=desktop
   pytest --integration=service-account
   ```
