# Commands

After making changes, run `mise run check` and fix issues until all pass. Then run `mise run review` (may take ~10 min) and fix any flagged items.

```bash
mise run check          # format (ruff), lint (ruff), typecheck (pyright), test (pytest)
mise run review         # codex review on uncommitted changes
pytest --integration=desktop          # real 1Password via desktop app (requires TEST_OP_ACCOUNT_NAME)
pytest --integration=service-account  # real 1Password via service account (requires TEST_OP_SA_TOKEN_URI)
```

# Architecture

Single-module library at `src/pydantic_settings_op/__init__.py`.

- **Field resolution order**: `OPField` annotation first, then convention-based lookup (`field_name/{password,credential}`). Missing items/fields return `None`; missing vaults raise (misconfiguration).
- **Protocols over concrete types**: use `Client`/`Secrets` protocols (not `onepassword` concrete classes) for type hints and test injection.
- **Sync/async bridge**: `run_sync` bridges the async `onepassword` SDK. Use `asyncio.run()` in sync contexts and thread pool executor in async contexts — never block an existing event loop.
- **Alias-aware keys**: emit alias/validation_alias/AliasChoices-aware keys so resolved secrets integrate with pydantic's aliasing.

# Style

- Python 3.12+, strict pyright, ruff with `line-length = 120`.
- Tests: async-compatible (`asyncio_mode = "auto"`).

# Testing

- Mock and real backends share expected values (`TEST_SECRETS` in `tests/conftest.py`, synced with `scripts/setup-test-vault.sh`).
- Mocks replicate real error distinctions — vault-not-found vs item/field-not-found must produce different errors matching 1Password SDK behavior.
- Use the library's own protocols (`Client`, `Secrets`) in tests — no test-specific wrapper protocols.
- Default to `MockClient` via `op_client` fixture; `--integration=desktop` or `--integration=service-account` for real 1Password.

# Releases

- **Version in pyproject.toml is static**: CI sets the real version from the tag at build time. Don't update `pyproject.toml` version for releases.
- Cut releases with `scripts/release.sh`.
