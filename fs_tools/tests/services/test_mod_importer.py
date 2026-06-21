"""Tests for ModImporter service."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import numpy as np
import pytest

from foxhole_stockpiles.enums.item_category import ItemCategory
from foxhole_stockpiles.enums.item_faction import ItemFaction
from foxhole_stockpiles.enums.supported_resolution import SupportedResolution
from foxhole_stockpiles.models.catalog_item import CatalogItem
from foxhole_stockpiles.models.icon_template import IconTemplate
from foxhole_stockpiles.models.mod_import_config import ModImportConfig
from foxhole_stockpiles.models.mod_import_progress import ModImportProgress
from foxhole_stockpiles.models.mod_import_result import ModImportResult
from foxhole_stockpiles.models.pak_validation_result import PakValidationResult
from fs_tools.services.mod_importer import ModImporter
from fs_tools.template_db.template_database import TemplateDatabase


def create_valid_pak_validation_result() -> PakValidationResult:
    """Create a valid PakValidationResult for test mocking."""
    result = PakValidationResult()
    result.is_valid = True
    result.has_crate_icon = True
    result.has_subicons = True
    result.subicons_count = 10
    return result


@pytest.fixture
def mock_config(tmp_path: Path) -> ModImportConfig:
    """Create a mock ModImportConfig for testing.

    Args:
        tmp_path: Temporary directory path

    Returns:
        ModImportConfig: Mock configuration
    """
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text("[]")

    extractor_tool = tmp_path / "repak.exe"
    extractor_tool.write_text("")

    converter_tool = tmp_path / "umodel.exe"
    converter_tool.write_text("")

    pak_file = tmp_path / "test.pak"
    pak_file.write_text("")

    database_path = tmp_path / "database.h5"

    return ModImportConfig(
        mod_pak_files=[str(pak_file)],
        mod_name="test_mod",
        catalog_path=catalog_file,
        overwrite=False,
        extractor_tool=extractor_tool,
        converter_tool=converter_tool,
        database_path=database_path,
        target_resolutions=None,
    )


# ===== Mod Name Validation Tests =====


class TestModNameValidation:
    """Test suite for mod name validation."""

    def test_valid_names(self, mock_config: ModImportConfig) -> None:
        """Test that valid mod names are accepted."""
        valid_names = [
            "test_mod",
            "Test-Mod",
            "Mod 123",
            "my_cool_mod-v2",
            "ABC",
            "mod_with_spaces and_underscores",
        ]

        for mod_name in valid_names:
            config = ModImportConfig(
                mod_pak_files=mock_config.mod_pak_files,
                mod_name=mod_name,
                catalog_path=mock_config.catalog_path,
                extractor_tool=mock_config.extractor_tool,
                converter_tool=mock_config.converter_tool,
                database_path=mock_config.database_path,
            )
            importer = ModImporter(config=config)
            assert importer.config.mod_name == mod_name.strip()

    def test_strips_whitespace(self, mock_config: ModImportConfig) -> None:
        """Test that mod name whitespace is stripped."""
        config = ModImportConfig(
            mod_pak_files=mock_config.mod_pak_files,
            mod_name="  test_mod  ",
            catalog_path=mock_config.catalog_path,
            extractor_tool=mock_config.extractor_tool,
            converter_tool=mock_config.converter_tool,
            database_path=mock_config.database_path,
        )
        importer = ModImporter(config=config)
        assert importer.config.mod_name == "test_mod"

    def test_empty_name_rejected(self, mock_config: ModImportConfig) -> None:
        """Test that empty mod names are rejected."""
        for empty_name in ["", "   "]:
            config = ModImportConfig(
                mod_pak_files=mock_config.mod_pak_files,
                mod_name=empty_name,
                catalog_path=mock_config.catalog_path,
                extractor_tool=mock_config.extractor_tool,
                converter_tool=mock_config.converter_tool,
                database_path=mock_config.database_path,
            )
            with pytest.raises(ValueError, match="Mod name cannot be empty"):
                ModImporter(config=config)

    def test_too_long_name_rejected(self, mock_config: ModImportConfig) -> None:
        """Test that too-long mod names are rejected."""
        config = ModImportConfig(
            mod_pak_files=mock_config.mod_pak_files,
            mod_name="a" * 101,
            catalog_path=mock_config.catalog_path,
            extractor_tool=mock_config.extractor_tool,
            converter_tool=mock_config.converter_tool,
            database_path=mock_config.database_path,
        )
        with pytest.raises(ValueError, match="Mod name is too long"):
            ModImporter(config=config)

    def test_path_traversal_blocked(self, mock_config: ModImportConfig) -> None:
        """Test that path traversal attempts are blocked."""
        invalid_names = [
            "../etc/passwd",
            "../../secret",
            "mod/../../../etc",
            "mod/subdir",
            "mod\\subdir",
            "C:\\Windows",
            "/etc/passwd",
        ]

        for mod_name in invalid_names:
            config = ModImportConfig(
                mod_pak_files=mock_config.mod_pak_files,
                mod_name=mod_name,
                catalog_path=mock_config.catalog_path,
                extractor_tool=mock_config.extractor_tool,
                converter_tool=mock_config.converter_tool,
                database_path=mock_config.database_path,
            )
            with pytest.raises(ValueError, match="can only contain alphanumeric"):
                ModImporter(config=config)

    def test_special_characters_rejected(self, mock_config: ModImportConfig) -> None:
        """Test that special characters are rejected."""
        invalid_names = [
            "mod<script>",
            "mod;rm -rf",
            "mod`whoami`",
            "mod$(whoami)",
            "mod&& echo test",
            "mod|cat",
            "mod\nmalicious",
            "mod\x00malicious",
            "mod@#$%",
        ]

        for mod_name in invalid_names:
            config = ModImportConfig(
                mod_pak_files=mock_config.mod_pak_files,
                mod_name=mod_name,
                catalog_path=mock_config.catalog_path,
                extractor_tool=mock_config.extractor_tool,
                converter_tool=mock_config.converter_tool,
                database_path=mock_config.database_path,
            )
            with pytest.raises(ValueError, match="can only contain alphanumeric"):
                ModImporter(config=config)


# ===== WSL Detection Tests =====


class TestWSLDetection:
    """Test suite for WSL temp directory detection."""

    def test_not_in_wsl(self) -> None:
        """Test WSL detection when not running in WSL."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = ModImporter.get_wsl_temp_dir()

        assert result is None

    def test_not_microsoft(self) -> None:
        """Test WSL detection when not Microsoft WSL."""
        mock_file = MagicMock()
        mock_file.read.return_value = "Linux version 5.4.0"
        mock_file.__enter__ = MagicMock(return_value=mock_file)
        mock_file.__exit__ = MagicMock(return_value=False)

        with patch("builtins.open", return_value=mock_file):
            result = ModImporter.get_wsl_temp_dir()

        assert result is None

    def test_success(self, tmp_path: Path) -> None:
        """Test successful WSL temp directory detection."""
        mock_proc_version = MagicMock()
        mock_proc_version.read.return_value = "Linux version with Microsoft WSL"
        mock_proc_version.__enter__ = MagicMock(return_value=mock_proc_version)
        mock_proc_version.__exit__ = MagicMock(return_value=False)

        wsl_temp = str(tmp_path / "wsl_temp")
        Path(wsl_temp).mkdir(exist_ok=True)

        with patch("builtins.open", return_value=mock_proc_version):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    Mock(stdout="C:\\Users\\Test\\AppData\\Local\\Temp\n", returncode=0),
                    Mock(stdout=f"{wsl_temp}\n", returncode=0),
                ]

                with patch("os.path.exists", return_value=True):
                    with patch("os.access", return_value=True):
                        result = ModImporter.get_wsl_temp_dir()

        assert result == wsl_temp

    def test_powershell_fails(self) -> None:
        """Test WSL temp directory when PowerShell fails."""
        mock_proc_version = MagicMock()
        mock_proc_version.read.return_value = "Linux version with Microsoft WSL"
        mock_proc_version.__enter__ = MagicMock(return_value=mock_proc_version)
        mock_proc_version.__exit__ = MagicMock(return_value=False)

        with patch("builtins.open", return_value=mock_proc_version):
            # Realistic failure: powershell.exe missing raises OSError/FileNotFoundError.
            with patch("subprocess.run", side_effect=OSError("PowerShell failed")):
                result = ModImporter.get_wsl_temp_dir()

        assert result is None

    def test_empty_temp(self) -> None:
        """Test WSL temp directory when TEMP is empty."""
        mock_proc_version = MagicMock()
        mock_proc_version.read.return_value = "Linux version with Microsoft WSL"
        mock_proc_version.__enter__ = MagicMock(return_value=mock_proc_version)
        mock_proc_version.__exit__ = MagicMock(return_value=False)

        with patch("builtins.open", return_value=mock_proc_version):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = Mock(stdout="", returncode=0)
                result = ModImporter.get_wsl_temp_dir()

        assert result is None

    def test_path_not_accessible(self) -> None:
        """Test WSL temp directory when path is not accessible."""
        mock_proc_version = MagicMock()
        mock_proc_version.read.return_value = "Linux version with Microsoft WSL"
        mock_proc_version.__enter__ = MagicMock(return_value=mock_proc_version)
        mock_proc_version.__exit__ = MagicMock(return_value=False)

        with patch("builtins.open", return_value=mock_proc_version):
            with patch("subprocess.run") as mock_run:
                mock_run.side_effect = [
                    Mock(stdout="C:\\Users\\Test\\AppData\\Local\\Temp\n", returncode=0),
                    Mock(stdout="/mnt/c/Users/Test/AppData/Local/Temp\n", returncode=0),
                ]

                with patch("os.path.exists", return_value=True):
                    with patch("os.access", return_value=False):
                        result = ModImporter.get_wsl_temp_dir()

        assert result is None


