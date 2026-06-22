"""Tests for ExternalToolsTab."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from foxhole_stockpiles.core.settings.sections.external_tools import ExternalToolsSettings
from fs_tools.gui.widgets.config_tabs.external_tools_tab import ExternalToolsTab


@pytest.fixture
def external_tools_tab(qtbot: Any) -> ExternalToolsTab:
    """Create an ExternalToolsTab instance with all tools visible.

    Args:
        qtbot: PyQt test fixture

    Returns:
        ExternalToolsTab: Tab instance
    """
    tab = ExternalToolsTab()
    qtbot.addWidget(tab)
    return tab


@pytest.fixture
def repak_only_tab(qtbot: Any) -> ExternalToolsTab:
    """Create an ExternalToolsTab with only repak visible.

    Args:
        qtbot: PyQt test fixture

    Returns:
        ExternalToolsTab: Tab instance
    """
    tab = ExternalToolsTab(show_repak=True, show_umodel=False, show_uassetgui=False)
    qtbot.addWidget(tab)
    return tab


@pytest.fixture
def umodel_only_tab(qtbot: Any) -> ExternalToolsTab:
    """Create an ExternalToolsTab with only umodel visible.

    Args:
        qtbot: PyQt test fixture

    Returns:
        ExternalToolsTab: Tab instance
    """
    tab = ExternalToolsTab(show_repak=False, show_umodel=True, show_uassetgui=False)
    qtbot.addWidget(tab)
    return tab


# ===== Initialization Tests =====


def test_external_tools_tab_initialization(external_tools_tab: ExternalToolsTab) -> None:
    """Test ExternalToolsTab initialization with all tools.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None
    assert external_tools_tab.repak_download_btn is not None
    assert external_tools_tab.umodel_download_btn is not None
    assert external_tools_tab.uassetgui_download_btn is not None


def test_external_tools_tab_repak_only(repak_only_tab: ExternalToolsTab) -> None:
    """Test ExternalToolsTab with only repak visible.

    Args:
        repak_only_tab: ExternalToolsTab instance
    """
    assert repak_only_tab.repak_input is not None
    assert repak_only_tab.umodel_input is None
    assert repak_only_tab.uassetgui_input is None
    assert repak_only_tab.repak_download_btn is not None
    assert repak_only_tab.umodel_download_btn is None
    assert repak_only_tab.uassetgui_download_btn is None


def test_external_tools_tab_umodel_only(umodel_only_tab: ExternalToolsTab) -> None:
    """Test ExternalToolsTab with only umodel visible.

    Args:
        umodel_only_tab: ExternalToolsTab instance
    """
    assert umodel_only_tab.repak_input is None
    assert umodel_only_tab.umodel_input is not None
    assert umodel_only_tab.uassetgui_input is None


def test_external_tools_tab_catalog_builder_config(qtbot: Any) -> None:
    """Test ExternalToolsTab configured for catalog builder (repak + uassetgui).

    Args:
        qtbot: PyQt test fixture
    """
    tab = ExternalToolsTab(show_repak=True, show_umodel=False, show_uassetgui=True)
    qtbot.addWidget(tab)

    assert tab.repak_input is not None
    assert tab.umodel_input is None
    assert tab.uassetgui_input is not None


def test_external_tools_tab_database_builder_config(qtbot: Any) -> None:
    """Test ExternalToolsTab configured for database builder (repak + umodel).

    Args:
        qtbot: PyQt test fixture
    """
    tab = ExternalToolsTab(show_repak=True, show_umodel=True, show_uassetgui=False)
    qtbot.addWidget(tab)

    assert tab.repak_input is not None
    assert tab.umodel_input is not None
    assert tab.uassetgui_input is None


# ===== Set Values Tests =====


def test_set_values_all_tools(external_tools_tab: ExternalToolsTab) -> None:
    """Test setting values for all tools.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None

    settings = ExternalToolsSettings(
        repak=Path("/path/to/repak.exe"),
        umodel=Path("/path/to/umodel.exe"),
        uassetgui=Path("/path/to/uassetgui.exe"),
    )

    external_tools_tab.set_values(settings)

    assert external_tools_tab.repak_input.text() == "/path/to/repak.exe"
    assert external_tools_tab.umodel_input.text() == "/path/to/umodel.exe"
    assert external_tools_tab.uassetgui_input.text() == "/path/to/uassetgui.exe"


def test_set_values_none_values(external_tools_tab: ExternalToolsTab) -> None:
    """Test setting None values clears the inputs.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None

    # First set some values
    external_tools_tab.repak_input.setText("some/path")
    external_tools_tab.umodel_input.setText("some/other/path")

    # Then set None values
    settings = ExternalToolsSettings(
        repak=None,
        umodel=None,
        uassetgui=None,
    )

    external_tools_tab.set_values(settings)

    assert external_tools_tab.repak_input.text() == ""
    assert external_tools_tab.umodel_input.text() == ""
    assert external_tools_tab.uassetgui_input.text() == ""


