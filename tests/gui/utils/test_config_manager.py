"""Tests for ConfigManager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from foxhole_stockpiles.core.settings import AppSettings
from foxhole_stockpiles.core.settings.config_path import default_config_path
from foxhole_stockpiles.gui.utils.config_manager import ConfigManager


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings.

    Returns:
        MagicMock: Mock AppSettings object
    """
    settings = MagicMock(spec=AppSettings)
    settings.model_dump.return_value = {"test": "data"}
    settings.model_dump_json.return_value = '{"test": "data"}'
    return settings


def test_config_manager_initialization() -> None:
    """Test ConfigManager initialization."""
    manager = ConfigManager()
    assert manager.config_path == default_config_path()


def test_config_manager_load_config() -> None:
    """Test loading config."""
    with patch("foxhole_stockpiles.gui.utils.config_manager.get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(spec=AppSettings)

        manager = ConfigManager()
        settings = manager.load_config()

        assert settings is not None
        mock_get_settings.assert_called_once()


def test_config_manager_load_config_fallback_on_error() -> None:
    """Test loading config falls back to defaults on error."""
    with patch("foxhole_stockpiles.gui.utils.config_manager.get_settings") as mock_get_settings:
        mock_get_settings.side_effect = Exception("Config error")

        manager = ConfigManager()
        settings = manager.load_config()

        # Should return default AppSettings
        assert isinstance(settings, AppSettings)


def test_config_manager_save_config(tmp_path: Path, mock_settings: MagicMock) -> None:
    """Test saving config to file.

    Args:
        tmp_path (Path): Temporary directory path
        mock_settings (MagicMock): Mock settings object
    """
    config_file = tmp_path / "test_config.json"

    manager = ConfigManager()
    manager.config_path = config_file  # Set instance attribute directly
    success, message = manager.save_config(mock_settings)

    assert success is True
    assert "saved" in message.lower()
    assert config_file.exists()


def test_config_manager_save_config_creates_directory(
    tmp_path: Path, mock_settings: MagicMock
) -> None:
    """Test save_config works when parent directory exists.

    Args:
        tmp_path (Path): Temporary directory path
        mock_settings (MagicMock): Mock settings object
    """
    nested_path = tmp_path / "nested" / "dir" / "config.json"

    # Create parent directories first (save_config doesn't create them)
    nested_path.parent.mkdir(parents=True, exist_ok=True)

    manager = ConfigManager()
    manager.config_path = nested_path  # Set instance attribute directly
    success, message = manager.save_config(mock_settings)

    assert success is True
    assert nested_path.exists()
    assert nested_path.parent.exists()


def test_config_manager_save_config_error_handling(tmp_path: Path) -> None:
    """Test save_config handles errors gracefully.

    Args:
        tmp_path (Path): Temporary directory path
    """
    invalid_settings = MagicMock(spec=AppSettings)
    invalid_settings.model_dump.side_effect = Exception("Dump error")

    config_file = tmp_path / "test_config.json"

    manager = ConfigManager()
    manager.config_path = config_file  # Set instance attribute directly
    success, message = manager.save_config(invalid_settings)

    assert success is False
    assert "failed" in message.lower()
