"""Tests for OPEnvironmentSettingsSource."""

from typing import Any

import pytest
from pydantic import AliasPath, Field
from pydantic_settings import BaseSettings

from pydantic_settings_op import Client, OPEnvironmentSettingsSource


def test_basic_resolution(op_client: Client, op_environment_id: str) -> None:
    """Test that fields are resolved by matching environment variable names."""

    class Settings(BaseSettings):
        db_password: str

    source = OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client)
    assert source() == {"db_password": "env-secret123"}


def test_multiple_fields(op_client: Client, op_environment_id: str) -> None:
    """Test resolving multiple fields from environment."""

    class Settings(BaseSettings):
        db_password: str
        api_key: str

    source = OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client)
    assert source() == {"db_password": "env-secret123", "api_key": "env-api-secret"}


def test_missing_variable_returns_empty(op_client: Client, op_environment_id: str) -> None:
    """Test that missing environment variables are not included in results."""

    class Settings(BaseSettings):
        nonexistent_field: str = "default"

    source = OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client)
    assert source() == {}


def test_missing_environment_raises(op_client: Client) -> None:
    """Test that a missing environment raises an error."""

    class Settings(BaseSettings):
        db_password: str

    source = OPEnvironmentSettingsSource(Settings, environment_id="nonexistent-env", client=op_client)
    with pytest.raises(Exception, match="environment not found"):
        source()


def test_client_and_auth_mutually_exclusive(op_client: Client, op_environment_id: str) -> None:
    """Test that passing both client and auth raises ValueError."""

    class Settings(BaseSettings):
        db_password: str

    with pytest.raises(ValueError, match="mutually exclusive"):
        OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client, auth="token")


def test_alias_field_key(op_client: Client, op_environment_id: str) -> None:
    """Alias should be used as key for model creation."""

    class Settings(BaseSettings):
        db_password: str = Field(alias="DB_PASSWORD")

    source = OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client)
    assert source() == {"DB_PASSWORD": "env-secret123"}


def test_validation_alias_field_key(op_client: Client, op_environment_id: str) -> None:
    """Validation alias should be used as key for model creation when provided."""

    class Settings(BaseSettings):
        db_password: str = Field(validation_alias="DB_PASSWORD")

    source = OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client)
    assert source() == {"DB_PASSWORD": "env-secret123"}


def test_alias_path_only_skipped(op_client: Client, op_environment_id: str) -> None:
    """AliasPath-only validation_alias cannot be represented as a flat key — field should be skipped."""

    class Settings(BaseSettings):
        db_password: str = Field(default="fallback", validation_alias=AliasPath("outer", "inner"))

    source = OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client)
    assert source() == {}


def test_repr(op_client: Client, op_environment_id: str) -> None:
    """Test string representation of source."""

    class Settings(BaseSettings):
        pass

    source = OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client)
    assert repr(source) == f"OPEnvironmentSettingsSource(environment_id='{op_environment_id}')"


def test_full_settings_instantiation(op_client: Client, op_environment_id: str) -> None:
    """Test that source works with full Settings instantiation."""

    class Settings(BaseSettings):
        db_password: str

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: Any,
            env_settings: Any,
            dotenv_settings: Any,
            file_secret_settings: Any,
        ) -> tuple[OPEnvironmentSettingsSource]:
            return (OPEnvironmentSettingsSource(settings_cls, environment_id=op_environment_id, client=op_client),)

    settings = Settings()  # pyright: ignore[reportCallIssue]
    assert settings.db_password == "env-secret123"


async def test_resolution_from_async_context(op_client: Client, op_environment_id: str) -> None:
    """Test that run_sync works from an async context for environment source."""

    class Settings(BaseSettings):
        db_password: str

    source = OPEnvironmentSettingsSource(Settings, environment_id=op_environment_id, client=op_client)
    assert source() == {"db_password": "env-secret123"}
