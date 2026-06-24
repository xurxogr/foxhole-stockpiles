"""Field rule engine for projecting the catalog onto smaller variants.

The full catalog (``catalog.json``) carries every field extracted from the game
blueprints. A *rule set* projects each item down to a chosen subset of fields by
applying an ordered list of **include/exclude rules** over dotted field paths.

Two consumers read the catalog and define the **required minimum** any usable
rule set must keep:

* the template DB build, via
  :meth:`foxhole_stockpiles.models.catalog_item.CatalogItem.from_catalog`, and
* the clipboard conversion, via
  :func:`foxhole_stockpiles.services.clipboard_parser.build_code_map`.

:data:`REQUIRED_PATHS` lists exactly those fields; :func:`missing_required_paths`
checks a rule set against them so the GUI can warn when a projection would break
the app. The ``FS`` preset is the rule set whose output equals that minimum.

Evaluation semantics:

* Items are flattened to dotted leaf paths, descending into dicts only (scalars
  and lists are leaves at their path).
* A rule's pattern *covers* a leaf when it matches the leaf or an ancestor of it
  (so ``include ItemProfileData`` keeps the whole subtree). Segment globs: ``*``
  matches one segment, ``**`` matches one or more segments.
* A leaf is kept iff the **last** rule covering it is ``include`` (the default,
  when no rule covers it, is to keep). An empty rule set therefore keeps
  everything (the ``FULL`` preset).
"""

from copy import deepcopy
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict


class RuleAction(StrEnum):
    """Whether a rule keeps (include) or drops (exclude) the fields it covers."""

    INCLUDE = "include"
    EXCLUDE = "exclude"


class CatalogRule(BaseModel):
    """A single include/exclude rule over a dotted field path pattern."""

    model_config = ConfigDict(frozen=True)

    action: RuleAction
    pattern: str


class CatalogRuleSet(BaseModel):
    """An ordered list of rules, optionally named, applied to the catalog."""

    name: str | None = None
    rules: list[CatalogRule] = []


class CatalogPreset(StrEnum):
    """A built-in rule-set preset the GUI dropdown can seed the editor with."""

    FULL = "full"
    FS = "fs"

    @classmethod
    def from_string(cls, value: str | None = None) -> "CatalogPreset":
        """Convert a string to a CatalogPreset, never returns None.

        Args:
            value (str | None): The string to convert (preset value or name).

        Returns:
            CatalogPreset: The matching preset, defaulting to FULL for
                invalid/empty input.
        """
        if not value:
            return cls.FULL

        normalized = value.strip().lower()
        for preset in cls:
            if normalized in (preset.value, preset.name.lower()):
                return preset
        return cls.FULL


# Field paths the two consumers read. Any rule set that excludes one of these
# would break the DB build or clipboard conversion, so the GUI warns about it.
#
#   CatalogItem.from_catalog -> CodeName, FactionVariant, Icon, SubTypeIcon,
#                               VehicleProfileType, ChassisName, ItemCategory,
#                               ItemProfileData.bIsCratable, ShippableInfo,
#                               ShippableInfo.bAllowPackagingToCrate,
#                               ProductionCategories.MassProductionFactory
#   clipboard build_code_map -> CodeName, FactionVariant, DisplayName,
#                               DisplayNameLocales
REQUIRED_PATHS: tuple[str, ...] = (
    "CodeName",
    "FactionVariant",
    "DisplayName",
    "DisplayNameLocales",
    "Icon",
    "SubTypeIcon",
    "VehicleProfileType",
    "ChassisName",
    "ItemCategory",
    "ItemProfileData.bIsCratable",
    "ShippableInfo",
    "ShippableInfo.bAllowPackagingToCrate",
    "ProductionCategories.MassProductionFactory",
)

