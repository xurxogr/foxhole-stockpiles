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
from foxhole_stockpiles.models.icon_template import IconTemplate
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


class TestGetCandidates:
    """Test suite for TemplateDatabase.get_candidates method.

    This class contains tests for candidate filtering functionality.
    """

    @pytest.fixture
    def populated_db(self) -> TemplateDatabase:
        """Create a database populated with various templates.

        Returns:
            TemplateDatabase: Database with multiple templates.
        """
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)

        # Add neutral item
        db.add_template(
            IconTemplate(
                image=image,
                code="BasicRifle",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )

        # Add colonial item
        db.add_template(
            IconTemplate(
                image=image,
                code="ColonialRifle",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.COLONIALS,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )

        # Add warden vehicle
        db.add_template(
            IconTemplate(
                image=image,
                code="WardenTank",
                crated=False,
                category=ItemCategory.Vehicle,
                faction=ItemFaction.WARDENS,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )

        # Add crated item
        db.add_template(
            IconTemplate(
                image=image,
                code="CratedSupplies",
                crated=True,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )

        # Add mod item
        db.add_template(
            IconTemplate(
                image=image,
                code="ModItem",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="custom_mod",
                resolution=SupportedResolution.R_1080,
            ),
        )

        return db

    def test_get_candidates_no_filters(self, populated_db: TemplateDatabase) -> None:
        """Test getting candidates with no filters returns all.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates()

        assert len(candidates) == 5
        assert set(candidates) == {0, 1, 2, 3, 4}

    def test_get_candidates_faction_filter(self, populated_db: TemplateDatabase) -> None:
        """Test filtering by faction.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(faction=ItemFaction.COLONIALS)

        # Should include colonial items + neutral items
        assert 0 in candidates  # Neutral item
        assert 1 in candidates  # Colonial item
        assert 3 in candidates  # Neutral crated item
        assert 4 in candidates  # Neutral mod item
        assert 2 not in candidates  # Warden vehicle

    def test_get_candidates_faction_wardens(self, populated_db: TemplateDatabase) -> None:
        """Test filtering by Warden faction.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(faction=ItemFaction.WARDENS)

        # Should include warden items + neutral items
        assert 0 in candidates  # Neutral item
        assert 2 in candidates  # Warden vehicle
        assert 3 in candidates  # Neutral crated item
        assert 4 in candidates  # Neutral mod item
        assert 1 not in candidates  # Colonial item

    def test_get_candidates_category_filter(self, populated_db: TemplateDatabase) -> None:
        """Test filtering by category.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(category=ItemCategory.Item)

        # Should only include items, not vehicles
        assert 0 in candidates  # Neutral item
        assert 1 in candidates  # Colonial item
        assert 3 in candidates  # Crated item
        assert 4 in candidates  # Mod item
        assert 2 not in candidates  # Vehicle

    def test_get_candidates_mod_filter(self, populated_db: TemplateDatabase) -> None:
        """Test filtering by mod.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(mod="vanilla")

        # Should only include vanilla items
        assert 0 in candidates
        assert 1 in candidates
        assert 2 in candidates
        assert 3 in candidates
        assert 4 not in candidates  # Custom mod item

    def test_get_candidates_crated_filter_true(self, populated_db: TemplateDatabase) -> None:
        """Test filtering for crated items only.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(crated=True)

        # Should only include crated items
        assert candidates == [3]

    def test_get_candidates_crated_filter_false(self, populated_db: TemplateDatabase) -> None:
        """Test filtering for non-crated items only.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(crated=False)

        # Should only include non-crated items
        assert 0 in candidates
        assert 1 in candidates
        assert 2 in candidates
        assert 4 in candidates
        assert 3 not in candidates  # Crated item

    def test_get_candidates_code_filter(self, populated_db: TemplateDatabase) -> None:
        """Test filtering by item code.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(code="Rifle")

        # Should only include items with "Rifle" in code
        assert 0 in candidates  # BasicRifle
        assert 1 in candidates  # ColonialRifle
        assert 2 not in candidates  # WardenTank
        assert 3 not in candidates  # CratedSupplies
        assert 4 not in candidates  # ModItem

    def test_get_candidates_combined_filters(self, populated_db: TemplateDatabase) -> None:
        """Test using multiple filters together.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(
            faction=ItemFaction.COLONIALS,
            category=ItemCategory.Item,
            crated=False,
        )

        # Should include colonial items + neutral items, category=item, not crated
        assert 0 in candidates  # Neutral item
        assert 1 in candidates  # Colonial item
        assert 4 in candidates  # Neutral mod item
        assert 2 not in candidates  # Warden vehicle
        assert 3 not in candidates  # Crated item

    def test_get_candidates_invalid_category_ignored(
        self,
        populated_db: TemplateDatabase,
    ) -> None:
        """Test that Invalid category filter is ignored.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(category=ItemCategory.Invalid)

        # Invalid category should be treated as no filter
        assert len(candidates) == 5

    def test_get_candidates_exclude_single_code(self, populated_db: TemplateDatabase) -> None:
        """Test excluding a single item code.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(excluded_codes=["BasicRifle"])

        # Should exclude BasicRifle (index 0)
        assert 0 not in candidates
        assert 1 in candidates  # ColonialRifle
        assert 2 in candidates  # WardenTank
        assert 3 in candidates  # CratedSupplies
        assert 4 in candidates  # ModItem
        assert len(candidates) == 4

    def test_get_candidates_exclude_multiple_codes(self, populated_db: TemplateDatabase) -> None:
        """Test excluding multiple item codes.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(excluded_codes=["BasicRifle", "WardenTank"])

        # Should exclude BasicRifle (index 0) and WardenTank (index 2)
        assert 0 not in candidates
        assert 1 in candidates  # ColonialRifle
        assert 2 not in candidates
        assert 3 in candidates  # CratedSupplies
        assert 4 in candidates  # ModItem
        assert len(candidates) == 3

    def test_get_candidates_exclude_with_other_filters(
        self, populated_db: TemplateDatabase
    ) -> None:
        """Test excluded_codes combined with other filters.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(
            faction=ItemFaction.COLONIALS, excluded_codes=["BasicRifle"]
        )

        # Should include colonial items + neutral items, but exclude BasicRifle
        assert 0 not in candidates  # BasicRifle (excluded)
        assert 1 in candidates  # ColonialRifle
        assert 3 in candidates  # CratedSupplies (neutral)
        assert 4 in candidates  # ModItem (neutral)
        assert 2 not in candidates  # WardenTank (filtered by faction)

    def test_get_candidates_exclude_nonexistent_code(self, populated_db: TemplateDatabase) -> None:
        """Test excluding a code that doesn't exist.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(excluded_codes=["NonexistentItem"])

        # Should return all items (nonexistent code doesn't affect anything)
        assert len(candidates) == 5

    def test_get_candidates_exclude_all_codes(self, populated_db: TemplateDatabase) -> None:
        """Test excluding all item codes.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        all_codes = [
            "BasicRifle",
            "ColonialRifle",
            "WardenTank",
            "CratedSupplies",
            "ModItem",
        ]
        candidates = populated_db.get_candidates(excluded_codes=all_codes)

        # Should return no candidates
        assert len(candidates) == 0
        assert candidates == []

    def test_get_candidates_exclude_empty_list(self, populated_db: TemplateDatabase) -> None:
        """Test with empty excluded_codes list.

        Args:
            populated_db (TemplateDatabase): Populated database from fixture.
        """
        candidates = populated_db.get_candidates(excluded_codes=[])

        # Should return all items (empty list means no exclusions)
        assert len(candidates) == 5


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


class TestGetAvailableMods:
    """Test suite for get_available_mods method."""

    def test_get_available_mods_empty_database(self) -> None:
        """Test getting mods from empty database returns empty set."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        mods = db.get_available_mods()

        assert mods == set()

    def test_get_available_mods_single_mod(self) -> None:
        """Test getting mods with single mod in database."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        db.add_template(
            IconTemplate(
                image=image,
                code="Item",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )

        mods = db.get_available_mods()

        assert mods == {"vanilla"}

    def test_get_available_mods_multiple_mods(self) -> None:
        """Test getting mods with multiple mods in database."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        db.add_template(
            IconTemplate(
                image=image,
                code="VanillaItem",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )
        db.add_template(
            IconTemplate(
                image=image,
                code="ModItem",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="custom_mod",
                resolution=SupportedResolution.R_1080,
            ),
        )
        db.add_template(
            IconTemplate(
                image=image,
                code="AnotherItem",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="airborne",
                resolution=SupportedResolution.R_1080,
            ),
        )

        mods = db.get_available_mods()

        assert mods == {"vanilla", "custom_mod", "airborne"}


class TestEdgeCases:
    """Test suite for edge cases and boundary conditions.

    This class contains tests for unusual or edge case scenarios.
    """

    def test_empty_database_get_candidates(self) -> None:
        """Test getting candidates from empty database."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        candidates = db.get_candidates()

        assert candidates == []

    def test_neutral_faction_filter(self) -> None:
        """Test filtering with NEUTRAL faction."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        db.add_template(
            IconTemplate(
                image=image,
                code="NeutralItem",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )
        db.add_template(
            IconTemplate(
                image=image,
                code="ColonialItem",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.COLONIALS,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )

        # NEUTRAL faction filter should not be applied (returns all)
        candidates = db.get_candidates(faction=ItemFaction.NEUTRAL)

        assert len(candidates) == 2

    def test_nonexistent_mod_filter(self) -> None:
        """Test filtering with non-existent mod."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        db.add_template(
            IconTemplate(
                image=image,
                code="Item",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )

        candidates = db.get_candidates(mod="nonexistent")

        assert candidates == []

    def test_nonexistent_code_filter(self) -> None:
        """Test filtering with non-existent code."""
        db = TemplateDatabase(SupportedResolution.R_1080)

        image = np.zeros((64, 64, 3), dtype=np.uint8)
        db.add_template(
            IconTemplate(
                image=image,
                code="Rifle",
                crated=False,
                category=ItemCategory.Item,
                faction=ItemFaction.NEUTRAL,
                mod="vanilla",
                resolution=SupportedResolution.R_1080,
            ),
        )

        candidates = db.get_candidates(code="Tank")

        assert candidates == []
