# fs-tools

Database and template tools for Foxhole Stockpiles.

These tools build and inspect the template/catalog databases that the main
`fs` scanner consumes. Regular users only need `fs`; mod creators and power
users use `fs-tools`.

## Usage

```bash
# Open the tools GUI (no subcommand)
fs-tools

# CLI commands
fs-tools build-catalog --pak War.pak --output ./catalog.json
fs-tools build-db --pak War.pak --catalog catalog.json --output ./db.h5
fs-tools generate-templates --help
fs-tools extract-assets --help
fs-tools add-icon --database db.h5 --icon icon.png --code MyItem --faction n --category item --mod vanilla --resolution 1080
fs-tools add-mod --help

# GUI tools
fs-tools visualize --database db.h5
fs-tools debug screenshot.png --database db.h5
```

Each subcommand forwards its arguments to the underlying tool, so
`fs-tools <command> --help` shows that tool's full option list.

## External tool requirements

- `repak` — PAK file extraction
- `umodel` — UE asset conversion
- `uassetgui` — uasset JSON conversion

Configure their paths via the fs configuration or the corresponding
environment variables.

## Relationship to the main package

`fs_tools` is a standalone top-level package (sibling to `fs_ocr`). It depends
on shared code in `foxhole_stockpiles` (models, enums, settings, i18n,
`TemplateManager`) and on `fs_ocr`. The main `foxhole_stockpiles` package must
**not** import from `fs_tools`.
