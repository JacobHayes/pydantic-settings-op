"""Pytest configuration and fixtures for pydantic-settings-op tests."""

import os
import subprocess

import pytest
from onepassword.types import EnvironmentVariable, GetVariablesResponse

from pydantic_settings_op import NOT_FOUND_MESSAGES, Client, Environments, Secrets, create_client

TEST_VAULT = "pydantic-settings-op-test"
TEST_VAULT_ALT = "pydantic-settings-op-test-alt"
MOCK_ENVIRONMENT_ID = "mock-env-id"

# NOTE: Keep in sync with scripts/setup-test-vault.sh
TEST_SECRETS: dict[str, str] = {
    f"op://{TEST_VAULT}/db_password/password": "secret123",
    f"op://{TEST_VAULT}/api_key/credential": "api-secret",
    f"op://{TEST_VAULT}/signing_key/key": "signing-secret",
    f"op://{TEST_VAULT_ALT}/api/key": "other-api-key",
}

# NOTE: Keep in sync with scripts/setup-test-vault.sh
TEST_ENVIRONMENT_VARIABLES: dict[str, dict[str, str]] = {
    MOCK_ENVIRONMENT_ID: {
        "db_password": "env-secret123",
        "api_key": "env-api-secret",
    },
}


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--integration",
        nargs="?",
        const="",
        default=None,
        metavar="{desktop,service-account}",
        help="Run tests with a real 1Password client",
    )


def pytest_configure(config: pytest.Config) -> None:
    if (mode := config.getoption("--integration", default=None)) is not None and mode not in (
        "desktop",
        "service-account",
    ):
        pytest.exit(
            "--integration requires a mode: --integration=desktop or --integration=service-account", returncode=2
        )


class MockEnvironmentsClient:
    """Mock environments client minimally matching onepassword.Environments interface."""

    def __init__(self, data: dict[str, dict[str, str]]) -> None:
        self._data = data

    async def get_variables(self, environment_id: str) -> GetVariablesResponse:
        if environment_id not in self._data:
            raise Exception(f"environment not found: {environment_id}")
        variables = [
            EnvironmentVariable(name=name, value=value, masked=True)
            for name, value in self._data[environment_id].items()
        ]
        return GetVariablesResponse(variables=variables)


class MockSecretsClient:
    """Mock secrets client minimally matching onepassword.Secrets interface."""

    def __init__(self, data: dict[str, str]) -> None:
        self._data = data
        self._vaults = {ref.split("/")[2] for ref in data}

    async def resolve(self, secret_reference: str) -> str:
        vault = secret_reference.split("/")[2]
        if vault not in self._vaults:
            raise Exception("error resolving secret reference: no vault matched the secret reference query")
        if secret_reference in self._data:
            return self._data[secret_reference]
        # Use the same phrase the production code checks for in NOT_FOUND_MESSAGES.
        raise Exception(f"{NOT_FOUND_MESSAGES[0]} for '{secret_reference}'")


class MockClient:
    """Mock 1Password client minimally matching the Client protocol."""

    def __init__(self, environment_variables: dict[str, dict[str, str]], secrets: dict[str, str]) -> None:
        self._environments = MockEnvironmentsClient(environment_variables)
        self._secrets = MockSecretsClient(secrets)

    @property
    def environments(self) -> Environments:
        return self._environments

    @property
    def secrets(self) -> Secrets:
        return self._secrets


# Verify mock client satisfies protocol. Pyright doesn't seem to check compatibility in isinstance checks, so we must
# define with an explicit expected type first.
v: Client = MockClient({}, {})
assert isinstance(v, Client)


def _setup_desktop_auth() -> None:
    if os.environ.get("OP_ACCOUNT_NAME"):
        return
    if account_name := os.environ.get("TEST_OP_ACCOUNT_NAME"):
        os.environ["OP_ACCOUNT_NAME"] = account_name
    else:
        pytest.fail("TEST_OP_ACCOUNT_NAME must be set for --integration=desktop")


def _setup_sa_token() -> None:
    if os.environ.get("OP_SERVICE_ACCOUNT_TOKEN"):
        return
    if uri := os.environ.get("TEST_OP_SA_TOKEN_URI"):
        os.environ["OP_SERVICE_ACCOUNT_TOKEN"] = subprocess.check_output(["op", "read", uri], text=True).strip()
    else:
        pytest.fail("TEST_OP_SA_TOKEN_URI must be set for --integration=service-account")


@pytest.fixture(scope="session")
def op_client(request: pytest.FixtureRequest) -> Client:
    """1Password client: mock by default, real client with --integration."""
    match request.config.getoption("--integration"):
        case "desktop":
            _setup_desktop_auth()
        case "service-account":
            _setup_sa_token()
        case _:
            return MockClient(TEST_ENVIRONMENT_VARIABLES, TEST_SECRETS)
    return create_client()


@pytest.fixture(scope="session")
def op_environment_id(request: pytest.FixtureRequest) -> str:
    """Environment ID: mock ID by default, real ID from TEST_OP_ENVIRONMENT_ID with --integration."""
    if request.config.getoption("--integration") is None:
        return MOCK_ENVIRONMENT_ID
    env_id = os.environ.get("TEST_OP_ENVIRONMENT_ID")
    if not env_id:
        pytest.skip("TEST_OP_ENVIRONMENT_ID must be set for environment integration tests")
    return env_id