# ===== Configuration Validation Tests =====


class TestConfigValidation:
    """Test suite for configuration validation."""

    @pytest.mark.asyncio
    async def test_missing_extractor_tool(self, mock_config: ModImportConfig) -> None:
        """Test validation fails when extractor tool is not configured."""
        mock_config.extractor_tool = None
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "Extractor tool not configured" in result.error_message

    @pytest.mark.asyncio
    async def test_missing_converter_tool(self, mock_config: ModImportConfig) -> None:
        """Test validation fails when converter tool is not configured."""
        mock_config.converter_tool = None
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "Converter tool not configured" in result.error_message

    @pytest.mark.asyncio
    async def test_extractor_not_found(self, mock_config: ModImportConfig, tmp_path: Path) -> None:
        """Test validation fails when extractor tool file doesn't exist."""
        mock_config.extractor_tool = tmp_path / "nonexistent" / "repak.exe"
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "Extractor tool not found" in result.error_message

    @pytest.mark.asyncio
    async def test_converter_not_found(self, mock_config: ModImportConfig, tmp_path: Path) -> None:
        """Test validation fails when converter tool file doesn't exist."""
        mock_config.converter_tool = tmp_path / "nonexistent" / "umodel.exe"
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "Converter tool not found" in result.error_message

    @pytest.mark.asyncio
    async def test_missing_database_path(self, mock_config: ModImportConfig) -> None:
        """Test validation fails when database path is not configured."""
        mock_config.database_path = None
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "Database path not configured" in result.error_message

    @pytest.mark.asyncio
    async def test_pak_file_not_found(self, mock_config: ModImportConfig) -> None:
        """Test validation fails when PAK file doesn't exist."""
        mock_config.mod_pak_files = ["/nonexistent/mod.pak"]
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "PAK file not found" in result.error_message


