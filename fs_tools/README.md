# fs-tools

Database and template tools for Foxhole Stockpiles.

These tools build and inspect the template/catalog databases that the main
`fs` scanner consumes. Regular users only need `fs`; mod creators and power
users use `fs-tools`.

## Usage

```bash
# Open the tools GUI (no subcommand)
fs-tools

# GUI tools
fs-tools visualize --database db.h5
fs-tools debug screenshot.png --database db.h5
```

Run `fs-tools <command> --help` for the full option list of each command.

## Catalog and template database

The catalog and the icon-template database are built by the external
[`fs-assets`](https://pypi.org/project/fs-assets/) package (installed with fs),
which reads the game PAK directly — no external tools are needed. The tools GUI
(*Build Catalog* and *Database Builder (Icon Import)*) is backed by it; from the
command line:

```bash
fs-assets build-catalog --pak War-WindowsNoEditor.pak -o catalog.json
fs-assets add-mod --pak War-WindowsNoEditor.pak --catalog catalog.json --db templates.h5
fs-assets check-paks --catalog catalog.json --pak Mod.pak
fs-assets add-mod --pak Mod.pak --vanilla-pak War-WindowsNoEditor.pak --catalog catalog.json --db templates.h5 --mod-name my-mod
fs-assets modify-icon --db templates.h5 --code RifleW --faction wardens --category item --icon rifle.png
```

`modify-icon` adds a single icon (PNG or game `.uasset`), resized and composited
like the game-built templates; `--replace` / `--remove` replace or remove it, and
`--resolution 1080,1440` limits it to those resolutions (default: all).

The Database Visualizer, Database Info and Debug Image Viewer read and edit the
database through `fs_tools/core/template_store.py`, a thin wrapper over
`fs-assets`; the visualizer's replace/delete edit one template at the current
resolution.

## Relationship to the main package

`fs_tools` is a standalone top-level package (sibling to `fs_ocr`). It depends
on shared code in `foxhole_stockpiles` (models, enums, settings, i18n), on
`fs_ocr` and on `fs_assets`. The main `foxhole_stockpiles` package must
**not** import from `fs_tools`.
