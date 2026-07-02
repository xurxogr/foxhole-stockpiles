"""Config migration steps v1 -> v7."""

from typing import Any


def migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v1 (flat output structure) to v2 (nested output structure).

    V1 had: output_format.{output_format, output_destination, file_path, webhook_url, ...}
    V2 has: output.{format, destination, file.{path}, webhook.{url, auth_type, token, ...}}

    Args:
        data: V1 configuration data

    Returns:
        V2 configuration data
    """
    # Check if we have old output_format structure
    if "output_format" in data and isinstance(data["output_format"], dict):
        old_output = data["output_format"]

        # Build new nested structure
        new_output: dict[str, Any] = {
            "format": old_output.get("output_format", "json"),
            "destination": old_output.get("output_destination", "return"),
            "file": {
                "path": old_output.get("file_path", "output.json"),
            },
            "webhook": {
                "url": old_output.get("webhook_url"),
                "auth_type": old_output.get("webhook_auth_type"),
                "token": old_output.get("webhook_token"),
                "client_auth_header": old_output.get("webhook_client_auth_header"),
            },
            "console": {},
        }

        # Replace with new structure
        data["output"] = new_output
        del data["output_format"]

    if "scanner" in data and isinstance(data["scanner"], dict):
        data["scanner"].pop("confidence_threshold", None)
        data["scanner"].pop("confidence_by_resolution", None)

    return data


def migrate_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v2 to v3 (move tools from database_builder to external_tools).

    V2 had: database_builder.{extractor_tool, converter_tool, catalog_file, ...}
    V3 has: external_tools.{repak, umodel, uassetgui} + database_builder.{catalog_file, ...}

    Args:
        data: V2 configuration data

    Returns:
        V3 configuration data
    """
    # Initialize external_tools if not present
    if "external_tools" not in data:
        data["external_tools"] = {}

    # Move tools from database_builder to external_tools
    if "database_builder" in data and isinstance(data["database_builder"], dict):
        db_builder = data["database_builder"]

        # Move extractor_tool -> repak
        if "extractor_tool" in db_builder:
            data["external_tools"]["repak"] = db_builder.pop("extractor_tool")

        # Move converter_tool -> umodel
        if "converter_tool" in db_builder:
            data["external_tools"]["umodel"] = db_builder.pop("converter_tool")

    return data


