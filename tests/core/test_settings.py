"""Tests for configuration settings module.

This module contains comprehensive tests for the settings system,
including validation, defaults, custom values, environment variable
handling, and file-based configuration loading.
"""

import os
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from pydantic_settings import BaseSettings
from pydantic_settings.sources import PydanticBaseSettingsSource

from foxhole_stockpiles.core.settings import AppSettings, get_settings, reload_settings
from foxhole_stockpiles.core.settings.config_migrator import ConfigMigrator
from foxhole_stockpiles.core.settings.sections import SheetsHandlerSettings
from foxhole_stockpiles.core.settings.sections.logging import LoggingSettings
from foxhole_stockpiles.core.settings.sections.ocr import OCRSettings
from foxhole_stockpiles.core.settings.sections.output import (
    ConsoleHandlerSettings,
    CsvFormatSettings,
    FileHandlerSettings,
    JsonFormatSettings,
    OutputHandlerConfig,
    OutputSettings,
    ReturnHandlerSettings,
    WebhookHandlerSettings,
)
from foxhole_stockpiles.core.settings.sections.scanner import ScannerSettings
from foxhole_stockpiles.core.settings.sections.stockpile_types import StockpileTypesSettings
from foxhole_stockpiles.enums.auth_type import AuthType
from foxhole_stockpiles.enums.output_format import OutputFormat


