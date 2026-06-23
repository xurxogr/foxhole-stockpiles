"""Tests for commands.generate_templates.generate_templates module.

This module contains comprehensive tests for the template generator command,
including TemplateGenerator class functionality, image processing, and
template generation for multiple resolutions.
"""

import argparse
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.models.catalog_item import CatalogItem
from fs_tools.commands.generate_templates.generate_templates import (
    TemplateGenerator,
    main,
)


class TestTemplateGeneratorInitialization:
    """Test suite for TemplateGenerator initialization.

    This class contains tests for TemplateGenerator instance creation
    with various parameter combinations and configurations.
    """

    async def test_initialization_with_valid_paths(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test TemplateGenerator initialization with valid paths.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        # Create mod folder
        (assets_path / "vanilla").mkdir()

        template_path = tmp_path / "templates"

        generator = TemplateGenerator(
            catalog_path=mock_catalog_file,
            assets_path=assets_path,
            template_path=template_path,
            filter_name=None,
        )

        assert generator.assets_path == assets_path
        assert generator.template_path == template_path
        assert generator.filter_name is None
        assert len(generator.catalog_data) > 0
        assert generator.template_path.exists()

    async def test_initialization_with_filter(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test TemplateGenerator initialization with filter.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()
        (assets_path / "vanilla").mkdir()

        template_path = tmp_path / "templates"

        generator = TemplateGenerator(
            catalog_path=mock_catalog_file,
            assets_path=assets_path,
            template_path=template_path,
            filter_name="Rifle",
        )

        assert generator.filter_name == "Rifle"

    async def test_initialization_catalog_not_found(self, tmp_path: Path) -> None:
        """Test TemplateGenerator initialization with missing catalog.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_path = tmp_path / "nonexistent.json"
        assets_path = tmp_path / "assets"
        assets_path.mkdir()
        template_path = tmp_path / "templates"

        with pytest.raises(FileNotFoundError, match="Catalog file not found"):
            TemplateGenerator(
                catalog_path=catalog_path,
                assets_path=assets_path,
                template_path=template_path,
            )

    async def test_initialization_assets_not_found(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test TemplateGenerator initialization with missing assets.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "nonexistent_assets"
        template_path = tmp_path / "templates"

        with pytest.raises(FileNotFoundError, match="Assets directory not found"):
            TemplateGenerator(
                catalog_path=mock_catalog_file,
                assets_path=assets_path,
                template_path=template_path,
            )


class TestTemplateGeneratorMethods:
    """Test suite for TemplateGenerator methods.

    This class contains tests for the core functionality of TemplateGenerator
    including image loading, icon processing, and template generation.
    """

    @pytest.fixture
    def generator(self, tmp_path: Path, mock_catalog_file: Path) -> TemplateGenerator:
        """Create a TemplateGenerator instance for testing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.

        Returns:
            TemplateGenerator: Configured generator instance for testing.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()
        (assets_path / "vanilla").mkdir()

        template_path = tmp_path / "templates"

        return TemplateGenerator(
            catalog_path=mock_catalog_file,
            assets_path=assets_path,
            template_path=template_path,
        )

    async def test_discover_mods(self, tmp_path: Path, mock_catalog_file: Path) -> None:
        """Test mod discovery in assets directory.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        # Create multiple mod folders
        (assets_path / "vanilla").mkdir()
        (assets_path / "mod1").mkdir()
        (assets_path / "mod2").mkdir()

        template_path = tmp_path / "templates"

        generator = TemplateGenerator(
            catalog_path=mock_catalog_file,
            assets_path=assets_path,
            template_path=template_path,
        )

        # Vanilla should be first
        assert generator.available_mods[0] == "vanilla"
        assert len(generator.available_mods) == 3

    async def test_calculate_icon_size(self, generator: TemplateGenerator, tmp_path: Path) -> None:
        """Test icon size calculation for different resolutions.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        size_1080 = generator._calculate_icon_size(SupportedResolution.R_1080)
        size_2160 = generator._calculate_icon_size(SupportedResolution.R_2160)

        # 1080p should be 32px, 2160p should be 64px
        assert size_1080 == 32
        assert size_2160 == 64

    async def test_load_icon_image_success(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading icon image successfully.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create test icon file
        icon_path = "War/Content/test_icon"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        # Mock PIL Image loading with RGBA image
        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.zeros((64, 64, 4), dtype=np.uint8)
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager using __enter__ and __exit__ as regular methods
        class MockContextManager:
            def __enter__(self) -> Any:
                return mock_img

            def __exit__(self, *args: Any) -> None:
                return None

        mock_open = MagicMock(return_value=MockContextManager())
        with patch("PIL.Image.open", mock_open):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._load_icon_image(icon_path=icon_path, mod_name="vanilla")

        assert result is not None
        assert result.shape == (64, 64, 4)

    async def test_load_icon_image_not_found(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading icon image when file doesn't exist.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = "War/Content/nonexistent"

        result = await generator._load_icon_image(icon_path=icon_path, mod_name="vanilla")

        assert result is None

    async def test_filter_catalog_items_with_filter(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test filtering catalog items by name.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Filter for items containing "Rifle"
        filtered = generator._filter_catalog_items(filter_name="Rifle")

        # Should filter the catalog
        assert isinstance(filtered, list)
        # All filtered items should contain "Rifle" in code
        for item in filtered:
            assert "rifle" in item.code.lower()

    async def test_filter_catalog_items_no_filter(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test catalog items without filter.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        filtered = generator._filter_catalog_items(filter_name=None)

        # Should return all items
        assert filtered == generator.catalog_data

    async def test_apply_subicon_effects(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test applying subicon color effects.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create test image
        test_image = np.ones((32, 32, 4), dtype=np.uint8) * 128

        result = generator._apply_subicon_effects(image=test_image)

        # Result should have same shape
        assert result.shape == test_image.shape
        # Result should be different from input (color tint applied)
        assert not np.array_equal(result[:, :, :3], test_image[:, :, :3])

    async def test_load_crate_icon_success(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading crate icon successfully.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create crate icon file
        crate_path = (
            generator.assets_path / "vanilla" / "War/Content/Textures/UI/Menus/IconFilterCrates.png"
        )
        crate_path.parent.mkdir(parents=True, exist_ok=True)
        crate_path.touch()

        # Mock PIL Image loading with RGBA image
        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.ones((64, 64, 4), dtype=np.uint8)
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_open = MagicMock(return_value=mock_cm)
        with patch("PIL.Image.open", mock_open):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._load_crate_icon()

        assert result is not None
        assert result.shape == (64, 64, 4)

    async def test_load_crate_icon_not_found(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading crate icon when not found in any mod.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Don't create the file, so it won't be found

        with pytest.raises(FileNotFoundError, match="Crate icon not found"):
            await generator._load_crate_icon()

    async def test_load_icon_image_grayscale(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading grayscale icon and converting to BGRA.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = "War/Content/test_icon"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        # Mock PIL Image loading - convert() will handle grayscale to RGBA
        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.zeros((64, 64, 4), dtype=np.uint8)
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_open = MagicMock(return_value=mock_cm)
        with patch("PIL.Image.open", mock_open):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._load_icon_image(icon_path=icon_path, mod_name="vanilla")

                assert result is not None
                # PIL's convert("RGBA") handles grayscale automatically
                mock_img.convert.assert_called_once_with("RGBA")

    async def test_load_icon_image_bgr(self, generator: TemplateGenerator, tmp_path: Path) -> None:
        """Test loading BGR icon and converting to BGRA.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = "War/Content/test_icon"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        # Mock PIL Image loading - convert() will handle RGB to RGBA
        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.zeros((64, 64, 4), dtype=np.uint8)
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_open = MagicMock(return_value=mock_cm)
        with patch("PIL.Image.open", mock_open):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._load_icon_image(icon_path=icon_path, mod_name="vanilla")

                assert result is not None
                # PIL's convert("RGBA") handles RGB/BGR automatically
                mock_img.convert.assert_called_once_with("RGBA")

    async def test_load_icon_image_imread_returns_none(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading icon when PIL Image.open raises exception.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = "War/Content/test_icon"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        # Mock PIL Image.open raising an exception (corrupted file)
        mock_open = MagicMock(side_effect=Exception("Corrupted image"))
        with patch("PIL.Image.open", mock_open):
            result = await generator._load_icon_image(icon_path=icon_path, mod_name="vanilla")

        assert result is None

    async def test_load_icon_image_exception(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading icon when an exception occurs.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = "War/Content/test_icon"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        # Mock PIL Image.open to raise exception
        def raise_error(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Read error")

        mock_open = MagicMock(side_effect=raise_error)
        with patch("PIL.Image.open", mock_open):
            result = await generator._load_icon_image(icon_path=icon_path, mod_name="vanilla")

        assert result is None

    async def test_load_subicon_cached_with_cache_hit(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading subicon with cache hit.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        subicon_path = "War/Content/test_subicon"
        mock_subicon = np.ones((32, 32, 4), dtype=np.uint8)

        # Prepopulate cache
        generator.subicon_cache["vanilla:War/Content/test_subicon"] = mock_subicon

        result = await generator._load_subicon_cached(subicon_path=subicon_path, mod_name="vanilla")

        assert result is not None
        assert np.array_equal(result, mock_subicon)

    async def test_load_subicon_cached_vanilla_fallback(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading subicon with vanilla fallback.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create multiple mod folders
        (generator.assets_path / "mod1").mkdir()

        subicon_path = "War/Content/test_subicon"
        vanilla_path = generator.assets_path / "vanilla" / f"{subicon_path}.png"
        vanilla_path.parent.mkdir(parents=True, exist_ok=True)
        vanilla_path.touch()

        # Mock PIL Image loading - fails for mod1, succeeds for vanilla
        from pathlib import Path as PathType

        def image_open_side_effect(path: PathType) -> MagicMock:
            if "vanilla" in str(path):
                mock_img = MagicMock()
                mock_rgba = MagicMock()
                mock_img.convert = MagicMock(return_value=mock_rgba)
                mock_cm = MagicMock()
                mock_cm.__enter__ = MagicMock(return_value=mock_img)
                mock_cm.__exit__ = MagicMock(return_value=None)
                return mock_cm
            raise FileNotFoundError("Not found")

        mock_rgba_array = np.ones((32, 32, 4), dtype=np.uint8) * 255  # Full alpha
        mock_open = MagicMock(side_effect=image_open_side_effect)
        with patch("PIL.Image.open", mock_open):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._load_subicon_cached(
                    subicon_path=subicon_path, mod_name="mod1"
                )

        # Should fallback to vanilla (non-blank subicon)
        assert result is not None
        # Cache should have entries for both mod1 (pointing to vanilla result) and vanilla
        assert "mod1:War/Content/test_subicon" in generator.subicon_cache

    async def test_load_subicon_cached_not_found_anywhere(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test loading subicon when not found anywhere.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        subicon_path = "War/Content/nonexistent"

        mock_open = MagicMock(side_effect=FileNotFoundError("Not found"))
        with patch("PIL.Image.open", mock_open):
            result = await generator._load_subicon_cached(
                subicon_path=subicon_path, mod_name="vanilla"
            )

        assert result is None
        # Should cache None result
        assert generator.subicon_cache["vanilla:War/Content/nonexistent"] is None

    def test_is_blank_subicon_fully_transparent(self, generator: TemplateGenerator) -> None:
        """Test blank subicon detection with fully transparent image."""
        # All pixels have alpha = 0 (fully transparent)
        blank_image = np.zeros((32, 32, 4), dtype=np.uint8)
        assert generator._is_blank_subicon(blank_image)

    def test_is_blank_subicon_low_alpha(self, generator: TemplateGenerator) -> None:
        """Test blank subicon detection with low alpha values."""
        # All pixels have alpha = 5 (below threshold of 10)
        low_alpha_image = np.ones((32, 32, 4), dtype=np.uint8) * 5
        assert generator._is_blank_subicon(low_alpha_image)

    def test_is_blank_subicon_valid_image(self, generator: TemplateGenerator) -> None:
        """Test blank subicon detection with valid visible image."""
        # Create image with variation (like a real subicon)
        visible_image = np.zeros((32, 32, 4), dtype=np.uint8)
        visible_image[:, :, 3] = 255  # Full alpha
        # Add some bright varied colors (not solid)
        visible_image[:16, :, 0] = 200  # Blue in top half
        visible_image[16:, :, 1] = 180  # Green in bottom half
        visible_image[:, :16, 2] = 220  # Red in left half
        assert not generator._is_blank_subicon(visible_image)

    def test_is_blank_subicon_partial_transparency(self, generator: TemplateGenerator) -> None:
        """Test blank subicon detection with partial transparency and varied colors."""
        # 50% of pixels have alpha > 10, with varied bright colors
        partial_image = np.zeros((32, 32, 4), dtype=np.uint8)
        partial_image[:16, :, 3] = 255  # Top half is visible
        # Add varied bright colors to visible area
        partial_image[:16, :16, 0] = 200
        partial_image[:16, 16:, 1] = 180
        partial_image[:8, :, 2] = 220
        assert not generator._is_blank_subicon(partial_image)

    def test_is_blank_subicon_solid_gray(self, generator: TemplateGenerator) -> None:
        """Test blank subicon detection with solid gray (clean-icons style)."""
        # Solid dark gray with full alpha - should be detected as blank
        gray_image = np.ones((32, 32, 4), dtype=np.uint8) * 60
        gray_image[:, :, 3] = 255  # Full alpha
        assert generator._is_blank_subicon(gray_image)

    def test_is_blank_subicon_solid_bright(self, generator: TemplateGenerator) -> None:
        """Test that solid bright colors are NOT detected as blank."""
        # Solid white - should NOT be blank (bright color)
        white_image = np.ones((32, 32, 4), dtype=np.uint8) * 255
        assert not generator._is_blank_subicon(white_image)

    def test_is_blank_subicon_edge_case_threshold(self, generator: TemplateGenerator) -> None:
        """Test blank subicon detection at threshold boundary."""
        # Just under 5% of pixels visible (should be blank due to low visibility)
        edge_image = np.zeros((100, 100, 4), dtype=np.uint8)
        edge_image[:4, :, 3] = 255  # 4% visible
        edge_image[:4, :, :3] = 200  # Give it bright colors
        assert generator._is_blank_subicon(edge_image)

        # Just over 5% of pixels visible with varied colors (should be valid)
        edge_image[:6, :, 3] = 255  # 6% visible
        edge_image[:3, :, 0] = 200
        edge_image[3:6, :, 1] = 180
        assert not generator._is_blank_subicon(edge_image)

    async def test_add_subicon_bottom_right(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test adding subicon in bottom-right corner.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        main_icon = np.zeros((64, 64, 4), dtype=np.uint8)
        subicon = np.ones((32, 32, 4), dtype=np.uint8) * 255

        result = generator._add_subicon(
            main_icon=main_icon, subicon=subicon, target_size=64, top_left=False
        )

        assert result.shape == (64, 64, 4)

    async def test_create_base_icon_without_subicon(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test creating base icon without subicon.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        main_icon = np.ones((32, 32, 4), dtype=np.uint8) * 128

        result = generator._create_base_icon(main_icon=main_icon, subicon=None, target_size=64)

        assert result.shape == (64, 64, 4)

    async def test_generate_templates_item_missing_code(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test generating templates for item with missing code.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create item with empty code
        catalog_item = CatalogItem(
            code="",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path="War/Content/test",
            subicon_path="",
        )

        result = await generator._generate_templates_for_item_and_mod(
            item=catalog_item, mod_name="vanilla"
        )

        assert result is False

    async def test_generate_templates_icon_not_found(
        self, generator: TemplateGenerator, tmp_path: Path
    ) -> None:
        """Test generating templates when icon not found.

        Args:
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Don't create the icon file

        catalog_item = CatalogItem(
            code="TestItem",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path="War/Content/missing",
            subicon_path="",
        )

        result = await generator._generate_templates_for_item_and_mod(
            item=catalog_item, mod_name="vanilla"
        )

        assert result is False

    @patch("fs_tools.commands.generate_templates.generate_templates.write_bgr")
    async def test_generate_templates_with_subicon(
        self,
        mock_imwrite: Mock,
        generator: TemplateGenerator,
        tmp_path: Path,
    ) -> None:
        """Test generating templates with subicon.

        Args:
            mock_imwrite (Mock): Mocked write_bgr function.
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create real icon and subicon image files for PIL to load
        from PIL import Image

        icon_path = "War/Content/test_rifle"
        subicon_path = "War/Content/test_subicon"

        icon_full = generator.assets_path / "vanilla" / f"{icon_path}.png"
        subicon_full = generator.assets_path / "vanilla" / f"{subicon_path}.png"

        icon_full.parent.mkdir(parents=True, exist_ok=True)
        subicon_full.parent.mkdir(parents=True, exist_ok=True)

        # Create a real 64x64 RGBA icon image
        icon_img = Image.new("RGBA", (64, 64), (128, 128, 128, 255))
        icon_img.save(icon_full)

        # Create a real 32x32 RGBA subicon image
        subicon_img = Image.new("RGBA", (32, 32), (200, 200, 200, 255))
        subicon_img.save(subicon_full)

        generator.crate_icon = np.ones((64, 64, 4), dtype=np.uint8)

        mock_imwrite.return_value = True

        catalog_item = CatalogItem(
            code="TestRifle",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path=icon_path,
            subicon_path=subicon_path,
        )

        result = await generator._generate_templates_for_item_and_mod(
            item=catalog_item, mod_name="vanilla"
        )

        assert result is True

    @patch("fs_tools.commands.generate_templates.generate_templates.write_bgr")
    async def test_generate_templates_crate_icon_not_loaded(
        self,
        mock_imwrite: Mock,
        generator: TemplateGenerator,
        tmp_path: Path,
    ) -> None:
        """Test generating templates when crate icon is not loaded.

        Args:
            mock_imwrite (Mock): Mocked write_bgr function.
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = "War/Content/test_rifle"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        # Don't set crate_icon
        generator.crate_icon = None

        # Mock PIL Image loading

        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.ones((64, 64, 4), dtype=np.uint8) * 128
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_imwrite.return_value = True

        catalog_item = CatalogItem(
            code="TestRifle",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path=icon_path,
            subicon_path="",
        )

        with patch("PIL.Image.open", return_value=mock_cm):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._generate_templates_for_item_and_mod(
                    item=catalog_item, mod_name="vanilla"
                )

        # Should return partial success (True) since normal templates succeed
        # Only crated templates fail, so success_count > 0
        assert result is True

    @patch("fs_tools.commands.generate_templates.generate_templates.write_bgr")
    async def test_generate_templates_imwrite_exception(
        self,
        mock_imwrite: Mock,
        generator: TemplateGenerator,
        tmp_path: Path,
    ) -> None:
        """Test generating templates when imwrite raises exception.

        Args:
            mock_imwrite (Mock): Mocked write_bgr function.
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        icon_path = "War/Content/test_rifle"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        generator.crate_icon = np.ones((64, 64, 4), dtype=np.uint8)

        # Mock PIL Image loading

        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.ones((64, 64, 4), dtype=np.uint8) * 128
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_imwrite.side_effect = RuntimeError("Write error")

        catalog_item = CatalogItem(
            code="TestRifle",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path=icon_path,
            subicon_path="",
        )

        with patch("PIL.Image.open", return_value=mock_cm):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._generate_templates_for_item_and_mod(
                    item=catalog_item, mod_name="vanilla"
                )

        # Should return False due to errors
        assert result is False

    @patch("fs_tools.commands.generate_templates.generate_templates.write_bgr")
    async def test_generate_all_templates_success(
        self,
        mock_imwrite: Mock,
        tmp_path: Path,
        mock_catalog_file: Path,
    ) -> None:
        """Test generating all templates successfully.

        Args:
            mock_imwrite (Mock): Mocked write_bgr function.
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        # Create a custom catalog with valid items
        catalog_data = [
            {
                "CodeName": "TestRifle",
                "FactionVariant": "EFactionId::Neutral",
                "Icon": "War/Content/test_rifle",
                "SubTypeIcon": "",
            }
        ]
        catalog_path = tmp_path / "custom_catalog.json"
        with open(catalog_path, "w") as f:
            json.dump(catalog_data, f)

        assets_path = tmp_path / "assets"
        assets_path.mkdir()
        (assets_path / "vanilla").mkdir()

        generator = TemplateGenerator(
            catalog_path=catalog_path,
            assets_path=assets_path,
            template_path=tmp_path / "templates",
        )

        # Create necessary icon files
        crate_path = assets_path / "vanilla" / "War/Content/Textures/UI/Menus/IconFilterCrates.png"
        crate_path.parent.mkdir(parents=True, exist_ok=True)
        crate_path.touch()

        icon_path = assets_path / "vanilla" / "War/Content/test_rifle.png"
        icon_path.parent.mkdir(parents=True, exist_ok=True)
        icon_path.touch()

        # Mock PIL Image loading

        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.ones((64, 64, 4), dtype=np.uint8)
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_imwrite.return_value = True

        with patch("PIL.Image.open", return_value=mock_cm):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator.generate_all_templates()

        assert result is True

    async def test_generate_all_templates_no_mods(
        self, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test generating templates when no mods are found.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "empty_assets"
        assets_path.mkdir()

        template_path = tmp_path / "templates"

        generator = TemplateGenerator(
            catalog_path=mock_catalog_file,
            assets_path=assets_path,
            template_path=template_path,
        )

        result = await generator.generate_all_templates()

        assert result is False

    async def test_generate_all_templates_no_matching_filter(
        self,
        tmp_path: Path,
        mock_catalog_file: Path,
    ) -> None:
        """Test generating templates when filter matches nothing.

        Args:
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()
        (assets_path / "vanilla").mkdir()

        template_path = tmp_path / "templates"

        generator = TemplateGenerator(
            catalog_path=mock_catalog_file,
            assets_path=assets_path,
            template_path=template_path,
            filter_name="NonexistentItem",
        )

        # Create crate icon
        crate_path = (
            generator.assets_path / "vanilla" / "War/Content/Textures/UI/Menus/IconFilterCrates.png"
        )
        crate_path.parent.mkdir(parents=True, exist_ok=True)
        crate_path.touch()

        # Mock PIL Image loading

        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.ones((64, 64, 4), dtype=np.uint8)
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_open = MagicMock(return_value=mock_cm)
        with patch("PIL.Image.open", mock_open):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator.generate_all_templates()

        assert result is False

    @patch("fs_tools.commands.generate_templates.generate_templates.write_bgr")
    async def test_generate_templates_for_item_and_mod(
        self,
        mock_imwrite: Mock,
        generator: TemplateGenerator,
        tmp_path: Path,
    ) -> None:
        """Test generating templates for a single item from a mod.

        Args:
            mock_imwrite (Mock): Mocked write_bgr function.
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create test icon file
        icon_path = "War/Content/test_rifle"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        # Mock crate icon
        generator.crate_icon = np.ones((64, 64, 4), dtype=np.uint8)

        # Mock PIL Image loading

        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.ones((64, 64, 4), dtype=np.uint8) * 128
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_imwrite.return_value = True

        # Create catalog item
        catalog_item = CatalogItem(
            code="TestRifle",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path=icon_path,
            subicon_path="",
        )

        with patch("PIL.Image.open", return_value=mock_cm):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._generate_templates_for_item_and_mod(
                    item=catalog_item, mod_name="vanilla"
                )

        # Should succeed
        assert result is True

        # Verify output directories were created
        assert (generator.template_path / "TestRifle").exists()
        assert (generator.template_path / "TestRifle_crated").exists()

    @patch("fs_tools.commands.generate_templates.generate_templates.write_bgr")
    async def test_generate_templates_skips_crated_for_non_cratable_items(
        self,
        mock_imwrite: Mock,
        generator: TemplateGenerator,
        tmp_path: Path,
    ) -> None:
        """Test that crated templates are not generated for non-cratable items.

        Args:
            mock_imwrite (Mock): Mocked write_bgr function.
            generator (TemplateGenerator): TemplateGenerator instance from fixture.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        # Create test icon file
        icon_path = "War/Content/test_material"
        full_path = generator.assets_path / "vanilla" / f"{icon_path}.png"
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.touch()

        # Mock crate icon
        generator.crate_icon = np.ones((64, 64, 4), dtype=np.uint8)

        # Mock PIL Image loading
        mock_img = MagicMock()
        mock_rgba = MagicMock()
        mock_rgba_array = np.ones((64, 64, 4), dtype=np.uint8) * 128
        mock_img.convert = MagicMock(return_value=mock_rgba)

        # Create context manager mock properly
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value=mock_img)
        mock_cm.__exit__ = MagicMock(return_value=None)

        mock_imwrite.return_value = True

        # Create catalog item with cratable=False
        catalog_item = CatalogItem(
            code="RawMaterial",
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            icon_path=icon_path,
            subicon_path="",
            cratable=False,
        )

        with patch("PIL.Image.open", return_value=mock_cm):
            with patch("numpy.array", return_value=mock_rgba_array):
                result = await generator._generate_templates_for_item_and_mod(
                    item=catalog_item, mod_name="vanilla"
                )

        # Should succeed
        assert result is True

        # Verify only normal output directory was created (not crated)
        assert (generator.template_path / "RawMaterial").exists()
        assert not (generator.template_path / "RawMaterial_crated").exists()


class TestMainFunction:
    """Test suite for the main CLI function.

    This class contains tests for the main entry point of the generate
    templates command, including argument parsing and workflow execution.
    """

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.generate_templates.generate_templates.TemplateGenerator")
    @patch("fs_tools.commands.generate_templates.generate_templates.setup_logging")
    async def test_main_with_default_args(
        self,
        mock_setup_logging: Mock,
        mock_generator_class: Mock,
        mock_args: Mock,
        tmp_path: Path,
        mock_catalog_file: Path,
    ) -> None:
        """Test main function with default arguments.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_generator_class (Mock): Mocked TemplateGenerator class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        templates_path = tmp_path / "templates"

        mock_args.return_value = argparse.Namespace(
            catalog=mock_catalog_file,
            assets=assets_path,
            templates=templates_path,
            filter=None,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Mock generator instance
        mock_generator = MagicMock()
        mock_generator.generate_all_templates = AsyncMock(return_value=True)
        mock_generator_class.return_value = mock_generator

        await main()

        # Verify TemplateGenerator was instantiated
        mock_generator_class.assert_called_once()

        # Verify generate_all_templates was called
        assert mock_generator.generate_all_templates.call_count > 0

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.generate_templates.generate_templates.TemplateGenerator")
    @patch("fs_tools.commands.generate_templates.generate_templates.setup_logging")
    async def test_main_with_filter(
        self,
        mock_setup_logging: Mock,
        mock_generator_class: Mock,
        mock_args: Mock,
        tmp_path: Path,
        mock_catalog_file: Path,
    ) -> None:
        """Test main function with filter argument.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_generator_class (Mock): Mocked TemplateGenerator class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        templates_path = tmp_path / "templates"

        mock_args.return_value = argparse.Namespace(
            catalog=mock_catalog_file,
            assets=assets_path,
            templates=templates_path,
            filter="Rifle",
            verbose=True,
            quiet=False,
            log_file=None,
        )

        # Mock generator instance
        mock_generator = MagicMock()

        async def mock_generate_all() -> bool:
            return True

        mock_generator.generate_all_templates = mock_generate_all
        mock_generator_class.return_value = mock_generator

        await main()

        # Verify TemplateGenerator was called with filter
        call_kwargs = mock_generator_class.call_args[1]
        assert call_kwargs["filter_name"] == "Rifle"

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.generate_templates.generate_templates.setup_logging")
    async def test_main_catalog_not_found(
        self, mock_setup_logging: Mock, mock_args: Mock, tmp_path: Path
    ) -> None:
        """Test main function when catalog file is not found.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
        """
        catalog_path = tmp_path / "nonexistent.json"
        assets_path = tmp_path / "assets"
        assets_path.mkdir()
        templates_path = tmp_path / "templates"

        mock_args.return_value = argparse.Namespace(
            catalog=catalog_path,
            assets=assets_path,
            templates=templates_path,
            filter=None,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.generate_templates.generate_templates.TemplateGenerator")
    @patch("fs_tools.commands.generate_templates.generate_templates.setup_logging")
    async def test_main_generation_failure(
        self,
        mock_setup_logging: Mock,
        mock_generator_class: Mock,
        mock_args: Mock,
        tmp_path: Path,
        mock_catalog_file: Path,
    ) -> None:
        """Test main function when template generation fails.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_generator_class (Mock): Mocked TemplateGenerator class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()

        templates_path = tmp_path / "templates"

        mock_args.return_value = argparse.Namespace(
            catalog=mock_catalog_file,
            assets=assets_path,
            templates=templates_path,
            filter=None,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Mock generator instance to return failure
        mock_generator = MagicMock()

        async def mock_generate_all() -> bool:
            return False

        mock_generator.generate_all_templates = mock_generate_all
        mock_generator_class.return_value = mock_generator

        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.generate_templates.generate_templates.setup_logging")
    async def test_main_assets_not_found(
        self, mock_setup_logging: Mock, mock_args: Mock, tmp_path: Path, mock_catalog_file: Path
    ) -> None:
        """Test main function when assets directory is not found.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "nonexistent_assets"
        templates_path = tmp_path / "templates"

        mock_args.return_value = argparse.Namespace(
            catalog=mock_catalog_file,
            assets=assets_path,
            templates=templates_path,
            filter=None,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.generate_templates.generate_templates.TemplateGenerator")
    @patch("fs_tools.commands.generate_templates.generate_templates.setup_logging")
    async def test_main_with_quiet_mode(
        self,
        mock_setup_logging: Mock,
        mock_generator_class: Mock,
        mock_args: Mock,
        tmp_path: Path,
        mock_catalog_file: Path,
    ) -> None:
        """Test main function with quiet mode.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_generator_class (Mock): Mocked TemplateGenerator class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()
        templates_path = tmp_path / "templates"

        mock_args.return_value = argparse.Namespace(
            catalog=mock_catalog_file,
            assets=assets_path,
            templates=templates_path,
            filter=None,
            verbose=False,
            quiet=True,
            log_file=None,
        )

        # Mock generator instance
        mock_generator = MagicMock()
        mock_generator.generate_all_templates = AsyncMock(return_value=True)
        mock_generator_class.return_value = mock_generator

        await main()

        # Verify setup_logging was called
        assert mock_setup_logging.call_count > 0

    @patch("argparse.ArgumentParser.parse_args")
    @patch("fs_tools.commands.generate_templates.generate_templates.TemplateGenerator")
    @patch("fs_tools.commands.generate_templates.generate_templates.setup_logging")
    async def test_main_with_exception(
        self,
        mock_setup_logging: Mock,
        mock_generator_class: Mock,
        mock_args: Mock,
        tmp_path: Path,
        mock_catalog_file: Path,
    ) -> None:
        """Test main function when an exception occurs during generation.

        Args:
            mock_setup_logging (Mock): Mocked setup_logging function.
            mock_generator_class (Mock): Mocked TemplateGenerator class.
            mock_args (Mock): Mocked ArgumentParser.parse_args method.
            tmp_path (Path): Temporary directory path from pytest fixture.
            mock_catalog_file (Path): Mock catalog file from fixture.
        """
        assets_path = tmp_path / "assets"
        assets_path.mkdir()
        templates_path = tmp_path / "templates"

        mock_args.return_value = argparse.Namespace(
            catalog=mock_catalog_file,
            assets=assets_path,
            templates=templates_path,
            filter=None,
            verbose=False,
            quiet=False,
            log_file=None,
        )

        # Mock generator to raise exception
        mock_generator_class.side_effect = RuntimeError("Unexpected error")

        # Should exit with code 1
        with pytest.raises(SystemExit) as exc_info:
            await main()

        assert exc_info.value.code == 1
