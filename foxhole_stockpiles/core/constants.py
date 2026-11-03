"""Shared constants used across the runtime and tooling apps."""

# Repository data folder where users download catalog.json and the template
# databases (catalog.json, fs_vanilla.h5, etc.). Surfaced by the "Download"
# buttons next to the catalog and database path fields in both apps.
DATA_DOWNLOAD_URL = "https://github.com/xurxogr/foxhole-stockpiles/tree/main/data"

# Seconds between two reads of a monitored source (clipboard, .sav file).
MIN_POLL_INTERVAL = 0.1
MAX_POLL_INTERVAL = 60.0
