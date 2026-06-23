"""Tests for GUISettings."""

import pytest
from pydantic import ValidationError

from foxhole_stockpiles.core.settings.sections.gui import GUISettings


class TestGUISettings:
    """Test suite for GUISettings."""

    def test_default_values(self) -> None:
        """Test default values are correct."""
        settings = GUISettings()

        assert settings.minimize_to_tray is False
        assert settings.language == "en"

    def test_minimize_to_tray_true(self) -> None:
        """Test minimize to tray enabled."""
        settings = GUISettings(minimize_to_tray=True)

        assert settings.minimize_to_tray is True

    def test_minimize_to_tray_false(self) -> None:
        """Test minimize to tray disabled."""
        settings = GUISettings(minimize_to_tray=False)

        assert settings.minimize_to_tray is False

    def test_full_settings(self) -> None:
        """Test setting all values."""
        settings = GUISettings(
            minimize_to_tray=True,
            language="es",
        )

        assert settings.minimize_to_tray is True
        assert settings.language == "es"

    def test_language_setting(self) -> None:
        """Test setting language."""
        settings = GUISettings(language="de")

        assert settings.language == "de"

    def test_extra_fields_forbidden(self) -> None:
        """Test extra fields are forbidden."""
        with pytest.raises(ValidationError):
            GUISettings(unknown_field="value")  # type: ignore[call-arg]

    def test_json_serialization(self) -> None:
        """Test JSON serialization."""
        settings = GUISettings(
            minimize_to_tray=True,
            language="en",
        )

        json_str = settings.model_dump_json()
        assert "true" in json_str.lower()
        assert '"en"' in json_str

    def test_dict_serialization(self) -> None:
        """Test dict serialization."""
        settings = GUISettings(
            minimize_to_tray=False,
            language="fr",
        )

        data = settings.model_dump()
        assert data["minimize_to_tray"] is False
        assert data["language"] == "fr"

    def test_model_copy(self) -> None:
        """Test model copy with update."""
        settings = GUISettings(language="en")

        updated = settings.model_copy(update={"language": "es"})

        assert settings.language == "en"
        assert updated.language == "es"
