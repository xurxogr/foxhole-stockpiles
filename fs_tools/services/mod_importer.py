"""Core service for importing mods into template databases.

This service orchestrates the full pipeline for adding a mod to the database:
1. Check catalog against existing database
2. Extract assets from PAK files
3. Generate templates from extracted assets
4. Build/merge database with new templates
"""

import logging
import re
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.commands.database_builder.database_builder import DatabaseBuilder
from fs_tools.commands.generate_templates.generate_templates import TemplateGenerator
from fs_tools.commands.uasset_extractor.uasset_extractor import PakExtractor
from fs_tools.core.utils import load_catalog
from fs_tools.models.mod_import_config import ModImportConfig
from fs_tools.models.mod_import_progress import ModImportProgress
from fs_tools.models.mod_import_result import ModImportResult
from fs_tools.models.pak_validation_result import PakValidationResult
from fs_tools.services import external_tools
from fs_tools.template_db.template_manager import TemplateManager

logger = logging.getLogger(__name__)


class ModImporter:
    """Core service for importing mods into template databases.

    Orchestrates the complete mod import pipeline with progress reporting
    and cancellation support.
    """

    def __init__(
        self,
        config: ModImportConfig,
        progress_callback: Callable[[ModImportProgress], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> None:
        """Initialize the mod importer.

        Args:
            config: Configuration for the import operation
            progress_callback: Optional callback for progress updates
            cancel_check: Optional function that returns True if operation should be cancelled

        Raises:
            ValueError: If config validation fails
        """
        self.config = config
        self._progress_callback = progress_callback
        self._cancel_check = cancel_check

        # Validate mod name
        self.config.mod_name = self._validate_mod_name(config.mod_name)

    @staticmethod
    def _validate_mod_name(mod_name: str) -> str:
        """Validate and normalize mod name to prevent injection attacks.

        Args:
            mod_name: The mod name to validate

        Returns:
            str: Normalized mod name

        Raises:
            ValueError: If mod_name is invalid or contains unsafe characters
        """
        # Strip whitespace
        normalized = mod_name.strip()

        # Check if empty
        if not normalized:
            raise ValueError("Mod name cannot be empty")

        # Check length (reasonable limit)
        if len(normalized) > 100:
            raise ValueError("Mod name is too long (max 100 characters)")

        # Only allow alphanumeric, spaces, underscores, and hyphens
        # This prevents path traversal (..), path separators (/, \), and injection
        if not re.match(r"^[a-zA-Z0-9_ -]+$", normalized):
            raise ValueError(
                "Mod name can only contain alphanumeric characters, "
                "spaces, underscores, and hyphens"
            )

        return normalized

    def _report_progress(
        self,
        step: int,
        step_name: str,
        message: str,
        is_complete: bool = False,
        is_error: bool = False,
        error_message: str = "",
    ) -> None:
        """Report progress to callback if configured.

        Args:
            step: Current step number
            step_name: Name of current step
            message: Progress message
            is_complete: Whether import is complete
            is_error: Whether an error occurred
            error_message: Error message if is_error
        """
        if self._progress_callback:
            progress = ModImportProgress(
                current_step=step,
                step_name=step_name,
                message=message,
                is_complete=is_complete,
                is_error=is_error,
                error_message=error_message,
            )
            self._progress_callback(progress)

        # Also log
        if is_error:
            logger.error("Step %d/%d (%s): %s - %s", step, 5, step_name, message, error_message)
        else:
            logger.info("Step %d/%d (%s): %s", step, 5, step_name, message)

    def _should_cancel(self) -> bool:
        """Check if operation should be cancelled.

        Returns:
            bool: True if operation should be cancelled
        """
        if self._cancel_check:
            return self._cancel_check()
        return False

    async def _get_existing_item_codes_from_database(self) -> set[str]:
        """Check which item codes already exist in the database.

        Returns:
            set[str]: Set of item codes that already have templates for this mod
        """
        database_path = self.config.database_path
        if not database_path or not database_path.exists():
            logger.debug("No existing database found")
            return set()

        logger.debug("Loading database from: %s", database_path)

        existing_codes: set[str] = set()

        # Check all target resolutions (or all enum resolutions if not specified)
        if self.config.target_resolutions:
            resolutions_to_check = [
                SupportedResolution(res) for res in self.config.target_resolutions
            ]
        else:
            resolutions_to_check = list(SupportedResolution)

        # Load database and get item codes from each resolution
        template_manager = TemplateManager(database_path, cache_size=0)

        for resolution in resolutions_to_check:
            try:
                database = await template_manager.load_database(resolution)

                # Get unique item codes from templates matching this mod
                resolution_codes = {
                    template.code
                    for template in database.templates
                    if template.mod == self.config.mod_name
                }
                logger.debug(
                    "Found %d item codes for mod '%s' in resolution %s",
                    len(resolution_codes),
                    self.config.mod_name,
                    resolution.value,
                )
                existing_codes.update(resolution_codes)

            except FileNotFoundError:
                logger.debug("No database found for resolution %s", resolution.value)
            except Exception as e:  # noqa: BLE001 - isolate one bad resolution from the rest
                logger.warning("Error loading database for resolution %s: %s", resolution.value, e)

        logger.info(
            "Found %d existing code(s) for mod '%s' in database",
            len(existing_codes),
            self.config.mod_name,
        )
        return existing_codes

    @staticmethod
    def get_wsl_temp_dir() -> str | None:
        """Get Windows-accessible temp directory when running in WSL.

        Delegates to the shared implementation in
        :mod:`fs_tools.services.external_tools`.

        Returns:
            str | None: Path to Windows temp directory, or None if not in WSL
        """
        return external_tools.get_wsl_temp_dir()

    async def run(self) -> ModImportResult:
        """Run the complete mod import pipeline.

        Returns:
            ModImportResult: Result of the import operation
        """
        result = ModImportResult()
        temp_base_dir = None
        should_cleanup = True

        try:
            # Validate configuration (raises if any required config is missing)
            self._validate_config()

            (
                extracted_assets_dir,
                templates_dir,
                use_existing_extract,
                temp_base_dir,
                should_cleanup,
            ) = self._setup_directories()

            if self._should_cancel():
                logger.info("Import cancelled before starting")
                return result

            extracted_count = await self._prepare_assets(
                extracted_assets_dir=extracted_assets_dir,
                use_existing_extract=use_existing_extract,
                result=result,
            )
            if extracted_count is None:
                return result

            # Step 3: Generate templates
            self._report_progress(3, "Generating templates", "Creating templates from assets...")
            await self._generate_templates(extracted_assets_dir.parent, templates_dir)

            if self._should_cancel():
                logger.info("Import cancelled after template generation")
                return result

            # Step 4: Build database
            self._report_progress(4, "Building database", "Adding templates to database...")
            await self._build_database(templates_dir)

            result.success = True
            result.templates_added = extracted_count  # Approximate
            msg = f"Successfully imported {extracted_count} templates"
            self._report_progress(5, "Complete", msg, is_complete=True)
            logger.info("Mod import pipeline completed successfully")

        except Exception as e:  # noqa: BLE001 - outermost boundary, must report any failure to the GUI
            logger.exception("Error in import pipeline")
            result.success = False
            result.error_message = str(e)
            self._report_progress(0, "Error", "Import failed", is_error=True, error_message=str(e))

        finally:
            # Clean up temporary directory (skip if using extract_dir)
            if temp_base_dir and should_cleanup:
                logger.info("Cleaning up temporary directory: %s", temp_base_dir)
                shutil.rmtree(temp_base_dir, ignore_errors=True)

        return result

    def _setup_directories(self) -> tuple[Path, Path, bool, str, bool]:
        """Determine the extraction/template directories to use for this run.

        Returns:
            tuple[Path, Path, bool, str, bool]: extracted_assets_dir, templates_dir,
                use_existing_extract, temp_base_dir, should_cleanup.

        Raises:
            FileNotFoundError: If a configured extract_dir does not exist.
        """
        use_existing_extract = False
        should_cleanup = True

        if self.config.extract_dir:
            # Use user-provided directory directly (no subdirectories added)
            extracted_assets_dir = self.config.extract_dir

            if self.config.extract_only:
                # Extract to this directory and stop
                should_cleanup = False
                logger.info("Extract-only mode: will save to %s", extracted_assets_dir)
            else:
                # Use existing extracted files
                use_existing_extract = True
                should_cleanup = False
                logger.info("Using pre-extracted assets from: %s", extracted_assets_dir)

                if not extracted_assets_dir.exists():
                    raise FileNotFoundError(
                        f"Extract directory does not exist: {extracted_assets_dir}. "
                        "Run with --extract-only first to extract assets."
                    )

            # Create directory if needed
            extracted_assets_dir.mkdir(parents=True, exist_ok=True)

            # Templates go in temp dir
            wsl_temp_dir = self.get_wsl_temp_dir()
            temp_base_dir = tempfile.mkdtemp(
                prefix=f"fs_mod_import_{self.config.mod_name}_", dir=wsl_temp_dir
            )
            templates_dir = Path(temp_base_dir) / "templates"
        else:
            # Create temporary base directory
            wsl_temp_dir = self.get_wsl_temp_dir()
            temp_base_dir = tempfile.mkdtemp(
                prefix=f"fs_mod_import_{self.config.mod_name}_", dir=wsl_temp_dir
            )
            logger.info("Created temporary directory: %s", temp_base_dir)

            temp_base_path = Path(temp_base_dir)
            extracted_assets_dir = temp_base_path / "extracted_assets" / self.config.mod_name
            templates_dir = temp_base_path / "templates"

        # Create subdirectories
        extracted_assets_dir.mkdir(parents=True, exist_ok=True)
        templates_dir.mkdir(parents=True, exist_ok=True)

        return (
            extracted_assets_dir,
            templates_dir,
            use_existing_extract,
            temp_base_dir,
            should_cleanup,
        )

    async def _prepare_assets(
        self, extracted_assets_dir: Path, use_existing_extract: bool, result: ModImportResult
    ) -> int | None:
        """Ensure extracted assets are ready, validating/extracting as needed.

        Args:
            extracted_assets_dir: Directory holding (or to hold) extracted assets.
            use_existing_extract: Whether to reuse assets already on disk instead
                of validating PAK files and extracting from them.
            result: Result object to populate when the pipeline completes or stops
                here (mutated in place; the caller returns it as-is on None).

        Returns:
            int | None: Number of extracted assets to continue the pipeline with,
                or None if the pipeline is already finished (success, skip, or
                cancellation) and `result` should be returned as-is.

        Raises:
            FileNotFoundError: If use_existing_extract is set but no PNGs are found.
        """
        # Skip validation and extraction if using pre-extracted assets
        if use_existing_extract:
            extracted_count = 0
            if extracted_assets_dir.exists():
                extracted_count = len(list(extracted_assets_dir.rglob("*.png")))

            if extracted_count == 0:
                raise FileNotFoundError(
                    f"No PNG files found in extract directory: {extracted_assets_dir}"
                )

            logger.info(
                "Using %d pre-extracted assets from: %s", extracted_count, extracted_assets_dir
            )
            self._report_progress(
                2,
                "Using pre-extracted assets",
                f"Found {extracted_count} assets in {extracted_assets_dir}",
            )
            return extracted_count

        # Step 0: Validate PAK files contain required assets
        self._report_progress(
            0, "Validating PAK files", "Checking for required assets (crate icon, subicons)..."
        )

        validation_result = await self._validate_pak_files()
        if not validation_result.is_valid:
            result.success = False
            result.error_message = validation_result.error_message
            self._report_progress(
                0,
                "Validation failed",
                "Required assets missing",
                is_error=True,
                error_message=validation_result.error_message,
            )
            return None

        logger.info(
            "PAK validation passed: crate_icon=%s, subicons=%d",
            validation_result.has_crate_icon,
            validation_result.subicons_count,
        )

        if self._should_cancel():
            logger.info("Import cancelled after validation")
            return None

        # Step 1: Check catalog against database
        self._report_progress(1, "Checking catalog", "Loading catalog and checking database...")

        catalog = load_catalog(self.config.catalog_path)
        total_items = len(catalog)
        logger.info("Catalog contains %d items", total_items)

        existing_codes = await self._get_existing_item_codes_from_database()
        items_to_extract = [item for item in catalog if item.code not in existing_codes]

        if not self.config.overwrite:
            if not items_to_extract:
                logger.info(
                    "All %d catalog items already exist in database. Nothing to extract.",
                    total_items,
                )
                result.success = True
                result.templates_skipped = total_items
                self._report_progress(
                    5, "Complete", "All items already in database", is_complete=True
                )
                return None
            logger.info(
                "Need to extract %d items (%d already exist in database)",
                len(items_to_extract),
                len(existing_codes),
            )
            result.templates_skipped = len(existing_codes)
        else:
            logger.info("Overwrite enabled - will extract all %d items", total_items)
            items_to_extract = catalog

        if self._should_cancel():
            logger.info("Import cancelled before extraction")
            return None

        # Step 2: Extract assets from PAK files
        msg = f"Extracting {len(items_to_extract)} items from PAK files..."
        self._report_progress(2, "Extracting assets", msg)
        await self._extract_assets(extracted_assets_dir, existing_codes)

        if self._should_cancel():
            logger.info("Import cancelled after extraction")
            return None

        # Check if anything was extracted
        extracted_count = 0
        if extracted_assets_dir.exists():
            extracted_count = len(list(extracted_assets_dir.rglob("*.png")))

        if extracted_count == 0:
            if existing_codes:
                logger.info(
                    "No new items extracted. Database already contains %d items for mod.",
                    len(existing_codes),
                )
                result.success = True
                self._report_progress(5, "Complete", "No new items to add", is_complete=True)
            else:
                result.warnings.append(
                    "No items extracted from PAK files. Catalog items may not exist in this mod."
                )
                result.success = True
                self._report_progress(
                    5, "Complete", "No items found in PAK files", is_complete=True
                )
            return None

        logger.info("Extracted %d assets, continuing with template generation...", extracted_count)

        # If extract_only, stop here
        if self.config.extract_only:
            result.success = True
            result.templates_added = extracted_count
            msg = f"Extracted {extracted_count} assets to {extracted_assets_dir.parent}"
            self._report_progress(5, "Complete", msg, is_complete=True)
            logger.info("Extract-only mode: stopping after extraction")
            return None

        return extracted_count

    def _validate_config(self) -> None:
        """Validate configuration before running.

        Raises:
            ValueError: If configuration is invalid
            FileNotFoundError: If required files don't exist
        """
        # Check if we're using pre-extracted assets (no extraction needed)
        using_preextracted = self.config.extract_dir and not self.config.extract_only

        # Extractor and converter tools only required when extracting
        if not using_preextracted:
            if not self.config.extractor_tool:
                raise ValueError(
                    "Extractor tool not configured. "
                    "Please configure external_tools.repak in settings."
                )

            if not self.config.converter_tool:
                raise ValueError(
                    "Converter tool not configured. "
                    "Please configure external_tools.umodel in settings."
                )

            if not self.config.extractor_tool.exists():
                raise FileNotFoundError(f"Extractor tool not found: {self.config.extractor_tool}")

            if not self.config.converter_tool.exists():
                raise FileNotFoundError(f"Converter tool not found: {self.config.converter_tool}")

            if not self.config.mod_pak_files:
                raise ValueError("No mod PAK files specified.")

            for pak_file in self.config.mod_pak_files:
                if not Path(pak_file).exists():
                    raise FileNotFoundError(f"PAK file not found: {pak_file}")

            if self.config.vanilla_pak_file and not Path(self.config.vanilla_pak_file).exists():
                raise FileNotFoundError(
                    f"Vanilla PAK file not found: {self.config.vanilla_pak_file}"
                )

        if not self.config.catalog_path.exists():
            raise FileNotFoundError(f"Catalog file not found: {self.config.catalog_path}")

        # Database path not required for extract_only mode
        if not self.config.extract_only and not self.config.database_path:
            raise ValueError("Database path not configured.")

    async def _validate_pak_files(self) -> PakValidationResult:
        """Validate that PAK files contain required assets before extraction.

        Checks for crate icon and subicons in the combined list of mod and vanilla PAK files.

        Returns:
            PakValidationResult: Validation result with details
        """
        # Combine mod PAK files and vanilla PAK file for validation
        all_pak_files: list[str] = list(self.config.mod_pak_files)
        if self.config.vanilla_pak_file:
            all_pak_files.append(self.config.vanilla_pak_file)

        logger.info("Validating %d PAK file(s) for required assets...", len(all_pak_files))

        # extractor_tool is validated in _validate_config before this is called
        assert self.config.extractor_tool is not None

        return await PakExtractor.validate_required_assets(
            pak_files=all_pak_files,
            extractor_tool=self.config.extractor_tool,
        )

    async def _extract_assets(self, output_dir: Path, existing_codes: set[str]) -> None:
        """Extract assets from PAK files.

        Extraction order:
        1. Vanilla subicons and crate icon (as fallback base)
        2. Mod assets (overwrite vanilla if mod has its own subicons)

        This ensures mods that intentionally modify/remove subicons (like clean-icons)
        have their subicons used instead of vanilla fallback.

        Args:
            output_dir: Directory to extract assets to
            existing_codes: Set of item codes that already exist (to skip)
        """
        logger.info("Using extractor tool: %s", self.config.extractor_tool)
        logger.info("Using converter tool: %s", self.config.converter_tool)

        # Step 1: Extract vanilla subicons and crate icon first (as fallback base)
        if self.config.vanilla_pak_file:
            logger.info("Extracting vanilla subicons and crate icon as fallback base...")

            def vanilla_filter(file_path: str) -> bool:
                # Extract subicons (files with "Subtype" in filename) and crate icon
                filename = file_path.split("/")[-1] if "/" in file_path else file_path
                return "Subtype" in filename or "IconFilterCrates" in file_path

            vanilla_extractor = PakExtractor(
                catalog_file=str(self.config.catalog_path),
                pak_files=[self.config.vanilla_pak_file],
                extractor_tool=str(self.config.extractor_tool),
                converter_tool=str(self.config.converter_tool),
                output_dir=str(output_dir),
                filter_assets=vanilla_filter,
            )

            vanilla_success = await vanilla_extractor.process_files()
            if not vanilla_success:
                logger.warning("Vanilla PAK extraction had some failures.")
            else:
                logger.info("Vanilla fallback assets extracted successfully")

        # Step 2: Extract mod assets (will overwrite vanilla subicons if mod has its own)
        # Create filter based on existing item codes (if overwrite is False)
        filter_assets = None
        if not self.config.overwrite and existing_codes:
            catalog = load_catalog(self.config.catalog_path)
            icon_to_code: dict[str, str] = {}
            for item in catalog:
                if item.icon_path:
                    icon_to_code[f"{item.icon_path}.uasset"] = item.code
                if item.subicon_path:
                    icon_to_code[f"{item.subicon_path}.uasset"] = item.code

            def mod_filter(file_path: str) -> bool:
                item_code = icon_to_code.get(file_path)
                if item_code is None:
                    return True  # Not in catalog, extract it anyway
                return item_code not in existing_codes

            filter_assets = mod_filter
            logger.info(
                "Filtering out %d existing item code(s) from extraction", len(existing_codes)
            )

        logger.info("Extracting mod assets...")
        extractor = PakExtractor(
            catalog_file=str(self.config.catalog_path),
            pak_files=self.config.mod_pak_files,
            extractor_tool=str(self.config.extractor_tool),
            converter_tool=str(self.config.converter_tool),
            output_dir=str(output_dir),
            filter_assets=filter_assets,
        )

        success = await extractor.process_files()

        if not success:
            logger.warning(
                "Some catalog items could not be found in PAK files. "
                "This is normal if the mod doesn't include all items."
            )
        else:
            logger.info("Mod asset extraction completed successfully")

    async def _generate_templates(self, assets_dir: Path, output_dir: Path) -> None:
        """Generate templates from extracted assets.

        Args:
            assets_dir: Directory containing extracted assets (with mod subfolders)
            output_dir: Directory to save templates to
        """
        generator = TemplateGenerator(
            catalog_path=self.config.catalog_path,
            assets_path=assets_dir,
            template_path=output_dir,
            template_settings=self.config.template_settings,
        )

        logger.debug(
            "Starting template generation: assets_path=%s, template_path=%s",
            assets_dir,
            output_dir,
        )

        success = await generator.generate_all_templates()

        template_count = 0
        if output_dir.exists():
            template_count = sum(1 for f in output_dir.rglob("*.png"))

        logger.info("Template generation completed: %d template files created", template_count)

        if not success:
            if template_count == 0:
                logger.warning("No templates were generated.")
            else:
                logger.warning(
                    "Template generation had some failures, but %d templates created",
                    template_count,
                )

    async def _build_database(self, templates_dir: Path) -> None:
        """Build database from templates.

        Args:
            templates_dir: Directory containing templates
        """
        database_path = self.config.database_path
        if not database_path:
            raise ValueError("No database path configured")

        # Convert resolution strings to enums
        target_resolutions_enum: list[SupportedResolution] | None = None
        if self.config.target_resolutions:
            target_resolutions_enum = []
            for res_str in self.config.target_resolutions:
                try:
                    resolution = SupportedResolution(res_str)
                    target_resolutions_enum.append(resolution)
                except ValueError:
                    logger.warning("Invalid resolution '%s', skipping", res_str)

        builder = DatabaseBuilder(
            catalog_path=self.config.catalog_path,
            assets_path=templates_dir,
            use_scaling=True,
        )

        await builder.build_all_databases(
            output_path=database_path,
            target_resolutions=target_resolutions_enum,
            overwrite=self.config.overwrite,
            workers=self.config.database_workers,
        )

        logger.info("Database build completed successfully")
