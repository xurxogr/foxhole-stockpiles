"""Tests for commands.uasset_extractor.uasset_extractor module.

This module contains comprehensive tests for the UAsset extractor command,
including PAK file extraction, asset processing, run function behavior,
and error handling scenarios.
"""

import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import typer

from fs_tools.commands.uasset_extractor.uasset_extractor import (
    CRATE_ICON_PATH,
    SUBICONS_PATH_PREFIX,
    PakExtractor,
    run,
)
from fs_tools.models.pak_validation_result import PakValidationResult


class TestPakExtractorInitialization:
    """Test suite for PakExtractor initialization.

    This class contains tests for PakExtractor instance creation
    with various parameter combinations and configurations.
    """

    async def test_default_initialization(self) -> None:
        """Test PakExtractor with default values.

        Validates that the PakExtractor initializes correctly with
        default parameter values.
        """
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_file", return_value=True),
        ):
            extractor = PakExtractor()

            assert str(extractor.catalog_file).endswith("catalog.json")
            assert str(extractor.output_dir).endswith("output")
            assert isinstance(extractor.pak_files, list)

    async def test_custom_initialization(self, tmp_path: Path) -> None:
        """Test PakExtractor with custom values.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create mock files to satisfy validation
        catalog_file = tmp_path / "custom_catalog.json"
        catalog_file.write_text("[]")

        pak_file = tmp_path / "custom.pak"
        pak_file.touch()

        extractor_tool = tmp_path / "custom_repak.exe"
        extractor_tool.touch()

        converter_tool = tmp_path / "custom_umodel.exe"
        converter_tool.touch()

        catalog = str(catalog_file)
        pak = [str(pak_file)]
        extractor_tool_str = str(extractor_tool)
        converter_tool_str = str(converter_tool)
        output = str(tmp_path / "output")

        extractor = PakExtractor(
            catalog_file=catalog,
            pak_files=pak,
            extractor_tool=extractor_tool_str,
            converter_tool=converter_tool_str,
            output_dir=output,
        )

        assert str(extractor.catalog_file) == catalog
        assert extractor.pak_files == [Path(p).resolve() for p in pak]
        assert str(extractor.extractor_tool) == extractor_tool_str
        assert str(extractor.converter_tool) == converter_tool_str
        assert str(extractor.output_dir) == output

    async def test_multiple_pak_files(self) -> None:
        """Test PakExtractor with multiple PAK files.

        Validates that the extractor properly handles lists of PAK files.
        """
        pak_files = ["pak1.pak", "pak2.pak", "pak3.pak"]

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_file", return_value=True),
        ):
            extractor = PakExtractor(pak_files=pak_files)

            assert extractor.pak_files == [Path(p).resolve() for p in pak_files]
            assert isinstance(extractor.pak_files, list)
            assert len(extractor.pak_files) == 3


class TestPakExtractorMethods:
    """Test suite for PakExtractor methods.

    This class contains tests for the core functionality of PakExtractor
    including PAK extraction, asset processing, and parallel operations.
    """

    @pytest.fixture
    def extractor(self, tmp_path: Path) -> PakExtractor:
        """Create a PakExtractor instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.

        Returns:
            PakExtractor: Configured extractor instance for testing.
        """
        # Create mock files to satisfy validation
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")

        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        return PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=str(pak_file),
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
            output_dir=str(tmp_path / "output"),
        )

    async def test_extract_single_file_success(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test successful single file extraction.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        with patch.object(extractor, "extract_single_file") as mock_extract:
            mock_extract.return_value = True
            result = await extractor.extract_single_file(file_path, temp_dir)

        assert result is True

    async def test_extract_single_file_failure(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test failed single file extraction.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/nonexistent.uasset"
        temp_dir = str(tmp_path / "temp")

        with patch.object(extractor, "extract_single_file") as mock_extract:
            mock_extract.return_value = False
            result = await extractor.extract_single_file(file_path, temp_dir)

        assert result is False

    async def test_get_files_to_extract_no_catalog(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test getting files to extract when catalog doesn't exist.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        extractor.catalog_file = tmp_path / "nonexistent.json"

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = []
            result = extractor.get_files_to_extract()

        assert result == set()

    async def test_process_files_success(self, extractor: PakExtractor) -> None:
        """Test successful file processing.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        with patch.object(extractor, "get_files_to_extract") as mock_get_files:
            mock_get_files.return_value = {"War/Content/test1.uasset", "War/Content/test2.uasset"}

            with patch.object(extractor, "process_files") as mock_process:
                mock_process.return_value = True
                result = await extractor.process_files(max_workers=2)

        assert result is True


