"""PAK file extraction tool for Foxhole game assets.

This module provides functionality to extract game assets from Foxhole PAK files
and convert them to PNG format for use in the stockpile recognition system.
Uses repak for extraction and UModel.exe for conversion.
"""

import argparse
import asyncio
import logging
import multiprocessing
import shutil
import tempfile
from collections.abc import Callable
from copy import copy
from pathlib import Path

from foxhole_stockpiles.core.logging import setup_logging
from foxhole_stockpiles.core.settings import get_settings
from foxhole_stockpiles.core.utils import get_subprocess_kwargs
from foxhole_stockpiles.models.catalog_item import CatalogItem
from fs_tools.core.utils import load_catalog, validate_tool_path
from fs_tools.models.pak_validation_result import PakValidationResult
from fs_tools.services import external_tools

DEFAULT_CATALOG = "catalog.json"
DEFAULT_PAK_FILES = (
    r"C:\Program Files (x86)\Steam\steamapps\common\Foxhole\War\Content\Paks"
    r"\War-WindowsNoEditor.pak"
)
DEFAULT_EXTRACTOR = r"C:\repak\repak.exe"
DEFAULT_CONVERTER = r"C:\UModel\umodel.exe"
DEFAULT_OUTPUT = "output"

# Required assets for database building
CRATE_ICON_PATH = "War/Content/Textures/UI/Menus/IconFilterCrates.uasset"
# Subicons are in ItemIcons folder with "Subtype" prefix (e.g., SubtypeAPIcon, SubtypeATIcon)
SUBICONS_PATH_PREFIX = "War/Content/Textures/UI/ItemIcons/"
SUBICONS_FILENAME_PREFIX = "Subtype"


def _is_safe_pak_relative_path(path: str) -> bool:
    """Check whether a PAK-internal asset path is safe to extract.

    Icon paths come from `catalog.json`, which is normally builder-controlled
    but may originate from a corrupted or malicious catalog. Extraction joins
    this path onto a temp directory and passes it to `repak`/`umodel.exe`, so
    a `..` segment or an absolute path could escape the intended extraction
    directory.

    Args:
        path (str): The PAK-internal relative path to check.

    Returns:
        bool: True if the path has no traversal or absolute-path segments.
    """
    if not path or Path(path).is_absolute():
        return False
    return ".." not in Path(path).parts