class TestLoggingSettings:
    """Test cases for LoggingSettings.

    This class contains tests for the LoggingSettings configuration model,
    including default values, custom configurations, and validation.
    """

    def test_logging_settings_defaults(self) -> None:
        """Test default logging settings.

        Verifies that LoggingSettings initializes with the correct default values
        for all configuration parameters.
        """
        settings = LoggingSettings()

        assert settings.loggers == {}
        assert settings.log_level == "INFO"
        assert settings.log_format == "[%(asctime)s] %(levelname)s [%(name)s] %(message)s"
        assert settings.date_format == "%Y-%m-%d %H:%M:%S"
        assert settings.rotate_logs is False
        assert settings.log_file is None

    def test_logging_settings_custom_values(self) -> None:
        """Test logging settings with custom values.

        Verifies that LoggingSettings properly accepts and stores custom
        configuration values for all parameters.
        """
        custom_loggers = {"foxhole_stockpiles": "DEBUG", "uvicorn": "WARNING"}

        settings = LoggingSettings(
            loggers=custom_loggers,
            log_level="DEBUG",
            log_format="%(levelname)s: %(message)s",
            date_format="%Y-%m-%d",
            rotate_logs=True,
            log_file="app.log",
        )

        assert settings.loggers == custom_loggers
        assert settings.log_level == "DEBUG"
        assert settings.log_format == "%(levelname)s: %(message)s"
        assert settings.date_format == "%Y-%m-%d"
        assert settings.rotate_logs is True
        assert settings.log_file == "app.log"

    def test_logging_settings_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden in logging settings.

        Verifies that LoggingSettings rejects unknown fields according to
        Pydantic's extra='forbid' configuration.
        """
        with pytest.raises(ValidationError) as exc_info:
            LoggingSettings(log_level="DEBUG", unknown_field="ignored")  # type: ignore[call-arg]

        assert "Extra inputs are not permitted" in str(exc_info.value)


class TestOCRSettings:
    """Test cases for OCRSettings.

    This class contains tests for the OCRSettings configuration model,
    including default values, custom configurations, and validation.
    """

    def test_ocr_settings_defaults(self) -> None:
        """Test default OCR settings.

        Verifies that OCRSettings initializes with the correct default values
        for all OCR-related configuration parameters.
        """
        settings = OCRSettings()

        assert settings.height == 2160
        assert settings.box_width == 84
        assert settings.box_height == 64
        assert settings.column_offset == 112
        assert settings.row_offset == 78
        assert settings.group_offset == 98

    def test_ocr_settings_custom_values(self) -> None:
        """Test OCR settings with custom values.

        Verifies that OCRSettings properly accepts and stores custom
        configuration values for all OCR parameters.
        """
        settings = OCRSettings(
            height=1080,
            box_width=100,
            box_height=80,
            column_offset=120,
            row_offset=85,
            group_offset=105,
        )

        assert settings.height == 1080
        assert settings.box_width == 100
        assert settings.box_height == 80
        assert settings.column_offset == 120
        assert settings.row_offset == 85
        assert settings.group_offset == 105

    def test_ocr_settings_validation_positive_values(self) -> None:
        """Test that OCR settings validate positive values."""
        with pytest.raises(ValidationError) as exc_info:
            OCRSettings(height=0)

        assert "greater than 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            OCRSettings(box_width=-1)

        assert "greater than 0" in str(exc_info.value)


class TestFileHandlerSettings:
    """Test cases for FileHandlerSettings."""

    def test_file_handler_defaults(self) -> None:
        """Test default file handler settings."""
        settings = FileHandlerSettings()
        assert settings.path == "output.json"

    def test_file_handler_custom_path(self) -> None:
        """Test file handler with custom path."""
        settings = FileHandlerSettings(path="custom.txt")
        assert settings.path == "custom.txt"


class TestWebhookHandlerSettings:
    """Test cases for WebhookHandlerSettings."""

    def test_webhook_handler_custom_values(self) -> None:
        """Test webhook handler with custom values."""
        settings = WebhookHandlerSettings(
            url="https://example.com/webhook",
            auth_type=AuthType.BEARER,
            token="secret_token",
        )
        assert settings.url == "https://example.com/webhook"
        assert settings.auth_type == AuthType.BEARER
        assert settings.token == "secret_token"

    def test_webhook_auth_bearer_validation(self) -> None:
        """Test bearer auth validation."""
        # Should fail when bearer auth_type is provided without token
        with pytest.raises(ValidationError) as exc_info:
            WebhookHandlerSettings(url="https://example.com", auth_type=AuthType.BEARER)
        assert "token must be set when auth_type is 'bearer'" in str(exc_info.value)

        # Should pass when bearer and token are provided
        settings = WebhookHandlerSettings(
            url="https://example.com", auth_type=AuthType.BEARER, token="token"
        )
        assert settings.auth_type == AuthType.BEARER
        assert settings.token == "token"

    def test_webhook_auth_forward_validation(self) -> None:
        """Test forward auth validation."""
        # Should fail when forward auth_type is provided without client header
        with pytest.raises(ValidationError) as exc_info:
            WebhookHandlerSettings(url="https://example.com", auth_type=AuthType.FORWARD)
        assert "client_auth_header must be set when auth_type is 'forward'" in str(exc_info.value)

        # Should pass when forward and client_auth_header are provided
        settings = WebhookHandlerSettings(
            url="https://example.com", auth_type=AuthType.FORWARD, client_auth_header="X-Auth"
        )
        assert settings.auth_type == AuthType.FORWARD
        assert settings.client_auth_header == "X-Auth"


class TestOutputSettings:
    """Test cases for OutputSettings (v5 with handlers)."""

    def test_output_settings_defaults(self) -> None:
        """Test default output settings has empty handlers list."""
        settings = OutputSettings()
        assert settings.handlers == []

    def test_output_settings_with_handlers(self) -> None:
        """Test output settings with handler configurations."""
        settings = OutputSettings(
            handlers=[
                OutputHandlerConfig(
                    name="Webhook",
                    handler=WebhookHandlerSettings(
                        url="https://example.com/webhook",
                        auth_type=AuthType.BEARER,
                        token="token123",
                    ),
                )
            ]
        )
        assert len(settings.handlers) == 1
        assert settings.handlers[0].name == "Webhook"
        handler = settings.handlers[0].handler
        assert isinstance(handler, WebhookHandlerSettings)
        assert handler.url == "https://example.com/webhook"

    def test_output_handler_enforces_json_for_webhook(self) -> None:
        """Test that webhook handlers are forced to use JSON format."""
        # Try to create a webhook handler with CSV format
        config = OutputHandlerConfig(
            name="Webhook",
            format=CsvFormatSettings(type=OutputFormat.CSV),
            handler=WebhookHandlerSettings(url="https://example.com/webhook"),
        )
        # Should be automatically converted to JSON
        assert isinstance(config.format, JsonFormatSettings)

    def test_output_handler_enforces_json_for_return(self) -> None:
        """Test that return handlers are forced to use JSON format."""
        config = OutputHandlerConfig(
            name="Return",
            format=CsvFormatSettings(type=OutputFormat.TSV),
            handler=ReturnHandlerSettings(),
        )
        assert isinstance(config.format, JsonFormatSettings)

    def test_output_handler_enforces_json_for_console(self) -> None:
        """Test that console handlers are forced to use JSON format."""
        config = OutputHandlerConfig(
            name="Console",
            format=CsvFormatSettings(type=OutputFormat.CSV),
            handler=ConsoleHandlerSettings(),
        )
        assert isinstance(config.format, JsonFormatSettings)

    def test_output_handler_allows_csv_for_file(self) -> None:
        """Test that file handlers allow CSV format."""
        config = OutputHandlerConfig(
            name="File",
            format=CsvFormatSettings(type=OutputFormat.CSV),
            handler=FileHandlerSettings(path="output.csv"),
        )
        assert isinstance(config.format, CsvFormatSettings)
        assert config.format.type == OutputFormat.CSV

    def test_output_handler_allows_tsv_for_file(self) -> None:
        """Test that file handlers allow TSV format."""
        config = OutputHandlerConfig(
            name="File",
            format=CsvFormatSettings(type=OutputFormat.TSV),
            handler=FileHandlerSettings(path="output.tsv"),
        )
        assert isinstance(config.format, CsvFormatSettings)
        assert config.format.type == OutputFormat.TSV


class TestStockpileTypesSettings:
    """Test cases for StockpileTypesSettings."""

    def test_stockpile_types_defaults(self) -> None:
        """Test default stockpile types settings has empty lists."""
        settings = StockpileTypesSettings()

        # All fields should default to empty lists (snake_case matching enum names)
        assert settings.encampment == []
        assert settings.keep == []
        assert settings.safe_house == []
        assert settings.relic_base == []
        assert settings.bunker_base_1 == []
        assert settings.border_base == []
        assert settings.town_base_1 == []
        assert settings.bms_longhook == []
        assert settings.bms_bluefin == []
        assert settings.storage_depot == []
        assert settings.seaport == []

    def test_stockpile_types_with_aliases(self) -> None:
        """Test stockpile types with additional aliases."""
        settings = StockpileTypesSettings(
            seaport=["seapon", "Seapont"],
            storage_depot=["Storage Depo"],
        )

        assert settings.seaport == ["seapon", "Seapont"]
        assert settings.storage_depot == ["Storage Depo"]

    def test_stockpile_types_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden."""
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            StockpileTypesSettings(unknown_field="value")  # type: ignore[call-arg]