class TestPakExtractorValidation:
    """Test suite for PakExtractor validation.

    This class contains tests for input validation and error handling.
    """

    def test_init_empty_catalog_file(self) -> None:
        """Test initialization with empty catalog file path raises ValueError."""
        with pytest.raises(ValueError, match="catalog_file cannot be an empty string"):
            PakExtractor(catalog_file="")

    def test_init_empty_pak_files(self) -> None:
        """Test initialization with empty pak_files raises ValueError."""
        with pytest.raises(ValueError, match="pak_files cannot be empty"):
            PakExtractor(pak_files=[])

    def test_init_empty_extractor_tool(self) -> None:
        """Test initialization with empty extractor_tool raises ValueError."""
        with pytest.raises(ValueError, match="extractor_tool cannot be an empty string"):
            PakExtractor(extractor_tool="")

    def test_init_empty_converter_tool(self) -> None:
        """Test initialization with empty converter_tool raises ValueError."""
        with pytest.raises(ValueError, match="converter_tool cannot be an empty string"):
            PakExtractor(converter_tool="")

    def test_init_empty_output_dir(self) -> None:
        """Test initialization with empty output_dir raises ValueError."""
        with pytest.raises(ValueError, match="output_dir cannot be an empty string"):
            PakExtractor(output_dir="")

    def test_init_nonexistent_catalog(self, tmp_path: Path) -> None:
        """Test initialization with non-existent catalog raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        nonexistent = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError, match="Catalog file not found"):
            PakExtractor(catalog_file=str(nonexistent))

    def test_init_nonexistent_extractor_tool(self, tmp_path: Path) -> None:
        """Test initialization with non-existent extractor raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog = tmp_path / "catalog.json"
        catalog.write_text("[]")
        nonexistent_tool = tmp_path / "nonexistent.exe"

        with pytest.raises(FileNotFoundError, match="Tool not found"):
            PakExtractor(catalog_file=str(catalog), extractor_tool=str(nonexistent_tool))

    def test_init_nonexistent_converter_tool(self, tmp_path: Path) -> None:
        """Test initialization with non-existent converter raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog = tmp_path / "catalog.json"
        catalog.write_text("[]")
        extractor_tool = tmp_path / "extractor.exe"
        extractor_tool.touch()
        nonexistent_converter = tmp_path / "nonexistent.exe"

        with pytest.raises(FileNotFoundError, match="Tool not found"):
            PakExtractor(
                catalog_file=str(catalog),
                extractor_tool=str(extractor_tool),
                converter_tool=str(nonexistent_converter),
            )

    def test_init_nonexistent_pak_file(self, tmp_path: Path) -> None:
        """Test initialization with non-existent PAK file raises FileNotFoundError.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog = tmp_path / "catalog.json"
        catalog.write_text("[]")
        extractor_tool = tmp_path / "extractor.exe"
        extractor_tool.touch()
        converter_tool = tmp_path / "converter.exe"
        converter_tool.touch()
        nonexistent_pak = tmp_path / "nonexistent.pak"

        with pytest.raises(FileNotFoundError, match="PAK file not found"):
            PakExtractor(
                catalog_file=str(catalog),
                extractor_tool=str(extractor_tool),
                converter_tool=str(converter_tool),
                pak_files=str(nonexistent_pak),
            )


class TestGetFilesToExtract:
    """Test suite for get_files_to_extract method."""

    @pytest.fixture
    def extractor(self, tmp_path: Path) -> PakExtractor:
        """Create a PakExtractor instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.

        Returns:
            PakExtractor: Configured extractor instance for testing.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()
        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()
        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        return PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=str(pak_file),
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
            output_dir=str(tmp_path / "output"),
        )

    def test_get_files_with_empty_catalog(self, extractor: PakExtractor) -> None:
        """Test get_files_to_extract with empty catalog.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = []
            result = extractor.get_files_to_extract()

        assert result == set()

    def test_get_files_with_items_without_icon_path(self, extractor: PakExtractor) -> None:
        """Test get_files_to_extract with items missing icon_path.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        from foxhole_stockpiles.models.catalog_item import CatalogItem

        mock_item = Mock(spec=CatalogItem)
        mock_item.code = "TEST001"
        mock_item.icon_path = None
        mock_item.subicon_path = None

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = [mock_item]
            result = extractor.get_files_to_extract()

        # Should only contain the crate icon
        assert len(result) == 1
        assert "War/Content/Textures/UI/Menus/IconFilterCrates.uasset" in result

    def test_get_files_with_subicon_path(self, extractor: PakExtractor) -> None:
        """Test get_files_to_extract with items having subicon_path.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        from foxhole_stockpiles.models.catalog_item import CatalogItem

        mock_item = Mock(spec=CatalogItem)
        mock_item.code = "TEST001"
        mock_item.icon_path = "War/Content/Icons/MainIcon"
        mock_item.subicon_path = "War/Content/Icons/SubIcon"

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = [mock_item]
            result = extractor.get_files_to_extract()

        assert "War/Content/Icons/MainIcon.uasset" in result
        assert "War/Content/Icons/SubIcon.uasset" in result
        assert "War/Content/Textures/UI/Menus/IconFilterCrates.uasset" in result


