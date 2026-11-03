"""Parsing can run on several threads, and the warnings state of Python is global."""

import threading
import time
import warnings
from typing import Any
from unittest.mock import patch

from foxhole_stockpiles.services.sav_parser import parse_save

_SAV_MODULE = "foxhole_stockpiles.services.sav_parser"
_OVERLAP_SECONDS = 0.05


def test_parses_do_not_overlap_while_capturing_warnings() -> None:
    """Two captures at once can leave the global filters and hooks of the other behind."""
    lock = threading.Lock()
    running = 0
    most_running = 0

    def slow_parse(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        nonlocal running, most_running
        with lock:
            running += 1
            most_running = max(most_running, running)
        time.sleep(_OVERLAP_SECONDS)
        with lock:
            running -= 1
        return []

    filters_before = list(warnings.filters)

    with patch(f"{_SAV_MODULE}.fs_sav.parse_save", side_effect=slow_parse):
        threads = [threading.Thread(target=parse_save, args=("x.sav",)) for _ in range(3)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert most_running == 1
    assert warnings.filters == filters_before