# The FS preset: drop everything, then re-include exactly the required minimum.
# ShippableInfo is kept whole (it is a scalar marker on some items) but reduced to
# the one used sub-key when it is a dict.
_FS_RULES: tuple[tuple[RuleAction, str], ...] = (
    (RuleAction.EXCLUDE, "**"),
    (RuleAction.INCLUDE, "CodeName"),
    (RuleAction.INCLUDE, "FactionVariant"),
    (RuleAction.INCLUDE, "DisplayName"),
    (RuleAction.INCLUDE, "DisplayNameLocales"),
    (RuleAction.INCLUDE, "Icon"),
    (RuleAction.INCLUDE, "SubTypeIcon"),
    (RuleAction.INCLUDE, "VehicleProfileType"),
    (RuleAction.INCLUDE, "ChassisName"),
    (RuleAction.INCLUDE, "ItemCategory"),
    (RuleAction.INCLUDE, "ItemProfileData.bIsCratable"),
    (RuleAction.INCLUDE, "ProductionCategories.MassProductionFactory"),
    (RuleAction.INCLUDE, "ShippableInfo"),
    (RuleAction.EXCLUDE, "ShippableInfo.**"),
    (RuleAction.INCLUDE, "ShippableInfo.bAllowPackagingToCrate"),
)


def preset_ruleset(preset: CatalogPreset) -> CatalogRuleSet:
    """Return the seed rule set for a preset.

    Args:
        preset (CatalogPreset): The preset to build a rule set for.

    Returns:
        CatalogRuleSet: An empty rule set for FULL (keep everything), or the
            required-minimum rule set for FS.
    """
    if preset is CatalogPreset.FULL:
        return CatalogRuleSet(name=CatalogPreset.FULL.value, rules=[])
    return CatalogRuleSet(
        name=CatalogPreset.FS.value,
        rules=[CatalogRule(action=action, pattern=pattern) for action, pattern in _FS_RULES],
    )


def detect_preset(ruleset: CatalogRuleSet) -> CatalogPreset | None:
    """Return the preset a rule set's rules match, or None if it is custom.

    Only the rules are compared (the name is ignored), so an edited-but-equivalent
    rule set is still recognised as its preset.

    Args:
        ruleset (CatalogRuleSet): The rule set to classify.

    Returns:
        CatalogPreset | None: The matching preset, or None for a custom rule set.
    """
    for preset in CatalogPreset:
        if ruleset.rules == preset_ruleset(preset).rules:
            return preset
    return None


def _glob(pattern_segs: list[str], path_segs: list[str]) -> bool:
    """Match path segments against pattern segments (``*`` = 1, ``**`` = 1+).

    Args:
        pattern_segs (list[str]): The pattern split on ".".
        path_segs (list[str]): The path split on ".".

    Returns:
        bool: True if the pattern matches the whole path.
    """
    if not pattern_segs:
        return not path_segs

    head, *rest = pattern_segs
    if head == "**":
        if not path_segs:
            return False
        # Consume one segment for "**" and either stop or keep consuming.
        return _glob(rest, path_segs[1:]) or _glob(pattern_segs, path_segs[1:])

    if not path_segs:
        return False
    if head == "*" or head == path_segs[0]:
        return _glob(rest, path_segs[1:])
    return False


def _covers(pattern_segs: list[str], path_segs: list[str]) -> bool:
    """Whether a pattern covers a leaf path or any of its ancestors.

    Ancestor coverage gives subtree semantics: ``include ItemProfileData`` covers
    the leaf ``ItemProfileData.bIsCratable``.

    Args:
        pattern_segs (list[str]): The pattern split on ".".
        path_segs (list[str]): The leaf path split on ".".

    Returns:
        bool: True if the pattern matches the path or a prefix of it.
    """
    return any(_glob(pattern_segs, path_segs[:k]) for k in range(1, len(path_segs) + 1))


