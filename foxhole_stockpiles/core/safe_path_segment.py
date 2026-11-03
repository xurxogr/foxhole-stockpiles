"""Turn text others can control into a safe file or directory name."""

import re

# Path separators, control characters and what else Windows refuses in a name.
_UNSAFE_PATH_CHARS = re.compile(r'[\\/<>:"|?*\x00-\x1f]')
# Windows device names, reserved with or without an extension.
_RESERVED_NAME = re.compile(r"^(con|prn|aux|nul|com\d|lpt\d)(\..*)?$", re.IGNORECASE)


def safe_path_segment(value: str) -> str:
    """Make a value safe to use as one segment of a path.

    Stockpile names, hexes and types originate from OCR-read in-game text, `.sav` data
    or the clipboard, which others can control. Without this, a stockpile named e.g.
    ".." or "../../etc/foo" could escape the configured directory, and "a:b" would
    write to an NTFS alternate data stream.

    Args:
        value (str): The raw value.

    Returns:
        str: A non-empty value that is neither a relative segment nor a reserved
            name. Letters of any alphabet are kept.
    """
    cleaned = _UNSAFE_PATH_CHARS.sub("_", value).strip(" .")
    if not cleaned:
        return "_"
    if _RESERVED_NAME.match(cleaned):
        return f"_{cleaned}"
    return cleaned