# ===== Database Query Tests =====


class TestDatabaseQueries:
    """Test suite for database query functionality."""

    @pytest.mark.asyncio
    async def test_get_existing_icons_no_database(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test get_existing_item_codes when database doesn't exist."""
        mock_config.database_path = tmp_path / "nonexistent_db"
        importer = ModImporter(config=mock_config)

        existing = await importer._get_existing_item_codes_from_database()

        assert existing == set()

    @pytest.mark.asyncio
    async def test_get_existing_icons_with_templates(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test get_existing_item_codes finds templates from database."""
        db_path = tmp_path / "database.h5"
        db_path.touch()
        mock_config.database_path = db_path

        mock_template = IconTemplate(
            code="TEST001",
            image=np.zeros((64, 64, 3), dtype=np.uint8),
            phash=0,
            crated=False,
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            mod="test_mod",
            resolution=SupportedResolution.R_1080,
        )

        mock_db = TemplateDatabase(SupportedResolution.R_1080)
        mock_db.add_template(mock_template)

        async def mock_load_database(
            self: Any, resolution: SupportedResolution
        ) -> TemplateDatabase:
            return mock_db

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.template_db.template_manager.TemplateManager.load_database",
            new=mock_load_database,
        ):
            existing = await importer._get_existing_item_codes_from_database()

        assert "TEST001" in existing
        assert len(existing) == 1

    @pytest.mark.asyncio
    async def test_get_existing_icons_filters_by_mod(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test get_existing_item_codes only returns codes for the current mod."""
        db_path = tmp_path / "database.h5"
        db_path.touch()
        mock_config.database_path = db_path

        template_same_mod = IconTemplate(
            code="SAME_MOD",
            image=np.zeros((64, 64, 3), dtype=np.uint8),
            phash=0,
            crated=False,
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            mod="test_mod",
            resolution=SupportedResolution.R_1080,
        )

        template_other_mod = IconTemplate(
            code="OTHER_MOD",
            image=np.zeros((64, 64, 3), dtype=np.uint8),
            phash=0,
            crated=False,
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            mod="other_mod",
            resolution=SupportedResolution.R_1080,
        )

        mock_db = TemplateDatabase(SupportedResolution.R_1080)
        mock_db.add_template(template_same_mod)
        mock_db.add_template(template_other_mod)

        async def mock_load_database(
            self: Any, resolution: SupportedResolution
        ) -> TemplateDatabase:
            return mock_db

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.template_db.template_manager.TemplateManager.load_database",
            new=mock_load_database,
        ):
            existing = await importer._get_existing_item_codes_from_database()

        assert "SAME_MOD" in existing
        assert "OTHER_MOD" not in existing
        assert len(existing) == 1


# ===== Progress Callback Tests =====


class TestProgressCallbacks:
    """Test suite for progress callback functionality."""

    @pytest.mark.asyncio
    async def test_progress_callback_called(self, mock_config: ModImportConfig) -> None:
        """Test that progress callback is called during import."""
        progress_updates: list[ModImportProgress] = []

        def capture_progress(progress: ModImportProgress) -> None:
            progress_updates.append(progress)

        importer = ModImporter(config=mock_config, progress_callback=capture_progress)

        # Run will fail validation but should still call progress callback
        await importer.run()

        # At least one progress update should have been made
        assert len(progress_updates) >= 1

    @pytest.mark.asyncio
    async def test_cancel_check_respected(self, mock_config: ModImportConfig) -> None:
        """Test that cancel check function is respected."""
        cancel_called = [False]

        def should_cancel() -> bool:
            cancel_called[0] = True
            return True  # Always cancel

        # Mock valid config
        with patch.object(ModImporter, "_validate_config"):
            with patch("tempfile.mkdtemp", return_value="/tmp/test"):
                with patch("shutil.rmtree"):
                    importer = ModImporter(config=mock_config, cancel_check=should_cancel)
                    result = await importer.run()

        # Cancel should have been checked
        assert cancel_called[0] is True
        # Result should indicate not complete (cancelled)
        assert result.success is False or result.templates_added == 0


# ===== Full Pipeline Tests =====


class TestFullPipeline:
    """Test suite for full pipeline execution."""

    @pytest.mark.asyncio
    async def test_pipeline_success(self, mock_config: ModImportConfig, tmp_path: Path) -> None:
        """Test successful full pipeline execution."""
        test_import_dir = tmp_path / "test_import"
        extracted_assets_dir = test_import_dir / "extracted_assets" / "test_mod"
        extracted_assets_dir.mkdir(parents=True, exist_ok=True)

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
        ]

        importer = ModImporter(config=mock_config)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        with patch.object(
                            importer, "_get_existing_item_codes_from_database", return_value=set()
                        ):
                            with patch(
                                "fs_tools.services.mod_importer.load_catalog",
                                return_value=mock_catalog,
                            ):

                                async def mock_extract(*args: Any, **kwargs: Any) -> None:
                                    (extracted_assets_dir / "icon1.png").touch()

                                with patch.object(
                                    importer, "_extract_assets", side_effect=mock_extract
                                ):
                                    with patch.object(
                                        importer, "_generate_templates", new_callable=AsyncMock
                                    ):
                                        with patch.object(
                                            importer, "_build_database", new_callable=AsyncMock
                                        ):
                                            result = await importer.run()

        assert result.success is True

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self, mock_config: ModImportConfig) -> None:
        """Test pipeline error handling when validation fails."""
        # Use invalid config to trigger validation error
        mock_config.extractor_tool = None
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "Extractor tool not configured" in result.error_message