def _decide(rules: list[CatalogRule], path_segs: list[str]) -> bool:
    """Decide whether a leaf path is kept (last covering rule wins).

    Args:
        rules (list[CatalogRule]): The ordered rules.
        path_segs (list[str]): The leaf path split on ".".

    Returns:
        bool: True to keep the leaf (default when no rule covers it).
    """
    keep = True
    for rule in rules:
        if _covers(rule.pattern.split("."), path_segs):
            keep = rule.action is RuleAction.INCLUDE
    return keep


def _leaf_paths(
    item: dict[str, Any], prefix: tuple[str, ...] = ()
) -> list[tuple[tuple[str, ...], Any]]:
    """Flatten a dict into (path, value) leaves, descending into dicts only.

    Args:
        item (dict[str, Any]): The dict to flatten.
        prefix (tuple[str, ...]): The path accumulated so far.

    Returns:
        list[tuple[tuple[str, ...], Any]]: Leaf paths and their values.
    """
    leaves: list[tuple[tuple[str, ...], Any]] = []
    for key, value in item.items():
        path = prefix + (key,)
        if isinstance(value, dict) and value:
            leaves.extend(_leaf_paths(value, path))
        else:
            leaves.append((path, value))
    return leaves


def _unflatten(leaves: list[tuple[tuple[str, ...], Any]]) -> dict[str, Any]:
    """Rebuild a nested dict from kept (path, value) leaves.

    Args:
        leaves (list[tuple[tuple[str, ...], Any]]): The kept leaves.

    Returns:
        dict[str, Any]: The reassembled (deep-copied) dict.
    """
    root: dict[str, Any] = {}
    for path, value in leaves:
        node = root
        for segment in path[:-1]:
            node = node.setdefault(segment, {})
        node[path[-1]] = deepcopy(value)
    return root


def _project_item(item: dict[str, Any], rules: list[CatalogRule]) -> dict[str, Any]:
    """Project a single item through the rules.

    Args:
        item (dict[str, Any]): A full catalog entry.
        rules (list[CatalogRule]): The ordered rules.

    Returns:
        dict[str, Any]: A new dict containing only the kept leaves.
    """
    kept = [(path, value) for path, value in _leaf_paths(item) if _decide(rules, list(path))]
    return _unflatten(kept)


def apply_rules(
    catalog: list[dict[str, Any]],
    ruleset: CatalogRuleSet,
) -> list[dict[str, Any]]:
    """Project a full catalog through a rule set.

    Args:
        catalog (list[dict[str, Any]]): The full catalog entries.
        ruleset (CatalogRuleSet): The rule set to apply.

    Returns:
        list[dict[str, Any]]: The catalog unchanged when the rule set is empty
            (keep everything), or a new list of projected entries otherwise.
    """
    if not ruleset.rules:
        return catalog
    return [_project_item(item, ruleset.rules) for item in catalog]


def missing_required_paths(ruleset: CatalogRuleSet) -> list[str]:
    """Return the required field paths a rule set would exclude.

    Args:
        ruleset (CatalogRuleSet): The rule set to validate.

    Returns:
        list[str]: The required paths that would be dropped (empty when the rule
            set keeps the full required minimum).
    """
    return [path for path in REQUIRED_PATHS if not _decide(ruleset.rules, path.split("."))]


def save_ruleset(path: Path, ruleset: CatalogRuleSet) -> None:
    """Export a rule set to a JSON file.

    Args:
        path (Path): Destination file path.
        ruleset (CatalogRuleSet): The rule set to write.
    """
    path.write_text(ruleset.model_dump_json(indent=2), encoding="utf-8")


def load_ruleset(path: Path) -> CatalogRuleSet:
    """Import a rule set from a JSON file.

    Args:
        path (Path): Source file path.

    Returns:
        CatalogRuleSet: The parsed rule set.

    Raises:
        ValueError: If the file is not a valid rule set.
    """
    try:
        return CatalogRuleSet.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 - surface any parse/validation error uniformly
        raise ValueError(f"Invalid rule set file: {e}") from e