def test_set_values_partial(repak_only_tab: ExternalToolsTab) -> None:
    """Test setting values when only some tools are visible.

    Args:
        repak_only_tab: ExternalToolsTab instance
    """
    assert repak_only_tab.repak_input is not None

    settings = ExternalToolsSettings(
        repak=Path("/path/to/repak.exe"),
        umodel=Path("/path/to/umodel.exe"),  # This tool is not shown
    )

    repak_only_tab.set_values(settings)

    assert repak_only_tab.repak_input.text() == "/path/to/repak.exe"
    # umodel_input is None since it's not shown
    assert repak_only_tab.umodel_input is None


# ===== Get Values Tests =====


def test_get_values_all_tools(external_tools_tab: ExternalToolsTab) -> None:
    """Test getting values for all tools.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None

    external_tools_tab.repak_input.setText("/path/to/repak.exe")
    external_tools_tab.umodel_input.setText("/path/to/umodel.exe")
    external_tools_tab.uassetgui_input.setText("/path/to/uassetgui.exe")

    settings = external_tools_tab.get_values()

    assert settings.repak == Path("/path/to/repak.exe")
    assert settings.umodel == Path("/path/to/umodel.exe")
    assert settings.uassetgui == Path("/path/to/uassetgui.exe")


def test_get_values_empty_fields(external_tools_tab: ExternalToolsTab) -> None:
    """Test getting values when fields are empty.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None

    external_tools_tab.repak_input.setText("")
    external_tools_tab.umodel_input.setText("")
    external_tools_tab.uassetgui_input.setText("")

    settings = external_tools_tab.get_values()

    assert settings.repak is None
    assert settings.umodel is None
    assert settings.uassetgui is None


def test_get_values_whitespace_only(external_tools_tab: ExternalToolsTab) -> None:
    """Test getting values when fields have only whitespace.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None

    external_tools_tab.repak_input.setText("   ")
    external_tools_tab.umodel_input.setText("\t")
    external_tools_tab.uassetgui_input.setText("  \n  ")

    settings = external_tools_tab.get_values()

    assert settings.repak is None
    assert settings.umodel is None
    assert settings.uassetgui is None


def test_get_values_partial(repak_only_tab: ExternalToolsTab) -> None:
    """Test getting values when only some tools are visible.

    Args:
        repak_only_tab: ExternalToolsTab instance
    """
    assert repak_only_tab.repak_input is not None

    repak_only_tab.repak_input.setText("/path/to/repak.exe")

    settings = repak_only_tab.get_values()

    assert settings.repak == Path("/path/to/repak.exe")
    assert settings.umodel is None
    assert settings.uassetgui is None


# ===== Roundtrip Tests =====


def test_roundtrip_all_tools(external_tools_tab: ExternalToolsTab) -> None:
    """Test set_values and get_values roundtrip.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    original_settings = ExternalToolsSettings(
        repak=Path("/tools/repak.exe"),
        umodel=Path("/tools/umodel.exe"),
        uassetgui=Path("/tools/uassetgui.exe"),
    )

    external_tools_tab.set_values(original_settings)
    retrieved_settings = external_tools_tab.get_values()

    assert retrieved_settings.repak == original_settings.repak
    assert retrieved_settings.umodel == original_settings.umodel
    assert retrieved_settings.uassetgui == original_settings.uassetgui


# ===== Merge With Existing Tests =====


