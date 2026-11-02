"""Google OAuth credentials: the saved token, its refresh and first authorization."""

import logging
from pathlib import Path
from typing import Final

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError

from foxhole_stockpiles.core.utils import write_private_file

logger = logging.getLogger(__name__)

# How long the browser authorization may stay unanswered.
OAUTH_TIMEOUT_SECONDS: Final[int] = 300

_DEFAULT_TOKEN_FILE: Final[str] = "~/.fs_token"


class CredentialsUnavailableError(RuntimeError):
    """Raised when no usable Google credentials can be obtained."""


def _read_saved_token(token_path: Path, scopes: list[str]) -> Credentials | None:
    """Read the saved token file, treating an unreadable one as missing.

    Args:
        token_path (Path): The token file location.
        scopes (list[str]): The OAuth scopes the token must cover.

    Returns:
        Credentials | None: The saved credentials, or None if there are none.
    """
    if not token_path.exists():
        return None
    try:
        saved: Credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
            str(token_path), scopes
        )
    except ValueError as e:
        logger.warning("Ignoring an unreadable Google token file: %s", e)
        return None
    return saved


def _refreshed(creds: Credentials | None) -> Credentials | None:
    """Try to renew expired credentials.

    Args:
        creds (Credentials | None): The saved credentials, if any.

    Returns:
        Credentials | None: The renewed credentials, or None if they cannot be
            renewed or Google rejected them.
    """
    if creds is None or not creds.expired or not creds.refresh_token:
        return None
    try:
        creds.refresh(Request())  # type: ignore[no-untyped-call]
    except RefreshError as e:
        logger.warning("Google rejected the saved token, authorizing again: %s", e)
        return None
    return creds


def _authorize(creds_path: str | None, scopes: list[str]) -> Credentials:
    """Ask the user to authorize the application in the browser.

    Args:
        creds_path (str | None): Path to the OAuth client secrets file.
        scopes (list[str]): The OAuth scopes to request.

    Returns:
        Credentials: The newly authorized credentials.

    Raises:
        CredentialsUnavailableError: If there is no client secrets file or the
            authorization was not completed in time.
    """
    if not creds_path or not Path(creds_path).exists():
        raise CredentialsUnavailableError("Credentials missing")

    flow = InstalledAppFlow.from_client_secrets_file(creds_path, scopes)
    try:
        creds: Credentials = flow.run_local_server(port=0, timeout_seconds=OAUTH_TIMEOUT_SECONDS)
    except WSGITimeoutError as e:
        raise CredentialsUnavailableError("Credentials invalid or authorization failed") from e
    return creds


def load_google_credentials(
    creds_path: str | None, scopes: list[str], token_path: Path | None = None
) -> Credentials:
    """Get valid credentials, refreshing or authorizing as needed.

    This blocks on the network and possibly on the user, so call it off the event
    loop.

    Args:
        creds_path (str | None): Path to the OAuth client secrets file.
        scopes (list[str]): The OAuth scopes needed.
        token_path (Path | None): The saved token location. Defaults to
            ``~/.fs_token``.

    Returns:
        Credentials: Credentials ready to use.

    Raises:
        CredentialsUnavailableError: If no usable credentials can be obtained.
    """
    path = token_path or Path(_DEFAULT_TOKEN_FILE).expanduser()

    saved = _read_saved_token(token_path=path, scopes=scopes)
    if saved is not None and saved.valid:
        return saved

    creds = _refreshed(saved) or _authorize(creds_path=creds_path, scopes=scopes)

    # The file holds a live OAuth refresh token.
    write_private_file(path=path, content=creds.to_json())  # type: ignore[no-untyped-call]
    return creds
