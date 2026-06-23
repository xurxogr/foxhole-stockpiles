# Troubleshooting Guide

Common issues and solutions for the Foxhole Stockpile Scanner.

## Installation Issues

### Python Version Error

**Problem:**
```
ERROR: This package requires Python 3.12 or higher
```

**Solution:**
Check your Python version and upgrade if needed:
```bash
python --version  # Should be 3.12 or higher

# On Ubuntu/Debian
sudo apt update
sudo apt install python3.12

# On macOS with Homebrew
brew install python@3.12
```

### OCR Engine Not Available

**Problem:**
Scans fail because the OCR engine cannot start.

**Solution:**
OCR is handled by the external `fs-ocr` Rust engine (installed from PyPI).
Tesseract is consumed internally by that engine and is no longer a direct
dependency of the runtime. Verify the engine is installed:
```bash
pip show fs-ocr
```

If it is missing, reinstall the project dependencies so `fs-ocr` is pulled in.

## Scanner Issues

### Database Not Found

**Problem:**
```
FileNotFoundError: Database file not found: foxhole_templates.h5
```

**Solution:**
1. Build the database first:
   ```bash
   fs-tools build-db \
     --catalog catalog.json \
     --templates processed_templates/ \
     --database foxhole_templates.h5
   ```

2. Or specify the correct path:
   ```bash
   fs scan --database /path/to/database.h5 --image screenshot.png
   ```

3. Or set via environment variable:
   ```bash
   export FS_SCANNER__DATABASE_PATH=/path/to/database.h5
   ```

### No Items Detected

**Problem:**
Scanner completes but finds 0 items in the screenshot.

**Possible Causes & Solutions:**

1. **Wrong resolution database**
   - Verify your screenshot resolution matches the database
   - Browse the database contents (resolutions, mods, templates) with the
     visualizer: `fs-tools visualize --database templates.h5`
   - Rebuild database with correct resolution

2. **Screenshot quality**
   - Use native game resolution screenshots (1080p, 1440p, 2160p)
   - Avoid compressed or scaled images
   - Use PNG format (lossless compression)

3. **Incorrect screenshot type**
   - Scanner expects stockpile inventory screenshots
   - Screenshot must show the stockpile grid with items
   - Title bar must be visible

4. **Resolution mismatch**
   - Matching is most accurate when the screenshot resolution matches a template resolution
   - Use a standard, unscaled screenshot (no display scaling / cropping)
   - The pHash/NCC matching thresholds are fixed defaults as of config v10 and are no longer user-tunable

5. **Debug the detection**
   ```bash
   # Verbose scan logs (per-icon match details)
   fs scan --database templates.h5 --image screenshot.png --verbose

   # Or inspect detection visually against the database
   fs-tools debug screenshot.png --database templates.h5
   ```
   The debug viewer shows the detected icon regions and their best matches.

### Some Items Not Detected

**Problem:**
Scanner detects most items but misses some specific ones.

**Solution:**

1. **Check confidence scores in output**
   - Look for warnings in debug logs about low-confidence detections
   - Check the `errors` field in the output for "No match found" messages

2. **Verify the item exists in database**
   ```bash
   # Browse templates by code / resolution / mod in the visualizer
   fs-tools visualize --database templates.h5
   ```

3. **Screenshot quality issues**
   - Ensure the screenshot resolution matches a database resolution
   - Avoid screenshots with compression artifacts
   - Make sure items are fully visible (not cut off)

4. **Resolution mismatch**
   - The scanner performs best when screenshot resolution exactly matches a database resolution
   - Supported resolutions: 720p, 1080p, 1440p, 2160p
   - Check what resolutions are in your database:
     ```bash
     # The visualizer lists every resolution group and mod in the database
     fs-tools visualize --database templates.h5
     ```

**Note:** The pHash and NCC matching thresholds are fixed defaults as of config v10 and
are no longer user-tunable. If items are consistently missed, the most common fixes are
using a screenshot at a supported resolution and rebuilding the database for the correct
mod version.

See [Configuration Guide](configuration.md) for details on scanner settings.

### Diagnosing Unknown Items

**Problem:**
Some items in the scan result show as `"code": "Unknown"` with `"confidence": 0.0`.

**Understanding the Matching Pipeline:**

The scanner uses a two-phase matching process:
1. **pHash pre-filtering** - Fast perceptual hash comparison filters candidates by Hamming distance (default threshold: 12)
2. **NCC matching** - Normalized Cross-Correlation on remaining candidates finds the best match

