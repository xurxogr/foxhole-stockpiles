"""Conversion of raw UAsset $type-tagged structures into simple Python values.

Extracted from :mod:`blueprint_parser` since these functions are pure
transformations of a `$type`-tagged dict/list into a plain value — they hold
no parser state (no caches, no logger) and recurse only among themselves.
"""

from typing import Any


def process_value(data: Any) -> Any:
    """Process any value, converting $type structures to simple values.

    This is the main dispatcher that routes to specific type handlers.

    Args:
        data (Any): Data to process (dict with $type, or simple value)

    Returns:
        Any: Processed value (simple type without $type structures)
    """
    # Handle lists - process each item recursively
    if isinstance(data, list):
        return [process_value(item) for item in data]

    # Handle non-dict primitives (int, str, bool, None, etc.)
    if not isinstance(data, dict):
        return data

    type_str = data.get("$type", "")
    if not type_str:
        # No $type, process dict values recursively
        return {k: process_value(v) for k, v in data.items()}

    # Route to appropriate handler based on $type
    # PropertyData types (most common)
    if "PropertyData" in type_str:
        if "Struct" in type_str:
            return _process_struct_data(data=data, type_str=type_str)
        return _process_property_data(data=data, type_str=type_str)

    # UnrealTypes
    if "UnrealTypes" in type_str:
        return _process_unreal_type(data=data)

    # Field types
    if "FieldTypes" in type_str:
        return _process_field_type(data=data)

    # CustomVersion
    if "CustomVersion" in type_str:
        return _process_custom_version(data)

    # Default: return Value field or the whole dict
    return data.get("Value", data)


def _process_property_data(data: dict[str, Any], type_str: str) -> Any:
    """Process PropertyData types.

    Handles types like IntPropertyData, BoolPropertyData, StrPropertyData, etc.

    Args:
        data (dict): Property data dict
        type_str (str): The $type string

    Returns:
        Any: Extracted simple value
    """
    # Integer types
    if any(
        x in type_str
        for x in [
            "IntPropertyData",
            "Int8PropertyData",
            "Int16PropertyData",
            "Int64PropertyData",
            "UInt16PropertyData",
            "UInt32PropertyData",
        ]
    ):
        return data.get("Value", 0)

    # Boolean
    if "BoolPropertyData" in type_str:
        return data.get("Value", False)

    # Float
    if "FloatPropertyData" in type_str:
        return data.get("Value", 0.0)

    # String/Name
    if "StrPropertyData" in type_str or "NamePropertyData" in type_str:
        value = data.get("Value")
        return value.get("Value", "") if isinstance(value, dict) else (str(value) if value else "")

    # Text
    if "TextPropertyData" in type_str:
        culture_invariant = data.get("CultureInvariantString")
        value = data.get("Value")

        # Return both text and GUID if both exist (for localization support)
        if culture_invariant and value and isinstance(value, str):
            return {"Text": culture_invariant, "Guid": value}

        # Fallback: just return the text
        if culture_invariant:
            return culture_invariant
        return (
            value.get("CultureInvariantString", "")
            if isinstance(value, dict)
            else (str(value) if value else "")
        )

    # Byte/Enum
    if "BytePropertyData" in type_str or "EnumPropertyData" in type_str:
        value = data.get("Value")
        return value.get("Value", "") if isinstance(value, dict) else value

    # SoftObject (check before ObjectPropertyData since it's a substring match)
    if "SoftObjectPropertyData" in type_str:
        value = data.get("Value")
        return value.get("AssetPathName", "") if isinstance(value, dict) else value

    # Object
    if "ObjectPropertyData" in type_str:
        value = data.get("Value")
        if isinstance(value, dict):
            # Value is dict with Index field
            index = value.get("Index", 0)
        elif isinstance(value, int):
            # Value is directly the index
            index = value
        else:
            return value

        # Mark as reference so we can identify it later
        return f"Reference: {index}"

    # Array
    if "ArrayPropertyData" in type_str:
        value = data.get("Value", [])
        return [process_value(item) for item in value] if isinstance(value, list) else value

    # Map
    if "MapPropertyData" in type_str:
        return data.get("Value", {})

    # Set
    if "SetPropertyData" in type_str:
        value = data.get("Value", [])
        return [process_value(item) for item in value] if isinstance(value, list) else value

    # Delegate
    if "FDelegate" in type_str or "DelegatePropertyData" in type_str:
        return data.get("Value")

    # MulticastDelegate
    if "MulticastSparseDelegatePropertyData" in type_str:
        return data.get("Value", [])

    # Default
    return data.get("Value")


def _process_struct_data(data: dict[str, Any], type_str: str) -> Any:
    """Process Struct types.

    Handles types like VectorPropertyData, ColorPropertyData, StructPropertyData, etc.

    Args:
        data (dict): Struct data dict
        type_str (str): The $type string

    Returns:
        Any: Extracted simple value (dict, list, or primitive)
    """
    value = data.get("Value", [])

    # StructPropertyData contains nested properties
    if "StructPropertyData" in type_str and not any(
        x in type_str
        for x in [
            "Vector",
            "Color",
            "Rotator",
            "Quat",
            "Box",
            "IntPoint",
            "Guid",
            "RichCurve",
        ]
    ):
        if isinstance(value, list):
            # Process each property in the struct
            result = {}
            for prop in value:
                if isinstance(prop, dict) and "Name" in prop:
                    prop_name = prop.get("Name")
                    result[prop_name] = process_value(prop)
            return result
        return value

    # GUID - extract Guid string from dict
    if "GuidPropertyData" in type_str:
        if isinstance(value, dict):
            return str(value.get("Guid", ""))
        return value

    # PerPlatformFloat - use data.get with default
    if "PerPlatformFloatPropertyData" in type_str:
        return data.get("Value", 0.0)

    # All other struct types return value as-is:
    # Vector types (Vector2D, Vector, Vector4), Rotator, Quat, Color types,
    # Box types, IntPoint, RichCurveKey, Material/Expression Input, SkeletalMesh
    return value


def _process_unreal_type(data: dict[str, Any]) -> Any:
    """Process UnrealTypes.

    Handles types like FVector, FRotator, FLinearColor, etc.

    Args:
        data (dict): Unreal type dict

    Returns:
        Any: Extracted simple value (dict without $type)
    """
    # These are usually simple structs, return without $type field
    return {k: v for k, v in data.items() if k != "$type"}


def _process_field_type(data: dict[str, Any]) -> Any:
    """Process Field types.

    Handles UArrayProperty, UBoolProperty, UObjectProperty, etc.

    Args:
        data (dict): Field type dict

    Returns:
        Any: Processed field data
    """
    # Field types describe property metadata, not values
    # For now, return simplified version
    return {
        "Name": data.get("Name", ""),
        "Flags": data.get("Flags", 0),
    }


def _process_custom_version(data: dict[str, Any]) -> dict[str, Any]:
    """Process CustomVersion type.

    Converts CustomVersion object to simple FriendlyName: Version mapping.

    Args:
        data (dict): CustomVersion data dict

    Returns:
        dict: Simple mapping of {FriendlyName: Version}
    """
    friendly_name = data.get("FriendlyName", "Unknown")
    version = data.get("Version", 0)
    return {friendly_name: version}
