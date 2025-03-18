"""Configuration module for the app."""

from functools import lru_cache
from typing import Any, Self, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# Sections of the INI (alphabetical order) - Start
class BackendSettings(BaseModel):
    """Settings for the backend API."""

    url: str | None = Field(description="Backend API URL", default=None)

    model_config = ConfigDict(
        extra="ignore",
        title="Backend settings",
        json_schema_extra={"example": {"url": "http://localhost:8000"}},
    )


class DeveloperSettings(BaseModel):
    """Settings for development."""

    save_image: bool = Field(description="Save image", default=False)
    save_name_image: bool = Field(description="Save detected stockpile name", default=False)
    save_type_image: bool = Field(description="Save detected stockpile type", default=False)
    backup_path: str = Field(description="Backup path", default="screenshots")

    icons_model_threshold_score: float = Field(
        description="Threshold score for the icons model", ge=0, default=0
    )
    save_icons_image: bool = Field(description="Save detected icons", default=False)
    icons_save_path: str = Field(
        description="Path to save the detected icons", default="screenshots/icons"
    )

    model_config = ConfigDict(
        extra="ignore",
        title="Developer settings",
        json_schema_extra={
            "example": {
                "save_image": False,
                "save_name_image": False,
                "save_type_image": False,
                "backup_path": "screenshots",
                "icons_model_threshold_score": 0,
                "save_icons_image": False,
                "icons_save_path": "screenshots/icons",
            }
        },
    )


class LoggingSettings(BaseModel):
    """Settings for logging."""

    loggers: dict = Field(description="Loggers and their levels", default={})
    log_level: str = Field(description="Logging level", default="INFO")
    log_format: str = Field(
        description="Logging format",
        default="[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
    )
    date_format: str = Field(description="Logging date format", default="%Y-%m-%d %H:%M:%S")

    model_config = ConfigDict(
        extra="ignore",
        title="Logging settings",
        json_schema_extra={
            "example": {
                "loggers": {"foxhole_stockpiles": "DEBUG", "uvicorn": "INFO"},
                "log_level": "INFO",
                "log_format": "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
                "date_format": "%Y-%m-%d %H:%M:%S",
            }
        },
    )


class ModelsSettings(BaseModel):
    """Settings for the keras models."""

    icons_path: str = Field(description="Path to the icons model", default="models/icons_model")

    model_config = ConfigDict(
        extra="ignore",
        title="Models settings",
        json_schema_extra={
            "example": {
                "icons_path": "models/icons_model",
            }
        },
    )


class OCRSettings(BaseModel):
    """Settings for the OCR."""

    base_height: int = Field(description="Base Height for the scaling", gt=0, default=1440)
    item_width: int = Field(description="Width of the quantity square", gt=0, default=56)
    item_height: int = Field(description="Height of the quantity square", gt=0, default=43)
    item_spacing_height: int = Field(
        description="Spacing between quantity squares", gt=0, default=9
    )
    item_spacing_width: int = Field(
        description="Spacing between icon and quantity square", gt=0, default=16
    )
    text_recognition_scale: float = Field(
        description="Scale for text recognition", gt=0, default=16
    )
    quantities_padding: int = Field(
        description="Padding for the quantities image creation", gt=0, default=15
    )

    model_config = ConfigDict(
        extra="ignore",
        title="OCR settings",
        json_schema_extra={
            "example": {
                "base_resolution": 1440,
                "item_width": 56,
                "item_height": 43,
                "item_spacing_height": 9,
                "item_spacing_width": 16,
                "text_recognition_scale": 16,
                "quantities_padding": 15,
            }
        },
    )


