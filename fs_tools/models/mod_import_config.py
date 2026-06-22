"""Configuration model for mod import operations."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from fs_tools.core.settings.sections.templates import TemplateSettings


class ModImportConfig(BaseModel):
    """Configuration for mod import operation."""

    mod_pak_files: list[str] = Field(description="List of mod PAK file paths to extract icons from")
    mod_name: str = Field(description="Name of the mod (used for organizing templates)")
    extract_dir: Path | None = Field(
        default=None,
        description="Directory for extracted assets. If extract_only=True, assets are saved here. "
        "Otherwise, assets are read from here (skipping extraction).",
    )
    extract_only: bool = Field(
        default=False,
        description="If True, only extract assets to extract_dir and stop. "
        "Does not generate templates or build database.",
    )
    catalog_path: Path = Field(description="Path to catalog.json file")
    overwrite: bool = Field(
        default=False, description="Whether to overwrite existing templates for this mod"
    )
    vanilla_pak_file: str | None = Field(
        default=None, description="Optional vanilla PAK file for shared dependencies"
    )
    extractor_tool: Path | None = Field(
        default=None, description="Path to repak.exe (PAK extractor)"
    )
    converter_tool: Path | None = Field(
        default=None, description="Path to umodel.exe (UAsset converter)"
    )
    database_path: Path | None = Field(
        default=None, description="Path to output HDF5 database file"
    )
    target_resolutions: list[str] | None = Field(
        default=None, description="List of resolutions to generate (None = all)"
    )
    template_settings: TemplateSettings | None = Field(
        default=None, description="Template generation settings"
    )
    database_workers: int | None = Field(
        default=None,
        description="Number of workers for database building. Set to 1 to disable multiprocessing "
        "(recommended for GUI to avoid freezing on Windows).",
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
        arbitrary_types_allowed=True,
    )