def test_merge_with_existing_all_tools(external_tools_tab: ExternalToolsTab) -> None:
    """Test merge_with_existing updates all tools.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None

    existing = ExternalToolsSettings(
        repak=Path("/old/repak.exe"),
        umodel=Path("/old/umodel.exe"),
        uassetgui=Path("/old/uassetgui.exe"),
    )

    external_tools_tab.repak_input.setText("/new/repak.exe")
    external_tools_tab.umodel_input.setText("/new/umodel.exe")
    external_tools_tab.uassetgui_input.setText("/new/uassetgui.exe")

    merged = external_tools_tab.merge_with_existing(existing)

    assert merged.repak == Path("/new/repak.exe")
    assert merged.umodel == Path("/new/umodel.exe")
    assert merged.uassetgui == Path("/new/uassetgui.exe")


def test_merge_with_existing_preserves_hidden_tools(
    repak_only_tab: ExternalToolsTab,
) -> None:
    """Test merge_with_existing preserves values for hidden tools.

    Args:
        repak_only_tab: ExternalToolsTab instance
    """
    assert repak_only_tab.repak_input is not None

    existing = ExternalToolsSettings(
        repak=Path("/old/repak.exe"),
        umodel=Path("/old/umodel.exe"),
        uassetgui=Path("/old/uassetgui.exe"),
    )

    repak_only_tab.repak_input.setText("/new/repak.exe")

    merged = repak_only_tab.merge_with_existing(existing)

    # Repak should be updated
    assert merged.repak == Path("/new/repak.exe")
    # Hidden tools should be preserved
    assert merged.umodel == Path("/old/umodel.exe")
    assert merged.uassetgui == Path("/old/uassetgui.exe")


def test_merge_with_existing_catalog_builder_config(qtbot: Any) -> None:
    """Test merge for catalog builder (repak + uassetgui, preserves umodel).

    Args:
        qtbot: PyQt test fixture
    """
    tab = ExternalToolsTab(show_repak=True, show_umodel=False, show_uassetgui=True)
    qtbot.addWidget(tab)

    assert tab.repak_input is not None
    assert tab.uassetgui_input is not None

    existing = ExternalToolsSettings(
        repak=Path("/old/repak.exe"),
        umodel=Path("/existing/umodel.exe"),  # Should be preserved
        uassetgui=Path("/old/uassetgui.exe"),
    )

    tab.repak_input.setText("/new/repak.exe")
    tab.uassetgui_input.setText("/new/uassetgui.exe")

    merged = tab.merge_with_existing(existing)

    assert merged.repak == Path("/new/repak.exe")
    assert merged.umodel == Path("/existing/umodel.exe")  # Preserved
    assert merged.uassetgui == Path("/new/uassetgui.exe")


# ===== Browse Tests =====


def test_browse_repak(qtbot: Any, external_tools_tab: ExternalToolsTab) -> None:
    """Test browse repak button.

    Args:
        qtbot: PyQt test fixture
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None

    test_path = "/selected/repak.exe"

    with patch(
        "fs_tools.gui.widgets.config_tabs.external_tools_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_path, "All Files (*)")

        external_tools_tab._browse_repak()

        assert external_tools_tab.repak_input.text() == test_path


def test_browse_repak_cancelled(qtbot: Any, external_tools_tab: ExternalToolsTab) -> None:
    """Test browse repak when cancelled.

    Args:
        qtbot: PyQt test fixture
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None

    external_tools_tab.repak_input.setText("original/path")

    with patch(
        "fs_tools.gui.widgets.config_tabs.external_tools_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("", "")

        external_tools_tab._browse_repak()

        assert external_tools_tab.repak_input.text() == "original/path"


def test_browse_umodel(qtbot: Any, external_tools_tab: ExternalToolsTab) -> None:
    """Test browse umodel button.

    Args:
        qtbot: PyQt test fixture
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.umodel_input is not None

    test_path = "/selected/umodel.exe"

    with patch(
        "fs_tools.gui.widgets.config_tabs.external_tools_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_path, "All Files (*)")

        external_tools_tab._browse_umodel()

        assert external_tools_tab.umodel_input.text() == test_path


def test_browse_umodel_cancelled(qtbot: Any, external_tools_tab: ExternalToolsTab) -> None:
    """Test browse umodel when cancelled.

    Args:
        qtbot: PyQt test fixture
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.umodel_input is not None

    external_tools_tab.umodel_input.setText("original/path")

    with patch(
        "fs_tools.gui.widgets.config_tabs.external_tools_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("", "")

        external_tools_tab._browse_umodel()

        assert external_tools_tab.umodel_input.text() == "original/path"


def test_browse_uassetgui(qtbot: Any, external_tools_tab: ExternalToolsTab) -> None:
    """Test browse UAssetGUI button.

    Args:
        qtbot: PyQt test fixture
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.uassetgui_input is not None

    test_path = "/selected/uassetgui.exe"

    with patch(
        "fs_tools.gui.widgets.config_tabs.external_tools_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = (test_path, "All Files (*)")

        external_tools_tab._browse_uassetgui()

        assert external_tools_tab.uassetgui_input.text() == test_path


def test_browse_uassetgui_cancelled(qtbot: Any, external_tools_tab: ExternalToolsTab) -> None:
    """Test browse UAssetGUI when cancelled.

    Args:
        qtbot: PyQt test fixture
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.uassetgui_input is not None

    external_tools_tab.uassetgui_input.setText("original/path")

    with patch(
        "fs_tools.gui.widgets.config_tabs.external_tools_tab.QFileDialog.getOpenFileName"
    ) as mock_dialog:
        mock_dialog.return_value = ("", "")

        external_tools_tab._browse_uassetgui()

        assert external_tools_tab.uassetgui_input.text() == "original/path"


# ===== Download Button Tests =====


def test_download_button_visibility_empty(
    external_tools_tab: ExternalToolsTab,
) -> None:
    """Test download buttons are not hidden when fields are empty.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None
    assert external_tools_tab.repak_download_btn is not None
    assert external_tools_tab.umodel_download_btn is not None
    assert external_tools_tab.uassetgui_download_btn is not None

    external_tools_tab.repak_input.setText("")
    external_tools_tab.umodel_input.setText("")
    external_tools_tab.uassetgui_input.setText("")
    external_tools_tab._update_download_buttons()

    # Use isHidden() since isVisible() requires parent to be shown
    assert not external_tools_tab.repak_download_btn.isHidden()
    assert not external_tools_tab.umodel_download_btn.isHidden()
    assert not external_tools_tab.uassetgui_download_btn.isHidden()


def test_download_button_visibility_filled(
    external_tools_tab: ExternalToolsTab,
) -> None:
    """Test download buttons are hidden when fields have values.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None
    assert external_tools_tab.repak_download_btn is not None
    assert external_tools_tab.umodel_download_btn is not None
    assert external_tools_tab.uassetgui_download_btn is not None

    external_tools_tab.repak_input.setText("/path/to/repak")
    external_tools_tab.umodel_input.setText("/path/to/umodel")
    external_tools_tab.uassetgui_input.setText("/path/to/uassetgui")
    external_tools_tab._update_download_buttons()

    assert external_tools_tab.repak_download_btn.isHidden()
    assert external_tools_tab.umodel_download_btn.isHidden()
    assert external_tools_tab.uassetgui_download_btn.isHidden()


def test_download_button_visibility_partial(
    external_tools_tab: ExternalToolsTab,
) -> None:
    """Test download button visibility is independent per field.

    Args:
        external_tools_tab: ExternalToolsTab instance
    """
    assert external_tools_tab.repak_input is not None
    assert external_tools_tab.umodel_input is not None
    assert external_tools_tab.uassetgui_input is not None
    assert external_tools_tab.repak_download_btn is not None
    assert external_tools_tab.umodel_download_btn is not None
    assert external_tools_tab.uassetgui_download_btn is not None

    external_tools_tab.repak_input.setText("/path/to/repak")
    external_tools_tab.umodel_input.setText("")
    external_tools_tab.uassetgui_input.setText("/path/to/uassetgui")
    external_tools_tab._update_download_buttons()

    # Use isHidden() since isVisible() requires parent to be shown
    assert external_tools_tab.repak_download_btn.isHidden()
    assert not external_tools_tab.umodel_download_btn.isHidden()
    assert external_tools_tab.uassetgui_download_btn.isHidden()


def test_open_url(qtbot: Any, external_tools_tab: ExternalToolsTab) -> None:
    """Test opening URL in default browser.

    Args:
        qtbot: PyQt test fixture
        external_tools_tab: ExternalToolsTab instance
    """
    with patch(
        "fs_tools.gui.widgets.config_tabs.external_tools_tab.QDesktopServices.openUrl"
    ) as mock_open:
        external_tools_tab._open_url("https://example.com")

        mock_open.assert_called_once()
        url_arg = mock_open.call_args[0][0]
        assert url_arg.toString() == "https://example.com"


# ===== Tool URLs Tests =====


def test_tool_urls_defined() -> None:
    """Test that all tool URLs are defined."""
    assert "repak" in ExternalToolsTab.TOOL_URLS
    assert "umodel" in ExternalToolsTab.TOOL_URLS
    assert "uassetgui" in ExternalToolsTab.TOOL_URLS
