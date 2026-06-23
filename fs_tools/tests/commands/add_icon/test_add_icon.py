"""Tests for commands.add_icon.add_icon module.

This module contains comprehensive tests for the add icon command,
including IconManager class functionality, icon addition, and database
update operations.
"""

import argparse
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from foxhole_stockpiles.core.image_io import write_bgr
from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.commands.add_icon.add_icon import main
from fs_tools.models.icon_template import IconTemplate
from fs_tools.template_db.icon_manager import IconManager
from fs_tools.template_db.template_database import TemplateDatabase
from fs_tools.template_db.template_manager import TemplateManager


@pytest.fixture
def sample_database_file(tmp_path: Path) -> Path:
    """Create a sample HDF5 database file for testing.

    Args:
        tmp_path (Path): Temporary directory path from pytest fixture.

    Returns:
        Path: Path to the created sample database file.
    """
    db_path = tmp_path / "test_database.h5"

    # Create databases with actual templates
    databases: dict[SupportedResolution, TemplateDatabase] = {}

    for resolution in [SupportedResolution.R_1080, SupportedResolution.R_1440]:
        # Calculate expected icon size for this resolution
        icon_size = int((64 / 2160) * int(resolution.value))
        db = TemplateDatabase(resolution)

        # Add a sample template
        template = IconTemplate(
            code="TestItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=resolution,
            image=np.zeros((icon_size, icon_size, 3), dtype=np.uint8),
            phash=0,
        )
        db.add_template(template)
        databases[resolution] = db

    # Save to HDF5 file using TemplateManager
    TemplateManager.save_databases_to_hdf5(databases=databases, output_path=db_path, workers=1)

    return db_path


@pytest.fixture
def sample_icon_file(tmp_path: Path) -> Path:
    """Create a sample icon file for testing.

    Args:
        tmp_path (Path): Temporary directory path from pytest fixture.

    Returns:
        Path: Path to the created sample icon file.
    """
    icon_path = tmp_path / "test_icon.png"

    # Create a 32x32 test image (correct size for 1080p)
    # Icon scaling: 64 / 2160 * 1080 = 32
    test_image = np.zeros((32, 32, 3), dtype=np.uint8)
    test_image[8:24, 8:24] = [255, 128, 0]  # Orange square

    write_bgr(str(icon_path), test_image)

    return icon_path


