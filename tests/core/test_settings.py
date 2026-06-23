"""Tests for configuration settings module.

This module contains comprehensive tests for the settings system,
including validation, defaults, custom values, environment variable
handling, and file-based configuration loading.
"""

import pytest
from pydantic import ValidationError

from foxhole_stockpiles.core.settings import AppSettings, get_settings, reload_settings
from foxhole_stockpiles.core.settings.config_migrator import ConfigMigrator
from foxhole_stockpiles.core.settings.sections import SheetsHandlerSettings
from foxhole_stockpiles.core.settings.sections.logging import LoggingSettings
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
        assert migrated["config_version"] == 13
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
        assert settings.config_version == 13
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
        assert migrated["config_version"] == 13
        assert len(migrated["output"]["handlers"]) == 1
        handler_config = migrated["output"]["handlers"][0]
        assert handler_config["handler"]["type"] == "file"
        assert handler_config["handler"]["path"] == "/custom/output.json"

        # Verify the migrated config can be loaded
        settings = AppSettings(**migrated)
        assert settings.config_version == 13
        assert len(settings.output.handlers) == 1
        handler = settings.output.handlers[0].handler
        assert isinstance(handler, FileHandlerSettings)
        assert handler.path == "/custom/output.json"

    def test_default_config_is_v7(self) -> None:
        """Test that default config is version 7."""
        settings = AppSettings()
        assert settings.config_version == 13

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
        assert migrated["config_version"] == 13
        # Verify deprecated fields are removed
        assert "confidence_threshold" not in migrated["scanner"]
        assert "confidence_by_resolution" not in migrated["scanner"]
        # Verify valid fields remain
        assert migrated["scanner"]["early_exit_threshold"] == 0.95

        # Verify the migrated config can be loaded
        settings = AppSettings(**migrated)
        assert settings.config_version == 13
        assert settings.scanner.early_exit_threshold == 0.95

    def test_migrate_config_with_non_dict_data(self) -> None:
        """Test that migration guard clause returns non-dict data unchanged."""
        # The method has a guard clause for non-dict data (defensive programming)
        # In practice, this should never happen since validators check before calling
        result = ConfigMigrator.apply_migrations(None)  # type: ignore[arg-type]
        assert result is None

    def test_migrate_v3_with_stockpile_types_drops_section(self) -> None:
        """A v3 config with stockpile_types migrates cleanly to v11, dropping it.

        The stockpile_types section (and the intermediate v3->v4/v5->v6 alias
        migrations) is removed at v11, so it must not survive a full migration.
        """
        v3_config = {
            "config_version": 3,
            "stockpile_types": {
                "seaport": ["custom_alias"],
                "undefined": ["some_value"],
                "bunker_base": ["MyCustomBase"],
            },
        }

        migrated = ConfigMigrator.apply_migrations(v3_config)
        assert migrated["config_version"] == 13
        assert "stockpile_types" not in migrated

        settings = AppSettings(**v3_config)  # type: ignore[arg-type]
        assert settings.config_version == 13
        assert not hasattr(settings, "stockpile_types")

    def test_migrate_v11_to_v12_drops_notifications(self) -> None:
        """A v11 config with a notifications section migrates to v12, dropping it.

        The notifications stack was dead code (never wired into the scan flow),
        so the section is removed and must not survive a full migration.
        """
        v11_config = {
            "config_version": 11,
            "notifications": {
                "enabled": True,
                "notifiers": [{"type": "discord", "webhook_url": "https://example/x"}],
            },
        }

        migrated = ConfigMigrator.apply_migrations(v11_config)
        assert migrated["config_version"] == 13
        assert "notifications" not in migrated

        settings = AppSettings(**v11_config)  # type: ignore[arg-type]
        assert settings.config_version == 13
        assert not hasattr(settings, "notifications")

    def test_migrate_v12_to_v13_drops_config_level(self) -> None:
        """A v12 config with gui.config_level migrates to v13, dropping it.

        The basic/advanced/developer config-level system was removed (it only
        guarded OCR/template internals that now live in fs-ocr/fs-tools), so the
        stored ``gui.config_level`` must not survive a full migration.
        """
        v12_config = {
            "config_version": 12,
            "gui": {
                "config_level": "developer",
                "minimize_to_tray": True,
                "language": "en",
            },
        }

        migrated = ConfigMigrator.apply_migrations(v12_config)
        assert migrated["config_version"] == 13
        assert "config_level" not in migrated["gui"]
        assert migrated["gui"]["minimize_to_tray"] is True

        settings = AppSettings(**v12_config)  # type: ignore[arg-type]
        assert settings.config_version == 13
        assert not hasattr(settings.gui, "config_level")

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

        assert migrated["config_version"] == 13
        assert "uesave" not in migrated["external_tools"]
        assert migrated["external_tools"]["repak"] == "/path/to/repak"
        assert migrated["external_tools"]["umodel"] == "/path/to/umodel"
        assert migrated["external_tools"]["uassetgui"] == "/path/to/uassetgui"

        # Verify the migrated config can be loaded
        settings = AppSettings(**migrated)
        assert settings.config_version == 13
        assert not hasattr(settings.external_tools, "uesave")

    def test_migrate_v6_to_v7_no_external_tools(self) -> None:
        """Test migration from v6 works even if external_tools is missing."""
        v6_config = {
            "config_version": 6,
        }

        migrated = ConfigMigrator.apply_migrations(v6_config)

        assert migrated["config_version"] == 13
        # Should work without error
        settings = AppSettings(**migrated)
        assert settings.config_version == 13

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

        assert migrated["config_version"] == 13
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
        assert settings.config_version == 13
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

        assert migrated["config_version"] == 13
        assert "ocr" not in migrated
        settings = AppSettings(**migrated)
        assert settings.config_version == 13

    def test_migrate_v8_to_v9_drops_web_icon_mod(self) -> None:
        """Test migration from v8 removes api_server.web_icon_mod."""
        v8_config = {
            "config_version": 8,
            "api_server": {
                "host": "0.0.0.0",
                "port": 8000,
                "web_icon_mod": "airborne",
            },
        }

        migrated = ConfigMigrator.apply_migrations(v8_config)

        # The full migration chain ends at v10, which drops the api_server
        # section entirely (the runtime no longer hosts a REST server).
        assert migrated["config_version"] == 13
        assert "api_server" not in migrated
        assert "api_auth" not in migrated

        # Verify the migrated config can be loaded (model forbids extra fields)
        settings = AppSettings(**migrated)
        assert settings.config_version == 13
        assert not hasattr(settings, "api_server")

    def test_migrate_v9_to_v10_drops_api_sections(self) -> None:
        """Test migration from v9 removes the api_server and api_auth sections."""
        v9_config = {
            "config_version": 9,
            "api_server": {"host": "0.0.0.0", "port": 8000},
            "api_auth": {"auth_type": "bearer", "auth_token": "secret"},
            "scanner": {"database_path": "db.h5"},
        }

        migrated = ConfigMigrator.apply_migrations(v9_config)

        assert migrated["config_version"] == 13
        assert "api_server" not in migrated
        assert "api_auth" not in migrated
        assert migrated["scanner"]["database_path"] == "db.h5"

        settings = AppSettings(**migrated)
        assert settings.config_version == 13
        assert settings.scanner.capture_key is None

    def test_migrate_v8_to_v9_no_api_server_section(self) -> None:
        """Test migration from v8 works even if api_server section is missing."""
        v8_config = {"config_version": 8}

        migrated = ConfigMigrator.apply_migrations(v8_config)

        assert migrated["config_version"] == 13
        settings = AppSettings(**migrated)
        assert settings.config_version == 13

    def test_migrate_v10_to_v11_drops_stockpile_types_and_dead_scanner_fields(self) -> None:
        """Test migration from v10 removes stockpile_types and dead scanner knobs."""
        v10_config = {
            "config_version": 10,
            "stockpile_types": {"keep": ["MyKeep"], "seaport": ["MyPort"]},
            "scanner": {
                "database_path": "db.h5",
                "confidence_gap": 0.2,
                "early_exit_threshold": 0.95,
                "template_cache_size": 8,
                "debug_mode": True,
                "extract_icons": True,
                "screenshots_folder": "shots",
            },
        }

        migrated = ConfigMigrator.apply_migrations(v10_config)

        assert migrated["config_version"] == 13
        assert "stockpile_types" not in migrated
        # Live scanner fields preserved (early_exit_threshold -> fs_tools;
        # screenshots_folder -> capture saving).
        assert migrated["scanner"]["database_path"] == "db.h5"
        assert migrated["scanner"]["confidence_gap"] == 0.2
        assert migrated["scanner"]["early_exit_threshold"] == 0.95
        assert migrated["scanner"]["screenshots_folder"] == "shots"
        # Dead scanner fields dropped
        for dead in ("template_cache_size", "debug_mode", "extract_icons"):
            assert dead not in migrated["scanner"]

        settings = AppSettings(**migrated)
        assert settings.config_version == 13
        assert not hasattr(settings, "stockpile_types")
        assert settings.scanner.confidence_gap == 0.2
        assert settings.scanner.early_exit_threshold == 0.95
        assert settings.scanner.screenshots_folder == "shots"


