"""Google OAuth credentials: the saved token, its refresh and first authorization."""

import logging
from pathlib import Path
from typing import Final

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError

from foxhole_stockpiles.connectors.credentials_unavailable_error import (
    CredentialsUnavailableError,
)
from foxhole_stockpiles.core.utils import write_private_file

logger = logging.getLogger(__name__)

# How long the browser authorization may stay unanswered.
OAUTH_TIMEOUT_SECONDS: Final[int] = 300

_DEFAULT_TOKEN_FILE: Final[str] = "~/.fs_token"


class GoogleCredentialsProvider:
    """Provides valid Google credentials, refreshing or authorizing as needed."""

    def __init__(
        self, creds_path: str | None, scopes: list[str], token_path: Path | None = None
    ) -> None:
        """Initialize the provider.

        Args:
            creds_path (str | None): Path to the OAuth client secrets file.
            scopes (list[str]): The OAuth scopes needed.
            token_path (Path | None): The saved token location. Defaults to
                ``~/.fs_token``.
        """
        self._creds_path = creds_path
        self._scopes = scopes
        self._token_path = token_path or Path(_DEFAULT_TOKEN_FILE).expanduser()

    def load(self) -> Credentials:
        """Get credentials ready to use.

        This blocks on the network and possibly on the user, so call it off the
        event loop.

        Returns:
            Credentials: Valid credentials.

        Raises:
            CredentialsUnavailableError: If no usable credentials can be obtained.
        """
        saved = self._read_saved_token()
        if saved is not None and saved.valid:
            return saved

        creds = self._refreshed(saved) or self._authorize()

        # The file holds a live OAuth refresh token.
        write_private_file(
            path=self._token_path,
            content=creds.to_json(),  # type: ignore[no-untyped-call]
        )
        return creds

    def _read_saved_token(self) -> Credentials | None:
        """Read the saved token file, treating an unreadable one as missing.

        Returns:
            Credentials | None: The saved credentials, or None if there are none.
        """
        if not self._token_path.exists():
            return None
        try:
            saved: Credentials = Credentials.from_authorized_user_file(  # type: ignore[no-untyped-call]
                str(self._token_path), self._scopes
            )
        except ValueError as e:
            logger.warning("Ignoring an unreadable Google token file: %s", e)
            return None
        return saved

    @staticmethod
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

    def _authorize(self) -> Credentials:
        """Ask the user to authorize the application in the browser.

        Returns:
            Credentials: The newly authorized credentials.

        Raises:
            CredentialsUnavailableError: If there is no client secrets file or the
                authorization was not completed in time.
        """
        if not self._creds_path or not Path(self._creds_path).exists():
            raise CredentialsUnavailableError("Credentials missing")

        flow = InstalledAppFlow.from_client_secrets_file(self._creds_path, self._scopes)
        try:
            creds: Credentials = flow.run_local_server(
                port=0, timeout_seconds=OAUTH_TIMEOUT_SECONDS
            )
        except WSGITimeoutError as e:
            raise CredentialsUnavailableError("Credentials invalid or authorization failed") from e
        return creds
