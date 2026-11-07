"""Config migration steps v7 -> v19."""

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
      options with no remaining consumer. (``screenshots_folder`` is kept
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


def migrate_v14_to_v15(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v14 to v15 (drop two dead settings).

    * ``scanner.early_exit_threshold`` had no consumer: nothing ever read it
      outside the config tab that displayed it (the claim in an earlier
      migration step that fs-tools' candidate inspector used it was stale).
    * ``sav_processing.emit_all_on_start`` was configurable via the GUI but
      never actually plumbed into ``SaveFileProcessor`` — both call sites
      that construct it hardcode their own ``True``/``False`` instead of
      reading the setting.

    Any stored values are dropped so they do not linger in the config file
    (the settings models forbid unknown fields).

    Args:
        data (dict[str, Any]): V14 configuration data.

    Returns:
        dict[str, Any]: V15 configuration data.
    """
    if "scanner" in data and isinstance(data["scanner"], dict):
        data["scanner"].pop("early_exit_threshold", None)

    if "sav_processing" in data and isinstance(data["sav_processing"], dict):
        data["sav_processing"].pop("emit_all_on_start", None)

    return data


def migrate_v15_to_v16(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v15 to v16 (drop the external tools and builder workers).

    The catalog and the icon-template database are now built by the
    ``fs-assets`` package, which reads the game PAK directly, so:

    * ``external_tools`` (repak, umodel, UAssetGUI paths) has no consumer.
    * ``database_builder.workers`` sized a Python process pool that no longer
      exists.

    Any stored values are dropped so they do not linger in the config file
    (the settings models forbid unknown fields).

    Args:
        data (dict[str, Any]): V15 configuration data.

    Returns:
        dict[str, Any]: V16 configuration data.
    """
    data.pop("external_tools", None)

    if "database_builder" in data and isinstance(data["database_builder"], dict):
        data["database_builder"].pop("workers", None)

    return data


# The handlers that draw stockpiles as images.
_IMAGE_HANDLER_TYPES = frozenset({"image", "discord"})


def _with_grouping(handler: dict[str, Any]) -> dict[str, Any]:
    """Replace the ``aggregate`` switch of an image handler with ``grouping``.

    Args:
        handler (dict[str, Any]): The settings of one handler.

    Returns:
        dict[str, Any]: A copy with ``grouping``, or the same handler if it has no
            ``aggregate`` or already has a ``grouping``.
    """
    if handler.get("type") not in _IMAGE_HANDLER_TYPES or "aggregate" not in handler:
        return handler
    updated = {key: value for key, value in handler.items() if key != "aggregate"}
    if "grouping" not in updated:
        updated["grouping"] = "all" if handler["aggregate"] is True else "none"
    return updated


def migrate_v16_to_v17(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v16 to v17 (image handlers group stockpiles in several ways).

    The ``aggregate`` switch of the ``image`` and ``discord`` handlers, which
    merged every stockpile of a send, becomes ``grouping``, which can also
    group them by hex or by place: ``true`` is ``"all"`` and ``false`` is
    ``"none"``. The old field is dropped, as the settings models forbid
    unknown fields.

    Args:
        data (dict[str, Any]): V16 configuration data.

    Returns:
        dict[str, Any]: V17 configuration data.
    """
    output = data.get("output")
    if not isinstance(output, dict) or not isinstance(output.get("handlers"), list):
        return data

    handlers = [
        {**config, "handler": _with_grouping(config["handler"])}
        if isinstance(config, dict) and isinstance(config.get("handler"), dict)
        else config
        for config in output["handlers"]
    ]
    return {**data, "output": {**output, "handlers": handlers}}


def _with_shared_selection(config: dict[str, Any]) -> dict[str, Any]:
    """Move the grouping of an image handler to its output.

    Args:
        config (dict[str, Any]): One entry of ``output.handlers``.

    Returns:
        dict[str, Any]: A copy with ``grouping`` and ``group_name`` beside the
            handler, or the same entry if its handler does not draw images.
    """
    handler = config.get("handler")
    if not isinstance(handler, dict) or handler.get("type") not in _IMAGE_HANDLER_TYPES:
        return config
    moved = {"grouping": "grouping", "headline": "group_name"}
    updated = {**config, "handler": {k: v for k, v in handler.items() if k not in moved}}
    for old_key, new_key in moved.items():
        if old_key in handler and new_key not in updated:
            updated[new_key] = handler[old_key]
    return updated


def migrate_v17_to_v18(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v17 to v18 (every output filters and groups its stockpiles).

    Grouping was a setting of the ``image`` and ``discord`` handlers; it now
    belongs to every output, beside its handler, as does the new
    ``public_stockpiles`` filter. For those two handlers, ``grouping`` moves
    up a level and ``headline``, the name of each merge, becomes
    ``group_name``.

    Args:
        data (dict[str, Any]): V17 configuration data.

    Returns:
        dict[str, Any]: V18 configuration data.
    """
    output = data.get("output")
    if not isinstance(output, dict) or not isinstance(output.get("handlers"), list):
        return data

    handlers = [
        _with_shared_selection(config) if isinstance(config, dict) else config
        for config in output["handlers"]
    ]
    return {**data, "output": {**output, "handlers": handlers}}


def migrate_v18_to_v19(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate from v18 to v19 (merges are named by what they share).

    The ``group_name`` of each output is dropped: a merge is now always named
    after its hex and its place, so a template had nothing left to add.

    Args:
        data (dict[str, Any]): V18 configuration data.

    Returns:
        dict[str, Any]: V19 configuration data.
    """
    output = data.get("output")
    if not isinstance(output, dict) or not isinstance(output.get("handlers"), list):
        return data

    handlers = [
        {key: value for key, value in config.items() if key != "group_name"}
        if isinstance(config, dict)
        else config
        for config in output["handlers"]
    ]
    return {**data, "output": {**output, "handlers": handlers}}
