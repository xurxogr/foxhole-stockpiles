"""Tests for connectors.google_credentials module."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import WSGITimeoutError

from foxhole_stockpiles.connectors import google_credentials as module
from foxhole_stockpiles.connectors.credentials_unavailable_error import (
    CredentialsUnavailableError,
)
from foxhole_stockpiles.connectors.google_credentials import (
    OAUTH_TIMEOUT_SECONDS,
    GoogleCredentialsProvider,
)

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _saved(*, valid: bool, expired: bool = False, refresh_token: str | None = None) -> MagicMock:
    """Build a stand-in for credentials read from the token file.

    Args:
        valid (bool): Whether the credentials can be used as they are.
        expired (bool): Whether they have expired.
        refresh_token (str | None): The refresh token they hold.

    Returns:
        MagicMock: The fake credentials.
    """
    creds = MagicMock(valid=valid, expired=expired, refresh_token=refresh_token)
    creds.to_json.return_value = json.dumps({"token": "t"})
    return creds


@pytest.fixture
def token_path(tmp_path: Path) -> Path:
    """Return a token file location that already exists on disk."""
    path = tmp_path / "token"
    path.write_text("{}", encoding="utf-8")
    return path


def test_valid_saved_token_is_used_as_is(token_path: Path) -> None:
    """Credentials that are still valid need neither a refresh nor a browser."""
    creds = _saved(valid=True)
    with patch.object(module.Credentials, "from_authorized_user_file", return_value=creds):
        assert (
            GoogleCredentialsProvider(creds_path=None, scopes=_SCOPES, token_path=token_path).load()
            is creds
        )
    creds.refresh.assert_not_called()


def test_expired_token_is_refreshed_and_saved(token_path: Path) -> None:
    """An expired token with a refresh token is renewed and written back."""
    creds = _saved(valid=False, expired=True, refresh_token="r")
    with patch.object(module.Credentials, "from_authorized_user_file", return_value=creds):
        assert (
            GoogleCredentialsProvider(creds_path=None, scopes=_SCOPES, token_path=token_path).load()
            is creds
        )
    creds.refresh.assert_called_once()
    assert json.loads(token_path.read_text(encoding="utf-8")) == {"token": "t"}


def test_revoked_token_falls_back_to_authorizing_again(token_path: Path, tmp_path: Path) -> None:
    """A refresh token Google rejects triggers a new authorization."""
    creds = _saved(valid=False, expired=True, refresh_token="r")
    creds.refresh.side_effect = RefreshError("revoked")
    fresh = _saved(valid=True)
    client_secrets = tmp_path / "client.json"
    client_secrets.write_text("{}", encoding="utf-8")
    flow = MagicMock()
    flow.run_local_server.return_value = fresh

    with (
        patch.object(module.Credentials, "from_authorized_user_file", return_value=creds),
        patch.object(module.InstalledAppFlow, "from_client_secrets_file", return_value=flow),
    ):
        result = GoogleCredentialsProvider(
            creds_path=str(client_secrets), scopes=_SCOPES, token_path=token_path
        ).load()

    assert result is fresh
    flow.run_local_server.assert_called_once_with(port=0, timeout_seconds=OAUTH_TIMEOUT_SECONDS)


def test_corrupt_token_file_is_ignored(token_path: Path) -> None:
    """A token file that cannot be parsed behaves like a missing one."""
    with (
        patch.object(
            module.Credentials, "from_authorized_user_file", side_effect=ValueError("bad")
        ),
        pytest.raises(CredentialsUnavailableError, match="Credentials missing"),
    ):
        GoogleCredentialsProvider(creds_path=None, scopes=_SCOPES, token_path=token_path).load()


def test_missing_client_secrets_is_reported(tmp_path: Path) -> None:
    """Without a saved token or a client secrets file nothing can authorize."""
    with pytest.raises(CredentialsUnavailableError, match="Credentials missing"):
        GoogleCredentialsProvider(
            creds_path=str(tmp_path / "nope.json"), scopes=_SCOPES, token_path=tmp_path / "token"
        ).load()


def test_abandoned_authorization_times_out(tmp_path: Path) -> None:
    """Closing the browser reports a failure instead of waiting forever."""
    client_secrets = tmp_path / "client.json"
    client_secrets.write_text("{}", encoding="utf-8")
    flow = MagicMock()
    flow.run_local_server.side_effect = WSGITimeoutError("timed out")

    with (
        patch.object(module.InstalledAppFlow, "from_client_secrets_file", return_value=flow),
        pytest.raises(CredentialsUnavailableError, match="authorization failed"),
    ):
        GoogleCredentialsProvider(
            creds_path=str(client_secrets), scopes=_SCOPES, token_path=tmp_path / "token"
        ).load()
