"""Background worker that imports a mod's icons into the template database."""

import logging
from pathlib import Path

import fs_assets
from PySide6.QtCore import QThread, Signal

from fs_tools.core.mod_name import validate_mod_name

logger = logging.getLogger(__name__)

# Progress message shown when each fs-assets import stage starts.
_STAGE_MESSAGES = {
    "extracting_icons": "Extracting the mod's icons ({total} files)...",
    "extracting_vanilla_icons": "Extracting fallback icons from the game PAK ({total} files)...",
    "building_templates": "Building templates for {total} catalog items...",
}


class IconImportWorker(QThread):
    """Worker thread that runs ``fs_assets.add_mod`` for one mod.

    The import runs in Rust with the GIL released. It reads the PAK files
    directly and replaces the mod's previous templates in the database.
    """

    finished = Signal(bool)  # Emits True on success, False on failure
    error = Signal(str)  # Emits error message
    progress = Signal(str)  # Emits progress message for UI updates

    def __init__(
        self,
        mod_pak_files: list[str],
        mod_name: str,
        catalog_path: Path,
        database_path: Path,
        vanilla_pak_file: str | None = None,
        resolutions: list[int] | None = None,
    ) -> None:
        """Initialize the icon import worker.

        Args:
            mod_pak_files (list[str]): The mod's PAK files; later ones override
                earlier ones.
            mod_name (str): Name recorded against the imported templates.
            catalog_path (Path): Catalog listing the items whose icons are imported.
            database_path (Path): Template database to create or update.
            vanilla_pak_file (str | None): The game PAK, used for the subtype and
                crate icons the mod lacks. Defaults to None.
            resolutions (list[int] | None): Resolutions to rebuild; all supported
                resolutions when None. Defaults to None.

        Raises:
            ValueError: If mod_name is invalid or contains unsafe characters.
        """
        super().__init__()
        self.mod_pak_files = mod_pak_files
        self.mod_name = validate_mod_name(mod_name)
        self.catalog_path = catalog_path
        self.database_path = database_path
        self.vanilla_pak_file = vanilla_pak_file
        self.resolutions = resolutions

        logger.debug(
            "IconImportWorker initialized: mod=%s, paks=%d, vanilla=%s, db=%s",
            self.mod_name,
            len(mod_pak_files),
            "Yes" if vanilla_pak_file else "No",
            database_path,
        )

    def run(self) -> None:
        """Import the mod and report the outcome through the signals."""
        try:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            stats = fs_assets.add_mod(
                catalog=str(self.catalog_path),
                pak=self.mod_pak_files,
                db=str(self.database_path),
                mod_name=self.mod_name,
                vanilla_pak=self.vanilla_pak_file,
                resolution=self.resolutions,
                progress=self._on_progress,
            )
        except Exception as e:  # noqa: BLE001 - report any failure via the error signal
            logger.error("Icon import failed: %s", e)
            self.error.emit(str(e))
            self.finished.emit(False)
            return

        logger.info(
            "Imported mod %s: %d of %d items embedded, %d icons missing, %d decode errors",
            self.mod_name,
            stats["items_embedded"],
            stats["total_items"],
            stats["icons_missing"],
            stats["decode_errors"],
        )
        self.progress.emit(
            f"Imported {stats['items_embedded']} of {stats['total_items']} catalog items "
            f"into {self.database_path} as '{self.mod_name}'"
        )
        self.finished.emit(True)

    def _on_progress(self, stage: str, done: int, total: int) -> None:
        """Relay the start of each import stage.

        Args:
            stage (str): The fs-assets import stage name.
            done (int): Steps completed in the stage.
            total (int): Total steps in the stage.
        """
        if done == 0:
            message = _STAGE_MESSAGES.get(stage, stage)
            self.progress.emit(message.replace("{total}", str(total)))