class TestExtractSingleFile:
    """Test suite for extract_single_file method."""

    @pytest.fixture
    def extractor(self, tmp_path: Path) -> PakExtractor:
        """Create a PakExtractor instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.

        Returns:
            PakExtractor: Configured extractor instance for testing.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()
        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()
        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        return PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=str(pak_file),
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
            output_dir=str(tmp_path / "output"),
        )

    async def test_extract_file_with_exception(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test extract_single_file when subprocess raises exception.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        mock_subprocess = MagicMock(side_effect=RuntimeError("Subprocess error"))
        with patch("asyncio.create_subprocess_exec", mock_subprocess):
            result = await extractor.extract_single_file(file_path, temp_dir)

        assert result is False

    async def test_extract_file_successful_extraction(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test extract_single_file with successful extraction.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        # Create the expected extraction structure
        pak_name = extractor.pak_files[0].stem
        pak_extract_dir = Path(temp_dir) / pak_name
        pak_extract_dir.mkdir(parents=True)
        extracted_file = pak_extract_dir / file_path
        extracted_file.parent.mkdir(parents=True, exist_ok=True)
        extracted_file.touch()

        # Mock subprocess to return success (returncode 0)
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await extractor.extract_single_file(file_path, temp_dir)

        assert result is True

    async def test_extract_file_not_found_in_pak(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test extract_single_file when file not found in PAK.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/nonexistent.uasset"
        temp_dir = str(tmp_path / "temp")

        # Create temp dir but don't create the file
        Path(temp_dir).mkdir(parents=True, exist_ok=True)

        # Mock subprocess to return success but file doesn't exist
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await extractor.extract_single_file(file_path, temp_dir)

        assert result is False

    async def test_extract_file_non_zero_returncode(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test extract_single_file with non-zero returncode.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        # Mock subprocess to return failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"error")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await extractor.extract_single_file(file_path, temp_dir)

        assert result is False


class TestConvertToPng:
    """Test suite for convert_to_png method."""

    @pytest.fixture
    def extractor(self, tmp_path: Path) -> PakExtractor:
        """Create a PakExtractor instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.

        Returns:
            PakExtractor: Configured extractor instance for testing.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()
        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()
        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        return PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=str(pak_file),
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
            output_dir=str(tmp_path / "output"),
        )

    async def test_convert_to_png_failure(self, extractor: PakExtractor, tmp_path: Path) -> None:
        """Test convert_to_png when conversion fails.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        with patch.object(extractor, "_try_convert_with_version", return_value=False):
            result = await extractor.convert_to_png(file_path, temp_dir)

        assert result is False

    async def test_try_convert_file_not_found(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test _try_convert_with_version when extracted file not found.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")
        Path(temp_dir).mkdir(parents=True, exist_ok=True)

        result = await extractor._try_convert_with_version(file_path, temp_dir)

        assert result is False

    async def test_try_convert_with_exception(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test _try_convert_with_version when subprocess raises exception.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        # Create a pak directory structure
        pak_dir = Path(temp_dir) / "test"
        pak_dir.mkdir(parents=True)
        (pak_dir / file_path).parent.mkdir(parents=True, exist_ok=True)
        (pak_dir / file_path).touch()

        mock_subprocess = MagicMock(side_effect=RuntimeError("Conversion error"))
        with patch("asyncio.create_subprocess_exec", mock_subprocess):
            result = await extractor._try_convert_with_version(file_path, temp_dir)

        assert result is False

    async def test_try_convert_success(self, extractor: PakExtractor, tmp_path: Path) -> None:
        """Test _try_convert_with_version with successful conversion.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        # Create a pak directory structure
        pak_dir = Path(temp_dir) / "test"
        pak_dir.mkdir(parents=True)
        (pak_dir / file_path).parent.mkdir(parents=True, exist_ok=True)
        (pak_dir / file_path).touch()

        # Create the expected output PNG file
        png_path = pak_dir / "War/Content/test.png"
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.touch()

        # Mock subprocess to return success
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await extractor._try_convert_with_version(file_path, temp_dir)

        assert result is True

    async def test_try_convert_file_not_created(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test _try_convert_with_version when output PNG not created.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        # Create a pak directory structure
        pak_dir = Path(temp_dir) / "test"
        pak_dir.mkdir(parents=True)
        (pak_dir / file_path).parent.mkdir(parents=True, exist_ok=True)
        (pak_dir / file_path).touch()

        # Don't create the PNG file

        # Mock subprocess to return success but no PNG created
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await extractor._try_convert_with_version(file_path, temp_dir)

        assert result is False

    async def test_try_convert_non_zero_returncode(
        self, extractor: PakExtractor, tmp_path: Path
    ) -> None:
        """Test _try_convert_with_version with non-zero returncode.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        # Create a pak directory structure
        pak_dir = Path(temp_dir) / "test"
        pak_dir.mkdir(parents=True)
        (pak_dir / file_path).parent.mkdir(parents=True, exist_ok=True)
        (pak_dir / file_path).touch()

        # Mock subprocess to return failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"error")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await extractor._try_convert_with_version(file_path, temp_dir)

        assert result is False

    async def test_convert_to_png_success(self, extractor: PakExtractor, tmp_path: Path) -> None:
        """Test convert_to_png with successful conversion.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        file_path = "War/Content/test.uasset"
        temp_dir = str(tmp_path / "temp")

        with patch.object(extractor, "_try_convert_with_version", return_value=True):
            result = await extractor.convert_to_png(file_path, temp_dir)

        assert result is True


class TestProcessFiles:
    """Test suite for process_files method."""

    @pytest.fixture
    def extractor(self, tmp_path: Path) -> PakExtractor:
        """Create a PakExtractor instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.

        Returns:
            PakExtractor: Configured extractor instance for testing.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()
        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()
        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        return PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=str(pak_file),
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
            output_dir=str(tmp_path / "output"),
        )

    async def test_process_files_no_files_to_extract(self, extractor: PakExtractor) -> None:
        """Test process_files when no files need extraction.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        with patch.object(extractor, "get_files_to_extract", return_value=set()):
            result = await extractor.process_files()

        assert result is False

    async def test_process_files_all_extractions_fail(self, extractor: PakExtractor) -> None:
        """Test process_files when all extractions fail.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        with patch.object(
            extractor, "get_files_to_extract", return_value={"file1.uasset", "file2.uasset"}
        ):
            with patch.object(extractor, "extract_single_file", return_value=False):
                result = await extractor.process_files()

        assert result is False

    async def test_process_files_with_successful_conversions(self, extractor: PakExtractor) -> None:
        """Test process_files with successful extractions and conversions.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        with patch.object(
            extractor, "get_files_to_extract", return_value={"file1.uasset", "file2.uasset"}
        ):
            with patch.object(extractor, "extract_single_file", return_value=True):
                with patch.object(extractor, "convert_to_png", return_value=True):
                    result = await extractor.process_files(max_workers=2)

        assert result is True

    async def test_process_files_partial_conversions(self, extractor: PakExtractor) -> None:
        """Test process_files when some conversions succeed.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        files = ["file1.uasset", "file2.uasset"]
        with patch.object(extractor, "get_files_to_extract", return_value=set(files)):
            with patch.object(extractor, "extract_single_file", return_value=True):
                # First conversion succeeds, second fails
                with patch.object(extractor, "convert_to_png", side_effect=[True, False]):
                    result = await extractor.process_files(max_workers=2)

        # Should still return True if at least one conversion succeeded
        assert result is True


class TestRunFunction:
    """Test suite for the run CLI function.

    This class contains tests for the run entry point of the uasset
    extractor command, including argument handling and workflow execution.
    """

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    async def test_run_with_default_args(self, mock_setup_logging: Mock) -> None:
        """Test run function with default arguments.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            instance = MagicMock()
            process_files_mock = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                """Mock process_files method."""
                process_files_mock(*args, **kwargs)
                return True

            instance.process_files = mock_process_files
            mock_extractor.return_value = instance

            await run(
                catalog="catalog.json",
                pak=None,
                extractor_tool="C:\\repak\\repak.exe",
                converter_tool="C:\\UModel\\umodel.exe",
                output="output",
                log_file=None,
                verbose=False,
                quiet=False,
                workers=None,
                filter_files=None,
                filter_pattern=None,
            )

            mock_extractor.assert_called_once()
            process_files_mock.assert_called_once()

    @patch("fs_tools.commands.uasset_extractor.uasset_extractor.setup_logging")
    async def test_run_with_verbose_logging(self, mock_setup_logging: Mock) -> None:
        """Test run function with verbose logging enabled.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            mock_instance = MagicMock()
            process_files_mock = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                process_files_mock(*args, **kwargs)
                return True

            mock_instance.process_files = mock_process_files
            mock_extractor.return_value = mock_instance

            await run(
                catalog="catalog.json",
                pak=["custom.pak"],
                extractor_tool="repak.exe",
                converter_tool="umodel.exe",
                output="output",
                log_file=Path("test.log"),
                verbose=True,
                quiet=False,
                workers=None,
                filter_files=None,
                filter_pattern=None,
            )

            # Verify verbose logging was set up
            mock_setup_logging.assert_called_once()

    @patch("fs_tools.commands.uasset_extractor.uasset_extractor.setup_logging")
    async def test_run_with_quiet_logging(self, mock_setup_logging: Mock) -> None:
        """Test run function with quiet logging enabled.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            instance = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                return True

            instance.process_files = mock_process_files
            mock_extractor.return_value = instance

            await run(
                catalog="catalog.json",
                pak=None,
                extractor_tool="C:\\repak\\repak.exe",
                converter_tool="C:\\UModel\\umodel.exe",
                output="output",
                log_file=None,
                verbose=False,
                quiet=True,
                workers=None,
                filter_files=None,
                filter_pattern=None,
            )

            # Verify logging was set up
            mock_setup_logging.assert_called_once()

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    async def test_run_with_multiple_pak_files(self, mock_setup_logging: Mock) -> None:
        """Test run function with multiple PAK files.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        pak_files = ["pak1.pak", "pak2.pak", "pak3.pak"]

        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            mock_instance = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                return True

            mock_instance.process_files = mock_process_files
            mock_extractor.return_value = mock_instance

            await run(
                catalog="catalog.json",
                pak=pak_files,
                extractor_tool="repak.exe",
                converter_tool="umodel.exe",
                output="output",
                log_file=None,
                verbose=False,
                quiet=False,
                workers=None,
                filter_files=None,
                filter_pattern=None,
            )

            # Verify PakExtractor was called with multiple PAK files
            call_args = mock_extractor.call_args
            assert call_args[1]["pak_files"] == pak_files

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    @patch("builtins.print")
    async def test_run_initialization_error(
        self, mock_print: Mock, mock_setup_logging: Mock
    ) -> None:
        """Test run function handles initialization errors.

        Args:
            mock_print (Mock): Mocked print function.
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor",
            side_effect=ValueError("Initialization error"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                await run(
                    catalog="catalog.json",
                    pak=None,
                    extractor_tool="C:\\repak\\repak.exe",
                    converter_tool="C:\\UModel\\umodel.exe",
                    output="output",
                    log_file=None,
                    verbose=False,
                    quiet=False,
                    workers=None,
                    filter_files=None,
                    filter_pattern=None,
                )

            # Verify error was printed and exit code is 1
            mock_print.assert_called()
            assert exc_info.value.exit_code == 1

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    @patch("builtins.print")
    async def test_run_file_not_found_error(
        self, mock_print: Mock, mock_setup_logging: Mock
    ) -> None:
        """Test run function handles file not found errors.

        Args:
            mock_print (Mock): Mocked print function.
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor",
            side_effect=FileNotFoundError("File not found"),
        ):
            with pytest.raises(typer.Exit) as exc_info:
                await run(
                    catalog="catalog.json",
                    pak=None,
                    extractor_tool="C:\\repak\\repak.exe",
                    converter_tool="C:\\UModel\\umodel.exe",
                    output="output",
                    log_file=None,
                    verbose=False,
                    quiet=False,
                    workers=None,
                    filter_files=None,
                    filter_pattern=None,
                )

            # Verify error was printed and exit code is 1
            mock_print.assert_called()
            assert exc_info.value.exit_code == 1

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    @patch("builtins.print")
    async def test_run_process_files_failure(
        self, mock_print: Mock, mock_setup_logging: Mock
    ) -> None:
        """Test run function handles process_files failure.

        Args:
            mock_print (Mock): Mocked print function.
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            instance = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                return False

            instance.process_files = mock_process_files
            mock_extractor.return_value = instance

            with pytest.raises(typer.Exit) as exc_info:
                await run(
                    catalog="catalog.json",
                    pak=None,
                    extractor_tool="C:\\repak\\repak.exe",
                    converter_tool="C:\\UModel\\umodel.exe",
                    output="output",
                    log_file=None,
                    verbose=False,
                    quiet=False,
                    workers=None,
                    filter_files=None,
                    filter_pattern=None,
                )

            # Verify failure message was printed and exit code is 1
            mock_print.assert_called()
            assert exc_info.value.exit_code == 1

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    async def test_run_with_filter_files(self, mock_setup_logging: Mock) -> None:
        """Test run function with filter-files argument.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            instance = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                return True

            instance.process_files = mock_process_files
            mock_extractor.return_value = instance

            await run(
                catalog="catalog.json",
                pak=None,
                extractor_tool="C:\\repak\\repak.exe",
                converter_tool="C:\\UModel\\umodel.exe",
                output="output",
                log_file=None,
                verbose=False,
                quiet=False,
                workers=None,
                filter_files=["War/Content/Icons/Icon1.uasset", "War/Content/Icons/Icon2.uasset"],
                filter_pattern=None,
            )

            # Verify PakExtractor was called with filter_assets as a set
            call_kwargs = mock_extractor.call_args[1]
            assert call_kwargs["filter_assets"] is not None
            assert isinstance(call_kwargs["filter_assets"], set)

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    async def test_run_with_filter_pattern(self, mock_setup_logging: Mock) -> None:
        """Test run function with filter-pattern argument.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            instance = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                return True

            instance.process_files = mock_process_files
            mock_extractor.return_value = instance

            await run(
                catalog="catalog.json",
                pak=None,
                extractor_tool="C:\\repak\\repak.exe",
                converter_tool="C:\\UModel\\umodel.exe",
                output="output",
                log_file=None,
                verbose=False,
                quiet=False,
                workers=None,
                filter_files=None,
                filter_pattern=["Subicons/"],
            )

            # Verify PakExtractor was called with filter_assets as a callable
            call_kwargs = mock_extractor.call_args[1]
            assert call_kwargs["filter_assets"] is not None
            assert callable(call_kwargs["filter_assets"])

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    async def test_run_with_combined_filters(self, mock_setup_logging: Mock) -> None:
        """Test run function with both filter-files and filter-pattern.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            instance = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                return True

            instance.process_files = mock_process_files
            mock_extractor.return_value = instance

            await run(
                catalog="catalog.json",
                pak=None,
                extractor_tool="C:\\repak\\repak.exe",
                converter_tool="C:\\UModel\\umodel.exe",
                output="output",
                log_file=None,
                verbose=False,
                quiet=False,
                workers=None,
                filter_files=["War/Content/Textures/UI/Menus/IconFilterCrates.uasset"],
                filter_pattern=["Subicons/"],
            )

            # Verify PakExtractor was called with filter_assets as a callable
            call_kwargs = mock_extractor.call_args[1]
            assert call_kwargs["filter_assets"] is not None
            assert callable(call_kwargs["filter_assets"])
            # Test that the filter works correctly
            filter_func = call_kwargs["filter_assets"]
            assert filter_func("War/Content/Textures/UI/Menus/IconFilterCrates.uasset") is True
            assert filter_func("War/Content/Icons/Subicons/Ammo.uasset") is True
            assert filter_func("War/Content/Icons/MainIcon.uasset") is False

    @patch("foxhole_stockpiles.core.logging.setup_logging")
    @patch("builtins.print")
    async def test_run_process_files_success(
        self, mock_print: Mock, mock_setup_logging: Mock
    ) -> None:
        """Test run function with successful process_files.

        Args:
            mock_print (Mock): Mocked print function.
            mock_setup_logging (Mock): Mocked setup_logging function.
        """
        with patch(
            "fs_tools.commands.uasset_extractor.uasset_extractor.PakExtractor"
        ) as mock_extractor:
            instance = MagicMock()

            async def mock_process_files(*args: Any, **kwargs: Any) -> bool:
                return True

            instance.process_files = mock_process_files
            mock_extractor.return_value = instance

            await run(
                catalog="catalog.json",
                pak=None,
                extractor_tool="C:\\repak\\repak.exe",
                converter_tool="C:\\UModel\\umodel.exe",
                output="output",
                log_file=None,
                verbose=False,
                quiet=False,
                workers=None,
                filter_files=None,
                filter_pattern=None,
            )

            # Verify success message was printed
            assert any("success" in str(call).lower() for call in mock_print.call_args_list)


class TestFilterAssets:
    """Test suite for filter_assets functionality."""

    @pytest.fixture
    def extractor(self, tmp_path: Path) -> PakExtractor:
        """Create a PakExtractor instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.

        Returns:
            PakExtractor: Configured extractor instance for testing.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()
        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()
        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        return PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=str(pak_file),
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
            output_dir=str(tmp_path / "output"),
        )

    def test_filter_assets_with_set(self, extractor: PakExtractor) -> None:
        """Test filter_assets with a set of file paths.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        from foxhole_stockpiles.models.catalog_item import CatalogItem

        mock_item1 = Mock(spec=CatalogItem)
        mock_item1.code = "TEST001"
        mock_item1.icon_path = "War/Content/Icons/Icon1"
        mock_item1.subicon_path = "War/Content/Icons/SubIcon1"

        mock_item2 = Mock(spec=CatalogItem)
        mock_item2.code = "TEST002"
        mock_item2.icon_path = "War/Content/Icons/Icon2"
        mock_item2.subicon_path = None

        # Set filter to only include Icon1 and crate icon
        extractor.filter_assets = {
            "War/Content/Icons/Icon1.uasset",
            "War/Content/Textures/UI/Menus/IconFilterCrates.uasset",
        }

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = [mock_item1, mock_item2]
            result = extractor.get_files_to_extract()

        # Should only contain Icon1 and crate icon, not Icon2 or SubIcon1
        assert "War/Content/Icons/Icon1.uasset" in result
        assert "War/Content/Textures/UI/Menus/IconFilterCrates.uasset" in result
        assert "War/Content/Icons/Icon2.uasset" not in result
        assert "War/Content/Icons/SubIcon1.uasset" not in result
        assert len(result) == 2

    def test_filter_assets_with_callable(self, extractor: PakExtractor) -> None:
        """Test filter_assets with a callable filter function.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        from foxhole_stockpiles.models.catalog_item import CatalogItem

        mock_item1 = Mock(spec=CatalogItem)
        mock_item1.code = "TEST001"
        mock_item1.icon_path = "War/Content/Icons/MainIcon"
        mock_item1.subicon_path = "War/Content/Icons/SubIcon"

        mock_item2 = Mock(spec=CatalogItem)
        mock_item2.code = "TEST002"
        mock_item2.icon_path = "War/Content/OtherIcons/Icon"
        mock_item2.subicon_path = None

        # Filter to only include files with "SubIcon" or "Crates" in path
        def filter_func(file_path: str) -> bool:
            return "SubIcon" in file_path or "Crates" in file_path

        extractor.filter_assets = filter_func

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = [mock_item1, mock_item2]
            result = extractor.get_files_to_extract()

        # Should only contain SubIcon and crate icon
        assert "War/Content/Icons/SubIcon.uasset" in result
        assert "War/Content/Textures/UI/Menus/IconFilterCrates.uasset" in result
        assert "War/Content/Icons/MainIcon.uasset" not in result
        assert "War/Content/OtherIcons/Icon.uasset" not in result
        assert len(result) == 2

    def test_filter_assets_none_returns_all(self, extractor: PakExtractor) -> None:
        """Test that filter_assets=None returns all catalog files.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        from foxhole_stockpiles.models.catalog_item import CatalogItem

        mock_item = Mock(spec=CatalogItem)
        mock_item.code = "TEST001"
        mock_item.icon_path = "War/Content/Icons/Icon"
        mock_item.subicon_path = "War/Content/Icons/SubIcon"

        extractor.filter_assets = None

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = [mock_item]
            result = extractor.get_files_to_extract()

        # Should contain all files
        assert "War/Content/Icons/Icon.uasset" in result
        assert "War/Content/Icons/SubIcon.uasset" in result
        assert "War/Content/Textures/UI/Menus/IconFilterCrates.uasset" in result
        assert len(result) == 3

    def test_filter_assets_empty_set_returns_none(self, extractor: PakExtractor) -> None:
        """Test that empty filter set returns no files.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        from foxhole_stockpiles.models.catalog_item import CatalogItem

        mock_item = Mock(spec=CatalogItem)
        mock_item.code = "TEST001"
        mock_item.icon_path = "War/Content/Icons/Icon"
        mock_item.subicon_path = None

        extractor.filter_assets = set()

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = [mock_item]
            result = extractor.get_files_to_extract()

        # Should return empty set
        assert len(result) == 0

    def test_filter_assets_callable_returns_all_false(self, extractor: PakExtractor) -> None:
        """Test callable filter that returns False for all files.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        from foxhole_stockpiles.models.catalog_item import CatalogItem

        mock_item = Mock(spec=CatalogItem)
        mock_item.code = "TEST001"
        mock_item.icon_path = "War/Content/Icons/Icon"
        mock_item.subicon_path = None

        # Filter that rejects everything
        extractor.filter_assets = lambda x: False

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = [mock_item]
            result = extractor.get_files_to_extract()

        # Should return empty set
        assert len(result) == 0

    def test_filter_assets_with_subicons_only(self, extractor: PakExtractor) -> None:
        """Test filtering to extract only subicons and crate icon.

        Args:
            extractor (PakExtractor): PakExtractor instance from fixture.
        """
        from foxhole_stockpiles.models.catalog_item import CatalogItem

        mock_item1 = Mock(spec=CatalogItem)
        mock_item1.code = "TEST001"
        mock_item1.icon_path = "War/Content/Icons/MainIcon1"
        mock_item1.subicon_path = "War/Content/Icons/Subicons/Ammo"

        mock_item2 = Mock(spec=CatalogItem)
        mock_item2.code = "TEST002"
        mock_item2.icon_path = "War/Content/Icons/MainIcon2"
        mock_item2.subicon_path = "War/Content/Icons/Subicons/Fuel"

        # Filter for subicons and crate only (use case for vanilla dependency extraction)
        def subicons_filter(file_path: str) -> bool:
            return "Subicons/" in file_path or "Crates" in file_path

        extractor.filter_assets = subicons_filter

        with patch("fs_tools.commands.uasset_extractor.uasset_extractor.load_catalog") as mock_load:
            mock_load.return_value = [mock_item1, mock_item2]
            result = extractor.get_files_to_extract()

        # Should only contain subicons and crate icon
        assert "War/Content/Icons/Subicons/Ammo.uasset" in result
        assert "War/Content/Icons/Subicons/Fuel.uasset" in result
        assert "War/Content/Textures/UI/Menus/IconFilterCrates.uasset" in result
        assert "War/Content/Icons/MainIcon1.uasset" not in result
        assert "War/Content/Icons/MainIcon2.uasset" not in result
        assert len(result) == 3


class TestWSLPathConversion:
    """Test suite for WSL path conversion functionality.

    This class contains tests for WSL path detection, conversion,
    and Windows tool compatibility.
    """

    def test_detect_windows_tools_with_exe_files(self, tmp_path: Path) -> None:
        """Test detection of Windows tools based on .exe extension.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()

        extractor = PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=[str(pak_file)],
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
        )

        assert extractor._extractor_is_windows is True
        assert extractor._converter_is_windows is True

    def test_detect_linux_tools(self, tmp_path: Path) -> None:
        """Test detection of Linux/native tools without .exe extension.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        extractor_tool = tmp_path / "repak"
        extractor_tool.touch()

        converter_tool = tmp_path / "umodel"
        converter_tool.touch()

        extractor = PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=[str(pak_file)],
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
        )

        assert extractor._extractor_is_windows is False
        assert extractor._converter_is_windows is False

    def test_detect_windows_tools_with_mnt_paths(self, tmp_path: Path) -> None:
        """Test detection of Windows tools in /mnt/ paths.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_file", return_value=True),
        ):
            extractor = PakExtractor(
                catalog_file=str(catalog_file),
                extractor_tool="/mnt/c/tools/repak.exe",
                converter_tool="/mnt/c/tools/umodel.exe",
            )

            assert extractor._extractor_is_windows is True
            assert extractor._converter_is_windows is True

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_get_wsl_temp_dir_not_in_wsl(self, mock_open: Mock) -> None:
        """Test _get_wsl_temp_dir when not running in WSL.

        Args:
            mock_open (Mock): Mocked open function.
        """
        result = PakExtractor._get_wsl_temp_dir()
        assert result is None

    @patch("builtins.open")
    def test_get_wsl_temp_dir_not_microsoft(self, mock_open: Mock) -> None:
        """Test _get_wsl_temp_dir when /proc/version doesn't contain 'microsoft'.

        Args:
            mock_open (Mock): Mocked open function.
        """
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.15.0"
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        result = PakExtractor._get_wsl_temp_dir()
        assert result is None

    @patch("subprocess.run")
    @patch("builtins.open")
    def test_get_wsl_temp_dir_empty_temp(self, mock_open: Mock, mock_run: Mock) -> None:
        """Test _get_wsl_temp_dir when Windows TEMP is empty.

        Args:
            mock_open (Mock): Mocked open function.
            mock_run (Mock): Mocked subprocess.run function.
        """
        # Mock /proc/version to indicate WSL
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.15.0-microsoft-standard"
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        # Mock powershell returning empty string
        mock_run.return_value = MagicMock(stdout="")

        result = PakExtractor._get_wsl_temp_dir()
        assert result is None

    @patch("subprocess.run")
    @patch("builtins.open")
    def test_get_wsl_temp_dir_subprocess_exception(self, mock_open: Mock, mock_run: Mock) -> None:
        """Test _get_wsl_temp_dir when subprocess raises exception.

        Args:
            mock_open (Mock): Mocked open function.
            mock_run (Mock): Mocked subprocess.run function.
        """
        # Mock /proc/version to indicate WSL
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.15.0-microsoft-standard"
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        # Mock subprocess raising exception
        mock_run.side_effect = subprocess.SubprocessError("Command failed")

        result = PakExtractor._get_wsl_temp_dir()
        assert result is None

    @patch("builtins.open", side_effect=FileNotFoundError)
    def test_convert_wsl_path_not_in_wsl(self, mock_open: Mock) -> None:
        """Test _convert_wsl_path_to_windows when not in WSL.

        Args:
            mock_open (Mock): Mocked open used by the WSL detection check.
        """
        path = "/home/user/file.txt"
        result = PakExtractor._convert_wsl_path_to_windows(path)
        assert result == path

    @patch("builtins.open")
    def test_convert_wsl_path_mnt_c(self, mock_open: Mock) -> None:
        """Test _convert_wsl_path_to_windows with /mnt/c/ path.

        Args:
            mock_open (Mock): Mocked open function.
        """
        # Mock /proc/version to indicate WSL
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.15.0-microsoft-standard"
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        path = "/mnt/c/Users/test/file.txt"
        result = PakExtractor._convert_wsl_path_to_windows(path)
        assert result == "C:\\Users\\test\\file.txt"

    @patch("builtins.open")
    def test_convert_wsl_path_mnt_d(self, mock_open: Mock) -> None:
        """Test _convert_wsl_path_to_windows with /mnt/d/ path.

        Args:
            mock_open (Mock): Mocked open function.
        """
        # Mock /proc/version to indicate WSL
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.15.0-microsoft-standard"
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        path = "/mnt/d/data/file.txt"
        result = PakExtractor._convert_wsl_path_to_windows(path)
        assert result == "D:\\data\\file.txt"

    @patch("builtins.open")
    def test_convert_wsl_path_mnt_only_drive(self, mock_open: Mock) -> None:
        """Test _convert_wsl_path_to_windows with /mnt/c only (no path after drive).

        Args:
            mock_open (Mock): Mocked open function.
        """
        # Mock /proc/version to indicate WSL
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.15.0-microsoft-standard"
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        path = "/mnt/c"
        result = PakExtractor._convert_wsl_path_to_windows(path)
        assert result == "C:\\"

    @patch("subprocess.run")
    @patch("builtins.open")
    def test_convert_wsl_path_wslpath_success(self, mock_open: Mock, mock_run: Mock) -> None:
        """Test _convert_wsl_path_to_windows using wslpath command.

        Args:
            mock_open (Mock): Mocked open function.
            mock_run (Mock): Mocked subprocess.run function.
        """
        # Mock /proc/version to indicate WSL
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.15.0-microsoft-standard"
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        # Mock wslpath success
        mock_run.return_value = MagicMock(stdout="C:\\Users\\test\\file.txt\n")

        path = "/home/user/file.txt"
        result = PakExtractor._convert_wsl_path_to_windows(path)
        assert result == "C:\\Users\\test\\file.txt"

    @patch("subprocess.run")
    @patch("builtins.open")
    def test_convert_wsl_path_wslpath_exception(self, mock_open: Mock, mock_run: Mock) -> None:
        """Test _convert_wsl_path_to_windows when wslpath fails.

        Args:
            mock_open (Mock): Mocked open function.
            mock_run (Mock): Mocked subprocess.run function.
        """
        # Mock /proc/version to indicate WSL
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.15.0-microsoft-standard"
        mock_file.__enter__.return_value = mock_file
        mock_open.return_value = mock_file

        # Mock wslpath raising exception
        mock_run.side_effect = FileNotFoundError("wslpath not found")

        path = "/home/user/file.txt"
        result = PakExtractor._convert_wsl_path_to_windows(path)
        # Should return original path when wslpath fails
        assert result == path

    async def test_extract_single_file_with_linux_tools(self, tmp_path: Path) -> None:
        """Test extract_single_file path format with Linux/native tools.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        # Use non-.exe tools to trigger Linux path
        extractor_tool = tmp_path / "repak"
        extractor_tool.touch()

        converter_tool = tmp_path / "umodel"
        converter_tool.touch()

        extractor = PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=[str(pak_file)],
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
        )

        # Verify Linux tools are detected
        assert extractor._extractor_is_windows is False
        assert extractor._converter_is_windows is False

        # Mock subprocess to capture command
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            # Create the expected output directory structure
            pak_dir = tmp_path / "test"
            pak_dir.mkdir()
            output_file = pak_dir / "War" / "Content" / "test.uasset"
            output_file.parent.mkdir(parents=True)
            output_file.touch()

            await extractor.extract_single_file(
                file_path="War/Content/test.uasset", temp_dir=str(tmp_path)
            )

            # Verify command used Linux-style path separator (ends with /)
            call_args = mock_subprocess.call_args[0][0]
            # The output dir should end with /
            assert any(arg.endswith("/") for arg in call_args if isinstance(arg, str))

    async def test_extract_single_file_process_cleanup_on_error(self, tmp_path: Path) -> None:
        """Test extract_single_file cleans up process on error.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()

        extractor = PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=[str(pak_file)],
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
        )

        # Mock subprocess with hanging process
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(side_effect=Exception("Error"))
            mock_process.returncode = None  # Still running
            mock_process.terminate = AsyncMock()
            mock_process.wait = AsyncMock()
            mock_subprocess.return_value = mock_process

            result = await extractor.extract_single_file(
                file_path="War/Content/test.uasset", temp_dir=str(tmp_path)
            )

            # Should fail and clean up
            assert result is False
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once()

    def test_try_convert_with_version_linux_tools(self, tmp_path: Path) -> None:
        """Test Linux tools detection for _try_convert_with_version.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        # Use non-.exe tools to trigger Linux path
        extractor_tool = tmp_path / "repak"
        extractor_tool.touch()

        converter_tool = tmp_path / "umodel"
        converter_tool.touch()

        extractor = PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=[str(pak_file)],
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
        )

        # Verify Linux tools are detected (which affects path format in convert)
        assert extractor._extractor_is_windows is False
        assert extractor._converter_is_windows is False

    async def test_try_convert_with_version_process_cleanup(self, tmp_path: Path) -> None:
        """Test _try_convert_with_version cleans up process on error.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_file = tmp_path / "catalog.json"
        catalog_file.write_text("[]")

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        converter_tool = tmp_path / "umodel.exe"
        converter_tool.touch()

        extractor = PakExtractor(
            catalog_file=str(catalog_file),
            pak_files=[str(pak_file)],
            extractor_tool=str(extractor_tool),
            converter_tool=str(converter_tool),
        )

        # Create extracted file structure
        pak_dir = tmp_path / "TestPak"
        pak_dir.mkdir()
        test_file = pak_dir / "War" / "Content" / "test.uasset"
        test_file.parent.mkdir(parents=True)
        test_file.touch()

        # Mock subprocess with hanging process
        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(side_effect=Exception("Error"))
            mock_process.returncode = None  # Still running
            mock_process.terminate = AsyncMock()
            mock_process.wait = AsyncMock()
            mock_subprocess.return_value = mock_process

            result = await extractor._try_convert_with_version(
                file_path="War/Content/test.uasset", temp_dir=str(tmp_path)
            )

            # Should fail and clean up
            assert result is False
            mock_process.terminate.assert_called_once()
            mock_process.wait.assert_called_once()


