"""Config migration steps v7 -> v14."""

from typing import Any


def migrate_v7_to_v8(data: dict[str, Any]) -> dict[str, Any]:
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


def migrate_v8_to_v9(data: dict[str, Any]) -> dict[str, Any]:
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


def migrate_v9_to_v10(data: dict[str, Any]) -> dict[str, Any]:
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


def migrate_v10_to_v11(data: dict[str, Any]) -> dict[str, Any]:
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


def migrate_v11_to_v12(data: dict[str, Any]) -> dict[str, Any]:
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


def migrate_v12_to_v13(data: dict[str, Any]) -> dict[str, Any]:
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


def migrate_v13_to_v14(data: dict[str, Any]) -> dict[str, Any]:
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