class PakExtractor:
    """Extract and convert assets from Foxhole PAK files.

    Handles the complete pipeline from PAK extraction to PNG conversion,
    including parallel processing and error handling. Supports multiple
    PAK files for mod compatibility.
    """

    def __init__(
        self,
        catalog_file: str = DEFAULT_CATALOG,
        pak_files: str | list[str] = DEFAULT_PAK_FILES,
        extractor_tool: str = DEFAULT_EXTRACTOR,
        converter_tool: str = DEFAULT_CONVERTER,
        output_dir: str = DEFAULT_OUTPUT,
        filter_assets: set[str] | Callable[[str], bool] | None = None,
    ) -> None:
        """Initialize the PAK extractor with default paths and tools.

        Args:
            catalog_file (str): Path to the catalog.json file.
            pak_files (str | list[str]): Path(s) to PAK file(s). Can be a single path or a list.
            extractor_tool (str): Path to the repak.exe tool for extraction.
            converter_tool (str): Path to the umodel.exe tool for conversion.
            output_dir (str): Directory where converted PNG files will be saved.
            filter_assets (set[str] | Callable[[str], bool] | None): Optional filter for assets.
                Can be a set of file paths to include, or a callable that takes a file path
                and returns True if the asset should be extracted. If None, all catalog assets
                are extracted.

        Raises:
            ValueError: If any of the parameters but log_file is empty.
            FileNotFoundError: If any specified file does not exist.
        """
        if not catalog_file:
            raise ValueError("catalog_file cannot be an empty string")

        if not pak_files:
            raise ValueError("pak_files cannot be empty")

        if not extractor_tool:
            raise ValueError("extractor_tool cannot be an empty string")

        if not converter_tool:
            raise ValueError("converter_tool cannot be an empty string")

        if not output_dir:
            raise ValueError("output_dir cannot be an empty string")

        self.catalog_file = Path(catalog_file).resolve()
        self.extractor_tool = Path(extractor_tool).resolve()
        self.converter_tool = Path(converter_tool).resolve()
        self.output_dir = Path(output_dir).resolve()

        if not self.catalog_file.exists():
            raise FileNotFoundError(f"Catalog file not found: {self.catalog_file}")

        # Validate tool paths for security (prevents command injection)
        validate_tool_path(self.extractor_tool)
        validate_tool_path(self.converter_tool)

        if isinstance(pak_files, str):
            self.pak_files = [Path(pak_files).resolve()]
        else:
            self.pak_files = [Path(pak_file).resolve() for pak_file in pak_files]

        # Validate that all pak files exist (optional but recommended)
        for pak_file in self.pak_files:
            if not pak_file.exists():
                raise FileNotFoundError(f"PAK file not found: {pak_file}")

        self.filter_assets = filter_assets

        self._logger = logging.getLogger(__name__)
        self._logger.info("Using PAK files: %s", self.pak_files)

        if self.filter_assets is not None:
            if isinstance(self.filter_assets, set):
                self._logger.info(
                    "Asset filter enabled: %d specific files", len(self.filter_assets)
                )
            else:
                self._logger.info("Asset filter enabled: custom filter function")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Detect if tools are Windows executables (need path conversion in WSL)
        self._extractor_is_windows, self._converter_is_windows = self._detect_windows_tools()

    @staticmethod
    async def validate_required_assets(
        pak_files: list[str] | list[Path],
        extractor_tool: str | Path,
    ) -> PakValidationResult:
        """Validate that required assets (crate icon, subicons) exist in PAK files.

        This is a pre-check to avoid expensive extraction when required assets are missing.

        Args:
            pak_files: List of PAK file paths to check
            extractor_tool: Path to the repak tool

        Returns:
            PakValidationResult: Validation result with details about what was found
        """
        logger = logging.getLogger(__name__)
        result = PakValidationResult()

        if not pak_files:
            result.error_message = "No PAK files provided"
            return result

        extractor_path = Path(extractor_tool)
        try:
            validate_tool_path(extractor_path)
        except (FileNotFoundError, ValueError) as e:
            result.error_message = str(e)
            return result

        # Collect all files from all PAK files
        all_files: set[str] = set()

        for pak_file in pak_files:
            pak_path = Path(pak_file)
            if not pak_path.exists():
                logger.warning("PAK file not found: %s", pak_file)
                continue

            try:
                # Run repak list to get all files in the PAK
                command = [str(extractor_path), "list", str(pak_path)]
                logger.debug("Listing files in PAK: %s", pak_path)

                returncode, stdout, stderr = await external_tools.run_tool(command)

                if returncode == 0:
                    # Parse the file list (one file per line)
                    files = stdout.strip().split("\n")
                    all_files.update(f.strip() for f in files if f.strip())
                    logger.debug("Found %d files in %s", len(files), pak_path.name)
                else:
                    logger.warning("Failed to list files in %s: %s", pak_path, stderr)

            except Exception as e:
                logger.error("Error listing files in %s: %s", pak_file, e)

        if not all_files:
            result.error_message = "Could not list any files from the provided PAK files"
            return result

        result.files_found = all_files

        # Check for crate icon
        result.has_crate_icon = CRATE_ICON_PATH in all_files

        # Check for subicons (files in ItemIcons folder with "Subtype" in the filename)
        subicons = [
            f
            for f in all_files
            if SUBICONS_PATH_PREFIX in f and SUBICONS_FILENAME_PREFIX in f.split("/")[-1]
        ]
        result.subicons_count = len(subicons)
        result.has_subicons = result.subicons_count > 0

        # Determine validity - we need both crate icon and subicons
        if not result.has_crate_icon and not result.has_subicons:
            result.error_message = (
                "The PAK files are missing required assets:\n"
                "  - Crate icon (IconFilterCrates)\n"
                "  - Subicons\n\n"
                "These assets are required to build template databases.\n"
                "Please include the vanilla game PAK file (War-WindowsNoEditor.pak) "
                "in your import."
            )
        elif not result.has_crate_icon:
            result.error_message = (
                "The PAK files are missing the crate icon (IconFilterCrates).\n"
                "This asset is required to build template databases.\n"
                "Please include the vanilla game PAK file."
            )
        elif not result.has_subicons:
            result.error_message = (
                "The PAK files are missing subicons.\n"
                "Subicons are required to build template databases.\n"
                "Please include the vanilla game PAK file."
            )
        else:
            result.is_valid = True
            logger.info(
                "PAK validation passed: crate_icon=%s, subicons=%d",
                result.has_crate_icon,
                result.subicons_count,
            )

        return result

    def _detect_windows_tools(self) -> tuple[bool, bool]:
        """Detect if the tools are Windows executables.

        Returns:
            tuple[bool, bool]: (extractor_is_windows, converter_is_windows)
        """
        extractor_is_windows = external_tools.tool_is_windows(self.extractor_tool)
        converter_is_windows = external_tools.tool_is_windows(self.converter_tool)

        if extractor_is_windows:
            self._logger.info(
                "Detected Windows extractor - will convert paths for WSL compatibility"
            )
        else:
            self._logger.info("Detected Linux/native extractor - using paths as-is")

        if converter_is_windows:
            self._logger.info(
                "Detected Windows converter - will convert paths for WSL compatibility"
            )
        else:
            self._logger.info("Detected Linux/native converter - using paths as-is")

        return extractor_is_windows, converter_is_windows

    @staticmethod
    def _get_wsl_temp_dir() -> str | None:
        """Get Windows-accessible temp directory when running in WSL.

        Delegates to the shared implementation in
        :mod:`fs_tools.services.external_tools`.

        Returns:
            str | None: Path to Windows temp directory, or None if not in WSL or failed
        """
        return external_tools.get_wsl_temp_dir()

    @staticmethod
    def _convert_wsl_path_to_windows(path: str | Path) -> str:
        """Convert WSL path to Windows path for Windows executables.

        Delegates to the shared implementation in
        :mod:`fs_tools.services.external_tools`.

        Args:
            path (str | Path): Path to convert (may be WSL or already Windows)

        Returns:
            str: Windows-compatible path
        """
        return external_tools.convert_wsl_path_to_windows(path)

    async def extract_single_file(self, file_path: str, temp_dir: str) -> bool:
        """Extract a single file from the PAK files to temporary directory.

        Tries each PAK file in order until the file is found and extracted.

        Args:
            file_path (str): The path of the file to extract.
            temp_dir (str): The temporary directory to extract files to.

        Returns:
            bool: True if extraction was successful, False otherwise.
        """
        for pak_file in self.pak_files:
            # Create a unique subdirectory for this PAK to avoid conflicts
            pak_name = Path(pak_file).stem
            pak_extract_dir = Path(temp_dir) / pak_name

            # Convert paths to Windows format if using Windows extractor in WSL
            if self._extractor_is_windows:
                pak_file_str = self._convert_wsl_path_to_windows(pak_file)
                output_dir_str = self._convert_wsl_path_to_windows(pak_extract_dir)
                # Ensure output directory ends with backslash for Windows
                if not output_dir_str.endswith("\\"):
                    output_dir_str += "\\"
            else:
                pak_file_str = str(pak_file)
                output_dir_str = str(pak_extract_dir) + "/"

            command = [
                str(self.extractor_tool),
                "unpack",
                "-o",
                output_dir_str,
                "--include",
                file_path,
                "-q",
                pak_file_str,
            ]

            process = None
            try:
                self._logger.debug("Extracting %s from %s", file_path, pak_file)
                self._logger.debug("Full extraction command: %s", " ".join(command))
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    **get_subprocess_kwargs(),
                )
                # Await process completion and capture output
                stdout, stderr = await process.communicate()
                returncode = process.returncode

                if returncode == 0:
                    # Check if the specific file was extracted
                    extracted_file_path = pak_extract_dir / file_path
                    if extracted_file_path.exists():
                        self._logger.info("Successfully extracted: %s", file_path)
                        return True
                    self._logger.debug("File %s not found in %s", file_path, pak_file)
                    continue
                else:
                    self._logger.debug(
                        "Failed to extract from %s (file not in PAK): %s", pak_file, stderr.decode()
                    )
                    continue

            except Exception as e:
                self._logger.error("Error extracting %s from %s: %s", file_path, pak_file, e)
                continue
            finally:
                # Ensure the process is terminated and resources are cleaned up
                if process is not None and process.returncode is None:
                    try:
                        process.terminate()
                        await process.wait()
                    except (ProcessLookupError, OSError):
                        # Process already terminated or cleanup failed
                        pass

        # If we get here, file wasn't found in any PAK
        self._logger.error("Failed to extract %s from any PAK file", file_path)
        return False

    async def convert_to_png(self, file_path: str, temp_dir: str) -> bool:
        """Convert extracted file to PNG using UModel.

        Args:
            file_path (str): The path of the file to convert.
            temp_dir (str): The temporary directory where the file is located.

        Returns:
            bool: True if conversion was successful, False otherwise.
        """
        if await self._try_convert_with_version(file_path=file_path, temp_dir=temp_dir):
            return True

        # If all versions fail, log the issue
        self._logger.error("Failed to convert %s with any UE version", file_path)
        return False

    async def _try_convert_with_version(
        self, file_path: str, temp_dir: str, ue_version: str = "ue4.27"
    ) -> bool:
        """Try to convert file with specific UE version.

        Args:
            file_path (str): The path of the file to convert.
            temp_dir (str): The temporary directory where the file is located.
            ue_version (str): The Unreal Engine version to use for conversion. Defaults to "ue4.27".

        Returns:
            bool: True if conversion succeeded, False otherwise.
        """
        process = None
        try:
            # Find the PAK directory that contains the extracted file
            temp_path = Path(temp_dir)
            pak_root_dir = None

            for pak_dir in temp_path.iterdir():
                if pak_dir.is_dir():
                    potential_file = pak_dir / file_path
                    if potential_file.exists():
                        pak_root_dir = pak_dir
                        break

            if not pak_root_dir:
                self._logger.error("Could not find extracted file: %s", file_path)
                return False

            # Convert paths to Windows format if using Windows converter in WSL
            if self._converter_is_windows:
                pak_root_dir_str = self._convert_wsl_path_to_windows(pak_root_dir)
                output_dir_str = pak_root_dir_str.rstrip("\\") + "\\War\\Content\\"
            else:
                pak_root_dir_str = str(pak_root_dir)
                output_dir_str = str(pak_root_dir) + "/War/Content/"

            command = [
                str(self.converter_tool),
                f"-path={pak_root_dir_str}",
                f"-game={ue_version}",
                "-png",
                "-export",
                file_path,
                f"-out={output_dir_str}",
            ]

            self._logger.debug("Trying conversion with %s: %s", ue_version, file_path)
            self._logger.debug("Full command: %s", " ".join(command))
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                **get_subprocess_kwargs(),
            )
            # Await process completion and capture output
            stdout, stderr = await process.communicate()
            returncode = process.returncode

            if returncode == 0:
                # Handle the output path conversion
                file_path_obj = Path(file_path)
                png_name = file_path_obj.with_suffix(".png")
                converted_path = pak_root_dir / png_name
                output_path = Path(self.output_dir) / png_name

                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Move the converted file if it exists
                if converted_path.exists():
                    shutil.move(str(converted_path), str(output_path))
                    self._logger.info("Successfully converted with %s: %s", ue_version, png_name)
                    return True
                else:
                    self._logger.debug(
                        "Converted file not found at expected path: %s", converted_path
                    )
                    return False
            else:
                self._logger.debug(
                    "Conversion failed with %s for %s: %s", ue_version, file_path, stderr.decode()
                )
                return False

        except Exception as e:
            self._logger.debug("Error converting %s with %s: %s", file_path, ue_version, e)
            return False
        finally:
            # Ensure the process is terminated and resources are cleaned up
            if process is not None and process.returncode is None:
                try:
                    process.terminate()
                    await process.wait()
                except (ProcessLookupError, OSError):
                    # Process already terminated or cleanup failed
                    pass

    def get_files_to_extract(self) -> set[str]:
        """Get all unique files that need to be extracted from the catalog.

        Applies the filter_assets if configured to limit which files are extracted.

        Returns:
            set[str]: A set of unique file paths to extract.
        """
        catalog: list[CatalogItem] = load_catalog(self.catalog_file)
        if not catalog:
            return set()

        files_to_extract: set[str] = set()

        # Add the crate icon file
        files_to_extract.add("War/Content/Textures/UI/Menus/IconFilterCrates.uasset")

        for item in catalog:
            if not item.icon_path:
                self._logger.warning("Item %s has no icon path, skipping", item.code)
                continue

            icon_file = f"{item.icon_path}.uasset"
            if not _is_safe_pak_relative_path(icon_file):
                self._logger.warning(
                    "Item %s has an unsafe icon path, skipping: %s", item.code, icon_file
                )
                continue
            files_to_extract.add(icon_file)

            if item.subicon_path:
                subicon_file = f"{item.subicon_path}.uasset"
                if not _is_safe_pak_relative_path(subicon_file):
                    self._logger.warning(
                        "Item %s has an unsafe subicon path, skipping: %s",
                        item.code,
                        subicon_file,
                    )
                    continue
                files_to_extract.add(subicon_file)

        # Apply filter if configured
        if self.filter_assets is not None:
            if isinstance(self.filter_assets, set):
                # Filter to only include files in the filter set
                files_to_extract = files_to_extract.intersection(self.filter_assets)
                self._logger.info(
                    "Applied asset filter: %d files after filtering", len(files_to_extract)
                )
            else:
                # Use callable filter function
                original_count = len(files_to_extract)
                files_to_extract = {f for f in files_to_extract if self.filter_assets(f)}
                self._logger.info(
                    "Applied asset filter: %d files after filtering (from %d)",
                    len(files_to_extract),
                    original_count,
                )

        self._logger.info("Found %d unique files to process", len(files_to_extract))
        return files_to_extract

    async def process_files(self, max_workers: int | None = None) -> bool:
        """Extract and convert all files.

        Args:
            max_workers (int | None): Number of parallel operations. Defaults to None, which uses
                the CPU count.

        Returns:
            bool: True if all operations were successful, False otherwise.
        """
        files_to_extract = self.get_files_to_extract()

        if not files_to_extract:
            self._logger.warning("No files found to extract")
            return False

        # Use CPU count if max_workers is not specified
        if max_workers is None:
            max_workers = multiprocessing.cpu_count()
            self._logger.info("Using %d workers based on CPU count", max_workers)

        # Get Windows-accessible temp directory if using any Windows tools in WSL
        wsl_temp_base = None
        if self._extractor_is_windows or self._converter_is_windows:
            wsl_temp_base = self._get_wsl_temp_dir()
            if wsl_temp_base:
                self._logger.info(
                    "Using Windows temp directory for Windows tools: %s", wsl_temp_base
                )

        # Create temporary directory
        with tempfile.TemporaryDirectory(dir=wsl_temp_base) as temp_dir:
            self._logger.info("Created temporary directory: %s", temp_dir)

            # Extract files individually
            self._logger.info("Starting extraction of %d files...", len(files_to_extract))
            semaphore = asyncio.Semaphore(max_workers)

            async def extract_with_semaphore(file_path: str) -> bool:
                async with semaphore:
                    return await self.extract_single_file(file_path, temp_dir)

            extract_tasks = [extract_with_semaphore(f) for f in files_to_extract]
            extract_results = await asyncio.gather(*extract_tasks)

            successful_extractions = sum(1 for result in extract_results if result)
            failed_extractions = sum(1 for result in extract_results if not result)

            self._logger.info(
                "Extracted %d/%d files successfully", successful_extractions, len(files_to_extract)
            )

            if successful_extractions == 0:
                self._logger.error("No files were extracted successfully")
                return False

            # Convert files to PNG
            self._logger.info("Starting conversion to PNG...")
            # Only convert files that were successfully extracted
            files_to_convert = [f for i, f in enumerate(files_to_extract) if extract_results[i]]

            async def convert_with_semaphore(file_path: str) -> bool:
                async with semaphore:
                    return await self.convert_to_png(file_path, temp_dir)

            convert_tasks = [convert_with_semaphore(f) for f in files_to_convert]
            convert_results = await asyncio.gather(*convert_tasks)

            successful_conversions = sum(1 for result in convert_results if result)
            failed_conversions = sum(1 for result in convert_results if not result)

            # Log summary
            self._logger.info("\nProcessing Summary:")
            self._logger.info("Total catalog files: %d", len(files_to_extract))
            self._logger.info("Successful extractions: %d", successful_extractions)
            self._logger.info("Failed extractions: %d", failed_extractions)
            self._logger.info("Successful conversions: %d", successful_conversions)
            self._logger.info("Failed conversions: %d", failed_conversions)

            # Consider it successful if we converted at least some files
            return successful_conversions > 0


