"""Translation management for multi-language support."""

import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal

from foxhole_stockpiles.core.utils import get_bundled_resource_path, is_frozen

logger = logging.getLogger(__name__)


def _get_exe_dir() -> Path:
    """Get the directory containing the executable or script.

    Returns:
        Path: Directory path where the executable/script is located.
    """
    if is_frozen():
        # Running as compiled executable (PyInstaller)
        return Path(sys.executable).parent
    else:
        # Running as script - use current working directory
        return Path.cwd()


# Resource path (relative to the project root / PyInstaller bundle root) of the
# translation catalog to load. Each self-contained app owns its own catalog and
# registers it via set_translations_resource() before the first get_translator()
# call. Defaults to the main foxhole_stockpiles app catalog.
_translations_resource = "foxhole_stockpiles/i18n/translations"


def set_translations_resource(resource: str) -> None:
    """Select which bundled translation catalog the translator loads from.

    Self-contained apps (e.g. fs-tools) call this at startup so each executable
    bundles and loads only its own strings.

    Args:
        resource (str): Path to the catalog directory relative to the project
            root / PyInstaller bundle root (e.g. "fs_tools/i18n/translations").
    """
    global _translations_resource
    _translations_resource = resource


def _get_bundled_translations_dir() -> Path:
    """Get the bundled translations directory.

    Returns:
        Path: Directory path for bundled translations.
    """
    return get_bundled_resource_path(_translations_resource)


def _get_user_translations_dir() -> Path:
    """Get the user-accessible translations directory.

    This is where users can place custom translation files to override
    or add to the bundled translations.

    Returns:
        Path: Directory path for user translations (next to executable).
    """
    return _get_exe_dir() / "i18n" / "translations"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override taking precedence.

    Args:
        base: Base dictionary (bundled translations).
        override: Override dictionary (user translations).

    Returns:
        Merged dictionary with override values taking precedence.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_json_file(path: Path) -> dict[str, Any] | None:
    """Load a JSON file safely.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON data, or None if file doesn't exist or is invalid.
    """
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read translation file %s: %s", path, e)
        return None


class TranslatorSignals(QObject):
    """Signals for translator events."""

    language_changed = Signal(str)  # Emits new language code


class Translator:
    """Handles loading and accessing translation strings."""

    def __init__(self, language: str = "en") -> None:
        """Initialize translator with a specific language.

        Args:
            language (str): Language code (e.g., 'en', 'es').
        """
        self.language = language
        self.translations: dict[str, Any] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """Load translation file for the current language.

        Loads bundled translations first, then merges user translations on top.
        User translations only need to contain the keys they want to override.
        Falls back to English if the requested language is not found.
        """
        filename = f"{self.language}.json"
        bundled_file = _get_bundled_translations_dir() / filename
        user_file = _get_user_translations_dir() / filename

        # Load bundled translations
        bundled_data = _load_json_file(bundled_file)

        if bundled_data is None:
            # Fallback to English if language file doesn't exist
            logger.warning(
                "Bundled translation file for '%s' not found, falling back to English",
                self.language,
            )
            bundled_file = _get_bundled_translations_dir() / "en.json"
            bundled_data = _load_json_file(bundled_file)

        if bundled_data is None:
            logger.error("English translation file not found")
            self.translations = {}
            return

        self.translations = bundled_data
        logger.debug("Loaded bundled translations for language: %s", self.language)

        # Merge user translations on top (if they exist)
        user_data = _load_json_file(user_file)
        if user_data is not None:
            self.translations = _deep_merge(self.translations, user_data)
            logger.info("Merged user translations from: %s", user_file)

    def get(self, key: str, **kwargs: Any) -> str:
        """Get a translation string by its key path.

        Args:
            key (str): Dot-separated path to the translation (e.g., 'app.menu.settings').
            **kwargs: Format parameters for the translation string.

        Returns:
            str: Translated and formatted string, or the key if not found.
        """
        keys = key.split(".")
        value: Any = self.translations

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    logger.debug("Translation key not found: %s", key)
                    return key  # Return key if translation not found
            else:
                return key

        if isinstance(value, str) and kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, IndexError, ValueError, AttributeError) as e:
                logger.warning("Cannot format translation %s: %r", key, e)
                return value

        return str(value) if value is not None else key

    def __call__(self, key: str, **kwargs: Any) -> str:
        """Shorthand for get method.

        Args:
            key (str): Dot-separated path to the translation.
            **kwargs: Format parameters for the translation string.

        Returns:
            str: Translated and formatted string.
        """
        return self.get(key, **kwargs)