# ===== Data Classes Tests =====


class TestDataClasses:
    """Test suite for data classes."""

    def test_mod_import_config_defaults(self, tmp_path: Path) -> None:
        """Test ModImportConfig default values."""
        catalog = tmp_path / "catalog.json"
        catalog.touch()

        config = ModImportConfig(
            mod_pak_files=["test.pak"],
            mod_name="test",
            catalog_path=catalog,
        )

        assert config.overwrite is False
        assert config.vanilla_pak_file is None
        assert config.extractor_tool is None
        assert config.converter_tool is None
        assert config.database_path is None
        assert config.target_resolutions is None
        assert config.template_settings is None

    def test_mod_import_progress_defaults(self) -> None:
        """Test ModImportProgress default values."""
        progress = ModImportProgress()

        assert progress.current_step == 0
        assert progress.total_steps == 4
        assert progress.step_name == ""
        assert progress.message == ""
        assert progress.is_complete is False
        assert progress.is_error is False
        assert progress.error_message == ""

    def test_mod_import_result_defaults(self) -> None:
        """Test ModImportResult default values."""
        result = ModImportResult()

        assert result.success is False
        assert result.templates_added == 0
        assert result.templates_skipped == 0
        assert result.error_message == ""
        assert result.warnings == []


# ===== Additional Config Validation Tests =====


