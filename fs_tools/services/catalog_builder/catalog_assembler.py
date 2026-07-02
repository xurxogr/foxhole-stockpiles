"""Catalog assembler for building item catalogs from game data.

This module orchestrates the catalog building process using BlueprintParser,
DataTableLookup, and LocalizationLookup to produce a complete catalog.
"""

import copy
import logging
from pathlib import Path
from typing import Any

from fs_tools.services.catalog_builder.blueprint_parser import BlueprintParser
from fs_tools.services.catalog_builder.damage_type_resolver import (
    build_damage_type_result,
    get_ammo_code,
    resolve_damage_type,
)
from fs_tools.services.catalog_builder.data_table_lookup import DataTableLookup
from fs_tools.services.catalog_builder.localization_lookup import (
    LocalizationLookup,
)
from fs_tools.services.catalog_builder.utils import (
    extract_localized_text,
    normalize_object_path,
)


class CatalogAssembler:
    """Service for building game catalogs from extracted blueprint data.

    This service orchestrates the catalog building process by:
    1. Scanning directories for blueprint files
    2. Filtering to stockpilable items
    3. Extracting and enriching data using specialized services
    4. Producing a complete catalog

    Attributes:
        blueprint_parser: Parser for blueprint JSON files.
        data_service: Service for data table lookups.
        loc_service: Service for localization lookups.
        search_directories: Directories to scan for blueprints.
        exclude_patterns: File name patterns to exclude.
    """

    def __init__(
        self,
        blueprint_parser: BlueprintParser,
        data_service: DataTableLookup,
        loc_service: LocalizationLookup,
    ) -> None:
        """Initialize the catalog builder service.

        Args:
            blueprint_parser (BlueprintParser): Parser for blueprint JSON files.
            data_service (DataTableLookup): Service for data table lookups.
            loc_service (LocalizationLookup): Service for localization lookups.
        """
        self.blueprint_parser = blueprint_parser
        self.data_service = data_service
        self.loc_service = loc_service
        self.logger = logging.getLogger(__name__)

        # Directories to scan for blueprints (relative to blueprints_dir)
        self.search_directories: list[str] = ["ItemPickups", "Vehicles", "Structures"]

        # File patterns to exclude from discovery
        self.exclude_patterns: list[str] = [
            "ItemComponent",  # Item component blueprints (e.g., BPFooItemComponent.json)
            "VehicleProxy",  # In-game placeholders
            "Ghost",
            "Destroyed",
        ]

        # Statistics
        self.stats = {
            "total_files": 0,
            "parsed": 0,
            "stockpilable": 0,
            "errors": 0,
        }

    @classmethod
    def from_extract_dir(
        cls,
        extract_dir: Path | str,
    ) -> "CatalogAssembler":
        """Create a CatalogAssembler from an extraction directory.

        Factory method that creates all required services from the root extraction
        directory, deriving the standard game paths internally.

        Args:
            extract_dir (Path | str): Root extraction directory (e.g., war/).

        Returns:
            CatalogAssembler: Configured service instance.

        Raises:
            FileNotFoundError: If extract_dir or required subdirectories don't exist.
            NotADirectoryError: If any path is not a directory.
        """
        extract_dir = Path(extract_dir).resolve()

        # Validate extract_dir exists
        if not extract_dir.exists():
            raise FileNotFoundError(f"Extraction directory not found: {extract_dir}")
        if not extract_dir.is_dir():
            raise NotADirectoryError(f"Not a directory: {extract_dir}")

        # Build and validate required paths
        content_dir = extract_dir / "War" / "Content"
        blueprints_dir = content_dir / "Blueprints"
        data_dir = blueprints_dir / "Data"
        localization_dir = content_dir / "Localization"

        required_dirs = {
            "Blueprints": blueprints_dir,
            "Data": data_dir,
            "Localization": localization_dir,
        }

        for name, path in required_dirs.items():
            if not path.exists():
                raise FileNotFoundError(f"{name} directory not found: {path}")
            if not path.is_dir():
                raise NotADirectoryError(f"{name} is not a directory: {path}")

        return cls(
            blueprint_parser=BlueprintParser(blueprints_dir=blueprints_dir, full_extraction=True),
            data_service=DataTableLookup(data_dir),
            loc_service=LocalizationLookup(localization_dir),
        )

    def _filter_blueprints_by_path(self) -> list[Path]:
        """Filter blueprint JSON files by path.

        Scans configured directories and filters out excluded patterns.

        Returns:
            list[Path]: List of paths to blueprint JSON files.
        """
        json_files: list[Path] = []
        blueprints_dir = self.blueprint_parser.blueprints_dir

        for directory in self.search_directories:
            dir_path = blueprints_dir / directory
            if not dir_path.exists():
                self.logger.debug("Directory not found: %s", dir_path)
                continue

            # Find all JSON files recursively
            found = list(dir_path.rglob("*.json"))

            # Filter out excluded patterns
            filtered = []
            for f in found:
                exclude = False
                for pattern in self.exclude_patterns:
                    if pattern in f.stem:
                        exclude = True
                        break
                if not exclude:
                    filtered.append(f)

            json_files.extend(filtered)
            self.logger.debug("Found %d JSON files in %s", len(filtered), directory)

        self.stats["total_files"] = len(json_files)
        self.logger.info("Total blueprint files to process: %d", len(json_files))
        return json_files

    def _filter_blueprint_by_content(self, data: dict[str, Any]) -> bool:
        """Filter blueprint by content.

        Validates required fields and checks stockpilable status based on
        categorization fields from the blueprint data.

        Note: This filtering is done after full blueprint parsing rather than
        before (pre-filtering). Benchmarks showed pre-filtering would only save
        ~70ms (~14%) for the full catalog build (0.43s vs 0.50s), which doesn't
        justify the added complexity of maintaining a separate light extraction
        path.

        Args:
            data (dict[str, Any]): Blueprint data dict.

        Returns:
            bool: True if the item should be included in the catalog.
        """
        # Must have required fields
        required_fields = ["CodeName", "DisplayName", "Icon", "Description"]
        if not all(data.get(field) for field in required_fields):
            return False

        # Check stockpilable criteria
        has_item_category = data.get("ItemCategory") is not None
        has_vehicle_profile = data.get("VehicleProfileType") is not None
        has_stockpilable = data.get("bIsStockpilable") is True
        has_reserve = data.get("bIsReserveStockpiled") is True

        # Vehicles with bIsStockpilable=False are not stockpilable
        # (trains, battle tanks, super tanks, mechs, large ships, relic vehicles)
        if has_vehicle_profile and data.get("bIsStockpilable") is False and not has_reserve:
            return False

        # Include if any stockpilable criterion is met
        return has_item_category or has_vehicle_profile or has_stockpilable or has_reserve

    def _get_ammo_code(self, data: dict[str, Any]) -> str | None:
        """Determine the ammo code for resolving DamageType.

        Args:
            data (dict[str, Any]): Blueprint data dict.

        Returns:
            str | None: Ammo CodeName to use for DamageType lookup, or None.
        """
        return get_ammo_code(data=data, data_service=self.data_service)

    def _parse_blueprint(self, json_path: Path) -> dict[str, Any] | None:
        """Build a complete catalog entry from a blueprint file.

        Extracts blueprint data, resolves localization, and enriches with
        data from data tables.

        Args:
            json_path (Path): Path to the blueprint JSON file.

        Returns:
            dict[str, Any] | None: Complete catalog entry, or None if invalid.
        """
        relative_path = json_path.relative_to(self.blueprint_parser.blueprints_dir)
        cached_data = self.blueprint_parser.extract_catalog_data(relative_path)

        if not cached_data:
            self.logger.debug("Failed to extract data from %s", json_path.name)
            return None

        # Deep copy to avoid modifying cached data (which would affect child blueprints
        # that inherit from this one via parent blueprint merging)
        data = copy.deepcopy(cached_data)

        code_name = data.get("CodeName", "")

        # Extract localization GUIDs from text fields
        # Blueprint parser returns {"Text": "...", "Guid": "..."} for localized text
        for field in ["DisplayName", "Description", "ChassisName"]:
            value = data.get(field)
            if isinstance(value, dict) and "Guid" in value:
                # Dict format: {"Text": "...", "Guid": "..."}
                data[f"{field}Key"] = value["Guid"]
                data[field] = extract_localized_text(value)
            elif isinstance(value, str) and self.loc_service.is_guid(value):
                # Legacy format: just a GUID string
                data[f"{field}Key"] = value
                data[field] = self.loc_service.get_with_fallback(value)

        # Expand with data tables and referenced blueprints
        self._expand_data(data, code_name)

        # Add AmmoDynamicData and resolve DamageType
        ammo_code = self._get_ammo_code(data)
        if ammo_code:
            # Add AmmoDynamicData from ammo if not already present (for weapons using ammo)
            if "AmmoDynamicData" not in data:
                ammo_dynamic = self.data_service.get_ammo_dynamic_data(ammo_code)
                if ammo_dynamic:
                    data["AmmoDynamicData"] = self._clean_data_table_entry(ammo_dynamic)

            # Resolve DamageType (expand import index like -25 to full object)
            ammo_data = data.get("AmmoDynamicData")
            if isinstance(ammo_data, dict) and not isinstance(ammo_data.get("DamageType"), dict):
                damage_type = self._resolve_damage_type(ammo_code)
                if damage_type:
                    ammo_data["DamageType"] = damage_type

        # Add SubTypeIcon
        self._add_subtype_icon(data)

        # Add locales
        self._enrich_locales(data)

        # Add ProductionCategories
        prod_cats = self.data_service.get_production_categories(code_name)
        if prod_cats:
            data["ProductionCategories"] = prod_cats

        # HARDCODED: Infer MassProductionFactory from VehicleBuildType/BuildLocationType
        # Queue types for vehicles/structures aren't in game data, only in C++
        if not prod_cats or "MassProductionFactory" not in prod_cats:
            vehicle_build_type = data.get("VehicleBuildType")
            build_location_type = data.get("BuildLocationType")
            shippable_info = data.get("ShippableInfo", "")

            if vehicle_build_type and vehicle_build_type != "EVehicleBuildType::NotBuildable":
                if "ProductionCategories" not in data:
                    data["ProductionCategories"] = {}
                data["ProductionCategories"]["MassProductionFactory"] = (
                    "EFactoryQueueType::Vehicles"
                )
            elif build_location_type in (
                "EBuildLocationType::Anywhere",
                "EBuildLocationType::ConstructionYard",
            ):
                if "ProductionCategories" not in data:
                    data["ProductionCategories"] = {}
                data["ProductionCategories"]["MassProductionFactory"] = (
                    "EFactoryQueueType::Structures"
                )
            elif "Large" in shippable_info:
                # Large shippable vehicles (e.g., landing crafts) are mass-produced
                if "ProductionCategories" not in data:
                    data["ProductionCategories"] = {}
                data["ProductionCategories"]["MassProductionFactory"] = (
                    "EFactoryQueueType::Vehicles"
                )

        return data

    def _expand_data(self, data: dict[str, Any], code_name: str) -> None:
        """Expand catalog entry with data tables and referenced blueprints.

        Args:
            data (dict[str, Any]): Blueprint data dict (modified in-place).
            code_name (str): Item CodeName for data table lookups.
        """
        if not code_name:
            return

        ds = self.data_service

        # Data table lookups by CodeName
        data_tables = [
            ("ItemDynamicData", ds.ITEM_DYNAMIC_DATA),
            ("WeaponDynamicData", ds.WEAPON_DYNAMIC_DATA),
            ("GrenadeDynamicData", ds.GRENADE_DYNAMIC_DATA),
            ("MeleeDynamicData", ds.MELEE_DYNAMIC_DATA),
            ("StructureDynamicData", ds.STRUCTURE_DYNAMIC_DATA),
            ("VehicleDynamicData", ds.VEHICLE_DYNAMIC_DATA),
            ("ShipDynamicData", ds.SHIP_DYNAMIC_DATA),
        ]
        for field_name, table_name in data_tables:
            table_data = ds.get(table_name, code_name)
            if table_data:
                data[field_name] = self._clean_data_table_entry(table_data)

        # Ammo data (case-insensitive lookup)
        ammo_data = ds.get_ammo_dynamic_data(code_name)
        if ammo_data:
            data["AmmoDynamicData"] = ammo_data

        # Profile table lookups by profile type
        profile_tables = [
            ("ItemProfileData", "ItemProfileType", ds.ITEM_PROFILE_TABLE, "ItemProfileTable"),
            ("ProfileData", "ProfileType", ds.STRUCTURE_PROFILE_TABLE, "StructureProfileMap"),
            (
                "VehicleProfileData",
                "VehicleProfileType",
                ds.VEHICLE_PROFILE_TABLE,
                "VehicleProfileMap",
            ),
            (
                "VehicleMovementProfileData",
                "VehicleMovementProfileType",
                ds.VEHICLE_MOVEMENT_PROFILE,
                "VehicleMovementProfileMap",
            ),
        ]
        for field_name, type_field, table_name, map_name in profile_tables:
            profile_type = data.get(type_field)
            if profile_type:
                profile_data = ds.get_profile(table_name, map_name, profile_type)
                if profile_data:
                    data[field_name] = profile_data

        # ItemComponentClass (referenced blueprint)
        self._enrich_item_component_class(data)

    def _build_damage_type_result(
        self,
        dt_data: dict[str, Any],
        bp_path: str,
    ) -> dict[str, Any]:
        """Build a resolved DamageType dict from blueprint data.

        Args:
            dt_data (dict[str, Any]): Extracted damage type blueprint data.
            bp_path (str): Blueprint path (for building ObjectPath).

        Returns:
            dict[str, Any]: Resolved DamageType with properties and resolved text.
        """
        return build_damage_type_result(
            dt_data=dt_data, bp_path=bp_path, loc_service=self.loc_service
        )

    def _resolve_damage_type(self, ammo_code: str) -> dict[str, Any] | None:
        """Resolve DamageType import reference to full object.

        Args:
            ammo_code (str): Ammo CodeName to resolve DamageType for.

        Returns:
            dict[str, Any] | None: Resolved DamageType dict with DisplayName,
                Icon, Type, etc., or None if not found.
        """
        return resolve_damage_type(
            ammo_code=ammo_code,
            data_service=self.data_service,
            blueprint_parser=self.blueprint_parser,
            loc_service=self.loc_service,
        )

    def _enrich_locales(
        self,
        data: dict[str, Any],
        fields: list[str] | None = None,
    ) -> None:
        """Enrich fields with all available locales (in-place).

        For each field that has a corresponding `*Key` field containing a GUID,
        adds a `*Locales` field with translations in all available languages,
        then removes the `*Key` field (no longer needed).

        Example: If data has `DisplayName` and `DisplayNameKey`, this adds
        `DisplayNameLocales` with {"en": "...", "de": "...", ...} and removes
        `DisplayNameKey`.

        Args:
            data: Catalog entry data to enrich.
            fields: Fields to localize. Defaults to
                ["DisplayName", "Description", "ChassisName"].
        """
        loc = self.loc_service

        if fields is None:
            fields = ["DisplayName", "Description", "ChassisName"]

        for field in fields:
            key_field = f"{field}Key"
            locales_field = f"{field}Locales"

            # Skip if already has locales or no GUID key
            if locales_field in data:
                # Still remove the key field if present
                data.pop(key_field, None)
                continue
            if key_field not in data:
                continue

            guid = data[key_field]
            if not loc.is_guid(guid):
                continue

            # Get all translations
            translations = loc.get_all_languages(guid)
            if translations:
                data[locales_field] = translations

            # Remove the GUID key field (no longer needed)
            del data[key_field]

    def _enrich_item_component_class(self, data: dict[str, Any]) -> None:
        """Enrich ItemComponentClass with all properties from component blueprint (in-place).

        Parses the item component blueprint and merges all its properties into
        ItemComponentClass, including:
        - MultiAmmo: List of compatible ammo CodeNames
        - CompatibleAmmoCodeName: Single ammo type
        - DeployCodeName: Deployed structure code
        - ProjectileClass: Resolved projectile info
        - All other component properties (weapon stats, etc.)

        Args:
            data: Catalog entry data containing ItemComponentClass.
        """
        bp = self.blueprint_parser

        item_comp_raw = data.get("ItemComponentClass")
        if not item_comp_raw:
            return

        # Handle both string path and dict formats
        # String: "/Game/Blueprints/Items/BPFoo"
        # Dict: {"ObjectPath": "War/Content/Blueprints/Items/BPFoo.0", ...}
        if isinstance(item_comp_raw, str):
            obj_path = item_comp_raw
            # Convert /Game/Blueprints/Items/BPFoo to Items/BPFoo.json
            bp_path = obj_path.replace("/Game/Blueprints/", "") + ".json"
            # Initialize as dict
            item_comp: dict[str, Any] = {"ObjectPath": obj_path}
            data["ItemComponentClass"] = item_comp
        elif isinstance(item_comp_raw, dict):
            item_comp = item_comp_raw
            obj_path = item_comp.get("ObjectPath", "")
            if not obj_path:
                return
            # Convert War/Content/Blueprints/Items/BPFoo.0 to Items/BPFoo.json
            bp_path = obj_path.replace("War/Content/Blueprints/", "").replace(".0", ".json")
        else:
            return

        # Parse the component blueprint. extract_catalog_data returns the parser's
        # cached dict by reference, so deep-copy before merging values into
        # item_comp — item_comp lives inside data, which callers already deep-copy
        # from cached_data, but that guarantee doesn't extend to values sourced
        # from a *second* cache lookup here.
        comp_data = bp.extract_catalog_data(bp_path)
        if not comp_data:
            return
        comp_data = copy.deepcopy(comp_data)

        # Merge all component properties into ItemComponentClass
        # Skip ObjectPath since we already have it
        for key, value in comp_data.items():
            if key == "ObjectPath":
                continue

            # Handle MultiAmmo specially - normalize to list of names
            if key == "MultiAmmo":
                if isinstance(value, list) and value:
                    item_comp["MultiAmmo"] = value
                elif isinstance(value, dict):
                    ammo_names = value.get("CompatibleAmmoNames", [])
                    if ammo_names:
                        item_comp["MultiAmmo"] = ammo_names
                continue

            # Store all other properties
            item_comp[key] = value

        # Resolve ProjectileClasses to get ExplosiveCodeName etc.
        # Skip for multi-ammo weapons (they use different projectiles per ammo)
        multi_ammo_list = item_comp.get("MultiAmmo", [])
        if isinstance(multi_ammo_list, list) and len(multi_ammo_list) > 1:
            return

        projectile_classes = item_comp.get("ProjectileClasses")
        if isinstance(projectile_classes, list) and projectile_classes:
            first_proj = projectile_classes[0]
            if isinstance(first_proj, str) and first_proj.startswith("/Game/"):
                proj_path = first_proj.replace("/Game/Blueprints/", "") + ".json"
                proj_data = bp.extract_catalog_data(proj_path)
                if proj_data:
                    # Store all projectile data (deep-copied for the same reason
                    # as comp_data above — proj_data is also a cached reference).
                    item_comp["ProjectileClass"] = {
                        k: copy.deepcopy(v) for k, v in proj_data.items() if k != "ObjectPath"
                    }

    # Subtype icons base path
    SUBTYPE_ICONS_BASE = "War/Content/Textures/UI/ItemIcons/"

    def _add_subtype_icon(self, data: dict[str, Any]) -> None:
        """Add SubTypeIcon from AmmoDynamicData.DamageType.Icon (in-place).

        Most items with SubTypeIcon have it defined directly in the blueprint
        (uniforms, wrecked parts, facility materials, etc.). This method only
        handles items where SubTypeIcon comes from DamageType.Icon:
        - Item's CodeName has its own AmmoDynamicData entry, OR
        - Item has ProjectileClass.ExplosiveCodeName (single-use/rocket), OR
        - Item has DeployCodeName (deployable tripod weapons)

        NOT added when:
        - SubTypeIcon already exists in the blueprint
        - AmmoDynamicData comes from MultiAmmo or CompatibleAmmoCodeName for weapons
        - Item is a Mine (mines have damage data but don't render subicons)

        Args:
            data: Catalog entry data.
        """
        # Skip if SubTypeIcon already exists in the blueprint
        if data.get("SubTypeIcon"):
            return

        code_name = data.get("CodeName", "")

        # DamageType.Icon from AmmoDynamicData
        ds = self.data_service

        ammo_data = data.get("AmmoDynamicData")
        if not isinstance(ammo_data, dict):
            # HARDCODED: ISGTC has no ammo info in blueprints
            if code_name == "ISGTC":
                data["SubTypeIcon"] = f"{self.SUBTYPE_ICONS_BASE}SubtypeSEIcon.0"
            return

        damage_type = ammo_data.get("DamageType")
        if not isinstance(damage_type, dict):
            return

        icon = damage_type.get("Icon")
        if not icon:
            return

        # Get ItemComponentClass for mine detection and other checks
        item_comp = data.get("ItemComponentClass")

        # Exclude mines - they have damage data but don't render subicons in-game
        # Mine detection requires ItemProfileType::Tool AND one of:
        # - bAutoActivate=True (land mines), OR
        # - no DeployCodeName AND no ExplosiveClass AND no ProjectileClass (water mines)
        profile_type = data.get("ItemProfileType", "")
        is_tool = "Tool" in str(profile_type)

        if is_tool and isinstance(item_comp, dict):
            is_auto_activate = item_comp.get("bAutoActivate") is True
            has_deploy_code = bool(item_comp.get("DeployCodeName"))
            has_explosive_class = bool(item_comp.get("ExplosiveClass"))
            has_projectile_class = bool(item_comp.get("ProjectileClass"))
            is_mine = is_auto_activate or (
                not has_deploy_code and not has_explosive_class and not has_projectile_class
            )
            if is_mine:
                return

        # Check if SubTypeIcon should be added from DamageType

        # Case 3a: Item's own CodeName has AmmoDynamicData entry
        if code_name and ds.get_ammo_dynamic_data(code_name):
            data["SubTypeIcon"] = icon
            return

        if isinstance(item_comp, dict):
            # Case 3b: Item has ProjectileClass.ExplosiveCodeName (single-use/rocket)
            proj_class = item_comp.get("ProjectileClass")
            if isinstance(proj_class, dict) and proj_class.get("ExplosiveCodeName"):
                data["SubTypeIcon"] = icon
                return

            # Case 3c: Item has DeployCodeName (deployable tripod weapons)
            if item_comp.get("DeployCodeName"):
                data["SubTypeIcon"] = icon
                return

        # Otherwise: ammo comes from MultiAmmo/CompatibleAmmoCodeName - no SubTypeIcon

    def _is_empty_resource_amounts(self, value: Any) -> bool:
        """Check if a ResourceAmounts value is empty/default.

        Detects the empty pattern:
        {
            "OtherResources": [],
            "Resource": {"CodeName": "None", "Quantity": 0}
        }

        Args:
            value: Value to check.

        Returns:
            True if this is an empty ResourceAmounts value.
        """
        if not isinstance(value, dict):
            return False

        other_resources = value.get("OtherResources")
        resource = value.get("Resource")

        if not isinstance(other_resources, list) or other_resources:
            return False  # Not empty list

        if not isinstance(resource, dict):
            return False

        return resource.get("CodeName") == "None" and resource.get("Quantity") == 0

    def _clean_data_table_entry(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Clean up empty/default values from a data table entry.

        Removes fields that contain default/empty values like:
        - AltResourceAmounts with empty resources

        Args:
            entry: Data table entry dict.

        Returns:
            Cleaned entry dict.
        """
        cleaned = {}
        for key, value in entry.items():
            # Skip AltResourceAmounts if it's empty/default
            if key == "AltResourceAmounts" and self._is_empty_resource_amounts(value):
                continue
            cleaned[key] = value
        return cleaned

    def _clean_entry(self, data: dict[str, Any]) -> dict[str, Any]:
        """Clean entry by removing None values and normalizing paths.

        Args:
            data: Catalog entry dict.

        Returns:
            Cleaned entry dict.
        """
        result: dict[str, Any] = {}
        for key, value in data.items():
            # Skip None values
            if value is None:
                continue

            # Normalize any /Game/ paths to War/Content/ format
            if isinstance(value, str) and value.startswith("/Game/"):
                value = normalize_object_path(value)

            # Recursively clean nested dicts
            elif isinstance(value, dict):
                value = self._clean_entry(value)

            # Recursively clean lists
            elif isinstance(value, list):
                cleaned_list: list[Any] = []
                for item in value:
                    if isinstance(item, dict):
                        cleaned_list.append(self._clean_entry(item))
                    elif isinstance(item, str) and item.startswith("/Game/"):
                        cleaned_list.append(normalize_object_path(item))
                    else:
                        cleaned_list.append(item)
                value = cleaned_list

            result[key] = value
        return result

    def build_catalog(self) -> list[dict[str, Any]]:
        """Build the complete catalog.

        Returns:
            list[dict[str, Any]]: List of catalog entries sorted by CodeName.
        """
        self.logger.info("Building catalog from %s", self.blueprint_parser.blueprints_dir)

        # Filter blueprint files by path
        json_files = self._filter_blueprints_by_path()

        # Process each blueprint
        catalog: list[dict[str, Any]] = []

        for json_path in json_files:
            self.stats["parsed"] += 1

            try:
                entry = self._parse_blueprint(json_path)
            except Exception as e:  # noqa: BLE001 - isolate one bad blueprint from the batch
                self.logger.error("Error building entry %s: %s", json_path.name, e)
                self.stats["errors"] += 1
                continue

            if not entry:
                continue

            # Filter blueprint by content
            if not self._filter_blueprint_by_content(data=entry):
                continue

            # Filter excluded keys
            filtered = self._clean_entry(entry)
            catalog.append(filtered)
            self.stats["stockpilable"] += 1

        # Sort by CodeName (case-insensitive)
        catalog.sort(key=lambda x: x.get("CodeName", "").lower())

        self.logger.info("Built catalog with %d entries", len(catalog))
        return catalog

    def get_stats(self) -> dict[str, int]:
        """Get processing statistics.

        Returns:
            dict[str, int]: Dict with processing stats.
        """
        return dict(self.stats)
