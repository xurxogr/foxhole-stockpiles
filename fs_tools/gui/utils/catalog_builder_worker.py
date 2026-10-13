"""Background worker that builds the item catalog from the game PAK."""

import logging
from pathlib import Path

import fs_assets
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)

# Progress message shown when each fs-assets build stage starts.
_STAGE_MESSAGES = {
    "extracting_catalog_inputs": "Extracting catalog inputs from the PAK file ({total} files)...",
    "building_catalog": "Building catalog from {total} blueprints...",
}


class CatalogBuilderWorker(QThread):
    """Worker thread that runs ``fs_assets.build_catalog`` on a PAK file.

    The build itself runs in Rust with the GIL released. Cancelling makes the
    next progress report raise, so the build ends without writing the catalog.
    """

    finished = Signal(bool)  # Emits True on success, False on failure/cancel
    error = Signal(str)  # Emits error message
    progress = Signal(str)  # Emits progress message for UI updates

    def __init__(self, pak_file: Path, output_path: Path, full: bool = False) -> None:
        """Initialize the catalog builder worker.

        Args:
            pak_file (Path): Path to the game PAK file.
            output_path (Path): Path for the output catalog JSON.
            full (bool): Keep audio, visual and engine-internal fields.
                Defaults to False.
        """
        super().__init__()
        self.pak_file = pak_file
        self.output_path = output_path
        self.full = full
        self._should_stop = False

        logger.debug(
            "CatalogBuilderWorker initialized: pak=%s, output=%s, full=%s",
            pak_file,
            output_path,
            full,
        )

    def stop(self) -> None:
        """Request the worker to stop."""
        self._should_stop = True
        logger.info("Catalog builder worker stop requested")

    def run(self) -> None:
        """Build the catalog and report the outcome through the signals."""
        try:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            stats = fs_assets.build_catalog(
                pak=str(self.pak_file),
                output=str(self.output_path),
                full=self.full,
                progress=self._on_progress,
            )
        except InterruptedError:
            logger.info("Catalog build cancelled")
            self.finished.emit(False)
            return
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            logger.error("Catalog build failed: %s", e)
            self.error.emit(str(e))
            self.finished.emit(False)
            return

        logger.info(
            "Catalog built: %d files parsed, %d stockpilable items, %d errors",
            stats["parsed"],
            stats["stockpilable"],
            stats["errors"],
        )
        self.progress.emit(
            f"Catalog saved: {stats['stockpilable']} items written to {self.output_path}"
        )
        self.finished.emit(True)

    def _on_progress(self, stage: str, done: int, total: int) -> None:
        """Relay the start of each build stage and honour cancellation.

        Args:
            stage (str): The fs-assets build stage name.
            done (int): Steps completed in the stage.
            total (int): Total steps in the stage.

        Raises:
            InterruptedError: If the user cancelled the build.
        """
        if self._should_stop:
            raise InterruptedError("catalog build cancelled")
        if done == 0:
            message = _STAGE_MESSAGES.get(stage, stage)
            self.progress.emit(message.replace("{total}", str(total)))
