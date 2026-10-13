"""Tests for models.icon_template module.

This module contains comprehensive tests for the IconTemplate model,
including template creation, optimization data computation, and string representations.
"""

import numpy as np
import pytest

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.models.icon_template import IconTemplate


class TestIconTemplateCreation:
    """Test suite for IconTemplate creation and initialization."""

    def test_create_template_with_valid_data(self) -> None:
        """Test creating an IconTemplate with valid data."""
        # Create a simple test image
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        image[10:54, 10:54] = 255  # White square in center

        template = IconTemplate(
            image=image,
            code="TestRifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        assert template.code == "TestRifle"
        assert template.crated is False
        assert template.category == ItemCategory.Item
        assert template.faction == ItemFaction.NEUTRAL
        assert template.mod == "vanilla"
        assert template.resolution == SupportedResolution.R_1080
        assert template.image.shape == (64, 64, 3)

    def test_create_template_with_crated_variant(self) -> None:
        """Test creating an IconTemplate for a crated item."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        template = IconTemplate(
            image=image,
            code="TestRifle",
            crated=True,  # Crated variant
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        assert template.crated is True

    def test_create_template_strips_whitespace(self) -> None:
        """Test that string fields strip whitespace."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        template = IconTemplate(
            image=image,
            code="  TestRifle  ",  # Whitespace should be stripped
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="  vanilla  ",  # Whitespace should be stripped
            resolution=SupportedResolution.R_1080,
        )

        assert template.code == "TestRifle"
        assert template.mod == "vanilla"

    def test_create_template_with_empty_code_raises_error(self) -> None:
        """Test that creating template with empty code raises validation error."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        with pytest.raises(ValueError):
            IconTemplate(
                image=image,
                code="",  # Empty code should fail validation
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )


class TestIconTemplatePhash:
    """The perceptual hash is stored as read from the database."""

    def test_phash_defaults_to_zero(self) -> None:
        """A template built without a hash keeps the default."""
        template = IconTemplate(
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            code="TestRifle",
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        assert template.phash == 0

    def test_phash_is_kept_as_given(self) -> None:
        """The hash passed in is stored unchanged."""
        template = IconTemplate(
            image=np.zeros((32, 32, 3), dtype=np.uint8),
            code="TestRifle",
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
            phash=0x076C07DE07FF07FE,
        )

        assert template.phash == 0x076C07DE07FF07FE


class TestIconTemplateStringRepresentations:
    """Test suite for IconTemplate string representations."""

    def test_str_representation(self) -> None:
        """Test __str__ method returns human-readable representation."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        template = IconTemplate(
            image=image,
            code="TestRifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        str_repr = str(template)

        # Verify string contains key information
        assert "IconTemplate" in str_repr
        assert "TestRifle" in str_repr
        assert "crated=False" in str_repr
        assert "neutral" in str_repr
        assert "vanilla" in str_repr

    def test_str_representation_crated(self) -> None:
        """Test __str__ method for crated variant."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        template = IconTemplate(
            image=image,
            code="TestRifle",
            crated=True,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        str_repr = str(template)

        assert "crated=True" in str_repr

    def test_repr_representation(self) -> None:
        """Test __repr__ method returns detailed representation."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        template = IconTemplate(
            image=image,
            code="TestRifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.COLONIALS,
            mod="vanilla",
            resolution=SupportedResolution.R_2160,
        )

        repr_str = repr(template)

        # Verify repr contains detailed information
        assert "IconTemplate" in repr_str
        assert "code='TestRifle'" in repr_str
        assert "crated=False" in repr_str
        assert "mod='vanilla'" in repr_str
        assert "resolution='2160'" in repr_str
        assert "faction='Colonials'" in repr_str  # Capitalized
        assert "image_shape=(64, 64, 3)" in repr_str

    def test_repr_representation_with_hasattr_check(self) -> None:
        """Test __repr__ method checks for shape attribute."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        template = IconTemplate(
            image=image,
            code="TestRifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        # Test normal case - image has shape
        repr_str = repr(template)
        assert "image_shape=(64, 64, 3)" in repr_str


class TestIconTemplateEdgeCases:
    """Test suite for IconTemplate edge cases and boundary conditions."""

    def test_different_resolutions(self) -> None:
        """Test creating templates for different resolutions."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        for resolution in SupportedResolution:
            template = IconTemplate(
                image=image,
                code="TestRifle",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=resolution,
            )

            assert template.resolution == resolution

    def test_different_factions(self) -> None:
        """Test creating templates for different factions."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        for faction in ItemFaction:
            template = IconTemplate(
                image=image,
                code="TestRifle",
                crated=False,
                category=ItemCategory.Item,
                faction=faction,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )

            assert template.faction == faction

    def test_different_categories(self) -> None:
        """Test creating templates for different categories."""
        image = np.zeros((64, 64, 3), dtype=np.uint8)

        for category in ItemCategory:
            template = IconTemplate(
                image=image,
                code="TestRifle",
                crated=False,
                category=category,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )

            assert template.category == category

    def test_large_image(self) -> None:
        """Test creating template with larger image."""
        # Create larger image
        image = np.random.randint(0, 255, (256, 256, 3), dtype=np.uint8)

        template = IconTemplate(
            image=image,
            code="TestRifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        assert template.image.shape == (256, 256, 3)

    def test_small_image(self) -> None:
        """Test creating template with small image."""
        # Create small image
        image = np.random.randint(0, 255, (16, 16, 3), dtype=np.uint8)

        template = IconTemplate(
            image=image,
            code="TestRifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        assert template.image.shape == (16, 16, 3)
