"""Parse Foxhole in-game stockpile clipboard exports into runtime ``Stockpile``.

The in-game "copy stockpile" feature places a text block on the clipboard with
this shape::

    Hex - Town - Type - Name - X: <x> Y: <y>,<UTC timestamp>
    <Item Display Name> (Crate),<quantity>
    ...

    <next group>
    ...

Lines are grouped by category, each group separated by a blank line, and the
groups always appear in the same order. Each item line carries an explicit
crate suffix when crated. Only items with a quantity of 1 or more are kept.

**Localization.** The export is in the game's language: item names, the crate
suffix, and the stockpile type are all localized. The parser therefore:

* maps item names against every locale in the catalog and *detects* the export
  language from the items themselves (the language that explains the most
  lines), so the rest of the file is read in that language;
* falls back to English per item, because untranslated items appear in English
  even within a localized export;
* detects "crated" structurally — an item is crated when the name only resolves
  after dropping its trailing parenthetical (the localized crate word) — so no
  per-language crate vocabulary is needed, and inherent parentheticals such as
  "(Small)" are preserved.

This module is the clipboard analogue of :mod:`services.scanner`: it adapts an
externally-defined format into the runtime :class:`Stockpile` model. It is pure
(no I/O): callers pass the clipboard text and a :class:`ClipboardCodeMap` built
from the item catalog. ``parse_clipboard`` returns ``None`` when the text is not
a stockpile export, which is the gate the monitor uses to ignore unrelated
clipboard content.
"""

from __future__ import annotations

from foxhole_stockpiles.services.clipboard_parser.code_map import (
    CatalogCode,
    ClipboardCodeMap,
    build_code_map,
    build_code_map_from_file,
)
from foxhole_stockpiles.services.clipboard_parser.items import _infer_faction  # noqa: F401
from foxhole_stockpiles.services.clipboard_parser.parser import parse_clipboard

__all__ = [
    "CatalogCode",
    "ClipboardCodeMap",
    "build_code_map",
    "build_code_map_from_file",
    "parse_clipboard",
]
