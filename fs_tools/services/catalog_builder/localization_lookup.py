"""Localization service for resolving text GUIDs to localized strings.

This module handles parsing and querying of UE4 .locres files for
multi-language text lookup.
"""

import logging
import struct
from io import BufferedReader
from pathlib import Path
from typing import Any

# Magic number for modern locres files (UE4 FTextLocalizationResource)
LOCRES_MAGIC = bytes.fromhex("0e147475674a03fc4a15909dc3377f1b")

# Supported languages and their folder names
SUPPORTED_LANGUAGES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
}


class LocalizationLookup:
    """Service for loading and querying localized strings.

    This service parses UE4 .locres files and provides methods to
    look up localized strings by their GUID keys.
    """

    def __init__(self, localization_dir: Path, default_language: str = "en") -> None:
        """Initialize the localization service.

        Args:
            localization_dir (Path): Path to the Localization directory containing
                language subdirectories (e.g., War/Content/Localization).
            default_language (str): Default language code for lookups (default: "en").
        """
        self.localization_dir = localization_dir.resolve()
        self.default_language = default_language
        self.logger = logging.getLogger(__name__)

        # Cache for loaded localizations: {language: {guid: text}}
        self._cache: dict[str, dict[str, str]] = {}

        # Track which locres files have been loaded
        self._loaded_files: set[str] = set()

    def _read_fstring(self, f: BufferedReader) -> str | None:
        """Read UE4 FString - handles both ANSI and Unicode.

        Args:
            f (BufferedReader): File handle to read from.

        Returns:
            str | None: Decoded string or None if read failed.
        """
        length_bytes = f.read(4)
        if len(length_bytes) < 4:
            return None

        length = struct.unpack("<i", length_bytes)[0]
        if length == 0:
            return ""

        if length < 0:
            # Unicode (UTF-16)
            char_count = -length
            data = f.read(char_count * 2)
            if len(data) < char_count * 2:
                return None
            return data.decode("utf-16-le").rstrip("\x00")
        else:
            # ANSI
            data = f.read(length)
            if len(data) < length:
                return None
            return data.decode("latin-1").rstrip("\x00")

    def _read_text_key(self, f: BufferedReader) -> tuple[int, str | None]:
        """Read FTextKey - hash + string.

        Args:
            f (BufferedReader): File handle to read from.

        Returns:
            tuple[int, str | None]: Tuple of (hash, string).
        """
        str_hash = struct.unpack("<I", f.read(4))[0]
        string = self._read_fstring(f)
        return str_hash, string

    def _read_string_array(self, f: BufferedReader, str_array_offset: int) -> list[str]:
        """Read the compact string array table from a locres file.

        Args:
            f (BufferedReader): File handle to read from.
            str_array_offset (int): Byte offset of the string array, or -1 if absent.

        Returns:
            list[str]: The strings in the string array, in index order.
        """
        string_array: list[str] = []
        if str_array_offset == -1:
            return string_array

        current_pos = f.tell()
        f.seek(str_array_offset)

        str_count = struct.unpack("<i", f.read(4))[0]
        for _ in range(str_count):
            s = self._read_fstring(f)
            if s is None:
                break
            struct.unpack("<I", f.read(4))[0]  # source string hash
            string_array.append(s)

        # Return to namespace section
        f.seek(current_pos)
        return string_array

    def _read_namespace_strings(
        self, f: BufferedReader, version: int, string_array: list[str]
    ) -> dict[str, str]:
        """Read all namespace/key/string entries following the string array.

        Args:
            f (BufferedReader): File handle to read from.
            version (int): Locres format version.
            string_array (list[str]): String array read from the file (for version >= 1).

        Returns:
            dict[str, str]: Dict mapping GUID keys to localized strings.
        """
        strings: dict[str, str] = {}

        namespace_count = struct.unpack("<I", f.read(4))[0]
        for _ in range(namespace_count):
            self._read_text_key(f)  # namespace key (hash + string)

            key_count = struct.unpack("<I", f.read(4))[0]
            for _ in range(key_count):
                _, key_string = self._read_text_key(f)
                struct.unpack("<I", f.read(4))[0]  # source string hash

                if version >= 1:
                    str_index = struct.unpack("<i", f.read(4))[0]
                    value = string_array[str_index] if 0 <= str_index < len(string_array) else ""
                else:
                    value = self._read_fstring(f) or ""

                # Use key_string as the key (this is the GUID)
                if key_string:
                    strings[key_string] = value

        return strings

    def _parse_locres(self, filepath: Path) -> dict[str, str]:
        """Parse a UE4 .locres file.

        Args:
            filepath (Path): Path to the .locres file.

        Returns:
            dict[str, str]: Dict mapping GUID keys to localized strings.
        """
        strings: dict[str, str] = {}

        try:
            with open(filepath, "rb") as f:
                # Check magic (16 bytes)
                magic = f.read(16)
                if magic != LOCRES_MAGIC:
                    self.logger.warning("Legacy locres format not supported: %s", filepath)
                    return strings

                # Version (1 byte)
                version = struct.unpack("<B", f.read(1))[0]

                # String array offset (8 bytes) - version >= 1 (Compact)
                str_array_offset = struct.unpack("<q", f.read(8))[0]
                string_array = self._read_string_array(f, str_array_offset)

                # Skip entries count if version >= 2 (Optimized_CRC32)
                if version >= 2:
                    struct.unpack("<I", f.read(4))[0]

                strings = self._read_namespace_strings(f, version, string_array)

        except Exception as e:  # noqa: BLE001 - malformed locres files vary by UE version
            self.logger.error("Error parsing locres file %s: %s", filepath, e)

        return strings

    def _load_language(self, language: str) -> dict[str, str]:
        """Load all locres files for a language.

        Args:
            language (str): Language code (e.g., "en", "de").

        Returns:
            dict[str, str]: Dict mapping GUID keys to localized strings.
        """
        if language in self._cache:
            return self._cache[language]

        strings: dict[str, str] = {}

        # Find all locres directories (Foxhole-Content, Foxhole-CodeStrings, etc.)
        if not self.localization_dir.exists():
            self.logger.warning("Localization directory not found: %s", self.localization_dir)
            return strings

        for loc_subdir in self.localization_dir.iterdir():
            if not loc_subdir.is_dir():
                continue

            lang_dir = loc_subdir / language
            if not lang_dir.exists():
                continue

            for locres_file in lang_dir.glob("*.locres"):
                file_key = f"{language}:{locres_file}"
                if file_key in self._loaded_files:
                    continue

                parsed = self._parse_locres(locres_file)
                strings.update(parsed)
                self._loaded_files.add(file_key)

                self.logger.debug("Loaded %d strings from %s", len(parsed), locres_file.name)

        self._cache[language] = strings
        self.logger.debug("Loaded %d total strings for language '%s'", len(strings), language)
        return strings

    def get(self, guid: str, language: str | None = None) -> str | None:
        """Get localized string for a GUID.

        Args:
            guid (str): The GUID key (e.g., "8BB336F4459740A6ADA7B28B2D91748B").
            language (str | None): Language code (default: self.default_language).

        Returns:
            str | None: Localized string or None if not found.
        """
        if language is None:
            language = self.default_language

        strings = self._load_language(language)
        return strings.get(guid)

    def get_with_fallback(self, guid: str, language: str | None = None) -> str:
        """Get localized string with fallback to English, then GUID.

        Args:
            guid (str): The GUID key.
            language (str | None): Language code (default: self.default_language).

        Returns:
            str: Localized string, English fallback, or original GUID.
        """
        if language is None:
            language = self.default_language

        # Try requested language
        result = self.get(guid, language)
        if result:
            return result

        # Fallback to English
        if language != "en":
            result = self.get(guid, "en")
            if result:
                return result

        # Return original GUID
        return guid

    def get_all_languages(self, guid: str) -> dict[str, str]:
        """Get localized string in all available languages.

        Args:
            guid (str): The GUID key.

        Returns:
            dict[str, str]: Dict mapping language codes to localized strings.
        """
        result = {}
        for lang_code in SUPPORTED_LANGUAGES:
            text = self.get(guid, lang_code)
            if text:
                result[lang_code] = text
        return result

    def is_guid(self, value: Any) -> bool:
        """Check if a value looks like a localization GUID.

        Args:
            value (Any): Value to check.

        Returns:
            bool: True if value appears to be a GUID.
        """
        if not isinstance(value, str):
            return False
        if len(value) != 32:
            return False
        return all(c in "0123456789ABCDEFabcdef" for c in value)

    def get_stats(self) -> dict[str, int]:
        """Get statistics about loaded localizations.

        Returns:
            dict[str, int]: Dict with counts per language.
        """
        return {lang: len(strings) for lang, strings in self._cache.items()}
