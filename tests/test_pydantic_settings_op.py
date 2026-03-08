"""Tests for resolve_auth and shared client construction."""

import pytest
from onepassword.client import DesktopAuth

from pydantic_settings_op import resolve_auth


def test_resolve_auth_explicit_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit token string is returned as-is, ignoring env vars."""
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "env-token")
    assert resolve_auth("explicit-token") == "explicit-token"


def test_resolve_auth_explicit_desktop_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit DesktopAuth is returned as-is, ignoring env vars."""
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "env-token")
    auth = DesktopAuth(account_name="my-account")
    assert resolve_auth(auth) is auth


def test_resolve_auth_fallback_to_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falls back to OP_SERVICE_ACCOUNT_TOKEN when no explicit auth."""
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.delenv("OP_ACCOUNT_NAME", raising=False)
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "env-token")
    assert resolve_auth(None) == "env-token"


def test_resolve_auth_fallback_to_desktop_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Falls back to OP_ACCOUNT_NAME (DesktopAuth) when no token."""
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.setenv("OP_ACCOUNT_NAME", "my-account")
    result = resolve_auth(None)
    assert isinstance(result, DesktopAuth)
    assert result.account_name == "my-account"


def test_resolve_auth_token_env_takes_priority(monkeypatch: pytest.MonkeyPatch) -> None:
    """OP_SERVICE_ACCOUNT_TOKEN takes priority over OP_ACCOUNT_NAME."""
    monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "env-token")
    monkeypatch.setenv("OP_ACCOUNT_NAME", "my-account")
    assert resolve_auth(None) == "env-token"


def test_resolve_auth_no_auth_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raises ValueError when no auth is available."""
    monkeypatch.delenv("OP_SERVICE_ACCOUNT_TOKEN", raising=False)
    monkeypatch.delenv("OP_ACCOUNT_NAME", raising=False)
    with pytest.raises(ValueError, match="No authentication provided"):
        resolve_auth(None)
