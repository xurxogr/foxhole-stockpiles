# Developer Tools

This directory contains utilities for developers working on the foxhole-stockpiles project.

## Stockpile Translations Sync

**File:** `sync_stockpile_translations.py`

Syncs the stockpile type translations of the clipboard parser (`_TYPE_ALIASES` in `foxhole_stockpiles/services/clipboard_parser/type_aliases.py`) with the game. It reads the blueprints and the `.locres` files directly from the game's PAK with `fs-assets`, matches each `StockpileType` to its blueprint by CodeName, and reports the names missing from the table.

It can also report structures that look like player-accessible stockpiles but aren't a known type, by scanning for patterns such as `ESimScreen::StorageFacility` or `GenericStockpileComponent`. This is useful after a game update.

### Requirements

- The game's `War-WindowsNoEditor.pak`, found in the Steam install or passed with `--pak`
- Project dependencies installed
- About 2 GB of free space for the temporary extraction

### Usage

```bash
# Compare the table with the game
python tools/sync_stockpile_translations.py

# Add the names the table lacks, then format the file
python tools/sync_stockpile_translations.py --update
ruff format foxhole_stockpiles/services/clipboard_parser/type_aliases.py

# Show the text GUID of each stockpile type
python tools/sync_stockpile_translations.py --show-guids

# Report new stockpile types (useful after game updates)
python tools/sync_stockpile_translations.py --discover

# Use a specific game PAK
python tools/sync_stockpile_translations.py --pak /path/to/War-WindowsNoEditor.pak
```

`--update` only adds names. Names the game doesn't have are reported but kept, because they may be hand-added or come from another game version.
