"""The output handler that posts stockpiles to Discord."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from foxhole_stockpiles.connectors.discord_send_error import DiscordSendError
from foxhole_stockpiles.core.settings.sections.output import (
    DiscordHandlerSettings,
    OutputHandlerConfig,
    OutputSettings,
)
from foxhole_stockpiles.core.settings.sections.output.discord_handler import (
    is_discord_webhook_url,
)
from foxhole_stockpiles.handlers import discord as discord_module
from foxhole_stockpiles.handlers.discord import DiscordOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.models.stockpile_item import StockpileItem
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator

_URL = "https://discord.com/api/webhooks/123/secret-token"


def _stockpile(name: str) -> Stockpile:
    return Stockpile(name=name, items=[StockpileItem(code="Rifle", quantity=5)])


def _handler(**settings: Any) -> tuple[DiscordOutputHandler, AsyncMock]:
    handler = DiscordOutputHandler(DiscordHandlerSettings(url=_URL, **settings))
    send = AsyncMock()
    patcher = patch.object(handler._connector, "send_images", new=send)
    patcher.start()
    return handler, send


@pytest.fixture(autouse=True)
def _simple_render() -> Any:
    with patch.object(discord_module, "render_stockpile", return_value=[b"png"]) as render:
        yield render
    patch.stopall()


@pytest.mark.parametrize(
    "url",
    [
        _URL,
        "https://discordapp.com/api/webhooks/123/abc_DEF-1",
        "https://canary.discord.com/api/v10/webhooks/123/abc",
        "https://ptb.discord.com/api/webhooks/123/abc/",
    ],
)
def test_webhooks_of_discord_are_accepted(url: str) -> None:
    """In all the forms Discord gives them."""
    assert is_discord_webhook_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://discord.com/api/webhooks/123/abc",
        "https://discord.com.evil.example/api/webhooks/123/abc",
        "https://evil.example/https://discord.com/api/webhooks/123/abc",
        "https://discord.com@evil.example/api/webhooks/123/abc",
        "https://discord.com/api/webhooks/123/abc?x=1",
        "https://discord.com/api/users/123/abc",
    ],
)
def test_other_urls_are_refused(url: str) -> None:
    """Stockpile data must not go anywhere else by mistake."""
    assert not is_discord_webhook_url(url)


@pytest.mark.asyncio
async def test_a_wrong_url_sends_nothing_and_says_why() -> None:
    """And the batch stays for when it is fixed."""
    handler = DiscordOutputHandler(DiscordHandlerSettings(url="https://evil.example/x"))
    stockpiles = [_stockpile("A")]

    with patch.object(handler._connector, "send_images", new=AsyncMock()) as send:
        response = await handler.handle(stockpiles)

    send.assert_not_awaited()
    assert response is not None and "not a Discord webhook" in response[0]
    assert handler.undelivered(stockpiles) == stockpiles


@pytest.mark.asyncio
async def test_each_stockpile_is_a_message() -> None:
    """With the text of the settings, its placeholders filled in."""
    handler, send = _handler(message="Report of {name}")

    response = await handler.handle([_stockpile("A"), _stockpile("B")])

    assert response is None
    assert [call.kwargs["content"] for call in send.await_args_list] == [
        "Report of A",
        "Report of B",
    ]
    assert handler.undelivered([]) == []


@pytest.mark.asyncio
async def test_only_what_was_not_posted_stays_pending() -> None:
    """A retry must not post again the images that arrived."""
    handler, send = _handler()
    send.side_effect = [None, DiscordSendError("Discord answered HTTP 500: "), None]
    first, second, third = _stockpile("A"), _stockpile("B"), _stockpile("C")

    response = await handler.handle([first, second, third])

    assert response is not None and "HTTP 500" in response[0]
    assert send.await_count == 2
    assert handler.undelivered([first, second, third]) == [second, third]


@pytest.mark.asyncio
async def test_a_failure_to_draw_also_keeps_what_was_not_posted(_simple_render: Any) -> None:
    """Whatever goes wrong, what arrived does not go again."""
    handler, _send = _handler()
    _simple_render.side_effect = [[b"png"], OSError("no font")]
    first, second = _stockpile("A"), _stockpile("B")

    await handler.handle([first, second])

    assert handler.undelivered([first, second]) == [second]


@pytest.mark.asyncio
async def test_no_stockpiles_post_nothing() -> None:
    """An empty message would only be noise."""
    handler, send = _handler()

    assert await handler.handle([]) is None
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_coordinator_sends_again_only_what_is_pending() -> None:
    """From settings to the retry of the next batch."""
    config = OutputHandlerConfig(name="discord", handler=DiscordHandlerSettings(url=_URL))
    coordinator = OutputCoordinator(OutputSettings(handlers=[config]))
    send = AsyncMock(side_effect=[None, DiscordSendError("no"), None, None])
    sent: list[str] = []

    async def post(_self: DiscordOutputHandler, stockpile: Stockpile) -> None:
        await send()
        sent.append(stockpile.name)

    with patch.object(DiscordOutputHandler, "_post", new=post):
        await coordinator.handle_output(stockpiles=[_stockpile("A"), _stockpile("B")])
        await coordinator.handle_output(stockpiles=[_stockpile("C")])

    assert sent == ["A", "B", "C"]


class TestMinimumInterval:
    """The time a handler waits between posts."""

    @pytest.fixture
    def clock(self) -> Any:
        """Replace the times of the posts.

        Yields:
            Any: The mocks of the wait left and of the record of a post.
        """
        with (
            patch.object(discord_module, "seconds_until_allowed", return_value=0.0) as wait,
            patch.object(discord_module, "record_post") as record,
        ):
            yield wait, record

    @pytest.mark.asyncio
    async def test_during_the_wait_nothing_is_posted_or_lost(self, clock: Any) -> None:
        """The batch stays for the next one, and the user knows why."""
        clock[0].return_value = 300.0
        handler, send = _handler(min_interval_minutes=10)
        stockpiles = [_stockpile("A")]

        response = await handler.handle(stockpiles)

        send.assert_not_awaited()
        assert handler.undelivered(stockpiles) == stockpiles
        assert response is not None and "5 minutes" in response[0]
        clock[1].assert_not_called()

    @pytest.mark.asyncio
    async def test_a_post_starts_the_wait(self, clock: Any) -> None:
        """Once per batch, whatever its size."""
        handler, _send = _handler(min_interval_minutes=10)

        await handler.handle([_stockpile("A"), _stockpile("B")])

        clock[1].assert_called_once_with(_URL)

    @pytest.mark.asyncio
    async def test_a_partial_post_also_starts_it(self, clock: Any) -> None:
        """Something reached the channel."""
        handler, send = _handler(min_interval_minutes=10)
        send.side_effect = [None, DiscordSendError("no")]

        await handler.handle([_stockpile("A"), _stockpile("B")])

        clock[1].assert_called_once_with(_URL)

    @pytest.mark.asyncio
    async def test_a_failed_post_does_not_start_it(self, clock: Any) -> None:
        """Otherwise a retry would have to wait for nothing."""
        handler, send = _handler(min_interval_minutes=10)
        send.side_effect = DiscordSendError("no")

        await handler.handle([_stockpile("A")])

        clock[1].assert_not_called()

    @pytest.mark.asyncio
    async def test_without_an_interval_nothing_is_recorded(self, clock: Any) -> None:
        """No file is written for a feature that is not used."""
        handler, _send = _handler()

        await handler.handle([_stockpile("A")])

        clock[1].assert_not_called()

    def test_a_negative_interval_is_refused(self) -> None:
        """It has no meaning."""
        with pytest.raises(ValidationError):
            DiscordHandlerSettings(url=_URL, min_interval_minutes=-1)
