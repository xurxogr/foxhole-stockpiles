"""Application settings."""

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from foxhole_stockpiles.core.settings.config_migrator import ConfigMigrator
from foxhole_stockpiles.core.settings.json_settings_source import Utf8JsonConfigSettingsSource
from foxhole_stockpiles.core.settings.sections import (
    DatabaseBuilderSettings,
    ExternalToolsSettings,
    GUISettings,
    LoggingSettings,
    NotificationsSettings,
    OutputSettings,
    SavProcessingSettings,
    ScannerSettings,
)


class AppSettings(BaseSettings):
    """Application Settings."""

    config_version: int = Field(
        default=ConfigMigrator.CURRENT_VERSION,
        description="Configuration format version for migration purposes",
    )
    external_tools: ExternalToolsSettings = Field(
        description="External tools settings", default_factory=ExternalToolsSettings
    )
    logging: LoggingSettings = Field(
        description="Logging settings", default_factory=LoggingSettings
    )
    output: OutputSettings = Field(description="Output settings", default_factory=OutputSettings)
    scanner: ScannerSettings = Field(
        description="Stockpile scanner settings", default_factory=ScannerSettings
    )
    database_builder: DatabaseBuilderSettings = Field(
        description="Database builder settings", default_factory=DatabaseBuilderSettings
    )
    notifications: NotificationsSettings = Field(
        description="Notifications settings", default_factory=NotificationsSettings
    )
    gui: GUISettings = Field(description="GUI settings", default_factory=GUISettings)
    sav_processing: SavProcessingSettings = Field(
        description="SAV file processing settings", default_factory=SavProcessingSettings
    )
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        env_prefix="FS_",
        json_file=str(Path("~/.fs_config").expanduser()),
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_config(cls, data: Any) -> Any:
        """Migrate configuration from older versions to current version.

        Args:
            data: Raw configuration data

        Returns:
            Migrated configuration data
        """
        if not isinstance(data, dict):
            return data

        return ConfigMigrator.apply_migrations(data)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customise settings sources to include JSON config file.

        Args:
            settings_cls: The settings class
            init_settings: Init settings source
            env_settings: Environment settings source
            dotenv_settings: Dotenv settings source
            file_secret_settings: File secret settings source

        Returns:
            tuple: Settings sources in priority order (highest to lowest)
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            Utf8JsonConfigSettingsSource(settings_cls),
            file_secret_settings,
        )
