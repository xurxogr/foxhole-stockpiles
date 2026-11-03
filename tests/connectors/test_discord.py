"""The connector that posts images to a Discord webhook."""

import json
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from foxhole_stockpiles.connectors import discord as discord_module
from foxhole_stockpiles.connectors.discord import DiscordConnector
from foxhole_stockpiles.connectors.discord_send_error import DiscordSendError
from foxhole_stockpiles.core.settings.sections.output import DiscordHandlerSettings

_URL = "https://discord.com/api/webhooks/123/secret-token"


def _connector(answer: Callable[[httpx.Request], httpx.Response], **identity: Any) -> Any:
    connector = DiscordConnector(url=_URL, **identity)
    connector._client = httpx.AsyncClient(transport=httpx.MockTransport(answer))
    return connector


def _ok(_request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"id": "1"})


def _payload(request: httpx.Request) -> dict[str, Any]:
    body = request.content.decode("latin-1")
    start = body.index('name="payload_json"')
    start = body.index("\r\n\r\n", start) + 4
    result: dict[str, Any] = json.loads(body[start : body.index("\r\n--", start)])
    return result


@pytest.fixture
def sleep() -> Any:
    """Replace the waits of the connector.

    Yields:
        Any: The mock of the wait.
    """
    with patch.object(discord_module.asyncio, "sleep", new=AsyncMock()) as mock:
        yield mock


@pytest.mark.asyncio
async def test_a_message_carries_its_images_and_no_mentions() -> None:
    """Names are written by players, so nothing they type may notify anyone."""
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _ok(request)

    await _connector(answer, username="Logi").send_images(
        content="@everyone hi", images=[b"one", b"two"]
    )

    assert len(requests) == 1
    assert requests[0].url.params["wait"] == "true"
    payload = _payload(requests[0])
    assert payload["allowed_mentions"] == {"parse": []}
    assert payload["username"] == "Logi"
    assert "avatar_url" not in payload
    assert b'name="files[0]"' in requests[0].content
    assert b'name="files[1]"' in requests[0].content


@pytest.mark.asyncio
async def test_more_images_than_a_message_allows_go_in_several() -> None:
    """Only the first message has the text."""
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _ok(request)

    await _connector(answer).send_images(content="text", images=[b"x"] * 11)

    assert [_payload(request)["content"] for request in requests] == ["text", ""]
    assert b'name="files[9]"' in requests[0].content
    assert b'name="files[1]"' not in requests[1].content


@pytest.mark.asyncio
async def test_long_text_is_cut_to_what_discord_accepts() -> None:
    """A longer one would reject the whole message."""
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _ok(request)

    await _connector(answer).send_images(content="x" * 3000, images=[b"x"])

    assert len(_payload(requests[0])["content"]) == 2000


@pytest.mark.asyncio
async def test_a_short_rate_limit_is_waited_out(sleep: AsyncMock) -> None:
    """The message goes again after the time Discord asks for."""
    answers = [httpx.Response(429, headers={"Retry-After": "2.5"}), httpx.Response(200, json={})]

    await _connector(lambda _request: answers.pop(0)).send_images(content=None, images=[b"x"])

    assert not answers
    sleep.assert_awaited_once_with(2.5)


@pytest.mark.asyncio
async def test_the_wait_can_come_in_the_json(sleep: AsyncMock) -> None:
    """The proxy of Discord may leave out the header."""
    answers = [httpx.Response(429, json={"retry_after": 4}), httpx.Response(200, json={})]

    await _connector(lambda _request: answers.pop(0)).send_images(content=None, images=[b"x"])

    sleep.assert_awaited_once_with(4.0)


@pytest.mark.parametrize("retry_after", ["nonsense", "nan", "-3"])
@pytest.mark.asyncio
async def test_a_wrong_wait_is_replaced(sleep: AsyncMock, retry_after: str) -> None:
    """It comes from the server, so it cannot be trusted to be a usable number."""
    answers = [httpx.Response(429, headers={"Retry-After": retry_after}), httpx.Response(200)]

    await _connector(lambda _request: answers.pop(0)).send_images(content=None, images=[b"x"])

    sleep.assert_awaited_once_with(1.0)


@pytest.mark.asyncio
async def test_a_long_rate_limit_is_a_failure(sleep: AsyncMock) -> None:
    """Waiting for it would hold back the other outputs."""
    connector = _connector(lambda _r: httpx.Response(429, headers={"Retry-After": "3600"}))

    with pytest.raises(DiscordSendError, match="3600"):
        await connector.send_images(content=None, images=[b"x"])

    sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_retries_of_a_rate_limit_end(sleep: AsyncMock) -> None:
    """Discord could keep answering the same."""
    requests: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": "1"})

    with pytest.raises(DiscordSendError):
        await _connector(answer).send_images(content=None, images=[b"x"])

    assert len(requests) == 4


@pytest.mark.asyncio
async def test_it_waits_when_no_more_messages_are_allowed(sleep: AsyncMock) -> None:
    """So the next one does not get a 429."""
    headers = {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset-After": "1.5"}

    await _connector(lambda _r: httpx.Response(200, headers=headers)).send_images(
        content=None, images=[b"x"]
    )

    sleep.assert_awaited_once_with(1.5)


@pytest.mark.asyncio
async def test_an_error_says_what_discord_answered() -> None:
    """Without the URL, which holds the credential."""
    connector = _connector(lambda _r: httpx.Response(404, json={"message": "Unknown Webhook"}))

    with pytest.raises(DiscordSendError) as caught:
        await connector.send_images(content=None, images=[b"x"])

    assert "404" in str(caught.value)
    assert "Unknown Webhook" in str(caught.value)
    assert "secret-token" not in str(caught.value)


@pytest.mark.asyncio
async def test_an_error_without_json_still_fails() -> None:
    """As when a proxy answers with a web page."""
    connector = _connector(lambda _r: httpx.Response(502, text="<html>"))

    with pytest.raises(DiscordSendError, match="502"):
        await connector.send_images(content=None, images=[b"x"])


@pytest.mark.asyncio
async def test_a_network_error_does_not_quote_the_url() -> None:
    """Neither in its text nor through the error that caused it."""

    def answer(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError(f"failed {request.url}")

    with pytest.raises(DiscordSendError) as caught:
        await _connector(answer).send_images(content=None, images=[b"x"])

    assert "secret-token" not in str(caught.value)
    assert caught.value.__suppress_context__


def test_the_url_is_not_in_the_settings_repr() -> None:
    """Logging the settings must not reveal the credential."""
    assert "secret-token" not in repr(DiscordHandlerSettings(url=_URL))
