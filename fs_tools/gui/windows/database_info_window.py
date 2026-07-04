"""Database information window."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from foxhole_stockpiles.i18n import off_language_changed, on_language_changed, t
from fs_tools.template_db.template_manager import TemplateManager

logger = logging.getLogger(__name__)


class DatabaseInfoWindow(QDialog):
    """Window for displaying database statistics."""

    def __init__(self, parent: QWidget | None = None, initial_db_path: str | None = None) -> None:
        """Initialize the database info window.

        Args:
            parent (QWidget | None): Parent widget. Defaults to None.
            initial_db_path (str | None): Initial database path to load. Defaults to None.
        """
        super().__init__(parent)
        self.init_ui()

        # Load initial database if provided
        if initial_db_path:
            self.db_path_input.setText(initial_db_path)
            self.load_statistics()

    def init_ui(self) -> None:
        """Initialize the user interface."""
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout(self)

        # Database selection section
        self.selection_group = QGroupBox()
        selection_layout = QHBoxLayout()
        self.selection_group.setLayout(selection_layout)

        self.db_path_input = QLineEdit()
        self.db_path_input.setReadOnly(True)
        selection_layout.addWidget(self.db_path_input)

        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self.browse_database)
        selection_layout.addWidget(self.browse_button)

        layout.addWidget(self.selection_group)

        # Statistics table section
        self.stats_group = QGroupBox()
        stats_layout = QVBoxLayout()
        self.stats_group.setLayout(stats_layout)

        # Info text explaining the numbers
        self.info_text = QLabel()
        self.info_text.setStyleSheet("QLabel { color: gray; font-size: 11px; font-style: italic; }")
        self.info_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stats_layout.addWidget(self.info_text)

        self.stats_table = QTableWidget()
        self.stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stats_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        vertical_header = self.stats_table.verticalHeader()
        if vertical_header:
            vertical_header.setVisible(False)

        stats_layout.addWidget(self.stats_table)

        layout.addWidget(self.stats_group)

        # Apply translations
        self.retranslate()

        # Show initial message
        self._show_message(
            t("database_info_window.no_database"), t("database_info_window.click_browse")
        )

        # Connect to language change signal with cleanup
        self._language_callback = self._on_language_changed
        on_language_changed(self._language_callback)
        self.destroyed.connect(lambda cb=self._language_callback: off_language_changed(cb))

    def _on_language_changed(self, _language: str) -> None:
        """Handle language change event."""
        self.retranslate()

    def retranslate(self) -> None:
        """Update all translatable strings."""
        self.setWindowTitle(t("database_info_window.title"))
        self.selection_group.setTitle(t("database_info_window.database_file"))
        self.db_path_input.setPlaceholderText(t("database_info_window.select_placeholder"))
        self.browse_button.setText(t("common.browse"))
        self.stats_group.setTitle(t("database_info_window.statistics_group"))
        self.info_text.setText(t("database_info_window.statistics_info"))

    def browse_database(self) -> None:
        """Open file dialog to select a database file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            t("database_info_window.select_database"),
            "",
            t("database_info_window.database_filter"),
        )
        if filepath:
            self.db_path_input.setText(filepath)
            # Automatically load statistics after selection
            self.load_statistics()

    def load_statistics(self) -> None:
        """Load and display statistics for the selected database."""
        db_path = self.db_path_input.text()
        if not db_path:
            self._show_message(
                t("database_info_window.no_file_selected"), t("database_info_window.select_first")
            )
            return

        db_path_obj = Path(db_path)
        if not db_path_obj.exists():
            self._show_message(
                t("database_info_window.file_not_found"),
                t("database_info_window.file_not_exist").replace("{path}", db_path),
            )
            return

        try:
            manager = TemplateManager(database_path=db_path_obj)
            stats = manager.get_database_statistics()

            # Set up table: Mod column + resolution columns
            num_cols = 1 + len(stats.resolutions)
            self.stats_table.setColumnCount(num_cols)

            # Set headers
            headers = [t("database_info_window.mod_column")] + [
                f"{res}p" for res in stats.resolutions
            ]
            self.stats_table.setHorizontalHeaderLabels(headers)

            # Add rows for each mod
            sorted_mods = sorted(stats.mod_stats.keys())
            self.stats_table.setRowCount(len(sorted_mods))

            for row, mod in enumerate(sorted_mods):
                # Mod name
                mod_item = QTableWidgetItem(mod)
                self.stats_table.setItem(row, 0, mod_item)

                # Template counts for each resolution
                for col, res in enumerate(stats.resolutions, start=1):
                    count = stats.mod_stats[mod].get(res, 0)
                    count_item = QTableWidgetItem(str(count))
                    count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.stats_table.setItem(row, col, count_item)

            # Resize columns
            header = self.stats_table.horizontalHeader()
            if header:
                header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
                for col in range(1, num_cols):
                    header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

            logger.info(f"Loaded statistics for database: {db_path}")

        except Exception as e:  # noqa: BLE001 - surface any load failure to the user
            logger.error(f"Failed to load database statistics: {e}")
            self._show_message(t("database_info_window.error_loading"), str(e)[:200])

    def _show_message(self, title: str, message: str) -> None:
        """Show a message in the statistics table.

        Args:
            title (str): Message title
            message (str): Message text
        """
        self.stats_table.clear()
        self.stats_table.setColumnCount(1)
        self.stats_table.setRowCount(2)
        self.stats_table.setHorizontalHeaderLabels([t("database_info_window.status_column")])

        title_item = QTableWidgetItem(title)
        title_item.setFlags(title_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.stats_table.setItem(0, 0, title_item)

        message_item = QTableWidgetItem(message)
        message_item.setFlags(message_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.stats_table.setItem(1, 0, message_item)

        header = self.stats_table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
