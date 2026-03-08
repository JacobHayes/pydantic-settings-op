"""1Password secrets source for pydantic-settings."""

import asyncio
import atexit
import concurrent.futures
import os
from collections.abc import Coroutine
from dataclasses import dataclass
from importlib.metadata import version
from typing import Any, Protocol, runtime_checkable

import onepassword
from onepassword.client import DesktopAuth
from pydantic import AliasPath
from pydantic.fields import FieldInfo
from pydantic_settings.main import BaseSettings
from pydantic_settings.sources.base import PydanticBaseSettingsSource

__all__ = ["DesktopAuth", "OPField", "OPVaultSettingsSource"]

# ---------------------------------------------------------------------------
# Types & protocols
# ---------------------------------------------------------------------------

Auth = str | DesktopAuth


class Secrets(Protocol):
    """Protocol matching onepassword.Secrets interface."""

    def resolve(self, secret_reference: str) -> Coroutine[Any, Any, str]: ...


@runtime_checkable
class Client(Protocol):
    """Protocol matching onepassword.Client interface."""

    @property
    def secrets(self) -> Secrets: ...


@dataclass(frozen=True, slots=True)
class OPField:
    """Annotation to specify explicit 1Password URI for a field.

    The URI can be either:
    - A relative path like "item/field" (vault from source config will be prepended)
    - A full URI like "op://vault/item/field" (uses specified vault, ignores source vault)

    Example:
        class Settings(BaseSettings):
            # Uses source vault, item "database", field "password"
            db_password: Annotated[str, OPField("database/password")]

            # Uses explicit vault "other-vault"
            api_key: Annotated[str, OPField("op://other-vault/api/key")]
    """

    uri: str


# ---------------------------------------------------------------------------
# Sync execution helper
# ---------------------------------------------------------------------------

_executor: concurrent.futures.ThreadPoolExecutor | None = None


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        atexit.register(_executor.shutdown, wait=False)
    return _executor


