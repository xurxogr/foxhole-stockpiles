"""Resolution of ammo codes and DamageType blueprints for catalog entries.

Extracted from :mod:`catalog_assembler` since these functions are pure
lookups/transforms over their explicit arguments — they hold no assembler
state of their own, only the services (`DataTableLookup`, `BlueprintParser`,
`LocalizationLookup`) passed in by the caller.
"""

from typing import Any

from fs_tools.services.catalog_builder.blueprint_parser import BlueprintParser
from fs_tools.services.catalog_builder.data_table_lookup import DataTableLookup
from fs_tools.services.catalog_builder.localization_lookup import LocalizationLookup
from fs_tools.services.catalog_builder.utils import (
    extract_localized_text,
    normalize_object_path,
)


def get_ammo_code(data: dict[str, Any], data_service: DataTableLookup) -> str | None:
    """Determine the ammo code for resolving DamageType.

    Args:
        data (dict[str, Any]): Blueprint data dict.
        data_service (DataTableLookup): Service for data table lookups.

    Returns:
        str | None: Ammo CodeName to use for DamageType lookup, or None.
    """
    code_name = data.get("CodeName", "")

    # Case 1: Item itself is ammo (has AmmoDynamicData entry)
    if data_service.get_ammo_dynamic_data(code_name):
        return str(code_name)

    item_comp = data.get("ItemComponentClass")
    if not isinstance(item_comp, dict):
        return None

    # Case 2: Single ammo type from MultiAmmo
    multi_ammo = item_comp.get("MultiAmmo", [])
    if isinstance(multi_ammo, list) and len(multi_ammo) == 1:
        return str(multi_ammo[0])

    # Case 3: CompatibleAmmoCodeName (single ammo weapons)
    compat_ammo = item_comp.get("CompatibleAmmoCodeName")
    if compat_ammo:
        return str(compat_ammo)

    # Case 4: ProjectileClass.ExplosiveCodeName
    proj_class = item_comp.get("ProjectileClass")
    if isinstance(proj_class, dict):
        explosive = proj_class.get("ExplosiveCodeName")
        if explosive:
            return str(explosive)

    return None


