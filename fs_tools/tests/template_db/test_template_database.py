"""Tests for fs_tools.template_db.template_database module.

This module contains comprehensive tests for the TemplateDatabase class,
which manages resolution-specific template storage with faction, mod, and
category filtering capabilities.
"""

import numpy as np
import pytest

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from fs_tools.models.icon_template import IconTemplate
from fs_tools.template_db.template_database import TemplateDatabase


class TestTemplateDatabaseInitialization:
    """Test suite for TemplateDatabase initialization.

    This class contains tests for proper initialization of the TemplateDatabase
    including resolution handling and initial state validation.
    """

    def test_init_with_resolution(self) -> None:
        """Test initializing TemplateDatabase with a resolution."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        assert db.resolution == SupportedResolution.R_1080
        assert db.templates == []
        assert db.faction_lookup == {}
        assert db.mod_lookup == {}
        assert db.category_lookup == {}

    def test_init_different_resolutions(self) -> None:
        """Test initializing with different resolutions."""
        db_720 = TemplateDatabase(SupportedResolution.R_720)
        db_1080 = TemplateDatabase(SupportedResolution.R_1080)
        db_1440 = TemplateDatabase(SupportedResolution.R_1440)

        assert db_720.resolution == SupportedResolution.R_720
        assert db_1080.resolution == SupportedResolution.R_1080
        assert db_1440.resolution == SupportedResolution.R_1440


class TestAddTemplate:
    """Test suite for TemplateDatabase.add_template method.

    This class contains tests for adding templates and updating lookup tables.
    """

    @pytest.fixture
    def sample_template(self) -> IconTemplate:
        """Create a sample template for testing.

        Returns:
            IconTemplate: A sample icon template.
        """
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        return IconTemplate(
            image=image,
            code="Rifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.NEUTRAL,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

    def test_add_single_template(self, sample_template: IconTemplate) -> None:
        """Test adding a single template.

        Args:
            sample_template (IconTemplate): Sample template from fixture.
        """
        db = TemplateDatabase(SupportedResolution.R_1080)

        db.add_template(sample_template)

        assert len(db.templates) == 1
        assert db.templates[0] == sample_template

    def test_add_template_updates_faction_lookup(self, sample_template: IconTemplate) -> None:
        """Test that adding template updates faction lookup.

        Args:
            sample_template (IconTemplate): Sample template from fixture.
        """
        db = TemplateDatabase(SupportedResolution.R_1080)

        db.add_template(sample_template)

        assert "neutral" in db.faction_lookup
        assert db.faction_lookup["neutral"] == {0}

    def test_add_template_updates_mod_lookup(self, sample_template: IconTemplate) -> None:
        """Test that adding template updates mod lookup.

        Args:
            sample_template (IconTemplate): Sample template from fixture.
        """
        db = TemplateDatabase(SupportedResolution.R_1080)

        db.add_template(sample_template)

        assert "vanilla" in db.mod_lookup
        assert db.mod_lookup["vanilla"] == {0}

    def test_add_template_updates_category_lookup(self, sample_template: IconTemplate) -> None:
        """Test that adding template updates category lookup.

        Args:
            sample_template (IconTemplate): Sample template from fixture.
        """
        db = TemplateDatabase(SupportedResolution.R_1080)

        db.add_template(sample_template)

        assert "item" in db.category_lookup
        assert db.category_lookup["item"] == {0}

    def test_add_multiple_templates_same_faction(self) -> None:
        """Test adding multiple templates with same faction."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        template1 = IconTemplate(
            image=image,
            code="Rifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.COLONIALS,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )
        template2 = IconTemplate(
            image=image,
            code="Tank",
            crated=False,
            category=ItemCategory.Vehicle,
            faction=ItemFaction.COLONIALS,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        db.add_template(template1)
        db.add_template(template2)

        assert db.faction_lookup["Colonials"] == {0, 1}

    def test_add_templates_different_factions(self) -> None:
        """Test adding templates with different factions."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        colonial_template = IconTemplate(
            image=image,
            code="ColonialRifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.COLONIALS,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )
        warden_template = IconTemplate(
            image=image,
            code="WardenRifle",
            crated=False,
            category=ItemCategory.Item,
            faction=ItemFaction.WARDENS,
            mod="vanilla",
            resolution=SupportedResolution.R_1080,
        )

        db.add_template(colonial_template)
        db.add_template(warden_template)

        assert "Colonials" in db.faction_lookup
        assert "Wardens" in db.faction_lookup
        assert db.faction_lookup["Colonials"] == {0}
        assert db.faction_lookup["Wardens"] == {1}


class TestDatabaseUtilities:
    """Test suite for TemplateDatabase utility methods.

    This class contains tests for __len__ and __repr__ methods.
    """

    def test_len_empty_database(self) -> None:
        """Test length of empty database."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        assert len(db) == 0

    def test_len_with_templates(self) -> None:
        """Test length with templates added."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        for i in range(5):
            template = IconTemplate(
                image=image,
                code=f"Item{i}",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            )
            db.add_template(template)

        assert len(db) == 5

    def test_repr(self) -> None:
        """Test string representation of database."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        db.add_template(
            IconTemplate(
                image=image,
                code="Rifle",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.COLONIALS,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )
        db.add_template(
            IconTemplate(
                image=image,
                code="Tank",
                crated=False,
                category=ItemCategory.Vehicle,
                faction=ItemFaction.WARDENS,
                mod="custom",
                resolution=SupportedResolution.R_1080,
            ),
        )

        repr_str = repr(db)

        assert "TemplateDatabase" in repr_str
        assert "resolution=1080" in repr_str
        assert "templates=2" in repr_str
        assert "factions=2" in repr_str
        assert "mods=2" in repr_str