class TestPakValidation:
    """Test suite for PAK validation functionality."""

    def test_pak_validation_result_init(self) -> None:
        """Test PakValidationResult initialization."""
        result = PakValidationResult()

        assert result.is_valid is False
        assert result.has_crate_icon is False
        assert result.has_subicons is False
        assert result.subicons_count == 0
        assert result.error_message == ""
        assert result.files_found == set()

    def test_pak_validation_result_str_valid(self) -> None:
        """Test PakValidationResult string representation when valid."""
        result = PakValidationResult()
        result.is_valid = True
        result.has_crate_icon = True
        result.subicons_count = 10

        str_repr = str(result)
        assert "Valid" in str_repr
        assert "crate_icon=True" in str_repr
        assert "subicons=10" in str_repr

    def test_pak_validation_result_str_invalid(self) -> None:
        """Test PakValidationResult string representation when invalid."""
        result = PakValidationResult()
        result.is_valid = False
        result.error_message = "Missing required assets"

        str_repr = str(result)
        assert "Invalid" in str_repr
        assert "Missing required assets" in str_repr

    @pytest.mark.asyncio
    async def test_validate_required_assets_no_pak_files(self, tmp_path: Path) -> None:
        """Test validation fails when no PAK files provided."""
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        result = await PakExtractor.validate_required_assets(
            pak_files=[],
            extractor_tool=extractor_tool,
        )

        assert result.is_valid is False
        assert "No PAK files provided" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_required_assets_extractor_not_found(self, tmp_path: Path) -> None:
        """Test validation fails when extractor tool not found."""
        result = await PakExtractor.validate_required_assets(
            pak_files=[str(tmp_path / "test.pak")],
            extractor_tool=tmp_path / "nonexistent_repak.exe",
        )

        assert result.is_valid is False
        assert "Tool not found" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_required_assets_success(self, tmp_path: Path) -> None:
        """Test validation succeeds when all required assets are found."""
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        # Mock the PAK file listing to include required assets
        # Subicons must have "Subtype" in the filename
        pak_contents = (
            f"{CRATE_ICON_PATH}\n"
            f"{SUBICONS_PATH_PREFIX}SubtypeAmmoIcon.uasset\n"
            f"{SUBICONS_PATH_PREFIX}SubtypeDamageIcon.uasset\n"
            "War/Content/Icons/Item1.uasset\n"
        )

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (pak_contents.encode(), b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await PakExtractor.validate_required_assets(
                pak_files=[str(pak_file)],
                extractor_tool=extractor_tool,
            )

        assert result.is_valid is True
        assert result.has_crate_icon is True
        assert result.has_subicons is True
        assert result.subicons_count == 2

    @pytest.mark.asyncio
    async def test_validate_required_assets_missing_crate(self, tmp_path: Path) -> None:
        """Test validation fails when crate icon is missing."""
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        # Mock the PAK file listing without crate icon
        # Subicons must have "Subtype" in the filename
        pak_contents = (
            f"{SUBICONS_PATH_PREFIX}SubtypeAmmoIcon.uasset\n"
            f"{SUBICONS_PATH_PREFIX}SubtypeDamageIcon.uasset\n"
            "War/Content/Icons/Item1.uasset\n"
        )

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (pak_contents.encode(), b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await PakExtractor.validate_required_assets(
                pak_files=[str(pak_file)],
                extractor_tool=extractor_tool,
            )

        assert result.is_valid is False
        assert result.has_crate_icon is False
        assert result.has_subicons is True
        assert "crate icon" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_required_assets_missing_subicons(self, tmp_path: Path) -> None:
        """Test validation fails when subicons are missing."""
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        # Mock the PAK file listing without subicons
        pak_contents = f"{CRATE_ICON_PATH}\nWar/Content/Icons/Item1.uasset\n"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (pak_contents.encode(), b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await PakExtractor.validate_required_assets(
                pak_files=[str(pak_file)],
                extractor_tool=extractor_tool,
            )

        assert result.is_valid is False
        assert result.has_crate_icon is True
        assert result.has_subicons is False
        assert "subicons" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_required_assets_missing_both(self, tmp_path: Path) -> None:
        """Test validation fails when both crate icon and subicons are missing."""
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        # Mock the PAK file listing without required assets
        pak_contents = "War/Content/Icons/Item1.uasset\n"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (pak_contents.encode(), b"")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await PakExtractor.validate_required_assets(
                pak_files=[str(pak_file)],
                extractor_tool=extractor_tool,
            )

        assert result.is_valid is False
        assert result.has_crate_icon is False
        assert result.has_subicons is False
        assert "vanilla" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_validate_required_assets_repak_fails(self, tmp_path: Path) -> None:
        """Test validation handles repak failure gracefully."""
        extractor_tool = tmp_path / "repak.exe"
        extractor_tool.touch()

        pak_file = tmp_path / "test.pak"
        pak_file.touch()

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Error reading PAK")

        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await PakExtractor.validate_required_assets(
                pak_files=[str(pak_file)],
                extractor_tool=extractor_tool,
            )

        assert result.is_valid is False
        assert "Could not list any files" in result.error_message
