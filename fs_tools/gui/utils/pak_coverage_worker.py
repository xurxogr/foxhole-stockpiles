"""Background worker that checks which catalog icons some PAK files contain."""

import logging
from pathlib import Path

import fs_assets
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class PakCoverageWorker(QThread):
    """Worker thread that runs ``fs_assets.pak_coverage`` on PAK files.

    Only the PAK indexes are read, so the check is quick even for the game PAK.
    """

    coverage_ready = Signal(object)  # fs_assets.types.PakCoverage
    failed = Signal(str)  # Error message

    def __init__(
        self,
        catalog_path: Path,
        pak_files: list[str],
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the coverage worker.

        Args:
            catalog_path (Path): Catalog listing the icons to look for.
            pak_files (list[str]): PAK files to inspect together.
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.catalog_path = catalog_path
        self.pak_files = pak_files

    def run(self) -> None:
        """Check the PAK files and report the coverage or the failure."""
        try:
            coverage = fs_assets.pak_coverage(catalog=str(self.catalog_path), pak=self.pak_files)
        except Exception as e:  # noqa: BLE001 - report any failure via the failed signal
            logger.error("PAK coverage check failed: %s", e)
            self.failed.emit(str(e))
            return

        logger.info(
            "PAK coverage: main icons %d/%d, overlays %d/%d, crate icon %s",
            coverage["main_icons_found"],
            coverage["main_icons_total"],
            coverage["overlays_found"],
            coverage["overlays_total"],
            coverage["has_crate_icon"],
        )
        self.coverage_ready.emit(coverage)
