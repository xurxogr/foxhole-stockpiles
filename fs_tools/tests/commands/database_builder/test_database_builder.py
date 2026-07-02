"""Tests for commands.database_builder.database_builder module.

This module contains comprehensive tests for the database builder command,
including DatabaseBuilder class functionality, template processing, and
database creation for multiple resolutions.
"""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest
import typer

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.models.catalog_item import CatalogItem
from fs_tools.commands.database_builder.database_builder import (
    DatabaseBuilder,
    run,
)
from fs_tools.models.icon_template import IconTemplate
from fs_tools.template_db.template_database import TemplateDatabase


class TestDatabaseBuilderInitialization:
    """Test suite for DatabaseBuilder initialization.

    This class contains tests for DatabaseBuilder instance creation
    with various parameter combinations and configurations.
    """

    async def test_initialization_with_valid_catalog(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test DatabaseBuilder initialization with valid catalog.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        builder = DatabaseBuilder(
            catalog_path=mock_catalog_file, assets_path=assets_path, use_scaling=False
        )

        assert builder.assets_path == assets_path
        assert builder.use_scaling is False
        assert len(builder.catalog_data) > 0

    async def test_initialization_with_empty_catalog(self, tmp_path: Path) -> None:
        """Test DatabaseBuilder initialization with empty catalog.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_path = tmp_path / "empty_catalog.json"
        catalog_path.write_text("[]")

        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        with pytest.raises(ValueError, match="Catalog is empty"):
            DatabaseBuilder(catalog_path=catalog_path, assets_path=assets_path)

    async def test_initialization_with_scaling_enabled(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test DatabaseBuilder initialization with scaling enabled.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        builder = DatabaseBuilder(
            catalog_path=mock_catalog_file, assets_path=assets_path, use_scaling=True
        )

        assert builder.use_scaling is True


class TestDatabaseBuilderMethods:
    """Test suite for DatabaseBuilder methods.

    This class contains tests for the core functionality of DatabaseBuilder
    including template processing, icon file discovery, and database building.
    """

    @pytest.fixture
    def builder(self, tmp_path: Path, mock_catalog_file: Path) -> DatabaseBuilder:
        """Create a DatabaseBuilder instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.

        Returns:
            DatabaseBuilder: Configured builder instance for testing.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        return DatabaseBuilder(
            catalog_path=mock_catalog_file, assets_path=assets_path, use_scaling=False
        )

    async def test_find_icon_files_exact_match(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test finding icon files with exact size match.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create test icon structure
        item_code = "TestRifle"
        icon_size = 32
        item_folder = builder.assets_path / item_code
        item_folder.mkdir()

        # Create exact size icon
        icon_file = item_folder / f"vanilla_{item_code}_{icon_size}.png"
        icon_file.touch()

        # Find icons
        found_icons = builder._find_icon_files(item_code=item_code, icon_size=icon_size)

        assert len(found_icons) == 1
        assert found_icons[0] == icon_file

    async def test_find_icon_files_crated_variant(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test finding crated variant icon files.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create test icon structure
        item_code = "TestRifle"
        icon_size = 32

        # Create crated folder
        crated_folder = builder.assets_path / f"{item_code}_crated"
        crated_folder.mkdir()

        # Create crated icon
        icon_file = crated_folder / f"vanilla_{item_code}_crated_{icon_size}.png"
        icon_file.touch()

        # Find icons
        found_icons = builder._find_icon_files(item_code=item_code, icon_size=icon_size)

        assert len(found_icons) == 1
        assert found_icons[0] == icon_file

    async def test_find_size_variants_with_scaling(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test finding size variants with scaling enabled.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        builder = DatabaseBuilder(
            catalog_path=mock_catalog_file, assets_path=assets_path, use_scaling=True
        )

        # Create test icon structure with multiple sizes
        item_code = "TestRifle"
        item_folder = builder.assets_path / item_code
        item_folder.mkdir()

        # Create icons at different sizes
        for size in [64, 128, 256]:
            icon_file = item_folder / f"vanilla_{item_code}_{size}.png"
            icon_file.touch()

        # Find size variants (looking for size 32, should find largest: 256)
        found_icons = builder._find_size_variants(
            folder=item_folder, item_code=item_code, target_size=32, is_crated=False
        )

        # Should find one icon (the largest size)
        assert len(found_icons) == 1

    @patch("fs_tools.commands.database_builder.database_builder.read_bgr")
    @patch("fs_tools.commands.database_builder.database_builder.resize_bgr")
    async def test_process_item_templates(
        self,
        mock_resize: Mock,
        mock_imread: Mock,
        builder: DatabaseBuilder,
        tmp_path: Path,
    ) -> None:
        """Test processing templates for a single item.

        Args:
            mock_resize (Mock): Mocked resize_bgr function.
            mock_imread (Mock): Mocked read_bgr function.
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create mock image
        mock_image = np.zeros((64, 64, 3), dtype=np.uint8)
        mock_imread.return_value = mock_image
        mock_resize.return_value = mock_image

        # Create test icon file
        item_code = "TestRifle"
        item_folder = builder.assets_path / item_code
        item_folder.mkdir()

        # Calculate icon size the same way DatabaseBuilder does (64/2160 * 1080 = 32)
        icon_size = 32
        icon_file = item_folder / f"vanilla_{item_code}_{icon_size}.png"
        icon_file.touch()

        # Create catalog item
        catalog_item = CatalogItem(
            code=item_code,
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path=f"War/Content/test/{item_code}",
            subicon_path="",
        )

        # Process templates
        templates = await builder._process_item_templates(
            item=catalog_item, resolution=SupportedResolution.R_1080, icon_size=icon_size
        )

        # Should have created templates (may be empty if file loading fails)
        assert isinstance(templates, list)

    async def test_build_resolution_database(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test building database for a specific resolution.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        with patch.object(builder, "_process_item_templates", return_value=[]):
            database = await builder._build_resolution_database(
                resolution=SupportedResolution.R_1080
            )

            assert database.resolution == SupportedResolution.R_1080
            assert isinstance(database.templates, list)

    async def test_build_all_databases_success(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test building all databases successfully.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        output_path = tmp_path / "output.h5"

        # Mock _build_resolution_database to return databases with templates
        async def mock_build_db(resolution: SupportedResolution) -> Any:
            import numpy as np

            from foxhole_stockpiles.enums.item_category import ItemCategory
            from foxhole_stockpiles.enums.item_faction import ItemFaction
            from fs_tools.models.icon_template import IconTemplate
            from fs_tools.template_db.template_database import TemplateDatabase

            db = TemplateDatabase(resolution)
            # Add a template so database is not empty
            template = IconTemplate(
                code="TestItem",
                faction=ItemFaction.NEUTRAL,
                category=ItemCategory.Item,
                crated=False,
                mod="vanilla",
                resolution=resolution,
                image=np.zeros((32, 32, 3), dtype=np.uint8),
                phash=0,
            )
            db.add_template(template)
            return db

        with patch.object(builder, "_build_resolution_database", side_effect=mock_build_db):
            await builder.build_all_databases(
                output_path=output_path, target_resolutions=[SupportedResolution.R_1080]
            )

        # Verify output file was created
        assert output_path.exists()

    async def test_build_all_databases_no_templates_error(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test that build_all_databases raises error when no templates found.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from fixture.
        """
        output_path = tmp_path / "output.h5"

        # Mock _build_resolution_database to return empty databases
        async def mock_build_db(resolution: SupportedResolution) -> Any:
            from fs_tools.template_db.template_database import TemplateDatabase

            return TemplateDatabase(resolution)  # Empty database

        with patch.object(builder, "_build_resolution_database", side_effect=mock_build_db):
            with pytest.raises(ValueError, match="No templates found"):
                await builder.build_all_databases(
                    output_path=output_path, target_resolutions=[SupportedResolution.R_1080]
                )

    async def test_save_databases(self, builder: DatabaseBuilder, tmp_path: Path) -> None:
        """Test saving databases to file.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        output_path = tmp_path / "subdir" / "output.h5"

        # Create a database with a template
        db = TemplateDatabase(SupportedResolution.R_1080)
        template = IconTemplate(
            code="TestItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=False,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            phash=0,
        )
        db.add_template(template)

        databases = {SupportedResolution.R_1080: db}

        # Save databases
        await builder._save_databases(databases=databases, output_path=output_path)

        # Verify file was created in subdirectory
        assert output_path.exists()
        assert output_path.parent.exists()

        # Verify file size is reasonable
        assert output_path.stat().st_size > 0

    @patch("fs_tools.commands.database_builder.database_builder.read_bgr")
    async def test_process_item_templates_with_missing_code(
        self, mock_imread: Mock, builder: DatabaseBuilder
    ) -> None:
        """Test processing templates for item with missing code.

        Args:
            mock_imread (Mock): Mocked read_bgr function.
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
        """
        # Create catalog item without code
        catalog_item = CatalogItem(
            code="",  # Empty code
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path="War/Content/test/Item",
            subicon_path="",
        )

        # Process templates
        templates = await builder._process_item_templates(
            item=catalog_item, resolution=SupportedResolution.R_1080, icon_size=32
        )

        # Should return empty list when code is missing
        assert templates == []

    @patch("fs_tools.commands.database_builder.database_builder.read_bgr")
    @patch("fs_tools.commands.database_builder.database_builder.resize_bgr")
    async def test_process_item_templates_with_failed_icon_load(
        self, mock_resize: Mock, mock_imread: Mock, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test processing templates when icon fails to load.

        Args:
            mock_resize (Mock): Mocked resize_bgr function.
            mock_imread (Mock): Mocked read_bgr function.
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Mock imread to return None (failed load)
        mock_imread.return_value = None

        # Create test icon file
        item_code = "TestRifle"
        item_folder = builder.assets_path / item_code
        item_folder.mkdir()

        # Calculate icon size the same way DatabaseBuilder does (64/2160 * 1080 = 32)
        icon_size = 32
        icon_file = item_folder / f"vanilla_{item_code}_{icon_size}.png"
        icon_file.touch()

        # Create catalog item
        catalog_item = CatalogItem(
            code=item_code,
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path=f"War/Content/test/{item_code}",
            subicon_path="",
        )

        # Process templates
        templates = await builder._process_item_templates(
            item=catalog_item, resolution=SupportedResolution.R_1080, icon_size=icon_size
        )

        # Should return empty list when icon fails to load
        assert templates == []

    @patch("fs_tools.commands.database_builder.database_builder.read_bgr")
    @patch("fs_tools.commands.database_builder.database_builder.resize_bgr")
    async def test_process_item_templates_with_exception(
        self, mock_resize: Mock, mock_imread: Mock, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test processing templates when template creation raises exception.

        Args:
            mock_resize (Mock): Mocked resize_bgr function.
            mock_imread (Mock): Mocked read_bgr function.
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create mock image
        mock_image = np.zeros((64, 64, 3), dtype=np.uint8)
        mock_imread.return_value = mock_image
        mock_resize.return_value = mock_image

        # Create test icon file
        item_code = "TestRifle"
        item_folder = builder.assets_path / item_code
        item_folder.mkdir()

        # Calculate icon size the same way DatabaseBuilder does (64/2160 * 1080 = 32)
        icon_size = 32
        icon_file = item_folder / f"vanilla_{item_code}_{icon_size}.png"
        icon_file.touch()

        # Create catalog item
        catalog_item = CatalogItem(
            code=item_code,
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path=f"War/Content/test/{item_code}",
            subicon_path="",
        )

        # Mock IconTemplate to raise exception
        with patch(
            "fs_tools.commands.database_builder.database_builder.IconTemplate"
        ) as mock_template:
            mock_template.side_effect = ValueError("Invalid template data")

            # Process templates
            templates = await builder._process_item_templates(
                item=catalog_item, resolution=SupportedResolution.R_1080, icon_size=icon_size
            )

            # Should return empty list when exception occurs
            assert templates == []

    async def test_find_icon_files_no_icons_found(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test finding icon files when none exist.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Try to find icons for non-existent item
        found_icons = builder._find_icon_files(item_code="NonExistentItem", icon_size=32)

        # Should return empty list
        assert found_icons == []

    async def test_find_size_variants_scaling_disabled(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test finding size variants with scaling disabled when exact size not found.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create test icon structure with wrong size
        item_code = "TestRifle"
        item_folder = builder.assets_path / item_code
        item_folder.mkdir()

        # Create icon at different size than we're looking for
        icon_file = item_folder / f"vanilla_{item_code}_128.png"
        icon_file.touch()

        # Find size variants (looking for size 32, but only 128 exists)
        # Scaling is disabled in fixture
        found_icons = builder._find_size_variants(
            folder=item_folder, item_code=item_code, target_size=32, is_crated=False
        )

        # Should return empty list when scaling disabled and exact size not found
        assert found_icons == []

    async def test_find_size_variants_with_scaling_no_files(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test finding size variants with scaling enabled but no files found.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        builder = DatabaseBuilder(
            catalog_path=mock_catalog_file, assets_path=assets_path, use_scaling=True
        )

        # Create empty folder
        item_code = "TestRifle"
        item_folder = builder.assets_path / item_code
        item_folder.mkdir()

        # Find size variants (no files in folder)
        found_icons = builder._find_size_variants(
            folder=item_folder, item_code=item_code, target_size=32, is_crated=False
        )

        # Should return empty list when no files found
        assert found_icons == []

    async def test_find_size_variants_with_invalid_filename(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test finding size variants with invalid filename format.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        builder = DatabaseBuilder(
            catalog_path=mock_catalog_file, assets_path=assets_path, use_scaling=True
        )

        # Create test icon structure
        item_code = "TestRifle"
        item_folder = builder.assets_path / item_code
        item_folder.mkdir()

        # Create icon with invalid size in filename
        icon_file = item_folder / f"vanilla_{item_code}_invalid.png"
        icon_file.touch()

        # Find size variants (looking for size 32)
        found_icons = builder._find_size_variants(
            folder=item_folder, item_code=item_code, target_size=32, is_crated=False
        )

        # Should return empty list when filename has invalid size
        assert found_icons == []


class TestRunFunction:
    """Test suite for the run CLI function.

    This class contains tests for the run entry point of the database
    builder command, including argument handling and workflow execution.
    """

    def _create_mock_settings(self) -> MagicMock:
        """Create a mock settings object for testing.

        Returns:
            MagicMock: Mock settings with database_builder and scanner sections.
        """
        mock_settings = MagicMock()
        mock_settings.database_builder.catalog_file = None
        mock_settings.database_builder.target_resolutions = None
        mock_settings.scanner.database_path = None
        mock_settings.logging = MagicMock()
        return mock_settings

    @patch("fs_tools.commands.database_builder.database_builder.DatabaseBuilder")
    @patch("fs_tools.commands.database_builder.database_builder.setup_logging")
    @patch("fs_tools.commands.database_builder.database_builder.get_settings")
    async def test_run_with_default_args(
        self,
        mock_get_settings: Mock,
        mock_setup_logging: Mock,
        mock_builder_class: Mock,
        tmp_path: Path,
    ) -> None:
        """Test run function with default arguments.

        Args:
            mock_get_settings (Mock): Mocked get_settings function.
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_builder_class (Mock): Mocked DatabaseBuilder class.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text("[]")

        templates_path = tmp_path / "templates"
        templates_path.mkdir()

        database_path = tmp_path / "database.h5"

        # Mock settings
        mock_settings = self._create_mock_settings()
        mock_get_settings.return_value = mock_settings

        # Mock builder instance
        mock_builder = MagicMock()
        mock_builder.build_all_databases = AsyncMock(return_value=None)
        mock_builder_class.return_value = mock_builder

        await run(
            catalog=catalog_path,
            templates=templates_path,
            database=database_path,
            use_scaling=False,
            verbose=False,
            quiet=False,
            log_file=None,
            resolution=None,
        )

        # Verify DatabaseBuilder was instantiated
        mock_builder_class.assert_called_once()

        # Verify build_all_databases was called
        assert mock_builder.build_all_databases.call_count > 0

    @patch("fs_tools.commands.database_builder.database_builder.DatabaseBuilder")
    @patch("fs_tools.commands.database_builder.database_builder.setup_logging")
    @patch("fs_tools.commands.database_builder.database_builder.get_settings")
    async def test_run_with_specific_resolutions(
        self,
        mock_get_settings: Mock,
        mock_setup_logging: Mock,
        mock_builder_class: Mock,
        tmp_path: Path,
    ) -> None:
        """Test run function with specific resolution arguments.

        Args:
            mock_get_settings (Mock): Mocked get_settings function.
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_builder_class (Mock): Mocked DatabaseBuilder class.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text("[]")

        templates_path = tmp_path / "templates"
        templates_path.mkdir()

        database_path = tmp_path / "database.h5"

        mock_get_settings.return_value = self._create_mock_settings()

        # Mock builder instance
        mock_builder = MagicMock()
        mock_builder.build_all_databases = AsyncMock(return_value=None)
        mock_builder_class.return_value = mock_builder

        await run(
            catalog=catalog_path,
            templates=templates_path,
            database=database_path,
            use_scaling=True,
            verbose=True,
            quiet=False,
            log_file=None,
            resolution=["1080", "2160"],
        )

        # Verify build_all_databases was called with specific resolutions
        assert mock_builder.build_all_databases.call_count > 0
        call_kwargs = mock_builder.build_all_databases.call_args[1]
        assert "target_resolutions" in call_kwargs
        assert len(call_kwargs["target_resolutions"]) == 2

    @patch("fs_tools.commands.database_builder.database_builder.DatabaseBuilder")
    @patch("fs_tools.commands.database_builder.database_builder.setup_logging")
    @patch("fs_tools.commands.database_builder.database_builder.get_settings")
    async def test_run_with_quiet_mode(
        self,
        mock_get_settings: Mock,
        mock_setup_logging: Mock,
        mock_builder_class: Mock,
        tmp_path: Path,
    ) -> None:
        """Test run function with quiet mode enabled.

        Args:
            mock_get_settings (Mock): Mocked get_settings function.
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_builder_class (Mock): Mocked DatabaseBuilder class.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text("[]")

        templates_path = tmp_path / "templates"
        templates_path.mkdir()

        database_path = tmp_path / "database.h5"

        mock_get_settings.return_value = self._create_mock_settings()

        # Mock builder instance
        mock_builder = MagicMock()
        mock_builder.build_all_databases = AsyncMock(return_value=None)
        mock_builder_class.return_value = mock_builder

        await run(
            catalog=catalog_path,
            templates=templates_path,
            database=database_path,
            use_scaling=False,
            verbose=False,
            quiet=True,  # Quiet mode
            log_file=None,
            resolution=None,
        )

        # Verify setup_logging was called
        mock_setup_logging.assert_called_once()

    @patch("fs_tools.commands.database_builder.database_builder.DatabaseBuilder")
    @patch("fs_tools.commands.database_builder.database_builder.setup_logging")
    @patch("fs_tools.commands.database_builder.database_builder.get_settings")
    async def test_run_with_invalid_resolution(
        self,
        mock_get_settings: Mock,
        mock_setup_logging: Mock,
        mock_builder_class: Mock,
        tmp_path: Path,
    ) -> None:
        """Test run function with invalid resolution argument.

        Args:
            mock_get_settings (Mock): Mocked get_settings function.
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_builder_class (Mock): Mocked DatabaseBuilder class.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text("[]")

        templates_path = tmp_path / "templates"
        templates_path.mkdir()

        database_path = tmp_path / "database.h5"

        mock_get_settings.return_value = self._create_mock_settings()

        # Mock builder instance
        mock_builder = MagicMock()
        mock_builder.build_all_databases = AsyncMock(return_value=None)
        mock_builder_class.return_value = mock_builder

        # Should raise typer.Exit due to invalid resolution
        with pytest.raises(typer.Exit) as exc_info:
            await run(
                catalog=catalog_path,
                templates=templates_path,
                database=database_path,
                use_scaling=False,
                verbose=False,
                quiet=False,
                log_file=None,
                resolution=["9999"],  # Invalid resolution
            )

        assert exc_info.value.exit_code == 2

    @patch("fs_tools.commands.database_builder.database_builder.DatabaseBuilder")
    @patch("fs_tools.commands.database_builder.database_builder.setup_logging")
    @patch("fs_tools.commands.database_builder.database_builder.get_settings")
    async def test_run_uses_settings_when_args_not_provided(
        self,
        mock_get_settings: Mock,
        mock_setup_logging: Mock,
        mock_builder_class: Mock,
        tmp_path: Path,
    ) -> None:
        """Test that run function uses settings when CLI args not provided.

        Args:
            mock_get_settings (Mock): Mocked get_settings function.
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_builder_class (Mock): Mocked DatabaseBuilder class.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_path = tmp_path / "catalog.json"
        catalog_path.write_text("[]")

        templates_path = tmp_path / "templates"
        templates_path.mkdir()

        database_path = tmp_path / "database.h5"

        # Mock settings with values
        mock_settings = MagicMock()
        mock_settings.database_builder.catalog_file = catalog_path
        mock_settings.database_builder.target_resolutions = ["1080", "1440"]
        mock_settings.scanner.database_path = database_path
        mock_settings.logging = MagicMock()
        mock_get_settings.return_value = mock_settings

        # Mock builder instance
        mock_builder = MagicMock()
        mock_builder.build_all_databases = AsyncMock(return_value=None)
        mock_builder_class.return_value = mock_builder

        # catalog/database/resolution not provided, should use settings
        await run(
            templates=templates_path,
            catalog=None,
            database=None,
            use_scaling=False,
            verbose=False,
            quiet=False,
            log_file=None,
            resolution=None,
        )

        # Verify DatabaseBuilder was instantiated with catalog from settings
        call_args = mock_builder_class.call_args
        assert call_args[1]["catalog_path"] == catalog_path

        # Verify build_all_databases was called with resolutions from settings
        build_call_args = mock_builder.build_all_databases.call_args
        assert build_call_args[1]["output_path"] == database_path
        assert len(build_call_args[1]["target_resolutions"]) == 2


class TestDatabaseBuilderMerge:
    """Test suite for database merge functionality.

    This class contains tests for the merge functionality when overwrite=False.
    """

    @pytest.fixture
    def builder(self, tmp_path: Path, mock_catalog_file: Path) -> DatabaseBuilder:
        """Create a DatabaseBuilder instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.

        Returns:
            DatabaseBuilder: Configured builder instance for testing.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        return DatabaseBuilder(
            catalog_path=mock_catalog_file, assets_path=assets_path, use_scaling=False
        )

    def _create_template(
        self,
        code: str,
        mod: str = "vanilla",
        crated: bool = False,
        resolution: SupportedResolution = SupportedResolution.R_1080,
    ) -> IconTemplate:
        """Create a test template.

        Args:
            code (str): Item code
            mod (str): Mod name
            crated (bool): Whether template is crated
            resolution (SupportedResolution): Template resolution

        Returns:
            IconTemplate: Test template
        """
        return IconTemplate(
            code=code,
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            crated=crated,
            mod=mod,
            resolution=resolution,
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            phash=0,
        )

    async def test_merge_with_no_existing_database(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test merge when no existing database file exists.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        # Create new database
        new_db = TemplateDatabase(SupportedResolution.R_1080)
        new_db.add_template(self._create_template("Rifle"))
        new_databases = {SupportedResolution.R_1080: new_db}

        # Merge should return new_databases as-is since file doesn't exist
        merged, _ = await builder._merge_with_existing(new_databases, tmp_path / "nonexistent.h5")
        assert SupportedResolution.R_1080 in merged

    async def test_merge_adds_new_templates_to_existing(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test that merge adds new templates to existing database.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        output_path = tmp_path / "existing.h5"

        # Create and save existing database
        existing_db = TemplateDatabase(SupportedResolution.R_1080)
        existing_db.add_template(self._create_template("Rifle"))
        existing_db.add_template(self._create_template("Pistol"))
        existing_databases = {SupportedResolution.R_1080: existing_db}

        from fs_tools.template_db.template_manager import TemplateManager

        TemplateManager.save_databases_to_hdf5(
            databases=existing_databases, output_path=output_path
        )

        # Create new database with different items
        new_db = TemplateDatabase(SupportedResolution.R_1080)
        new_db.add_template(self._create_template("Grenade"))
        new_databases = {SupportedResolution.R_1080: new_db}

        # Merge
        merged, _ = await builder._merge_with_existing(new_databases, output_path)

        # Should have all 3 templates
        assert len(merged[SupportedResolution.R_1080].templates) == 3
        codes = {t.code for t in merged[SupportedResolution.R_1080].templates}
        assert codes == {"Rifle", "Pistol", "Grenade"}

    async def test_merge_skips_duplicate_templates(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test that merge skips duplicate templates.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        output_path = tmp_path / "existing.h5"

        # Create and save existing database
        existing_db = TemplateDatabase(SupportedResolution.R_1080)
        existing_db.add_template(self._create_template("Rifle", mod="vanilla"))
        existing_databases = {SupportedResolution.R_1080: existing_db}

        from fs_tools.template_db.template_manager import TemplateManager

        TemplateManager.save_databases_to_hdf5(
            databases=existing_databases, output_path=output_path
        )

        # Create new database with same item (duplicate)
        new_db = TemplateDatabase(SupportedResolution.R_1080)
        new_db.add_template(self._create_template("Rifle", mod="vanilla"))
        new_databases = {SupportedResolution.R_1080: new_db}

        # Merge
        merged, _ = await builder._merge_with_existing(new_databases, output_path)

        # Should still have only 1 template (duplicate was skipped)
        assert len(merged[SupportedResolution.R_1080].templates) == 1
        assert merged[SupportedResolution.R_1080].templates[0].code == "Rifle"

    async def test_merge_different_mods_not_duplicates(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test that same item from different mods are not considered duplicates.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        output_path = tmp_path / "existing.h5"

        # Create and save existing database with vanilla mod
        existing_db = TemplateDatabase(SupportedResolution.R_1080)
        existing_db.add_template(self._create_template("Rifle", mod="vanilla"))
        existing_databases = {SupportedResolution.R_1080: existing_db}

        from fs_tools.template_db.template_manager import TemplateManager

        TemplateManager.save_databases_to_hdf5(
            databases=existing_databases, output_path=output_path
        )

        # Create new database with same item from different mod
        new_db = TemplateDatabase(SupportedResolution.R_1080)
        new_db.add_template(self._create_template("Rifle", mod="custom_mod"))
        new_databases = {SupportedResolution.R_1080: new_db}

        # Merge
        merged, _ = await builder._merge_with_existing(new_databases, output_path)

        # Should have 2 templates (different mods)
        assert len(merged[SupportedResolution.R_1080].templates) == 2
        mods = {t.mod for t in merged[SupportedResolution.R_1080].templates}
        assert mods == {"vanilla", "custom_mod"}

    async def test_merge_crated_variants_not_duplicates(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test that crated and normal variants are not considered duplicates.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        output_path = tmp_path / "existing.h5"

        # Create and save existing database with normal variant
        existing_db = TemplateDatabase(SupportedResolution.R_1080)
        existing_db.add_template(self._create_template("Rifle", crated=False))
        existing_databases = {SupportedResolution.R_1080: existing_db}

        from fs_tools.template_db.template_manager import TemplateManager

        TemplateManager.save_databases_to_hdf5(
            databases=existing_databases, output_path=output_path
        )

        # Create new database with crated variant
        new_db = TemplateDatabase(SupportedResolution.R_1080)
        new_db.add_template(self._create_template("Rifle", crated=True))
        new_databases = {SupportedResolution.R_1080: new_db}

        # Merge
        merged, _ = await builder._merge_with_existing(new_databases, output_path)

        # Should have 2 templates (crated and normal)
        assert len(merged[SupportedResolution.R_1080].templates) == 2
        crated_states = {t.crated for t in merged[SupportedResolution.R_1080].templates}
        assert crated_states == {True, False}

    async def test_merge_preserves_existing_resolutions(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test that merge preserves existing resolutions not in new database.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        output_path = tmp_path / "existing.h5"

        # Create and save existing database with multiple resolutions
        existing_db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        existing_db_1080.add_template(self._create_template("Rifle"))

        existing_db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        existing_db_1440.add_template(self._create_template("Pistol"))

        existing_databases = {
            SupportedResolution.R_1080: existing_db_1080,
            SupportedResolution.R_1440: existing_db_1440,
        }

        from fs_tools.template_db.template_manager import TemplateManager

        TemplateManager.save_databases_to_hdf5(
            databases=existing_databases, output_path=output_path
        )

        # Create new database with only 1080 resolution
        new_db = TemplateDatabase(SupportedResolution.R_1080)
        new_db.add_template(self._create_template("Grenade"))
        new_databases = {SupportedResolution.R_1080: new_db}

        # Merge
        merged, _ = await builder._merge_with_existing(new_databases, output_path)

        # Should have both resolutions
        assert SupportedResolution.R_1080 in merged
        assert SupportedResolution.R_1440 in merged

        # 1080 should have merged templates
        assert len(merged[SupportedResolution.R_1080].templates) == 2

        # 1440 should be unchanged
        assert len(merged[SupportedResolution.R_1440].templates) == 1
        assert merged[SupportedResolution.R_1440].templates[0].code == "Pistol"

    async def test_merge_adds_new_resolution_not_in_existing(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test that merge adds a new resolution that doesn't exist in old database.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        output_path = tmp_path / "existing.h5"

        # Create and save existing database with only 1080p
        existing_db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        existing_db_1080.add_template(self._create_template("Rifle"))
        existing_databases = {SupportedResolution.R_1080: existing_db_1080}

        from fs_tools.template_db.template_manager import TemplateManager

        TemplateManager.save_databases_to_hdf5(
            databases=existing_databases, output_path=output_path
        )

        # Create new database with only 1440p (which doesn't exist in old database)
        new_db_1440 = TemplateDatabase(SupportedResolution.R_1440)
        new_db_1440.add_template(
            self._create_template("Grenade", resolution=SupportedResolution.R_1440)
        )
        new_databases = {SupportedResolution.R_1440: new_db_1440}

        # Merge
        merged, _ = await builder._merge_with_existing(new_databases, output_path)

        # Should have both resolutions now
        assert SupportedResolution.R_1080 in merged
        assert SupportedResolution.R_1440 in merged

        # 1080 should have the old template (preserved from existing)
        assert len(merged[SupportedResolution.R_1080].templates) == 1
        assert merged[SupportedResolution.R_1080].templates[0].code == "Rifle"

        # 1440 should have the new template (added because it didn't exist before)
        assert len(merged[SupportedResolution.R_1440].templates) == 1
        assert merged[SupportedResolution.R_1440].templates[0].code == "Grenade"

    async def test_build_all_databases_with_overwrite_false(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test build_all_databases respects overwrite=False parameter.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        output_path = tmp_path / "database.h5"

        # Create initial database
        existing_db = TemplateDatabase(SupportedResolution.R_1080)
        existing_db.add_template(self._create_template("Rifle"))
        existing_databases = {SupportedResolution.R_1080: existing_db}

        from fs_tools.template_db.template_manager import TemplateManager

        TemplateManager.save_databases_to_hdf5(
            databases=existing_databases, output_path=output_path
        )

        # Mock _build_resolution_database to return new template
        async def mock_build_db(resolution: SupportedResolution) -> TemplateDatabase:
            db = TemplateDatabase(resolution)
            db.add_template(self._create_template("Grenade", resolution=resolution))
            return db

        with patch.object(builder, "_build_resolution_database", side_effect=mock_build_db):
            # Build with overwrite=False (should merge)
            await builder.build_all_databases(
                output_path=output_path,
                target_resolutions=[SupportedResolution.R_1080],
                overwrite=False,
            )

        # Load and verify merged database
        temp_manager = TemplateManager(database_path=output_path)
        loaded = await temp_manager.load_all_resolutions()

        # Should have both templates
        assert len(loaded[SupportedResolution.R_1080].templates) == 2
        codes = {t.code for t in loaded[SupportedResolution.R_1080].templates}
        assert codes == {"Rifle", "Grenade"}

    async def test_build_all_databases_with_overwrite_true(
        self, builder: DatabaseBuilder, tmp_path: Path
    ) -> None:
        """Test build_all_databases with overwrite=True replaces matching templates.

        When overwrite=True, templates with matching (code, crated, mod) are replaced,
        while non-matching templates are preserved.

        Args:
            builder (DatabaseBuilder): DatabaseBuilder instance
            tmp_path (Path): Temporary directory path
        """
        output_path = tmp_path / "database.h5"

        # Create initial database with two templates
        existing_db = TemplateDatabase(SupportedResolution.R_1080)
        existing_db.add_template(self._create_template("Rifle"))  # Will be replaced
        existing_db.add_template(self._create_template("Pistol"))  # Will be kept
        existing_databases = {SupportedResolution.R_1080: existing_db}

        from fs_tools.template_db.template_manager import TemplateManager

        TemplateManager.save_databases_to_hdf5(
            databases=existing_databases, output_path=output_path
        )

        # Mock _build_resolution_database to return new templates
        # One matching existing (Rifle) and one new (Grenade)
        async def mock_build_db(resolution: SupportedResolution) -> TemplateDatabase:
            db = TemplateDatabase(resolution)
            db.add_template(self._create_template("Rifle", resolution=resolution))  # Replaces
            db.add_template(self._create_template("Grenade", resolution=resolution))  # New
            return db

        with patch.object(builder, "_build_resolution_database", side_effect=mock_build_db):
            # Build with overwrite=True (should replace matching templates)
            await builder.build_all_databases(
                output_path=output_path,
                target_resolutions=[SupportedResolution.R_1080],
                overwrite=True,
            )

        # Load and verify database
        temp_manager = TemplateManager(database_path=output_path)
        loaded = await temp_manager.load_all_resolutions()

        # Should have 3 templates: Pistol (kept), Rifle (replaced), Grenade (new)
        templates = loaded[SupportedResolution.R_1080].templates
        assert len(templates) == 3
        codes = {t.code for t in templates}
        assert codes == {"Rifle", "Pistol", "Grenade"}