class TestConfigMigration:
    """Test cases for config version migration."""

    def test_migrate_v1_to_v7_with_output_format(self) -> None:
        """Test migration from v1 (flat output) to v7 (handlers list + uesave removed)."""
        # V1 config with old flat structure
        v1_config = {
            "output_format": {
                "output_format": "json",
                "output_destination": "webhook",
                "file_path": "/tmp/output.json",
                "webhook_url": "https://example.com/webhook",
                "webhook_auth_type": "bearer",
                "webhook_token": "secret123",
                "webhook_client_auth_header": "X-API-TOKEN",
            }
        }

        # Apply migrations
        migrated = ConfigMigrator.apply_migrations(v1_config)

        # Verify migration occurred (v1 -> ... -> v8)
        assert migrated["config_version"] == 8
        assert "output_format" not in migrated
        assert "output" in migrated
        assert len(migrated["output"]["handlers"]) == 1

        handler_config = migrated["output"]["handlers"][0]
        assert handler_config["handler"]["type"] == "webhook"
        assert handler_config["handler"]["url"] == "https://example.com/webhook"
        assert handler_config["handler"]["auth_type"] == "bearer"
        assert handler_config["handler"]["token"] == "secret123"
        assert handler_config["handler"]["client_auth_header"] == "X-API-TOKEN"

        # Verify the migrated config can be loaded
        settings = AppSettings(**migrated)
        assert settings.config_version == 8
        assert len(settings.output.handlers) == 1
        handler = settings.output.handlers[0].handler
        assert isinstance(handler, WebhookHandlerSettings)
        assert handler.url == "https://example.com/webhook"

    def test_v2_config_migrates_to_v7(self) -> None:
        """Test that v2 configs migrate to v7."""
        # V2 config with nested structure
        v2_config = {
            "config_version": 2,
            "output": {
                "format": "json",
                "destination": "file",
                "file": {"path": "/custom/output.json"},
                "webhook": {"url": None},
            },
        }

        # Apply migrations
        migrated = ConfigMigrator.apply_migrations(v2_config)

        # Should migrate to v7 (v2 -> ... -> v8)
        assert migrated["config_version"] == 8
        assert len(migrated["output"]["handlers"]) == 1
        handler_config = migrated["output"]["handlers"][0]
        assert handler_config["handler"]["type"] == "file"
        assert handler_config["handler"]["path"] == "/custom/output.json"

        # Verify the migrated config can be loaded
        settings = AppSettings(**migrated)
        assert settings.config_version == 8
        assert len(settings.output.handlers) == 1
        handler = settings.output.handlers[0].handler
        assert isinstance(handler, FileHandlerSettings)
        assert handler.path == "/custom/output.json"

    def test_default_config_is_v7(self) -> None:
        """Test that default config is version 7."""
        settings = AppSettings()
        assert settings.config_version == 8

    def test_migrate_v1_to_v2_with_scanner_fields_cleanup(self) -> None:
        """Test migration removes deprecated scanner fields."""
        # V1 config with old scanner fields that should be removed
        v1_config = {
            "output_format": {
                "output_format": "json",
                "output_destination": "return",
            },
            "scanner": {
                "database_path": None,
                "confidence_threshold": 0.8,  # Should be removed
                "confidence_by_resolution": {"1080p": 0.85, "720p": 0.75},  # Should be removed
                "early_exit_threshold": 0.95,
            },
        }

        # Apply migrations
        migrated = ConfigMigrator.apply_migrations(v1_config)

        # Verify migration occurred (v1 -> ... -> v8)
        assert migrated["config_version"] == 8
        # Verify deprecated fields are removed
        assert "confidence_threshold" not in migrated["scanner"]
        assert "confidence_by_resolution" not in migrated["scanner"]
        # Verify valid fields remain
        assert migrated["scanner"]["early_exit_threshold"] == 0.95

        # Verify the migrated config can be loaded
        settings = AppSettings(**migrated)
        assert settings.config_version == 8
        assert settings.scanner.early_exit_threshold == 0.95

    def test_migrate_config_with_non_dict_data(self) -> None:
        """Test that migration guard clause returns non-dict data unchanged."""
        # The method has a guard clause for non-dict data (defensive programming)
        # In practice, this should never happen since validators check before calling
        result = ConfigMigrator.apply_migrations(None)  # type: ignore[arg-type]
        assert result is None

    def test_migrate_v3_to_v7_removes_undefined(self) -> None:
        """Test migration from v3 removes the undefined field from stockpile_types."""
        v3_config = {
            "config_version": 3,
            "stockpile_types": {
                "seaport": ["custom_alias"],
                "undefined": ["some_value"],  # Should be removed
            },
        }

        settings = AppSettings(**v3_config)  # type: ignore[arg-type]

        assert settings.config_version == 8
        # custom_alias remains in snake_case field
        assert settings.stockpile_types.seaport == ["custom_alias"]
        # undefined field should not exist on the model
        assert not hasattr(settings.stockpile_types, "undefined")

    def test_migrate_v3_to_v7_filters_default_translations(self) -> None:
        """Test migration from v3 filters out default translations, keeping only custom aliases."""
        v3_config = {
            "config_version": 3,
            "stockpile_types": {
                # Mix of defaults (should be filtered) and custom aliases (should remain)
                "seaport": ["Seaport", "Port", "seapon", "5eaport"],  # First two are defaults
                "storage_depot": [
                    "Storage Depot",
                    "Dépôt",
                    "Storage Depo",
                ],  # First two are defaults
                "encampment": ["Encampment"],  # Only default, should be empty after migration
            },
        }

        settings = AppSettings(**v3_config)  # type: ignore[arg-type]

        assert settings.config_version == 8
        # Only custom aliases should remain (snake_case field names)
        assert settings.stockpile_types.seaport == ["seapon", "5eaport"]
        assert settings.stockpile_types.storage_depot == ["Storage Depo"]
        assert settings.stockpile_types.encampment == []

    def test_migrate_v3_to_v7_keeps_only_custom_aliases(self) -> None:
        """Test migration preserves only user-added custom aliases."""
        v3_config = {
            "config_version": 3,
            "stockpile_types": {
                "bunker_base": ["Bunker Base", "MyCustomBase", "Base Bunker"],
                "town_base": ["custom_town"],
            },
        }

        settings = AppSettings(**v3_config)  # type: ignore[arg-type]

        assert settings.config_version == 8
        # v5->v6 migration renames bunker_base to bunker_base_1, town_base to town_base_1
        assert settings.stockpile_types.bunker_base_1 == ["MyCustomBase"]
        assert settings.stockpile_types.town_base_1 == ["custom_town"]

    def test_migrate_v6_to_v7_removes_uesave(self) -> None:
        """Test migration from v6 removes uesave from external_tools."""
        v6_config = {
            "config_version": 6,
            "external_tools": {
                "repak": "/path/to/repak",
                "umodel": "/path/to/umodel",
                "uassetgui": "/path/to/uassetgui",
                "uesave": "/path/to/uesave",  # Should be removed
            },
        }

        migrated = ConfigMigrator.apply_migrations(v6_config)

        assert migrated["config_version"] == 8
        assert "uesave" not in migrated["external_tools"]
        assert migrated["external_tools"]["repak"] == "/path/to/repak"
        assert migrated["external_tools"]["umodel"] == "/path/to/umodel"
        assert migrated["external_tools"]["uassetgui"] == "/path/to/uassetgui"

        # Verify the migrated config can be loaded
        settings = AppSettings(**migrated)
        assert settings.config_version == 8
        assert not hasattr(settings.external_tools, "uesave")

    def test_migrate_v6_to_v7_no_external_tools(self) -> None:
        """Test migration from v6 works even if external_tools is missing."""
        v6_config = {
            "config_version": 6,
        }

        migrated = ConfigMigrator.apply_migrations(v6_config)

        assert migrated["config_version"] == 8
        # Should work without error
        settings = AppSettings(**migrated)
        assert settings.config_version == 8

    def test_migrate_v7_to_v8_drops_ocr_and_template_sections(self) -> None:
        """Test migration from v7 removes ocr/templates sections and scanner extras."""
        v7_config = {
            "config_version": 7,
            "ocr": {"height": 2160, "box_width": 84},
            "templates": {"some_field": "value"},
            "scanner": {
                "database_path": None,
                "early_exit_threshold": 0.95,
                "custom_model": "renner_numbers",
                "tessdata_path": "./tessdata",
                "max_ncc_candidates": 25,
                "phash_threshold": 12,
                "ncc_tiebreaker_threshold": 0.0015,
            },
        }

        migrated = ConfigMigrator.apply_migrations(v7_config)

        assert migrated["config_version"] == 8
        # Top-level sections removed
        assert "ocr" not in migrated
        assert "templates" not in migrated
        # Scanner extras removed, valid fields preserved
        assert "custom_model" not in migrated["scanner"]
        assert "tessdata_path" not in migrated["scanner"]
        assert "max_ncc_candidates" not in migrated["scanner"]
        assert "phash_threshold" not in migrated["scanner"]
        assert "ncc_tiebreaker_threshold" not in migrated["scanner"]
        assert migrated["scanner"]["early_exit_threshold"] == 0.95

        # Verify the migrated config can be loaded
        settings = AppSettings(**migrated)
        assert settings.config_version == 8
        assert not hasattr(settings, "ocr")
        assert not hasattr(settings, "templates")
        assert settings.scanner.early_exit_threshold == 0.95

    def test_migrate_v7_to_v8_no_scanner_section(self) -> None:
        """Test migration from v7 works even if scanner section is missing."""
        v7_config = {
            "config_version": 7,
            "ocr": {"height": 2160},
        }

        migrated = ConfigMigrator.apply_migrations(v7_config)

        assert migrated["config_version"] == 8
        assert "ocr" not in migrated
        settings = AppSettings(**migrated)
        assert settings.config_version == 8