def run_sync[T](coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine synchronously.

    If called from a sync context (no running event loop), uses asyncio.run().
    If called from an async context, runs in a thread pool to avoid blocking.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    future = _get_executor().submit(asyncio.run, coro)
    return future.result()


# ---------------------------------------------------------------------------
# Client construction
# ---------------------------------------------------------------------------


def resolve_auth(auth: Auth | None) -> Auth:
    """Resolve authentication from explicit value or environment variables.

    Resolution order:
    1. If auth is provided, use it directly.
    2. Check OP_SERVICE_ACCOUNT_TOKEN env var.
    3. Check OP_ACCOUNT_NAME env var (uses DesktopAuth).
    4. Raise ValueError.
    """
    if auth is not None:
        return auth

    if token := os.environ.get("OP_SERVICE_ACCOUNT_TOKEN"):
        return token

    if account_name := os.environ.get("OP_ACCOUNT_NAME"):
        return DesktopAuth(account_name=account_name)

    raise ValueError(
        "No authentication provided. Either pass 'auth' parameter, "
        "set OP_SERVICE_ACCOUNT_TOKEN, or set OP_ACCOUNT_NAME environment variable."
    )


async def _create_client_async(
    auth: Auth | None = None,
    integration_name: str = "pydantic-settings-op",
    integration_version: str | None = None,
) -> onepassword.Client:
    """Create a 1Password client with the given authentication.

    Args:
        auth: Authentication credential. A service account token string, a DesktopAuth
            instance, or None to auto-detect from environment variables.
        integration_name: Name of the integration for 1Password logging.
        integration_version: Version of the integration.

    Returns:
        Authenticated 1Password client.

    Raises:
        ValueError: If no authentication can be resolved.
    """
    return await onepassword.Client.authenticate(
        auth=resolve_auth(auth),
        integration_name=integration_name,
        integration_version=integration_version or version("pydantic-settings-op"),
    )


def create_client(
    auth: Auth | None = None, integration_name: str = "pydantic-settings-op", integration_version: str | None = None
) -> onepassword.Client:
    """Create a 1Password client synchronously."""
    return run_sync(_create_client_async(auth, integration_name, integration_version))


# ---------------------------------------------------------------------------
# Settings source
# ---------------------------------------------------------------------------

# Error messages from the 1Password SDK (Rust core via FFI) for missing secrets.
# Vault-not-found errors are intentionally excluded — a missing vault is misconfiguration.
NOT_FOUND_MESSAGES = (
    "no item matched the secret reference query",
    "no section matched the secret reference",
    "the specified field cannot be found within the item",
)


class OPVaultSettingsSource(PydanticBaseSettingsSource):
    """Settings source that reads secrets from a 1Password Vault.

    Resolution order for each pydantic field:
    1. Annotated override: `Annotated[str, OPField("op://vault/item/field")]` or `Annotated[str, OPField("item/field")]`
    2. Convention-based: field name -> item name, tries "password" then "credential" fields

    Example:
        class Settings(BaseSettings):
            db_password: str

            @classmethod
            def settings_customise_sources(
                cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
            ):
                return (init_settings, env_settings, OPVaultSettingsSource(settings_cls, vault="MyApp"))
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        vault: str,
        *,
        client: Client | None = None,
        auth: Auth | None = None,
        default_fields: tuple[str, ...] = ("password", "credential"),
    ) -> None:
        """Initialize the 1Password Vault settings source.

        Args:
            settings_cls: The Settings class.
            vault: The 1Password vault name or ID.
            client: Pre-configured 1Password client. Mutually exclusive with auth.
            auth: Authentication credential — a service account token string, a DesktopAuth
                instance, or None to auto-detect from env vars. Mutually exclusive with client.
            default_fields: Field names to try within items when no explicit OPField is set.

        Raises:
            ValueError: If both client and auth are provided.
        """
        if client is not None and auth is not None:
            raise ValueError("'client' and 'auth' are mutually exclusive.")
        super().__init__(settings_cls)
        self.vault = vault
        self._client = client
        self._auth = auth
        self.default_fields = default_fields
        self._secrets_cache: dict[str, str] = {}

    def _get_client(self) -> Client:
        if self._client is None:
            self._client = create_client(self._auth)
        return self._client

    def _get_op_field_annotation(self, field_info: FieldInfo) -> OPField | None:
        """Extract OPField annotation from a field if present."""
        for metadata in field_info.metadata:
            if isinstance(metadata, OPField):
                return metadata
        return None

    def _resolve_uri(self, uri: str) -> str:
        """Resolve a potentially relative URI to a full op:// URI."""
        if uri.startswith("op://"):
            return uri
        return f"op://{self.vault}/{uri}"

    def _resolve_secret(self, uri: str) -> str:
        """Resolve a secret from 1Password, with caching."""
        if uri not in self._secrets_cache:
            client = self._get_client()
            self._secrets_cache[uri] = run_sync(client.secrets.resolve(uri))
        return self._secrets_cache[uri]

    def _try_resolve_secret(self, uri: str) -> str | None:
        """Try to resolve a secret, returning None if not found.

        Only catches item/section/field-not-found errors. Other errors (auth, network,
        vault-not-found, etc.) propagate since they indicate misconfiguration.
        """
        try:
            return self._resolve_secret(uri)
        except Exception as e:
            error_msg = str(e).lower()
            if any(phrase in error_msg for phrase in NOT_FOUND_MESSAGES):
                return None
            raise

    def _preferred_field_key(self, field: FieldInfo, field_name: str) -> str | None:
        """Return the alias-aware key expected during model construction, or None if no flat key is usable.

        Returns None when validation_alias is set but contains only multi-segment AliasPath entries —
        this source emits flat key/value mappings, so multi-segment path aliases cannot be represented.
        Single-segment AliasPath entries (e.g. AliasPath("KEY")) are treated as flat keys.
        """
        # When validation_alias is set, pydantic ignores alias and field_name for input,
        # so we must only consider the validation_alias itself.
        if field.validation_alias is not None:
            if isinstance(field.validation_alias, str):
                return field.validation_alias
            if isinstance(field.validation_alias, AliasPath):
                # Single-segment AliasPath (e.g. AliasPath("KEY")) is a flat key pydantic can consume.
                if len(field.validation_alias.path) == 1 and isinstance(field.validation_alias.path[0], str):
                    return field.validation_alias.path[0]
                return None
            for choice in field.validation_alias.choices:
                if isinstance(choice, str):
                    return choice
                if len(choice.path) == 1 and isinstance(choice.path[0], str):
                    return choice.path[0]
            # AliasChoices with only multi-segment AliasPath entries — no usable flat key.
            return None

        if isinstance(field.alias, str):
            return field.alias

        return field_name

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        """Resolve a single field's value from 1Password."""
        is_complex = self.field_is_complex(field)
        field_key = self._preferred_field_key(field, field_name)

        # If no flat key is usable (e.g. AliasPath-only validation_alias), skip resolution
        # entirely — we cannot emit a value that pydantic would accept.
        if field_key is None:
            return None, field_name, is_complex

        op_field = self._get_op_field_annotation(field)

        if op_field:
            uri = self._resolve_uri(op_field.uri)
            value = self._try_resolve_secret(uri)
            if value is not None:
                return value, field_key, is_complex
        else:
            for default_field in self.default_fields:
                uri = self._resolve_uri(f"{field_name}/{default_field}")
                value = self._try_resolve_secret(uri)
                if value is not None:
                    return value, field_key, is_complex

        return None, field_key, is_complex

    def __call__(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for field_name, field_info in self.settings_cls.model_fields.items():
            value, field_key, value_is_complex = self.get_field_value(field_info, field_name)
            value = self.prepare_field_value(field_name, field_info, value, value_is_complex)
            if value is not None:
                d[field_key] = value
        return d

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(vault={self.vault!r})"
