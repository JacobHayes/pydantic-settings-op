# pydantic-settings-op

[![PyPI version](https://img.shields.io/pypi/v/pydantic-settings-op)](https://pypi.org/project/pydantic-settings-op/)
[![Python versions](https://img.shields.io/pypi/pyversions/pydantic-settings-op)](https://pypi.org/project/pydantic-settings-op/)
[![License](https://img.shields.io/pypi/l/pydantic-settings-op)](https://github.com/JacobHayes/pydantic-settings-op/blob/main/LICENSE)

A [1Password](https://1password.com/) secrets source for [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/).

## Installation

```bash
pip install pydantic-settings-op
```

## Usage

```python
from pydantic_settings import BaseSettings

from pydantic_settings_op import OPVaultSettingsSource


class Settings(BaseSettings):
    db_password: str
    api_key: str

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        return (init_settings, env_settings, OPVaultSettingsSource(settings_cls, vault="MyVault"))

settings = Settings()
```

By convention, each field name is used as the 1Password item name within the configured vault, trying `password` then `credential` as the field name (configurable via `default_fields`).

### Explicit field references with `OPField`

For fields that don't follow the convention, use `OPField` to specify an explicit secret reference:

```python
from typing import Annotated

from pydantic_settings_op import OPField

class Settings(BaseSettings):
    # Relative path — vault from OPVaultSettingsSource is prepended
    db_password: Annotated[str, OPField("database/password")]

    # Full URI — uses the specified vault, ignoring the source vault
    api_key: Annotated[str, OPField("op://other-vault/api/key")]
```

### Authentication

Authentication is resolved in order:

1. Explicit `auth` parameter (a [service account](https://developer.1password.com/docs/service-accounts/get-started/) token string or [`DesktopAuth`](https://developer.1password.com/docs/sdks/desktop-app-integrations/) instance)
2. `OP_SERVICE_ACCOUNT_TOKEN` environment variable
3. `OP_ACCOUNT_NAME` environment variable (uses `DesktopAuth`)

You can also pass a pre-configured `client` directly instead of using `auth`.

### Aliases

The source respects pydantic's `alias`, `validation_alias`, and `AliasChoices` when emitting keys, so resolved secrets integrate with your existing alias configuration.
