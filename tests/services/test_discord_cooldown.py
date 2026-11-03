"""The time between posts to a Discord webhook."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.services import discord_cooldown
from foxhole_stockpiles.services.discord_cooldown import record_post, seconds_until_allowed

_URL = "https://discord.com/api/webhooks/1/secret-token"


@pytest.fixture
def state(tmp_path: Path) -> Any:
    """Keep the times in a temporary file.

    Args:
        tmp_path (Path): The temporary directory.

    Yields:
        Any: The path of the file.
    """
    path = tmp_path / "state" / "cooldowns.json"
    with patch.object(discord_cooldown, "_state_path", return_value=path):
        yield path


def test_a_webhook_without_posts_can_post(state: Path) -> None:
    """There is no file yet."""
    assert seconds_until_allowed(url=_URL, minutes=10) == 0


def test_a_recent_post_makes_it_wait(state: Path) -> None:
    """For the rest of the interval."""
    with patch.object(discord_cooldown.time, "time", return_value=1000.0):
        record_post(_URL)
    with patch.object(discord_cooldown.time, "time", return_value=1060.0):
        assert seconds_until_allowed(url=_URL, minutes=10) == 540


def test_after_the_interval_it_can_post(state: Path) -> None:
    """Exactly when it ends as well."""
    with patch.object(discord_cooldown.time, "time", return_value=1000.0):
        record_post(_URL)
    with patch.object(discord_cooldown.time, "time", return_value=1600.0):
        assert seconds_until_allowed(url=_URL, minutes=10) == 0


def test_no_interval_means_no_wait(state: Path) -> None:
    """The file is not even read."""
    record_post(_URL)

    assert seconds_until_allowed(url=_URL, minutes=0) == 0


def test_each_webhook_has_its_own_time(state: Path) -> None:
    """Posting to one channel does not delay another."""
    record_post(_URL)

    assert seconds_until_allowed(url=f"{_URL}-other", minutes=10) == 0


def test_the_url_is_not_stored(state: Path) -> None:
    """It holds the credential of the webhook."""
    record_post(_URL)

    assert "secret-token" not in state.read_text(encoding="utf-8")
    assert "webhooks" not in state.read_text(encoding="utf-8")


def test_a_time_in_the_future_does_not_block(state: Path) -> None:
    """The clock changed, and the wait could otherwise be very long."""
    with patch.object(discord_cooldown.time, "time", return_value=9000.0):
        record_post(_URL)
    with patch.object(discord_cooldown.time, "time", return_value=1000.0):
        assert seconds_until_allowed(url=_URL, minutes=10) == 0


@pytest.mark.parametrize("content", ["not json", "[1, 2]"])
def test_a_damaged_file_does_not_block(state: Path, content: str) -> None:
    """And it is replaced by the next post."""
    state.parent.mkdir(parents=True)
    state.write_text(content, encoding="utf-8")

    assert seconds_until_allowed(url=_URL, minutes=10) == 0
    record_post(_URL)
    assert len(json.loads(state.read_text(encoding="utf-8"))) == 1


def test_wrong_values_in_the_file_are_ignored(state: Path) -> None:
    """It can be edited by hand."""
    key = discord_cooldown._key(_URL)
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({key: "yesterday"}), encoding="utf-8")

    assert seconds_until_allowed(url=_URL, minutes=10) == 0


def test_a_failure_to_save_is_only_logged(state: Path, caplog: Any) -> None:
    """The message has already been posted."""
    with patch.object(discord_cooldown, "write_private_file", side_effect=OSError("full")):
        record_post(_URL)

    assert "Could not save" in caplog.text
