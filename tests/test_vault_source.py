"""Tests for OPVaultSettingsSource."""

from typing import Annotated, Any

import pytest
from pydantic import AliasChoices, AliasPath, Field
from pydantic_settings import BaseSettings

from pydantic_settings_op import Client, OPField, OPVaultSettingsSource
from tests.conftest import TEST_VAULT, TEST_VAULT_ALT


def test_convention_based_resolution(op_client: Client) -> None:
    """Test that fields are resolved by convention (field_name/password)."""

    class Settings(BaseSettings):
        db_password: str

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"db_password": "secret123"}


def test_credential_fallback(op_client: Client) -> None:
    """Test that 'credential' is tried when 'password' is not found."""

    class Settings(BaseSettings):
        api_key: str

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"api_key": "api-secret"}


def test_op_field_annotation_relative(op_client: Client) -> None:
    """Test OPField with relative URI (prepends vault)."""

    class Settings(BaseSettings):
        secret: Annotated[str, OPField("db_password/password")]

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"secret": "secret123"}


def test_op_field_annotation_full_uri(op_client: Client) -> None:
    """Test OPField with full op:// URI (ignores source vault)."""

    class Settings(BaseSettings):
        api_key: Annotated[str, OPField(f"op://{TEST_VAULT_ALT}/api/key")]

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"api_key": "other-api-key"}


def test_missing_secret_returns_empty(op_client: Client) -> None:
    """Test that missing secrets are not included in results."""

    class Settings(BaseSettings):
        nonexistent_field: str = "default"

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {}


def test_non_default_field_not_found(op_client: Client) -> None:
    """Test that items with non-default field names are not resolved by convention."""

    class Settings(BaseSettings):
        signing_key: str = "default"

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {}


def test_missing_vault_raises(op_client: Client) -> None:
    """Test that a missing vault raises an error (misconfiguration, not silently ignored)."""

    class Settings(BaseSettings):
        db_password: str

    source = OPVaultSettingsSource(Settings, vault="nonexistent-vault", client=op_client)
    with pytest.raises(Exception, match="no vault matched"):
        source()


async def test_item_not_found_error_message(op_client: Client) -> None:
    """Verify the SDK's item-not-found error contains the expected phrase."""
    with pytest.raises(Exception, match="no item matched the secret reference query"):
        await op_client.secrets.resolve(f"op://{TEST_VAULT}/nonexistent-item/password")


def test_multiple_fields(op_client: Client) -> None:
    """Test resolving multiple fields."""

    class Settings(BaseSettings):
        db_password: str
        api_key: str

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {
        "db_password": "secret123",
        "api_key": "api-secret",
    }


def test_repr(op_client: Client) -> None:
    """Test string representation of source."""

    class Settings(BaseSettings):
        pass

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert repr(source) == f"OPVaultSettingsSource(vault='{TEST_VAULT}')"


def test_custom_default_fields(op_client: Client) -> None:
    """Test using custom default field names."""

    class Settings(BaseSettings):
        signing_key: str

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client, default_fields=("key",))
    assert source() == {"signing_key": "signing-secret"}


def test_client_and_auth_mutually_exclusive(op_client: Client) -> None:
    """Test that passing both client and auth raises ValueError."""

    class Settings(BaseSettings):
        db_password: str

    with pytest.raises(ValueError, match="mutually exclusive"):
        OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client, auth="token")


def test_full_settings_instantiation(op_client: Client) -> None:
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
        ) -> tuple[OPVaultSettingsSource]:
            return (OPVaultSettingsSource(settings_cls, vault=TEST_VAULT, client=op_client),)

    settings = Settings()  # pyright: ignore[reportCallIssue]
    assert settings.db_password == "secret123"


def test_alias_field_key_is_used_in_source_output(op_client: Client) -> None:
    """Alias should be used as key for model creation, not the internal field name."""

    class Settings(BaseSettings):
        db_password: str = Field(alias="DB_PASSWORD")

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"DB_PASSWORD": "secret123"}


def test_validation_alias_field_key_is_used_in_source_output(op_client: Client) -> None:
    """Validation alias should be used as key for model creation when provided."""

    class Settings(BaseSettings):
        db_password: str = Field(validation_alias="DB_PASSWORD")

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"DB_PASSWORD": "secret123"}


async def test_resolution_from_async_context(op_client: Client) -> None:
    """Test that run_sync works from an async context (exercises the thread pool executor path)."""

    class Settings(BaseSettings):
        db_password: str

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"db_password": "secret123"}