async def main() -> None:
    """Command-line interface for the PAK extraction tool.

    Parses command-line arguments and runs the extraction process.
    Exits with code 1 if any operations fail, 0 if all succeed.
    """
    parser = argparse.ArgumentParser(
        description="Extract and convert files from a PAK file based on catalog.json",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--pak",
        action="append",
        help="Path to PAK file(s). Can be specified multiple times for mod support.",
    )
    parser.add_argument(
        "--catalog",
        help="Path to catalog.json file (default: from database_builder.catalog_file setting)",
    )
    parser.add_argument(
        "--extractor-tool",
        help="Path to repak.exe (default: from database_builder.extractor_tool setting)",
    )
    parser.add_argument(
        "--converter-tool",
        help="Path to umodel.exe (default: from database_builder.converter_tool setting)",
    )
    parser.add_argument(
        "--output",
        help="Output directory for converted files",
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel operations (default: cpu count)",
    )
    parser.add_argument(
        "--filter-files",
        action="append",
        help="Extract only these specific file paths. Can be specified multiple times. "
        "Example: --filter-files 'War/Content/Icons/Icon1.uasset'",
    )
    parser.add_argument(
        "--filter-pattern",
        action="append",
        help="Extract only files matching this pattern (substring match). "
        "Can be specified multiple times. Example: --filter-pattern 'Subicons/'",
    )
    parser.add_argument("--log-file", type=Path, help="Path to log file (default: console only)")
    parser.add_argument(
        "--verbose", action="store_true", help="Enable verbose logging (debug level)"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress all output except errors and warnings. "
        "Only errors will be printed to console.",
    )
    args = parser.parse_args()

    # Setup logging
    settings = copy(get_settings())
    logging_settings = settings.logging
    # Setup logging
    if args.quiet:
        logging_settings.log_level = "WARNING"
    elif args.verbose:
        logging_settings.log_level = "DEBUG"

    logging_settings.log_file = args.log_file
    setup_logging(logging_settings)

    # Use settings as defaults
    catalog_file = args.catalog or (
        str(settings.database_builder.catalog_file)
        if settings.database_builder.catalog_file
        else DEFAULT_CATALOG
    )
    extractor_tool = args.extractor_tool or (
        str(settings.external_tools.repak) if settings.external_tools.repak else DEFAULT_EXTRACTOR
    )
    converter_tool = args.converter_tool or (
        str(settings.external_tools.umodel) if settings.external_tools.umodel else DEFAULT_CONVERTER
    )

    # Build filter_assets from CLI arguments
    filter_assets: set[str] | Callable[[str], bool] | None = None

    if args.filter_files or args.filter_pattern:
        if args.filter_files and not args.filter_pattern:
            # Only specific files - use set
            filter_assets = set(args.filter_files)
        elif args.filter_pattern and not args.filter_files:
            # Only patterns - use callable
            patterns = args.filter_pattern

            def pattern_filter(path: str) -> bool:
                return any(pattern in path for pattern in patterns)

            filter_assets = pattern_filter
        else:
            # Both specified - combine them
            specific_files = set(args.filter_files)
            patterns = args.filter_pattern

            def combined_filter(path: str) -> bool:
                return path in specific_files or any(pattern in path for pattern in patterns)

            filter_assets = combined_filter

    try:
        extractor = PakExtractor(
            pak_files=args.pak or DEFAULT_PAK_FILES,
            catalog_file=catalog_file,
            extractor_tool=extractor_tool,
            converter_tool=converter_tool,
            output_dir=args.output,
            filter_assets=filter_assets,
        )
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}")
        exit(1)

    success = await extractor.process_files(max_workers=args.workers)
    if not success:
        print("\nSome operations failed. Check the logs above for details.")
        exit(1)
    else:
        print("\nAll operations completed successfully!")
