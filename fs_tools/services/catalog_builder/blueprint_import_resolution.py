"""Resolution of raw UAsset import entries to `/Game/...` object paths.

Extracted from :mod:`blueprint_parser` since these functions are pure
lookups over the raw imports array — they hold no parser state (no caches,
no logger).
"""

from typing import Any

from fs_tools.services.catalog_builder.utils import normalize_object_path


def resolve_import_full_path(
    import_obj: dict[str, Any], all_imports: list[dict[str, Any]]
) -> str | None:
    """Resolve an import's full path by following OuterIndex chain.

    Only resolves BlueprintGeneratedClass imports. For other assets, use
    resolve_import_asset_path instead.

    Args:
        import_obj (dict): The import object to resolve
        all_imports (list[dict]): All raw imports for OuterIndex resolution (unprocessed dicts)

    Returns:
        str | None: Full path like "/Game/Blueprints/Items/Grenade" or None
    """
    # Only resolve BlueprintGeneratedClass imports
    if import_obj.get("ClassName") != "BlueprintGeneratedClass":
        return None

    # Follow OuterIndex to get package path
    outer_index = import_obj.get("OuterIndex", 0)
    if outer_index < 0:
        try:
            # Get the package import
            package_import = all_imports[abs(outer_index) - 1]
            package_path: str = package_import.get("ObjectName", "")

            # The package path should start with /Game/
            if package_path.startswith("/Game/"):
                return package_path
        except IndexError:
            pass

    return None


def resolve_import_asset_path(
    import_obj: dict[str, Any], all_imports: list[dict[str, Any]]
) -> str | None:
    """Resolve any import to its asset path (for full extraction).

    Unlike resolve_import_full_path, this resolves all asset types
    (Texture2D, StaticMesh, etc.) not just BlueprintGeneratedClass.

    Args:
        import_obj (dict): The import object to resolve
        all_imports (list[dict]): All raw imports for OuterIndex resolution

    Returns:
        str | None: Asset path like "War/Content/Textures/UI/Icon.0" or None
    """
    class_name: str = import_obj.get("ClassName", "")

    # Skip script/engine classes (not assets)
    if class_name in ("Package", "Class", "Function", "ScriptStruct"):
        return None

    # Follow OuterIndex to get package path
    outer_index = import_obj.get("OuterIndex", 0)
    if outer_index < 0:
        try:
            package_import = all_imports[abs(outer_index) - 1]
            package_path: str = package_import.get("ObjectName", "")

            if package_path.startswith("/Game/"):
                return normalize_object_path(package_path)
        except IndexError:
            pass

    return None


def process_import(data: dict[str, Any], all_imports: list[dict[str, Any]]) -> str | None:
    """Process Import - return full path for blueprints, None for others.

    Args:
        data (dict): Import data dict
        all_imports (list[dict]): All raw imports for path resolution (unprocessed dicts)

    Returns:
        str | None: Full blueprint path or None if not a blueprint
    """
    # Resolve to full path for BlueprintGeneratedClass, None otherwise
    return resolve_import_full_path(import_obj=data, all_imports=all_imports)