def test_full_settings_instantiation_with_alias(op_client: Client) -> None:
    """Settings instantiation should work when a field uses an alias."""

    class Settings(BaseSettings):
        db_password: str = Field(alias="DB_PASSWORD")

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: Any,
            env_settings: Any,
            dotenv_settings: Any,
            file_secret_settings: Any,
        ) -> tuple[OPVaultSettingsSource]:
            return (OPVaultSettingsSource(settings_cls, vault=TEST_VAULT, client=op_client),)

    settings = Settings()  # pyright: ignore[reportCallIssue]
    assert settings.db_password == "secret123"


def test_validation_alias_preferred_over_alias_in_source_output(op_client: Client) -> None:
    """When both are present, validation_alias should be used for input key selection."""

    class Settings(BaseSettings):
        db_password: str = Field(alias="DB_PASSWORD_SERIALIZE", validation_alias="DB_PASSWORD_INPUT")

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"DB_PASSWORD_INPUT": "secret123"}


def test_full_settings_instantiation_with_alias_and_validation_alias(op_client: Client) -> None:
    """Settings instantiation should use validation_alias when alias is also defined."""

    class Settings(BaseSettings):
        db_password: str = Field(alias="DB_PASSWORD_SERIALIZE", validation_alias="DB_PASSWORD_INPUT")

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: Any,
            env_settings: Any,
            dotenv_settings: Any,
            file_secret_settings: Any,
        ) -> tuple[OPVaultSettingsSource]:
            return (OPVaultSettingsSource(settings_cls, vault=TEST_VAULT, client=op_client),)

    settings = Settings()  # pyright: ignore[reportCallIssue]
    assert settings.db_password == "secret123"


def test_alias_choices_prefers_usable_string_alias_over_path(op_client: Client) -> None:
    """Path aliases cannot be represented as flat keys; use a string alias choice when available."""

    class Settings(BaseSettings):
        db_password: str = Field(validation_alias=AliasChoices(AliasPath("outer", "inner"), "DB_PASSWORD"))

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"DB_PASSWORD": "secret123"}


def test_alias_path_only_validation_alias_is_skipped(op_client: Client) -> None:
    """AliasPath-only validation_alias cannot be represented as a flat key — field should be skipped."""

    class Settings(BaseSettings):
        db_password: str = Field(default="fallback", validation_alias=AliasPath("outer", "inner"))

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {}


def test_single_segment_alias_path_is_used_as_flat_key(op_client: Client) -> None:
    """Single-segment AliasPath should be treated as a flat key, not skipped."""

    class Settings(BaseSettings):
        db_password: str = Field(validation_alias=AliasPath("DB_PASSWORD"))

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"DB_PASSWORD": "secret123"}


def test_alias_choices_with_single_segment_alias_path(op_client: Client) -> None:
    """AliasChoices with a single-segment AliasPath should use it as a flat key."""

    class Settings(BaseSettings):
        db_password: str = Field(validation_alias=AliasChoices(AliasPath("outer", "inner"), AliasPath("DB_PASSWORD")))

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {"DB_PASSWORD": "secret123"}


def test_alias_choices_all_paths_is_skipped(op_client: Client) -> None:
    """AliasChoices containing only AliasPath entries should be skipped (no usable flat key)."""

    class Settings(BaseSettings):
        db_password: str = Field(
            default="fallback", validation_alias=AliasChoices(AliasPath("a", "b"), AliasPath("c", "d"))
        )

    source = OPVaultSettingsSource(Settings, vault=TEST_VAULT, client=op_client)
    assert source() == {}


def test_full_settings_instantiation_with_alias_path_only(op_client: Client) -> None:
    """Settings instantiation should succeed (using default) when validation_alias is AliasPath-only."""

    class Settings(BaseSettings):
        db_password: str = Field(default="fallback", validation_alias=AliasPath("outer", "inner"))

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: Any,
            env_settings: Any,
            dotenv_settings: Any,
            file_secret_settings: Any,
        ) -> tuple[OPVaultSettingsSource]:
            return (OPVaultSettingsSource(settings_cls, vault=TEST_VAULT, client=op_client),)

    settings = Settings()  # pyright: ignore[reportCallIssue]
    assert settings.db_password == "fallback"


def test_full_settings_instantiation_with_alias_choices_path_and_string(op_client: Client) -> None:
    """Settings instantiation should succeed when AliasChoices includes a usable string alias."""

    class Settings(BaseSettings):
        db_password: str = Field(validation_alias=AliasChoices(AliasPath("outer", "inner"), "DB_PASSWORD"))

        @classmethod
        def settings_customise_sources(
            cls,
            settings_cls: type[BaseSettings],
            init_settings: Any,
            env_settings: Any,
            dotenv_settings: Any,
            file_secret_settings: Any,
        ) -> tuple[OPVaultSettingsSource]:
            return (OPVaultSettingsSource(settings_cls, vault=TEST_VAULT, client=op_client),)

    settings = Settings()  # pyright: ignore[reportCallIssue]
    assert settings.db_password == "secret123"
