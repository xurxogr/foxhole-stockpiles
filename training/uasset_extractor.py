import json
import logging
import multiprocessing
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


class PakExtractor:
    def __init__(
        self,
        pak_file: str = None,
        catalog_file: str = None,
        extractor_tool: str = None,
        converter_tool: str = None,
        output_dir: str = None,
        log_file: str = None,
    ):
        """
        Initialize the PAK extractor with default paths
        """
        # Set default paths
        default_pak = r"C:\Program Files (x86)\Steam\steamapps\common\Foxhole\War\Content\Paks\War-WindowsNoEditor.pak"
        default_catalog = os.path.join(os.getcwd(), "catalog.json")
        default_output = os.path.join(os.getcwd(), "output")
        default_extractor = r"C:\UnrealPakTool\Unrealpak.exe"
        default_converter = r"C:\UModel\umodel.exe"

        # Use provided paths or defaults
        self.pak_file = os.path.abspath(pak_file if pak_file else default_pak)
        self.catalog_file = catalog_file if catalog_file else default_catalog
        self.extractor_tool = os.path.abspath(
            extractor_tool if extractor_tool else default_extractor
        )
        self.converter_tool = os.path.abspath(
            converter_tool if converter_tool else default_converter
        )
        self.output_dir = os.path.abspath(output_dir if output_dir else default_output)

        # Setup logging
        self.setup_logging(log_file)
        self.logger = logging.getLogger(__name__)

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

    def setup_logging(self, log_file: str = None):
        """Setup logging configuration"""
        log_format = "%(asctime)s - %(levelname)s - %(message)s"
        if log_file:
            logging.basicConfig(
                level=logging.INFO,
                format=log_format,
                handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
            )
        else:
            logging.basicConfig(level=logging.INFO, format=log_format)

    def load_catalog(self) -> list | None:
        """Load and parse the catalog.json file"""
        try:
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.logger.error(f"Error parsing catalog file: {e}")
            return None
        except FileNotFoundError:
            self.logger.error(f"Catalog file not found: {self.catalog_file}")
            return None

    def convert_path(self, icon_path: str) -> str:
        """Convert .[0-9] endings to .uasset"""
        return re.sub(r"\.\d+$", ".uasset", icon_path)

    def extract_single_file(self, file_path: str, temp_dir: str) -> bool:
        """Extract a single file from the PAK file to temporary directory"""
        command = [
            self.extractor_tool,
            self.pak_file,
            "-Extract",
            temp_dir,
            f"-Filter={file_path}",
        ]

        try:
            self.logger.info(f"Extracting: {file_path}")
            process = subprocess.run(command, capture_output=True, text=True)

            if process.returncode == 0:
                self.logger.info(f"Successfully extracted: {file_path}")
                return True
            else:
                self.logger.error(f"Failed to extract {file_path}")
                self.logger.error(f"Error output: {process.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error extracting {file_path}: {e}")
            return False

    def convert_to_png(self, file_path: str, temp_dir: str) -> bool:
        """Convert extracted file to PNG using UModel"""
        try:
            # Convert paths to use OS-specific separators
            temp_path = Path(temp_dir)
            file_path_obj = Path(file_path)

            # Construct full path in temp directory using Path objects
            full_path = temp_path / file_path_obj
            full_path = str(full_path.absolute())

            # For .uasset files, convert using UModel
            command = [
                self.converter_tool,
                f"-path={temp_dir}",
                "-game=ue4.27",
                "-png",
                "-export",
                str(file_path_obj),
                "-out=" + str(temp_path) + "\\War\\Content\\",
            ]

            self.logger.info(f"Converting to PNG: {file_path}")
            process = subprocess.run(command, capture_output=True, text=True)

            if process.returncode == 0:
                # Handle the output path conversion
                png_name = file_path_obj.with_suffix(".png")
                converted_path = temp_path / png_name
                output_path = Path(self.output_dir) / png_name

                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Move the converted file if it exists
                if converted_path.exists():
                    shutil.move(str(converted_path), str(output_path))
                    self.logger.info(f"Successfully converted and moved: {png_name}")
                    return True
                else:
                    self.logger.error(
                        f"Converted file not found at expected path: {converted_path}"
                    )
                    return False
            else:
                self.logger.error(f"Failed to convert {file_path}")
                self.logger.error(f"Error output: {process.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error converting {file_path}: {e}")
            return False

    def get_files_to_extract(self) -> set[str]:
        """Get all unique files that need to be extracted from the catalog"""
        catalog_data = self.load_catalog()
        if not catalog_data:
            return set()

        files_to_extract = set()

        # Add the special UI file
        files_to_extract.add("War/Content/Textures/UI/Menus/IconFilterCrates.uasset")

        for item in catalog_data:
            # Add main Icon
            if "Icon" in item:
                original_path = item["Icon"]
                converted_path = self.convert_path(original_path)
                files_to_extract.add(converted_path)

            # Add SubTypeIcon
            if "SubTypeIcon" in item:
                original_path = item["SubTypeIcon"]
                converted_path = self.convert_path(original_path)
                files_to_extract.add(converted_path)

        self.logger.info(f"Found {len(files_to_extract)} unique files to process")
        return files_to_extract

    def process_files(self, max_workers: int = None) -> bool:
        """Extract and convert all files"""

        # Use CPU count if max_workers is not specified
        if max_workers is None:
            max_workers = multiprocessing.cpu_count()
            logging.info(f"Using {max_workers} workers based on CPU count")

        files_to_extract = self.get_files_to_extract()

        if not files_to_extract:
            logging.warning("No files found to extract")
            return False

        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            self.logger.info(f"Created temporary directory: {temp_dir}")

            # Extract files
            self.logger.info(f"Starting extraction of {len(files_to_extract)} files...")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                extract_results = list(
                    executor.map(
                        lambda f: self.extract_single_file(f, temp_dir),
                        files_to_extract,
                    )
                )

            successful_extractions = sum(1 for result in extract_results if result)
            failed_extractions = sum(1 for result in extract_results if not result)

            if failed_extractions > 0:
                self.logger.error(f"Failed to extract {failed_extractions} files")
                return False

            # Convert files
            self.logger.info("Starting conversion to PNG...")
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                convert_results = list(
                    executor.map(lambda f: self.convert_to_png(f, temp_dir), files_to_extract)
                )

            successful_conversions = sum(1 for result in convert_results if result)
            failed_conversions = sum(1 for result in convert_results if not result)

            # Log summary
            self.logger.info("\nProcessing Summary:")
            self.logger.info(f"Total files: {len(files_to_extract)}")
            self.logger.info(f"Successful extractions: {successful_extractions}")
            self.logger.info(f"Failed extractions: {failed_extractions}")
            self.logger.info(f"Successful conversions: {successful_conversions}")
            self.logger.info(f"Failed conversions: {failed_conversions}")

            return failed_extractions == 0 and failed_conversions == 0


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract and convert files from a PAK file based on catalog.json"
    )
    parser.add_argument(
        "--pak", help="Path to the PAK file (default: Foxhole War-WindowsNoEditor.pak)"
    )
    parser.add_argument("--catalog", help="Path to the catalog.json file (default: ./catalog.json)")
    parser.add_argument(
        "--extractor-tool",
        help="Path to UnrealPak.exe (default: C:\\UnrealPakTool\\Unrealpak.exe)",
    )
    parser.add_argument(
        "--converter-tool", help="Path to umodel.exe (default: C:\\UModel\\umodel.exe)"
    )
    parser.add_argument("--output", help="Output directory for converted files (default: ./output)")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel operations (default: cpu count)",
    )
    parser.add_argument("--logfile", help="Path to log file (default: console only)")

    args = parser.parse_args()

    extractor = PakExtractor(
        pak_file=args.pak,
        catalog_file=args.catalog,
        extractor_tool=args.extractor_tool,
        converter_tool=args.converter_tool,
        output_dir=args.output,
        log_file=args.logfile,
    )

    success = extractor.process_files(max_workers=args.workers)
    if not success:
        print("\nSome operations failed. Check the logs above for details.")
        exit(1)
    else:
        print("\nAll operations completed successfully!")


if __name__ == "__main__":
    main()
