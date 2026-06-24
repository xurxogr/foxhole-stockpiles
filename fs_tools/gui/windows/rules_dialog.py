"""Dialog for editing the catalog field rule set.

The dropdown picks a preset that seeds the editable rules table; the user can add,
remove, reorder and edit rules. A warning is shown whenever the current rules
would drop a field the app needs (see
:func:`fs_tools.services.catalog_builder.missing_required_paths`). Rule sets can be
imported from / exported to a JSON file.
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from fs_tools.services.catalog_builder import (
    CatalogPreset,
    CatalogRule,
    CatalogRuleSet,
    RuleAction,
    detect_preset,
    load_ruleset,
    missing_required_paths,
    preset_ruleset,
    save_ruleset,
)

logger = logging.getLogger(__name__)

# Sentinel userData for the "Custom" preset entry (no preset matched).
_CUSTOM = "custom"


class RulesDialog(QDialog):
    """Modal editor for a :class:`CatalogRuleSet`."""

    def __init__(self, ruleset: CatalogRuleSet, parent: QWidget | None = None) -> None:
        """Initialize the rules dialog.

        Args:
            ruleset (CatalogRuleSet): The rule set to seed the editor with.
            parent (QWidget | None): Parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.ruleset = ruleset
        self._loading = False
        self.init_ui()
        self._set_rules(list(ruleset.rules))

    def init_ui(self) -> None:
        """Build the dialog UI."""
        self.setMinimumSize(640, 520)
        self.resize(760, 640)
        layout = QVBoxLayout(self)

        # Preset selector.
        preset_layout = QHBoxLayout()
        self.preset_label = QLabel()
        preset_layout.addWidget(self.preset_label)
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("", CatalogPreset.FULL)
        self.preset_combo.addItem("", CatalogPreset.FS)
        self.preset_combo.addItem("", _CUSTOM)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        preset_layout.addWidget(self.preset_combo)
        preset_layout.addStretch()
        layout.addLayout(preset_layout)

        # Rules table: Action (combo) + Pattern (line edit).
        self.table = QTableWidget(0, 2)
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        # Row buttons.
        row_buttons = QHBoxLayout()
        self.add_button = QPushButton()
        self.add_button.clicked.connect(self._add_row)
        self.remove_button = QPushButton()
        self.remove_button.clicked.connect(self._remove_selected)
        self.up_button = QPushButton()
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button = QPushButton()
        self.down_button.clicked.connect(lambda: self._move_selected(1))
        for button in (self.add_button, self.remove_button, self.up_button, self.down_button):
            row_buttons.addWidget(button)
        row_buttons.addStretch()
        layout.addLayout(row_buttons)

        # Warning banner (hidden when the rules keep the required minimum).
        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("color: #FFA500;")
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)

        # Import / Export.
        io_layout = QHBoxLayout()
        self.import_button = QPushButton()
        self.import_button.clicked.connect(self._import)
        self.export_button = QPushButton()
        self.export_button.clicked.connect(self._export)
        io_layout.addWidget(self.import_button)
        io_layout.addWidget(self.export_button)
        io_layout.addStretch()
        layout.addLayout(io_layout)

        # OK / Cancel.
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.retranslate()
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle a language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setWindowTitle(t("rules_dialog.title"))
        self.preset_label.setText(t("rules_dialog.preset_label"))
        self.preset_combo.setItemText(0, t("catalog_builder.variant_full"))
        self.preset_combo.setItemText(1, t("catalog_builder.variant_fs"))
        self.preset_combo.setItemText(2, t("rules_dialog.preset_custom"))
        self.table.setHorizontalHeaderLabels(
            [t("rules_dialog.col_action"), t("rules_dialog.col_pattern")]
        )
        self.add_button.setText(t("rules_dialog.add"))
        self.remove_button.setText(t("rules_dialog.remove"))
        self.up_button.setText(t("rules_dialog.move_up"))
        self.down_button.setText(t("rules_dialog.move_down"))
        self.import_button.setText(t("rules_dialog.import_button"))
        self.export_button.setText(t("rules_dialog.export_button"))
        # Action combos in existing rows.
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            if isinstance(combo, QComboBox):
                combo.setItemText(0, t("rules_dialog.action_include"))
                combo.setItemText(1, t("rules_dialog.action_exclude"))
        self._refresh_warning()

    # ----- table model helpers -----

    def _make_action_combo(self, action: RuleAction) -> QComboBox:
        """Create an action dropdown for a table row.

        Args:
            action (RuleAction): The action to preselect.

        Returns:
            QComboBox: The configured combo box.
        """
        combo = QComboBox()
        combo.addItem(t("rules_dialog.action_include"), RuleAction.INCLUDE)
        combo.addItem(t("rules_dialog.action_exclude"), RuleAction.EXCLUDE)
        combo.setCurrentIndex(0 if action is RuleAction.INCLUDE else 1)
        combo.currentIndexChanged.connect(self._on_rules_changed)
        return combo

    def _set_rules(self, rules: list[CatalogRule]) -> None:
        """Rebuild the table from a list of rules.

        Args:
            rules (list[CatalogRule]): The rules to display.
        """
        self._loading = True
        self.table.setRowCount(0)
        for rule in rules:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setCellWidget(row, 0, self._make_action_combo(rule.action))
            pattern_edit = QLineEdit(rule.pattern)
            pattern_edit.textChanged.connect(self._on_rules_changed)
            self.table.setCellWidget(row, 1, pattern_edit)
        self._loading = False
        self._on_rules_changed()

    def _collect(self) -> list[CatalogRule]:
        """Read the rules from the table (skipping blank patterns).

        Returns:
            list[CatalogRule]: The current rules.
        """
        rules: list[CatalogRule] = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            pattern_edit = self.table.cellWidget(row, 1)
            if not isinstance(combo, QComboBox) or not isinstance(pattern_edit, QLineEdit):
                continue
            pattern = pattern_edit.text().strip()
            if not pattern:
                continue
            rules.append(CatalogRule(action=combo.currentData(), pattern=pattern))
        return rules

    def current_ruleset(self) -> CatalogRuleSet:
        """Build a rule set from the current table contents.

        Returns:
            CatalogRuleSet: The rule set, named after the matching preset if any.
        """
        rules = self._collect()
        preset = detect_preset(CatalogRuleSet(rules=rules))
        return CatalogRuleSet(name=preset.value if preset else None, rules=rules)

    # ----- row actions -----

    def _add_row(self) -> None:
        """Append a new empty include rule and select it."""
        rules = self._collect()
        rules.append(CatalogRule(action=RuleAction.INCLUDE, pattern=""))
        self._set_rules(rules)
        self.table.selectRow(self.table.rowCount() - 1)

    def _remove_selected(self) -> None:
        """Remove the selected rows."""
        selected = {index.row() for index in self.table.selectionModel().selectedRows()}
        if not selected:
            return
        rules = [rule for row, rule in enumerate(self._collect_all()) if row not in selected]
        self._set_rules(rules)

    def _move_selected(self, delta: int) -> None:
        """Move the selected row up or down.

        Args:
            delta (int): -1 to move up, +1 to move down.
        """
        selected = self.table.selectionModel().selectedRows()
        if len(selected) != 1:
            return
        row = selected[0].row()
        target = row + delta
        rules = self._collect_all()
        if not 0 <= target < len(rules):
            return
        rules[row], rules[target] = rules[target], rules[row]
        self._set_rules(rules)
        self.table.selectRow(target)

    def _collect_all(self) -> list[CatalogRule]:
        """Read every table row including blank patterns (for structural edits).

        Returns:
            list[CatalogRule]: All rows as rules.
        """
        rules: list[CatalogRule] = []
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            pattern_edit = self.table.cellWidget(row, 1)
            if not isinstance(combo, QComboBox) or not isinstance(pattern_edit, QLineEdit):
                continue
            rules.append(CatalogRule(action=combo.currentData(), pattern=pattern_edit.text()))
        return rules

    # ----- reactions -----

    def _on_rules_changed(self) -> None:
        """Recompute the warning and reflect the matching preset."""
        if self._loading:
            return
        self._refresh_warning()
        self._sync_preset_combo()

    def _refresh_warning(self) -> None:
        """Show or hide the required-minimum warning."""
        missing = missing_required_paths(CatalogRuleSet(rules=self._collect()))
        if missing:
            self.warning_label.setText(
                t("rules_dialog.warning").replace("{fields}", ", ".join(missing))
            )
            self.warning_label.setVisible(True)
        else:
            self.warning_label.setVisible(False)

    def _sync_preset_combo(self) -> None:
        """Set the preset dropdown to the detected preset or Custom."""
        preset = detect_preset(CatalogRuleSet(rules=self._collect()))
        target = preset if preset is not None else _CUSTOM
        index = self.preset_combo.findData(target)
        if index < 0:
            return
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(index)
        self.preset_combo.blockSignals(False)

    def _on_preset_selected(self, _index: int) -> None:
        """Load a preset's rules when the user picks Full or FS.

        Qt coerces the StrEnum userData to a plain string, so the preset is
        matched by value rather than by ``isinstance``. The "Custom" entry is
        display-only. Picking a preset while the current rules are custom warns
        first, because loading the preset discards those edits.
        """
        data = self.preset_combo.currentData()
        selected = next((preset for preset in CatalogPreset if data == preset), None)
        if selected is None:
            # "Custom" is not an action; restore the dropdown to the true state.
            self._sync_preset_combo()
            return

        if detect_preset(CatalogRuleSet(rules=self._collect())) is None:
            reply = QMessageBox.question(
                self,
                t("rules_dialog.replace_title"),
                t("rules_dialog.replace_message"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._sync_preset_combo()  # revert to Custom; keep the edits
                return

        self._set_rules(list(preset_ruleset(selected).rules))

    # ----- import / export -----

    def _import(self) -> None:
        """Import a rule set from a JSON file."""
        path, _ = QFileDialog.getOpenFileName(
            self, t("rules_dialog.import_title"), "", t("catalog_builder.json_filter")
        )
        if not path:
            return
        try:
            imported = load_ruleset(Path(path))
        except ValueError as e:
            QMessageBox.warning(
                self,
                t("common.validation_error"),
                t("rules_dialog.import_error").replace("{error}", str(e)),
            )
            return
        self._set_rules(list(imported.rules))

    def _export(self) -> None:
        """Export the current rule set to a JSON file."""
        path, _ = QFileDialog.getSaveFileName(
            self, t("rules_dialog.export_title"), "rules.json", t("catalog_builder.json_filter")
        )
        if not path:
            return
        if not path.endswith(".json"):
            path += ".json"
        save_ruleset(Path(path), self.current_ruleset())

    def _accept(self) -> None:
        """Store the current rule set and accept the dialog."""
        self.ruleset = self.current_ruleset()
        self.accept()
