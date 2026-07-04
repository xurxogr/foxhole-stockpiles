"""Data table lookup for loading and querying Foxhole data tables.

This module handles parsing and querying of UAsset data tables exported to JSON,
including ItemDynamicData, VehicleDynamicData, AmmoDynamicData, and profile tables.
"""

import json
import logging
from pathlib import Path
from typing import Any, cast

from fs_tools.services.catalog_builder.utils import (
    extract_property_value,
    resolve_import_path,
)


class DataTableLookup:
    """Service for loading and querying Foxhole data tables.

    Data tables contain dynamic data for items, vehicles, ammo, etc.
    This service loads the JSON exports and provides methods to query
    data by CodeName.
    """

    # Data table file names
    ITEM_DYNAMIC_DATA = "BPItemDynamicData.json"
    ITEM_PROFILE_TABLE = "BPItemProfileTable.json"
    AMMO_DYNAMIC_DATA = "BPAmmoDynamicData.json"
    WEAPON_DYNAMIC_DATA = "BPWeaponDynamicData.json"
    GRENADE_DYNAMIC_DATA = "BPGrenadeDynamicData.json"
    MELEE_DYNAMIC_DATA = "BPMeleeDynamicData.json"
    STRUCTURE_DYNAMIC_DATA = "BPStructureDynamicData.json"
    STRUCTURE_PROFILE_TABLE = "BPStructureProfileList.json"  # Note: List not Table
    VEHICLE_DYNAMIC_DATA = "BPVehicleDynamicData.json"
    VEHICLE_PROFILE_TABLE = "BPVehicleProfileList.json"  # Note: List not Table
    VEHICLE_MOVEMENT_PROFILE = "BPVehicleMovementProfileList.json"  # Note: List not Table
    SHIP_DYNAMIC_DATA = "BPShipDynamicData.json"

    # Factory blueprint paths (relative to Blueprints folder, not Data)
    FACTORY_BLUEPRINT = "Structures/BPFactory.json"
    MASS_PRODUCTION_BLUEPRINT = "Structures/BPMassProduction.json"

    def __init__(self, data_dir: Path) -> None:
        """Initialize the data table service.

        Args:
            data_dir (Path): Path to the Data directory containing data table JSON files.
        """
        self.data_dir = data_dir.resolve()
        # Blueprints dir is parent of Data dir (for accessing factory blueprints)
        self.blueprints_dir = self.data_dir.parent
        self.logger = logging.getLogger(__name__)

        # Cache for loaded data tables (keyed by file name)
        self._table_cache: dict[str, dict[str, dict[str, Any]]] = {}

        # Cache for raw JSON data
        self._raw_cache: dict[str, dict[str, Any]] = {}

        # Cache for production categories: CodeName -> {Factory: QueueType, ...}
        self._production_categories_cache: dict[str, dict[str, str]] | None = None

    def _load_raw_table(self, table_name: str) -> dict[str, Any] | None:
        """Load raw JSON data from a data table file.

        Args:
            table_name (str): Name of the data table file (e.g., "BPItemDynamicData.json")

        Returns:
            dict[str, Any] | None: Raw JSON data or None if loading fails
        """
        if table_name in self._raw_cache:
            return self._raw_cache[table_name]

        table_path = self.data_dir / table_name
        if not table_path.exists():
            self.logger.debug("Data table not found: %s", table_path)
            return None

        try:
            with open(table_path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
                self._raw_cache[table_name] = data
                return data
        except Exception as e:  # noqa: BLE001 - isolate one malformed table from the batch
            self.logger.error("Error loading data table %s: %s", table_name, e)
            return None

    def _extract_property_value(self, prop: dict[str, Any]) -> Any:
        """Extract the value from a UAsset property dict.

        Uses the shared extract_property_value utility, but handles
        ObjectPropertyData specially to return raw import indices
        (needed for import resolution).

        Args:
            prop (dict[str, Any]): Property dict with $type and Value fields

        Returns:
            Any: Extracted value (simplified)
        """
        prop_type = prop.get("$type", "")

        # ObjectPropertyData: return raw import index for resolution
        if "ObjectPropertyData" in prop_type:
            return prop.get("Value")

        # StructPropertyData: recursively extract (need self reference)
        if "StructPropertyData" in prop_type:
            value = prop.get("Value")
            if isinstance(value, list):
                result = {}
                for inner_prop in value:
                    if isinstance(inner_prop, dict) and "Name" in inner_prop:
                        inner_name = inner_prop.get("Name")
                        inner_value = self._extract_property_value(inner_prop)
                        result[inner_name] = inner_value
                return result
            return value

        # ArrayPropertyData: recursively extract (need self reference)
        if "ArrayPropertyData" in prop_type:
            value = prop.get("Value")
            if isinstance(value, list):
                return [
                    self._extract_property_value(item) if isinstance(item, dict) else item
                    for item in value
                ]
            return value

        # All other types: use shared utility
        return extract_property_value(prop)

    def _parse_table_data(self, raw_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """Parse raw data table JSON into a lookup dict.

        Args:
            raw_data (dict[str, Any]): Raw JSON data from data table file

        Returns:
            dict[str, dict[str, Any]]: Dict mapping CodeName to extracted data
        """
        result: dict[str, dict[str, Any]] = {}

        exports = raw_data.get("Exports", [])
        if not exports:
            return result

        # Find the DataTableExport
        for export in exports:
            if export.get("$type") != "UAssetAPI.ExportTypes.DataTableExport, UAssetAPI":
                continue

            table = export.get("Table", {})
            table_data = table.get("Data", [])

            for entry in table_data:
                code_name = entry.get("Name")
                if not code_name:
                    continue

                # Extract all properties from Value array
                values = entry.get("Value", [])
                extracted = {}

                for prop in values:
                    if not isinstance(prop, dict):
                        continue

                    prop_name = prop.get("Name")
                    if not prop_name:
                        continue

                    extracted[prop_name] = self._extract_property_value(prop)

                result[code_name] = extracted

            break  # Only process first DataTableExport

        return result

    def _get_table(self, table_name: str) -> dict[str, dict[str, Any]]:
        """Get parsed data table, loading and caching if needed.

        Args:
            table_name (str): Name of the data table file

        Returns:
            dict[str, dict[str, Any]]: Dict mapping CodeName to extracted data
        """
        if table_name in self._table_cache:
            return self._table_cache[table_name]

        raw_data = self._load_raw_table(table_name)
        if not raw_data:
            return {}

        parsed = self._parse_table_data(raw_data)
        self._table_cache[table_name] = parsed

        self.logger.debug("Loaded %d entries from %s", len(parsed), table_name)
        return parsed

    def _parse_profile_table(
        self, raw_data: dict[str, Any], map_name: str
    ) -> dict[str, dict[str, Any]]:
        """Parse a profile table (blueprint with Map property).

        Profile tables are blueprints with a Map property keyed by enum values.

        Args:
            raw_data (dict[str, Any]): Raw JSON data from the file
            map_name (str): Name of the Map property (e.g., "ItemProfileTable")

        Returns:
            dict[str, dict[str, Any]]: Dict mapping enum values to profile data
        """
        result: dict[str, dict[str, Any]] = {}

        exports = raw_data.get("Exports", [])
        if not exports:
            return result

        # Find Default__ export
        for export in exports:
            obj_name = export.get("ObjectName", "")
            if not obj_name.startswith("Default__"):
                continue

            props = export.get("Data", [])
            for prop in props:
                if prop.get("Name") != map_name:
                    continue

                # Map property value is a list of [key, value] pairs
                map_value = prop.get("Value", [])
                for entry in map_value:
                    if not isinstance(entry, list) or len(entry) != 2:
                        continue

                    key_prop, value_props = entry

                    # Extract key (enum value)
                    key = None
                    if isinstance(key_prop, dict):
                        key = key_prop.get("Value")
                    if not key:
                        continue

                    # Extract values - value_props is a dict with "Value" containing the list
                    extracted = {}
                    value_list = value_props
                    if isinstance(value_props, dict):
                        value_list = value_props.get("Value", [])

                    if isinstance(value_list, list):
                        for val_prop in value_list:
                            if not isinstance(val_prop, dict):
                                continue
                            prop_name = val_prop.get("Name")
                            if prop_name:
                                extracted[prop_name] = self._extract_property_value(val_prop)

                    result[key] = extracted

            break  # Only process first Default__ export

        return result

    def _get_profile_table(self, table_name: str, map_name: str) -> dict[str, dict[str, Any]]:
        """Get parsed profile table, loading and caching if needed.

        Args:
            table_name (str): Name of the profile table file
            map_name (str): Name of the Map property

        Returns:
            dict[str, dict[str, Any]]: Dict mapping enum values to profile data
        """
        cache_key = f"{table_name}:{map_name}"
        if cache_key in self._table_cache:
            return self._table_cache[cache_key]

        raw_data = self._load_raw_table(table_name)
        if not raw_data:
            return {}

        parsed = self._parse_profile_table(raw_data, map_name)
        self._table_cache[cache_key] = parsed

        self.logger.debug("Loaded %d entries from %s.%s", len(parsed), table_name, map_name)
        return parsed

    def _table_object_path(self, table_name: str) -> str:
        """Get ObjectPath for a data table.

        Args:
            table_name: Table file name (e.g., "BPItemDynamicData.json")

        Returns:
            ObjectPath string (e.g., "War/Content/Blueprints/Data/BPItemDynamicData")
        """
        base_name = table_name.replace(".json", "")
        return f"War/Content/Blueprints/Data/{base_name}"

    def _with_object_path(
        self, data: dict[str, Any] | None, table_name: str
    ) -> dict[str, Any] | None:
        """Add ObjectPath to data dict.

        Args:
            data: Data dict to add ObjectPath to
            table_name: Table file name for ObjectPath

        Returns:
            Data dict with ObjectPath added, or None if data is None
        """
        if data is None:
            return None
        result = dict(data)
        result["ObjectPath"] = self._table_object_path(table_name)
        return result

    def get(self, table_name: str, key: str) -> dict[str, Any] | None:
        """Get data from a data table by key.

        Args:
            table_name: Name of the data table file (e.g., "BPWeaponDynamicData.json")
            key: Lookup key (usually CodeName)

        Returns:
            Data dict with ObjectPath added, or None if not found
        """
        table = self._get_table(table_name)
        return self._with_object_path(table.get(key), table_name)

    def get_profile(self, table_name: str, map_name: str, key: str) -> dict[str, Any] | None:
        """Get data from a profile table by key.

        Args:
            table_name: Name of the profile table file
            map_name: Name of the Map property in the blueprint
            key: Lookup key (usually profile type enum)

        Returns:
            Data dict with ObjectPath added, or None if not found
        """
        table = self._get_profile_table(table_name, map_name)
        return self._with_object_path(table.get(key), table_name)

    def get_ammo_dynamic_data(self, code_name: str) -> dict[str, Any] | None:
        """Get AmmoDynamicData for an ammo type by CodeName.

        Performs case-insensitive lookup since component blueprints may use
        different casing than the data table (e.g., RPGAmmo vs RpgAmmo).

        Args:
            code_name: Ammo's CodeName

        Returns:
            Dict with Damage, Suppression, DamageType, etc., or None if not found
        """
        if not code_name:
            return None

        table = self._get_table(self.AMMO_DYNAMIC_DATA)

        # Try exact match first
        if code_name in table:
            return self._with_object_path(table.get(code_name), self.AMMO_DYNAMIC_DATA)

        # Try case-insensitive match
        code_lower = code_name.lower()
        for key in table:
            if key.lower() == code_lower:
                return self._with_object_path(table.get(key), self.AMMO_DYNAMIC_DATA)

        return None

    def resolve_damage_type_import(
        self, code_name: str, raw_imports: list[dict[str, Any]] | None = None
    ) -> str | None:
        """Resolve damage type import path for an ammo type.

        Args:
            code_name (str): Ammo CodeName.
            raw_imports (list[dict] | None): Raw imports from the data table
                (for path resolution).

        Returns:
            str | None: Damage type blueprint path or None.
        """
        ammo_data = self.get_ammo_dynamic_data(code_name)
        if not ammo_data:
            return None

        damage_type_ref = ammo_data.get("DamageType")
        if not isinstance(damage_type_ref, int) or damage_type_ref >= 0:
            return None

        # Need raw imports to resolve the path
        if not raw_imports:
            raw_data = self._load_raw_table(self.AMMO_DYNAMIC_DATA)
            if raw_data:
                raw_imports = raw_data.get("Imports", [])

        if not raw_imports:
            return None

        return resolve_import_path(damage_type_ref, raw_imports)

    @staticmethod
    def _find_specialized_factory_export(exports: list[dict[str, Any]]) -> dict[str, Any] | None:
        """Find the SpecializedFactoryComponent export in a blueprint's exports.

        Args:
            exports (list[dict[str, Any]]): The blueprint's "Exports" list.

        Returns:
            dict[str, Any] | None: The matching export, or None if not found.
        """
        for export in exports:
            if "SpecializedFactoryComponent" in export.get("ObjectName", ""):
                return export
        return None

    @staticmethod
    def _extract_production_categories_prop(export: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract the ProductionCategories property value from a factory export.

        Args:
            export (dict[str, Any]): The SpecializedFactoryComponent export.

        Returns:
            list[dict[str, Any]]: The ProductionCategories value, or [] if absent.
        """
        for prop in export.get("Data", []):
            if prop.get("Name") == "ProductionCategories":
                return cast(list[dict[str, Any]], prop.get("Value", []))
        return []

    @staticmethod
    def _extract_category_item_codes(cat_value: list[dict[str, Any]]) -> list[str]:
        """Extract CodeName values from a category's CategoryItems property.

        Args:
            cat_value (list[dict[str, Any]]): Properties of one production category.

        Returns:
            list[str]: CodeName values found in CategoryItems.
        """
        item_codes: list[str] = []
        for cprop in cat_value:
            if cprop.get("Name") != "CategoryItems":
                continue
            for item in cprop.get("Value", []):
                for iprop in item.get("Value", []):
                    if iprop.get("Name") == "CodeName":
                        item_codes.append(iprop.get("Value"))
        return item_codes

    @classmethod
    def _parse_production_category(
        cls, cat_value: list[dict[str, Any]]
    ) -> tuple[str | None, list[str]]:
        """Parse a single production category entry into its type and item codes.

        Args:
            cat_value (list[dict[str, Any]]): Properties of one production category.

        Returns:
            tuple[str | None, list[str]]: The category's QueueType (or None) and
                the CodeNames it contains.
        """
        cat_type = next(
            (cprop.get("Value") for cprop in cat_value if cprop.get("Name") == "Type"), None
        )
        return cat_type, cls._extract_category_item_codes(cat_value)

    def _parse_factory_production_categories(self, factory_path: str) -> dict[str, str]:
        """Parse production categories from a factory blueprint.

        Args:
            factory_path (str): Path to factory blueprint relative to Blueprints dir.

        Returns:
            dict[str, str]: Dict mapping CodeName to QueueType for this factory.
        """
        result: dict[str, str] = {}

        factory_file = self.blueprints_dir / factory_path
        if not factory_file.exists():
            self.logger.debug("Factory blueprint not found: %s", factory_file)
            return result

        try:
            with open(factory_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:  # noqa: BLE001 - isolate one malformed blueprint from the batch
            self.logger.error("Error loading factory blueprint %s: %s", factory_path, e)
            return result

        export = self._find_specialized_factory_export(data.get("Exports", []))
        if export is None:
            self.logger.debug("Loaded %d production categories from %s", len(result), factory_path)
            return result

        for category in self._extract_production_categories_prop(export):
            cat_type, cat_items = self._parse_production_category(category.get("Value", []))
            if cat_type:
                for code_name in cat_items:
                    result[code_name] = cat_type

        self.logger.debug("Loaded %d production categories from %s", len(result), factory_path)
        return result

    def _load_production_categories(self) -> dict[str, dict[str, str]]:
        """Load and cache all production categories from factory blueprints.

        Returns:
            dict[str, dict[str, str]]: Dict mapping CodeName (lowercase) to
                {Factory: QueueType, MassProductionFactory: QueueType}.
        """
        if self._production_categories_cache is not None:
            return self._production_categories_cache

        result: dict[str, dict[str, str]] = {}

        # Parse Factory blueprint
        factory_cats = self._parse_factory_production_categories(self.FACTORY_BLUEPRINT)
        for code_name, queue_type in factory_cats.items():
            # Use lowercase key for case-insensitive lookup
            key = code_name.lower()
            if key not in result:
                result[key] = {}
            result[key]["Factory"] = queue_type

        # Parse MassProductionFactory blueprint
        mass_cats = self._parse_factory_production_categories(self.MASS_PRODUCTION_BLUEPRINT)
        for code_name, queue_type in mass_cats.items():
            # Use lowercase key for case-insensitive lookup
            key = code_name.lower()
            if key not in result:
                result[key] = {}
            result[key]["MassProductionFactory"] = queue_type

        self._production_categories_cache = result
        return result

    def get_production_categories(self, code_name: str) -> dict[str, str] | None:
        """Get production categories for an item by CodeName (case-insensitive).

        Args:
            code_name (str): Item's CodeName.

        Returns:
            dict[str, str] | None: Dict with Factory and/or MassProductionFactory keys
                mapping to EFactoryQueueType values, or None if not producible.
        """
        if not code_name:
            return None
        categories = self._load_production_categories()
        return categories.get(code_name.lower())