class TestIconManagerInitialization:
    """Test suite for IconManager initialization.

    This class contains tests for IconManager instance creation
    with various parameter combinations and configurations.
    """

    async def test_initialization_with_valid_database(self, sample_database_file: Path) -> None:
        """Test IconManager initialization with valid database.

        Args:
            sample_database_file (Path): Sample database file from fixture.
        """
        # Load databases using TemplateManager
        template_manager = TemplateManager(database_path=sample_database_file)
        databases = await template_manager.load_all_resolutions()

        adder = IconManager(
            database_path=sample_database_file, databases=databases, icon_scale=64 / 2160
        )

        assert adder.database_path == sample_database_file
        assert len(adder.databases) == 2
        assert SupportedResolution.R_1080 in adder.databases
        assert SupportedResolution.R_1440 in adder.databases

    async def test_initialization_with_empty_databases_dict(self) -> None:
        """Test IconManager initialization with empty databases dict."""
        with pytest.raises(ValueError, match="Databases dictionary cannot be empty"):
            IconManager(database_path=Path("/tmp/test.h5"), databases={}, icon_scale=64 / 2160)

    async def test_initialization_with_empty_database(self, tmp_path: Path) -> None:
        """Test IconManager initialization with empty database.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "empty.h5"

        # Create empty HDF5 database
        TemplateManager.save_databases_to_hdf5(
            databases={SupportedResolution.R_1080: TemplateDatabase(SupportedResolution.R_1080)},
            output_path=db_path,
            workers=1,
        )

        # Load databases using TemplateManager
        template_manager = TemplateManager(database_path=db_path)
        databases = await template_manager.load_all_resolutions()

        # IconManager should load but database will be empty
        adder = IconManager(database_path=db_path, databases=databases, icon_scale=64 / 2160)
        assert len(adder.databases[SupportedResolution.R_1080].templates) == 0


class TestIconManagerMethods:
    """Test suite for IconManager methods.

    This class contains tests for the core functionality of IconManager
    including icon addition, database saving, and error handling.
    """

    @pytest.fixture
    async def adder(self, sample_database_file: Path) -> IconManager:
        """Create an IconManager instance for testing.

        Args:
            sample_database_file (Path): Sample database file from fixture.

        Returns:
            IconManager: Configured adder instance for testing.
        """
        template_manager = TemplateManager(database_path=sample_database_file)
        databases = await template_manager.load_all_resolutions()
        return IconManager(
            database_path=sample_database_file, databases=databases, icon_scale=64 / 2160
        )

    async def test_add_icon_success(self, adder: IconManager, sample_icon_file: Path) -> None:
        """Test adding icon successfully.

        Args:
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        initial_count = len(adder.databases[SupportedResolution.R_1080].templates)

        await adder.add_icon(
            icon_path=sample_icon_file,
            item_code="NewItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        # Verify template was added
        final_count = len(adder.databases[SupportedResolution.R_1080].templates)
        assert final_count == initial_count + 1

        # Verify template properties
        new_template = adder.databases[SupportedResolution.R_1080].templates[-1]
        assert new_template.code == "NewItem"
        assert new_template.faction == ItemFaction.NEUTRAL
        assert new_template.category == ItemCategory.Item
        assert new_template.crated is False
        assert new_template.mod == "vanilla"

    async def test_add_icon_crated_variant(
        self, adder: IconManager, sample_icon_file: Path
    ) -> None:
        """Test adding crated icon variant.

        Args:
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        await adder.add_icon(
            icon_path=sample_icon_file,
            item_code="CratedItem",
            faction=ItemFaction.COLONIALS,
            category=ItemCategory.Vehicle,
            crated=True,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        # Verify crated template was added
        new_template = adder.databases[SupportedResolution.R_1080].templates[-1]
        assert new_template.code == "CratedItem"
        assert new_template.crated is True
        assert new_template.faction == ItemFaction.COLONIALS
        assert new_template.category == ItemCategory.Vehicle

    async def test_add_icon_with_nonexistent_file(self, adder: IconManager) -> None:
        """Test adding icon with nonexistent file.

        Args:
            adder (IconManager): IconManager instance from fixture.
        """
        fake_path = Path("nonexistent_icon.png")

        with pytest.raises(FileNotFoundError, match="Icon file not found"):
            await adder.add_icon(
                icon_path=fake_path,
                item_code="Item",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )

    async def test_add_icon_with_invalid_resolution(
        self, adder: IconManager, sample_icon_file: Path
    ) -> None:
        """Test adding icon with resolution not in database.

        Args:
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        with pytest.raises(ValueError, match="Resolution .* not found in database"):
            await adder.add_icon(
                icon_path=sample_icon_file,
                item_code="Item",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_2160,  # Not in test database
            )

    @patch("fs_tools.template_db.icon_manager.read_bgr")
    async def test_add_icon_with_failed_image_load(
        self, mock_imread: Mock, adder: IconManager, sample_icon_file: Path
    ) -> None:
        """Test adding icon when image fails to load.

        Args:
            mock_imread (Mock): Mocked read_bgr function.
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        mock_imread.return_value = None

        with pytest.raises(ValueError, match="Failed to load icon image"):
            await adder.add_icon(
                icon_path=sample_icon_file,
                item_code="Item",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )

    async def test_add_icon_multiple_factions(
        self, adder: IconManager, sample_icon_file: Path
    ) -> None:
        """Test adding icons with different factions.

        Args:
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        # Add Colonial icon
        await adder.add_icon(
            icon_path=sample_icon_file,
            item_code="ColonialItem",
            faction=ItemFaction.COLONIALS,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        # Add Warden icon
        await adder.add_icon(
            icon_path=sample_icon_file,
            item_code="WardenItem",
            faction=ItemFaction.WARDENS,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        # Verify both were added
        templates = adder.databases[SupportedResolution.R_1080].templates
        colonial_templates = [t for t in templates if t.faction == ItemFaction.COLONIALS]
        warden_templates = [t for t in templates if t.faction == ItemFaction.WARDENS]

        assert len(colonial_templates) >= 1
        assert len(warden_templates) >= 1

    async def test_add_icon_custom_mod(self, adder: IconManager, sample_icon_file: Path) -> None:
        """Test adding icon with custom mod name.

        Args:
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        await adder.add_icon(
            icon_path=sample_icon_file,
            item_code="ModItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="custom_mod",
            resolution=SupportedResolution.R_1080,
        )

        # Verify mod name
        new_template = adder.databases[SupportedResolution.R_1080].templates[-1]
        assert new_template.mod == "custom_mod"

    async def test_add_icon_with_wrong_dimensions(self, adder: IconManager, tmp_path: Path) -> None:
        """Test adding icon with incorrect dimensions.

        Args:
            adder (IconManager): IconManager instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create icon with wrong size (16x16 instead of 32x32 for 1080p)
        wrong_size_icon = tmp_path / "wrong_size.png"
        wrong_image = np.zeros((16, 16, 3), dtype=np.uint8)
        write_bgr(str(wrong_size_icon), wrong_image)

        with pytest.raises(ValueError, match="Icon has incorrect dimensions"):
            await adder.add_icon(
                icon_path=wrong_size_icon,
                item_code="WrongSize",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )

    async def test_add_duplicate_icon_without_replace(
        self, adder: IconManager, sample_icon_file: Path
    ) -> None:
        """Test that adding duplicate icon without replace flag fails.

        Args:
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        # Add icon first time
        await adder.add_icon(
            icon_path=sample_icon_file,
            item_code="DuplicateTest",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        # Try to add same icon again without replace flag
        with pytest.raises(ValueError, match="Icon already exists"):
            await adder.add_icon(
                icon_path=sample_icon_file,
                item_code="DuplicateTest",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
                replace=False,
            )

    async def test_replace_existing_icon(
        self, adder: IconManager, sample_icon_file: Path, tmp_path: Path
    ) -> None:
        """Test replacing existing icon with replace flag.

        Args:
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
            tmp_path (Path): Temporary directory path from fixture.
        """
        # Add icon first time
        await adder.add_icon(
            icon_path=sample_icon_file,
            item_code="ReplaceTest",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        initial_count = len(adder.databases[SupportedResolution.R_1080].templates)

        # Create a different icon with same size
        new_icon_file = tmp_path / "new_icon.png"
        new_image = np.zeros((32, 32, 3), dtype=np.uint8)
        new_image[8:24, 8:24] = [0, 255, 0]  # Green square
        write_bgr(str(new_icon_file), new_image)

        # Replace with new icon
        await adder.add_icon(
            icon_path=new_icon_file,
            item_code="ReplaceTest",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            replace=True,
        )

        # Verify count didn't increase (replaced, not added)
        final_count = len(adder.databases[SupportedResolution.R_1080].templates)
        assert final_count == initial_count

        # Verify the icon was actually replaced (check it's the new image)
        template = None
        for t in adder.databases[SupportedResolution.R_1080].templates:
            if t.code == "ReplaceTest":
                template = t
                break

        assert template is not None
        # Check that the new image has green pixels (from new icon)
        assert np.any(template.image[:, :, 1] > 200)  # Green channel

    async def test_add_icon_from_image_success(self, adder: IconManager) -> None:
        """Test adding icon directly from image array.

        Args:
            adder (IconManager): IconManager instance from fixture.
        """
        initial_count = len(adder.databases[SupportedResolution.R_1080].templates)

        # Create a 32x32 BGR image
        icon_image = np.zeros((32, 32, 3), dtype=np.uint8)
        icon_image[:, :, 2] = 128  # Red channel

        adder.add_icon_from_image(
            icon_image=icon_image,
            item_code="FromImage",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        final_count = len(adder.databases[SupportedResolution.R_1080].templates)
        assert final_count == initial_count + 1

    async def test_add_icon_from_image_wrong_dimensions(self, adder: IconManager) -> None:
        """Test add icon from image with wrong dimensions.

        Args:
            adder (IconManager): IconManager instance from fixture.
        """
        # Create wrong size image (64x64 instead of 32x32 for 1080p)
        icon_image = np.zeros((64, 64, 3), dtype=np.uint8)

        with pytest.raises(ValueError, match="incorrect dimensions"):
            adder.add_icon_from_image(
                icon_image=icon_image,
                item_code="WrongSize",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )

    async def test_add_icon_from_image_invalid_resolution(self, adder: IconManager) -> None:
        """Test add icon from image with resolution not in database.

        Args:
            adder (IconManager): IconManager instance from fixture.
        """
        icon_image = np.zeros((64, 64, 3), dtype=np.uint8)

        with pytest.raises(ValueError, match="Resolution .* not found in database"):
            adder.add_icon_from_image(
                icon_image=icon_image,
                item_code="Test",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_2160,  # Not in test database
            )

    async def test_add_icon_from_image_replace(self, adder: IconManager) -> None:
        """Test replacing icon using add_icon_from_image.

        Args:
            adder (IconManager): IconManager instance from fixture.
        """
        # First add an icon
        icon_image = np.zeros((32, 32, 3), dtype=np.uint8)
        icon_image[:, :, 2] = 100  # Red

        adder.add_icon_from_image(
            icon_image=icon_image,
            item_code="ReplaceFromImage",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        initial_count = len(adder.databases[SupportedResolution.R_1080].templates)

        # Replace with different image
        new_icon = np.zeros((32, 32, 3), dtype=np.uint8)
        new_icon[:, :, 1] = 255  # Green

        adder.add_icon_from_image(
            icon_image=new_icon,
            item_code="ReplaceFromImage",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            replace=True,
        )

        final_count = len(adder.databases[SupportedResolution.R_1080].templates)
        assert final_count == initial_count

    async def test_add_icon_from_image_duplicate_without_replace(self, adder: IconManager) -> None:
        """Test adding duplicate icon from image without replace flag.

        Args:
            adder (IconManager): IconManager instance from fixture.
        """
        icon_image = np.zeros((32, 32, 3), dtype=np.uint8)

        adder.add_icon_from_image(
            icon_image=icon_image,
            item_code="DuplicateImage",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        with pytest.raises(ValueError, match="Icon already exists"):
            adder.add_icon_from_image(
                icon_image=icon_image,
                item_code="DuplicateImage",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )

    async def test_delete_icon_success(self, adder: IconManager, sample_icon_file: Path) -> None:
        """Test deleting an icon successfully.

        Args:
            adder (IconManager): IconManager instance from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        # First add an icon
        await adder.add_icon(
            icon_path=sample_icon_file,
            item_code="DeleteTest",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        initial_count = len(adder.databases[SupportedResolution.R_1080].templates)

        # Now delete it
        adder.delete_icon(
            item_code="DeleteTest",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        # Verify count decreased
        final_count = len(adder.databases[SupportedResolution.R_1080].templates)
        assert final_count == initial_count - 1

        # Verify template no longer exists
        for template in adder.databases[SupportedResolution.R_1080].templates:
            assert template.code != "DeleteTest"

    async def test_delete_icon_not_found(self, adder: IconManager) -> None:
        """Test deleting a non-existent icon raises error.

        Args:
            adder (IconManager): IconManager instance from fixture.
        """
        with pytest.raises(ValueError, match="Icon not found"):
            adder.delete_icon(
                item_code="NonExistent",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )

    async def test_delete_icon_invalid_resolution(self, adder: IconManager) -> None:
        """Test deleting icon with resolution not in database.

        Args:
            adder (IconManager): IconManager instance from fixture.
        """
        with pytest.raises(ValueError, match="Resolution .* not found in database"):
            adder.delete_icon(
                item_code="TestItem",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=SupportedResolution.R_2160,  # Not in test database
            )


class TestMainFunction:
    """Test suite for the main CLI function.

    This class contains tests for the main entry point of the add icon
    command, including argument parsing and workflow execution.
    """

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.add_icon.add_icon.IconManager")
    @patch("fs_tools.commands.add_icon.add_icon.setup_logging")
    async def test_main_with_default_args(
        self,
        mock_setup_logging: Mock,
        mock_adder_class: Mock,
        mock_args: Mock,
        sample_database_file: Path,
        sample_icon_file: Path,
    ) -> None:
        """Test main function with default arguments.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_adder_class (Mock): Mocked IconManager class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            sample_database_file (Path): Sample database file from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        mock_args.return_value = argparse.Namespace(
            database=sample_database_file,
            icon=sample_icon_file,
            code="TestItem",
            faction="n",  # Use shorthand like inspector
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Mock adder instance
        mock_adder = MagicMock()
        mock_adder.add_icon = AsyncMock(return_value=None)
        mock_adder_class.return_value = mock_adder

        await main()

        # Verify IconManager was instantiated with database_path and databases
        mock_adder_class.assert_called_once()
        call_kwargs = mock_adder_class.call_args.kwargs
        assert call_kwargs["database_path"] == sample_database_file
        assert "databases" in call_kwargs

        # Verify add_icon was called
        assert mock_adder.add_icon.call_count == 1

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.add_icon.add_icon.IconManager")
    @patch("fs_tools.commands.add_icon.add_icon.setup_logging")
    async def test_main_with_multiple_resolutions(
        self,
        mock_setup_logging: Mock,
        mock_adder_class: Mock,
        mock_args: Mock,
        sample_database_file: Path,
        sample_icon_file: Path,
    ) -> None:
        """Test main function with multiple resolution arguments.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_adder_class (Mock): Mocked IconManager class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            sample_database_file (Path): Sample database file from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        mock_args.return_value = argparse.Namespace(
            database=sample_database_file,
            icon=sample_icon_file,
            code="TestItem",
            faction="n",  # Use shorthand like inspector
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["1080", "1440"],
            replace=False,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Mock adder instance
        mock_adder = MagicMock()
        mock_adder.add_icon = AsyncMock(return_value=None)
        mock_adder_class.return_value = mock_adder

        await main()

        # Verify add_icon was called twice (once for each resolution)
        assert mock_adder.add_icon.call_count == 2

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.add_icon.add_icon.IconManager")
    @patch("fs_tools.commands.add_icon.add_icon.setup_logging")
    async def test_main_with_crated_flag(
        self,
        mock_setup_logging: Mock,
        mock_adder_class: Mock,
        mock_args: Mock,
        sample_database_file: Path,
        sample_icon_file: Path,
    ) -> None:
        """Test main function with crated flag.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_adder_class (Mock): Mocked IconManager class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            sample_database_file (Path): Sample database file from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        mock_args.return_value = argparse.Namespace(
            database=sample_database_file,
            icon=sample_icon_file,
            code="TestItem",
            faction="n",  # Use shorthand like inspector
            category="item",
            crated=True,  # Crated flag enabled
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Mock adder instance
        mock_adder = MagicMock()
        mock_adder.add_icon = AsyncMock(return_value=None)
        mock_adder_class.return_value = mock_adder

        await main()

        # Verify add_icon was called with crated=True
        call_kwargs = mock_adder.add_icon.call_args[1]
        assert call_kwargs["crated"] is True

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.add_icon.add_icon.IconManager")
    @patch("fs_tools.commands.add_icon.add_icon.setup_logging")
    async def test_main_with_verbose_mode(
        self,
        mock_setup_logging: Mock,
        mock_adder_class: Mock,
        mock_args: Mock,
        sample_database_file: Path,
        sample_icon_file: Path,
    ) -> None:
        """Test main function with verbose mode enabled.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_adder_class (Mock): Mocked IconManager class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            sample_database_file (Path): Sample database file from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        mock_args.return_value = argparse.Namespace(
            database=sample_database_file,
            icon=sample_icon_file,
            code="TestItem",
            faction="n",  # Use shorthand like inspector
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=True,  # Verbose mode
            quiet=False,
            log_file=None,
        )

        # Mock adder instance
        mock_adder = MagicMock()
        mock_adder.add_icon = AsyncMock(return_value=None)
        mock_adder_class.return_value = mock_adder

        await main()

        # Verify setup_logging was called
        mock_setup_logging.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.add_icon.add_icon.IconManager")
    @patch("fs_tools.commands.add_icon.add_icon.setup_logging")
    async def test_main_with_invalid_resolution(
        self,
        mock_setup_logging: Mock,
        mock_adder_class: Mock,
        mock_args: Mock,
        sample_database_file: Path,
        sample_icon_file: Path,
    ) -> None:
        """Test main function with invalid resolution argument.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_adder_class (Mock): Mocked IconManager class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            sample_database_file (Path): Sample database file from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        mock_args.return_value = argparse.Namespace(
            database=sample_database_file,
            icon=sample_icon_file,
            code="TestItem",
            faction="n",  # Use shorthand like inspector
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["9999"],  # Invalid resolution
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Mock adder instance
        mock_adder = MagicMock()
        mock_adder.add_icon = AsyncMock(return_value=None)
        mock_adder_class.return_value = mock_adder

        # Should raise SystemExit due to parser.error()
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 2

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.add_icon.add_icon.IconManager")
    @patch("fs_tools.commands.add_icon.add_icon.setup_logging")
    async def test_main_with_different_factions(
        self,
        mock_setup_logging: Mock,
        mock_adder_class: Mock,
        mock_args: Mock,
        sample_database_file: Path,
        sample_icon_file: Path,
    ) -> None:
        """Test main function with different faction values.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_adder_class (Mock): Mocked IconManager class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            sample_database_file (Path): Sample database file from fixture.
            sample_icon_file (Path): Sample icon file from fixture.
        """
        # ItemFaction.from_string converts shorthand to proper enum values
        expected_faction_values = {
            "c": "Colonials",
            "w": "Wardens",
            "n": "neutral",
        }

        for faction in ["c", "w", "n"]:
            # Reset mock for each iteration
            mock_adder_class.reset_mock()

            mock_args.return_value = argparse.Namespace(
                database=sample_database_file,
                icon=sample_icon_file,
                code="TestItem",
                faction=faction,
                category="item",
                crated=False,
                mod="vanilla",
                resolution=["1080"],
                replace=False,
                verbose=False,
                quiet=False,
                log_file=None,
            )

            # Mock adder instance
            mock_adder = MagicMock()
            mock_adder.add_icon = AsyncMock(return_value=None)
            mock_adder_class.return_value = mock_adder

            await main()

            # Verify add_icon was called with correct faction
            call_kwargs = mock_adder.add_icon.call_args[1]
            assert call_kwargs["faction"].value == expected_faction_values[faction]

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.add_icon.add_icon.get_settings")
    async def test_main_missing_database_path(
        self,
        mock_get_settings: Mock,
        mock_args: Mock,
        tmp_path: Path,
    ) -> None:
        """Test main function when database path is not provided.

        Args:
            mock_get_settings (Mock): Mocked get_settings function.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = tmp_path / "icon.png"
        icon_path.touch()

        # Mock settings with no database path
        mock_settings = MagicMock()
        mock_settings.scanner.database_path = None
        mock_get_settings.return_value = mock_settings

        mock_args.return_value = argparse.Namespace(
            database=None,  # No database provided
            icon=icon_path,
            code="TestItem",
            name="Test Item",
            faction="w",
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Should exit with code 2 for argparse error
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 2

    @patch("argparse.ArgumentParser.parse_args")
    async def test_main_database_file_not_exists(
        self,
        mock_args: Mock,
        tmp_path: Path,
    ) -> None:
        """Test main function when database file does not exist.

        Args:
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = tmp_path / "icon.png"
        icon_path.touch()

        database_path = tmp_path / "nonexistent.h5"  # Doesn't exist

        mock_args.return_value = argparse.Namespace(
            database=database_path,
            icon=icon_path,
            code="TestItem",
            name="Test Item",
            faction="w",
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1

    @patch("argparse.ArgumentParser.parse_args")
    async def test_main_database_path_is_directory(
        self,
        mock_args: Mock,
        tmp_path: Path,
    ) -> None:
        """Test main function when database path is a directory instead of a file.

        Args:
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = tmp_path / "icon.png"
        icon_path.touch()

        database_path = tmp_path / "database_dir"
        database_path.mkdir()  # Create directory instead of file

        mock_args.return_value = argparse.Namespace(
            database=database_path,
            icon=icon_path,
            code="TestItem",
            name="Test Item",
            faction="w",
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.add_icon.add_icon.IconManager")
    @patch("fs_tools.commands.add_icon.add_icon.TemplateManager")
    @patch("fs_tools.commands.add_icon.add_icon.setup_logging")
    async def test_main_with_quiet_mode(
        self,
        mock_setup_logging: Mock,
        mock_template_manager_class: Mock,
        mock_adder_class: Mock,
        mock_args: Mock,
        tmp_path: Path,
    ) -> None:
        """Test main function with quiet mode enabled.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_template_manager_class (Mock): Mocked TemplateManager class.
            mock_adder_class (Mock): Mocked IconManager class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        db_path.touch()

        icon_path = tmp_path / "icon.png"
        icon_path.touch()

        mock_args.return_value = argparse.Namespace(
            database=db_path,
            icon=icon_path,
            code="TestItem",
            faction="w",
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=False,
            quiet=True,  # Quiet mode
            log_file=None,
        )

        # Mock template manager
        mock_template_manager = MagicMock()
        mock_template_manager.load_all_resolutions = AsyncMock(return_value={})
        mock_template_manager_class.return_value = mock_template_manager

        # Mock adder instance
        mock_adder = MagicMock()
        mock_adder.add_icon = AsyncMock(return_value=None)
        mock_adder_class.return_value = mock_adder

        await main()

        # Verify setup_logging was called
        mock_setup_logging.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    async def test_main_with_invalid_faction(
        self,
        mock_args: Mock,
        tmp_path: Path,
    ) -> None:
        """Test main function with invalid faction that becomes NEUTRAL.

        Args:
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        db_path.touch()

        icon_path = tmp_path / "icon.png"
        icon_path.touch()

        mock_args.return_value = argparse.Namespace(
            database=db_path,
            icon=icon_path,
            code="TestItem",
            name="Test Item",
            faction="invalid_faction",  # Invalid faction
            category="item",
            crated=False,
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Should exit with code 2 for argparse error
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 2

    @patch("argparse.ArgumentParser.parse_args")
    async def test_main_with_invalid_category(
        self,
        mock_args: Mock,
        tmp_path: Path,
    ) -> None:
        """Test main function with Invalid category value.

        Args:
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        db_path = tmp_path / "test.h5"
        db_path.touch()

        icon_path = tmp_path / "icon.png"
        icon_path.touch()

        mock_args.return_value = argparse.Namespace(
            database=db_path,
            icon=icon_path,
            code="TestItem",
            name="Test Item",
            faction="w",
            category="invalid",  # Invalid category (ItemCategory.Invalid)
            crated=False,
            mod="vanilla",
            resolution=["1080"],
            replace=False,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Should exit with code 2 for argparse error
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 2


def test_main_module_importable() -> None:
    """Test that __main__ module can be imported without errors."""
    import fs_tools.commands.add_icon.__main__  # noqa: F401