class TestConfigValidationExtended:
    """Extended test suite for configuration validation."""

    @pytest.mark.asyncio
    async def test_catalog_not_found(self, mock_config: ModImportConfig, tmp_path: Path) -> None:
        """Test validation fails when catalog file doesn't exist."""
        mock_config.catalog_path = tmp_path / "nonexistent" / "catalog.json"
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "Catalog file not found" in result.error_message

    @pytest.mark.asyncio
    async def test_no_mod_pak_files(self, mock_config: ModImportConfig) -> None:
        """Test validation fails when no PAK files are specified."""
        mock_config.mod_pak_files = []
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "No mod PAK files specified" in result.error_message

    @pytest.mark.asyncio
    async def test_vanilla_pak_not_found(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test validation fails when vanilla PAK file doesn't exist."""
        mock_config.vanilla_pak_file = str(tmp_path / "nonexistent" / "vanilla.pak")
        importer = ModImporter(config=mock_config)

        result = await importer.run()

        assert result.success is False
        assert "Vanilla PAK file not found" in result.error_message


# ===== Database Query Extended Tests =====


class TestDatabaseQueryExtended:
    """Extended test suite for database query functionality."""

    @pytest.mark.asyncio
    async def test_get_existing_icons_with_target_resolutions(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test get_existing_item_codes uses target_resolutions when specified."""
        db_path = tmp_path / "database.h5"
        db_path.touch()
        mock_config.database_path = db_path
        mock_config.target_resolutions = ["1080"]

        mock_template = IconTemplate(
            code="TEST001",
            image=np.zeros((64, 64, 3), dtype=np.uint8),
            phash=0,
            crated=False,
            faction=ItemFaction.NEUTRAL,
            category=ItemCategory.Item,
            mod="test_mod",
            resolution=SupportedResolution.R_1080,
        )

        mock_db = TemplateDatabase(SupportedResolution.R_1080)
        mock_db.add_template(mock_template)

        async def mock_load_database(
            self: Any, resolution: SupportedResolution
        ) -> TemplateDatabase:
            return mock_db

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.template_db.template_manager.TemplateManager.load_database",
            new=mock_load_database,
        ):
            existing = await importer._get_existing_item_codes_from_database()

        assert "TEST001" in existing

    @pytest.mark.asyncio
    async def test_get_existing_icons_handles_file_not_found(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test get_existing_item_codes handles FileNotFoundError gracefully."""
        db_path = tmp_path / "database.h5"
        db_path.touch()
        mock_config.database_path = db_path

        async def mock_load_database(
            self: Any, resolution: SupportedResolution
        ) -> TemplateDatabase:
            raise FileNotFoundError("Database not found")

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.template_db.template_manager.TemplateManager.load_database",
            new=mock_load_database,
        ):
            existing = await importer._get_existing_item_codes_from_database()

        assert existing == set()

    @pytest.mark.asyncio
    async def test_get_existing_icons_handles_generic_exception(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test get_existing_item_codes handles generic exceptions gracefully."""
        db_path = tmp_path / "database.h5"
        db_path.touch()
        mock_config.database_path = db_path

        async def mock_load_database(
            self: Any, resolution: SupportedResolution
        ) -> TemplateDatabase:
            raise RuntimeError("Unexpected error loading database")

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.template_db.template_manager.TemplateManager.load_database",
            new=mock_load_database,
        ):
            existing = await importer._get_existing_item_codes_from_database()

        assert existing == set()


# ===== Full Pipeline Extended Tests =====


class TestFullPipelineExtended:
    """Extended test suite for full pipeline execution."""

    @pytest.mark.asyncio
    async def test_pipeline_all_items_exist_in_database(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test pipeline succeeds when all items already exist in database."""
        test_import_dir = tmp_path / "test_import"
        test_import_dir.mkdir(parents=True, exist_ok=True)

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
        ]

        importer = ModImporter(config=mock_config)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        with patch.object(
                            importer,
                            "_get_existing_item_codes_from_database",
                            return_value={"ITEM001"},
                        ):
                            with patch(
                                "fs_tools.services.mod_importer.load_catalog",
                                return_value=mock_catalog,
                            ):
                                result = await importer.run()

        assert result.success is True
        assert result.templates_skipped == 1

    @pytest.mark.asyncio
    async def test_pipeline_overwrite_mode(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test pipeline in overwrite mode extracts all items."""
        mock_config.overwrite = True
        test_import_dir = tmp_path / "test_import"
        extracted_assets_dir = test_import_dir / "extracted_assets" / "test_mod"
        extracted_assets_dir.mkdir(parents=True, exist_ok=True)

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
        ]

        importer = ModImporter(config=mock_config)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        with patch.object(
                            importer,
                            "_get_existing_item_codes_from_database",
                            return_value={"ITEM001"},
                        ):
                            with patch(
                                "fs_tools.services.mod_importer.load_catalog",
                                return_value=mock_catalog,
                            ):

                                async def mock_extract(*args: Any, **kwargs: Any) -> None:
                                    (extracted_assets_dir / "icon1.png").touch()

                                with patch.object(
                                    importer, "_extract_assets", side_effect=mock_extract
                                ):
                                    with patch.object(
                                        importer, "_generate_templates", new_callable=AsyncMock
                                    ):
                                        with patch.object(
                                            importer, "_build_database", new_callable=AsyncMock
                                        ):
                                            result = await importer.run()

        assert result.success is True
        assert result.templates_skipped == 0

    @pytest.mark.asyncio
    async def test_pipeline_cancel_before_extraction(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test pipeline can be cancelled before extraction."""
        test_import_dir = tmp_path / "test_import"
        test_import_dir.mkdir(parents=True, exist_ok=True)

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
        ]

        # Cancel on third check (after catalog check, before extraction)
        cancel_count = [0]

        def should_cancel() -> bool:
            cancel_count[0] += 1
            return cancel_count[0] >= 3

        importer = ModImporter(config=mock_config, cancel_check=should_cancel)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        with patch.object(
                            importer,
                            "_get_existing_item_codes_from_database",
                            return_value=set(),
                        ):
                            with patch(
                                "fs_tools.services.mod_importer.load_catalog",
                                return_value=mock_catalog,
                            ):
                                result = await importer.run()

        assert result.templates_added == 0

    @pytest.mark.asyncio
    async def test_pipeline_no_items_extracted_with_existing(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test pipeline when no items are extracted but some exist in database."""
        test_import_dir = tmp_path / "test_import"
        extracted_assets_dir = test_import_dir / "extracted_assets" / "test_mod"
        extracted_assets_dir.mkdir(parents=True, exist_ok=True)

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
            CatalogItem(
                code="ITEM002",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon2",
                subicon_path="",
            ),
        ]

        importer = ModImporter(config=mock_config)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        with patch.object(
                            importer,
                            "_get_existing_item_codes_from_database",
                            return_value={"ITEM001"},
                        ):
                            with patch(
                                "fs_tools.services.mod_importer.load_catalog",
                                return_value=mock_catalog,
                            ):
                                with patch.object(
                                    importer, "_extract_assets", new_callable=AsyncMock
                                ):
                                    result = await importer.run()

        assert result.success is True

    @pytest.mark.asyncio
    async def test_pipeline_no_items_extracted_no_existing(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test pipeline when no items are extracted and none exist."""
        test_import_dir = tmp_path / "test_import"
        extracted_assets_dir = test_import_dir / "extracted_assets" / "test_mod"
        extracted_assets_dir.mkdir(parents=True, exist_ok=True)

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
        ]

        importer = ModImporter(config=mock_config)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        with patch.object(
                            importer,
                            "_get_existing_item_codes_from_database",
                            return_value=set(),
                        ):
                            with patch(
                                "fs_tools.services.mod_importer.load_catalog",
                                return_value=mock_catalog,
                            ):
                                with patch.object(
                                    importer, "_extract_assets", new_callable=AsyncMock
                                ):
                                    result = await importer.run()

        assert result.success is True
        assert len(result.warnings) > 0

    @pytest.mark.asyncio
    async def test_pipeline_cancel_after_extraction(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test pipeline can be cancelled after extraction."""
        test_import_dir = tmp_path / "test_import"
        extracted_assets_dir = test_import_dir / "extracted_assets" / "test_mod"
        extracted_assets_dir.mkdir(parents=True, exist_ok=True)

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
        ]

        # Cancel on fourth check (after extraction)
        cancel_count = [0]

        def should_cancel() -> bool:
            cancel_count[0] += 1
            return cancel_count[0] >= 4

        importer = ModImporter(config=mock_config, cancel_check=should_cancel)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        with patch.object(
                            importer,
                            "_get_existing_item_codes_from_database",
                            return_value=set(),
                        ):
                            with patch(
                                "fs_tools.services.mod_importer.load_catalog",
                                return_value=mock_catalog,
                            ):

                                async def mock_extract(*args: Any, **kwargs: Any) -> None:
                                    (extracted_assets_dir / "icon1.png").touch()

                                with patch.object(
                                    importer, "_extract_assets", side_effect=mock_extract
                                ):
                                    result = await importer.run()

        assert result.templates_added == 0

    @pytest.mark.asyncio
    async def test_pipeline_cancel_after_template_generation(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test pipeline can be cancelled after template generation."""
        test_import_dir = tmp_path / "test_import"
        extracted_assets_dir = test_import_dir / "extracted_assets" / "test_mod"
        extracted_assets_dir.mkdir(parents=True, exist_ok=True)

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
        ]

        # Cancel on fifth check (after template generation)
        cancel_count = [0]

        def should_cancel() -> bool:
            cancel_count[0] += 1
            return cancel_count[0] >= 5

        importer = ModImporter(config=mock_config, cancel_check=should_cancel)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        with patch.object(
                            importer,
                            "_get_existing_item_codes_from_database",
                            return_value=set(),
                        ):
                            with patch(
                                "fs_tools.services.mod_importer.load_catalog",
                                return_value=mock_catalog,
                            ):

                                async def mock_extract(*args: Any, **kwargs: Any) -> None:
                                    (extracted_assets_dir / "icon1.png").touch()

                                with patch.object(
                                    importer, "_extract_assets", side_effect=mock_extract
                                ):
                                    with patch.object(
                                        importer, "_generate_templates", new_callable=AsyncMock
                                    ):
                                        result = await importer.run()

        assert result.templates_added == 0


# ===== Extract Assets Tests =====


class TestExtractAssets:
    """Test suite for asset extraction."""

    @pytest.mark.asyncio
    async def test_extract_assets_basic(self, mock_config: ModImportConfig, tmp_path: Path) -> None:
        """Test basic asset extraction."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_extractor = MagicMock()
        mock_extractor.process_files = AsyncMock(return_value=True)

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.PakExtractor",
            return_value=mock_extractor,
        ):
            await importer._extract_assets(output_dir, set())

        mock_extractor.process_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_assets_with_filter(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test asset extraction with existing codes filter."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Icons/Icon1",
                subicon_path="",
            ),
        ]

        mock_extractor = MagicMock()
        mock_extractor.process_files = AsyncMock(return_value=True)

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.load_catalog",
            return_value=mock_catalog,
        ):
            with patch(
                "fs_tools.services.mod_importer.PakExtractor",
                return_value=mock_extractor,
            ):
                await importer._extract_assets(output_dir, {"ITEM001"})

        mock_extractor.process_files.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_assets_with_vanilla_pak(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test asset extraction with vanilla PAK for dependencies."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        vanilla_pak = tmp_path / "vanilla.pak"
        vanilla_pak.touch()
        mock_config.vanilla_pak_file = str(vanilla_pak)

        mock_extractor = MagicMock()
        mock_extractor.process_files = AsyncMock(return_value=True)

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.PakExtractor",
            return_value=mock_extractor,
        ):
            (output_dir / "icon.png").touch()
            await importer._extract_assets(output_dir, set())

        assert mock_extractor.process_files.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_assets_extraction_fails(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test asset extraction when extraction fails."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_extractor = MagicMock()
        mock_extractor.process_files = AsyncMock(return_value=False)

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.PakExtractor",
            return_value=mock_extractor,
        ):
            await importer._extract_assets(output_dir, set())

        mock_extractor.process_files.assert_called_once()


# ===== Generate Templates Tests =====


class TestGenerateTemplates:
    """Test suite for template generation."""

    @pytest.mark.asyncio
    async def test_generate_templates_basic(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test basic template generation."""
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        output_dir = tmp_path / "templates"
        output_dir.mkdir()

        mock_generator = MagicMock()
        mock_generator.generate_all_templates = AsyncMock(return_value=True)

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.TemplateGenerator",
            return_value=mock_generator,
        ):
            await importer._generate_templates(assets_dir, output_dir)

        mock_generator.generate_all_templates.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_templates_fails_no_output(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test template generation when it fails with no output."""
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        output_dir = tmp_path / "templates"
        output_dir.mkdir()

        mock_generator = MagicMock()
        mock_generator.generate_all_templates = AsyncMock(return_value=False)

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.TemplateGenerator",
            return_value=mock_generator,
        ):
            await importer._generate_templates(assets_dir, output_dir)

        mock_generator.generate_all_templates.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_templates_partial_success(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test template generation with partial success."""
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()
        output_dir = tmp_path / "templates"
        output_dir.mkdir()
        (output_dir / "template.png").touch()

        mock_generator = MagicMock()
        mock_generator.generate_all_templates = AsyncMock(return_value=False)

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.TemplateGenerator",
            return_value=mock_generator,
        ):
            await importer._generate_templates(assets_dir, output_dir)

        mock_generator.generate_all_templates.assert_called_once()


