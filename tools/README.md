# Developer Tools

This directory contains utilities for developers working on the foxhole-stockpiles project.

## Stockpile Translations

**File:** `sync_stockpile_translations.py`

Lists the name of each stockpile type in every game language (en, de, fr, pt, ru, zh). It reads the blueprints and the `.locres` files directly from the game's PAK with `fs-assets`, and matches each `StockpileType` to its blueprint by CodeName.

It can also report structures that look like player-accessible stockpiles but aren't a known type, by scanning for patterns such as `ESimScreen::StorageFacility` or `GenericStockpileComponent`. This is useful after a game update.

### Requirements

- The game's `War-WindowsNoEditor.pak`, found in the Steam install or passed with `--pak`
- Project dependencies installed
- About 2 GB of free space for the temporary extraction

### Usage

```bash
# List every stockpile type with its translations
python tools/sync_stockpile_translations.py

# Show the text GUID of each stockpile type
python tools/sync_stockpile_translations.py --show-guids

# Report new stockpile types (useful after game updates)
python tools/sync_stockpile_translations.py --discover

# Use a specific game PAK
python tools/sync_stockpile_translations.py --pak /path/to/War-WindowsNoEditor.pak
```