def migrate_v3_to_v4(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v3 to v4 (stockpile_types now only stores additional aliases).

    V3 had: stockpile_types with all translations as defaults (including undefined)
    V4 has: stockpile_types with only user-added aliases (no undefined field)

    The default texts are hardcoded here as they existed at v3 time, so this
    migration remains stable regardless of later changes. (The stockpile_types
    section itself is dropped entirely in the v10->v11 migration.)

    Args:
        data: V3 configuration data

    Returns:
        V4 configuration data
    """
    if "stockpile_types" not in data or not isinstance(data["stockpile_types"], dict):
        return data

    stockpile_types = data["stockpile_types"]

    # Remove the undefined field (no longer valid)
    stockpile_types.pop("undefined", None)

    # Hardcoded defaults as they existed at v3 time (before enum refactoring)
    # These are the translations that should be filtered out
    v3_defaults: dict[str, set[str]] = {
        "encampment": {
            "Encampment",
            "Feldlager",
            "Campement",
            "Acampamento",
            "Лагерь",
            "营地",
        },
        "keep": {
            "Keep",
            "Wehrturm",
            "Place Forte",
            "Torreão",
            "Крепость",
            "要塞",
        },
        "safe_house": {
            "Safe House",
            "Unterschlupf",
            "Planque",
            "Casa Fortificada",
            "Убежище",
            "安全屋",
        },
        "relic_base": {
            "Relic Base",
            "Reliktbasis",
            "Base Relique",
            "Base Relíquia",
            "Реликтовая База",
            "遗迹基地",
        },
        "bunker_base": {
            "Bunker Base",
            "Bunkerbasis",
            "Base Bunker",
            "Centro do Bunker",
            "Base de Bunker",
            "Centro do bunker",
            "Бункерная база",
            "Бункерная База",
            "地堡基地",
        },
        "border_base": {
            "Border Base",
            "Grenzbasis",
            "Base Frontalière",
            "Base Fronteiriça",
            "Пограничная База",
            "边境基地",
        },
        "town_base": {
            "Town Base",
            "Stadtkernbasis",
            "Quartier Général",
            "Base da Cidade",
            "Ратуша",
            "城镇基地",
        },
        "underground_fortress": {
            "Underground Fortress",
            "Untergrundfestung",
            "Forteresse Souterraine",
            "Bunker Subterrâneo",
            "Подземная Крепость",
            "地下要塞",
        },
        "bms_longhook": {"BMS - Longhook"},
        "bms_bluefin": {"BMS - Bluefin"},
        "storage_depot": {
            "Storage Depot",
            "Lagerdepot",
            "Dépôt",
            "Depósito",
            "Складское помещение",
            "仓库",
        },
        "seaport": {
            "Seaport",
            "Seehafen",
            "Port",
            "Porto",
            "Морской порт",
            "海港",
        },
        "aircraft_depot": {"Aircraft Depot"},
    }

    # Filter out default translations, keeping only user-added aliases
    for field_name, defaults in v3_defaults.items():
        if field_name in stockpile_types and isinstance(stockpile_types[field_name], list):
            stockpile_types[field_name] = [
                alias for alias in stockpile_types[field_name] if alias not in defaults
            ]

    return data


def migrate_v4_to_v5(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v4 to v5 (output now supports multiple handlers).

    V4 had: output.{format, destination, file.{path}, webhook.{...}, console.{}}
    V5 has: output.{handlers: [{name, format: {type, ...}, handler: {type, ...}}, ...]}

    Args:
        data: V4 configuration data

    Returns:
        V5 configuration data
    """
    if "output" not in data or not isinstance(data["output"], dict):
        return data

    old_output = data["output"]

    # Check if already migrated (has handlers key)
    if "handlers" in old_output:
        return data

    # Get old values with defaults
    old_format = old_output.get("format", "json")
    old_destination = old_output.get("destination", "return")
    old_file = old_output.get("file", {})
    old_webhook = old_output.get("webhook", {})

    # Build format settings
    format_settings: dict[str, Any] = {"type": old_format}

    # Build handler settings based on destination
    handler_settings: dict[str, Any] = {"type": old_destination}

    if old_destination == "file":
        handler_settings["path"] = old_file.get("path", "output.json")
    elif old_destination == "webhook":
        if old_webhook.get("url"):
            handler_settings["url"] = old_webhook["url"]
        if old_webhook.get("auth_type"):
            handler_settings["auth_type"] = old_webhook["auth_type"]
        if old_webhook.get("token"):
            handler_settings["token"] = old_webhook["token"]
        if old_webhook.get("client_auth_header"):
            handler_settings["client_auth_header"] = old_webhook["client_auth_header"]

    # Determine handler name based on destination
    destination_names = {
        "return": "API Response",
        "file": "File Output",
        "webhook": "Webhook",
        "console": "Console",
    }
    handler_name = destination_names.get(old_destination, "Output")

    # Build new structure with single handler
    data["output"] = {
        "handlers": [
            {
                "name": handler_name,
                "format": format_settings,
                "handler": handler_settings,
            }
        ]
    }

    return data


def migrate_v5_to_v6(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v5 to v6 (expand non-tiered fields to tiered fields).

    V5 had: stockpile_types with non-tiered fields (bunker_base, town_base)
    V6 has: stockpile_types with tiered fields (bunker_base_1, town_base_1, etc.)

    Args:
        data: V5 configuration data

    Returns:
        V6 configuration data
    """
    if "stockpile_types" not in data or not isinstance(data["stockpile_types"], dict):
        return data

    stockpile_types = data["stockpile_types"]

    # Rename non-tiered fields to tier 1 (user aliases apply to all tiers via tier 1)
    if "bunker_base" in stockpile_types:
        stockpile_types["bunker_base_1"] = stockpile_types.pop("bunker_base")

    if "town_base" in stockpile_types:
        stockpile_types["town_base_1"] = stockpile_types.pop("town_base")

    return data


def migrate_v6_to_v7(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v6 to v7 (remove uesave from external_tools).

    V6 had: external_tools.{repak, umodel, uassetgui, uesave}
    V7 has: external_tools.{repak, umodel, uassetgui} (uesave removed)

    The uesave tool is no longer needed as SAV parsing is now handled
    natively by the fs-sav Rust library.

    Args:
        data: V6 configuration data

    Returns:
        V7 configuration data
    """
    if "external_tools" in data and isinstance(data["external_tools"], dict):
        data["external_tools"].pop("uesave", None)

    return data
