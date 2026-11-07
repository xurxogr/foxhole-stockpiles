"""Sequential dispatcher applying config migrations in order."""

from collections.abc import Callable
from typing import Any, Final

from foxhole_stockpiles.core.settings.config_migrator import steps_early, steps_late

# The step that upgrades a config from each version to the next one.
_MIGRATIONS: Final[dict[int, Callable[[dict[str, Any]], dict[str, Any]]]] = {
    1: steps_early.migrate_v1_to_v2,
    2: steps_early.migrate_v2_to_v3,
    3: steps_early.migrate_v3_to_v4,
    4: steps_early.migrate_v4_to_v5,
    5: steps_early.migrate_v5_to_v6,
    6: steps_early.migrate_v6_to_v7,
    7: steps_late.migrate_v7_to_v8,
    8: steps_late.migrate_v8_to_v9,
    9: steps_late.migrate_v9_to_v10,
    10: steps_late.migrate_v10_to_v11,
    11: steps_late.migrate_v11_to_v12,
    12: steps_late.migrate_v12_to_v13,
    13: steps_late.migrate_v13_to_v14,
    14: steps_late.migrate_v14_to_v15,
    15: steps_late.migrate_v15_to_v16,
    16: steps_late.migrate_v16_to_v17,
    17: steps_late.migrate_v17_to_v18,
}


class ConfigMigrator:
    """Handles migration of configuration data between versions."""

    CURRENT_VERSION: Final[int] = max(_MIGRATIONS) + 1

    @classmethod
    def apply_migrations(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Apply configuration migrations.

        Args:
            data (dict[str, Any]): Raw configuration data

        Returns:
            dict[str, Any]: Migrated configuration data. A version with no step,
                such as a newer one, is returned as it is.
        """
        if not isinstance(data, dict):
            return data

        data = dict(data)

        # Configs from before the version field are version 1.
        version = data.get("config_version", 1)
        while isinstance(version, int) and version in _MIGRATIONS:
            data = _MIGRATIONS[version](data)
            version += 1
            data["config_version"] = version

        return data
