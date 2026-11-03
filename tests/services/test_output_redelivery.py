"""What a handler failed to deliver reaches it with the next batch, and only it."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from googleapiclient.errors import HttpError

from foxhole_stockpiles.core.settings.sections.output import (
    ConsoleHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
    SheetsHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.handlers.base_handler import BaseOutputDestinationHandler
from foxhole_stockpiles.handlers.sheets import SheetsOutputHandler
from foxhole_stockpiles.handlers.webhook import WebhookOutputHandler
from foxhole_stockpiles.models.stockpile import Stockpile
from foxhole_stockpiles.services import savefile_processor
from foxhole_stockpiles.services.output_coordinator import OutputCoordinator
from foxhole_stockpiles.services.savefile_processor import SaveFileProcessor


class _FakeHandler(BaseOutputDestinationHandler):
    """Records every batch, and fails the way it is told to."""

    def __init__(self, fails_with: str | None = None) -> None:
        """Initialize the fake.

        Args:
            fails_with (str | None): "flag" to report a failed delivery, "raise" to
                raise, None to succeed.
        """
        self.fails_with = fails_with
        self.batches: list[list[Stockpile]] = []

    async def handle(self, stockpiles: list[Stockpile], **kwargs: Any) -> None:
        """Record the batch and fail if told to.

        Args:
            stockpiles (list[Stockpile]): The batch.
            **kwargs: Unused.

        Raises:
            RuntimeError: If told to fail by raising.
        """
        self.batches.append(stockpiles)
        self.delivered = self.fails_with != "flag"
        if self.fails_with == "raise":
            raise RuntimeError("boom")

    def batch_names(self) -> list[list[str]]:
        """List the stockpile names of every batch received.

        Returns:
            list[list[str]]: The names, batch by batch.
        """
        return [[stockpile.name for stockpile in batch] for batch in self.batches]


def _stockpile(name: str, day: int = 1) -> Stockpile:
    """Build a stockpile.

    Args:
        name (str): Its name, which tells it apart from the others.
        day (int): The day of its timestamp.

    Returns:
        Stockpile: The stockpile.
    """
    return Stockpile(
        name=name, type="Seaport", hex="H", timestamp=datetime(2026, 1, day, tzinfo=UTC)
    )


def _coordinator(*handlers: BaseOutputDestinationHandler) -> OutputCoordinator:
    """Build a coordinator whose configured handlers are the given ones.

    Args:
        *handlers (BaseOutputDestinationHandler): The handlers, in configuration order.

    Returns:
        OutputCoordinator: The coordinator.
    """
    configs = [
        OutputHandlerConfig(
            name=f"handler{position}", format=JsonFormatSettings(), handler=ConsoleHandlerSettings()
        )
        for position in range(len(handlers))
    ]
    coordinator = OutputCoordinator(OutputSettings(handlers=configs))
    by_config = {
        id(config): handler
        for config, handler in zip(coordinator.output_settings.handlers, handlers, strict=True)
    }
    coordinator._create_handler = lambda config: by_config[id(config)]  # type: ignore[method-assign]
    return coordinator


def _webhook_handler(reply: Any) -> WebhookOutputHandler:
    """Build a webhook handler whose HTTP client answers with ``reply``.

    Args:
        reply (Any): The callable given to the mock transport.

    Returns:
        WebhookOutputHandler: The handler.
    """
    handler = WebhookOutputHandler(WebhookHandlerSettings(url="https://hooks.example/x"))
    handler._webhook_connector._client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
    return handler


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["flag", "raise"])
async def test_a_failed_batch_goes_again_with_the_next_one(failure: str) -> None:
    """Neither way of failing loses the stockpiles, and a delivered batch is forgotten."""
    handler = _FakeHandler(fails_with=failure)
    coordinator = _coordinator(handler)

    await coordinator.handle_output([_stockpile("a")])
    handler.fails_with = None
    await coordinator.handle_output([_stockpile("b")])
    await coordinator.handle_output([_stockpile("c")])

    assert handler.batch_names() == [["a"], ["a", "b"], ["c"]]


@pytest.mark.asyncio
async def test_the_handler_that_delivered_does_not_receive_it_twice() -> None:
    """Appending to a sheet again would duplicate its rows."""
    sheet = _FakeHandler()
    webhook = _FakeHandler(fails_with="flag")
    coordinator = _coordinator(sheet, webhook)

    await coordinator.handle_output([_stockpile("a")])
    webhook.fails_with = None
    await coordinator.handle_output([_stockpile("b")])

    assert sheet.batch_names() == [["a"], ["b"]]
    assert webhook.batch_names() == [["a"], ["a", "b"]]


@pytest.mark.asyncio
async def test_a_newer_version_replaces_the_undelivered_one() -> None:
    """The same stockpile is sent once, as it is now."""
    handler = _FakeHandler(fails_with="flag")
    coordinator = _coordinator(handler)

    await coordinator.handle_output([_stockpile("a", day=1)])
    handler.fails_with = None
    await coordinator.handle_output([_stockpile("a", day=2)])

    assert [stockpile.timestamp.day for stockpile in handler.batches[1]] == [2]


@pytest.mark.asyncio
async def test_the_response_of_a_failed_handler_still_reaches_the_caller() -> None:
    """The user keeps seeing why it failed."""
    coordinator = _coordinator(_webhook_handler(lambda _request: httpx.Response(500)))

    response = await coordinator.handle_output([_stockpile("a")])

    assert response == ["HTTP 500 error from server"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "body", "delivered"),
    [
        (200, '{"message": "ok"}', True),
        (200, "not json", True),
        (500, "", False),
        (401, "", False),
    ],
    ids=["json", "plain-text", "server-error", "rejected"],
)
async def test_webhook_reports_whether_it_delivered(
    status: int, body: str, delivered: bool
) -> None:
    """Any answer outside the 2xx range means the data did not arrive."""
    handler = _webhook_handler(lambda _request: httpx.Response(status, text=body))

    await handler.handle([_stockpile("a")])
    await handler.close()

    assert handler.delivered is delivered


@pytest.mark.asyncio
async def test_webhook_transport_failure_is_not_delivered() -> None:
    """A dropped connection is reported as a message, and it did not arrive either."""

    def drop(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadError("connection dropped")

    handler = _webhook_handler(drop)

    await handler.handle([_stockpile("a")])
    await handler.close()

    assert handler.delivered is False


@pytest.mark.asyncio
async def test_sheets_append_failure_is_not_delivered() -> None:
    """An API error while appending leaves the rows unwritten."""
    handler = SheetsOutputHandler(
        SheetsHandlerSettings(
            spreadsheet_url="https://docs.google.com/spreadsheets/d/abc",
            sheet_id="Sheet1",
            start_cell="A1",
            row_format="region",
        )
    )
    handler._credentials = MagicMock()
    error = HttpError(resp=MagicMock(status=500), content=b"")

    with patch.object(handler, "_append_rows", side_effect=error):
        await handler.handle([_stockpile("a")])

    assert handler.delivered is False


@pytest.mark.asyncio
async def test_sav_monitor_sends_a_failed_change_with_the_next_change() -> None:
    """A webhook outage no longer loses the update of a stockpile that does not change again."""
    handler = _FakeHandler(fails_with="flag")
    processor = SaveFileProcessor(Path("x.sav"), output_coordinator=_coordinator(handler))

    with patch.object(savefile_processor, "parse_save", return_value=[_stockpile("a")]):
        await processor._process_file()

    handler.fails_with = None
    saved = [_stockpile("a"), _stockpile("b")]
    with patch.object(savefile_processor, "parse_save", return_value=saved):
        await processor._process_file()

    assert handler.batch_names() == [["a"], ["a", "b"]]