class TestAppSettings:
    """Test cases for main AppSettings class."""

    def test_app_settings_defaults(self) -> None:
        """Test default app settings."""
        settings = AppSettings()

        assert isinstance(settings.logging, LoggingSettings)
        assert isinstance(settings.output, OutputSettings)
        # scanner field should exist
        assert hasattr(settings, "scanner")

    def test_app_settings_custom_values(self) -> None:
        """Test app settings with custom values."""
        settings = AppSettings(
            logging=LoggingSettings(log_level="DEBUG", rotate_logs=True),
            scanner=ScannerSettings(confidence_gap=0.15),
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
        assert settings.scanner.confidence_gap == 0.15
        assert len(settings.output.handlers) == 1
        handler = settings.output.handlers[0].handler
        assert isinstance(handler, FileHandlerSettings)
        assert handler.path == "custom.txt"

    def test_app_settings_nested_configuration(self) -> None:
        """Test app settings with nested configuration."""
        settings = AppSettings(
            logging=LoggingSettings(log_level="DEBUG", rotate_logs=True),
            scanner=ScannerSettings(confidence_gap=0.2, capture_key="F9"),
        )

        assert settings.logging.log_level == "DEBUG"
        assert settings.logging.rotate_logs is True
        assert settings.scanner.confidence_gap == 0.2
        assert settings.scanner.capture_key == "F9"

    def test_app_settings_from_environment_variables(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading app settings from environment variables.

        Args:
            monkeypatch (pytest.MonkeyPatch): Fixture used to set FS_* env vars.
        """
        # Only test non-output env vars since the output structure is now handlers-based.
        # The isolate_app_settings fixture already disables the JSON config file, so the
        # env source is the only one contributing here.
        monkeypatch.setenv("FS_SCANNER__CONFIDENCE_GAP", "0.3")
        monkeypatch.setenv("FS_LOGGING__LOG_LEVEL", "WARNING")

        settings = AppSettings()

        assert settings.scanner.confidence_gap == 0.3
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
        assert not hasattr(settings, "stockpile_types")


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