An item becomes "Unknown" when:
- No candidates pass the pHash filter, OR
- The item doesn't exist in the database for the detected category/crated status

**Step-by-Step Diagnosis:**

1. **Check the errors field in the output**
   ```bash
   fs scan --image screenshot.png --output-destination return 2>&1 | grep -A5 '"errors"'
   ```

   Look for messages like:
   ```
   "Group 1, index 64: No match found. Quantity: 21, crated: True. Best match: MGTW (crated) (confidence: 0.620)"
   ```

   This tells you:
   - The icon position (group 1, index 64)
   - The quantity detected (21)
   - Whether it's crated (True)
   - The best candidate found and its confidence score

2. **Inspect the detection visually**
   ```bash
   fs-tools debug screenshot.png --database templates.h5
   ```

   The debug viewer shows each detected icon region alongside its best database
   matches and their confidence scores, so you can see what the failing icon
   was compared against.

3. **Check if the item exists in the database**
   ```bash
   # Browse templates by code / resolution / mod in the visualizer
   fs-tools visualize --database templates.h5
   ```

   Verify the item exists with the correct crated status and mod.

**Common Causes and Solutions:**

| Cause | Symptom | Solution |
|-------|---------|----------|
| Resolution mismatch | Best match has confidence > 0.5 but item still Unknown | Use a screenshot whose resolution matches a database resolution (no display scaling) |
| Mod version mismatch | Item exists but pixels differ | Rebuild database with current mod version |
| Item not in database | No best match found | Add the item using `fs-tools add-icon` or rebuild database |
| Wrong category detected | Match found but wrong category | Check if screenshot has UI artifacts |
| Compression artifacts | Low confidence across all candidates | Use uncompressed PNG screenshots |

**Example: Inspecting a Low-Confidence Match**

If the error shows a best match with decent confidence (e.g., 0.62) but the item is still Unknown:

```bash
# Compare the detected icons against the database visually
fs-tools debug screenshot.png --database templates.h5
```

If the correct item appears only with low confidence, the screenshot likely doesn't match a
database resolution, or the database is built for a different mod version — rebuild the database
for the relevant mod rather than adjusting matching thresholds (which are fixed as of config v10).

**Example: Mod Version Mismatch**

If you're using a mod (e.g., clean-icons) and items show as Unknown:

```bash
# Verify mod templates exist (filter by mod in the visualizer)
fs-tools visualize --database templates.h5

# If templates exist but don't match, rebuild with current mod files
./build_database.sh
```

### Low Confidence Scores

**Problem:**
Items detected but with low confidence scores.

**This is normal in some cases:**
- Some items naturally have lower match confidence due to similar icons
- Lighting/gamma variations in screenshots
- Mod version mismatch between screenshot and database

**Solution:**
1. Check if items are correctly identified despite low confidence
   - Low confidence doesn't mean incorrect — verify the match is right

2. Verify screenshot quality (resolution, compression)

3. Check template quality:
   ```bash
   fs-tools visualize --database templates.h5
   ```

4. Rebuild database if using different mod versions

### Incorrect Quantities Detected

**Problem:**
Items detected correctly but quantities are wrong.

**Possible Causes:**

1. **OCR model issue**
   - OCR runs inside the external `fs-ocr` Rust engine (which uses a custom
     Tesseract model internally)
   - Check logs for OCR warnings

2. **Screenshot quality**
   - Quantity boxes must be clear and unobstructed
   - Avoid screenshots with UI overlays

3. **Calibration needed**
   - OCR detection boxes may need adjustment for your resolution
   - See [Configuration](configuration.md) OCR settings

## Screenshot Capture Issues

Capture works by binding a global hotkey (`scanner.capture_key`, e.g. `"F9"`).
When pressed, the runtime grabs the Foxhole game window (window title `"War"`)
and scans it locally — no server is involved.

### Capture Does Nothing / No Hotkey

**Problem:**
Pressing the hotkey has no effect, or no hotkey seems to be registered.

**Solution:**
The capture hotkey is not set. Configure `scanner.capture_key`:
- In the GUI: **Settings → Scanner** tab, set the capture key.
- Or via environment variable:
  ```bash
  export FS_SCANNER__CAPTURE_KEY=F9
  ```

Hotkeys with modifiers are supported (e.g. `Ctrl+F3`); a bare letter is also
fine.

### No Window Titled "War" Found

**Problem:**
```
No window titled 'War' found. Is Foxhole running?
```