class StockpileTypesSettings(BaseModel):
    """Settings for the stockpile types."""

    encampment: list[str] = Field(
        description="Encampment values",
        default=[
            "Encampment",
            "Campement",
            "Feldlager",
            "Acampamento",
            "Лагерь",
            "营地",
        ],
    )
    keep: list[str] = Field(
        description="Keep values",
        default=[
            "Keep",
            "Place Forte",
            "Wehrturm",
            "Torreão",
            "Крепость",
            "要塞",
        ],
    )
    safe_house: list[str] = Field(
        description="Safe House values",
        default=[
            "Safe House",
            "Planque",
            "Unterschlupf",
            "Casa Fortificada",
            "Yбeжищe",
            "安全屋",
        ],
    )
    relic_base: list[str] = Field(
        description="Relic Base values",
        default=[
            "Relic Base",
            "Base Relique",
            "Reliktbasis",
            "Base Relíquia",
            "Peликтoвая база",
            "遗迹基地",
        ],
    )
    bunker_base: list[str] = Field(
        description="Bunker Base values",
        default=[
            "Bunker Base",
            "Base Bunker",
            "Bunkerbasis",
            "Centro do Bunker",
            "Base de Bunker",
            "Base de Casamata",
            "Бункерная база",
            "Бункерная База",
            "地堡基地",
        ],
    )
    border_base: list[str] = Field(
        description="Border Base values",
        default=[
            "Border Base",
            "Base Frontalière",
            "Grenzbasis",
            "Base Fronteiriça",
            "Пограничная База",
            "边境基地",
        ],
    )
    town_base: list[str] = Field(
        description="Town Base values",
        default=[
            "Town Base",
            "Quartier Général",
            "Stadtkernbasis",
            "Base de Cidade",
            "Ратуша",
            "城镇基地",
        ],
    )
    bms_longhook: list[str] = Field(
        description="BMS - Longhook values",
        default=["BMS - Longhook"],
    )
    storage_depot: list[str] = Field(
        description="Storage Depot values",
        default=[
            "Storage Depot",
            "Dépôt",
            "Lagerdepot",
            "Depósito",
            "Складское Помещение",
            "仓库",
        ],
    )
    seaport: list[str] = Field(
        description="Seaport values",
        default=[
            "Seaport",
            "Port",
            "Seehafen",
            "Porto",
            "Морской порт",
            "海港",
        ],
    )
    undefined: list[str] = Field(
        description="Undefined values",
        default=["Undefined"],
    )

    model_config = ConfigDict(
        extra="ignore",
        title="Stockpile types settings",
        json_schema_extra={
            "example": {
                "encampment": [
                    "Encampment",
                    "Campement",
                    "Feldlager",
                    "Acampamento",
                    "Лагерь",
                    "营地",
                ],
                "keep": [
                    "Keep",
                    "Place Forte",
                    "Wehrturm",
                    "Torreão",
                    "Крепость",
                    "要塞",
                ],
                "safe_house": [
                    "Safe House",
                    "Planque",
                    "Unterschlupf",
                    "Casa Fortificada",
                    "Yбeжищe",
                    "安全屋",
                ],
                "relic_base": [
                    "Relic Base",
                    "Base Relique",
                    "Reliktbasis",
                    "Base Relíquia",
                    "Peликтoвая база",
                    "遗迹基地",
                ],
                "bunker_base": [
                    "Bunker Base",
                    "Base Bunker",
                    "Bunkerbasis",
                    "Centro do Bunker",
                    "Base de Bunker",
                    "Base de Casamata",
                    "Бункерная база",
                    "Бункерная База",
                    "地堡基地",
                ],
                "border_base": [
                    "Border Base",
                    "Base Frontalière",
                    "Grenzbasis",
                    "Base Fronteiriça",
                    "Пограничная База",
                    "边境基地",
                ],
                "town_base": [
                    "Town Base",
                    "Quartier Général",
                    "Stadtkernbasis",
                    "Base de Cidade",
                    "Ратуша",
                    "城镇基地",
                ],
                "bms_longhook": ["BMS - Longhook"],
                "storage_depot": [
                    "Storage Depot",
                    "Dépôt",
                    "Lagerdepot",
                    "Depósito",
                    "Складское Помещение",
                    "仓库",
                ],
                "seaport": [
                    "Seaport",
                    "Port",
                    "Seehafen",
                    "Porto",
                    "Морской порт",
                    "海港",
                ],
                "undefined": ["Undefined"],
            }
        },
    )


# Sections. End


class AppSettings(BaseModel):
    """Application Settings."""

    logging: LoggingSettings
    ocr: OCRSettings
    models: ModelsSettings
    backend: BackendSettings
    developer: DeveloperSettings
    stockpile_types: StockpileTypesSettings

    model_config = SettingsConfigDict(env_nested_delimiter="__")


class _AppSettings(BaseSettings):
    """Application Settings.

    This Model exists to allow to have sections without environment variables.
    The model_validator will dynamically initialize any section that is None.

    if a field was defined as `sample_field: ModelClass` and no environment variables were set with
    prefix SAMPLE_FIELD__, the model would have failed with a pydantic.ValidationError.

    To prevent the code hint types from having sections that could be None, a new model copy from
    this one is created with the same fields but with a different base class.
    """

    logging: LoggingSettings | None = None
    ocr: OCRSettings | None = None
    models: ModelsSettings | None = None
    backend: BackendSettings | None = None
    developer: DeveloperSettings | None = None
    stockpile_types: StockpileTypesSettings | None = None

    model_config = SettingsConfigDict(env_nested_delimiter="__")

    @model_validator(mode="after")
    def validate_model(self) -> Self:
        """Validate model.

        Returns:
            Self, the validated model
        """
        # Dynamically initialize fields that are None
        for field_name, field_value in self.model_dump().items():
            if field_value is not None:
                continue

            # Extract the non-None type from the Union
            field_type = self.model_fields[field_name].annotation
            non_none_type = self._extract_non_none_type(field_type)
            setattr(self, field_name, non_none_type())

        return self

    @staticmethod
    def _extract_non_none_type(field_type: type[Any] | None) -> type:
        """Extract the non-None type from a Union type.

        Args:
            field_type (type[Any] | None): The field type

        Returns:
            type: The non-None type

        Raises:
            ValueError: If no non-None type is found in the Union
        """
        # Get all types in the Union
        for t in get_args(field_type):
            if t is not type(None):
                return t

        raise ValueError("No non-None type found in the Union")


@lru_cache()
def get_settings() -> AppSettings:
    """Get the settings.

    Returns:
        AppSettings: The settings
    """
    # Load the settings from the environment with the internal model
    app_settings = _AppSettings()

    # Return the settings as the AppSettings model where the sections are not None
    return AppSettings(**app_settings.model_dump())
