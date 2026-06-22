"""Blueprint extractor for extracting and converting PAK files to JSON.

This module handles the infrastructure layer:
- Extracting .uasset files from .pak using repak
- Converting .uasset to .json using UAssetAPI
- Managing extraction caching
"""

import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

from fs_tools.core.utils import validate_tool_path
from fs_tools.services import external_tools


class BlueprintExtractor:
    """Extract and convert blueprint files from PAK to JSON.

    This class handles the infrastructure layer:
    - Extracting .uasset files from .pak using repak
    - Converting .uasset to .json using UAssetAPI
    - Managing extraction caching

    Attributes:
        pak_file: Path to the PAK file.
        extractor_tool: Path to the repak executable.
        converter_tool: Path to the UAssetGUI executable.
    """

    # Directories to extract from PAK
    EXTRACT_DIRECTORIES = [
        "War/Content/Blueprints/ItemPickups/**",
        "War/Content/Blueprints/Vehicles/**",
        "War/Content/Blueprints/Structures/**",
        "War/Content/Blueprints/Data/**",
        "War/Content/Blueprints/DamageTypes/**",
        "War/Content/Blueprints/Items/**",
        "War/Content/Localization/**",
    ]

    # Directories to convert from uasset to JSON
    CONVERT_DIRECTORIES = [
        "ItemPickups",
        "Vehicles",
        "Structures",
        "Data",
        "DamageTypes",
        "Items",
    ]

    # Required directories for a valid extraction
    REQUIRED_DIRECTORIES = [
        "ItemPickups",
        "Vehicles",
        "Structures",
        "Data",
        "DamageTypes",
        "Items",
    ]

    def __init__(
        self,
        pak_file: Path | str,
        extractor_tool: Path | str,
        converter_tool: Path | str,
        max_workers: int = 4,
        force_extract: bool = False,
        extraction_dir: Path | str | None = None,
    ) -> None:
        """Initialize blueprint extractor.

        Args:
            pak_file: Path to .pak file.
            extractor_tool: Path to repak executable.
            converter_tool: Path to UAssetGUI executable.
            max_workers: Maximum number of parallel conversions.
            force_extract: Force re-extraction even if JSON files exist.
            extraction_dir: Directory for extraction. If None, uses temp directory.

        Raises:
            FileNotFoundError: If any of the required files don't exist.
        """
        self.pak_file = Path(pak_file).resolve()
        self.extractor_tool = Path(extractor_tool).resolve()
        self.converter_tool = Path(converter_tool).resolve()
        self.max_workers = max_workers
        self.force_extract = force_extract
        self.extraction_dir = Path(extraction_dir) if extraction_dir else None
        self.logger = logging.getLogger(__name__)

        # Validate paths
        if not self.pak_file.exists():
            raise FileNotFoundError(f"PAK file not found: {self.pak_file}")

        # Validate tool paths for security (prevents command injection)
        validate_tool_path(self.extractor_tool)
        validate_tool_path(self.converter_tool)

        self.temp_dir: Path | None = None
        self.stats = {
            "extracted": 0,
            "converted": 0,
        }

    async def extract(self) -> Path:
        """Extract and convert blueprints from PAK file.

        Returns:
            Path to directory containing extracted/converted blueprints.
        """
        existing = None if self.force_extract else self.find_existing_extraction()

        if existing:
            self.logger.info("Using existing extraction directory")
            self.logger.info("Skipping Stage 1 (PAK extraction)")
            self.logger.info("Skipping Stage 2 (JSON conversion)")
            return existing

        if self.force_extract:
            self.logger.info("Force extraction enabled - re-extracting from PAK")

        # Stage 1: Extract from PAK
        self.logger.info("Stage 1: Extracting from PAK...")
        try:
            extract_dir = await self.extract_from_pak()
        except (OSError, RuntimeError, subprocess.SubprocessError) as e:
            # OSError: file system errors
            # RuntimeError: extraction logic errors
            # SubprocessError: repak tool failures
            self.logger.error("Failed to extract PAK file: %s", e)
            raise

        # Stage 2: Convert to JSON
        self.logger.info("\nStage 2: Converting .uasset to .json...")
        converted_count = await self.convert_uassets_to_json(extract_dir)
        if converted_count == 0:
            raise RuntimeError("No files converted successfully")

        if self.temp_dir and self.temp_dir.exists():
            if self.extraction_dir:
                self.logger.info("Extraction cached in: %s", self.temp_dir)
            else:
                self.logger.info("Temporary extraction kept in: %s", self.temp_dir)

        self.logger.info("\n✅ Extraction complete: %s", extract_dir)
        return extract_dir

    def find_existing_extraction(self) -> Path | None:
        """Check if a valid extraction directory already exists.

        Returns:
            Path to existing extraction directory, or None if not found.
        """
        if not self.extraction_dir or not self.extraction_dir.exists():
            return None

        blueprints_dir = self.extraction_dir / "War" / "Content" / "Blueprints"
        if not blueprints_dir.exists():
            return None

        for dir_name in self.REQUIRED_DIRECTORIES:
            dir_path = blueprints_dir / dir_name
            if not dir_path.exists():
                self.logger.info("Missing directory: %s", dir_name)
                return None

            json_files = list(dir_path.rglob("*.json"))
            if not json_files:
                self.logger.info("No JSON files in directory: %s", dir_name)
                return None

        self.logger.info("Found existing extraction directory: %s", self.extraction_dir)
        return self.extraction_dir

    async def extract_from_pak(self) -> Path:
        """Extract needed directories from PAK file.

        Returns:
            Path to extraction directory.
        """
        self.logger.info("Extracting from PAK: %s", self.pak_file)

        if self.extraction_dir:
            self.temp_dir = self.extraction_dir
            if self.temp_dir.exists():
                self.logger.info("Using existing extraction directory: %s", self.temp_dir)
            else:
                self.temp_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info("Created extraction directory: %s", self.temp_dir)
        else:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="catalog_builder_"))
            self.logger.info("Created temp directory: %s", self.temp_dir)

        for directory in self.EXTRACT_DIRECTORIES:
            self.logger.info("Extracting: %s", directory)

            command = [
                str(self.extractor_tool),
                "unpack",
                "-o",
                str(self.temp_dir) + "/",
                "--include",
                directory,
                str(self.pak_file),
            ]

            try:
                returncode, _stdout, stderr = await external_tools.run_tool(command)

                if returncode != 0:
                    self.logger.error("Failed to extract %s: %s", directory, stderr)
                    raise RuntimeError(f"repak extraction failed for {directory}")

                self.logger.info("Extracted: %s", directory)

            except Exception as e:
                self.logger.error("Error extracting %s: %s", directory, e)
                raise

        uasset_files = list(self.temp_dir.rglob("*.uasset"))
        self.stats["extracted"] = len(uasset_files)
        self.logger.info("Extracted %d .uasset files", len(uasset_files))

        return self.temp_dir

    async def convert_single_uasset(self, uasset_path: Path) -> tuple[bool, str]:
        """Convert a single .uasset file to .json.

        Args:
            uasset_path: Path to the .uasset file.

        Returns:
            Tuple of (success, status) where status is 'success', 'skipped', or 'failed'.
        """
        json_path = uasset_path.with_suffix(".json")

        if json_path.exists():
            self.logger.debug("⊙ Skipped: %s (already exists)", uasset_path.name)
            return True, "skipped"

        command = [
            str(self.converter_tool),
            "tojson",
            str(uasset_path),
            str(json_path),
            "VER_UE4_27",
        ]

        try:
            self.logger.debug("Converting %s", uasset_path.name)
            returncode, _stdout, stderr = await external_tools.run_tool(command)

            if returncode == 0:
                self.logger.debug("✓ Converted: %s", uasset_path.name)
                return True, "success"
            else:
                self.logger.warning(
                    "✗ Failed to convert %s: %s",
                    uasset_path.name,
                    stderr.strip(),
                )
                return False, "failed"

        except Exception as e:
            self.logger.error("✗ Error converting %s: %s", uasset_path.name, e)
            return False, "failed"

    async def convert_uassets_to_json(self, extract_dir: Path) -> int:
        """Convert all .uasset files to .json.

        Args:
            extract_dir: Directory containing extracted .uasset files.

        Returns:
            Number of successfully converted files.
        """
        self.logger.info("Converting .uasset files to .json...")

        blueprints_dir = extract_dir / "War" / "Content" / "Blueprints"
        if not blueprints_dir.exists():
            self.logger.error("Blueprints directory not found: %s", blueprints_dir)
            return 0

        uasset_files = []
        for directory in self.CONVERT_DIRECTORIES:
            dir_path = blueprints_dir / directory
            if dir_path.exists():
                found = list(dir_path.rglob("*.uasset"))
                uasset_files.extend(found)
                self.logger.info("Found %d .uasset files in %s", len(found), directory)

        if not uasset_files:
            self.logger.warning("No .uasset files found")
            return 0

        self.logger.info("Converting %d files...", len(uasset_files))

        semaphore = asyncio.Semaphore(self.max_workers)

        async def convert_with_semaphore(uasset_path: Path) -> tuple[bool, str]:
            async with semaphore:
                return await self.convert_single_uasset(uasset_path)

        tasks = [convert_with_semaphore(f) for f in uasset_files]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for success, status in results if success and status == "success")
        skipped_count = sum(1 for success, status in results if status == "skipped")
        failed_count = sum(1 for success, status in results if status == "failed")

        self.stats["converted"] = success_count + skipped_count
        self.logger.info(
            "Conversion complete: %d success, %d skipped, %d failed",
            success_count,
            skipped_count,
            failed_count,
        )

        return success_count + skipped_count