**Solution:**
Foxhole must be running for capture to find its window. Launch the game and
try again.

### The Foxhole Window Is Minimized

**Problem:**
```
The Foxhole window is minimized
```

**Solution:**
Restore the Foxhole window before pressing the capture hotkey. Capture cannot
grab a minimized window.

### The Foxhole Window Must Be the Active Window

**Problem:**
```
The Foxhole window must be the active window
```

**Solution:**
Click or focus the game window before pressing the hotkey so Foxhole is the
active (foreground) window.

### Screenshot Capture Is Not Available on This Platform

**Problem:**
```
Screenshot capture is not available on this platform
```

**Solution:**
Capture needs a desktop environment with window-management and screen-grab
support — it is a Windows/desktop feature and requires `pywinctl`, `pynput`,
and Pillow's `ImageGrab` to load. On a headless Linux host capture will not
work. Use file-based scanning or SAV processing instead:
```bash
fs scan --image screenshot.png
fs sav world.sav
```

### Capture Won't Start (No Database)

**Problem:**
Capture fails to start because the scanner has no template database.

**Solution:**
The scanner needs a valid `database_path` (the template DB) to start capture.
See [Database Not Found](#database-not-found) for building or pointing at a
database.

## Template Generation Issues

### Missing Game Assets

**Problem:**
```
FileNotFoundError: Asset not found: path/to/icon.png
```

**Solution:**
1. Verify assets were extracted:
   ```bash
   ls raw_assets/  # Should contain PNG files
   ```

2. Re-run asset extraction:
   ```bash
   fs-tools extract-assets \
     --catalog catalog.json \
     --pak /path/to/game.pak \
     --output raw_assets/
   ```

### Template Generation Fails

**Problem:**
Template generation completes but produces no templates.

**Solution:**
1. Check catalog.json is valid:
   ```bash
   python -m json.tool catalog.json > /dev/null
   ```

2. Verify asset paths in catalog match extracted files

3. Check for errors in logs:
   ```bash
   export FS_LOGGING__LOG_LEVEL=DEBUG
   fs-tools generate-templates --catalog catalog.json --assets raw_assets/ --templates output/
   ```

## Configuration Issues

### Environment Variables Not Working

**Problem:**
Settings don't change when setting environment variables.

**Solution:**
1. Verify variable names use the `FS_<SECTION>__<KEY>` format:
   ```bash
   # Correct
   export FS_SCANNER__CAPTURE_KEY=F9

   # Wrong (single underscore instead of double underscore)
   export FS_SCANNER_CAPTURE_KEY=F9
   ```

2. Check variable is exported:
   ```bash
   echo $FS_SCANNER__CAPTURE_KEY
   ```

3. Restart the application after setting variables

### Config File Ignored

**Problem:**
Settings in `~/.fs_config` are not being used.

**Solution:**
1. Verify file location:
   ```bash
   ls -la ~/.fs_config
   ```

2. Check JSON syntax is valid (the config file is schema v10):
   ```bash
   python -m json.tool ~/.fs_config
   ```

3. Remember: Environment variables override the config file

## Getting Help

If you're still experiencing issues:

1. **Enable debug logging:**
   ```bash
   export FS_LOGGING__LOG_LEVEL=DEBUG
   export FS_LOGGING__LOG_FILE=/tmp/foxhole-scanner.log
   ```

2. **Collect information:**
   - Python version: `python --version`
   - `fs-ocr` engine version: `pip show fs-ocr`
   - Operating system
   - Screenshot resolution
   - Full error message and stack trace

3. **Check existing issues:**
   - Search [GitHub Issues](https://github.com/xurxogr/foxhole-stockpiles/issues)

4. **Create a new issue:**
   - Include all collected information
   - Provide a minimal reproduction example
   - Attach logs (redact sensitive information)

## Output / Webhook Issues

Results not reaching a configured output handler?

- **Nothing happens after a scan** — confirm at least one handler is configured
  under `output.handlers`. Add a `console` handler to verify items were detected.
- **Webhook returns 401** — check the handler's `auth_type`/`token` match what
  your endpoint expects.
- **Webhook never arrives** — verify the `url` is reachable; the connector retries
  only on connection timeouts (3×, 2s apart), not on HTTP 4xx/5xx.

See [Webhook Integration](webhooks.md) for full webhook setup and debugging.

## See Also

- [Configuration Guide](configuration.md) - All configuration options
- [Webhook Integration](webhooks.md) - Sending results to a webhook