# ===== Build Database Tests =====


class TestBuildDatabase:
    """Test suite for database building."""

    @pytest.mark.asyncio
    async def test_build_database_basic(self, mock_config: ModImportConfig, tmp_path: Path) -> None:
        """Test basic database building."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        mock_builder = MagicMock()
        mock_builder.build_all_databases = AsyncMock()

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.DatabaseBuilder",
            return_value=mock_builder,
        ):
            await importer._build_database(templates_dir)

        mock_builder.build_all_databases.assert_called_once()

    @pytest.mark.asyncio
    async def test_build_database_with_resolutions(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test database building with specific resolutions."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        mock_config.target_resolutions = ["1080", "1440"]

        mock_builder = MagicMock()
        mock_builder.build_all_databases = AsyncMock()

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.DatabaseBuilder",
            return_value=mock_builder,
        ):
            await importer._build_database(templates_dir)

        call_kwargs = mock_builder.build_all_databases.call_args[1]
        assert len(call_kwargs["target_resolutions"]) == 2

    @pytest.mark.asyncio
    async def test_build_database_invalid_resolution_skipped(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test database building skips invalid resolutions."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        mock_config.target_resolutions = ["1080", "invalid", "1440"]

        mock_builder = MagicMock()
        mock_builder.build_all_databases = AsyncMock()

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.DatabaseBuilder",
            return_value=mock_builder,
        ):
            await importer._build_database(templates_dir)

        call_kwargs = mock_builder.build_all_databases.call_args[1]
        assert len(call_kwargs["target_resolutions"]) == 2

    @pytest.mark.asyncio
    async def test_build_database_no_database_path_raises(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test database building raises when database path is None."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        mock_config.database_path = None

        importer = ModImporter(config=mock_config)

        with pytest.raises(ValueError, match="No database path configured"):
            await importer._build_database(templates_dir)


# ===== Create Config From Settings Tests =====


class TestCreateConfigFromSettings:
    """Test suite for create_config_from_settings function."""

    def test_create_config_success(self, tmp_path: Path) -> None:
        """Test successful config creation from settings."""
        from fs_tools.services.mod_importer import create_config_from_settings

        catalog = tmp_path / "catalog.json"
        catalog.touch()

        settings = MagicMock()
        settings.database_builder.catalog_file = catalog
        settings.database_builder.target_resolutions = ["1080"]
        settings.external_tools.repak = tmp_path / "repak.exe"
        settings.external_tools.umodel = tmp_path / "umodel.exe"
        settings.scanner.database_path = tmp_path / "db.h5"
        settings.templates = None

        config = create_config_from_settings(
            settings=settings,
            mod_pak_files=["test.pak"],
            mod_name="TestMod",
            overwrite=True,
            vanilla_pak_file="vanilla.pak",
        )

        assert config.mod_pak_files == ["test.pak"]
        assert config.mod_name == "TestMod"
        assert config.overwrite is True
        assert config.vanilla_pak_file == "vanilla.pak"
        assert config.catalog_path == catalog

    def test_create_config_no_catalog_raises(self) -> None:
        """Test config creation raises when catalog is not configured."""
        from fs_tools.services.mod_importer import create_config_from_settings

        settings = MagicMock()
        settings.database_builder.catalog_file = None

        with pytest.raises(ValueError, match="catalog_file not configured"):
            create_config_from_settings(
                settings=settings,
                mod_pak_files=["test.pak"],
                mod_name="TestMod",
            )


# ===== PAK Validation Tests =====


class TestPakValidation:
    """Test suite for PAK file validation."""

    @pytest.mark.asyncio
    async def test_validate_pak_files_with_vanilla(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test PAK validation includes vanilla PAK file when configured."""
        vanilla_pak = tmp_path / "vanilla.pak"
        vanilla_pak.touch()
        mock_config.vanilla_pak_file = str(vanilla_pak)

        importer = ModImporter(config=mock_config)

        mock_result = create_valid_pak_validation_result()

        with patch(
            "fs_tools.services.mod_importer.PakExtractor.validate_required_assets",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_validate:
            result = await importer._validate_pak_files()

        # Verify vanilla PAK was included in the validation
        call_args = mock_validate.call_args
        pak_files = call_args[1]["pak_files"]
        assert str(vanilla_pak) in pak_files
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_pipeline_cancel_after_validation(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test pipeline can be cancelled immediately after validation."""
        test_import_dir = tmp_path / "test_import"
        test_import_dir.mkdir(parents=True, exist_ok=True)

        # Cancel on second check (after validation)
        cancel_count = [0]

        def should_cancel() -> bool:
            cancel_count[0] += 1
            return cancel_count[0] >= 2

        importer = ModImporter(config=mock_config, cancel_check=should_cancel)

        async def mock_validate() -> PakValidationResult:
            return create_valid_pak_validation_result()

        with patch.object(ModImporter, "get_wsl_temp_dir", return_value=None):
            with patch("tempfile.mkdtemp", return_value=str(test_import_dir)):
                with patch("shutil.rmtree"):
                    with patch.object(importer, "_validate_pak_files", side_effect=mock_validate):
                        result = await importer.run()

        # Should have cancelled after validation, before catalog check
        assert result.templates_added == 0


# ===== Extract Assets Filter Tests =====


class TestExtractAssetsFilters:
    """Test suite for asset extraction filter functions."""

    @pytest.mark.asyncio
    async def test_extract_assets_filter_with_subicon(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test asset extraction filter correctly handles subicon_path."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_catalog = [
            CatalogItem(
                code="ITEM001",
                category=ItemCategory.Item,
                icon_path="War/Content/Textures/UI/ItemIcons/Icon1",
                subicon_path="War/Content/Textures/UI/ItemIcons/SubtypeAmmoIcon",
            ),
            CatalogItem(
                code="ITEM002",
                category=ItemCategory.Item,
                icon_path="War/Content/Textures/UI/ItemIcons/Icon2",
                subicon_path="",
            ),
        ]

        captured_filter = [None]

        class MockExtractor:
            def __init__(self, **kwargs: Any) -> None:
                captured_filter[0] = kwargs.get("filter_assets")

            async def process_files(self) -> bool:
                return True

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.load_catalog",
            return_value=mock_catalog,
        ):
            with patch(
                "fs_tools.services.mod_importer.PakExtractor",
                MockExtractor,
            ):
                # Pass existing codes to trigger filter creation
                await importer._extract_assets(output_dir, {"ITEM001"})

        # Verify filter was created and works correctly
        filter_fn = captured_filter[0]
        assert filter_fn is not None

        # Icon for ITEM001 should be filtered out (exists in database)
        assert filter_fn("War/Content/Textures/UI/ItemIcons/Icon1.uasset") is False
        # Subicon for ITEM001 should also be filtered out
        assert filter_fn("War/Content/Textures/UI/ItemIcons/SubtypeAmmoIcon.uasset") is False
        # Icon for ITEM002 should be allowed (not in existing codes)
        assert filter_fn("War/Content/Textures/UI/ItemIcons/Icon2.uasset") is True
        # Unknown path should be allowed
        assert filter_fn("War/Content/Other/Something.uasset") is True

    @pytest.mark.asyncio
    async def test_extract_assets_vanilla_filter(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test vanilla extraction filter correctly identifies dependencies."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        vanilla_pak = tmp_path / "vanilla.pak"
        vanilla_pak.touch()
        mock_config.vanilla_pak_file = str(vanilla_pak)

        captured_filters: list[Any] = []

        class MockExtractor:
            def __init__(self, **kwargs: Any) -> None:
                captured_filters.append(kwargs.get("filter_assets"))

            async def process_files(self) -> bool:
                return True

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.PakExtractor",
            MockExtractor,
        ):
            await importer._extract_assets(output_dir, set())

        # First filter should be the vanilla filter (extracted first as fallback base)
        # Second filter is the mod filter (None when no existing codes)
        assert len(captured_filters) == 2
        vanilla_filter = captured_filters[0]
        assert vanilla_filter is not None

        # Test vanilla filter logic - subicons have "Subtype" in filename
        assert vanilla_filter("War/Content/Textures/UI/ItemIcons/SubtypeAmmoIcon.uasset") is True
        assert vanilla_filter("War/Content/IconFilterCrates.uasset") is True
        assert vanilla_filter("War/Content/Icons/random.uasset") is False

    @pytest.mark.asyncio
    async def test_extract_assets_vanilla_extraction_fails(
        self, mock_config: ModImportConfig, tmp_path: Path
    ) -> None:
        """Test warning is logged when vanilla PAK extraction fails."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        vanilla_pak = tmp_path / "vanilla.pak"
        vanilla_pak.touch()
        mock_config.vanilla_pak_file = str(vanilla_pak)

        call_count = [0]

        class MockExtractor:
            def __init__(self, **kwargs: Any) -> None:
                pass

            async def process_files(self) -> bool:
                call_count[0] += 1
                # First call (vanilla) fails, second call (mod) succeeds
                return call_count[0] == 2

        importer = ModImporter(config=mock_config)

        with patch(
            "fs_tools.services.mod_importer.PakExtractor",
            MockExtractor,
        ):
            # Should not raise, just log warning for vanilla failure
            await importer._extract_assets(output_dir, set())

        assert call_count[0] == 2