def build_damage_type_result(
    dt_data: dict[str, Any],
    bp_path: str,
    loc_service: LocalizationLookup,
) -> dict[str, Any]:
    """Build a resolved DamageType dict from blueprint data.

    Args:
        dt_data (dict[str, Any]): Extracted damage type blueprint data.
        bp_path (str): Blueprint path (for building ObjectPath).
        loc_service (LocalizationLookup): Service for localization lookups.

    Returns:
        dict[str, Any]: Resolved DamageType with properties and resolved text.
    """
    # Build ObjectPath from blueprint path
    # DamageTypes/BPFoo.json -> /Game/Blueprints/DamageTypes/BPFoo -> normalized
    game_path = "/Game/Blueprints/" + bp_path.replace(".json", "")
    object_path = normalize_object_path(game_path)

    resolved: dict[str, Any] = {"ObjectPath": object_path}

    # Copy relevant properties
    for key in [
        "Type",
        "Icon",
        "VehicleSubsystemDisableMultipliers",
        "bApplyDamageFalloff",
        "bCanWoundCharacter",
        "bExposeInUI",
        "bAlwaysAppliesBleeding",
        "bCanRuinStructures",
        # Tank armour related
        "TankArmourPenetrationFactor",
        "TankArmourEffectType",
        "bApplyTankArmourMechanics",
        "bApplyTankArmourAngleRangeBonuses",
    ]:
        if key in dt_data:
            value = dt_data[key]
            # Simplify Icon to just the ResourceObject path
            if key == "Icon" and isinstance(value, dict):
                value = value.get("ResourceObject", value)
            resolved[key] = value

    # Resolve DisplayName
    display_name = dt_data.get("DisplayName")
    if display_name:
        text = extract_localized_text(display_name)
        if text and loc_service.is_guid(text):
            resolved["DisplayName"] = loc_service.get_with_fallback(text)
        elif text:
            resolved["DisplayName"] = text

    # Resolve DescriptionDetails (array of tooltip texts joined with newlines)
    desc_details = dt_data.get("DescriptionDetails")
    if isinstance(desc_details, list) and desc_details:
        # Collect texts from the array (may be GUIDs or already resolved text)
        texts: list[str] = []
        guids: list[str] = []
        for item in desc_details:
            if isinstance(item, dict):
                text_value = item.get("Text", "")
                # Handle nested dict format {"Text": {"Text": "...", "Guid": "..."}}
                if isinstance(text_value, dict):
                    text = str(text_value.get("Text", ""))
                    guid = text_value.get("Guid")
                    if guid and isinstance(guid, str):
                        guids.append(guid)
                else:
                    text = str(text_value) if text_value else ""
            elif isinstance(item, str):
                text = item
            else:
                continue
            if not text:
                continue
            if loc_service.is_guid(text):
                guids.append(text)
                texts.append(loc_service.get_with_fallback(text))
            else:
                # Already resolved text (from CultureInvariantString)
                texts.append(text)

        if texts:
            resolved["DescriptionDetails"] = "\n".join(texts)

            # Build locales only if we have GUIDs to look up
            if guids:
                all_langs: set[str] = set()
                for guid in guids:
                    translations = loc_service.get_all_languages(guid)
                    if translations:
                        all_langs.update(translations.keys())

                if all_langs:
                    locales: dict[str, str] = {}
                    for lang in sorted(all_langs):
                        lang_texts = []
                        for guid in guids:
                            translations = loc_service.get_all_languages(guid)
                            if translations and lang in translations:
                                lang_texts.append(translations[lang])
                        if lang_texts:
                            locales[lang] = "\n".join(lang_texts)
                    if locales:
                        resolved["DescriptionDetailsLocales"] = locales

    # Generate DescriptionDetails from boolean properties if not already set
    if "DescriptionDetails" not in resolved:
        generated_texts: list[str] = []
        if dt_data.get("bBreachesBunkers"):
            generated_texts.append("Always has a chance to breach bunkers")
        if generated_texts:
            resolved["DescriptionDetails"] = "\n".join(generated_texts)

    return resolved


def resolve_damage_type(
    ammo_code: str,
    data_service: DataTableLookup,
    blueprint_parser: BlueprintParser,
    loc_service: LocalizationLookup,
) -> dict[str, Any] | None:
    """Resolve DamageType import reference to full object.

    Args:
        ammo_code (str): Ammo CodeName to resolve DamageType for.
        data_service (DataTableLookup): Service for data table lookups.
        blueprint_parser (BlueprintParser): Parser for blueprint JSON files.
        loc_service (LocalizationLookup): Service for localization lookups.

    Returns:
        dict[str, Any] | None: Resolved DamageType dict with DisplayName,
            Icon, Type, etc., or None if not found.
    """
    # Get the damage type path from ammo data table
    damage_type_path = data_service.resolve_damage_type_import(ammo_code)
    if not damage_type_path:
        return None

    # Handle Script paths (C++ classes) - return as Type field
    if damage_type_path.startswith("/Script/"):
        # Extract package path (e.g., /Script/War/Foo -> /Script/War)
        parts = damage_type_path.split("/")
        if len(parts) >= 3:
            return {"Type": f"/Script/{parts[2]}"}
        return {"Type": damage_type_path}

    # Convert /Game/ path to relative path for parser
    bp_path = damage_type_path.replace("/Game/Blueprints/", "")
    bp_path = bp_path.replace("_C", "")
    parts = bp_path.split("/")
    if len(parts) >= 2 and parts[-1] == parts[-2]:
        bp_path = "/".join(parts[:-1])
    bp_path += ".json"

    # Load damage type blueprint
    dt_data = blueprint_parser.extract_catalog_data(bp_path)
    if not dt_data:
        return None

    return build_damage_type_result(dt_data=dt_data, bp_path=bp_path, loc_service=loc_service)
