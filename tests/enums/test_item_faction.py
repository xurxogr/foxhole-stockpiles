"""Tests for enums.item_faction module.

This module contains comprehensive tests for the ItemFaction enum,
including string conversion, CLI validation, and help text generation.
"""

from foxhole_stockpiles.enums.item_faction import ItemFaction


class TestItemFactionEnum:
    """Test suite for ItemFaction enum values.

    This class contains tests for the basic enum functionality
    and value access.
    """

    def test_enum_values(self) -> None:
        """Test that all faction enum values are correctly defined.

        Validates that the enum has the expected faction values.
        """
        assert ItemFaction.NEUTRAL.value == "neutral"
        assert ItemFaction.COLONIALS.value == "Colonials"
        assert ItemFaction.WARDENS.value == "Wardens"

    def test_enum_membership(self) -> None:
        """Test enum membership checks.

        Validates that faction values can be checked for membership.
        """
        assert ItemFaction.NEUTRAL in ItemFaction
        assert ItemFaction.COLONIALS in ItemFaction
        assert ItemFaction.WARDENS in ItemFaction


class TestFromString:
    """Test suite for the from_string class method.

    This class contains tests for converting various string inputs
    to ItemFaction enum values.
    """

    def test_from_string_none(self) -> None:
        """Test from_string with None input.

        Validates that None input returns NEUTRAL faction.
        """
        result = ItemFaction.from_string(None)
        assert result == ItemFaction.NEUTRAL

    def test_from_string_empty(self) -> None:
        """Test from_string with empty string.

        Validates that empty string returns NEUTRAL faction.
        """
        result = ItemFaction.from_string("")
        assert result == ItemFaction.NEUTRAL

    def test_from_string_whitespace(self) -> None:
        """Test from_string with whitespace only.

        Validates that whitespace-only input returns NEUTRAL faction.
        """
        result = ItemFaction.from_string("   ")
        assert result == ItemFaction.NEUTRAL

    def test_from_string_colonials_full(self) -> None:
        """Test from_string with full 'colonials' input.

        Validates that 'colonials' returns COLONIALS faction.
        """
        result = ItemFaction.from_string("colonials")
        assert result == ItemFaction.COLONIALS

    def test_from_string_colonials_uppercase(self) -> None:
        """Test from_string with uppercase 'COLONIALS'.

        Validates case-insensitive conversion for colonials.
        """
        result = ItemFaction.from_string("COLONIALS")
        assert result == ItemFaction.COLONIALS

    def test_from_string_colonials_abbreviation(self) -> None:
        """Test from_string with 'c' abbreviation.

        Validates that single letter 'c' returns COLONIALS.
        """
        result = ItemFaction.from_string("c")
        assert result == ItemFaction.COLONIALS

    def test_from_string_colonial_singular(self) -> None:
        """The singular 'Colonial' (as emitted by fs-sav) returns COLONIALS."""
        assert ItemFaction.from_string("Colonial") == ItemFaction.COLONIALS

    def test_from_string_warden_singular(self) -> None:
        """The singular 'Warden' (as emitted by fs-sav) returns WARDENS."""
        assert ItemFaction.from_string("Warden") == ItemFaction.WARDENS

    def test_from_string_colonials_efactionid(self) -> None:
        """Test from_string with EFactionId format.

        Validates that engine format returns COLONIALS.
        """
        result = ItemFaction.from_string("EFactionId::Colonials")
        assert result == ItemFaction.COLONIALS

    def test_from_string_colonials_with_whitespace(self) -> None:
        """Test from_string with colonials and whitespace.

        Validates that leading/trailing whitespace is handled correctly.
        """
        result = ItemFaction.from_string("  colonials  ")
        assert result == ItemFaction.COLONIALS

    def test_from_string_wardens_full(self) -> None:
        """Test from_string with full 'wardens' input.

        Validates that 'wardens' returns WARDENS faction.
        """
        result = ItemFaction.from_string("wardens")
        assert result == ItemFaction.WARDENS

    def test_from_string_wardens_uppercase(self) -> None:
        """Test from_string with uppercase 'WARDENS'.

        Validates case-insensitive conversion for wardens.
        """
        result = ItemFaction.from_string("WARDENS")
        assert result == ItemFaction.WARDENS

    def test_from_string_wardens_abbreviation(self) -> None:
        """Test from_string with 'w' abbreviation.

        Validates that single letter 'w' returns WARDENS.
        """
        result = ItemFaction.from_string("w")
        assert result == ItemFaction.WARDENS

    def test_from_string_wardens_efactionid(self) -> None:
        """Test from_string with EFactionId format.

        Validates that engine format returns WARDENS.
        """
        result = ItemFaction.from_string("EFactionId::Wardens")
        assert result == ItemFaction.WARDENS

    def test_from_string_wardens_with_whitespace(self) -> None:
        """Test from_string with wardens and whitespace.

        Validates that leading/trailing whitespace is handled correctly.
        """
        result = ItemFaction.from_string("  wardens  ")
        assert result == ItemFaction.WARDENS

    def test_from_string_invalid_input(self) -> None:
        """Test from_string with invalid input.

        Validates that invalid input returns NEUTRAL as default.
        """
        result = ItemFaction.from_string("invalid")
        assert result == ItemFaction.NEUTRAL

    def test_from_string_neutral_explicit(self) -> None:
        """Test from_string with explicit 'neutral' input.

        Validates that 'neutral' string returns NEUTRAL faction.
        """
        result = ItemFaction.from_string("neutral")
        assert result == ItemFaction.NEUTRAL


class TestGetCliHelpText:
    """Test suite for the get_cli_help_text static method.

    This class contains tests for the CLI help text generation.
    """

    def test_get_cli_help_text_returns_string(self) -> None:
        """Test that get_cli_help_text returns a string.

        Validates the return type of the help text method.
        """
        result = ItemFaction.get_cli_help_text()
        assert isinstance(result, str)

    def test_get_cli_help_text_contains_colonials(self) -> None:
        """Test that help text mentions Colonials.

        Validates that the help text includes information about Colonials.
        """
        result = ItemFaction.get_cli_help_text()
        assert "colonials" in result.lower()

    def test_get_cli_help_text_contains_wardens(self) -> None:
        """Test that help text mentions Wardens.

        Validates that the help text includes information about Wardens.
        """
        result = ItemFaction.get_cli_help_text()
        assert "wardens" in result.lower()

    def test_get_cli_help_text_contains_abbreviations(self) -> None:
        """Test that help text mentions abbreviations.

        Validates that the help text includes abbreviation options.
        """
        result = ItemFaction.get_cli_help_text()
        assert "'c'" in result.lower() or "'w'" in result.lower()

    def test_get_cli_help_text_not_empty(self) -> None:
        """Test that help text is not empty.

        Validates that the help text has meaningful content.
        """
        result = ItemFaction.get_cli_help_text()
        assert len(result) > 0