class TestAppSettings:
    """Test cases for main AppSettings class."""

    def test_app_settings_defaults(self) -> None:
        """Test default app settings."""
        settings = AppSettings()

        assert isinstance(settings.logging, LoggingSettings)
        assert isinstance(settings.output, OutputSettings)
        assert isinstance(settings.stockpile_types, StockpileTypesSettings)
        # scanner field should exist
        assert hasattr(settings, "scanner")

    def test_app_settings_custom_values(self) -> None:
        """Test app settings with custom values."""
        import warnings

        # Mock settings sources to avoid loading from ~/.fs_config
        def mock_settings_customise_sources(
            cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            *args: PydanticBaseSettingsSource,
            **kwargs: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            # Only use init_settings (passed kwargs), ignore file and env
            return (init_settings,)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Config key.*json_file.*will be ignored")
            with patch.object(
                AppSettings, "settings_customise_sources", mock_settings_customise_sources
            ):
                settings = AppSettings(
                    logging=LoggingSettings(log_level="DEBUG", rotate_logs=True),
                    scanner=ScannerSettings(template_cache_size=8),
                    output=OutputSettings(
                        handlers=[
                            OutputHandlerConfig(
                                name="File Output",
                                handler=FileHandlerSettings(path="custom.txt"),
                            )
                        ]
                    ),
                )

        assert settings.logging.log_level == "DEBUG"
        assert settings.logging.rotate_logs is True
        assert settings.scanner.template_cache_size == 8
        assert len(settings.output.handlers) == 1
        handler = settings.output.handlers[0].handler
        assert isinstance(handler, FileHandlerSettings)
        assert handler.path == "custom.txt"

    def test_app_settings_nested_configuration(self) -> None:
        """Test app settings with nested configuration."""
        settings = AppSettings(
            logging=LoggingSettings(log_level="DEBUG", rotate_logs=True),
            scanner=ScannerSettings(template_cache_size=8),
            stockpile_types=StockpileTypesSettings(seaport=["seapon"]),
        )

        assert settings.logging.log_level == "DEBUG"
        assert settings.logging.rotate_logs is True
        assert settings.scanner.template_cache_size == 8
        assert settings.stockpile_types.seaport == ["seapon"]

    def test_app_settings_from_environment_variables(self) -> None:
        """Test loading app settings from environment variables."""
        import warnings

        # Only test non-output env vars since the output structure is now handlers-based
        env_vars = {
            "FS_SCANNER__TEMPLATE_CACHE_SIZE": "8",
            "FS_LOGGING__LOG_LEVEL": "WARNING",
        }

        # Mock settings sources to use env but not file
        def mock_settings_customise_sources(
            cls: type[BaseSettings],
            init_settings: PydanticBaseSettingsSource,
            env_settings: PydanticBaseSettingsSource,
            *args: PydanticBaseSettingsSource,
            **kwargs: PydanticBaseSettingsSource,
        ) -> tuple[PydanticBaseSettingsSource, ...]:
            # Use env_settings and init_settings, but not file
            return (init_settings, env_settings)

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Config key.*json_file.*will be ignored")
            with patch.dict(os.environ, env_vars, clear=True):
                with patch.object(
                    AppSettings, "settings_customise_sources", mock_settings_customise_sources
                ):
                    settings = AppSettings()

                    assert settings.scanner.template_cache_size == 8
                    assert settings.logging.log_level == "WARNING"


class TestGetSettings:
    """Test cases for get_settings function."""

    def test_get_settings_singleton(self) -> None:
        """Test that get_settings returns the same instance."""
        settings1 = get_settings()
        settings2 = get_settings()

        assert settings1 is settings2

    def test_get_settings_caching(self) -> None:
        """Test that get_settings uses LRU cache."""
        # Clear the cache first
        get_settings.cache_clear()

        # Call multiple times and verify same instance
        settings1 = get_settings()
        settings2 = get_settings()
        settings3 = get_settings()

        assert settings1 is settings2 is settings3

        # Check cache info
        cache_info = get_settings.cache_info()
        assert cache_info.hits >= 2
        assert cache_info.misses == 1

    def test_get_settings_cache_clear(self) -> None:
        """Test clearing the settings cache."""
        settings1 = get_settings()
        get_settings.cache_clear()
        settings2 = get_settings()

        # After clearing cache, we should get a new instance
        assert settings1 is not settings2
        assert isinstance(settings1, type(settings2))

    def test_get_settings_returns_app_settings(self) -> None:
        """Test that get_settings returns AppSettings instance."""
        settings = get_settings()
        assert isinstance(settings, AppSettings)
        assert hasattr(settings, "logging")
        assert hasattr(settings, "scanner")
        assert hasattr(settings, "output")
        assert hasattr(settings, "stockpile_types")


class TestReloadSettings:
    """Test cases for reload_settings function."""

    def test_reload_settings_clears_cache(self) -> None:
        """Test that reload_settings clears the cache and returns new settings."""
        settings1 = get_settings()
        settings2 = reload_settings()

        # After reload, we should get a new instance
        assert settings1 is not settings2

    def test_reload_settings_returns_app_settings(self) -> None:
        """Test that reload_settings returns AppSettings instance."""
        settings = reload_settings()
        assert isinstance(settings, AppSettings)

    def test_reload_settings_updates_get_settings_cache(self) -> None:
        """Test that reload_settings updates the cache used by get_settings."""
        get_settings.cache_clear()

        settings1 = get_settings()
        settings2 = reload_settings()
        settings3 = get_settings()

        # After reload, get_settings should return the new instance
        assert settings1 is not settings2
        assert settings2 is settings3


class TestSheetsHandlerSettings:
    """Test cases for SheetsHandlerSettings."""

    def test_sheets_handler_custom_values(self) -> None:
        """Test sheets handler with custom values."""
        settings = SheetsHandlerSettings(
            creds_path="C:/example/creds.json",
            spreadsheet_url="https://docs.google.com/spreadsheets/d/12345/edit?gid=0#gid=0",
            sheet_id="Sheet1",
        )
        assert settings.creds_path == "C:/example/creds.json"
        assert (
            settings.spreadsheet_url
            == "https://docs.google.com/spreadsheets/d/12345/edit?gid=0#gid=0"
        )
        assert settings.sheet_id == "Sheet1"
