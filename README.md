# Foxhole Stockpiles

[![CI](https://github.com/xurxogr/foxhole-stockpiles/workflows/CI/badge.svg)](https://github.com/xurxogr/foxhole-stockpiles/actions)
[![codecov](https://codecov.io/gh/xurxogr/foxhole-stockpiles/branch/main/graph/badge.svg)](https://codecov.io/gh/xurxogr/foxhole-stockpiles)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%20%7C%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Read your Foxhole stockpiles into clean, structured data — by screenshot (OCR), by clipboard, or straight from `.sav` files — and send the results wherever you want.**

> This README is for everyday use. For running with more control — installing
> from source, the command line, custom OCR databases, and configuration — see
> **[docs/advanced.md](docs/advanced.md)**. To work on the code, see
> **[CONTRIBUTING.md](CONTRIBUTING.md)**.

## What it does

Foxhole Stockpiles is a desktop app that turns a stockpile into machine-readable data (JSON / CSV / TSV) using **any of the three methods the game gives you**, all behind one app and one set of outputs:

- **OCR** — press a global hotkey to capture the live game window, or scan a screenshot file.
- **Clipboard** — copy a stockpile list from the in-game UI and it's parsed automatically.
- **SAV** — read stockpiles directly from Foxhole `.sav` world files.

Every method produces the same result, sent to your configured outputs: the console, a file, a webhook (e.g. Discord), or Google Sheets.

## Quick start (Windows)

No Python required — use the prebuilt app.

1. **Download `fs.exe`** from the [Releases page](https://github.com/xurxogr/foxhole-stockpiles/releases).
2. **Add the data file(s) for the method(s) you'll use.** They are *not* in the release — download them from the repository's [`data/` folder](https://github.com/xurxogr/foxhole-stockpiles/tree/main/data) and put them in a `data/` folder next to `fs.exe` (see the table below). SAV needs none.
3. **Run `fs.exe`** — with no arguments it opens the app (the GUI, with no console window).
4. **Set up a method** in **Settings → Input**, then **choose where results go** in **Settings → Output**.

That's all most people ever need.

## What you need for each method

You always need `fs.exe`. Some methods also need a data file (download links below):

| Method | What it needs |
|---|---|
| **SAV** (`.sav` files) | Nothing extra — works out of the box. |
| **Clipboard** | [`data/catalog.json`](https://github.com/xurxogr/foxhole-stockpiles/blob/main/data/catalog.json) — maps in-game item names to item codes. |
| **OCR** (screenshots / live capture) | [`data/fs_vanilla.h5`](https://github.com/xurxogr/foxhole-stockpiles/blob/main/data/fs_vanilla.h5) — the template database used to recognise icons. |

**These data files are not bundled in the release** — it contains only `fs.exe` and `fs-tools.exe`. Download the ones you need straight from the repository's [`data/` folder](https://github.com/xurxogr/foxhole-stockpiles/tree/main/data) (links above) and place them in a `data/` folder next to `fs.exe`.

> Only the second executable, `fs-tools.exe`, is for **generating** a catalog or **building** an OCR database yourself (e.g. for mods). The average user never needs it — see [docs/advanced.md](docs/advanced.md).

## Using each method

All three are configured in **Settings → Input** and share the same outputs.

### OCR — screenshots & live capture

Needs **`data/fs_vanilla.h5`**.

- **Live capture:** set a capture hotkey in **Settings → Input** (e.g. `F9`), open a stockpile in game, make the Foxhole window active (any monitor), and press the hotkey. The app grabs the window, scans it, and routes the result — no manual screenshotting.
- **Screenshot file:** scan an existing screenshot from the main window.
- *Chinese* screenshots additionally need Tesseract installed (see [docs/advanced.md](docs/advanced.md#tesseract-only-for-chinese-ocr)); every other language works out of the box.

### Clipboard

Needs **`data/catalog.json`**.

- Enable clipboard scanning in **Settings → Input**, then in game copy a stockpile's contents. The app parses it the moment you copy and routes the result.

### SAV — `.sav` world files

No extra files needed.

- Point the app at your Foxhole `MapData.sav` file in **Settings → Input**. You can scan it once or have it watch the file and re-scan when it changes.

## Where results go

A scan is sent to whichever outputs you enable in **Settings → Output**:

- **Console** — prints the result.
- **File** — writes JSON, CSV, or TSV to disk.
- **Webhook** — HTTP POST to a URL. **Sending to Discord?** Point a webhook at a Discord webhook URL.
- **Google Sheets** — appends rows to a sheet.

## Languages

The interface is available in English, German, Spanish, French, Portuguese, Russian, and Chinese. Change it in **Settings → General**.

You can also override individual translations next to the executable without rebuilding: create an `i18n/translations/<lang>.json` file beside `fs.exe` containing just the keys you want to change — they're merged over the bundled ones.

```
fs.exe
i18n/translations/en.json   # e.g. {"common": {"cancel": "My Custom Text"}}
```

> Translations were generated with AI assistance and may contain inaccuracies — corrections are very welcome (see [CONTRIBUTING.md](CONTRIBUTING.md#translations)).

## Performance & accuracy (OCR only)

These figures apply to the **OCR** method — screenshot recognition by the `fs-ocr` engine. The clipboard and `.sav` methods read exact game data, so they aren't subject to recognition accuracy.

Based on 1,000+ production OCR scans:

- **99.99% detection** — only 4 missed of 27,538 items — at **97.89% average confidence**.
- **1–2 seconds** per screenshot on a modern 6+ core CPU; speed scales with cores.
- Tuned for common resolutions: 1920×1080 (most tested), 1920×1200, 2560×1440, 3840×2160 (4K), 1600×1200, 1600×900, 1280×1024.

## Troubleshooting & support

- Check the [Troubleshooting guide](docs/troubleshooting.md) for common issues.
- Still stuck? [Open an issue on GitHub](https://github.com/xurxogr/foxhole-stockpiles/issues).

## Want more control?

Installing from source, the full command-line interface, building custom OCR databases (for mods or game updates), and configuration live in **[docs/advanced.md](docs/advanced.md)**. To contribute code or translations, see **[CONTRIBUTING.md](CONTRIBUTING.md)**.

## Credits

Inspired by the [FIR (Foxhole Item Recognition)](https://github.com/GICodeWarrior/fir) project — its catalog seeded ours until we built our own catalog generator, and its PAK-extraction approach inspired the image pipeline.

## License

MIT — see [LICENSE](LICENSE).

**Note:** the bundled `data/catalog.json` and template database contain data derived from Foxhole assets, which are property of [Siege Camp](https://www.siegecamp.com/). They're provided under Fair Use for personal use; you are responsible for complying with applicable terms of service.
