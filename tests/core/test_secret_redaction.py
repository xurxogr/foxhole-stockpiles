"""Secrets must stay out of validation errors, reprs and logs."""

import io
import logging
from collections.abc import Iterator

import httpx
import pytest
from pydantic import ValidationError

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import AppSettings
from foxhole_stockpiles.core.settings.sections.logging import LoggingSettings
from foxhole_stockpiles.core.settings.sections.output import WebhookHandlerSettings

_TOKEN = "SUPERSECRET-TOKEN"
_SECRET_PATH = "SECRET-PATH"
_OAUTH_LOGGERS = ("requests_oauthlib", "oauthlib")


@pytest.fixture
def restore_logging() -> Iterator[None]:
    """Put the root handlers and the quietened levels back after a test changes them."""
    root = logging.getLogger()
    quiet_loggers = [logging.getLogger(name) for name in ("httpx", *_OAUTH_LOGGERS)]
    handlers = list(root.handlers)
    root_level = root.level
    quiet_levels = [logger.level for logger in quiet_loggers]
    yield
    root.handlers[:] = handlers
    root.setLevel(root_level)
    for logger, level in zip(quiet_loggers, quiet_levels, strict=True):
        logger.setLevel(level)


def _invalid_webhook() -> dict[str, str]:
    """Build webhook settings that fail validation while holding a secret.

    Returns:
        dict[str, str]: Raw settings values with a disallowed URL scheme.
    """
    return {
        "url": f"ftp://hooks.example/{_SECRET_PATH}",
        "auth_type": "bearer",
        "token": _TOKEN,
    }


def test_webhook_validation_error_hides_secrets() -> None:
    """The error text of invalid webhook settings holds neither token nor URL."""
    with pytest.raises(ValidationError) as caught:
        WebhookHandlerSettings(**_invalid_webhook())

    assert _TOKEN not in str(caught.value)
    assert _SECRET_PATH not in str(caught.value)


def test_app_settings_validation_error_hides_secrets() -> None:
    """The same holds when validation starts from the whole application config."""
    handler = {
        "name": "hook",
        "format": {"type": "json"},
        "handler": {"type": "webhook", **_invalid_webhook()},
    }

    with pytest.raises(ValidationError) as caught:
        AppSettings(output={"handlers": [handler]})

    assert _TOKEN not in str(caught.value)
    assert _SECRET_PATH not in str(caught.value)


def test_webhook_repr_hides_secrets() -> None:
    """Logging a settings object does not print the token or the URL."""
    settings = WebhookHandlerSettings(
        url=f"https://hooks.example/{_SECRET_PATH}", auth_type="bearer", token=_TOKEN
    )

    assert _TOKEN not in repr(settings)
    assert _SECRET_PATH not in repr(settings)


def test_saving_settings_keeps_the_token() -> None:
    """Hiding the token from reprs must not drop it from the saved config."""
    settings = WebhookHandlerSettings(
        url="https://hooks.example/x", auth_type="bearer", token=_TOKEN
    )

    assert settings.model_dump(mode="json")["token"] == _TOKEN


@pytest.mark.asyncio
@pytest.mark.usefixtures("restore_logging")
async def test_default_logging_does_not_print_request_urls() -> None:
    """Webhook URLs are credentials, so httpx request lines stay out of the logs."""
    setup_logging(LoggingSettings(log_level="DEBUG"))
    stream = io.StringIO()
    logging.getLogger().addHandler(logging.StreamHandler(stream))

    transport = httpx.MockTransport(lambda _request: httpx.Response(200))
    async with httpx.AsyncClient(transport=transport) as client:
        await client.post(f"https://hooks.example/{_SECRET_PATH}")

    assert _SECRET_PATH not in stream.getvalue()


@pytest.mark.usefixtures("restore_logging")
def test_configured_httpx_level_wins() -> None:
    """Someone debugging HTTP can still turn the logger on explicitly."""
    setup_logging(LoggingSettings(loggers={"httpx": "INFO"}))

    assert logging.getLogger("httpx").level == logging.INFO


@pytest.mark.parametrize("logger_name", [f"{name}.child" for name in _OAUTH_LOGGERS])
@pytest.mark.usefixtures("restore_logging")
def test_debug_logging_does_not_print_oauth_tokens(logger_name: str) -> None:
    """The OAuth libraries log whole token responses at DEBUG, refresh token included."""
    setup_logging(LoggingSettings(log_level="DEBUG"))
    stream = io.StringIO()
    logging.getLogger().addHandler(logging.StreamHandler(stream))

    logging.getLogger(logger_name).debug("Obtained token %s", _TOKEN)

    assert _TOKEN not in stream.getvalue()
