"""What an input-method pipeline needs from the widget hosting it."""

from typing import Protocol


class PipelineHost(Protocol):
    """The widget a pipeline reports to."""

    def feed(self, message: str) -> None:
        """Append a user-facing line to the activity feed.

        Args:
            message (str): The message to show.
        """
        ...

    def feed_detail(self, message: str) -> None:
        """Append an indented detail line to the activity feed.

        Args:
            message (str): The detail line to show.
        """
        ...

    def on_output_response(self, response: object) -> None:
        """Show the response of the output handlers.

        Args:
            response (object): The output coordinator's response.
        """
        ...

    def refresh_controls(self) -> None:
        """Refresh the status labels and the start/stop control."""
        ...

    def is_active(self) -> bool:
        """Return whether any input method is currently running.

        Returns:
            bool: True if a hotkey listener or monitor is active.
        """
        ...

    def stop_all(self) -> None:
        """Stop the hotkey listener and any running monitors."""
        ...
