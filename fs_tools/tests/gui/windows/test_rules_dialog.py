"""Tests for RulesDialog."""

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QLineEdit

from fs_tools.gui.windows.rules_dialog import _CUSTOM, RulesDialog
from fs_tools.services.catalog_builder import (
    CatalogPreset,
    CatalogRule,
    CatalogRuleSet,
    RuleAction,
    preset_ruleset,
    save_ruleset,
)


@pytest.fixture
def fs_dialog(qtbot: Any) -> RulesDialog:
    """A dialog seeded with the FS preset.

    Args:
        qtbot: pytest-qt fixture.

    Returns:
        RulesDialog: The dialog under test.
    """
    dialog = RulesDialog(preset_ruleset(CatalogPreset.FS))
    qtbot.addWidget(dialog)
    return dialog


def test_seeds_table_from_ruleset(fs_dialog: RulesDialog) -> None:
    """The table is populated from the seed rule set."""
    assert fs_dialog.table.rowCount() == len(preset_ruleset(CatalogPreset.FS).rules)
    assert fs_dialog.current_ruleset().rules == preset_ruleset(CatalogPreset.FS).rules


def test_add_row(fs_dialog: RulesDialog) -> None:
    """Add appends a row."""
    before = fs_dialog.table.rowCount()
    fs_dialog._add_row()
    assert fs_dialog.table.rowCount() == before + 1


def test_remove_selected(fs_dialog: RulesDialog) -> None:
    """Remove deletes the selected row."""
    before = fs_dialog.table.rowCount()
    fs_dialog.table.selectRow(0)
    fs_dialog._remove_selected()
    assert fs_dialog.table.rowCount() == before - 1


def test_move_row_down_reorders(qtbot: Any) -> None:
    """Moving a row down swaps it with the next."""
    ruleset = CatalogRuleSet(
        rules=[
            CatalogRule(action=RuleAction.INCLUDE, pattern="A"),
            CatalogRule(action=RuleAction.INCLUDE, pattern="B"),
        ]
    )
    dialog = RulesDialog(ruleset)
    qtbot.addWidget(dialog)
    dialog.table.selectRow(0)
    dialog._move_selected(1)
    patterns = [r.pattern for r in dialog.current_ruleset().rules]
    assert patterns == ["B", "A"]


def test_selecting_preset_populates_table(qtbot: Any) -> None:
    """Choosing a preset loads its rules."""
    dialog = RulesDialog(preset_ruleset(CatalogPreset.FULL))
    qtbot.addWidget(dialog)
    fs_index = dialog.preset_combo.findData(CatalogPreset.FS)
    dialog.preset_combo.setCurrentIndex(fs_index)
    assert dialog.current_ruleset().rules == preset_ruleset(CatalogPreset.FS).rules


def test_editing_flips_to_custom(fs_dialog: RulesDialog) -> None:
    """Editing a pattern flips the preset dropdown to Custom."""
    pattern_edit = fs_dialog.table.cellWidget(1, 1)
    assert isinstance(pattern_edit, QLineEdit)
    pattern_edit.setText("SomethingElse")
    assert fs_dialog.preset_combo.currentData() == _CUSTOM


def test_warning_visibility(qtbot: Any) -> None:
    """The warning shows when the required minimum is missing and hides otherwise."""
    missing = CatalogRuleSet(rules=[CatalogRule(action=RuleAction.EXCLUDE, pattern="**")])
    dialog = RulesDialog(missing)
    qtbot.addWidget(dialog)
    # isVisibleTo (not isVisible) reflects setVisible regardless of the unshown dialog.
    assert dialog.warning_label.isVisibleTo(dialog)

    ok = RulesDialog(preset_ruleset(CatalogPreset.FS))
    qtbot.addWidget(ok)
    assert not ok.warning_label.isVisibleTo(ok)


def test_import_export_round_trip(qtbot: Any, tmp_path: Path) -> None:
    """Export then import reproduces the rule set."""
    path = tmp_path / "rules.json"
    save_ruleset(path, preset_ruleset(CatalogPreset.FS))

    dialog = RulesDialog(preset_ruleset(CatalogPreset.FULL))
    qtbot.addWidget(dialog)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "fs_tools.gui.windows.rules_dialog.QFileDialog.getOpenFileName",
            lambda *a, **k: (str(path), ""),
        )
        dialog._import()
    assert dialog.current_ruleset().rules == preset_ruleset(CatalogPreset.FS).rules


def _custom_ruleset() -> CatalogRuleSet:
    """A non-preset (custom) rule set.

    Returns:
        CatalogRuleSet: A rule set matching no preset.
    """
    return CatalogRuleSet(rules=[CatalogRule(action=RuleAction.INCLUDE, pattern="CodeName")])


def test_switch_from_custom_confirms_and_loads_when_accepted(qtbot: Any) -> None:
    """Picking a preset from Custom warns, then loads it when confirmed."""
    from PySide6.QtWidgets import QMessageBox

    dialog = RulesDialog(_custom_ruleset())
    qtbot.addWidget(dialog)
    assert dialog.preset_combo.currentData() == _CUSTOM  # starts custom

    fs_index = dialog.preset_combo.findData(CatalogPreset.FS)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "fs_tools.gui.windows.rules_dialog.QMessageBox.question",
            lambda *a, **k: QMessageBox.StandardButton.Yes,
        )
        dialog.preset_combo.setCurrentIndex(fs_index)
    assert dialog.current_ruleset().rules == preset_ruleset(CatalogPreset.FS).rules


def test_switch_from_custom_keeps_rules_when_declined(qtbot: Any) -> None:
    """Declining the warning keeps the custom rules and reverts to Custom."""
    from PySide6.QtWidgets import QMessageBox

    dialog = RulesDialog(_custom_ruleset())
    qtbot.addWidget(dialog)

    fs_index = dialog.preset_combo.findData(CatalogPreset.FS)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "fs_tools.gui.windows.rules_dialog.QMessageBox.question",
            lambda *a, **k: QMessageBox.StandardButton.No,
        )
        dialog.preset_combo.setCurrentIndex(fs_index)
    assert dialog.current_ruleset().rules == _custom_ruleset().rules
    assert dialog.preset_combo.currentData() == _CUSTOM


def test_switch_between_presets_does_not_warn(qtbot: Any) -> None:
    """Switching FS -> FULL needs no warning (no custom edits to lose)."""
    from PySide6.QtWidgets import QMessageBox

    dialog = RulesDialog(preset_ruleset(CatalogPreset.FS))
    qtbot.addWidget(dialog)

    full_index = dialog.preset_combo.findData(CatalogPreset.FULL)
    with pytest.MonkeyPatch.context() as mp:
        called = {"n": 0}

        def _question(*_a: Any, **_k: Any) -> Any:
            called["n"] += 1
            return QMessageBox.StandardButton.Yes

        mp.setattr("fs_tools.gui.windows.rules_dialog.QMessageBox.question", _question)
        dialog.preset_combo.setCurrentIndex(full_index)
        assert called["n"] == 0
    assert dialog.current_ruleset().rules == []


def test_accept_stores_ruleset(fs_dialog: RulesDialog) -> None:
    """Accepting stores the current rule set on the dialog."""
    fs_dialog._accept()
    assert fs_dialog.ruleset.rules == preset_ruleset(CatalogPreset.FS).rules
