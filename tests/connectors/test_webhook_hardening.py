"""Tests for transport safety in the webhook connector and its handler lifetime."""

import logging

import httpx
import pytest

from foxhole_stockpiles.connectors.webhook import (
    MAX_ERROR_BODY_CHARS,
    WebhookConnector,
)
from foxhole_stockpiles.core.settings.sections.output import (
    ConsoleHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.handlers.webhook import WebhookOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator


@pytest.mark.parametrize(
    ("url", "warns"),
    [
        ("http://hooks.example/x", True),
        ("HTTP://hooks.example/x", True),
        ("https://hooks.example/x", False),
        ("http://localhost:8000/x", False),
        ("http://127.0.0.1/x", False),
        ("http://[::1]/x", False),
    ],
)
def test_warns_when_a_token_would_travel_unencrypted(
    url: str, warns: bool, caplog: pytest.LogCaptureFixture
) -> None:
    """Sending a token over plain HTTP to another machine logs a warning."""
    settings = WebhookHandlerSettings(url=url, auth_type="bearer", token="t")

    with caplog.at_level(logging.WARNING):
        WebhookConnector(settings)

    assert ("unencrypted" in caplog.text) is warns


def test_warning_does_not_print_the_url(caplog: pytest.LogCaptureFixture) -> None:
    """The warning names the host only, because the URL path can be a credential."""
    settings = WebhookHandlerSettings(
        url="http://hooks.example/SECRET-PATH", auth_type="bearer", token="t"
    )

    with caplog.at_level(logging.WARNING):
        WebhookConnector(settings)

    assert "hooks.example" in caplog.text
    assert "SECRET-PATH" not in caplog.text


def test_plain_http_without_a_token_does_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    """Without a token there is no credential header to protect."""
    with caplog.at_level(logging.WARNING):
        WebhookConnector(WebhookHandlerSettings(url="http://hooks.example/x"))

    assert caplog.text == ""


@pytest.mark.asyncio
async def test_non_json_response_body_is_truncated() -> None:
    """A huge non-JSON answer is cut before it reaches the user interface."""
    connector = WebhookConnector(WebhookHandlerSettings(url="https://hooks.example/x"))
    body = "x" * (MAX_ERROR_BODY_CHARS * 2)
    await connector.close()
    connector._client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, text=body))
    )

    response = await connector.send_stockpile({"stockpiles": []})
    await connector.close()

    assert response == [f"HTTP 200: {'x' * MAX_ERROR_BODY_CHARS}"]


@pytest.mark.asyncio
async def test_handler_close_closes_the_http_client() -> None:
    """Closing the handler releases the connection pool of its connector."""
    handler = WebhookOutputHandler(WebhookHandlerSettings(url="https://hooks.example/x"))
    client = handler._webhook_connector._client

    await handler.close()

    assert client.is_closed


@pytest.mark.asyncio
async def test_coordinator_closes_every_handler_it_creates() -> None:
    """One batch leaves no open HTTP client behind, even when a handler fails."""
    settings = OutputSettings(
        handlers=[
            OutputHandlerConfig(
                name="hook",
                format=JsonFormatSettings(),
                handler=WebhookHandlerSettings(url="https://hooks.example/x"),
            ),
            OutputHandlerConfig(
                name="console",
                format=JsonFormatSettings(),
                handler=ConsoleHandlerSettings(),
            ),
        ]
    )
    created: list[httpx.AsyncClient] = []
    coordinator = OutputCoordinator(settings)
    create = coordinator._create_handler

    def spy(config: OutputHandlerConfig) -> object:
        handler = create(config)
        if isinstance(handler, WebhookOutputHandler):
            connector = handler._webhook_connector
            created.append(connector._client)

            async def boom(**_kwargs: object) -> list[str]:
                raise RuntimeError("send failed")

            connector.send_stockpile = boom  # type: ignore[method-assign]
        return handler

    coordinator._create_handler = spy  # type: ignore[method-assign,assignment]

    await coordinator.handle_output([Stockpile()])

    assert len(created) == 1
    assert created[0].is_closed
