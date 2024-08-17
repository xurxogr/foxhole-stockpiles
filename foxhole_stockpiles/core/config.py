import configparser
from functools import lru_cache
import json
import os
import types
from typing import get_args, get_origin

from pydantic import Field, ConfigDict, model_validator
from pydantic_settings import BaseSettings

from foxhole_stockpiles.core.env_interpolation import EnvInterpolation


def read_ini_file(file_path: str) -> dict[str, dict[str, str]]:
    """
    Read an INI file and return it as dictionary where the keys are sections and the values are dictionaries of key-value pairs.

    Args:
        file_path (str): The path to the INI file

    Returns:
        dict[str, dict[str, str]]: The INI file as a dictionary
    """
    config = configparser.ConfigParser(interpolation=EnvInterpolation())
    config.read(file_path)
    return {section: dict(config[section]) for section in config.sections()}

class SectionSettings(BaseSettings):
    model_config = ConfigDict(extra='ignore')

    @classmethod
    def from_dict(cls, data: dict):
        """
        Convert a dictionary to a class instance.

        Args:
            data (dict): The dictionary to convert
        """
        converted_data = {}
        for attr_name, attr_type in cls.__annotations__.items():
            if attr_name not in data:
                continue

            origin = get_origin(attr_type)
            if isinstance(attr_type, types.UnionType):
                args = get_args(attr_type)
                attr_type = next((arg for arg in args if arg is not type(None)), args[0])
            elif origin:
                attr_type = origin

            try:
                # list or dict
                if attr_type in [dict, list]:
                    converted_data[attr_name] = json.loads(data[attr_name]) if data[attr_name] else None
                # primitive types
                elif attr_type in [str, int, float, bool]:
                    converted_data[attr_name] = attr_type(data[attr_name])
                # anything else
                else:
                    converted_data[attr_name] = data[attr_name]
            except ValueError:
                converted_data[attr_name] = data[attr_name]

        return cls(**converted_data)

###### Sections of the INI
class LoggingSettings(SectionSettings):
    loggers: dict | None = Field(description="Loggers and their levels", default=None)
    level: str | None = Field(description="Logging level", default="INFO")
    format: str | None = Field(description="Logging format", default="[%(asctime)s] %(levelname)s [%(name)s] %(message)s")
    date_format: str | None = Field(description="Logging date format", default="%Y-%m-%d %H:%M:%S")
    file: bool | None = Field(description="Log to file", default=False)

class OCRSettings(SectionSettings):
    item_min_w: int = Field(description="Minimum width of an OCR item", gt=0)
    item_max_w: int = Field(description="Maximum width of an OCR item", gt=0)
    item_min_ratio: float = Field(description="Minimum width-height ratio of an OCR item", gt=1)
    item_max_ratio: float = Field(description="Maximum width-height ratio of an OCR item", gt=1)
    item_spacing_height: int = Field(description="Spacing between OCR items in height", gt=0)
    item_spacing_width: int = Field(description="Spacing between OCR items in width", gt=0)

    @model_validator(mode="after")
    def validate(self):
        if self.item_min_w >= self.item_max_w:
            raise ValueError("item_min_w must be less than item_max_w")
        if self.item_min_ratio >= self.item_max_ratio:
            raise ValueError("item_min_ratio must be less than item_max_ratio")
        
        return self

class ModelsSettings(SectionSettings):
    icons_path: str = Field(description="Path to the icons model")
    quantities_path: str = Field(description="Path to the quantities model")
    catalog_items_path: str = Field(description="Path to the catalog items")

class BackendSettings(SectionSettings):
    url: str = Field(description="Backend API URL")

class DeveloperSettings(SectionSettings):
    detect_quantities: bool = Field(description="Detect quantities", default=True)
    detect_icons: bool = Field(description="Detect icons", default=True)
    detect_stockpile_type: bool = Field(description="Detect stockpile type", default=True)
    detect_stockpile_name: bool = Field(description="Detect stockpile name", default=True)
    draw_rectangles: bool = Field(description="Draw rectangles", default=False)
    save_images: bool = Field(description="Save images", default=False)
    backup_path: str = Field(description="Backup path", default="screenshots")

class StockpileTypesSettings(SectionSettings):
    encampment: list[str] = Field(description="Encampment values", min_items=1)
    keep: list[str] = Field(description="Keep values", min_items=1)
    safe_house: list[str] = Field(description="Safe House values", min_items=1)
    relic_base: list[str] = Field(description="Relic Base values", min_items=1)
    bunker_base: list[str] = Field(description="Bunker Base values", min_items=1)
    border_base: list[str] = Field(description="Border Base values", min_items=1)
    town_base: list[str] = Field(description="Town Base values", min_items=1)
    bms_longhook: list[str] = Field(description="BMS - Longhook values", min_items=1)
    storage_depot: list[str] = Field(description="Storage Depot values", min_items=1)
    seaport: list[str] = Field(description="Seaport values", min_items=1)
    undefined: list[str] = Field(description="Undefined values", min_items=1)

# Sections. End

class AppSettings(BaseSettings):
    logging: LoggingSettings | None = None
    ocr: OCRSettings | None = None
    models: ModelsSettings | None = None
    backend: BackendSettings | None = None
    developer: DeveloperSettings | None = None
    stockpile_types: StockpileTypesSettings | None = None

    @classmethod
    def from_ini(cls, file_name: str):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(script_dir, file_name)

        ini_data = read_ini_file(file_path)

        settings_data = {}
        for attr_name, attr_type in cls.__annotations__.items():
            attr_name_upper = attr_name.upper()
            if attr_name_upper in ini_data:
                section_class = attr_type.__args__[0]  # Get the type from Optional
                section_data = ini_data[attr_name_upper]
                settings_data[attr_name] = section_class.from_dict(section_data)

        return cls(**settings_data)

@lru_cache()
def get_settings():
    return AppSettings().from_ini("app.ini")

settings = get_settings()
