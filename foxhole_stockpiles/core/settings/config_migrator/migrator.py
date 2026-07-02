"""Sequential dispatcher applying config migrations in order."""

from typing import Any

from foxhole_stockpiles.core.settings.config_migrator import steps_early, steps_late


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
            data = steps_early.migrate_v1_to_v2(data)
            data["config_version"] = 2
            version = 2

        if version == 2:
            data = steps_early.migrate_v2_to_v3(data)
            data["config_version"] = 3
            version = 3

        if version == 3:
            data = steps_early.migrate_v3_to_v4(data)
            data["config_version"] = 4
            version = 4

        if version == 4:
            data = steps_early.migrate_v4_to_v5(data)
            data["config_version"] = 5
            version = 5

        if version == 5:
            data = steps_early.migrate_v5_to_v6(data)
            data["config_version"] = 6
            version = 6

        if version == 6:
            data = steps_early.migrate_v6_to_v7(data)
            data["config_version"] = 7
            version = 7

        if version == 7:
            data = steps_late.migrate_v7_to_v8(data)
            data["config_version"] = 8
            version = 8

        if version == 8:
            data = steps_late.migrate_v8_to_v9(data)
            data["config_version"] = 9
            version = 9

        if version == 9:
            data = steps_late.migrate_v9_to_v10(data)
            data["config_version"] = 10
            version = 10

        if version == 10:
            data = steps_late.migrate_v10_to_v11(data)
            data["config_version"] = 11
            version = 11

        if version == 11:
            data = steps_late.migrate_v11_to_v12(data)
            data["config_version"] = 12
            version = 12

        if version == 12:
            data = steps_late.migrate_v12_to_v13(data)
            data["config_version"] = 13
            version = 13

        if version == 13:
            data = steps_late.migrate_v13_to_v14(data)
            data["config_version"] = 14

        return data