# Global translator instance and signals
_translator: Translator | None = None
_signals: TranslatorSignals | None = None


def _get_signals() -> TranslatorSignals:
    """Get or create the global signals instance.

    Returns:
        TranslatorSignals: The global signals instance.
    """
    global _signals
    if _signals is None:
        _signals = TranslatorSignals()
    return _signals


def get_translator(language: str | None = None) -> Translator:
    """Get or create the global translator instance.

    Args:
        language (str | None): Language code to use. If None, keeps current or defaults to 'en'.

    Returns:
        Translator: The global translator instance.
    """
    global _translator

    if language is not None:
        _translator = Translator(language)
    elif _translator is None:
        _translator = Translator("en")

    return _translator


def set_language(language: str) -> None:
    """Change language and notify all listeners.

    Args:
        language (str): The new language code.
    """
    global _translator
    _translator = Translator(language)
    _get_signals().language_changed.emit(language)
    logger.info("Language changed to: %s", language)


def on_language_changed(callback: Callable[[str], None]) -> None:
    """Connect a callback to language change events.

    A bound method of a QObject is disconnected by Qt when that object is destroyed;
    any other callable stays connected until passed to ``off_language_changed``.

    Args:
        callback (Callable[[str], None]): Function to call when language changes.
            Receives the new language code as argument.
    """
    _get_signals().language_changed.connect(callback)


def off_language_changed(callback: Callable[[str], None]) -> None:
    """Disconnect a callback from language change events.

    Args:
        callback (Callable[[str], None]): The callback to disconnect.
    """
    try:
        _get_signals().language_changed.disconnect(callback)
    except (TypeError, RuntimeError, SystemError):
        # TypeError: Callback was not connected
        # RuntimeError: Qt signals object was already deleted during shutdown
        # SystemError: disconnect raised while a C++ object was being torn down
        pass


def t(key: str, **kwargs: Any) -> str:
    """Convenience function for translation.

    Args:
        key (str): Dot-separated path to the translation.
        **kwargs: Format parameters for the translation string.

    Returns:
        str: Translated and formatted string.
    """
    translator = get_translator()
    return translator(key, **kwargs)


def get_available_languages() -> list[tuple[str, str]]:
    """Get list of available languages.

    Scans both user and bundled translation directories.
    User translations take precedence for the same language code.

    Returns:
        list[tuple[str, str]]: List of tuples (language_code, language_name).
    """
    languages_dict: dict[str, str] = {}

    # First, load bundled translations
    bundled_dir = _get_bundled_translations_dir()
    if bundled_dir.exists():
        for translation_file in bundled_dir.glob("*.json"):
            language_code = translation_file.stem
            try:
                with open(translation_file, encoding="utf-8") as f:
                    data = json.load(f)
                    language_name = data.get("language_name", language_code)
                    languages_dict[language_code] = language_name
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read language file %s: %s", translation_file, e)
                languages_dict[language_code] = language_code

    # Then, load user translations (override bundled ones with same code)
    user_dir = _get_user_translations_dir()
    if user_dir.exists():
        for translation_file in user_dir.glob("*.json"):
            language_code = translation_file.stem
            try:
                with open(translation_file, encoding="utf-8") as f:
                    data = json.load(f)
                    language_name = data.get("language_name", language_code)
                    languages_dict[language_code] = language_name
                    logger.debug("Found user translation: %s (%s)", language_name, language_code)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read user language file %s: %s", translation_file, e)
                if language_code not in languages_dict:
                    languages_dict[language_code] = language_code

    if not languages_dict:
        return [("en", "English")]

    # Sort by language code and return as list of tuples
    return sorted(languages_dict.items(), key=lambda x: x[0])
