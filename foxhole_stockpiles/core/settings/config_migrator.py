"""Configuration migration logic for upgrading old config formats."""

from typing import Any


class ConfigMigrator:
    """Handles migration of configuration data between versions."""

    CURRENT_VERSION = 14

    @classmethod
    def apply_migrations(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Apply configuration migrations.

        Args:
            data: Raw configuration data

        Returns:
            Migrated configuration data
        """
        if not isinstance(data, dict):
            return data

        # Make a copy to avoid modifying the original
        data = dict(data)

        # Determine config version (default to 1 for old configs without version field)
        version = data.get("config_version", 1)

        # Apply migrations sequentially
        if version == 1:
            data = cls._migrate_v1_to_v2(data)
            data["config_version"] = 2
            version = 2

        if version == 2:
            data = cls._migrate_v2_to_v3(data)
            data["config_version"] = 3
            version = 3

        if version == 3:
            data = cls._migrate_v3_to_v4(data)
            data["config_version"] = 4
            version = 4

        if version == 4:
            data = cls._migrate_v4_to_v5(data)
            data["config_version"] = 5
            version = 5

        if version == 5:
            data = cls._migrate_v5_to_v6(data)
            data["config_version"] = 6
            version = 6

        if version == 6:
            data = cls._migrate_v6_to_v7(data)
            data["config_version"] = 7
            version = 7

        if version == 7:
            data = cls._migrate_v7_to_v8(data)
            data["config_version"] = 8
            version = 8

        if version == 8:
            data = cls._migrate_v8_to_v9(data)
            data["config_version"] = 9
            version = 9

        if version == 9:
            data = cls._migrate_v9_to_v10(data)
            data["config_version"] = 10
            version = 10

        if version == 10:
            data = cls._migrate_v10_to_v11(data)
            data["config_version"] = 11
            version = 11

        if version == 11:
            data = cls._migrate_v11_to_v12(data)
            data["config_version"] = 12
            version = 12

        if version == 12:
            data = cls._migrate_v12_to_v13(data)
            data["config_version"] = 13
            version = 13

        if version == 13:
            data = cls._migrate_v13_to_v14(data)
            data["config_version"] = 14

        return data

    @staticmethod
    def _migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
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

    @staticmethod
    def _migrate_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
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

    @staticmethod
    def _migrate_v3_to_v4(data: dict[str, Any]) -> dict[str, Any]:
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

    @staticmethod
    def _migrate_v4_to_v5(data: dict[str, Any]) -> dict[str, Any]:
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

    @staticmethod
    def _migrate_v5_to_v6(data: dict[str, Any]) -> dict[str, Any]:
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

    @staticmethod
    def _migrate_v6_to_v7(data: dict[str, Any]) -> dict[str, Any]:
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

    @staticmethod
    def _migrate_v7_to_v8(data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from v7 to v8 (drop OCR/template/advanced-scanner settings).

        These values are no longer user-configurable: the OCR geometry and
        template-generation settings now use fixed model defaults, and the
        custom model name, tessdata path, and icon-matching thresholds are
        hardcoded. Any stored values are removed so they no longer linger in
        ``.fs_config``.

        V7 had: top-level ``ocr`` and ``templates`` sections, plus
            ``scanner.{custom_model, tessdata_path, max_ncc_candidates,
            phash_threshold, ncc_tiebreaker_threshold}``.
        V8 has: none of the above.

        Args:
            data (dict[str, Any]): V7 configuration data.

        Returns:
            dict[str, Any]: V8 configuration data.
        """
        # Remove top-level sections that are no longer part of settings.
        data.pop("ocr", None)
        data.pop("templates", None)

        # Remove scanner fields that are now fixed defaults.
        if "scanner" in data and isinstance(data["scanner"], dict):
            for field_name in (
                "custom_model",
                "tessdata_path",
                "max_ncc_candidates",
                "phash_threshold",
                "ncc_tiebreaker_threshold",
            ):
                data["scanner"].pop(field_name, None)

        return data

    @staticmethod
    def _migrate_v8_to_v9(data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from v8 to v9 (drop api_server.web_icon_mod).

        The web interface no longer serves item icons from the template
        database, so the icon mod is no longer configurable. Any stored value
        is removed so it does not linger in ``.fs_config`` (the settings model
        forbids unknown fields).

        V8 had: ``api_server.web_icon_mod``.
        V9 has: no such field.

        Args:
            data (dict[str, Any]): V8 configuration data.

        Returns:
            dict[str, Any]: V9 configuration data.
        """
        if "api_server" in data and isinstance(data["api_server"], dict):
            data["api_server"].pop("web_icon_mod", None)

        return data

    @staticmethod
    def _migrate_v9_to_v10(data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from v9 to v10 (drop the FastAPI server sections).

        The runtime no longer hosts a REST API; scanning happens locally from a
        captured screenshot. The ``api_server`` and ``api_auth`` sections are
        removed so they do not linger in ``.fs_config``.

        V9 had: top-level ``api_server`` and ``api_auth`` sections.
        V10 has: neither (a new ``capture`` section uses its model defaults).

        Args:
            data (dict[str, Any]): V9 configuration data.

        Returns:
            dict[str, Any]: V10 configuration data.
        """
        data.pop("api_server", None)
        data.pop("api_auth", None)

        return data

    @staticmethod
    def _migrate_v10_to_v11(data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from v10 to v11 (drop dead settings no longer consumed).

        Two cleanups:

        * The ``stockpile_types`` section and its config tab are removed —
          type detection happens inside the external ``fs-ocr`` engine, so the
          user-editable aliases had no effect.
        * The dead ``scanner`` knobs ``template_cache_size``, ``debug_mode``
          and ``extract_icons`` are removed — they were old in-repo-engine
          options with no remaining consumer. (``early_exit_threshold`` is kept
          for ``fs_tools``' candidate inspector; ``screenshots_folder`` is kept
          and now drives screenshot saving in the capture flow.)

        Any stored values are dropped so they do not linger in ``.fs_config``
        (the settings models forbid unknown fields).

        Args:
            data (dict[str, Any]): V10 configuration data.

        Returns:
            dict[str, Any]: V11 configuration data.
        """
        data.pop("stockpile_types", None)

        if "scanner" in data and isinstance(data["scanner"], dict):
            for field_name in (
                "template_cache_size",
                "debug_mode",
                "extract_icons",
            ):
                data["scanner"].pop(field_name, None)

        return data

    @staticmethod
    def _migrate_v11_to_v12(data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from v11 to v12 (drop the dead notifications section).

        The ``notifications`` section, its config tab and the Discord notifier
        were leftovers from the removed REST-server/event-bus architecture: no
        runtime code ever instantiated the notification service or emitted the
        events it listened for, so configured notifications were never sent.
        The whole stack is removed; any stored value is dropped so it does not
        linger in ``.fs_config`` (the settings models forbid unknown fields).

        Args:
            data (dict[str, Any]): V11 configuration data.

        Returns:
            dict[str, Any]: V12 configuration data.
        """
        data.pop("notifications", None)

        return data

    @staticmethod
    def _migrate_v12_to_v13(data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from v12 to v13 (drop the GUI ``config_level`` setting).

        The basic/advanced/developer configuration-level system is removed: it
        existed to hide the OCR/template internals that have since moved to the
        external ``fs-ocr`` engine and the ``fs-tools`` package, so it no longer
        guards anything. All settings tabs are now always visible. Any stored
        ``gui.config_level`` value is dropped so it does not linger in
        ``.fs_config`` (the settings models forbid unknown fields).

        Args:
            data (dict[str, Any]): V12 configuration data.

        Returns:
            dict[str, Any]: V13 configuration data.
        """
        if "gui" in data and isinstance(data["gui"], dict):
            data["gui"].pop("config_level", None)

        return data

    @staticmethod
    def _migrate_v13_to_v14(data: dict[str, Any]) -> dict[str, Any]:
        """Migrate from v13 to v14 (rework webhook 'forward' auth into 'header').

        The webhook ``forward`` auth type was a leftover from the removed REST
        server, where it forwarded an inbound client's ``Authorization`` header
        to the webhook. With no server, the new ``header`` auth type simply
        places the configured token in a user-chosen header. Each webhook
        handler is updated in place:

        * ``auth_type: "forward"`` becomes ``auth_type: "header"``.
        * the ``client_auth_header`` field is renamed to ``auth_header``.

        Any stored ``client_auth_header`` value is moved so it does not linger in
        ``.fs_config`` (the settings models forbid unknown fields).

        Args:
            data (dict[str, Any]): V13 configuration data.

        Returns:
            dict[str, Any]: V14 configuration data.
        """
        output = data.get("output")
        if not isinstance(output, dict):
            return data

        handlers = output.get("handlers")
        if not isinstance(handlers, list):
            return data

        for handler_config in handlers:
            if not isinstance(handler_config, dict):
                continue
            handler = handler_config.get("handler")
            if not isinstance(handler, dict) or handler.get("type") != "webhook":
                continue

            if handler.get("auth_type") == "forward":
                handler["auth_type"] = "header"

            if "client_auth_header" in handler:
                handler["auth_header"] = handler.pop("client_auth_header")

        return data
