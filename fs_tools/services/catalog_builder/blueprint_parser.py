"""Blueprint JSON parser for Unreal Engine assets.

This module handles parsing and processing of UAsset JSON files exported from
Unreal Engine blueprints. It resolves references, processes property structures,
and handles blueprint inheritance.
"""

import json
import logging
from pathlib import Path
from typing import Any

from fs_tools.services.catalog_builder.blueprint_import_resolution import (
    process_import,
    resolve_import_asset_path,
    resolve_import_full_path,
)
from fs_tools.services.catalog_builder.blueprint_type_processing import process_value
from fs_tools.services.catalog_builder.utils import (
    parse_reference,
    simplify_value,
)


class BlueprintParser:
    """Parse and process Unreal Engine blueprint JSON files.

    This parser handles:
    - Loading blueprint JSON files
    - Resolving import/export references (negative/positive indices)
    - Processing property structures ($type fields)
    - Detecting parent blueprint inheritance chains
    - Filtering exports to catalog-relevant data (Default__ + inheritance chain)
    - Caching raw and processed blueprint data
    """

    def __init__(self, blueprints_dir: Path, full_extraction: bool = False) -> None:
        """Initialize the blueprint parser.

        Args:
            blueprints_dir (Path): Root directory containing blueprint JSON files.
            full_extraction (bool): If True, extract all data including export references.
                If False (default), use simplified extraction that filters out
                export references and invalid imports.
        """
        self.blueprints_dir = blueprints_dir.resolve()
        self.full_extraction = full_extraction
        self.logger = logging.getLogger(__name__)

        # Cache for raw JSON data (as loaded from file)
        self.raw_cache: dict[str, dict[str, Any] | None] = {}

        # Cache for processed blueprint data (with resolved references and inheritance)
        self.processed_cache: dict[str, dict[str, Any] | None] = {}

        # Cache for fully resolved catalog data (with parent inheritance merged)
        # This stores the final result so parent data is only computed once
        self.catalog_cache: dict[str, dict[str, Any] | None] = {}

        # Cache for resolved paths (original path -> actual path)
        self._path_cache: dict[str, Path | None] = {}

    def _find_blueprint_path(self, json_path: Path) -> Path | None:
        """Find blueprint file path, searching subdirectories if needed.

        Some blueprints have ObjectPaths that don't match the actual file location.
        For example, Structures/BPEmplacedATW.json may actually be at
        Structures/Emplacements/BPEmplacedATW.json.

        Args:
            json_path: Requested path to the blueprint JSON file.

        Returns:
            Path to the actual file, or None if not found.
        """
        # Check cache first
        cache_key = str(json_path)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]

        # Try direct path first
        if json_path.exists():
            self._path_cache[cache_key] = json_path
            return json_path

        # Search in subdirectories
        # e.g., Structures/BPEmplacedATW.json -> Structures/Emplacements/BPEmplacedATW.json
        try:
            rel_path = json_path.relative_to(self.blueprints_dir)
            parts = rel_path.parts
            if len(parts) >= 2:
                parent_dir = self.blueprints_dir / parts[0]  # e.g., "Structures"
                filename = parts[-1]  # e.g., "BPEmplacedATW.json"

                if parent_dir.exists():
                    for found in parent_dir.rglob(filename):
                        self._path_cache[cache_key] = found
                        return found
        except ValueError:
            pass  # Path not relative to blueprints_dir

        self._path_cache[cache_key] = None
        return None

    def parse(self, json_path: Path | str) -> dict[str, Any] | None:
        """Parse a blueprint JSON file and return processed data.

        This method:
        1. Loads the raw JSON file (with caching)
        2. Filters Exports to catalog-relevant ones (Default__ + inheritance chain)
        3. Simplifies Imports to blueprint paths only (None for non-blueprints)
        4. Resolves references (imports/exports indices)
        5. Processes property structures (removes $type, extracts values)
        6. Returns processed dict with simplified values

        Args:
            json_path (Path | str): Path to the blueprint JSON file

        Returns:
            dict | None: Processed blueprint data with filtered Exports and simplified
                        Imports, or None if loading fails

        Example:
            parser = BlueprintParser("/path/to/blueprints")
            data = parser.parse("Items/BPGrenadeW.json")
            # Returns: {
            #     "Exports": [<inheritance export>, <Default__ export with data>],
            #     "Imports": [None, "/Game/Blueprints/Items/Grenade", ...],
            #     ...
            # }
        """
        json_path = Path(json_path)

        # Make path absolute if relative
        if not json_path.is_absolute():
            json_path = self.blueprints_dir / json_path

        json_path = json_path.resolve()

        # Find actual file path (may be in subdirectory)
        actual_path = self._find_blueprint_path(json_path)
        if actual_path:
            json_path = actual_path

        # Check processed cache first
        cache_key = str(json_path)
        if cache_key in self.processed_cache:
            self.logger.debug("Returning cached processed data for %s", json_path.name)
            return self.processed_cache[cache_key]

        # Load raw JSON
        raw_data = self._load_raw_json(json_path)
        if raw_data is None:
            self.processed_cache[cache_key] = None
            return None

        # Process the blueprint data
        processed_data = self._process_blueprint(raw_data)

        self.processed_cache[cache_key] = processed_data
        return processed_data

    def _resolve_parent_blueprint(
        self,
        default_export: dict[str, Any],
        exports: list[dict[str, Any]],
        imports: list[str | None],
    ) -> str | None:
        """Resolve parent blueprint path from the class export's SuperIndex.

        Finds the class export (matching name without Default__ prefix), then
        resolves its SuperIndex to get the parent blueprint path.

        Args:
            default_export (dict): The Default__ export dict.
            exports (list): List of processed exports.
            imports (list): List of processed imports (blueprint paths or None).

        Returns:
            str | None: Parent blueprint path (e.g., "/Game/Blueprints/Items/Grenade"),
                or None if no parent blueprint found.
        """
        # Get the class name from Default__ export (e.g., Default__BPFooW_C -> BPFooW_C)
        default_name = default_export.get("ObjectName", "")
        if not default_name.startswith("Default__"):
            return None
        class_name = default_name[9:]  # Remove "Default__" prefix

        # Find the class export by name
        class_export = next((exp for exp in exports if exp.get("ObjectName") == class_name), None)
        if not class_export:
            return None

        # Get SuperIndex from class export
        super_index = class_export.get("SuperIndex")
        super_ref = parse_reference(super_index) if isinstance(super_index, str) else None
        if super_ref is None or super_ref >= 0:
            return None

        # Resolve import path
        import_path = imports[abs(super_ref) - 1]
        return import_path or None

    def _resolve_actual_json_path(self, json_path: Path | str) -> Path:
        """Resolve the requested blueprint path to its actual on-disk location.

        Args:
            json_path (Path | str): Path to the blueprint JSON file, as requested.

        Returns:
            Path: The resolved, absolute path — the actual file location if found
                in a subdirectory, otherwise the requested path resolved as-is.
        """
        json_path_obj = Path(json_path)
        if not json_path_obj.is_absolute():
            json_path_obj = self.blueprints_dir / json_path_obj
        json_path_obj = json_path_obj.resolve()

        actual_path = self._find_blueprint_path(json_path_obj)
        return actual_path or json_path_obj

    def _compute_object_path(self, json_path_obj: Path) -> str:
        """Compute the catalog ObjectPath for a blueprint file.

        ObjectPath is the path relative to the extraction root (the war/
        directory three levels above blueprints_dir), with the .json extension
        stripped.

        Args:
            json_path_obj (Path): Resolved, absolute path to the blueprint JSON file.

        Returns:
            str: The ObjectPath, or the absolute path if it isn't relative to the
                extraction root.
        """
        try:
            extraction_root = self.blueprints_dir.parent.parent.parent.resolve()
            relative_path = json_path_obj.relative_to(extraction_root)
            object_path = str(relative_path).replace("\\", "/")
            if object_path.endswith(".json"):
                object_path = object_path[:-5]
            return object_path
        except ValueError:
            # Path is not relative to extraction root
            return str(json_path_obj)

    def _extract_property_data(self, data: Any, imports: list[str | None], cache_key: str) -> Any:
        """Process the Default__ export's Data fields into catalog properties.

        Args:
            data (Any): The Default__ export's Data payload (dict or list).
            imports (list[str | None]): Processed imports array for the blueprint.
            cache_key (str): Cache key used to look up raw imports/exports when
                full extraction is enabled.

        Returns:
            Any: Processed catalog properties (dict, matching _process_data's contract).
        """
        if not self.full_extraction:
            return self._process_data(data=data, imports=imports)

        # For full extraction, get raw imports/exports to resolve all references
        raw_data = self.raw_cache.get(cache_key) or {}
        raw_imports = raw_data.get("Imports", [])
        raw_exports = raw_data.get("Exports", [])
        return self._process_data(
            data=data, imports=imports, raw_imports=raw_imports, raw_exports=raw_exports
        )

    def _merge_with_parent(self, catalog_data: dict[str, Any], parent_path: str) -> dict[str, Any]:
        """Merge parent blueprint catalog data beneath the child's own data.

        Args:
            catalog_data (dict[str, Any]): The child blueprint's own catalog data.
            parent_path (str): Parent blueprint path (e.g., /Game/Blueprints/...).

        Returns:
            dict[str, Any]: Merged catalog data (parent values first, child
                overrides), or catalog_data unchanged if the parent has no data.
        """
        parent_data = self._get_parent_data(parent_path)
        if not parent_data:
            return catalog_data

        # Merge parent data (parent values first, child overrides)
        merged = dict(parent_data)
        merged.update(catalog_data)
        # Keep child's CodeName, ObjectPath and ParentBlueprint
        merged["CodeName"] = catalog_data.get("CodeName")
        merged["ObjectPath"] = catalog_data.get("ObjectPath")
        if "ParentBlueprint" in catalog_data:
            merged["ParentBlueprint"] = catalog_data["ParentBlueprint"]
        return merged

    def extract_catalog_data(self, json_path: Path | str) -> dict[str, Any] | None:
        """Extract simplified catalog data from a blueprint.

        This method extracts only the relevant data for catalog building:
        1. Finds the Default__ export (catalog properties)
        2. Adds ParentBlueprint if the blueprint inherits from another blueprint
        3. Expands valid blueprint references to full paths
        4. Removes invalid references (C++ classes, visual/audio assets, components)
        5. Keeps literal values as-is

        Args:
            json_path (Path | str): Path to the blueprint JSON file

        Returns:
            dict | None: Simplified catalog data with:
                - ParentBlueprint: Optional parent blueprint path
                - All catalog properties from Default__ export Data
                - Blueprint references expanded to full paths
                - Invalid references removed
                Or None if parsing fails

        Example:
            parser = BlueprintParser("/path/to/blueprints")
            catalog = parser.extract_catalog_data("Items/BPGrenadeW.json")
            # Returns: {
            #     "ParentBlueprint": "/Game/Blueprints/Items/Grenade",
            #     "ExplosiveCodeName": "GrenadeW",
            #     "ExplosionTemplate": "/Game/Blueprints/Items/GrenadeExplosion",
            #     ...
            # }
        """
        # Resolve the actual path first (for cache key)
        json_path_obj = self._resolve_actual_json_path(json_path)

        # Check catalog cache first (stores fully merged data with parents)
        cache_key = str(json_path_obj)
        if cache_key in self.catalog_cache:
            return self.catalog_cache[cache_key]

        # Parse the blueprint
        processed = self.parse(json_path)
        if not processed:
            self.catalog_cache[cache_key] = None
            return None

        exports = processed.get("Exports", [])
        imports = processed.get("Imports", [])

        # Step 1: Find the Default__ export
        default_export = next(
            (exp for exp in exports if exp.get("ObjectName", "").startswith("Default__")), None
        )

        if not default_export:
            self.catalog_cache[cache_key] = None
            return None

        catalog_data: dict[str, Any] = {"ObjectPath": self._compute_object_path(json_path_obj)}

        # Step 2: Check for ParentBlueprint via ClassIndex → SuperIndex chain
        parent_path = self._resolve_parent_blueprint(default_export, exports, imports)
        if parent_path:
            catalog_data["ParentBlueprint"] = parent_path

        # Step 3: Process Data fields
        data = default_export.get("Data", {})
        if not isinstance(data, (dict, list)):
            # Data is not properly converted (e.g., base64 string from UAssetGUI)
            self.logger.debug("Skipping blueprint with unconverted Data: %s", json_path_obj.name)
            self.catalog_cache[cache_key] = catalog_data
            return catalog_data

        catalog_data.update(
            self._extract_property_data(data=data, imports=imports, cache_key=cache_key)
        )

        # Step 4: Merge properties from parent blueprints (parent first, then child overrides)
        if parent_path and parent_path.startswith("/Game/Blueprints/"):
            catalog_data = self._merge_with_parent(catalog_data, parent_path)

        # Cache the fully merged result
        self.catalog_cache[cache_key] = catalog_data
        return catalog_data

    def _get_parent_data(self, parent_path: str) -> dict[str, Any] | None:
        """Get catalog data from a parent blueprint.

        Args:
            parent_path (str): Parent blueprint path (e.g., /Game/Blueprints/...).

        Returns:
            dict | None: Parent's catalog data or None if not found.
        """
        if not parent_path.startswith("/Game/Blueprints/"):
            return None

        relative_path = parent_path.replace("/Game/Blueprints/", "") + ".json"
        json_path_obj = self.blueprints_dir / relative_path

        if not json_path_obj.exists():
            return None

        # Recursively extract parent data (this will also merge grandparent data)
        return self.extract_catalog_data(relative_path)

    def _process_data(
        self,
        data: Any,
        imports: list[str | None],
        raw_imports: list[dict[str, Any]] | None = None,
        raw_exports: list[dict[str, Any]] | None = None,
    ) -> Any:
        """Process catalog data fields recursively.

        When raw_imports/raw_exports are provided (full extraction mode):
        - Resolves export references to object names
        - Falls back to raw_imports for asset path resolution
        - Applies simplify_value to results

        When raw_imports/raw_exports are None (simple mode):
        - Skips export references
        - Only uses processed imports (skips if null)
        - Filters empty results

        Args:
            data: Data to process (dict, list, or primitive).
            imports: Processed imports array (blueprint paths or None).
            raw_imports: Raw imports array for resolving asset paths (full mode).
            raw_exports: Raw exports array for resolving export refs (full mode).

        Returns:
            Processed data with references resolved.
        """
        full_mode = raw_imports is not None or raw_exports is not None
        if raw_imports is None:
            raw_imports = []
        if raw_exports is None:
            raw_exports = []

        if isinstance(data, dict):
            dict_result: dict[str, Any] = {}
            for key, value in data.items():
                ref_idx = parse_reference(value) if isinstance(value, str) else None
                if ref_idx is not None:
                    if ref_idx == 0:
                        continue  # Skip null references
                    if ref_idx < 0:  # Import reference
                        import_path = imports[abs(ref_idx) - 1]
                        if import_path:
                            dict_result[key] = import_path
                        elif full_mode and raw_imports:
                            # Try resolving as asset path from raw imports
                            raw_import = raw_imports[abs(ref_idx) - 1]
                            asset_path = resolve_import_asset_path(raw_import, raw_imports)
                            if asset_path:
                                dict_result[key] = asset_path
                    elif full_mode and ref_idx <= len(raw_exports):  # Export reference
                        export_obj = raw_exports[ref_idx - 1]
                        obj_name = export_obj.get("ObjectName")
                        if obj_name:
                            dict_result[key] = obj_name
                    # else: skip unresolved references

                elif isinstance(value, (dict, list)):
                    processed = self._process_data(
                        data=value,
                        imports=imports,
                        raw_imports=raw_imports if full_mode else None,
                        raw_exports=raw_exports if full_mode else None,
                    )
                    if full_mode:
                        dict_result[key] = simplify_value(processed)
                    elif processed:  # Simple mode: only include if not empty
                        dict_result[key] = processed

                else:
                    dict_result[key] = simplify_value(value) if full_mode else value

            return dict_result

        if isinstance(data, list):
            list_result: list[Any] = []
            for item in data:
                ref_idx = parse_reference(item) if isinstance(item, str) else None
                if ref_idx is not None:
                    if ref_idx == 0:
                        continue  # Skip null references
                    if ref_idx < 0:
                        import_path = imports[abs(ref_idx) - 1]
                        if import_path:
                            list_result.append(import_path)
                        elif full_mode and raw_imports:
                            raw_import = raw_imports[abs(ref_idx) - 1]
                            asset_path = resolve_import_asset_path(raw_import, raw_imports)
                            if asset_path:
                                list_result.append(asset_path)
                    elif full_mode and ref_idx <= len(raw_exports):
                        export_obj = raw_exports[ref_idx - 1]
                        obj_name = export_obj.get("ObjectName")
                        if obj_name:
                            list_result.append(obj_name)

                elif isinstance(item, (dict, list)):
                    processed = self._process_data(
                        data=item,
                        imports=imports,
                        raw_imports=raw_imports if full_mode else None,
                        raw_exports=raw_exports if full_mode else None,
                    )
                    if full_mode or processed:
                        list_result.append(processed)
                else:
                    list_result.append(item)

            return list_result

        return data

    def _load_raw_json(self, json_path: Path) -> dict[str, Any] | None:
        """Load raw JSON file with caching.

        Args:
            json_path (Path): Path to JSON file

        Returns:
            dict | None: Raw JSON data as dict, or None if loading fails
        """
        cache_key = str(json_path)

        # Check raw cache
        if cache_key in self.raw_cache:
            return self.raw_cache[cache_key]

        # Load from file
        if not json_path.exists():
            self.logger.debug("JSON file not found: %s", json_path)
            self.raw_cache[cache_key] = None
            return None

        try:
            with open(json_path, encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)

            self.logger.debug("Loaded raw JSON: %s", json_path.name)
            self.raw_cache[cache_key] = data
            return data

        except (OSError, json.JSONDecodeError) as e:
            self.logger.error("Failed to load JSON %s: %s", json_path, e)
            self.raw_cache[cache_key] = None
            return None

    def _process_blueprint(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Process a raw blueprint JSON into simplified structure.

        Args:
            raw_data (dict): Raw blueprint JSON data

        Returns:
            dict: Processed blueprint with simplified values
        """
        # Start with all fields from raw data
        result: dict[str, Any] = {}

        # Get raw imports and exports for reference resolution
        raw_imports = raw_data.get("Imports", [])
        raw_exports = raw_data.get("Exports", [])

        # Process all top-level fields
        for key, value in raw_data.items():
            if key == "Exports":
                # Special handling for Exports - keep Default__ export and any exports
                # needed for inheritance chain (ClassIndex → SuperIndex → parent blueprint)
                processed_exports = []

                # Find the Default__ export first
                default_export = None
                default_index = -1
                for i, export in enumerate(value):
                    if export.get("ObjectName", "").startswith("Default__"):
                        default_export = export
                        default_index = i
                        break

                if default_export:
                    # Collect export indices to include
                    exports_to_include = {default_index}

                    # Check if Default__ export's ClassIndex references another export
                    class_index = default_export.get("ClassIndex", 0)
                    if class_index > 0:  # Positive = Export reference
                        # Include the referenced export (needed for SuperIndex/parent chain)
                        exports_to_include.add(class_index - 1)  # Convert to 0-based

                    # Process only the exports we need
                    for i, export in enumerate(value):
                        if i in exports_to_include:
                            processed_export = self._process_export(
                                export=export, imports=raw_imports, exports=raw_exports
                            )
                            processed_exports.append(processed_export)

                result["Exports"] = processed_exports

            elif key == "Imports":
                # Special handling for Imports - resolve blueprint paths, null for others
                processed_imports = []
                for import_obj in value:
                    # Returns full path for BlueprintGeneratedClass, None otherwise
                    processed_import = process_import(data=import_obj, all_imports=raw_imports)
                    processed_imports.append(processed_import)
                result["Imports"] = processed_imports

            else:
                # Process all other fields recursively (strips $type, simplifies values)
                result[key] = process_value(value)

        return result

    def _resolve_index_to_name(
        self, index: int, imports: list[dict[str, Any]], exports: list[dict[str, Any]]
    ) -> str | None:
        """Resolve an import/export index to the object name.

        Args:
            index (int): The index to resolve (negative = import, positive = export)
            imports (list[dict]): Raw imports array (unprocessed dicts)
            exports (list[dict]): Raw exports array (unprocessed dicts)

        Returns:
            str | None: The ObjectName of the referenced object, or None if not found
        """
        if index == 0:
            return None

        try:
            if index < 0:
                # Negative index = import (1-indexed)
                import_obj = imports[abs(index) - 1]
                obj_name: str = import_obj.get("ObjectName", "Unknown")
                return obj_name
            else:
                # Positive index = export (1-indexed)
                export_obj = exports[index - 1]
                obj_name = export_obj.get("ObjectName", "Unknown")
                return obj_name
        except (IndexError, KeyError):
            return f"Invalid:{index}"

    def _process_export(
        self, export: dict[str, Any], imports: list[dict[str, Any]], exports: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Process a single export, converting all properties to simple values.

        Args:
            export (dict): Raw export data
            imports (list[dict]): Raw imports array for reference resolution (unprocessed dicts)
            exports (list[dict]): Raw exports array for reference resolution (unprocessed dicts)

        Returns:
            dict: Processed export with simplified properties
        """
        result = {
            "ObjectName": export.get("ObjectName", ""),
            "Data": {},
        }

        # Resolve ClassIndex and OuterIndex conditionally
        # - If negative (Import): always resolve to name (imports don't have data)
        # - If positive (Export): resolve to name only if export has no data
        class_index = export.get("ClassIndex", 0)
        if class_index != 0:
            if class_index < 0:
                # Import reference - always resolve
                class_name = self._resolve_index_to_name(
                    index=class_index, imports=imports, exports=exports
                )
                if class_name:
                    result["ClassIndex"] = class_name
            else:
                # Export reference - check if it has data
                try:
                    ref_export = exports[class_index - 1]
                    ref_data = ref_export.get("Data", [])
                    if not ref_data or len(ref_data) == 0:
                        # No data, resolve to name
                        class_name = self._resolve_index_to_name(
                            index=class_index, imports=imports, exports=exports
                        )
                        if class_name:
                            result["ClassIndex"] = class_name
                    else:
                        # Has data, keep as reference
                        result["ClassIndex"] = f"Reference: {class_index}"
                except (IndexError, KeyError):
                    result["ClassIndex"] = f"Reference: {class_index}"

        # OuterIndex removed - not relevant for catalog building
        # (only shows internal component hierarchy)

        # Keep SuperIndex and TemplateIndex as references (might need for inheritance)
        super_index = export.get("SuperIndex", 0)
        if super_index != 0:
            result["SuperIndex"] = f"Reference: {super_index}"

        template_index = export.get("TemplateIndex", 0)
        if template_index != 0:
            result["TemplateIndex"] = f"Reference: {template_index}"

        # Check if this is a RawExport (extraction tool couldn't parse it properly)
        export_type = export.get("$type", "")
        if "RawExport" in export_type:
            # Keep Data as-is for RawExport (it's unparsed/binary data)
            result["Data"] = export.get("Data")
            return result

        # Process the Data array (convert to dict keyed by property name)
        data = export.get("Data", [])
        for prop in data:
            if isinstance(prop, dict) and "Name" in prop:
                prop_name = prop.get("Name")
                # Process the property value, stripping $type structures
                prop_value = process_value(prop)
                result["Data"][prop_name] = prop_value

        # Post-process: resolve simple Export references to names
        # (exports with no data can be simplified, exports with data stay as references)
        for prop_name, prop_value in list(result["Data"].items()):
            ref_index = parse_reference(prop_value) if isinstance(prop_value, str) else None
            if ref_index is not None and ref_index > 0:  # Positive = Export reference
                try:
                    ref_export = exports[ref_index - 1]
                    ref_data = ref_export.get("Data", [])

                    # If the referenced export has no data, resolve to simple name
                    if not ref_data or len(ref_data) == 0:
                        ref_name = ref_export.get("ObjectName", f"Export{ref_index}")
                        result["Data"][prop_name] = ref_name
                except (IndexError, KeyError):
                    # Keep as reference if we can't resolve
                    pass

        return result

    def _process_value(self, data: Any) -> Any:
        """Process any value, converting $type structures to simple values.

        Args:
            data (Any): Data to process (dict with $type, or simple value)

        Returns:
            Any: Processed value (simple type without $type structures)
        """
        return process_value(data)

    def _resolve_import_full_path(
        self, import_obj: dict[str, Any], all_imports: list[dict[str, Any]]
    ) -> str | None:
        """Resolve an import's full path by following OuterIndex chain.

        Args:
            import_obj (dict): The import object to resolve
            all_imports (list[dict]): All raw imports for OuterIndex resolution (unprocessed dicts)

        Returns:
            str | None: Full path like "/Game/Blueprints/Items/Grenade" or None
        """
        return resolve_import_full_path(import_obj=import_obj, all_imports=all_imports)

    def _resolve_import_asset_path(
        self, import_obj: dict[str, Any], all_imports: list[dict[str, Any]]
    ) -> str | None:
        """Resolve any import to its asset path (for full extraction).

        Args:
            import_obj (dict): The import object to resolve
            all_imports (list[dict]): All raw imports for OuterIndex resolution

        Returns:
            str | None: Asset path like "War/Content/Textures/UI/Icon.0" or None
        """
        return resolve_import_asset_path(import_obj=import_obj, all_imports=all_imports)
